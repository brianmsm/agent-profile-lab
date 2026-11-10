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
