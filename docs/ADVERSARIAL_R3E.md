# Agent Profile Lab R3e — local trust-boundary remediation

**Status:** Local candidate source and adversarial regression suite. NOT
independently approved, NOT deployed, NOT newly signed or pushed.

This intervention follows the independent R3d closeout. The scientific
baselines remain 2,496 profiles, 33,414 active role decisions, 52,134
original source rows, 3,744 original native files, and 3,241 numeric
BFCL observations. R3e does not change models or effort choices.

## C01 / S-03 — historical Git source

The historical readers for CSVs and native blobs now invoke an absolute
trusted Git binary at /usr/bin/git with a sanitized environment and
direct ls-tree/cat-file object verification. They do not use a program
called git found through PATH or rely on a transformable git archive.
Candidate-local Git metadata is inspected before any Git subprocess:
core.fsmonitor, include.path/includeIf, process filters, hooks,
diff/merge helpers and uploadpack hooks are refused. Command-line
Git overrides disable fsmonitor/hooks as defense in depth. This is a
standalone-repository contract, not linked-Git-worktree support.

Synthetic negative tests cover the precise historical CSV change plus
reissued manifest/receipt and malicious PATH shim from R3d, in private
and public editions. Neither the individual amendment check nor the
full preflight may say unchanged historical non-label fields. Synthetic
fsmonitor/include markers must never run. All ancestors of a tracked
file must be real directories rather than symlinks, even when path alias
bytes match another blob.

## C02 / S-04 — prevent signer privileges reaching candidate source

External authority source now validates all Git/source/Pages content
inside a separate Bubblewrap subprocess with no signing-key mount,
no operator HOME, no network and no /run/var/mnt host sockets. Its
filesystem root consists of read-only /usr, synthetic /proc and /dev,
the minimal read-only candidate checkout and Pages, and a reviewed
isolated trust-code copy. The signing parent only reads the existing
private key AFTER the child has validated the exact source and assets.
The verification path checks Ed25519 first and rechecks source/assets
inside a no-key child. Test signatures use EPHEMERAL keys only.

Candidate build/test sandboxes also use a minimal filesystem rather than
a root ro-bind. The build uses a pinned installed Node SHA-256 in
republication/trust/isolation.py and writable disposable checkout and
Vite cache; it cannot read the installed signer state and has no network.
There is no unsandboxed fallback.

**Deployment boundary:** the reviewable authority files plus the new
isolation.py and sandbox_release.py dependencies must be installed in the
external independent trust directory ONLY AFTER separate review.
Changes to the candidate repository do NOT automatically update the
operative signing authority. Never copy or inspect the existing real
private key or sign a new release during these tests.

## S-04 — public references and data redistribution

The content-inspection guard now rejects the demonstrated Number("82.1")
TS/JS example and editorial numeric metadata embedded in SVG, including
the public Git history and staged site, without rejecting legitimately
licensed BFCL values, local synthetic fixtures or aggregate counts.

The inspector is still heuristic. A valid Ed25519 signature ties down
the reviewed bytes, not original publisher identity or universal legal
rights. No arbitrary encoded-content classifier has exhaustive accuracy.

The live GitHub main ruleset mandates PR and CI, but has zero required
independent reviewers and does NOT enforce the local Ed25519 authority
on every newly created public branch or tag. Publishing content to a
public PR branch is itself public redistribution. Accordingly, one
operator MUST privately review content, staged changes and rights and
authorize exact commit/Pages BYTES BEFORE any public-branch push.
R3e cannot honestly claim universal prevention against a direct writer
bypassing the voluntary local gate. Additional remote authority would
need GitHub-side policy outside this repository.

## Quality/contract regressions

- Reject internal symlink aliases in tracked-path ancestors.
- Ephemeral signature tests build a 17-file Pages fixture from the exact
  current public source commit rather than ignored R3c staging.
- Remove duplicate R3d integrity invocation from public CI.
- Add explicit DLP negative/positive cases for Number wrappers and SVG.
- Preserve 3,241 BFCL numeric rows and the prior 34 approved R3d Pages
  assets unchanged.

## Evidence and release conditions

Both editions require negative adversarial cases plus positive scientific
baselines and full offline pipelines. All attacks are synthetic and run
only in disposable clones; no real signing, public push, key inspection,
provider inference or mutation of active installed agent homes is
authorized. R3e remains LOCAL until two independent adverse reviews and
a coordinator approve the bounded controls.

The R3d root-cause adjudication is preserved at
validation/adversarial-r3d-20261015/03_closure.md.
