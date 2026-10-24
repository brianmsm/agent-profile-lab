"""R3i independently authorised, exact-byte human-rights review barrier.

No review record is issued by candidate code. At runtime the trust roster and
signed decisions live OUTSIDE the checkout under administrator-controlled
paths. The fixed OpenSSL verifies Ed25519 public signatures only. Without an
independently enrolled reviewer and signed decision, REVIEW is DENIED.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import tempfile

TRUST_FILE=Path("/etc/agent-profile-lab/independent-review-trust.json")
DECISIONS_DIR=Path("/var/lib/agent-profile-lab/independent-reviews")
OPENSSL=Path("/usr/bin/openssl")
OID=re.compile(r"(?:[a-f0-9]{40}|[a-f0-9]{64})\Z")
SHA=re.compile(r"[a-f0-9]{64}\Z")
REVIEW_CODES=(
    "indeterminate-", "opaque-editorial-encoding-requires-independent-review",
)
ALLOWED_SURFACES={
    "source","history","pages-public","pages-reference","sync-source",
    "release-public","release-reference","release-frozen",
}

def canonical(value:dict)->bytes:
    return (json.dumps(value,ensure_ascii=False,sort_keys=True,
                       separators=(",",":"),allow_nan=False)+"\n").encode("utf-8")

def _unique(pairs):
    result={}
    for key,val in pairs:
        if key in result:
            raise ValueError("Ambiguous duplicate signed review key")
        result[key]=val
    return result

def read_json(blob:bytes)->dict:
    if len(blob)>512000 or not blob:
        raise ValueError("Oversized/empty human review artifact")
    v=json.loads(blob,object_pairs_hook=_unique)
    if not isinstance(v,dict):
        raise ValueError("Human review payload must be object")
    return v

def required_external_file(file:Path,*,directory:bool=False)->None:
    if file.is_symlink() or not file.exists():
        raise ValueError("External independently controlled review authority absent")
    st=file.lstat()
    if (st.st_uid!=0 or st.st_mode & 0o022
        or (directory and not stat.S_ISDIR(st.st_mode))
        or (not directory and not stat.S_ISREG(st.st_mode))):
        raise ValueError("Untrusted review authority filesystem ownership or permissions")
    # Parent directories are checked to prevent candidate-owned replacement.
    for parent in file.parents:
        if parent==Path("/"):break
        st=parent.lstat()
        if parent.is_symlink() or st.st_uid!=0 or st.st_mode & 0o022:
            raise ValueError("Untrusted review authority parent directory")

def _utc(raw:str)->datetime:
    if not isinstance(raw,str):
        raise ValueError("Missing or ambiguous review datetime")
    parsed=datetime.fromisoformat(raw.replace("Z","+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Naive independent review timestamp refused")
    return parsed.astimezone(timezone.utc)

def _verify_signature(pem:bytes,message:bytes,signature:bytes)->None:
    if not OPENSSL.is_file() or len(pem)>16000 or len(signature)!=64:
        raise ValueError("Invalid Ed25519 review key, signature or verifier")
    with tempfile.TemporaryDirectory(prefix="apl-review-verify-") as t:
        folder=Path(t)
        key=folder/"verify.pem"
        msg=folder/"message.json"
        sig=folder/"signature.raw"
        for file,contents in ((key,pem),(msg,message),(sig,signature)):
            file.write_bytes(contents)
        check=subprocess.run(
            [str(OPENSSL),"pkeyutl","-verify","-pubin",
             "-inkey",str(key),"-rawin","-in",str(msg),"-sigfile",str(sig)],
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            env={"PATH":"/usr/bin:/bin","LC_ALL":"C.UTF-8","HOME":"/nonexistent"},
            timeout=10,close_fds=True)
        if check.returncode:
            raise ValueError("Independent Ed25519 reviewer signature invalid")

def is_review_code(reason:str)->bool:
    return reason.startswith(REVIEW_CODES)

def needs_review(reasons:list[str])->bool:
    return bool(reasons) and all(is_review_code(r) for r in reasons)

def _context(*,head:str,surface:str,path:str,blob:bytes,
             commit:str|None=None,reasons:list[str]|None=None)->dict:
    if not isinstance(head,str) or not OID.fullmatch(head):
        raise ValueError("Review requires exact candidate Git HEAD")
    if surface not in ALLOWED_SURFACES:
        raise ValueError("Unrecognized review scope")
    if (not isinstance(path,str) or not path or len(path)>8192 or
        path.startswith("/") or "\\" in path or
        ".." in PurePosixPath(path).parts or
        any(ord(c)<32 for c in path)):
        raise ValueError("Unsafe or ambiguous reviewed relative path")
    if commit is not None and not OID.fullmatch(commit):
        raise ValueError("Invalid reviewed history commit")
    if not isinstance(blob,bytes):
        raise ValueError("Review bytes must be immutable byte payload")
    codes=sorted(set(reasons or []))
    if any(not isinstance(r,str) or len(r)>180 for r in codes):
        raise ValueError("Invalid review reason code")
    return {"candidateHEAD":head,"surface":surface,"path":path,
            "sha256":hashlib.sha256(blob).hexdigest(),"commit":commit,
            "reasons":codes}

def _approve(context:dict,package:dict,roster:dict,*,now:datetime|None=None)->dict:
    if set(package)!={"document","ed25519Signature"}:
        raise ValueError("Invalid independent review package fields")
    d=package["document"]
    required={"schemaVersion","kind","decision","reviewerID","reviewID",
              "issuedAt","expiresAt","revoked","context","rights"}
    if not isinstance(d,dict) or set(d)!=required:
        raise ValueError("Unrecognized independent review decision schema")
    if d["schemaVersion"]!=1 or d["kind"]!="APL_INDEPENDENT_RIGHTS_REVIEW":
        raise ValueError("Wrong signed review document kind/version")
    if d["decision"]!="APPROVE" or d["revoked"] is not False:
        raise ValueError("Non-approving or revoked independent review")
    if d["context"]!=context:
        raise ValueError("Review is not bound to candidate HEAD/surface/path/exact bytes")
    reviewer=d["reviewerID"]
    if not isinstance(reviewer,str) or not re.fullmatch(r"[A-Za-z0-9._-]{3,96}",reviewer):
        raise ValueError("Unverifiable independent reviewer identity")
    if (not isinstance(d["reviewID"],str)
        or not re.fullmatch(r"[A-Za-z0-9._-]{8,128}",d["reviewID"])):
        raise ValueError("Invalid review identifier")
    rights=d["rights"]
    if (not isinstance(rights,dict)
        or set(rights)!={"provenanceExamined","licensesExamined","attributionExamined",
                         "redistributionAllowed","scopeDescription","sourceDocuments"}
        or any(rights.get(k) is not True for k in
               ("provenanceExamined","licensesExamined","attributionExamined",
                "redistributionAllowed"))
        or not isinstance(rights["scopeDescription"],str)
        or not 20<=len(rights["scopeDescription"])<=4000
        or not isinstance(rights["sourceDocuments"],list)
        or not rights["sourceDocuments"]
        or len(rights["sourceDocuments"])>200
        or any(not isinstance(x,str) or not 8<=len(x)<=2048
               for x in rights["sourceDocuments"])):
        raise ValueError("Unexamined independent redistribution/provenance/attribution rights")
    issue=_utc(d["issuedAt"]);expiry=_utc(d["expiresAt"])
    current=(now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if issue>current or expiry<=current or expiry<=issue:
        raise ValueError("Review missing valid issuance/expiry period")
    if set(roster)!={"schemaVersion","reviewers","revocations"} or roster["schemaVersion"]!=1:
        raise ValueError("Invalid independent externally installed reviewer roster")
    known=roster["reviewers"]
    if not isinstance(known,dict) or reviewer not in known:
        raise ValueError("Reviewer identity not independently enrolled")
    entry=known[reviewer]
    if (not isinstance(entry,dict)
        or set(entry)!={"publicKeyPEM","active","independent"}
        or entry["active"] is not True or entry["independent"] is not True):
        raise ValueError("Reviewer revoked/not independent/not active in roster")
    if (not isinstance(roster["revocations"],list)
        or d["reviewID"] in roster["revocations"]
        or reviewer in roster["revocations"]):
        raise ValueError("Independent review was revoked or roster is invalid")
    try:
        key=base64.b64decode(entry["publicKeyPEM"],validate=True)
        sig=base64.b64decode(package["ed25519Signature"],validate=True)
    except (ValueError,TypeError) as exc:
        raise ValueError("Invalid trusted public key or signed decision encoding") from exc
    _verify_signature(key,canonical(d),sig)
    return {"status":"INDEPENDENT_SIGNED_EXACT_BYTES_REVIEW",
            "reviewID":d["reviewID"],"reviewerID":reviewer,
            "head":context["candidateHEAD"],"surface":context["surface"],
            "path":context["path"],"sha256":context["sha256"],
            "expiresAt":d["expiresAt"]}

def enforce(head:str,surface:str,path:str,blob:bytes,
            *,commit:str|None=None,reasons:list[str]|None=None,
            trust_file:Path=TRUST_FILE,decisions_dir:Path=DECISIONS_DIR,
            allow_synthetic_test_roots:bool=False,
            now:datetime|None=None)->dict:
    """Exact-byte and HEAD-scoped human decision, absent=>DENY.

    Synthetic roots may only be passed by explicit offline test code; public
    production call sites use immutable default paths and never pass overrides.
    """
    context=_context(head=head,surface=surface,path=path,blob=blob,
                     commit=commit,reasons=reasons)
    if not allow_synthetic_test_roots:
        if trust_file!=TRUST_FILE or decisions_dir!=DECISIONS_DIR:
            raise ValueError("Candidate cannot choose review trust roots")
        required_external_file(trust_file)
        required_external_file(decisions_dir,directory=True)
    digest=hashlib.sha256(canonical(context)).hexdigest()
    record=decisions_dir/(digest+".json")
    if not record.is_file() or record.is_symlink():
        raise ValueError("Missing independent exact-byte review decision")
    if not allow_synthetic_test_roots:required_external_file(record)
    roster=read_json(trust_file.read_bytes())
    package=read_json(record.read_bytes())
    return _approve(context,package,roster,now=now)

def gate(reasons:list[str],head:str,surface:str,path:str,blob:bytes,
         *,commit:str|None=None)->list[str]:
    """NEVER downgrade an unequivocal PROHIBITED result to REVIEW."""
    if not reasons:return []
    if not needs_review(reasons):
        return list(reasons)
    enforce(head,surface,path,blob,commit=commit,reasons=reasons)
    return []   # authenticated exact-scope reviewer authorisation, not public release

def pages_release_gate(public_head:str,site:str,assets:dict[str,str])->dict:
    """Separately require exact-site independent rights clearance before upload."""
    if site not in ("public","reference"):
        raise ValueError("Unknown Pages release target")
    if len(assets)!=17 or any(not SHA.fullmatch(v) for v in assets.values()):
        raise ValueError("Unexpected reviewed 17-file Pages inventory")
    blob=canonical(assets)
    return enforce(public_head,"release-"+site,site+"/manifest.json",blob,
                   reasons=["indeterminate-final-human-rights-approval"])

def frozen_release_gate(public_head:str,stage_manifest_bytes:bytes)->dict:
    return enforce(public_head,"release-frozen","FROZEN_STAGE.json",
                   stage_manifest_bytes,
                   reasons=["indeterminate-final-human-rights-approval"])

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser(description="R3i exact-byte independent rights gate")
    p.add_argument("--pages",choices=("public","reference"),required=True)
    p.add_argument("--built",type=Path,required=True)
    p.add_argument("--repo",type=Path,required=True)
    args=p.parse_args()
    # Compute actual site inventory, never trust a supplied hash manifest.
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
    from git_object_integrity import git_bytes
    repo=args.repo.resolve(strict=True)
    head=git_bytes(repo,"rev-parse","HEAD").decode().strip()
    built=args.built.resolve(strict=True)
    if not built.is_dir():raise ValueError("Missing staged Pages")
    assets={}
    for f in built.rglob("*"):
        if f.is_symlink():raise ValueError("Pages symlink not reviewable")
        if f.is_file():
            assets[f.relative_to(built).as_posix()]=hashlib.sha256(f.read_bytes()).hexdigest()
    print(json.dumps(pages_release_gate(head,args.pages,assets),indent=2))
