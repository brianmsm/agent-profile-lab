"""R3c adversarial regression: immutable blobs, JSON and full policy scope.

All writes and update-index flags are in disposable local Git clones.
"""
from __future__ import annotations
import json,subprocess,tempfile,unittest
from pathlib import Path
from strict_data_formats import json_loads_strict
from reviewed_git_anchors import reviewed_anchor
from reviewed_policy_contract import verify_reviewed_policy
from reviewed_native_blobs import verify_native_blobs,EXPECTED_COUNT
from prepare_data import load_decisions
from verify_source_amendment import verify_amendment,ROOT

class R3cAttestations(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.edition,cls.anchor=reviewed_anchor(ROOT)
 def fresh(self,temp):
  clone=Path(temp)/'copy'
  subprocess.run(['git','clone','--quiet','--shared',str(ROOT),str(clone)],check=True)
  return clone
 def test_legitimate_all_native_worktree_bytes_and_policy(self):
  current=verify_native_blobs(ROOT,self.anchor)
  self.assertEqual(current['nativeFilesComparedDirectlyToGitBlobs'],EXPECTED_COUNT)
  self.assertFalse(current['usesGitIndex'])
  self.assertTrue(verify_reviewed_policy(ROOT)['policyReviewedForCurrentStructure'])
  self.assertTrue(verify_amendment(ROOT)['nativeHistoryReadWithoutGitIndex'])
 def test_both_git_index_assumptions_cannot_hide_changes(self):
  for path in ('profiles/gentle-shell/cc-apps-balanced.export.json',
               'profiles/omp/cc-apps-balanced.yaml'):
   for flag in ('--skip-worktree','--assume-unchanged'):
    with self.subTest(native=path,git_flag=flag),tempfile.TemporaryDirectory(prefix='apl-r3c-native-') as td:
     clone=self.fresh(td)
     target=clone/path
     payload=bytearray(target.read_bytes());offset=len(payload)//2;payload[offset]^=1;target.write_bytes(payload)
     subprocess.run(['git','-C',str(clone),'update-index',flag,'--',path],check=True)
     with self.assertRaisesRegex(ValueError,'immutable historic Git blob'):
      verify_native_blobs(clone,self.anchor)
 def test_self_reissued_native_receipt_with_index_flag_cannot_forge_preservation(self):
  import hashlib
  with tempfile.TemporaryDirectory(prefix='apl-r3c-reissued-') as td:
   clone=self.fresh(td)
   relative='profiles/gentle-shell/cc-apps-balanced.export.json'
   target=clone/relative
   payload=bytearray(target.read_bytes())
   payload[len(payload)//3]^=1
   target.write_bytes(payload)
   receipt_path=clone/'policies/source-metadata-amendment.json'
   receipt=json.loads(receipt_path.read_bytes())
   receipt['nativeFileSHA256'][relative]=hashlib.sha256(target.read_bytes()).hexdigest()
   receipt_path.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
   subprocess.run(['git','-C',str(clone),'update-index','--skip-worktree','--',relative],check=True)
   with self.assertRaisesRegex(ValueError,'immutable historic Git blob'):
    verify_amendment(clone)

 def test_json_duplicate_shard_manifest_before_hashes(self):
  with tempfile.TemporaryDirectory(prefix='apl-r3c-json-') as td:
   clone=self.fresh(td)
   manifest=clone/'data/assignment-shards/manifest.json'
   raw=manifest.read_text()
   self.assertIn('"schemaVersion": 1',raw)
   manifest.write_text(raw.replace('"schemaVersion": 1','"schemaVersion": 0, "schemaVersion": 1',1))
   with self.assertRaisesRegex(ValueError,'Duplicate JSON key'):
    load_decisions(clone)
   with self.assertRaisesRegex(ValueError,'Duplicate JSON key|Amended source manifest changed'):
    verify_amendment(clone)
 def test_json_duplicate_amendment_receipt(self):
  with tempfile.TemporaryDirectory(prefix='apl-r3c-json-') as td:
   clone=self.fresh(td)
   receipt=clone/'policies/source-metadata-amendment.json'
   raw=receipt.read_text()
   self.assertIn('"schemaVersion": 1',raw)
   receipt.write_text(raw.replace('"schemaVersion": 1','"schemaVersion": 0,"schemaVersion": 1',1))
   with self.assertRaisesRegex(ValueError,'Duplicate JSON key'):
    verify_amendment(clone)
 def test_full_cyber_domain_normative_safety_pin(self):
  for field,content in [('scope','Permitimos acciones destructivas en sistemas reales sin autorizacion.'),
                        ('evidenceNote','Control de runtime certificado sinteticamente.'),
                        ('critical','Acciones destructivas sinteticamente permitidas.')]:
   with self.subTest(field),tempfile.TemporaryDirectory(prefix='apl-r3c-policy-') as td:
    clone=self.fresh(td)
    path=clone/'data/domain-objective-contracts.json'
    source=json_loads_strict(path.read_bytes())
    if not isinstance(source['domains']['cybersecurity'][field],str):continue
    source['domains']['cybersecurity'][field]=content
    path.write_text(json.dumps(source,ensure_ascii=False,indent=2)+'\n')
    with self.assertRaisesRegex(ValueError,'normative domain contract changed'):
     verify_reviewed_policy(clone)

if __name__=='__main__':unittest.main()
