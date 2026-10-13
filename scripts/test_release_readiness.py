from __future__ import annotations
import unittest,tempfile,subprocess
from pathlib import Path
from audit_release_readiness import matches_in_content,scan
class ReleaseAudit(unittest.TestCase):
 def test_non_revealing_sensitive_patterns(self):
    b=b'Private example: ghp_' + b'A'*32 + b' and -----BEGIN '+b'OPENSSH PRIVATE KEY-----'
    x=matches_in_content(b)
    self.assertEqual(x,{'private-key-header':1,'github-token':1})
    self.assertNotIn('ghp_',str(x))
 def test_explicit_local_user_path_requires_privacy_review(self):
    b=b'/home/' + b'person/.config/private'
    self.assertEqual(matches_in_content(b,{'path':__import__('re').compile(rb'/home/[A-Za-z0-9._-]{2,}/')}),{'path':1})
 def test_report_does_not_expose_secret_bytes(self):
    with tempfile.TemporaryDirectory() as td:
     path=Path(td);subprocess.run(['git','init','-q'],cwd=path,check=True)
     (path/'captured.txt').write_bytes(b'ghp_'+b'B'*40)
     subprocess.run(['git','add','captured.txt'],cwd=path,check=True)
     r=scan(path)
     self.assertFalse(r['publicationReady'])
     self.assertEqual(r['sensitiveCandidateCount'],1)
     self.assertEqual(r['sensitiveCandidates'][0]['pattern'],'github-token')
     self.assertNotIn('BBBB',str(r))
 def test_bounded_scan_does_not_claim_complete_content(self):
    with tempfile.TemporaryDirectory() as td:
     path=Path(td);subprocess.run(['git','init','-q'],cwd=path,check=True)
     (path/'huge.dat').write_bytes(b'a'*101)
     subprocess.run(['git','add','huge.dat'],cwd=path,check=True)
     r=scan(path,max_file_bytes=100)
     self.assertEqual(r['uninspectedCount'],1)
     self.assertFalse(r['publicationReady'])
if __name__=='__main__':unittest.main()
