"""R3e adversarial trust boundary regressions, all mutations in /tmp clones.

Original repositories, installed signing state, GitHub and provider APIs are
never modified. Unsafe Git metadata only writes synthetic temp markers.
"""
from __future__ import annotations
import csv
import hashlib
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from git_object_integrity import git_bytes,verify_worktree_blobs
from reviewed_git_anchors import reviewed_anchor
from verify_source_amendment import ROOT,verify_amendment,normalized_digest
from profile_compiler import compile_request
from preflight_profile import preflight

GIT="/usr/bin/git"

def call(repo:Path,*args:str):
    return subprocess.check_output([GIT,"-C",str(repo),*args],text=True).strip()

class R3eTrustBoundaries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.edition,cls.anchor=reviewed_anchor(ROOT)

    def tiny_repo(self,temp:Path):
        repo=temp/"synthetic-source"
        repo.mkdir()
        subprocess.run([GIT,"-C",str(repo),"init","-q","-b","main"],check=True)
        call(repo,"config","user.name","Synthetic Auditor")
        call(repo,"config","user.email","synthetic@example.invalid")
        (repo/"README.md").write_text("synthetic bytes\n")
        call(repo,"add","README.md")
        call(repo,"-c","core.hooksPath=/dev/null","commit","-qm","synthetic baseline")
        return repo

    def test_path_cannot_replace_git_even_with_environment_overrides(self):
        with tempfile.TemporaryDirectory(prefix="apl-r3e-git-binary-") as td:
            temp=Path(td);repo=self.tiny_repo(temp)
            bindir=temp/"shim";bindir.mkdir()
            marker=temp/"path-shim-invocations.txt"
            exe=bindir/"git"
            exe.write_text(f'#!/bin/sh\nprintf "SHIM_EXECUTED\\n" >> "{marker}"\n'
                           f'exec {GIT} "$@"\n')
            exe.chmod(0o700)
            old=os.environ.get("PATH")
            old_extra=os.environ.get("GIT_CONFIG_COUNT")
            try:
                os.environ["PATH"]=str(bindir)+os.pathsep+str(old or "")
                os.environ["GIT_CONFIG_COUNT"]="1"
                os.environ["GIT_CONFIG_KEY_0"]="core.fsmonitor"
                os.environ["GIT_CONFIG_VALUE_0"]="/bin/false"
                head=git_bytes(repo,"rev-parse","HEAD").decode().strip()
                self.assertEqual(len(head),40)
                self.assertFalse(marker.exists())
            finally:
                if old is None:os.environ.pop("PATH",None)
                else:os.environ["PATH"]=old
                if old_extra is None:os.environ.pop("GIT_CONFIG_COUNT",None)
                else:os.environ["GIT_CONFIG_COUNT"]=old_extra
                for k in ("GIT_CONFIG_KEY_0","GIT_CONFIG_VALUE_0"):
                    os.environ.pop(k,None)

    def test_fsmonitor_include_and_process_config_rejected_before_any_command(self):
        variants=("core.fsmonitor","include.path","filter.example.process",
                  "uploadpack.packObjectsHook")
        for index,key in enumerate(variants):
            with self.subTest(key),tempfile.TemporaryDirectory(prefix="apl-r3e-config-") as td:
                temp=Path(td);repo=self.tiny_repo(temp)
                marker=temp/"NO_EXECUTION_EXPECTED.txt"
                hook=temp/"synthetic-hook.sh"
                hook.write_text(f'#!/bin/sh\nprintf "RUN\\n" >> "{marker}"\n')
                hook.chmod(0o700)
                if key=="include.path":
                    included=temp/"synthetic-included.conf"
                    included.write_text(f'[core]\nfsmonitor = {hook}\n')
                    call(repo,"config","--local",key,str(included))
                else:call(repo,"config","--local",key,str(hook))
                with self.assertRaisesRegex(ValueError,"Git configuration"):
                    git_bytes(repo,"status","--porcelain=v1")
                self.assertFalse(marker.exists(),"Untrusted Git metadata executed")

    def test_signed_worktree_cannot_follow_symlink_ancestors(self):
        with tempfile.TemporaryDirectory(prefix="apl-r3e-symlink-") as td:
            repo=self.tiny_repo(Path(td))
            for name in ("a","b"):
                d=repo/name;d.mkdir()
                (d/"same.txt").write_bytes(b"synthetic identical content")
            call(repo,"add","a/same.txt","b/same.txt")
            call(repo,"-c","core.hooksPath=/dev/null","commit","-qm","two identical blobs")
            head=call(repo,"rev-parse","HEAD")
            expected=verify_worktree_blobs(repo,head,minimum_count=3)
            self.assertEqual(expected["trackedGitBlobsCompared"],3)
            (repo/"a/same.txt").unlink()
            (repo/"a").rmdir()
            (repo/"a").symlink_to("b",target_is_directory=True)
            with self.assertRaisesRegex(ValueError,"ancestor is symlink"):
                verify_worktree_blobs(repo,head,minimum_count=3)

    def test_changed_csv_reissued_receipt_is_not_signed_by_path_shim(self):
        with tempfile.TemporaryDirectory(prefix="apl-r3e-csv-shim-") as td:
            temp=Path(td)
            repo=temp/"source"
            subprocess.run([GIT,"clone","--quiet","--no-local","--single-branch",
                            str(ROOT),str(repo)],check=True,timeout=120)
            directory=repo/"data/assignment-shards"
            manifest=directory/"manifest.json"
            receipt=repo/"policies/source-metadata-amendment.json"
            m=json.loads(manifest.read_bytes())
            rel="data/assignment-shards/"+sorted(m["shards"])[0]
            source=repo/rel
            from strict_data_formats import strict_csv_rows
            rows,fields=strict_csv_rows(source.read_bytes())
            rows[0]["rationale"]+=" [SYNTHETIC R3e FALSIFICATION]"
            sink=io.StringIO(newline="")
            writer=csv.DictWriter(sink,fieldnames=fields)
            writer.writeheader();writer.writerows(rows)
            source.write_bytes(b"\xef\xbb\xbf"+sink.getvalue().encode())
            sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
            entry=m["shards"][rel.removeprefix("data/assignment-shards/")]
            entry["sha256"]=sha(source)
            manifest.write_text(json.dumps(m,indent=2,ensure_ascii=False)+"\n")
            r=json.loads(receipt.read_bytes())
            r["currentSourceManifestSHA256"]=sha(manifest)
            r["originalSourceManifestSHA256"]=sha(manifest)
            rec=r["sourceFiles"][rel]
            rec["originalFileSHA256"]=sha(source)
            rec["currentFileSHA256"]=sha(source)
            rec["originalNonlabelFieldsSHA256"]=normalized_digest(rows)
            receipt.write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n")
            marker=temp/"NO_EXECUTED_SHIM.txt"
            bindir=temp/"malicious-PATH";bindir.mkdir()
            # Full R3d A-H01 synthetic forgery, not just a shim marker.
            # If called, it would return the REISSUED current CSV/manifest
            # as fake historic bytes, then delegate other calls.
            shim = """#!/usr/bin/python3
import os,subprocess,sys
from pathlib import Path
args=sys.argv[1:]
repo=Path(os.environ["APL_R3E_SYNTHETIC_ROOT"])
marker=Path(os.environ["APL_R3E_SYNTHETIC_MARKER"])
with marker.open("a") as output:
    output.write("FORGED_GIT_EXECUTED\\n")
if len(args)>=4 and args[0]=="-C" and args[2]=="show" and ":" in args[3]:
    target=args[3].split(":",1)[1]
    if target in ("data/assignment-shards/manifest.json",
                  os.environ["APL_R3E_SYNTHETIC_SHARD"]):
        sys.stdout.buffer.write((repo/target).read_bytes())
        sys.exit(0)
sys.exit(subprocess.run(["/usr/bin/git",*args],check=False).returncode)
"""
            (bindir/"git").write_text(shim)
            (bindir/"git").chmod(0o700)
            old=os.environ.get("PATH","")
            prior={k:os.environ.get(k) for k in (
                "APL_R3E_SYNTHETIC_ROOT","APL_R3E_SYNTHETIC_MARKER",
                "APL_R3E_SYNTHETIC_SHARD")}
            try:
                os.environ.update(PATH=str(bindir)+":"+old,
                                  APL_R3E_SYNTHETIC_ROOT=str(repo),
                                  APL_R3E_SYNTHETIC_MARKER=str(marker),
                                  APL_R3E_SYNTHETIC_SHARD=rel)
                with self.assertRaisesRegex(ValueError,
                  "Original source manifest SHA|Non-descriptive source differences"):
                    verify_amendment(repo)
                self.assertFalse(marker.exists())
                # A full preflight must also refuse an invalid historical
                # receipt rather than accepting artifactCurrent=true.
                try:
                    bundle=compile_request({
                        "schemaVersion":1,"targetId":"omp@18.8.7",
                        "baseProfile":"omp--nan-web-balanced"},root=repo)
                    result=preflight(bundle["manifest"],bundle["native"]["content"].encode(),root=repo)
                    self.assertFalse(result["artifactCurrent"] and
                                     result["historicalSourceComparedWithGit"])
                except (ValueError,KeyError,RuntimeError):
                    pass
                self.assertFalse(marker.exists())
            finally:
                os.environ["PATH"]=old
                for k,v in prior.items():
                    if v is None:os.environ.pop(k,None)
                    else:os.environ[k]=v

    def test_baseline_remains_accepted(self):
        result=verify_amendment(ROOT)
        self.assertEqual(result["sourceRowsPreserved"],52134)
        self.assertEqual(result["nativeFilesByteIdentical"],3744)
        self.assertEqual(result["historicalAnchor"],self.anchor)
        for domain in ("cybersecurity","web"):
            bundle=compile_request({"schemaVersion":1,"targetId":"omp@18.8.7",
                                    "baseProfile":"omp--nan-"+domain+"-balanced"})
            s=preflight(bundle["manifest"],bundle["native"]["content"].encode())
            self.assertTrue(s["artifactCurrent"])
            self.assertEqual(s["policyReviewed"],domain=="cybersecurity")
            self.assertFalse(s["readyForOperation"])

if __name__=="__main__":
    unittest.main()
