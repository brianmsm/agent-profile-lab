# Agent Profile Lab: R3c trust boundary

This is targeted structural/publication remediation, NOT model re-ranking or
runtime permission certification.

## F01: historical native bytes without Git index

All 3,744 native files are compared directly with their approved historical
Git tree using git archive. No git diff/index state is trusted, including
assume-unchanged and skip-worktree. Public and private Git histories stay
separate. SHA continuity is NOT an editor signature.

## F02/F03: reviewed policy and unambiguous inputs

The complete normative cybersecurity domain contract (scope, routine,
critical, evidenceNote, evidenceBoundary, gate) is independently pinned
against a reviewed Git commit, not just the gate. The full assurance policy
also remains pinned. Source manifests, historical receipts, domain contracts,
roles and compiler inputs reject recursively duplicate JSON keys before
parsing/canonicalizing. policyReviewed means DOCUMENTARY coverage only:
readyForOperation, controlsVerified and policyEnforcedAtRuntime stay FALSE.

## Independent PUBLIC release authority

The PUBLIC candidate does not contain its own operative trust root. The
operative r3c_release_authority.py and Ed25519 signing/verification keys
are installed separately under the user's private local state directory,
outside BOTH repos. The private signing key is never copied into a
repository, artifact, message or public website.

For each release, a separately signed manifest binds the approved PUBLIC
SHA40 and full Git tree; worktree bytes read independently of the index;
exactly 3,241 authorized BFCL observations; only the approved publisher
numeric source; and the exact 17+17 static Pages file hashes including
the two public content-addressed chunks. Files or HEADs changed without
a new signature FAIL, even if the candidate tampers with its own DLP
guard or included tests. No automatic signature renewal occurs on failure.

CRITICAL LIMIT: this is a SINGLE-USER local delegated signature, not proof
of a separate human reviewer. Anyone able to access the off-repository
signing key or overwrite the external trusted tool can authorize false
content. It cannot detect every possible encoded publisher value merely
from code semantics. A responsible reviewer must examine new numerical
sources and rights before signing.

## Clean build and branch protection

The separate private helper build_exact_pages.py clones the reviewed
public-only commit and builds both public and reference-only Pages using
local dependencies. It removes the raw snapshot; only the reference HTML
gets two noindex directives. Executing build tools is NOT a security
sandbox, so source must be vetted before any build.

For future changes, use verified GitHub PR/ruleset protection on public
main, require CI checks, and review content rights BEFORE pushing any
publicly visible branch. GitHub CI after push cannot erase bytes already
published in history. The repository has one known collaborator: a rule
requiring ZERO approving reviewers does not authenticate an independent
human. Never claim verified human/branch protection without inspecting
actual remote settings.

## Preservation and review

The 2,496 baseline profiles, 33,414 active assignments, 3,744 native
configuration files, and 3,241 approved BFCL values stay unchanged.
No provider inference. Reproduce the Git index flag, duplicate JSON,
cybersecurity scope, altered guard/test and synthetic TSX/compiled JS
negative cases in disposable clones. Audit BOTH actual Pages bundles
and reference-only noindex, without confusing it with authentication.

Independent R3c review is required to close scope-limited guarantees.
No E3 model/cost/latency comparison or operational authorization
enforcement is claimed by this release.
