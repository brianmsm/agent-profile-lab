#!/usr/bin/env python3
"""Audit public files and, optionally, every change after an approved Git baseline.

Read-only, offline and fail-closed. Findings contain paths/reasons, never matched
secrets. This is a release guard, not legal clearance or an adversarial DLP proof.
Pair it with verify_public_release.py, review, and the private transfer allowlist.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from strict_data_formats import json_loads_strict
APPROVED_PUBLIC_BASE = "58a682d6ca6f3ed0b595d7daed5208bc56bd9385"
MAX_BYTES = 128 * 1024 * 1024
BAD_COMPONENTS = {"evidence", "sources", "internal-research", "republication"}
RUNTIME_DIRS = {"node_modules", "dist", "__pycache__", "validation", ".venv", ".pytest_cache"}
REGENERATED = {
    "data/assignments.csv", "data/assignments.csv.gz", "data/assignments.json",
    "data/profiles.json", "data/model-catalog.json", "data/omp-runtime-policies.json",
    "policies/functional-precedents.json",
}
BAD_SUFFIXES = {".raw", ".pdf", ".sqlite", ".sqlite3", ".db", ".env", ".bundle",
                ".zip", ".tar", ".tgz", ".bz2", ".xz", ".7z", ".pyc", ".pyo"}
MUST_EXIST = ["LICENSE", "README.md", "THIRD_PARTY_NOTICES.md",
              "data/assignment-shards/manifest.json", "data/public-evidence/source-links.json",
              "dashboard/public/data/snapshot.json", "tools/verify_public_release.py"]
CHUNK = re.compile(r"dashboard/public/data/chunks/(?:core|evidence)-([a-f0-9]{64})\.json\.gz\Z")
PATTERNS = {
    "private-user-home": re.compile(rb"/(?:home|Users)/[A-Za-z0-9_.-]+/(?:Documents|\.config|\.local|Library)/", re.I),
    "github-access-token": re.compile(rb"(?:ghp_|gho_|ghu_|ghs_|github_pat_)[A-Za-z0-9_]{25,}"),
    "provider-api-secret": re.compile(rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}\b"),
    "private-key-PEM": re.compile(rb"-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----"),
    "long-bearer-token": re.compile(rb"\bBearer[ \t]+[A-Za-z0-9_.~-]{40,}\b", re.I),
}


def git(root: Path, *args: str) -> bytes:
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_NO_REPLACE_OBJECTS": "1"}
    return subprocess.check_output(["git", "-C", str(root), *args], env=env,
                                   stderr=subprocess.PIPE)


def path_reason(relative: str, *, tracked: bool = True) -> str | None:
    parts = PurePosixPath(relative).parts
    if (not parts or relative != PurePosixPath(relative).as_posix() or
            relative.startswith("/") or "\\" in relative or ".." in parts or
            any(ord(c) < 32 for c in relative)):
        return "unsafe-path"
    if ".git" in parts or ".gitmodules" in parts:
        return "nested-vcs-or-submodule"
    if any(p in BAD_COMPONENTS for p in parts) or parts[0] == "generated":
        return "private-source-archive-present"
    if tracked and (any(p in RUNTIME_DIRS for p in parts) or relative in REGENERATED):
        return "runtime-or-private-output-tracked"
    if any(p == ".env" or p.startswith(".env.") for p in parts):
        return "environment-file-not-approved"
    suffix = PurePosixPath(relative).suffix.lower()
    if suffix in BAD_SUFFIXES or (suffix == ".gz" and not CHUNK.fullmatch(relative)):
        return "archive-or-capture-not-authorized"
    return None


SCORE_FIELDS={'value','score','accuracy','scorepct','scorepercent','intelligenceindex','benchmarkscore','overallacc','overallaccuracy',
              'latency','tokenspersecond','modelscore','passrate'}
IDENTITY_FIELDS={'sourceid','publisher','sourceurl','source','provider','url'}
AGGREGATE_UNITS={'reference-links','reference-count','references','rows','source-count'}
NUMERIC=re.compile(r'[+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+)(?:[eE][+-]?\d+)?%?\Z')
SOURCE_TOKEN=re.compile(r'(?:sourceId|source_id|publisher)\s*["\x27\\]*\s*[:=]\s*["\x27\\]*([A-Za-z][A-Za-z0-9_-]{0,48})',re.I)
METRIC_TOKEN=re.compile(r'(?:value|score(?:_pct|Percent)?|accuracy|intelligence[_-]?index|benchmark[_-]?score)\s*["\x27\\]*\s*[:=]\s*["\x27\\]*\s*[+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+)',re.I)

def normalized_key(key: object) -> str:
    return re.sub('[^a-z0-9]','',str(key).lower())

def is_numeric_score(value: object) -> bool:
    return (isinstance(value,(int,float)) and not isinstance(value,bool)) or (
        isinstance(value,str) and bool(NUMERIC.fullmatch(value.strip())))

def legitimate_aggregate(row: dict) -> bool:
    kind=str(row.get('kind','')).lower()
    unit=str(row.get('unit','')).lower()
    return (kind=='aggregate-count' and unit in AGGREGATE_UNITS
            and isinstance(row.get('value'),int) and not isinstance(row.get('value'),bool)
            and not any(normalized_key(k) in ('model','benchmark','metric','evaluation') for k in row))

def numeric_source_rows(value: object) -> bool:
    """Detect typed direct and inherited publisher scores, not local oracles.

    An unknown sourceId by itself can identify a local test document; only
    carry numerical publisher context to descendants when the provenance is
    independently identified as external (AA/FCDATA or publisher website).
    """
    stack=[(value,False)]
    while stack:
        row,inherited_publisher=stack.pop()
        if isinstance(row,list):
            stack.extend((item,inherited_publisher) for item in row)
        elif isinstance(row,dict):
            lower={normalized_key(k):v for k,v in row.items()}
            source_id=str(lower.get('sourceid','')).lower()
            provenance=' '.join(str(lower.get(k,'')) for k in IDENTITY_FIELDS).lower()
            publisher=inherited_publisher or source_id in ('aa','fcdata') or any(
                x in provenance for x in ('artificialanalysis','slopalytics','frontiercode'))
            if source_id=='br-bfcl-data':publisher=False
            if legitimate_aggregate(row):continue
            numeric=any(k in SCORE_FIELDS or k.startswith(('scorepct','accuracy','benchmarkscore'))
                        for k,v in lower.items() if is_numeric_score(v))
            if numeric and (publisher or (source_id and source_id!='br-bfcl-data' and (
                 'sourceid' in lower and any(k in SCORE_FIELDS or k.startswith(('scorepct','accuracy'))
                                             for k,v in lower.items() if is_numeric_score(v))))):
                return True
            stack.extend((v,publisher) for v in row.values())
    return False

def tabular_score_reasons(relative: str, text: str) -> list[str]:
    """Block unreviewed publisher score tables; allow typed aggregate counts.

    Unknown editorial sources should be reviewed rather than silently
    treated as authorized based only on a transport SHA.
    """
    header=text.splitlines()[0] if text.splitlines() else ''
    delimiter='\t' if relative.lower().endswith('.tsv') else ';' if header.count(';')>header.count(',') else ','
    try:
        reader=csv.DictReader(io.StringIO(text,newline=''),delimiter=delimiter,restkey='__EXTRA__')
        fields=reader.fieldnames
        if not fields or len(fields)>128:return ['invalid-tabular-schema']
        normalized=[normalized_key(x.strip()) for x in fields]
        if len(set(normalized))!=len(normalized):return ['duplicate-tabular-column']
        scores=[name for name,norm in zip(fields,normalized) if norm in SCORE_FIELDS or norm.startswith(('scorepct','accuracy'))]
        if not scores:return []
        has_origin=bool(set(normalized)&IDENTITY_FIELDS)
        if not has_origin:return []  # local synthetic model/score fixtures without publisher provenance
        for row in reader:
            if '__EXTRA__' in row or any(v is None for v in row.values()):
                return ['malformed-tabular-score-row']
            normalized_row={normalized_key(k):v.strip() for k,v in row.items()}
            if (normalized_row.get('unit','').lower() in AGGREGATE_UNITS
                    and normalized_row.get('kind','aggregate-count').lower()=='aggregate-count'):
                continue
            source=' '.join(normalized_row.get(k,'') for k in IDENTITY_FIELDS).lower()
            if not source:continue
            if any(is_numeric_score(row.get(field,'')) for field in scores):
                return ['unreviewed-tabular-publisher-score']
        return []
    except (csv.Error,ValueError,TypeError):return ['invalid-tabular-schema']

def embedded_publisher_score(text: str) -> bool:
    """High-confidence visible literals, including JSX attributes and minified JS.

    This is a heuristic, not an exhaustive encoding-aware DLP system. Explicit
    pre-publication human source review remains mandatory.
    """
    flattened=text.replace('\\\"','"').replace("\\'", "'")
    for match in SOURCE_TOKEN.finditer(flattened):
        source=match.group(1).lower()
        if source in ('br-bfcl-data','synthetic','local'):continue
        snippet=flattened[match.end():match.end()+260]
        if METRIC_TOKEN.search(snippet):
            # Exclude documented review-count aggregations, not model scores.
            if re.search(r'(?:aggregate-count|reference-links)',snippet[:125],re.I) and source=='aa':
                continue
            return True
    return False

def inspect_payload(relative: str, data: bytes, *, max_bytes: int = MAX_BYTES) -> list[str]:
    reasons = []
    if len(data) > max_bytes:
        return ["file-size-limit"]
    match = CHUNK.fullmatch(relative)
    if match:
        if hashlib.sha256(data).hexdigest() != match[1]:
            reasons.append("compressed-name-hash-mismatch")
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream:
                decoded = stream.read(max_bytes + 1)
            if len(decoded) > max_bytes:
                return reasons + ["decompression-size-limit"]
            data = decoded
        except (OSError, EOFError):
            return reasons + ["invalid-compressed-json"]
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return reasons + ["unexpected-binary-file"]
    if "\0" in text:
        reasons.append("unexpected-binary-file")
    for label, pattern in PATTERNS.items():
        if pattern.search(data):
            reasons.append(label)
    if relative.lower().endswith(('.csv','.tsv')):
        reasons.extend(tabular_score_reasons(relative,text))
    if relative.lower().endswith(('.ts','.tsx','.js','.jsx','.html','.txt','.md','.css')):
        # Explicit historic review of this synthetic cybersecurity test file.
        # A future edit changes the SHA and must undergo renewed release review.
        vetted_test=(relative=='dashboard/tests/cybersecurityEvidence.test.tsx' and
                     hashlib.sha256(data).hexdigest()==
                     '7bef270f1a0d5b6dfa007936f0615548ede966b4c0fb85d2981ddd71b3498494')
        if not vetted_test and embedded_publisher_score(text):
            reasons.append('unreviewed-embedded-publisher-score')
    if relative.endswith(".json") or match:
        # TypeScript's two existing JSONC configs permit comments/trailing commas.
        # Strip only outside strings, and still validate/inspect the resulting JSON.
        if relative in {"dashboard/tsconfig.app.json", "dashboard/tsconfig.node.json"}:
            text = re.sub(r'"(?:\\.|[^"\\])*"|//[^\r\n]*|/\*[\s\S]*?\*/',
                          lambda m: m[0] if m[0].startswith('"') else ' ', text)
            text = re.sub(r'("(?:\\.|[^"\\])*")|,(\s*[}\]])',
                          lambda m: m[1] if m[1] is not None else m[2], text)
        try:
            value = json_loads_strict(text)
        except (ValueError, RecursionError):
            reasons.append("invalid-json")
        else:
            if numeric_source_rows(value):
                reasons.append("non-allowlisted-publisher-numeric-row")
    return reasons


def audit_built_site(built: Path, *, root: Path=ROOT) -> dict:
    """Independently check exactly what Pages uploads, after removing snapshot.json."""
    root=root.resolve();built=built.resolve()
    manifest=root/'dashboard/public/data/delivery.json'
    try:approved=json_loads_strict(manifest.read_bytes())
    except (ValueError,OSError,TypeError) as e:raise ValueError('Missing reviewed public delivery manifest') from e
    if set(approved.get('parts',{}))!={'core','evidence'}:raise ValueError('Unexpected public Pages delivery parts')
    expected={'data/delivery.json'}
    expected_chunks={}
    for item in approved['parts'].values():
        rel='data/'+item['path']
        if not CHUNK.fullmatch('dashboard/public/'+rel):
            raise ValueError('Unapproved content-addressed Pages fragment')
        expected.add(rel);expected_chunks[rel]=root/'dashboard/public'/rel
    observed=set()
    if not built.is_dir():raise ValueError('Missing generated Pages artifact')
    for item in built.rglob('*'):
        relative=item.relative_to(built).as_posix()
        if item.is_symlink():raise ValueError('Symlink in Pages artifact')
        if item.is_dir():continue
        if not item.is_file() or item.stat().st_size>MAX_BYTES:raise ValueError('Invalid Pages file size or type')
        observed.add(relative)
        if (relative not in expected and relative not in {'index.html','icons.svg','favicon.svg'}
                and not (relative.startswith('assets/') and item.suffix in {'.js','.css'})):
            raise ValueError('Unapproved Pages output file: '+relative)
        if relative in expected_chunks:
            if item.read_bytes()!=expected_chunks[relative].read_bytes():
                raise ValueError('Pages chunk differs from reviewed public source: '+relative)
            reasons=inspect_payload('dashboard/public/'+relative,item.read_bytes())
        elif relative=='data/delivery.json':
            if item.read_bytes()!=manifest.read_bytes():raise ValueError('Pages delivery manifest differs')
            reasons=inspect_payload(relative,item.read_bytes())
        else:
            reasons=inspect_payload(relative,item.read_bytes())
        if reasons:raise ValueError('Unapproved Pages content type/pattern in '+relative+': '+','.join(reasons))
    if not expected.issubset(observed) or 'index.html' not in observed:
        raise ValueError('Pages is missing approved content-addressed files or its entrypoint')
    return {'pagesFilesScanned':len(observed),'approvedChunks':len(expected_chunks),'verifiedAgainstPublicSource':True}

def tracked_paths(root: Path) -> set[str]:
    # Never inherit a parent private repository when auditing a staging directory.
    if not (root / ".git").exists():
        return set()
    actual = Path(git(root, "rev-parse", "--show-toplevel").decode().strip()).resolve()
    if actual != root.resolve():
        raise ValueError("Audit root is not the Git worktree root")
    return {p.decode() for p in git(root, "ls-files", "-z").split(b"\0") if p}


def audit(root: Path | None = None) -> dict:
    root = (root or ROOT).resolve()
    failures = []
    tracked = tracked_paths(root)
    files = set(tracked)
    for directory, dirs, names in os.walk(root, followlinks=False):
        parent = Path(directory)
        for name in list(dirs):
            item = parent / name
            rel = item.relative_to(root).as_posix()
            if item.is_symlink():
                files.add(rel)
                dirs.remove(name)
            elif (parent == root and name == ".git") or name in RUNTIME_DIRS:
                dirs.remove(name)
        for name in names:
            item = parent / name
            rel = item.relative_to(root).as_posix()
            if rel == ".git" or (rel in REGENERATED and rel not in tracked):
                continue
            files.add(rel)
    for required in MUST_EXIST:
        if not (root / required).is_file():
            failures.append({"path": required, "reason": "required-public-file-missing"})
    allowed_chunks = set()
    delivery = root / "dashboard/public/data/delivery.json"
    if delivery.is_file() and not delivery.is_symlink():
        try:
            spec = json_loads_strict(delivery.read_bytes())
            allowed_chunks = {"dashboard/public/data/" + v["path"] for v in spec["parts"].values()}
        except (ValueError, KeyError, TypeError):
            failures.append({"path": delivery.relative_to(root).as_posix(), "reason": "invalid-delivery-manifest"})
    count = total = compressed = 0
    for relative in sorted(files):
        reason = path_reason(relative, tracked=relative in tracked)
        file = root / relative
        if reason:
            failures.append({"path": relative, "reason": reason})
            continue
        parts = PurePosixPath(relative).parts
        if any((root.joinpath(*parts[:i])).is_symlink() for i in range(1, len(parts) + 1)):
            failures.append({"path": relative, "reason": "symlink-not-approved"})
            continue
        if not file.exists() or not stat.S_ISREG(file.stat().st_mode):
            failures.append({"path": relative, "reason": "missing-or-nonregular-file"})
            continue
        if file.stat().st_size > MAX_BYTES:
            failures.append({"path": relative, "reason": "file-size-limit"})
            continue
        if CHUNK.fullmatch(relative) and relative not in allowed_chunks:
            failures.append({"path": relative, "reason": "unreferenced-compressed-payload"})
        data = file.read_bytes()
        failures.extend({"path": relative, "reason": r} for r in inspect_payload(relative, data))
        count += 1
        total += len(data)
        compressed += int(bool(CHUNK.fullmatch(relative)))
    report = {"filesScanned": count, "bytesScanned": total, "compressedFilesDecoded": compressed,
              "candidateFailures": failures, "publicBoundaryPassed": not failures,
              "providerInferenceCalls": 0,
              "caution": "Heuristic checks plus typed evidence contracts; not legal clearance or exhaustive DLP."}
    if failures:
        raise ValueError(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def audit_history(root: Path | None = None, *, base: str = APPROVED_PUBLIC_BASE,
                  head: str = "HEAD") -> dict:
    root = root or ROOT
    base_sha = git(root, "rev-parse", "--verify", base + "^{commit}").decode().strip()
    head_sha = git(root, "rev-parse", "--verify", head + "^{commit}").decode().strip()
    git(root, "merge-base", "--is-ancestor", base_sha, head_sha)
    revisions = git(root, "rev-list", "--reverse", f"{base_sha}..{head_sha}").decode().splitlines()
    seen = set()
    scanned = 0
    failures = []
    approved_merges = 0
    for revision in revisions:
        commit_line = git(root, "rev-list", "--parents", "-n", "1", revision).decode().split()
        if not commit_line or commit_line[0] != revision:
            raise ValueError("Cannot resolve historical commit parentage")
        parents = commit_line[1:]
        if not 1 <= len(parents) <= 2:
            raise ValueError("Unsupported public history root/octopus merge after baseline: " + revision)
        for parent in parents:
            try:
                git(root, "merge-base", "--is-ancestor", base_sha, parent)
            except subprocess.CalledProcessError as exc:
                raise ValueError("Merged public branch contains history outside approved baseline: " + revision) from exc
        if len(parents) == 2:
            # Only content-preserving merges, as generated for the reviewed
            # PR tree, are accepted. A conflict-resolution merge whose tree
            # differs from the reviewed second parent needs separate approval.
            merge_tree = git(root, "rev-parse", revision + "^{tree}")
            reviewed_tree = git(root, "rev-parse", parents[1] + "^{tree}")
            if merge_tree != reviewed_tree:
                raise ValueError("Unreviewed merge resolution changed approved PR source tree: " + revision)
            approved_merges += 1
        # Scan every parent edge, not Git diff-tree's default empty output
        # for merge commits. Every introduced blob remains audited, even
        # when later deleted on the feature branch.
        changes = set()
        for parent in parents:
            changed = git(root, "diff-tree", "--no-commit-id", "--name-only", "-r", "-z",
                          "--diff-filter=ACMT", "--no-renames", parent, revision).split(b"\0")
            changes.update(item for item in changed if item)
        for raw in sorted(changes):
            if not raw:
                continue
            relative = raw.decode()
            reason = path_reason(relative)
            if reason:
                failures.append({"commit": revision, "path": relative, "reason": reason})
                continue
            record = git(root, "ls-tree", "-z", revision, "--", relative).split(b"\0")[0]
            mode, kind, oid = record.split(b"\t", 1)[0].decode().split()
            if kind != "blob" or mode not in {"100644", "100755"}:
                failures.append({"commit": revision, "path": relative, "reason": "nonregular-git-object"})
                continue
            if (relative, oid) in seen:
                continue
            seen.add((relative, oid))
            if int(git(root, "cat-file", "-s", oid)) > MAX_BYTES:
                reasons = ["file-size-limit"]
            else:
                reasons = inspect_payload(relative, git(root, "cat-file", "blob", oid))
            scanned += 1
            failures.extend({"commit": revision, "path": relative, "reason": r} for r in reasons)
    report = {"historyBoundaryPassed": not failures, "approvedBaseline": base_sha,
              "head": head_sha, "newCommits": len(revisions),
              "reviewedContentPreservingMerges": approved_merges,
              "changedBlobsScanned": scanned,
              "failures": failures, "scope": "All added/modified blobs in every commit after baseline, including later deletions."}
    if failures:
        raise ValueError(json.dumps(report, indent=2))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", action="store_true", help="Also audit history from the fixed approved public baseline")
    parser.add_argument("--built",type=Path,help="Inspect exact staged Pages dist; run after removal of unneeded raw snapshot.json")
    parser.add_argument("--head", default="HEAD", help="PR head or HEAD; does not change the approved baseline")
    args = parser.parse_args()
    result = audit()
    if args.history:
        result["history"] = audit_history(head=args.head)
    if args.built:
        result["pagesArtifact"] = audit_built_site(args.built)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
