#!/usr/bin/env python3
"""Fail-closed, *policy-scoped* public release gate.

This does not attest that a person or AI performed a legal review. It checks
exact author-owned changes already documented by the standing rights policy,
the pre-existing numeric-rights boundary, and pinned Pages artifact bytes.

The release tooling/workflow is part of the trusted publisher codebase:
changes to the gate itself require a reviewed policy-code revision. Never
silently infer redistribution rights merely because a path is syntactically
safe or a DLP scan passes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
POLICY = "tools/standing-release-policy.json"
GATE_PATHS = frozenset({
    ".github/workflows/pages.yml",
    "tools/standing_release_gate.py",
    "tools/standing-release-policy.json",
    "tools/test_standing_release_gate.py",
    "docs/STANDING_RELEASE_SCOPE.md",
    "docs/SAFE_MAINTENANCE.md",
})
SOURCE_PATHS = frozenset({
    "dashboard/src/Profiles.tsx",
    "dashboard/src/PublicSubscriptionAddons.tsx",
    "dashboard/src/publicSupplementPlan.ts",
    "dashboard/tests/publicSubscriptionAddons.test.tsx",
    "docs/SUBSCRIPTION_RESOURCES.md",
})
BASE = "60744bae87696ae2aa01eeba1a4bad68a720399f"
FEATURE = "59e02f081b0b8b7884df5c924e8bcb392d621990"
PUBLIC_ORIGIN = {
    "https://github.com/brianmsm/agent-profile-lab.git",
    "https://github.com/brianmsm/agent-profile-lab",
}
SHA = re.compile(r"[0-9a-f]{64}\Z")
HEAD_SHA = re.compile(r"[0-9a-f]{40}\Z")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(repo: Path, *args: str) -> bytes:
    proc = subprocess.run(
        ["git", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null",
         "-c", "core.pager=cat", "-C", str(repo), *args],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,
        timeout=70, check=False)
    if proc.returncode:
        raise ValueError("Git integrity/ancestry command failed: " + " ".join(args))
    return proc.stdout


def policy_at(root: Path = ROOT) -> dict:
    p = root / POLICY
    if p.is_symlink() or not p.is_file():
        raise ValueError("Missing or symlinked standing rights policy")
    policy = json.loads(p.read_bytes())
    required = {
        "schemaVersion", "id", "status", "rightsBasis",
        "reviewedPublicBase", "verifiedPublicFeatureCommit",
        "originalPublicLicense", "authorizedHistoricalChanges",
        "controlledReleaseInfrastructure", "authorizedInfrastructureSHA256",
        "authorizedInfrastructureHistoricalSHA256",
        "expectedPagesInventorySHA256",
        "rightsRules", "publicationBoundary", "humanRightsReviewed", "origin",
        "remotePushRequiresValidPolicyCheck",
    }
    if set(policy) != required or policy["schemaVersion"] != 1:
        raise ValueError("Unknown policy shape")
    if policy["reviewedPublicBase"] != BASE or policy["verifiedPublicFeatureCommit"] != FEATURE:
        raise ValueError("Historical rights boundary changed")
    if policy["originalPublicLicense"] != "MIT" or policy["status"] != "source-rights-policy-scoped":
        raise ValueError("No recognized author-owned source license")
    if set(policy["authorizedHistoricalChanges"]) != SOURCE_PATHS:
        raise ValueError("The listed author-owned source paths changed")
    if set(policy["controlledReleaseInfrastructure"]) != GATE_PATHS:
        raise ValueError("Unreviewed trusted release infrastructure was added")
    if set(policy["authorizedInfrastructureSHA256"]) != (GATE_PATHS - {POLICY}):
        raise ValueError("Trusted release infrastructure must have pinned SHA-256 values")
    if not all(isinstance(v, str) and SHA.fullmatch(v)
               for v in {**policy["authorizedHistoricalChanges"],
                         **policy["authorizedInfrastructureSHA256"]}.values()):
        raise ValueError("Invalid exact source/control hashes")
    older=policy["authorizedInfrastructureHistoricalSHA256"]
    if (not isinstance(older,dict) or set(older)-set(policy["authorizedInfrastructureSHA256"])
        or any(not isinstance(versions,list) or not versions or
               len(versions)!=len(set(versions)) or
               any(not isinstance(v,str) or not SHA.fullmatch(v) or
                   v == policy["authorizedInfrastructureSHA256"][name] for v in versions)
               for name,versions in older.items())):
        raise ValueError("Unknown or malformed older reviewed infrastructure hashes")
    if set(policy["expectedPagesInventorySHA256"]) != {"public", "reference"}:
        raise ValueError("Missing expected Pages site digest")
    if not all(isinstance(v, str) and SHA.fullmatch(v)
               for v in policy["expectedPagesInventorySHA256"].values()):
        raise ValueError("Invalid Pages site hashes")
    rules = policy["rightsRules"]
    if set(rules) != {
        "allowOriginalProjectSource", "allowShortPlanFactsAndProviderLinks",
        "permitBFCLNumericOnlyUnderExistingRightsPolicy", "denyThirdPartyRawCaptures",
        "denyThirdPartyPublisherScores", "denyPrivateResearchAndAccountData",
        "denyNewRoleAssignmentsOrDataChanges",
        "denyAutomaticRightsExtensionToNewPaths", "verifyHumanRightsClaim",
    } or any(v is not (k != "verifyHumanRightsClaim") for k, v in rules.items()):
        raise ValueError("Standing rights safeguards were weakened")
    if policy["humanRightsReviewed"] is not False or policy["remotePushRequiresValidPolicyCheck"] is not True:
        raise ValueError("Standing scope cannot impersonate a human rights review")
    return policy


def compare_historical_versions(
    path_to_sha: dict[str, str], seen_versions: list[tuple[str, bytes | None]],
    infra: set[str], older: dict[str, list[str]] | None = None,
) -> None:
    allowed = set(path_to_sha) | infra
    for path, data in seen_versions:
        if not isinstance(path, str) or path not in allowed:
            raise ValueError("Unreviewed new public Git path: " + str(path))
        if data is None:
            raise ValueError("Deletion of a reviewed source/control path is not permitted: " + path)
        if path in path_to_sha and digest(data) not in {
            path_to_sha[path], *(older or {}).get(path, []),
        }:
            raise ValueError("Changed source has no standing rights coverage: " + path)
        if path in infra and (not data or len(data) > 4_194_304 or b"\0" in data):
            raise ValueError("Invalid release infrastructure content")


def historical_versions(root: Path, base: str, head: str) -> tuple[list[tuple[str, bytes | None]], int]:
    commits = git(root, "rev-list", "--reverse", f"{base}..{head}").decode().splitlines()
    if not 1 <= len(commits) <= 5:
        raise ValueError("Release history not in the expected bounded review range")
    versions = []
    for commit in commits:
        parents = git(root, "rev-list", "--parents", "-n", "1", commit).decode().split()
        if parents[0] != commit or len(parents) not in (2, 3):
            raise ValueError("Unexpected ancestry in standing release range")
        if len(parents) == 3:
            # A GitHub PR merge is acceptable only when its tree matches
            # the reviewed PR parent byte for byte. Conflict-resolution
            # merges and octopus merges remain outside the standing scope.
            merged_tree = git(root, "rev-parse", commit + "^{tree}")
            reviewed_tree = git(root, "rev-parse", parents[2] + "^{tree}")
            if merged_tree != reviewed_tree:
                raise ValueError("Unreviewed conflict resolution in merge commit")
        parent = parents[1]
        names = git(root, "diff-tree", "-r", "-z", "--no-renames", "--name-only",
                    parent, commit).split(b"\0")
        for name in names:
            if not name:
                continue
            path = name.decode()
            if PurePosixPath(path).is_absolute() or ".." in PurePosixPath(path).parts:
                raise ValueError("Unsafe changed path")
            tree = git(root, "ls-tree", "-z", commit, "--", path).split(b"\0")[0]
            if not tree:
                versions.append((path, None))
                continue
            meta, recorded = tree.split(b"\t", 1)
            mode, kind, oid = meta.decode().split()
            if recorded.decode() != path or mode != "100644" or kind != "blob":
                raise ValueError("Unreviewed Git type or mode at " + path)
            data = git(root, "cat-file", "blob", oid)
            if digest(data) != digest((root / path).read_bytes()) and commit == head:
                raise ValueError("Worktree differs from final commit: " + path)
            versions.append((path, data))
    return versions, len(commits)


def verify_source(root: Path = ROOT, expected_head: str | None = None) -> dict:
    root = root.resolve(strict=True)
    pol = policy_at(root)
    if git(root, "remote", "get-url", "origin").decode().strip() not in PUBLIC_ORIGIN:
        raise ValueError("Not the dedicated public repository")
    head = git(root, "rev-parse", "HEAD").decode().strip()
    if expected_head and (not HEAD_SHA.fullmatch(expected_head) or head != expected_head):
        raise ValueError("Wrong exact public release commit")
    git(root, "merge-base", "--is-ancestor", BASE, FEATURE)
    git(root, "merge-base", "--is-ancestor", FEATURE, head)
    version_list, count = historical_versions(root, BASE, head)
    pinned={**pol["authorizedHistoricalChanges"], **pol["authorizedInfrastructureSHA256"]}
    compare_historical_versions(
        pinned, version_list, {POLICY},
        pol["authorizedInfrastructureHistoricalSHA256"])
    for path, h in pinned.items():
        if digest(git(root, "show", f"{head}:{path}")) != h:
            raise ValueError("Source SHA changed after previous review: " + path)
    for path in GATE_PATHS:
        if not (root / path).is_file() or (root / path).is_symlink():
            raise ValueError("Required scoped release infrastructure missing: " + path)
    # Previously reviewed numerical licensing basis stays unchanged.
    rights = json.loads((root / "policies/public-evidence-redistribution.json").read_bytes())
    if rights.get("schemaVersion") != 1 or rights.get("numericSourceIds") != ["BR-BFCL-DATA"]:
        raise ValueError("Numerical publisher rights were widened")
    bfcl = rights.get("reviewedSource", {}).get("BR-BFCL-DATA", {})
    if bfcl.get("license") != "Apache-2.0" or bfcl.get("releaseDecision") != "cleared-with-attribution-and-original-source-metadata":
        raise ValueError("Explicit BFCL permission disappeared")
    if not (root / "LICENSE").read_text().startswith("MIT License"):
        raise ValueError("Original project software license changed")
    for forbidden in ("evidence", "sources", "internal-research", "catalog/opencode-go-current.json",
                      "catalog/nan-gentle.json", "catalog/google-ai-plans.json"):
        if (root / forbidden).exists():
            raise ValueError("Private content was introduced in public tree: " + forbidden)
    return {
        "result":"POLICY_SCOPE_VERIFIED", "head":head,
        "base":BASE, "historicalCommits":count,
        "newVersionCount":len(version_list),
        "originalSourceVersions":len(SOURCE_PATHS),
        "releaseInfrastructure":len(GATE_PATHS),
        "sourceRightsBasis":"author-owned MIT code + links/short factual plan references",
        "humanRightsReviewClaimed":False,
        "automaticBroadRightsApproval":False,
        "modelCalls":0,
    }


def verify_pages(root: Path, built: Path, site: str, expected_head: str | None = None) -> dict:
    source = verify_source(root, expected_head)
    if site not in {"public", "reference"}:
        raise ValueError("Unknown release target")
    sys.path.insert(0, str(root / "tools"))
    from audit_public_distribution import audit_built_site, exact_site_inventory, site_inventory_digest
    built = built.resolve(strict=True)
    report = audit_built_site(built, root=root)
    actual = site_inventory_digest(exact_site_inventory(built))
    expected = policy_at(root)["expectedPagesInventorySHA256"][site]
    if report["pagesFilesScanned"] != 17 or actual != expected:
        raise ValueError("Pages bytes do not match standing source-rights scope for "+site)
    return {**source, "site":site, "pagesFiles":report["pagesFilesScanned"],
            "pagesSHA256":actual, "rightsBasis":"policy-scoped-not-human-attestation"}


def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, default=ROOT)
    ap.add_argument("--head")
    ap.add_argument("--site", choices=("public","reference"))
    ap.add_argument("--built", type=Path)
    args=ap.parse_args()
    if bool(args.site) != bool(args.built):
        ap.error("--site and --built must be used together")
    value=(verify_pages(args.source,args.built,args.site,args.head)
           if args.site else verify_source(args.source,args.head))
    print(json.dumps(value,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
