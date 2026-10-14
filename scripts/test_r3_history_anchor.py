"""Negative case: forging current hashes cannot rewrite the approved Git baseline.

An isolated local clone is created under the OS temporary directory. No
files, revisions or refs in the source checkout are modified by this test.
"""
from __future__ import annotations
import csv,hashlib,json,shutil,subprocess,tempfile,unittest
from pathlib import Path
from verify_source_amendment import ROOT,verify_amendment

class HistoricTrustRoot(unittest.TestCase):
 def test_legitimate_source_and_reissued_fake_historical_receipt(self):
  good=verify_amendment(ROOT)
  self.assertTrue(good['nonlabelFieldsPreserved'])
  with tempfile.TemporaryDirectory(prefix='apl-r3-attestation-') as td:
   cloned=Path(td)/'clone'
   subprocess.run(['git','clone','--quiet','--shared',str(ROOT),str(cloned)],check=True)
   # Before committing R3, the clone does not contain the new verifier.
   for f in ('scripts/reviewed_git_anchors.py','scripts/verify_source_amendment.py'):
    dest=cloned/f;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/f,dest)
   pristine=verify_amendment(cloned)
   self.assertEqual(pristine['historicalAnchor'],good['historicalAnchor'])
   target=cloned/'data/assignment-shards/agent-use/gentle-shell.csv'
   with target.open(encoding='utf-8-sig',newline='') as f:
    reader=csv.DictReader(f);fields=reader.fieldnames;rows=list(reader)
   assert fields and rows
   before=rows[0]['rationale'];rows[0]['rationale']='SYNTHETIC R3 FORGED ROLE RATIONALE'
   self.assertNotEqual(before,rows[0]['rationale'])
   with target.open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
   sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
   shard=cloned/'data/assignment-shards/manifest.json'
   manifest=json.loads(shard.read_bytes())
   manifest['shards']['agent-use/gentle-shell.csv']['sha256']=sha(target)
   shard.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
   receipt_file=cloned/'policies/source-metadata-amendment.json'
   receipt=json.loads(receipt_file.read_bytes())
   rel='data/assignment-shards/agent-use/gentle-shell.csv'
   receipt['sourceFiles'][rel]['currentFileSHA256']=sha(target)
   # The attacker tries to reissue the digest of "unchanged" non-label fields.
   from verify_source_amendment import normalized_digest
   receipt['sourceFiles'][rel]['originalNonlabelFieldsSHA256']=normalized_digest(rows)
   receipt['currentSourceManifestSHA256']=sha(shard)
   receipt_file.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
   with self.assertRaisesRegex(ValueError,'Git|historic|descriptive|Non-descriptive'):
    verify_amendment(cloned)
if __name__=='__main__':unittest.main()
