#!/usr/bin/env python3
"""Audit public files and, optionally, every change after an approved Git baseline.

Read-only, offline and fail-closed. Findings contain paths/reasons, never matched
secrets. This is a release guard, not legal clearance or an adversarial DLP proof.
Pair it with verify_public_release.py, review, and the private transfer allowlist.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess

ROOT = Path(__file__).resolve().parents[1]
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


def numeric_source_rows(value: object) -> bool:
    """Recognize typed publisher score rows, including those in test fixtures.

Unlabelled or deliberately encoded numbers require human review; source links,
aggregate corpus counts and null-valued review references are not score rows.
"""
    stack = [value]
    while stack:
        row = stack.pop()
        if isinstance(row, list):
            stack.extend(row)
        elif isinstance(row, dict):
            stack.extend(row.values())
            numeric = any(isinstance(row.get(k), (int, float)) and not isinstance(row.get(k), bool)
                          for k in ("value", "score", "intelligence_index"))
            if not numeric:
                continue
            source_id = row.get("sourceId")
            source = " ".join(str(row.get(k, "")) for k in
                              ("source", "sourceUrl", "url", "provider")).lower()
            if source_id == "AA" or "artificialanalysis" in source or "slopalytics" in source:
                return True
            if source_id and source_id != "BR-BFCL-DATA":
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
    if relative.endswith(".json") or match:
        # TypeScript's two existing JSONC configs permit comments/trailing commas.
        # Strip only outside strings, and still validate/inspect the resulting JSON.
        if relative in {"dashboard/tsconfig.app.json", "dashboard/tsconfig.node.json"}:
            text = re.sub(r'"(?:\\.|[^"\\])*"|//[^\r\n]*|/\*[\s\S]*?\*/',
                          lambda m: m[0] if m[0].startswith('"') else ' ', text)
            text = re.sub(r'("(?:\\.|[^"\\])*")|,(\s*[}\]])',
                          lambda m: m[1] if m[1] is not None else m[2], text)
        try:
            value = json.loads(text)
        except (ValueError, RecursionError):
            reasons.append("invalid-json")
        else:
            if numeric_source_rows(value):
                reasons.append("non-allowlisted-publisher-numeric-row")
    return reasons


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
            spec = json.loads(delivery.read_bytes())
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
    for revision in revisions:
        parents = git(root, "rev-list", "--parents", "-n", "1", revision).decode().split()
        if len(parents) != 2:
            raise ValueError("Nonlinear public history after approved baseline; review required: " + revision)
        changes = git(root, "diff-tree", "--no-commit-id", "--name-only", "-r", "-z",
                      "--diff-filter=ACMT", "--no-renames", revision).split(b"\0")
        for raw in changes:
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
              "head": head_sha, "newCommits": len(revisions), "changedBlobsScanned": scanned,
              "failures": failures, "scope": "All added/modified blobs in every commit after baseline, including later deletions."}
    if failures:
        raise ValueError(json.dumps(report, indent=2))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", action="store_true", help="Also audit history from the fixed approved public baseline")
    parser.add_argument("--head", default="HEAD", help="PR head or HEAD; does not change the approved baseline")
    args = parser.parse_args()
    result = audit()
    if args.history:
        result["history"] = audit_history(head=args.head)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
