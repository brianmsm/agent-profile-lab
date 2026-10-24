"""R3f synthetic TOCTOU, shard-alias and dynamic-loader guards.

Only disposable clones and nonsecret marker files. No genuine signer,
external network access, GitHub pushes, or active-agent operations.
"""
from __future__ import annotations
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from git_object_integrity import git_bytes, git_environment
from profile_compiler import compile_request
from preflight_profile import preflight
from reviewed_policy_contract import verify_reviewed_policy
from verify_source_amendment import ROOT,verify_amendment

class R3fTrustBoundaryTests(unittest.TestCase):
    def clone(self, area:Path)->Path:
        repo=area/"synthetic-copy"
        subprocess.run(["/usr/bin/git","clone","--quiet","--no-local",
                        "--single-branch",str(ROOT),str(repo)],
                       check=True,timeout=120)
        return repo

    def test_loader_environment_does_not_cross_to_fixed_git(self):
        with tempfile.TemporaryDirectory(prefix="apl-r3f-loader-") as tmp:
            fake=Path(tmp)/"nonexistent-untrusted-loader.so"
            old={k:os.environ.get(k) for k in ("LD_PRELOAD","LD_AUDIT","PYTHONPATH","GIT_CONFIG_COUNT")}
            try:
                os.environ.update(LD_PRELOAD=str(fake),LD_AUDIT=str(fake),
                                  PYTHONPATH=tmp,GIT_CONFIG_COUNT="1")
                env=git_environment()
                self.assertTrue({"LD_PRELOAD","LD_AUDIT","PYTHONPATH","GIT_CONFIG_COUNT"}.isdisjoint(env))
                self.assertEqual(len(git_bytes(ROOT,"rev-parse","HEAD").decode().strip()),40)
            finally:
                for k,v in old.items():
                    if v is None:os.environ.pop(k,None)
                    else:os.environ[k]=v

    def test_preflight_rejects_source_changed_during_evaluation(self):
        with tempfile.TemporaryDirectory(prefix="apl-r3f-racing-source-") as tmp:
            repo=self.clone(Path(tmp))
            req={"schemaVersion":1,"targetId":"omp@18.8.7",
                 "baseProfile":"omp--nan-web-balanced"}
            produced=compile_request(req,root=repo)
            changed=repo/"data/profile-index.csv"
            original=changed.read_bytes()
            invoked=[]
            def synthetic_writer(root:Path):
                if not invoked:
                    # Mutation AFTER preflight's initial hash inventory and
                    # after its historic Git source verification.
                    with changed.open("ab") as stream:stream.write(b"\n")
                    invoked.append(True)
                return verify_reviewed_policy(root)
            with patch("preflight_profile.verify_reviewed_policy",side_effect=synthetic_writer):
                with self.assertRaisesRegex(ValueError,
                         "Source changed during preflight"):
                    preflight(produced["manifest"],produced["native"]["content"].encode(),
                              root=repo)
            self.assertTrue(invoked)
            self.assertNotEqual(changed.read_bytes(),original)

    def test_original_shard_alias_not_approved_even_with_identical_bytes(self):
        with tempfile.TemporaryDirectory(prefix="apl-r3f-shard-alias-") as tmp:
            repo=self.clone(Path(tmp))
            shard=repo/"data/assignment-shards/agent-use"
            self.assertTrue(shard.is_dir())
            mirror=repo/"r3f-synthetic-alias"
            shutil.copytree(shard,mirror)
            shutil.rmtree(shard)
            shard.symlink_to("../../r3f-synthetic-alias",target_is_directory=True)
            with self.assertRaisesRegex(ValueError,
                "Unsafe amended CSV ancestor|coverage differs|Unsafe transitive shard ancestor"):
                verify_amendment(repo)

if __name__=="__main__":
    unittest.main(verbosity=2)
