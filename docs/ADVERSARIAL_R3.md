# Targeted R3 structural remediation · 2026-10-14

The R3 corrective phase addresses R2's five demonstrated verifier/publication
false acceptances without reranking baseline models or invoking providers.

## Corrections and proof boundaries

- **S-01 — Native ↔ manifest.** Python-generated manifests now contain a
  sanitized compilationRequest. Preflight regenerates the complete manifest
  and native file from that declared request and reviewed sources, rejecting
  changed selectors, efforts, resources, roles, conditions, advisor flags,
  target/domain, filenames, and rehashed malformed native content.
  A self-declared request is not an authenticated author signature. Browser
  manifests are explicitly marked as not independently Python-recompiled.
- **S-02 — Sources.** Exactly 25 compiler dependencies and their hashes are
  required, plus transitive checks of all 12 source CSV shards.
- **S-03 — History.** Current descriptive source claims are compared with
  fixed, reviewed Git commits and all 13 original CSV blobs. Neither edition
  needs the other's Git history. Full Git history is required in CI. This
  is historical consistency, not a signed identity or proof against someone
  able to change trusted verification code.
- **S-04 — Public release.** CSV/TSV publisher scores are screened as well
  as JSON and compressed chunks. The precise built Pages artifact is audited
  after snapshot.json is removed, including all allowlisted assets/chunks.
  This is heuristic DLP, not an unrestricted redistribution license.
- **S-05 — BFCL.** Every one of 3,241 approved rows is matched to the
  independently pinned public Git corpus (values, identities, metadata),
  not merely newly issued transport hashes. Future source updates require
  a distinct content and rights review.
- **S-06 — Source/projection.** Standalone validators compare rows to
  hashed shards and reject nullable, scalar or malformed provenance arrays.
- **S-07 — Safety wording.** Contradictory permissive clauses in textual
  gates are rejected; the six documented external controls remain explicit.
  No runtime authorization controller has been installed.
- **S-08 — Experimental plan.** Allowed xhigh neighbors are now present for
  max baselines. Higher effort arms require an explicit planning switch,
  which does not authorize spending or inference.

## Tests and deployment

Private validation:

    python3 -B scripts/verify_source_amendment.py
    python3 -B scripts/test_targeted_r3.py
    python3 -B scripts/test_r3_history_anchor.py
    python3 -B scripts/check_project.py --rebuild --install

Public validation:

    python3 -B tools/test_public_boundary.py
    python3 -B tools/test_bfcl_anchor.py
    python3 -B tools/audit_public_distribution.py --history
    python3 -B tools/verify_public_release.py

Pages validation, after the unneeded raw snapshot.json has been removed from
the staged dist directory:

    python3 -B tools/audit_public_distribution.py --built dashboard/dist

The five original R2 synthetic attacks must fail, legitimate profiles must
pass, both CI pipelines must succeed, and public Pages must expose no private
numerical evidence. Historical exports without a reproducible compilation
request remain historical-only.

## Not proven

The structural checks do not establish independent reviewer errors,
cost/latency superiority, safety enforcement, real endpoint availability,
credential routing or model-version compatibility. Those remain separate
operational tests and controlled, explicitly authorized experiments.
