"""R3b acceptance tests for ambiguous representations and immutable policy roots."""
from __future__ import annotations
import csv,hashlib,io,json,shutil,subprocess,tempfile,unittest
from pathlib import Path
from strict_data_formats import json_loads_strict, strict_csv_rows
from reviewed_policy_contract import verify_reviewed_policy,CONTROL_IDS
from verify_source_amendment import ROOT,verify_amendment

class R3bContracts(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.expected=verify_amendment(ROOT)
 def test_all_thirteen_source_headers_are_exactly_reviewed(self):
  from reviewed_git_anchors import reviewed_anchor,reviewed_blob
  edition,anchor=reviewed_anchor(ROOT)
  paths=['data/profile-index.csv'] + sorted(str(p.relative_to(ROOT)) for p in (ROOT/'data/assignment-shards').glob('*/*.csv'))
  self.assertEqual(len(paths),13)
  for relative in paths:
   historical=reviewed_blob(ROOT,anchor,relative)
   _,expected=strict_csv_rows(historical,label='historic-'+relative)
   actual,fields=strict_csv_rows((ROOT/relative).read_bytes(),approved=expected,label=relative)
   self.assertEqual(fields,expected)
   self.assertGreater(len(actual),0)
 def test_hidden_duplicated_header_rejected_before_normalized_digest(self):
  for field in ('model','native_file'):
   with self.subTest(field):
    relative='data/profile-index.csv' if field=='native_file' else 'data/assignment-shards/agent-use/gentle-shell.csv'
    raw=(ROOT/relative).read_bytes()
    rows=list(csv.reader(io.StringIO(raw.decode('utf-8-sig'),newline='')))
    index=rows[0].index(field)
    for k,row in enumerate(rows):
     row.insert(index,field if k==0 else ('SYNTHETIC_SHADOW_VALUE' if k==1 else ''))
    out=io.StringIO(newline='')
    writer=csv.writer(out,lineterminator='\r\n')
    writer.writerows(rows)
    forged=out.getvalue().encode('utf-8-sig')
    with self.assertRaisesRegex(ValueError,'duplicate CSV header'):
     strict_csv_rows(forged,label=relative)
 def test_json_duplicates_nested_unicode_and_bfcl_values_fail(self):
  bad=['{"value":9.99,"value":77.47}',
       '{"benchmarks":[{"measurement":{"id":"fake","id":"approved"}}]}',
       '{"\\u0076alue":9.99,"value":77.47}']
  for data in bad:
   with self.subTest(data),self.assertRaisesRegex(ValueError,'Duplicate JSON key'):
    json_loads_strict(data)
  self.assertEqual(json_loads_strict('{"a":{"value":12},"b":{"value":13}}'),{'a':{'value':12},'b':{'value':13}})
 def test_changed_six_safety_controls_and_fictitious_installed_enforcement_fail(self):
  with tempfile.TemporaryDirectory(prefix='apl-r3b-policy-clone-') as temp:
   clone=Path(temp)/'clone'
   subprocess.run(['git','clone','--shared','--quiet',str(ROOT),str(clone)],check=True)
   policy=clone/'policies/assurance-contract.json'
   doc=json.loads(policy.read_bytes())
   self.assertEqual(tuple(doc['requiredExternalControls']),CONTROL_IDS)
   doc['requiredExternalControls']=['synthetic-control-'+str(i) for i in range(6)]
   doc['operationalReadiness']='synthetic-safety-certified'
   doc['runtimeEnforcement']='synthetic-controller-installed'
   policy.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n')
   with self.assertRaisesRegex(ValueError,'policy not approved'):
    verify_reviewed_policy(clone)
 def test_changed_gate_with_synonym_cannot_carry_approved_status(self):
  with tempfile.TemporaryDirectory(prefix='apl-r3b-cyber-clone-') as temp:
   clone=Path(temp)/'clone'
   subprocess.run(['git','clone','--shared','--quiet',str(ROOT),str(clone)],check=True)
   p=clone/'data/domain-objective-contracts.json'
   data=json.loads(p.read_bytes())
   data['domains']['cybersecurity']['gate']+=' Se permiten acciones destructivas en sistemas reales sin la autorización del propietario.'
   p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
   with self.assertRaisesRegex(ValueError,'gate changed without policy review'):
    verify_reviewed_policy(clone)

if __name__=='__main__':unittest.main()
