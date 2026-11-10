# Standing release policy: public subscription supplement

**Scope:** public-only, project-authored subscription selector from the
previously inspected public candidate. This is a *standing source-rights
decision under a user-delegated maintenance workflow*, **not** a claim that
someone performed a new independent legal review.

The public release remains limited to:
- Five exact author-owned source/documentation versions listed by SHA-256
  in `tools/standing-release-policy.json`.
- The minimal project-owned release tooling needed to check that policy,
  inspect Git history and reproduce both Pages artifacts.
- Existing, unchanged numerical BFCL V4 values under the Apache-2.0 basis
  already recorded in `policies/public-evidence-redistribution.json`.
- Short factual names/prices of published plans, with links to original
  providers. This does not copy provider logos, website HTML, terms,
  screenshots, source data or benchmark score tables.

**Still forbidden:** raw evidence, account data, private catalogs, Artificial
Analysis / Vals numerical scores, new routing decisions, or a silent expansion
of rights because a scanner happens not to find a problem.

## Release operation

`tools/standing_release_gate.py` verifies the commit history after the
reviewed public baseline, every changed source path, exact SHA-256 for the five
previously examined application files, intact BFCL licensing scope and the
exact 17-file Pages inventories for both the public and the non-indexed
reference site.

This gate reports `POLICY_SCOPE_VERIFIED` or **fails**. It never emits
`humanRightsReviewed=true`, signs on behalf of a person, accesses accounts,
or authorizes unknown third-party material.

Future releases with different paths/content must extend this narrow policy
with separately documented provenance and a new test. Code that merely
resembles an allowed path does not automatically inherit rights.

Deployments use `workflow_dispatch` with an exact public commit SHA, rather
than an owner's personal rights-attestation phrase. The authorized agent can
trigger the workflow; no local interactive owner acknowledgement is required
for content already inside this fixed scope. Uploads are rejected if Git,
source rights, BFCL scope, DLP checks or built Pages diverge.

The original private and public repositories and their Git histories remain
separate. The private repository must **never** be used as the Pages build
source. No `snapshot.json` raw file, capture or source archive may be uploaded.

This controls **source publication**, not the operational entitlement of Go,
NaN or Google subscriptions. Selecting one does not configure a client, run a
model, spend money or establish benchmark calibration.

The release gate itself and its workflow are trusted first-party publishing
code. Changes to those files are never silently licensed by the user-facing
subscription selector; their implementation must be assessed and versioned
under this project's source governance.

### Reference sources

- OpenCode: https://dev.opencode.ai/v2/docs/console/go
- NaN Gentle: https://cloud.nan.builders/gentle
- Google Antigravity: https://antigravity.google/docs/plans

The NaN Gentle 20 EUR offer is confirmed by the supplied official-page
screenshot. The screenshot is **not** redistributed.
