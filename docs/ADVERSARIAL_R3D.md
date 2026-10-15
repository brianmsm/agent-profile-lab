# Agent Profile Lab R3d — immutable Git objects and bounded release trust

**Scope:** R3d addresses R3c C01/C03, narrows C04 and strengthens C02. It
does not change the 2,496 reference profiles, 33,414 role assignments,
3,744 native files, model efforts or 3,241 BFCL published values.

## C01 — Git source integrity

The shared module scripts/git_object_integrity.py and the separately
installed external release authority use Git ls-tree and cat-file, NOT
git archive. For every committed path they compare OID, object type,
mode, byte length and exact actual worktree bytes, without trusting
Git index flags, replacement refs, or export-ignore/export-subst.
No self-reissued receipt is a substitute for the approved original
Git commit; public and private histories remain independent.

## C03 — Typed source and auxiliary CSV

The value true is NOT schemaVersion 1. JSON numeric value 1.0 remains
acceptable when a schema represents an integer by numeric value,
as in JSON Schema. Nonfinite exponents, NaN and Infinity are refused
by the strict parser. Portfolios CSV, like the 13 historical CSVs,
must have unique headers and regular row widths. A source manifest
or amendment receipt must be interpreted strictly before its hash
can be called semantically valid.

## C04 — Explicit policy scope

The Python compiled manifest/preflight expose reviewedFields and
reviewScope and separate the reviewed assurance policy from an
individually reviewed domain. The cybersecurity normative contract
is pinned; unrelated domains are NOT thereby independently reviewed.
Browser-generated exports say their offline policy review is NOT
authenticated. No runtime permissions, safety controls, authorization
or provider access are installed by this documentary review.

## C02 — External authority and candidate isolation

An off-repository executable pins its Ed25519 PUBLIC verification key
fingerprint. An installed, reviewed Git-object helper checks exact
source OIDs and bytes, while the signature binds exact SHA40 and
Git tree, BFCL rights and the 17+17 approved Pages file hashes.

An offline build executes source code exclusively in Bubblewrap with
network unavailable, the operator HOME (including signing keys)
hidden, read-only preinstalled dependencies, and writable paths only
for a disposable public clone and Vite's temporary cache. Never fall
back to unsandboxed execution of unreviewed candidate code. The
prepublication script first asks the off-repo authority to VERIFY
the previously approved SHA/assets, only then running candidate
Python tests in another sandbox without access to signing keys.

A commit that changes its own DLP/tests cannot approve itself:
there is no signature for that new SHA. Conversely, a valid
signature proves EXACT-BYTE approval by the local signer, NOT that
all encoding/semantic forms of restricted publisher data were
automatically detected. New scientific data must receive a separate
rights/content review BEFORE any public-branch push.

The GitHub main ruleset requires PR and CI and prevents non-fast-forward
updates/deletion. It has zero required approving reviewers (one
collaborator) and does not govern all public refs. Neither the same
operator's local key nor the GitHub ruleset authenticates a second
human review. A new public ref is readable immediately upon push,
even before any PR is evaluated. This remains a documented limit.

## Required negative and positive tests

In disposable clones attempt: identical-length Git blob replacement
with refs/replace; export-ignore and altered index flags; source
receipt re-hashing; boolean schema versions, nonfinite JSON and
auxiliary CSV duplicates; normatively false domain declarations;
changed source with altered candidate inspector/tests; and replay
of a synthetic ephemeral Ed25519 signature. Ensure the baseline,
3,744 nativos, 13 source CSVs and 3,241 BFCL rows remain accepted,
and both 17-file Pages bundles are signed/verifiable after a
fresh isolated build.

Only an independent R3d adversarial review can adjudicate these
bounded structural claims. No paid inference, E3 model performance,
provider entitlement or operational safety enforcement is claimed.
