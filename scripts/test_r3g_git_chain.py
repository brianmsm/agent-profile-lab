#!/usr/bin/env python3
"""R3g raw Git commit/tree/blob chain negatives, disposable synthetic repo."""
from __future__ import annotations
import hashlib,os,subprocess,tempfile,unittest,zlib
from pathlib import Path
from git_object_integrity import read_committed_blob,verified_git_tree_inventory,git_bytes

def git(repo:Path,*args):
    return subprocess.check_output(["/usr/bin/git","-C",str(repo),*args],
                                   stderr=subprocess.PIPE).decode().strip()

class IdentityChain(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="apl-r3g-git-object-")
        self.repo=Path(self.temp.name)
        git(self.repo,"init","-q","-b","main")
        git(self.repo,"config","user.name","Synthetic")
        git(self.repo,"config","user.email","synthetic@example.invalid")
        (self.repo/"docs").mkdir()
        (self.repo/"docs/example.md").write_text("Safe synthetic original\n")
        git(self.repo,"add","docs/example.md")
        git(self.repo,"-c","core.hooksPath=/dev/null","commit","-qm","Synthetic original")
        self.head=git(self.repo,"rev-parse","HEAD")

    def tearDown(self):self.temp.cleanup()

    def replace_loose(self,oid:str,kind:str,data:bytes):
        p=self.repo/".git/objects"/oid[:2]/oid[2:]
        p.parent.mkdir(parents=True,exist_ok=True)
        if p.exists():p.chmod(0o600)
        p.write_bytes(zlib.compress(kind.encode()+b" "+str(len(data)).encode()+b"\0"+data))

    def test_positive_commit_and_tree_chain(self):
        verified=verified_git_tree_inventory(self.repo,self.head,"sha1")
        self.assertIn("docs/example.md",verified)
        self.assertEqual(read_committed_blob(self.repo,self.head,"docs/example.md"),
                         b"Safe synthetic original\n")

    def test_valid_new_leaf_under_poisoned_original_tree_oid(self):
        old_tree=git(self.repo,"rev-parse","HEAD:docs")
        old_leaf=git(self.repo,"rev-parse","HEAD:docs/example.md")
        candidate=b"Different synthetic source\n"
        new_leaf=subprocess.check_output(
            ["/usr/bin/git","-C",str(self.repo),"hash-object","-w","--stdin"],
            input=candidate).decode().strip()
        original=subprocess.check_output(
            ["/usr/bin/git","-C",str(self.repo),"cat-file","tree",old_tree])
        self.assertIn(bytes.fromhex(old_leaf),original)
        forged=original.replace(bytes.fromhex(old_leaf),bytes.fromhex(new_leaf))
        self.assertNotEqual(hashlib.sha1(b"tree "+str(len(forged)).encode()+b"\0"+forged).hexdigest(),old_tree)
        self.replace_loose(old_tree,"tree",forged)
        (self.repo/"docs/example.md").write_bytes(candidate)
        git(self.repo,"update-index","--skip-worktree","docs/example.md")
        with self.assertRaises(ValueError):
            read_committed_blob(self.repo,self.head,"docs/example.md")
        with self.assertRaises(ValueError):
            verified_git_tree_inventory(self.repo,self.head,"sha1")

    def test_commit_oid_poison_is_rejected_before_trusting_tree(self):
        original=subprocess.check_output(
            ["/usr/bin/git","-C",str(self.repo),"cat-file","commit",self.head])
        modified=original+b"\nSYNTHETIC EXTRA COMMIT DATA"
        self.replace_loose(self.head,"commit",modified)
        with self.assertRaises(ValueError):
            read_committed_blob(self.repo,self.head,"docs/example.md")

class R3hCompleteHistoricalAuthentication(unittest.TestCase):
    """SHA-1 and SHA-256 physical OID/kind tests in disposable loose-object repos."""

    @staticmethod
    def _store(repo: Path, fmt: str, kind: str, payload: bytes)->str:
        raw=kind.encode()+b" "+str(len(payload)).encode()+b"\0"+payload
        oid=hashlib.new(fmt,raw).hexdigest()
        location=repo/".git/objects"/oid[:2]/oid[2:]
        location.parent.mkdir(parents=True,exist_ok=True)
        location.write_bytes(zlib.compress(raw))
        return oid

    @staticmethod
    def _commit_raw(tree:str,parent:str|None=None)->bytes:
        blob=b"tree "+tree.encode()+b"\n"
        if parent:blob+=b"parent "+parent.encode()+b"\n"
        blob+=(b"author Synthetic <test@example.invalid> 0 +0000\n"
              b"committer Synthetic <test@example.invalid> 0 +0000\n\nfixture\n")
        return blob

    @staticmethod
    def _physical_oid(repo:Path,oid:str)->tuple[str,bytes]:
        result=subprocess.run(["/usr/bin/git","-C",str(repo),"cat-file","--batch"],
                       input=(oid+"\n").encode(),check=True,capture_output=True).stdout
        header,body=result.split(b"\n",1)
        parts=header.split()
        if len(parts)!=3 or parts[0].decode()!=oid:raise ValueError("Fixture did not serve object")
        return parts[1].decode(),body[:int(parts[2])]

    def _repo(self,fmt:str):
        temp=tempfile.TemporaryDirectory(prefix=f"apl-r3h-{fmt}-")
        repo=Path(temp.name)
        flags=["--object-format=sha256"] if fmt=="sha256" else []
        git(repo,"init","-q","-b","main",*flags)
        git(repo,"config","user.name","Synthetic")
        git(repo,"config","user.email","test@example.invalid")
        (repo/"old.txt").write_text("Original test blob\n")
        git(repo,"add","old.txt")
        git(repo,"-c","core.hooksPath=/dev/null","commit","-qm","older")
        ancestor=git(repo,"rev-parse","HEAD")
        (repo/"new.txt").write_text("New test blob\n")
        git(repo,"add","new.txt")
        git(repo,"-c","core.hooksPath=/dev/null","commit","-qm","newer")
        head=git(repo,"rev-parse","HEAD")
        self.assertNotEqual(ancestor,head)
        return temp,repo,ancestor,head

    def _poison_under_oid(self,repo:Path,oid:str,fmt:str)->None:
        kind,data=self._physical_oid(repo,oid)
        bad=data[:-1]+bytes([data[-1]^1])
        loc=repo/".git/objects"/oid[:2]/oid[2:]
        self.assertTrue(loc.is_file(),"Only loose-object effective corruption is admissible")
        loc.chmod(0o600)  # Git normally creates read-only loose ODB objects.
        loc.write_bytes(zlib.compress(kind.encode()+b" "+str(len(bad)).encode()+b"\0"+bad))
        actual_kind,served=self._physical_oid(repo,oid)
        self.assertEqual(served,bad,"Git did not serve the altered bytes")
        self.assertNotEqual(
            hashlib.new(fmt,actual_kind.encode()+b" "+str(len(served)).encode()+b"\0"+served).hexdigest(),oid)

    def test_all_ancestor_trees_sha1_sha256(self):
        from git_object_integrity import verified_git_history_inventories
        for fmt in ("sha1","sha256"):
            with self.subTest(format=fmt):
                tmp,repo,older,head=self._repo(fmt)
                with tmp:
                    self.assertIn("new.txt",verified_git_tree_inventory(repo,head,fmt))
                    self.assertIn(older,verified_git_history_inventories(repo,head,fmt,[older]))
                    tree=git(repo,"rev-parse",older+"^{tree}")
                    self._poison_under_oid(repo,tree,fmt)
                    with self.assertRaises(ValueError):
                        verified_git_tree_inventory(repo,head,fmt)
                    with self.assertRaises(ValueError):
                        verified_git_history_inventories(repo,head,fmt,[older])

    def test_inherited_leaf_oid_corruption_sha1_sha256(self):
        for fmt in ("sha1","sha256"):
            with self.subTest(format=fmt):
                tmp,repo,older,head=self._repo(fmt)
                with tmp:
                    oid=git(repo,"rev-parse",older+":old.txt")
                    self.assertEqual(oid,git(repo,"rev-parse",head+":old.txt"))
                    self._poison_under_oid(repo,oid,fmt)
                    git(repo,"update-index","--skip-worktree","old.txt")
                    self.assertEqual(git(repo,"status","--porcelain=v1"),"")
                    with self.assertRaises(ValueError):
                        verified_git_tree_inventory(repo,head,fmt)

    def test_physical_leaf_commit_type_sha1_sha256(self):
        from git_object_integrity import complete_git_tree
        for fmt in ("sha1","sha256"):
            with self.subTest(format=fmt):
                tmp,repo,older,head=self._repo(fmt)
                with tmp:
                    forged_tree=self._store(
                        repo,fmt,"tree",b"100644 bogus.txt\0"+bytes.fromhex(older))
                    forged_commit=self._store(repo,fmt,"commit",
                                              self._commit_raw(forged_tree,head))
                    with self.assertRaisesRegex(ValueError,"non-blob physical type"):
                        verified_git_tree_inventory(repo,forged_commit,fmt)
                    with self.assertRaises(ValueError):
                        complete_git_tree(repo,forged_commit)

    def test_corrupt_current_commit_subtree_sha1_sha256(self):
        for fmt in ("sha1","sha256"):
            with self.subTest(format=fmt):
                tmp,repo,older,head=self._repo(fmt)
                with tmp:
                    (repo/"sub").mkdir()
                    (repo/"sub/file.txt").write_text("Valid child\n")
                    git(repo,"add","sub/file.txt")
                    git(repo,"-c","core.hooksPath=/dev/null","commit","-qm","child")
                    latest=git(repo,"rev-parse","HEAD")
                    subtree=git(repo,"rev-parse",latest+":sub")
                    self._poison_under_oid(repo,subtree,fmt)
                    with self.assertRaises(ValueError):
                        verified_git_tree_inventory(repo,latest,fmt)
                tmp,repo,older,head=self._repo(fmt)
                with tmp:
                    self._poison_under_oid(repo,older,fmt)
                    with self.assertRaises(ValueError):
                        verified_git_tree_inventory(repo,head,fmt)

if __name__=="__main__":unittest.main(verbosity=2)
