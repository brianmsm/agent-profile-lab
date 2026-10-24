# Agent Profile Lab R3f — focused local trust-boundary follow-up

**Status:** Local unsigned review candidate. Do not install the operative
release authority, sign, push public refs, deploy Pages or run paid
inference until independent adversarial review and operator authorization.

The R3e coordinator adjudication (17 October 2026) supports bounded local
structural closure but identifies specific residual defects in DLP encoding,
concurrent source changes, maintenance Git object validation and isolation.

## Repair scope

1. **Source/history/Pages DLP:** conservative publisher provenance checks
   for JSX expression numeric conversions, indirect conversions,
   XML/SVG metadata attributes and nested numeric elements. Tests cover
   direct inspection, added-then-deleted commits and compiled assets,
   retaining BFCL and approved aggregate counts. This is a heuristic,
   not a substitute for a human/editorial rights review.
2. **Concurrent preflight sources:** preflight computes SHA-256 inventories
   before and after the validation, including all compiler inputs,
   twelve shards, profile-index.csv and the source amendment receipt.
   A change DURING validation is rejected. The recorded
   sourceStableDuringPreflight field is NOT a filesystem lock, nor
   prevention of writes AFTER the final comparison. Actual release
   operations still require a frozen private checkout.
3. **Git object poisoning:** the private-to-public maintenance planner
   now recomputes the source blob OID and refuses tampered local loose
   objects even if skip-worktree masks their worktree changes.
4. **Child environment:** trusted Git and Bubblewrap child processes
   receive an explicit environment allowlist, excluding LD_PRELOAD,
   LD_AUDIT, PYTHONPATH and inherited custom Git config overrides.
   This does not protect an already compromised host, loader or
   initial operator Python process.
5. **File descriptors/HOME:** child stdin is DEVNULL, unrelated
   descriptors are closed, and using the operator HOME as the
   candidate repo is forbidden. Synthetic stdin/loader canaries
   must not reach the candidate child.
6. **CSV topology:** ancestors of reviewed source shards must be
   ordinary directories, not symlinks, even for byte-identical files.

## Preservation and publishing boundary

The candidate changes no model selections or efforts, no 2,496
profiles, no 33,414 active decisions, no 52,134 source rows, no
3,744 historical native files, and no 3,241 approved BFCL measurements.
Pages are expected to remain 17 files per site identical to the
signed R3d assets after building from the exact R3f SHA40.

GitHub's active main ruleset does NOT enforce the off-repository
local Ed25519 approval on every newly created public branch or tag.
A valid release under this one-operator protocol requires staging,
external rights review and exact byte signing BEFORE ANY public
branch push. This is not universal GitHub prepublication enforcement.

The independent installed R3d signer and existing real key/approvals
must remain untouched. After passing new independent R3f adversarial
reviews, an owner may separately authorize an installed authority
update, exact SHA release signature and controlled publication.
