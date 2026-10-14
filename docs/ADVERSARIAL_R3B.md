# Agent Profile Lab R3b · targeted publication and provenance controls

**Status:** corrective implementation against the three independent R3
reviewers. No new experimental model score, inference, subscription quota,
installed agent or operational security controller is introduced.

## Applied corrections

- The **13 source CSV headers** must be unique and match their independently
  approved historic Git headers, including exact order. All source/projection
  loaders now reject duplicate names and irregular row width before using a
  last-wins dict. Renewed SHA receipts cannot legitimize ambiguous headers.
- **Strict JSON** rejects duplicated object keys, including inside BFCL,
  decoded gzip delivery fragments and browser-imported snapshots. Both Python
  and TypeScript check the raw text *before* JSON.parse/canonicalization.
  Canonical BFCL values remain pinned to reviewed public history.
- **Security policy attestation** now checks six fixed external control IDs,
  declarative readiness states and the cybersecurity gate against a reviewed
  earlier Git commit for the appropriate edition. This proves neither a
  publisher identity signature nor real tool-permission enforcement;
  readyForOperation remains false.
- **Publisher data publication**: direct, nested, stringified and alternate
  numeric score forms in JSON/CSV/TSV, text and TSX/JavaScript/HTML are
  screened, in both the Git tree/history and the uploaded static Pages
  directory. Original R3-C TSX→JS test and typed aggregate/BFCL positives
  are regression fixtures. A specific unmodified cybersecurity *synthetic*
  test file has an exact audited SHA allowlist; changing it triggers review.
  Text scanning is heuristic and cannot guarantee detection of encoded,
  obfuscated or otherwise novel publisher data.
- **Sync overlay**: public and private-maintenance copies of the rights
  scanner and synthetic tests are aligned. The patch planner runs a small
  independent no-downgrade contract. Its per-path allowlist remains explicit.
- **Prepublication sequence**: use the reviewed local public release gate,
  inspect proposed commits, and obtain explicit human approval *before*
  pushing public Git blobs. GitHub post-push CI alone cannot undo an
  accidental publication. This repository does not claim remote enforced
  branch protection unless settings have been checked separately.

## Preservation and release criteria

No baseline model selector/effort, account inventory, 2,496 profile IDs,
33,414 nominal slots, historical decisions, or 3,744 native configuration
files may change. No new AA or other restricted numeric observations may be
redistributed. The 3,241 public BFCL rows are fixed to their approved
public Git baseline. Run offline tests and source-rights checks in clean
public/private checkouts; verify actual Pages bundles and separate noindex
metadata for the reference-only site.

### Targeted negative tests

- Historical shard/index CSV duplicated header with current hashes reissued:
  **reject** before normalized comparison.
- Duplicated BFCL value key with recompression/new delivery SHA: **reject**.
- Six modified safety control identifiers + fake installed status with
  valid manifest/self-hashes: **reject** as unapproved declarative policy.
- Source JSX containing a synthetic external editor score compiled to
  assets/*.js: **reject** in both source tree and staged Pages package.
- Legitimate typed BFCL and aggregate counts, plus synthetic internal
  fixtures: **accept**.

This package does **not** establish E3 quality/cost optimization,
publisher authentication, reviewer independence or actual runtime controls.
The independent R3b refutation is still needed before audit closure.
