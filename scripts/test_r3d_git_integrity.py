"""Falsification attempts against fixed historical Git blob comparisons.

Only clone worktrees are modified; Git refs/replace and info/attributes are
never written in either authentic source repository.
"""
from __future__ import annotations
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from git_object_integrity import verify_worktree_blobs,git_bytes,complete_git_tree
from reviewed_git_anchors import reviewed_anchor
from reviewed_native_blobs import verify_native_blobs,EXPECTED_COUNT
from verify_source_amendment import ROOT,verify_amendment

class GitObjectIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.edition,cls.anchor=reviewed_anchor(ROOT)

    def clone(self,path:Path)->Path:
        repo=path/'repository'
        subprocess.run(["git","clone","--quiet","--shared",str(ROOT),str(repo)],check=True)
        return repo

    def create_replace_attack(self,repo:Path,rel:str):
        file=repo/rel
        original=file.read_bytes()
        corrupted=bytearray(original)
        offset=len(corrupted)//2
        corrupted[offset]^=1  # exact same length, synthetic bytes only
        file.write_bytes(corrupted)
        old_oid=git_bytes(repo,"rev-parse",f"{self.anchor}:{rel}").decode().strip()
        new_oid=subprocess.check_output(["git","-C",str(repo),"hash-object","-w",rel],
                                         text=True).strip()
        subprocess.run(["git","-C",str(repo),"replace",old_oid,new_oid],check=True)
        subprocess.run(["git","-C",str(repo),"update-index","--skip-worktree","--",rel],check=True)
        return old_oid,new_oid

    def test_approved_inventory_and_normal_baseline(self):
        a=verify_native_blobs(ROOT,self.anchor)
        self.assertEqual(a["nativeFilesComparedDirectlyToGitBlobs"],EXPECTED_COUNT)
        self.assertFalse(a["usesGitArchive"])
        tree=complete_git_tree(ROOT,self.anchor,
                               ("profiles/gentle-shell","profiles/omp",
                                "profiles/gentle-shell-variants/critical-review"))
        self.assertEqual(len(tree),EXPECTED_COUNT)

    def test_sha_forged_replace_objects_and_index_flags_rejected(self):
        cases=("profiles/gentle-shell/cc-apps-balanced.export.json",
               "profiles/omp/cc-apps-balanced.yaml")
        for rel in cases:
            with self.subTest(rel),tempfile.TemporaryDirectory(prefix="apl-r3d-git-replace-") as d:
                repo=self.clone(Path(d))
                self.create_replace_attack(repo,rel)
                with self.assertRaisesRegex(ValueError,"differs from immutable historic Git blob"):
                    verify_native_blobs(repo,self.anchor)
                receipt=repo/"policies/source-metadata-amendment.json"
                r=json.loads(receipt.read_bytes())
                r["nativeFileSHA256"][rel]=hashlib.sha256((repo/rel).read_bytes()).hexdigest()
                receipt.write_text(json.dumps(r,indent=2,ensure_ascii=False)+"\n")
                with self.assertRaisesRegex(ValueError,"differs from immutable historic Git blob"):
                    verify_amendment(repo)

    def test_local_export_ignore_cannot_drop_tracked_native(self):
        with tempfile.TemporaryDirectory(prefix="apl-r3d-export-") as d:
            repo=self.clone(Path(d))
            rel="profiles/omp/cc-apps-balanced.yaml"
            file=repo/rel
            payload=bytearray(file.read_bytes())
            payload[len(payload)//2]^=1
            file.write_bytes(payload)
            attributes=repo/".git/info/attributes"
            attributes.write_text(f"/{rel} export-ignore\n")
            with self.assertRaisesRegex(ValueError,"differs from immutable historic Git blob"):
                verify_native_blobs(repo,self.anchor)
            self.assertEqual(len(complete_git_tree(repo,self.anchor,
                ("profiles/gentle-shell","profiles/omp",
                 "profiles/gentle-shell-variants/critical-review"))),3744)

    def test_boolean_version_and_numeric_overflow_rejected(self):
        from strict_data_formats import json_loads_strict,schema_version_is_one
        self.assertFalse(schema_version_is_one(True))
        self.assertTrue(schema_version_is_one(1))
        self.assertTrue(schema_version_is_one(1.0))
        for invalid in ('{"x":1e999}','{"x":-1e999}','{"x":NaN}'):
            with self.assertRaisesRegex(ValueError,"Nonfinite"):
                json_loads_strict(invalid)
        with tempfile.TemporaryDirectory(prefix="apl-r3d-version-") as d:
            repo=self.clone(Path(d))
            manifest=repo/"data/assignment-shards/manifest.json"
            data=json.loads(manifest.read_bytes())
            data["schemaVersion"]=True
            manifest.write_text(json.dumps(data,indent=2)+"\n")
            with self.assertRaisesRegex(ValueError,"Invalid decision-shard manifest"):
                from prepare_data import load_decisions
                load_decisions(repo)

    def test_amendment_bool_version_and_duplicate_manifest_with_reissued_hash(self):
        from verify_source_amendment import verify_amendment
        with tempfile.TemporaryDirectory(prefix="apl-r3d-version-receipt-") as d:
            repo=self.clone(Path(d))
            receipt=repo/"policies/source-metadata-amendment.json"
            raw=json.loads(receipt.read_bytes())
            raw["schemaVersion"]=True
            receipt.write_text(json.dumps(raw,indent=2)+"\n")
            with self.assertRaisesRegex(ValueError,"Unknown amendment"):
                verify_amendment(repo)
        with tempfile.TemporaryDirectory(prefix="apl-r3d-duplicates-") as d:
            repo=self.clone(Path(d))
            manifest=repo/"data/assignment-shards/manifest.json"
            data=manifest.read_text()
            self.assertIn('"schemaVersion": 1',data)
            manifest.write_text(data.replace('"schemaVersion": 1',
                        '"schemaVersion": 0, "schemaVersion": 1',1))
            receipt=repo/"policies/source-metadata-amendment.json"
            raw=json.loads(receipt.read_bytes())
            raw["currentSourceManifestSHA256"]=hashlib.sha256(manifest.read_bytes()).hexdigest()
            receipt.write_text(json.dumps(raw,indent=2)+"\n")
            with self.assertRaisesRegex(ValueError,"Duplicate JSON key"):
                verify_amendment(repo)

    def test_domain_review_scope_is_explicit_and_not_global(self):
        from profile_compiler import compile_request
        from preflight_profile import preflight
        for dom in ("cybersecurity","web"):
            with self.subTest(dom):
                bundle=compile_request({"schemaVersion":1,
                    "targetId":"omp@18.8.7",
                    "baseProfile":"omp--nan-"+dom+"-balanced"})
                state=preflight(bundle["manifest"],bundle["native"]["content"].encode())
                self.assertTrue(state["artifactCurrent"])
                self.assertEqual(state["policyReviewed"],dom=="cybersecurity")
                self.assertTrue(state["assurancePolicyReviewed"])
                self.assertEqual(bundle["manifest"]["policyReview"]["domainReviewed"],
                                 dom=="cybersecurity")
                self.assertEqual(state["policyReviewedScope"]["otherDomains"],
                                 "not-reviewed-by-this-attestation")
                self.assertFalse(state["readyForOperation"])

    def test_portfolio_duplicate_header_rejected(self):
        from metadata_contracts import label_contract
        import csv,io
        with tempfile.TemporaryDirectory(prefix="apl-r3d-csv-") as d:
            repo=self.clone(Path(d))
            file=repo/"data/portfolios.csv"
            read=list(csv.reader(io.StringIO(file.read_text(encoding="utf-8-sig"))))
            idx=read[0].index("label")
            for i,row in enumerate(read):
                row.insert(idx,row[idx])
            sink=io.StringIO()
            writer=csv.writer(sink)
            writer.writerows(read)
            file.write_text(sink.getvalue(),encoding="utf-8-sig")
            with self.assertRaisesRegex(ValueError,"duplicate CSV header"):
                label_contract(repo)

if __name__=="__main__":
    unittest.main()
