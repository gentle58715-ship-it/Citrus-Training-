"""Regression gates for concrete failure modes; stdlib only."""
import copy
import importlib.util
import json
import pathlib
import shutil
import tempfile
import unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('pipeline',ROOT/'scripts/citrus_v4.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)

class PipelineTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory()
  cls.root=pathlib.Path(cls.temp.name)
  (cls.root/'candidates').mkdir()
  for name in ['config.json','sources.json','tool_schemas.json','reviews.json',
               'candidates/authored_0001.jsonl','candidates/tool_replay_0001.jsonl']:
   shutil.copyfile(p.DATA/name,cls.root/name)
  cls.config=p.read_json(cls.root/'config.json')
  cls.sources={s['id'] for s in p.read_json(cls.root/'sources.json')}
  cls.tools={t['function']['name']:t for t in p.read_json(cls.root/'tool_schemas.json')}
  cls.rows,_,cls.report=p.audit(cls.root)
  cls.tool=next(r for r in cls.rows if r['tool_execution_verified'])
  cls.plain=next(r for r in cls.rows if r['category']=='luau')
 @classmethod
 def tearDownClass(cls):cls.temp.cleanup()
 def errors(self,row):return p.validate_row(row,self.config,self.sources,self.tools)
 def test_target_and_summary_quota(self):
  self.assertEqual(sum(c['total'] for c in self.config['categories']),60000)
  self.assertEqual(sum(c['knowledge'] for c in self.config['categories']),12000)
  self.assertEqual(len(self.config['categories']),14)
 def test_actual_is_not_target(self):
  self.assertEqual(self.report['actual_valid_candidates'],100)
  self.assertFalse(self.report['completion'])
 def test_original_records_validate(self):self.assertEqual(self.report['errors'],[])
 def test_plan_cannot_call_even_read_tool(self):
  row=copy.deepcopy(self.tool);row['mode']='plan'
  self.assertIn('Plan mode forbids every tool call',self.errors(row))
 def test_orphan_tool_output(self):
  row=copy.deepcopy(self.tool)
  next(m for m in row['messages'] if m['role']=='tool')['tool_call_id']='missing'
  self.assertIn('orphan or repeated tool response',self.errors(row))
 def test_unknown_tool(self):
  row=copy.deepcopy(self.tool)
  next(m for m in row['messages'] if m.get('tool_calls'))['tool_calls'][0]['function']['name']='invented_tool'
  self.assertIn('called tool is absent from tools',self.errors(row))
 def test_false_tool_verification(self):
  row=copy.deepcopy(self.tool);row['tool_execution_verified']=False
  self.assertIn('tool outputs require actual isolated execution',self.errors(row))
 def test_invalid_service_detected(self):
  row=copy.deepcopy(self.plain)
  row['messages'][-1]['content']='```luau\nlocal x=game:GetService("RemoteFunction")\n```'
  self.assertIn('Instance class incorrectly used as a service',self.errors(row))
 def test_fake_player_api_detected(self):
  row=copy.deepcopy(self.plain);row['messages'][-1]['content']='```luau\nplayer:SetData("Coins",10)\n```'
  self.assertIn('unsupported Player method in answer code',self.errors(row))
 def test_type_and_enum_validation(self):
  with self.assertRaises(ValueError):p.validate_schema({'rig':'R7'},self.tools['read_rig']['function']['parameters'])
  with self.assertRaises(ValueError):p.validate_schema({'rig':'R6','extra':1},self.tools['read_rig']['function']['parameters'])
 def test_runtime_claim_requires_evidence(self):
  row=copy.deepcopy(self.plain);row['runtime_verified']=True;row['evidence']={}
  self.assertIn('missing runtime evidence',self.errors(row))
 def test_hash_binds_approval_to_content(self):
  row=copy.deepcopy(self.plain);old=p.content_hash(row);row['messages'][-1]['content']+=' changed'
  self.assertNotEqual(old,p.content_hash(row))
 def test_export_incomplete_blocked(self):
  with tempfile.TemporaryDirectory() as out:
   with self.assertRaises(ValueError):p.export(self.root,pathlib.Path(out)/'export')
 def test_partial_export_preserves_group_boundary(self):
  with tempfile.TemporaryDirectory() as out:
   p.export(self.root,out,allow_partial=True)
   membership=p.read_json(pathlib.Path(out)/'membership.json')
   families={}
   for item in membership:
    families.setdefault(item['family'],set()).add(item['split'])
   self.assertTrue(all(len(v)==1 for v in families.values()))
   self.assertEqual(len(membership),100)
 def test_family_split_stable(self):
  self.assertEqual(p.split_for('same-family'),p.split_for('same-family'))
  self.assertTrue(all(p.split_for(str(i)) in ('train','validation','test') for i in range(100)))
 def test_parse_rejects_missing_grounding(self):
  with self.assertRaises(ValueError):p.parse_generation(json.dumps({'question':'q','answer':'a'*200,'family_id':'f','subtype':'s'}))

if __name__=='__main__':unittest.main()
