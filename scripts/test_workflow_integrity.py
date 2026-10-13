"""GitHub workflow is opt-in hosting metadata, not publication authority."""
from pathlib import Path
import re,unittest
ROOT=Path(__file__).resolve().parents[1]
WORKFLOW=ROOT/'.github/workflows/offline-validation.yml'
class WorkflowIntegrity(unittest.TestCase):
 def test_pinned_actions_exact_hash_and_unprivileged_scope(self):
  text=WORKFLOW.read_text()
  matches=re.findall(r'^\s*uses:\s*([a-z0-9-]+/[a-z0-9-]+)@([0-9a-f]{40})\s*#',text,re.M)
  self.assertEqual(len(matches),3,matches)
  self.assertEqual({a for a,h in matches},{'actions/checkout','actions/setup-python','oven-sh/setup-bun'})
  self.assertIn('permissions:\n  contents: read',text)
  self.assertIn('persist-credentials: false',text)
  self.assertNotIn('contents: write',text)
  self.assertNotIn('pull-requests: write',text)
 def test_no_secrets_model_calls_or_publication(self):
  text=WORKFLOW.read_text()
  self.assertIn('scripts/check_project.py --rebuild --install',text)
  self.assertIn('scripts/audit_release_readiness.py',text)
  self.assertIn('scripts/review_objective_equivalences.py --verify',text)
  self.assertIn('python-version: "3.14"',text)
  self.assertIn('bun-version: "1.4.3"',text)
  for token in ['secrets.','gh release','gh repo','git push','curl ','--fetch','ssh-key']:
   self.assertNotIn(token,text)
 def test_manual_and_branch_triggers_without_background_scheduler(self):
  text=WORKFLOW.read_text()
  self.assertIsNotNone(re.search(r'^on:\n',text,re.M))
  self.assertIn('workflow_dispatch:',text)
  self.assertIn('pull_request:',text)
  self.assertNotIn('  schedule:',text)
if __name__=='__main__':unittest.main()
