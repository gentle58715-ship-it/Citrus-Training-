#!/usr/bin/env python3
"""Resumable local-model generation of draft candidates; never auto-approves."""
import argparse
import collections
import hashlib
import json
import os
import pathlib
import re
import sqlite3
import time
import unicodedata

TOPICS = {
    'luau': ['optional types', 'tables and aliasing', 'pure functions', 'error handling', 'iteration', 'module interfaces', 'numeric edge cases'],
    'api_services': ['Instance lifecycle', 'service access', 'event connections', 'replication timing', 'hierarchy lookup', 'class checks', 'cleanup'],
    'client_server': ['purchase requests', 'reward claims', 'equip requests', 'cooldowns', 'prediction reconciliation', 'remote contracts', 'authorization'],
    'datastore': ['load failures', 'UpdateAsync purity', 'schema migration', 'retry budgets', 'session conflicts', 'save lifecycle', 'idempotent writes'],
    'animation_r6': ['walk cycles', 'sprint cycles', 'crouch approximation', 'local joint axes', 'loop seams', 'export transforms', 'arm counterbalance'],
    'animation_r15': ['rig inspection', 'retargeting', 'foot sliding', 'crouch transitions', 'IK blending', 'animation layers', 'respawn lifecycle'],
    'gui_ui': ['responsive layout', 'text wrapping', 'layout ordering', 'button lifecycle', 'pending states', 'tween interruption', 'input accessibility'],
    'mesh_3d': ['silhouette preservation', 'UV seams', 'normals', 'collision geometry', 'memory budgets', 'asset permissions', 'mesh export'],
    'physics': ['network ownership', 'raycast filtering', 'constraints', 'collision groups', 'moving platforms', 'assembly lifecycle', 'server validation'],
    'security': ['remote validation', 'rate limits', 'numeric validation', 'ownership checks', 'request replay', 'server catalogs', 'role authorization'],
    'optimization': ['profiling baselines', 'allocation', 'cache invalidation', 'network deltas', 'event driven updates', 'pool cleanup', 'render cost'],
    'debugging': ['stack traces', 'nil causes', 'race conditions', 'respawn references', 'fault injection', 'cyclic requires', 'minimal reproduction'],
    'architecture': ['inventory contracts', 'quest systems', 'purchase services', 'module dependencies', 'versioned schema', 'undo design', 'transaction boundaries'],
    'tool_calling': ['schema inspection', 'read before patch', 'conflict recovery', 'timeout ambiguity', 'result verification', 'untrusted tool content', 'missing tool capability'],
    'project_editing': ['scope preservation', 'diff review', 'checkpoints', 'concurrent edits', 'target ambiguity', 'asset versions', 'regression checks'],
}

ANCHORS = {
    'datastore': 'UpdateAsync callbacks must not yield and may run repeatedly. Separate missing data from a failed read. Never award rewards inside a retryable callback.',
    'animation_r6': 'A standard R6 leg is one rigid part with no knee joint. Inspect actual local axes. Respect user scope and describe custom-rig changes explicitly.',
    'animation_r15': 'Inspect actual rig and joint types; do not assume all R15 rigs use Motor6D. Current AvatarJointUpgrade rigs may use AnimationConstraint.',
    'client_server': 'The server owns consequential state. Validate type, range, permission, context and rate. Client requests intent, not an authoritative result.',
    'security': 'Treat all client input as untrusted. Check finite numbers and ownership. UI visibility is not authorization. Never trust a client supplied price.',
    'mesh_3d': 'Visual geometry and collision may differ. EditableMesh changes do not automatically rebuild all physics geometry. Report unsupported operations honestly.',
    'tool_calling': 'Use only provided tool schemas. Never invent tool outputs or claim execution. Without a schema provide a plan, not fabricated tool-call JSON.',
}

SYSTEM = '''You author original Roblox/Luau educational training examples in Thai.
Return ONLY a JSON array. Each item has question and answer (strings).
Write complete, technically precise, non-repetitive answers. Do not paste raw documentation.
Knowledge questions teach concepts with concise rationale and examples when useful.
Practical questions request a specific implementation, diagnosis, test, or design;
answer that exact task. If requesting code, include complete scoped Luau code,
placement/context, assumptions and concrete test cases. Do not claim code was run.
Do not manufacture unknown API methods, asset IDs, tool schemas or successful actions.
Explain missing prerequisites honestly, but do not make every example a refusal.
Generate substantially different situations, not renamed or numerically varied copies.
No hidden chain-of-thought: use concise explanations of the resulting solution.
Avoid tasks requiring images not supplied. Respect changes limited by the user.
Outputs are draft candidates, not verified facts or training-ready examples.'''

def normalize(s):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', s)).strip().casefold()

def parse_output(text):
    text = text.strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
    value = json.loads(text)
    if not isinstance(value, list):
        raise ValueError('Expected JSON array')
    return value

def validate_item(item):
    if not isinstance(item, dict): return False
    q, a = item.get('question'), item.get('answer')
    if not isinstance(q, str) or not isinstance(a, str): return False
    if len(q.strip()) < 20 or len(a.strip()) < 160: return False
    if a.count('```') % 2: return False
    if any(x in a.casefold() for x in ['[insert code]', 'code goes here', 'todo: implement']): return False
    return True

def connect(path):
    db = sqlite3.connect(path)
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('CREATE TABLE IF NOT EXISTS records (id TEXT PRIMARY KEY, kind TEXT, category TEXT, prompt TEXT UNIQUE, answer TEXT UNIQUE, payload TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')
    return db

def counts(db):
    return collections.Counter(dict(db.execute('SELECT kind, COUNT(*) FROM records GROUP BY kind')))

def save_item(db, item, kind, category, topic, model_name):
    if not validate_item(item): return False
    prompt, answer = normalize(item['question']), normalize(item['answer'])
    digest = hashlib.sha256((prompt + '\n' + answer).encode()).hexdigest()
    row = {
        'id': 'citrus-kaggle-' + digest[:24],
        'family_id': 'topic-' + category + '-' + hashlib.sha256(topic.encode()).hexdigest()[:12],
        'kind': kind, 'category': category,
        'messages': [{'role': 'user', 'content': item['question'].strip()}, {'role': 'assistant', 'content': item['answer'].strip()}],
        'sources': [], 'provenance': 'synthetic_local_model:' + model_name,
        'review_status': 'draft', 'runtime_verified': False,
    }
    try:
        db.execute('INSERT INTO records VALUES (?,?,?,?,?,?)', (row['id'], kind, category, prompt, answer, json.dumps(row, ensure_ascii=False)))
        db.commit()
        return True
    except sqlite3.IntegrityError:
        return False

def category_targets(total, names):
    base, extra = divmod(total, len(names))
    return {name: base + (i < extra) for i, name in enumerate(names)}

def configure_targets(db, targets, extend=False):
    config = json.dumps(targets, sort_keys=True)
    old = db.execute("SELECT value FROM settings WHERE key='targets'").fetchone()
    if old and old[0] != config:
        previous = json.loads(old[0])
        if not extend or set(previous) != set(targets) or any(targets[k] < previous[k] for k in targets):
            raise RuntimeError('Resume target mismatch; use --extend-targets only to increase existing quotas')
    actual = counts(db)
    if any(actual[k] > n for k, n in targets.items()):
        raise RuntimeError('Existing records exceed requested quotas')
    db.execute("INSERT OR REPLACE INTO settings VALUES ('targets', ?)", (config,))
    db.commit()

def next_work(db, targets):
    present = counts(db)
    todo = [k for k in targets if present[k] < targets[k]]
    if not todo: return None
    kind = min(todo, key=lambda k: present[k] / targets[k])
    cat_targets = category_targets(targets[kind], list(TOPICS))
    used = dict(db.execute('SELECT category, COUNT(*) FROM records WHERE kind=? GROUP BY category', (kind,)))
    cats = [c for c in TOPICS if used.get(c, 0) < cat_targets[c]]
    category = min(cats, key=lambda c: used.get(c, 0) / cat_targets[c])
    remaining = min(targets[kind] - present[kind], cat_targets[category] - used.get(category, 0))
    return kind, category, remaining

def export_checkpoint(db, root, targets):
    out = root / 'candidates'
    out.mkdir(exist_ok=True)
    # SQLite is authoritative. Atomic replace avoids a truncated export on interruption.
    tmp = out / 'kaggle_generated.jsonl.tmp'
    with tmp.open('w', encoding='utf-8') as handle:
        for (payload,) in db.execute('SELECT payload FROM records ORDER BY id'):
            handle.write(payload + '\n')
    os.replace(tmp, out / 'kaggle_generated.jsonl')
    current = counts(db)
    manifest = {
        'version': 'kaggle-50k-drafts', 'target_total': sum(targets.values()),
        'target_counts': targets, 'actual_counts': {**dict(current), 'total': sum(current.values())},
        'status': 'draft_generation_complete' if all(current[k] == targets[k] for k in targets) else 'in_progress',
        'approved_total': 0, 'model_training_started': False,
        'categories': [{'name': c, **{'target_' + k: category_targets(n, list(TOPICS))[c] for k, n in targets.items()}} for c in TOPICS],
        'quality_checks': ['JSON schema', 'normalized exact prompt/answer duplicates'],
        'pending_checks': ['factual review', 'semantic deduplication', 'code execution', 'source/license review'],
    }
    temp = root / 'manifest.json.tmp'
    temp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.replace(temp, root / 'manifest.json')
    return manifest

def load_model(name):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA GPU required for this configured 4-bit generator; no generation started')
    tokenizer = AutoTokenizer.from_pretrained(name)
    model = AutoModelForCausalLM.from_pretrained(
        name, device_map='auto', torch_dtype=torch.float16,
        quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4', bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.float16),
    )
    model.eval()
    def generate(prompt, max_tokens):
        text = tokenizer.apply_chat_template([{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': prompt}], tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(text, return_tensors='pt').to(model.device)
        with torch.inference_mode():
            result = model.generate(**inputs, max_new_tokens=max_tokens, do_sample=True, temperature=0.8, top_p=0.9, pad_token_id=tokenizer.eos_token_id)
        return tokenizer.decode(result[0, inputs['input_ids'].shape[1]:], skip_special_tokens=True)
    return generate

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=pathlib.Path, default=pathlib.Path('/kaggle/working/citrus-50k'))
    parser.add_argument('--model', default='Qwen/Qwen2.5-7B-Instruct')
    parser.add_argument('--knowledge', type=int, default=15000)
    parser.add_argument('--practice', type=int, default=35000)
    parser.add_argument('--batch-size', type=int, default=3)
    parser.add_argument('--max-new-tokens', type=int, default=4096)
    parser.add_argument('--max-minutes', type=float, default=480)
    parser.add_argument('--max-failures', type=int, default=20)
    parser.add_argument('--checkpoint-every', type=int, default=30)
    parser.add_argument('--export-only', action='store_true')
    parser.add_argument('--extend-targets', action='store_true', help='Explicitly increase quotas while preserving all existing records and duplicate checks')
    args = parser.parse_args()
    if min(args.knowledge, args.practice, args.batch_size, args.max_new_tokens, args.max_failures, args.checkpoint_every) <= 0 or args.max_minutes <= 0:
        parser.error('Counts and limits must be positive')
    args.out.mkdir(parents=True, exist_ok=True)
    db = connect(args.out / 'progress.sqlite')
    targets = {'knowledge': args.knowledge, 'practice': args.practice}
    configure_targets(db, targets, args.extend_targets)
    if args.export_only:
        print(json.dumps(export_checkpoint(db, args.out, targets), ensure_ascii=False)); return
    if not next_work(db, targets):
        print(json.dumps(export_checkpoint(db, args.out, targets), ensure_ascii=False)); return
    started = time.monotonic()
    generate = load_model(args.model)
    failures = attempts = accepted_since_export = 0
    try:
        while time.monotonic() - started < args.max_minutes * 60:
            work = next_work(db, targets)
            if work is None: break
            kind, category, remaining = work
            topics = TOPICS[category]
            topic = topics[attempts % len(topics)]
            size = min(args.batch_size, remaining)
            examples = [r[0] for r in db.execute('SELECT prompt FROM records WHERE category=? ORDER BY rowid DESC LIMIT 8', (category,))]
            prompt = json.dumps({'kind': kind, 'category': category, 'topic': topic, 'count': size, 'factual_constraints': ANCHORS.get(category, ''), 'avoid_previous_questions': examples, 'instruction': 'Create new substantive tasks and complete answers, not paraphrases. Return exactly count JSON items.'}, ensure_ascii=False)
            attempts += 1
            try:
                output = parse_output(generate(prompt, args.max_new_tokens))
                accepted = sum(save_item(db, item, kind, category, topic, args.model) for item in output[:size])
                failures = 0 if accepted else failures + 1
                accepted_since_export += accepted
                print(json.dumps({'attempt': attempts, 'accepted': accepted, 'actual': dict(counts(db))}), flush=True)
            except (ValueError, TypeError) as exc:
                failures += 1
                print(json.dumps({'attempt': attempts, 'rejected': str(exc)}), flush=True)
            if accepted_since_export >= args.checkpoint_every:
                export_checkpoint(db, args.out, targets); accepted_since_export = 0
            if failures >= args.max_failures:
                print('Stopped: repeated invalid or duplicate output. Inspect candidates/model before resuming.', flush=True)
                break
    finally:
        report = export_checkpoint(db, args.out, targets)
        print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
        db.close()

if __name__ == '__main__':
    main()
