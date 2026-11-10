#!/usr/bin/env python3
"""Deterministic regression tests for the standing, scope-limited release contract."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import standing_release_gate as gate


class StandingReleaseGateTests(unittest.TestCase):
    def test_policy_has_explicit_exact_scope_and_denies_human_impersonation(self):
        policy = gate.policy_at()
        self.assertEqual(set(policy["authorizedHistoricalChanges"]), gate.SOURCE_PATHS)
        self.assertEqual(set(policy["controlledReleaseInfrastructure"]), gate.GATE_PATHS)
        self.assertFalse(policy["humanRightsReviewed"])
        self.assertFalse(policy["rightsRules"]["verifyHumanRightsClaim"])
        self.assertTrue(policy["rightsRules"]["denyAutomaticRightsExtensionToNewPaths"])
        self.assertEqual(policy["verifiedPublicFeatureCommit"], gate.FEATURE)

    def test_only_previously_scoped_exact_bytes_pass(self):
        policy=gate.policy_at()
        pinned={**policy["authorizedHistoricalChanges"],
                **policy["authorizedInfrastructureSHA256"]}
        samples=[(path,(gate.ROOT/path).read_bytes()) for path in pinned]
        samples.append((gate.POLICY,(gate.ROOT/gate.POLICY).read_bytes()))
        gate.compare_historical_versions(pinned,samples,{gate.POLICY})
        with self.assertRaisesRegex(ValueError,"Unreviewed new public Git path"):
            gate.compare_historical_versions(pinned,
                                             [("catalog/private-models.json",b"safe")], {gate.POLICY})
        with self.assertRaisesRegex(ValueError,"no standing rights coverage"):
            gate.compare_historical_versions(pinned,
                                             [("dashboard/src/Profiles.tsx",b"mutated")], {gate.POLICY})
        with self.assertRaisesRegex(ValueError,"no standing rights coverage"):
            gate.compare_historical_versions(pinned,
                                             [("tools/standing_release_gate.py",b"mutated")], {gate.POLICY})
        with self.assertRaisesRegex(ValueError,"Deletion"):
            gate.compare_historical_versions(pinned,
                                             [("dashboard/src/Profiles.tsx",None)], {gate.POLICY})

    def test_new_evidence_and_policy_widening_rejected(self):
        raw = gate.policy_at()
        def fixture(changes):
            with tempfile.TemporaryDirectory() as folder:
                p=Path(folder)/"tools";p.mkdir(parents=True)
                (p/"standing-release-policy.json").write_text(json.dumps(changes))
                return gate.policy_at(Path(folder))
        for change in (
            lambda v: v["authorizedHistoricalChanges"].update({"evidence/new.json":"a"*64}),
            lambda v: v["controlledReleaseInfrastructure"].append("catalog/restricted.json"),
            lambda v: v["authorizedInfrastructureSHA256"].update({"tools/unreviewed.py":"a"*64}),
            lambda v: v["rightsRules"].update({"denyThirdPartyPublisherScores":False}),
            lambda v: v.update({"humanRightsReviewed":True}),
            lambda v: v["expectedPagesInventorySHA256"].pop("reference"),
            lambda v: v.update({"schemaVersion":2}),
        ):
            with self.subTest(change=str(change)):
                bad=copy.deepcopy(raw);change(bad)
                with self.assertRaises(ValueError):fixture(bad)

    def test_older_exact_infrastructure_versions_are_explicitly_grandfathered(self):
        policy=gate.policy_at()
        pinned={**policy["authorizedHistoricalChanges"],
                **policy["authorizedInfrastructureSHA256"]}
        older=policy["authorizedInfrastructureHistoricalSHA256"]
        path="tools/standing_release_gate.py"
        self.assertIn(path,older)
        old=older[path][0]
        from unittest.mock import patch
        with patch.object(gate,"digest",return_value=old):
            gate.compare_historical_versions(pinned,[(path,b"previous reviewed gate")],
                                             {gate.POLICY},older)
        with self.assertRaisesRegex(ValueError,"no standing rights coverage"):
            gate.compare_historical_versions(pinned,[(path,b"unreviewed changed gate")],
                                             {gate.POLICY},older)

    def test_content_preserving_pr_merge_only(self):
        import subprocess
        def git_at(root, *args):
            p = subprocess.run(["git","-C",str(root),*args],check=True,
                               capture_output=True,text=True)
            return p.stdout.strip()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            git_at(root,"init","-b","main")
            git_at(root,"config","user.name","Synthetic release test")
            git_at(root,"config","user.email","synthetic@invalid.example")
            (root/"base.txt").write_text("baseline\\n")
            git_at(root,"add","base.txt");git_at(root,"commit","-m","baseline")
            base=git_at(root,"rev-parse","HEAD")
            git_at(root,"checkout","-b","feature")
            (root/"change.txt").write_text("reviewed source\\n")
            git_at(root,"add","change.txt");git_at(root,"commit","-m","reviewed feature")
            git_at(root,"checkout","main")
            git_at(root,"merge","--no-ff","--no-edit","feature")
            valid=git_at(root,"rev-parse","HEAD")
            versions,count=gate.historical_versions(root,base,valid)
            self.assertEqual(count,2)
            self.assertEqual(len(versions),2)
            # A maintainer changing the merge tree without changing its
            # second-parent identity must fail rather than inherit approval.
            (root/"change.txt").write_text("unreviewed conflict resolution\\n")
            git_at(root,"add","change.txt")
            git_at(root,"commit","--amend","--no-edit")
            poisoned=git_at(root,"rev-parse","HEAD")
            with self.assertRaisesRegex(ValueError,"Unreviewed conflict resolution"):
                gate.historical_versions(root,base,poisoned)

    def test_site_inventory_cannot_be_replaced_by_arbitrary_build(self):
        from unittest.mock import patch
        pol=gate.policy_at()
        expected=pol["expectedPagesInventorySHA256"]["public"]
        report={"pagesFilesScanned":17}
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);b=root/"dist";b.mkdir()
            (b/"index.html").write_text("synthetic")
            with patch.object(gate,"verify_source",return_value={"result":"POLICY_SCOPE_VERIFIED"}),\
                 patch.object(gate,"policy_at",return_value=pol):
                # The genuine auditor must not mistake a one-file synthetic site for Pages.
                with self.assertRaises((ValueError,FileNotFoundError)):
                    gate.verify_pages(gate.ROOT,b,"public")
            self.assertRegex(expected,r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main(verbosity=2)
