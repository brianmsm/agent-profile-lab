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

# Do not use executable names from PATH, a candidate-local include.path,
# fsmonitor, process filters or checkout hooks for ANY trust-boundary Git call.
TRUSTED_GIT="/usr/bin/git"
OVERRIDES=(
    "core.fsmonitor=false",
    "core.hooksPath=/dev/null",
    "core.untrackedCache=false",
    "core.pager=cat",
    "diff.external=/usr/bin/false",
    "protocol.ext.allow=never",
)

def git_environment():
    """Block inherited Git commands/config and untrusted executable resolution."""
    # Full allowlist, not merely GIT_* filtering: dynamic loader variables
    # (LD_PRELOAD, LD_AUDIT, DYLD_*) execute before Git itself starts.
    # No operator HOME, shell functions, Python variables or user config
    # should cross into the fixed system Git process.
    env={
        "PATH":"/usr/bin:/bin",
        "HOME":"/nonexistent",
        "LANG":"C.UTF-8",
        "LC_ALL":"C.UTF-8",
        "GIT_CONFIG_NOSYSTEM":"1",
        "GIT_CONFIG_GLOBAL":"/dev/null",
        "GIT_CONFIG_SYSTEM":"/dev/null",
        "GIT_NO_REPLACE_OBJECTS":"1",
        "GIT_OPTIONAL_LOCKS":"0",
        "GIT_NO_LAZY_FETCH":"1",
        "GIT_TERMINAL_PROMPT":"0",
        "GIT_PAGER":"cat",
        "GIT_LFS_SKIP_SMUDGE":"1",
    }
    # Git honours explicit -c options above repository .git/config. A
    # separate metadata gate additionally rejects executable local settings.
    return env

def validate_git_metadata(repo:Path)->None:
    """Fail closed on candidate-local Git options that can launch programs.

    Read the config as bytes BEFORE the first Git process. This gate is for
    independent standalone checkouts (not linked worktrees). Git includes,
    process hooks, filters, external diff/merge and upload-pack helpers are
    intentionally unsupported. The whole signing repository runs separately
    from candidate-build processes.
    """
    repo=Path(repo).resolve(strict=True)
    directory=repo/".git"
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("Require a standalone Git metadata directory, not a linked worktree")
    # Git still honours grafts with GIT_NO_REPLACE_OBJECTS=1. Even an
    # apparently stale/empty graft file is unsupported provenance metadata.
    # Refuse before any Git traversal or ancestry-dependent path selection.
    for unsupported in ("info/grafts", "shallow"):
        item=directory/unsupported
        if item.exists() or item.is_symlink():
            raise ValueError("Unauthenticated Git ancestry metadata refused: "+unsupported)
    config=directory/"config"
    if config.is_symlink() or not config.is_file() or config.stat().st_size>1_048_576:
        raise ValueError("Unsafe or missing local Git configuration")
    if (directory/"config.worktree").exists() or (directory/"config.worktree").is_symlink():
        raise ValueError("Separate local Git worktree configuration is unsupported")
    try:
        text=config.read_bytes().decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Invalid local Git configuration encoding") from exc
    if "\x00" in text:
        raise ValueError("Invalid NUL in local Git configuration")
    section=""
    for line in text.splitlines():
        stripped=line.strip()
        if not stripped or stripped.startswith(("#",";")):
            continue
        if stripped.startswith("["):
            m=re.fullmatch(r'\[\s*([a-zA-Z][a-zA-Z0-9.-]*)(?:\s+[^\]]+)?\s*\]\s*(?:[;#].*)?',stripped)
            if not m:raise ValueError("Unrecognised local Git configuration section")
            section=m.group(1).casefold()
            if (section.startswith("include") or section in
                  {"filter","credential","alias","diff","merge","uploadpack",
                   "receive","http","https","core.fsmonitor"}):
                raise ValueError("Executable or external Git configuration section refused: "+section)
            continue
        key=stripped.split("=",1)[0].strip().casefold()
        if not re.fullmatch(r"[a-z0-9._-]+",key):
            raise ValueError("Unrecognised local Git configuration key")
        if section=="core" and key in {
            "fsmonitor","hookspath","sshcommand","pager","worktree",
            "attributesfile","gitproxy","askpass","excludesfile"
        }:
            raise ValueError("Executable local Git configuration key refused: core."+key)
        if section=="protocol" and key not in {"version"}:
            raise ValueError("Nonstandard local Git protocol controls refused")
        if section=="extensions" and key=="worktreeconfig":
            raise ValueError("Worktree-local override configuration refused")

def git_bytes(repo:Path,*args:str,input:bytes|None=None,timeout:int=90)->bytes:
    """Use a fixed executable and conservative configuration from the first call."""
    validate_git_metadata(repo)
    done=subprocess.run(
        [TRUSTED_GIT,*sum((["-c",flag] for flag in OVERRIDES),[]),
         "-C",str(repo),*args],
        input=input,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
        timeout=timeout,env=git_environment())
    if done.returncode:
        raise ValueError("Immutable Git object inspection failed: "+str(args[:2]))
    return done.stdout


def verified_git_objects(repo:Path,oids:list[str],fmt:str)->dict[str,tuple[str,bytes]]:
    """Parse raw cat-file framing and verify each payload against its OID.

    All tree and commit bytes, not just blob bytes, must hash to the OID
    referenced by their authenticated parent.
    """
    if not oids:return {}
    digest_len=40 if fmt=="sha1" else 64 if fmt=="sha256" else 0
    if not digest_len or any(not isinstance(x,str) or len(x)!=digest_len or
                             not OID.fullmatch(x) for x in oids):
        raise ValueError("Invalid Git OID for authenticated object request")
    raw=git_bytes(repo,"cat-file","--batch",
                  input=("\n".join(oids)+"\n").encode(),timeout=120)
    cursor=0
    result={}
    for oid in oids:
        end=raw.find(b"\n",cursor)
        if end<0:raise ValueError("Truncated authenticated Git header")
        header=raw[cursor:end].decode("ascii").split()
        if len(header)!=3 or header[0]!=oid or header[1] not in ("commit","tree","blob"):
            raise ValueError("Incorrect authenticated Git object header")
        if not header[2].isdigit() or len(header[2])>12:
            raise ValueError("Invalid Git object payload size")
        size=int(header[2])
        if size>MAX_BLOB_BYTES:
            raise ValueError("Oversized authenticated Git object")
        start=end+1;finish=start+size
        if finish>=len(raw) or raw[finish:finish+1]!=b"\n":
            raise ValueError("Truncated authenticated Git object")
        data=raw[start:finish]
        hashed=header[1].encode()+b" "+str(size).encode()+b"\0"+data
        if hashlib.new(fmt,hashed).hexdigest()!=oid:
            raise ValueError("Git commit/tree/blob object OID does not match actual payload")
        cursor=finish+1
        result[oid]=(header[1],data)
    if cursor!=len(raw):
        raise ValueError("Unexpected trailing authenticated Git payload")
    return result


def _commit_fields(raw:bytes,fmt:str)->tuple[str,list[str]]:
    """Extract tree and parents from an already verified canonical Git commit."""
    oid_len=40 if fmt=="sha1" else 64
    header=raw.split(b"\n\n",1)[0]
    lines=header.split(b"\n")
    if not lines or not lines[0].startswith(b"tree "):
        raise ValueError("Missing canonical commit tree header")
    tree=lines[0][5:].decode("ascii")
    parents=[]
    for line in lines[1:]:
        if line.startswith(b"parent "):
            parents.append(line[7:].decode("ascii"))
    if len(tree)!=oid_len or not OID.fullmatch(tree):
        raise ValueError("Malformed verified commit tree OID")
    if any(len(parent)!=oid_len or not OID.fullmatch(parent) for parent in parents):
        raise ValueError("Malformed verified commit ancestry")
    if len(parents)!=len(set(parents)):
        raise ValueError("Duplicate Git parent OID")
    return tree,parents


def _tree_entries(raw:bytes,fmt:str)->list[tuple[str,str,str]]:
    """Parse canonical Git tree binary, not git ls-tree's mutable report."""
    width=20 if fmt=="sha1" else 32
    offset=0
    seen=set()
    entries=[]
    while offset<len(raw):
        space=raw.find(b" ",offset)
        if space<0:raise ValueError("Malformed Git tree mode delimiter")
        mode=raw[offset:space].decode("ascii")
        name_end=raw.find(b"\0",space+1)
        if name_end<0:raise ValueError("Malformed Git tree name framing")
        name=raw[space+1:name_end].decode("utf-8")
        if (not name or name in (".","..") or "/" in name or
            "\\" in name or "\0" in name or name in seen):
            raise ValueError("Unsafe or duplicated verified Git tree entry")
        oid_start=name_end+1
        oid_raw=raw[oid_start:oid_start+width]
        if len(oid_raw)!=width:
            raise ValueError("Truncated verified Git tree child OID")
        child=oid_raw.hex()
        if mode not in ALLOWED_MODES and mode!="40000":
            raise ValueError("Unexpected Git tree mode; symbolic links/submodules unsupported")
        entries.append((mode,name,child))
        seen.add(name)
        offset=oid_start+width
    return entries


def verified_git_history_inventories(
    repo:Path,commit:str,fmt:str,revisions:list[str],
    *, verified_parents:dict[str,list[str]]|None=None,
)->dict[str,dict[str,tuple[str,str]]]:
    """Authenticate *all* reachable ancestry objects, not just changed leaves.

    Deduplicate commits, trees and blobs by physical OID. Validate the canonical
    Git payload framing, full digest and physical object type before consuming
    ls-tree/diff-tree metadata. Return inventories only for requested revisions.
    Reject over-budget histories rather than silently skip any reachable object.
    """
    width={"sha1":40,"sha256":64}.get(fmt)
    if width is None:
        raise ValueError("Unsupported Git hash format")
    for oid in [commit,*revisions]:
        if not isinstance(oid,str) or len(oid)!=width or not OID.fullmatch(oid):
            raise ValueError("Historical authentication needs full Git object IDs")

    byte_budget=1_000_000_000
    object_budget=200_000
    bytes_seen=0
    commits={}
    roots={}
    pending=[commit]
    while pending:
        todo=list(dict.fromkeys(x for x in pending if x not in commits))
        pending=[]
        for offset in range(0,len(todo),48):
            chunk=todo[offset:offset+48]
            objects=verified_git_objects(repo,chunk,fmt)
            for oid in chunk:
                kind,raw=objects[oid]
                if kind!="commit":
                    raise ValueError("Historical ancestry points to non-commit object")
                tree,parents=_commit_fields(raw,fmt)
                commits[oid]=parents
                roots[oid]=tree
                bytes_seen+=len(raw)
                if bytes_seen>byte_budget or len(commits)>4096:
                    raise ValueError("Git ancestry authentication budget exceeded")
                pending.extend(parent for parent in parents if parent not in commits)
    if any(oid not in commits for oid in revisions):
        raise ValueError("Requested historical revision is not a reachable ancestor")
    if verified_parents is not None:
        # Export only ancestry recovered from SHA-bound *physical* commit bytes.
        # Never substitute rev-list --parents or a mutable Git graft view.
        verified_parents.clear()
        verified_parents.update((oid,list(parents)) for oid,parents in commits.items())

    # Traverse every ancestor's root tree, deduplicating subtrees by OID. A
    # baseline-inherited LICENSE leaf is therefore authenticated even when
    # no post-baseline diff ever mentioned it.
    trees={}
    leaves=set()
    pending=[(tree,0) for tree in roots.values()]
    while pending:
        current=pending
        pending=[]
        for offset in range(0,len(current),48):
            batch=current[offset:offset+48]
            todo={oid:depth for oid,depth in batch if oid not in trees}
            if not todo:continue
            if any(depth>128 for depth in todo.values()):
                raise ValueError("Excessively deep historical Git tree")
            objects=verified_git_objects(repo,list(todo),fmt)
            for oid in todo:
                kind,raw=objects[oid]
                if kind!="tree":
                    raise ValueError("Historical root/subtree is not physically a Git tree")
                entries=_tree_entries(raw,fmt)
                trees[oid]=entries
                bytes_seen+=len(raw)
                for mode,name,child in entries:
                    if mode=="40000":
                        if child not in trees:pending.append((child,todo[oid]+1))
                    else:
                        leaves.add(child)
                if (len(commits)+len(trees)+len(leaves)>object_budget
                        or bytes_seen>byte_budget):
                    raise ValueError("Git historical tree authentication budget exceeded")
    # Every leaf has to be a *real* verified blob. Checking only ls-tree's
    # declared mode is insufficient (a 100644 leaf can point to a commit).
    ordered=sorted(leaves)
    if ordered:
        # Batch-check is used ONLY to size safe batches, never as an
        # authenticity oracle. A forged size/type cannot bypass the subsequent
        # SHA-bound raw cat-file framing, kind and OID rehash for every leaf.
        reported=git_bytes(repo,"cat-file","--batch-check",
                           input=("\n".join(ordered)+"\n").encode("ascii"),
                           timeout=120).splitlines()
        if len(reported)!=len(ordered):
            raise ValueError("Incomplete Git leaf sizing inventory")
        expected_sizes={}
        for oid,line in zip(ordered,reported):
            cols=line.decode("ascii").split()
            if (len(cols)!=3 or cols[0]!=oid or cols[1]!="blob"
                    or not cols[2].isdigit() or len(cols[2])>12):
                raise ValueError("Historical Git leaf has non-blob physical type or invalid size")
            size=int(cols[2])
            if size>MAX_BLOB_BYTES:
                raise ValueError("Oversized historical Git blob")
            expected_sizes[oid]=size
        if sum(expected_sizes.values())>byte_budget-bytes_seen:
            raise ValueError("Git historical blob authentication budget exceeded")

        # A single Git subprocess can authenticate many small leaf objects.
        # Limit both count and total advertised bytes to bound peak output
        # memory; unusually large individual blobs remain singleton batches.
        pending_batch=[]
        batch_bytes=0
        batches=[]
        max_batch_bytes=16*1024*1024
        for oid in ordered:
            size=expected_sizes[oid]
            if pending_batch and (len(pending_batch)>=64 or
                                  batch_bytes+size>max_batch_bytes):
                batches.append(pending_batch)
                pending_batch=[]
                batch_bytes=0
            pending_batch.append(oid)
            batch_bytes+=size
        if pending_batch:batches.append(pending_batch)
        for chunk in batches:
            objects=verified_git_objects(repo,chunk,fmt)
            for oid in chunk:
                kind,raw=objects[oid]
                if kind!="blob" or len(raw)!=expected_sizes[oid]:
                    raise ValueError("Historical Git leaf physical kind/size changed during audit")
                bytes_seen+=len(raw)
                if bytes_seen>byte_budget:
                    raise ValueError("Historical Git blob authentication budget exceeded")

    result={}
    for revision in dict.fromkeys(revisions):
        inventory={}
        stack=[(roots[revision],"",0)]
        while stack:
            tree,prefix,depth=stack.pop()
            if depth>128:
                raise ValueError("Excessively deep requested historical Git tree")
            for mode,name,child in trees[tree]:
                path=prefix+name
                if mode=="40000":
                    stack.append((child,path+"/",depth+1))
                else:
                    if path in inventory:
                        raise ValueError("Duplicate path in authenticated historical tree")
                    inventory[path]=(mode,child)
                    if len(inventory)>150000:
                        raise ValueError("Oversized historical inventory")
        result[revision]=inventory
    return result


def verified_git_tree_inventory(repo:Path,commit:str,fmt:str)->dict[str,tuple[str,str]]:
    """Fully authenticate reachable commits, all ancestral trees and all leaves."""
    return verified_git_history_inventories(repo,commit,fmt,[commit])[commit]



def read_committed_blob(repo:Path,commit:str,relative:str)->bytes:
    """Read and hash-check one exact historical blob without textconv/export."""
    if (not isinstance(relative,str) or relative.startswith("/") or
        "\\" in relative or ".." in Path(relative).parts):
        raise ValueError("Unsafe historical source pathname")
    entries=complete_git_tree(repo,commit,(relative,))
    if len(entries)!=1 or entries[0]["path"]!=relative:
        raise ValueError("Missing precise immutable historical file: "+relative)
    fmt=git_bytes(repo,"rev-parse","--show-object-format").decode().strip()
    return next(_blob_bytes(repo,entries,fmt))[1]

def complete_git_tree(repo:Path,commit:str,prefixes:tuple[str,...]=())->list[dict]:
    """Return exact tracked blobs, without Git index or export attribute filtering."""
    if not OID.fullmatch(commit):
        raise ValueError("A full immutable commit identifier is required")
    args=("ls-tree","-rz","-l","--full-tree",commit)
    if prefixes:args+=("--",*prefixes)
    fmt=git_bytes(repo,"rev-parse","--show-object-format").decode().strip()
    authenticated=verified_git_tree_inventory(repo,commit,fmt)
    expected={path:(mode,oid) for path,(mode,oid) in authenticated.items()
              if not prefixes or any(path==prefix.rstrip("/") or
                 path.startswith(prefix.rstrip("/")+"/") for prefix in prefixes)}
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
        if expected.get(text)!=(mode,oid):
            raise ValueError("Git ls-tree inventory differs from authenticated tree objects")
        seen.add(text)
        result.append(dict(path=text,mode=mode,oid=oid,size=count))
    if seen!=set(expected):
        raise ValueError("Git ls-tree paths omit entries from authenticated tree objects")
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
            # Reject symlinks in every ancestor, not merely the terminal
            # filename. Identical bytes through an aliased directory are
            # not the same audited source-path topology.
            ancestor=repo
            for part in Path(name).parts[:-1]:
                ancestor=ancestor/part
                if ancestor.is_symlink() or not ancestor.is_dir():
                    raise ValueError("Tracked Git path ancestor is symlink/non-directory: "+name)
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
