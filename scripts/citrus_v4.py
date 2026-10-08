#!/usr/bin/env python3
"""Citrus v4 audit/export and resumable, source-grounded candidate generation.

No function in this module approves generated records. Completion is computed
from reviewed records, never from a requested quota or a successful process exit.
"""
from __future__ import annotations
import argparse
import collections
import hashlib
import json
import pathlib
import re
import sqlite3
import sys
import time
import unicodedata

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / 'datasets/v4'
ROLES = {'system', 'user', 'assistant', 'tool'}

def read_json(path):
    return json.loads(pathlib.Path(path).read_text(encoding='utf-8'))

def write_json(path, value):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))

def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()

def normalize(text):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', text)).casefold().strip()

def content_hash(row):
    # Approval is tied to the exact substantive data, not just a reusable ID.
    fields = ['category','kind','subtype','mode','family_id','messages','tools',
              'sources','provenance','runtime_verified','tool_execution_verified','evidence']
    return digest({k: row.get(k) for k in fields})

def validate_schema(value, schema, where='arguments'):
    """Validate the provider's bounded JSON-schema subset; not Roblox behavior."""
    typ = schema.get('type')
    types = {'object': dict, 'array': list, 'string': str, 'boolean': bool,
             'integer': int, 'number': (int, float)}
    if typ in types and (not isinstance(value, types[typ]) or
                        (typ in ('integer','number') and isinstance(value, bool))):
        raise ValueError(f'{where}: expected {typ}')
    if 'enum' in schema and value not in schema['enum']:
        raise ValueError(f'{where}: value outside enum')
    if typ == 'object':
        missing = set(schema.get('required', [])) - set(value)
        extra = set(value) - set(schema.get('properties', {}))
        if missing: raise ValueError(f'{where}: missing {sorted(missing)}')
        if extra and schema.get('additionalProperties') is False:
            raise ValueError(f'{where}: unexpected {sorted(extra)}')
        for key, item in value.items():
            if key in schema.get('properties', {}):
                validate_schema(item, schema['properties'][key], where + '.' + key)
    elif typ == 'array':
        if len(value) < schema.get('minItems', 0) or len(value) > schema.get('maxItems', float('inf')):
            raise ValueError(f'{where}: invalid length')
        for i, item in enumerate(value): validate_schema(item, schema.get('items', {}), f'{where}[{i}]')
    elif typ in ('number','integer'):
        import math
        if not math.isfinite(value): raise ValueError(f'{where}: non-finite number')
        if value < schema.get('minimum', -float('inf')) or value > schema.get('maximum', float('inf')):
            raise ValueError(f'{where}: out of range')

def validate_row(row, config, source_ids, catalog):
    errors = []
    def need(ok, message):
        if not ok: errors.append(message)
    if not isinstance(row, dict): return ['record must be an object']
    need(row.get('category') in {c['id'] for c in config['categories']}, 'unknown category')
    need(row.get('kind') in ('knowledge', 'practice'), 'unknown kind')
    need(row.get('mode') in ('plan','agent','explain'), 'unknown mode')
    for key in ('id','family_id','subtype'):
        need(isinstance(row.get(key), str) and bool(row.get(key)), 'missing ' + key)
    need(row.get('review_status') in ('draft','approved','rejected'), 'invalid review status')
    need(type(row.get('runtime_verified')) is bool, 'runtime_verified must be boolean')
    need(type(row.get('tool_execution_verified')) is bool, 'tool_execution_verified must be boolean')
    need(isinstance(row.get('provenance'), dict), 'provenance required')
    sources = row.get('sources', [])
    need(isinstance(sources, list) and bool(sources), 'source references required')
    if isinstance(sources, list): need(all(s in source_ids for s in sources), 'unknown source reference')
    messages = row.get('messages')
    if not isinstance(messages, list) or len(messages) < 2: return errors + ['conversation too short']
    need(any(m.get('role') == 'user' for m in messages), 'missing user')
    need(messages[-1].get('role') == 'assistant', 'conversation must end with assistant')
    tools = row.get('tools', [])
    if not isinstance(tools, list): return errors + ['tools must be a list']
    supplied = {}
    for t in tools:
        name = t.get('function', {}).get('name')
        need(name in catalog, 'unregistered tool: ' + str(name))
        if name in catalog: need(t == catalog[name], 'tool definition differs from captured schema')
        supplied[name] = t
    pending, seen = {}, set()
    for i, message in enumerate(messages):
        role, text = message.get('role'), message.get('content')
        need(role in ROLES, f'invalid role at {i}')
        calls = message.get('tool_calls', [])
        need(text is None or isinstance(text, str), f'invalid content at {i}')
        need(bool(text) or bool(calls), f'empty message at {i}')
        if role != 'tool': need(not pending, 'missing tool response before next conversation turn')
        if calls:
            need(role == 'assistant', 'only assistant may call tools')
            need(row.get('mode') != 'plan', 'Plan mode forbids every tool call')
            for call in calls:
                cid = call.get('id')
                fn = call.get('function', {})
                name, args = fn.get('name'), fn.get('arguments')
                need(bool(cid) and cid not in seen, 'missing or repeated tool_call_id')
                need(call.get('type') == 'function', 'invalid tool call type')
                need(name in supplied, 'called tool is absent from tools')
                need(isinstance(args, dict), 'canonical arguments must be objects, not encoded strings')
                if name in supplied and isinstance(args, dict):
                    try: validate_schema(args, supplied[name]['function']['parameters'])
                    except ValueError as e: errors.append(str(e))
                pending[cid] = name
                seen.add(cid)
        if role == 'tool':
            cid = message.get('tool_call_id')
            need(cid in pending, 'orphan or repeated tool response')
            if cid in pending:
                need(message.get('name') == pending[cid], 'tool response name mismatch')
                del pending[cid]
            try: json.loads(text or '')
            except (ValueError, TypeError): errors.append('tool response must contain JSON')
        if role == 'assistant' and isinstance(text, str):
            need(text.count('```') % 2 == 0, 'unbalanced code fence')
            for code in re.findall(r'```(?:luau|lua)\n(.*?)```', text, re.S):
                # Concrete failures observed in the previous generation run.
                need(not re.search(r'GetService\s*\(\s*[\"\'](?:RemoteEvent|RemoteFunction|Part|Humanoid)[\"\']', code),
                     'Instance class incorrectly used as a service')
                need(not re.search(r'\b(?:player|Player|plr):(?:SetData|GetData|SetState)\s*\(', code),
                     'unsupported Player method in answer code')
                need(not re.search(r'\bR6LegPart\b', code), 'undefined R6LegPart type')
    need(not pending, 'unanswered tool calls')
    if seen:
        need(row.get('tool_execution_verified') is True, 'tool outputs require actual isolated execution')
        need(bool(row.get('evidence', {}).get('tool_execution')), 'missing tool execution evidence')
    if row.get('runtime_verified'):
        need(bool(row.get('evidence', {}).get('runtime')), 'missing runtime evidence')
    return errors

def read_rows(paths):
    for path in paths:
        with pathlib.Path(path).open(encoding='utf-8') as stream:
            for n, line in enumerate(stream, 1):
                if line.strip():
                    try: yield json.loads(line), str(path) + ':' + str(n)
                    except ValueError as exc: yield {'_parse_error': str(exc)}, str(path) + ':' + str(n)

def audit(root=DATA, require_complete=False):
    root = pathlib.Path(root)
    config = read_json(root / 'config.json')
    sources = {s['id'] for s in read_json(root / 'sources.json')}
    catalog = {t['function']['name']: t for t in read_json(root / 'tool_schemas.json')}
    reviews_path = root / 'reviews.json'
    reviews = read_json(reviews_path) if reviews_path.exists() else {}
    counts, kinds, reviewed = collections.Counter(), collections.Counter(), []
    errors, warnings, rows = [], [], []
    ids, signatures, surfaces = set(), {}, {}
    family_splits = {}
    for row, loc in read_rows(sorted((root / 'candidates').glob('*.jsonl'))):
        problems = validate_row(row, config, sources, catalog)
        if row.get('id') in ids: problems.append('duplicate id')
        ids.add(row.get('id'))
        content = canonical(row.get('messages', []))
        exact = normalize(content)
        surface = re.sub(r'\d+', '#', exact)
        if exact in signatures: problems.append('exact conversation duplicate of ' + signatures[exact])
        elif surface in surfaces:
            warnings.append({'id': row.get('id'), 'type':'numeric_variant', 'similar_to': surfaces[surface]})
        signatures[exact] = str(row.get('id'))
        surfaces[surface] = str(row.get('id'))
        errors.extend({'location':loc, 'id':row.get('id'), 'error':e} for e in problems)
        if problems: continue
        rows.append(row)
        counts[(row['category'], row['kind'])] += 1
        kinds[row['kind']] += 1
        review = reviews.get(row['id'])
        if row['review_status'] == 'approved':
            valid = (isinstance(review,dict) and review.get('content_sha256') == content_hash(row)
                     and review.get('decision') == 'approved' and review.get('reviewer')
                     and review.get('factual_checked') is True
                     and review.get('diversity_checked') is True
                     and review.get('source_rights_checked') is True
                     and review.get('notes'))
            if not valid: errors.append({'id':row['id'],'error':'approval lacks matching substantive review'})
            else: reviewed.append(row)
        family = config.get('family_aliases', {}).get(row['family_id'], row['family_id'])
        family_splits.setdefault(family, split_for(family))
    expected = {(c['id'],k):c[k] for c in config['categories'] for k in ('knowledge','practice')}
    accepted_counts = collections.Counter((r['category'],r['kind']) for r in reviewed)
    complete = len(reviewed) == config['target_total'] and all(accepted_counts[k] == n for k,n in expected.items())
    if require_complete and not complete: errors.append({'error':'reviewed totals/category allocations have not reached the target'})
    report = {
        'target_total':config['target_total'], 'actual_valid_candidates':len(rows),
        'actual_counts':dict(kinds),'approved_total':len(reviewed),
        'remaining_to_approve':max(0,config['target_total']-len(reviewed)),
        'completion':complete and not errors, 'errors':errors, 'warnings':warnings,
        'category_counts':[{**c,'actual_knowledge':counts[(c['id'],'knowledge')],
                            'actual_practice':counts[(c['id'],'practice')]} for c in config['categories']],
        'tool_execution_records':sum(r['tool_execution_verified'] for r in rows),
        'runtime_verified_records':sum(r['runtime_verified'] for r in rows),
        'grouped_families':len(family_splits),
        'checks':['record structure','tool schemas and response pairing','Plan mode boundary',
                  'known bad APIs','exact duplicates','numeric-variant screening','approval hash'],
        'limitations':['Numeric-variant screening is not semantic deduplication.',
                      'Syntax compilation does not prove Roblox runtime behavior.',
                      'Automated validation does not approve factual correctness.'],
    }
    return rows, reviewed, report

def split_for(family):
    value = int(hashlib.sha256(family.encode()).hexdigest()[:8], 16) % 100
    return 'train' if value < 80 else 'validation' if value < 90 else 'test'

def export(root, out, allow_partial=False):
    rows, approved, report = audit(root, require_complete=not allow_partial)
    if report['errors']: raise ValueError('Export blocked: ' + canonical(report['errors'][:5]))
    out = pathlib.Path(out)
    out.mkdir(parents=True, exist_ok=True)
    counts = collections.Counter()
    handles = {s:(out / (s+'.jsonl')).open('w',encoding='utf-8') for s in ('train','validation','test')}
    config = read_json(pathlib.Path(root)/'config.json')
    membership = []
    try:
        for row in approved:
            family = config.get('family_aliases', {}).get(row['family_id'], row['family_id'])
            split = split_for(family)
            # Audit metadata stays separate from the model's training messages.
            payload = {'messages':row['messages'], 'tools':row.get('tools',[])}
            handles[split].write(canonical(payload)+'\n')
            counts[split] += 1
            membership.append({'id':row['id'],'family':family,'split':split,'kind':row['kind'],'category':row['category']})
    finally:
        for h in handles.values(): h.close()
    write_json(out/'export_manifest.json', {'counts':dict(counts),'complete':report['completion'],
                                          'family_grouped':True,'target_total':report['target_total']})
    write_json(out/'membership.json',membership)
    return report

GENERATOR_SYSTEM = '''Create original Thai training examples for Citrus, a Roblox development agent.
Use the supplied factual anchors and task scope. Return only one JSON object with question,
answer, family_id, subtype, and source_ids. Knowledge answers must synthesize and explain;
never paste source text. Practical answers must solve a concrete task and contain complete
scoped code if the question requests code. Do not claim unperformed tests. Do not emit fake
tool calls or tool outputs: tool trajectories are collected separately from an isolated executor.
Plan mode never calls tools. Do not invent object paths, APIs, asset IDs or unknown permissions.
Do not repeat old tasks by changing names, numbers or wording. Give concise outcome rationale,
not hidden chain-of-thought. Outputs are candidates and are not approved for training.'''

def parse_generation(text):
    text = text.strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*','',text)
        text = re.sub(r'\s*```$','',text)
    value = json.loads(text)
    if not isinstance(value,dict): raise ValueError('Expected one JSON object')
    for key in ('question','answer','family_id','subtype'):
        if not isinstance(value.get(key),str) or not value[key].strip(): raise ValueError('Missing '+key)
    if len(value['answer']) < 120: raise ValueError('Answer is too short for this generation pass')
    if not isinstance(value.get('source_ids'),list) or not value['source_ids']: raise ValueError('Sources required')
    return value

def generate(args):
    # Model/dependencies are imported only for an explicitly requested run.
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    except ImportError as exc:
        raise RuntimeError('Generation runtime is absent; use the supplied GPU notebook. No data was generated.') from exc
    if not torch.cuda.is_available(): raise RuntimeError('Configured generation requires a CUDA GPU; no run started.')
    root = pathlib.Path(args.root)
    config = read_json(root/'config.json')
    sources_list = read_json(root/'sources.json')
    source_ids = {s['id'] for s in sources_list}
    catalog = {t['function']['name']:t for t in read_json(root/'tool_schemas.json')}
    existing, _, report = audit(root)
    if report['errors']: raise RuntimeError('Existing data fails audit; correct it before generation.')
    args.out.mkdir(parents=True,exist_ok=True)
    db = sqlite3.connect(args.out/'progress.sqlite')
    db.execute('CREATE TABLE IF NOT EXISTS records (id TEXT PRIMARY KEY, category TEXT, kind TEXT, question TEXT UNIQUE, answer TEXT UNIQUE, payload TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')
    signature = digest(config)
    previous = db.execute("SELECT value FROM settings WHERE key='config_sha256'").fetchone()
    if previous and previous[0] != signature: raise RuntimeError('Checkpoint uses a different target/config. Do not overwrite it.')
    db.execute("INSERT OR REPLACE INTO settings VALUES ('config_sha256',?)",(signature,))
    db.commit()
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    quant = BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type='nf4',bnb_4bit_use_double_quant=True,bnb_4bit_compute_dtype=torch.float16)
    model = AutoModelForCausalLM.from_pretrained(args.model,device_map='auto',torch_dtype=torch.float16,quantization_config=quant)
    model.eval()
    starting = collections.Counter((r['category'],r['kind']) for r in existing)
    known_questions = {normalize(m['content']) for r in existing for m in r['messages'] if m['role']=='user'}
    known_answers = {normalize(r['messages'][-1]['content']) for r in existing}
    started, accepted, failures = time.monotonic(), 0, 0
    try:
        while accepted < args.limit and time.monotonic()-started < args.minutes*60:
            totals = starting.copy()
            totals.update({(c,k):n for c,k,n in db.execute('SELECT category,kind,COUNT(*) FROM records GROUP BY category,kind')})
            available=[(totals[(c['id'],k)]/c[k],c,k) for c in config['categories'] for k in ('knowledge','practice') if totals[(c['id'],k)]<c[k]]
            if not available: break
            _,cat,kind=min(available,key=lambda x:x[0])
            recent=[r[0] for r in db.execute('SELECT question FROM records WHERE category=? ORDER BY rowid DESC LIMIT 12',(cat['id'],))]
            anchors=[s for s in sources_list if s['id'] in cat['sources']]
            topic=cat['topics'][totals[(cat['id'],kind)] % len(cat['topics'])]
            prompt=canonical({'kind':kind,'category':cat['id'],'topics':cat['topics'],
                              'focus_topic':topic,
                              'factual_anchors':anchors,'avoid_previous_questions':recent,
                              'mode':'plan' if cat['id']=='mode_scope' else 'explain'})
            chat=tokenizer.apply_chat_template([{'role':'system','content':GENERATOR_SYSTEM},{'role':'user','content':prompt}],tokenize=False,add_generation_prompt=True)
            inputs=tokenizer(chat,return_tensors='pt').to(model.device)
            with torch.inference_mode():
                result=model.generate(**inputs,max_new_tokens=args.max_tokens,do_sample=True,temperature=.7,top_p=.9,pad_token_id=tokenizer.eos_token_id)
            try:
                item=parse_generation(tokenizer.decode(result[0,inputs['input_ids'].shape[1]:],skip_special_tokens=True))
                q,a=normalize(item['question']),normalize(item['answer'])
                if q in known_questions or a in known_answers: raise ValueError('Duplicate of authored data')
                if not set(item['source_ids']).issubset(set(cat['sources'])): raise ValueError('Ungrounded source reference')
                # The teacher cannot mint a new family per paraphrase and leak it
                # into another evaluation split.
                row={'id':'citrus-v4-gen-'+digest([q,a])[:24], 'family_id':cat['id']+'/topic-'+digest(topic)[:12],
                     'category':cat['id'],'kind':kind,'subtype':item['subtype'],'mode':'plan' if cat['id']=='mode_scope' else 'explain',
                     'messages':[{'role':'user','content':item['question']},{'role':'assistant','content':item['answer']}],
                     'tools':[],'sources':item['source_ids'],'provenance':{'method':'local_model','model':args.model},
                     'review_status':'draft','runtime_verified':False,'tool_execution_verified':False,'evidence':{}}
                errors=validate_row(row,config,source_ids,catalog)
                if errors: raise ValueError('; '.join(errors))
                db.execute('INSERT INTO records VALUES (?,?,?,?,?,?)',(row['id'],cat['id'],kind,q,a,canonical(row)))
                db.commit(); accepted+=1; failures=0
                print(canonical({'accepted_this_run':accepted,'category':cat['id'],'kind':kind}),flush=True)
            except (ValueError,sqlite3.IntegrityError) as exc:
                failures+=1; print(canonical({'rejected':str(exc)}),flush=True)
                if failures>=20: break
    finally:
        checkpoint=args.out/'generated_candidates.jsonl.tmp'
        with checkpoint.open('w',encoding='utf-8') as handle:
            for payload, in db.execute('SELECT payload FROM records ORDER BY id'): handle.write(payload+'\n')
        checkpoint.replace(args.out/'generated_candidates.jsonl')
        generated=db.execute('SELECT COUNT(*) FROM records').fetchone()[0]
        write_json(args.out/'status.json',{'generated_candidates':generated,'approved_total':0,
                   'target_total':config['target_total'],'target_complete':False,
                   'status':'draft_checkpoint','next':'review, deduplicate, replay tool cases, and verify code before import/export'})
        db.close()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    a=sub.add_parser('audit'); a.add_argument('--root',type=pathlib.Path,default=DATA)
    a.add_argument('--require-complete',action='store_true'); a.add_argument('--report',type=pathlib.Path)
    e=sub.add_parser('export'); e.add_argument('--root',type=pathlib.Path,default=DATA)
    e.add_argument('--out',type=pathlib.Path,required=True); e.add_argument('--allow-partial',action='store_true')
    g=sub.add_parser('generate'); g.add_argument('--root',type=pathlib.Path,default=DATA)
    g.add_argument('--out',type=pathlib.Path,required=True); g.add_argument('--model',required=True)
    g.add_argument('--limit',type=int,default=200); g.add_argument('--minutes',type=float,default=60)
    g.add_argument('--max-tokens',type=int,default=3000)
    args=parser.parse_args()
    try:
        if args.command=='generate':
            if min(args.limit,args.minutes,args.max_tokens)<=0: parser.error('limits must be positive')
            generate(args); return 0
        if args.command=='export': report=export(args.root,args.out,args.allow_partial)
        else: _,_,report=audit(args.root,args.require_complete)
        if getattr(args,'report',None): write_json(args.report,report)
        print(json.dumps(report,ensure_ascii=False,indent=2))
        return 1 if report['errors'] else 0
    except (ValueError,RuntimeError) as exc:
        print(str(exc),file=sys.stderr); return 2

if __name__=='__main__': raise SystemExit(main())
