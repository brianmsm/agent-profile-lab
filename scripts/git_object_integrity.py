"""Direct, index/attributes/replace-insensitive SHA-bound Git blob inspection.

Use git ls-tree -rz -l plus git cat-file --batch with a sanitized Git
environment. Git archive is forbidden because export-ignore, export-subst
and refs/replace can transform/omit the historical files.
"""
from __future__ import annotations
import hashlib
import os
import re
import stat
import subprocess
from pathlib import Path

ALLOWED_MODES={"100644","100755"}
MAX_BLOB_BYTES=150_000_000
OID=re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")

def git_environment():
    """Strip caller-controlled Git overrides, ignoring the index entirely."""
    env={k:v for k,v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_NO_REPLACE_OBJECTS="1",GIT_OPTIONAL_LOCKS="0",
               GIT_NO_LAZY_FETCH="1",GIT_CONFIG_NOSYSTEM="1")
    return env

def git_bytes(repo:Path,*args:str,input:bytes|None=None,timeout:int=90)->bytes:
    done=subprocess.run(["/usr/bin/git","-C",str(repo),*args],input=input,
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout,
        env=git_environment())
    if done.returncode:
        raise ValueError("Immutable Git object inspection failed: "+str(args[:2]))
    return done.stdout

def complete_git_tree(repo:Path,commit:str,prefixes:tuple[str,...]=())->list[dict]:
    """Return exact tracked blobs, without Git index or export attribute filtering."""
    if not OID.fullmatch(commit):
        raise ValueError("A full immutable commit identifier is required")
    args=("ls-tree","-rz","-l","--full-tree",commit)
    if prefixes:args+=("--",*prefixes)
    data=git_bytes(repo,*args)
    seen=set()
    result=[]
    for raw in data.split(b"\x00"):
        if not raw:continue
        meta,separator,name=raw.partition(b"\t")
        fields=meta.decode("ascii").split()
        if not separator or len(fields)!=4:
            raise ValueError("Malformed immutable Git tree inventory")
        mode,kind,oid,size=fields
        if mode not in ALLOWED_MODES or kind!="blob" or not size.isdigit():
            raise ValueError("Unexpected Git object mode/type/size")
        if not OID.fullmatch(oid):
            raise ValueError("Malformed immutable Git object identity")
        count=int(size)
        if count>MAX_BLOB_BYTES:
            raise ValueError("Unapproved oversized tracked Git blob")
        text=name.decode("utf-8")
        parts=Path(text)
        if (parts.is_absolute() or '..' in parts.parts or '\\' in text or
                text.startswith("./") or text in seen):
            raise ValueError("Unsafe or duplicated Git tree path")
        seen.add(text)
        result.append(dict(path=text,mode=mode,oid=oid,size=count))
    return result

def _blob_bytes(repo:Path,entries:list[dict],fmt:str):
    raw=git_bytes(repo,"cat-file","--batch",input=(
        "\n".join(item["oid"] for item in entries)+"\n").encode("ascii"),timeout=120)
    cursor=0
    for item in entries:
        end=raw.find(b"\n",cursor)
        if end<0:raise ValueError("Truncated Git cat-file header")
        header=raw[cursor:end].decode("ascii").split()
        if header!=[item["oid"],"blob",str(item["size"])]:
            raise ValueError("Git blob identity, type or size mismatch")
        start=end+1
        finish=start+item["size"]
        if finish>=len(raw) or raw[finish:finish+1]!=b"\n":
            raise ValueError("Truncated Git object or invalid framing")
        data=raw[start:finish]
        content=b"blob "+str(len(data)).encode()+b"\x00"+data
        if hashlib.new(fmt,content).hexdigest()!=item["oid"]:
            raise ValueError("Git blob payload does not hash to the reviewed object ID")
        cursor=finish+1
        yield item,data
    if cursor!=len(raw):raise ValueError("Unexpected trailing Git object data")

def verify_worktree_blobs(
    repo:Path,commit:str,prefixes:tuple[str,...]=(),
    *,required_count:int|None=None,minimum_count:int=0,minimum_bytes:int=0,
)->dict:
    """Compare real file bytes and modes to every direct reviewed Git object."""
    repo=repo.resolve(strict=True)
    if repo.is_symlink() or not repo.is_dir():
        raise ValueError("Invalid Git review root")
    fmt=git_bytes(repo,"rev-parse","--show-object-format").decode().strip()
    if fmt not in ("sha1","sha256"):
        raise ValueError("Unsupported immutable Git object format")
    tree=complete_git_tree(repo,commit,prefixes)
    if ((required_count is not None and len(tree)!=required_count) or
            len(tree)<minimum_count):
        raise ValueError("Historical Git tree inventory count mismatch")
    seen=set()
    total=0
    for offset in range(0,len(tree),24):
        for item,original in _blob_bytes(repo,tree[offset:offset+24],fmt):
            name=item["path"];path=repo/name
            if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(repo):
                raise ValueError("Tracked worktree Git blob missing or unsafe: "+name)
            st=path.stat()
            if st.st_size!=item["size"]:
                raise ValueError("Tracked worktree size differs from Git blob: "+name)
            if bool(st.st_mode&stat.S_IXUSR)!=(item["mode"]=="100755"):
                raise ValueError("Tracked executable mode differs from Git tree: "+name)
            if path.read_bytes()!=original:
                raise ValueError("Tracked worktree differs from immutable historic Git blob: "+name)
            total+=len(original);seen.add(name)
    if total<minimum_bytes:raise ValueError("Unexpectedly small reviewed Git source tree")
    if prefixes:
        actual={p.relative_to(repo).as_posix() for prefix in prefixes
                for p in (repo/prefix).rglob("*") if p.is_file() or p.is_symlink()}
        if actual!=seen:raise ValueError("Native worktree path inventory differs from Git tree")
    return {"trackedGitBlobsCompared":len(seen),"totalBytesCompared":total,
            "gitIndexUsed":False,"gitArchiveUsed":False,
            "gitattributesExportAttributesIgnored":True,
            "gitReplaceObjectsDisabled":True,"objectHashVerified":True,
            "modeAndPathVerified":True}
