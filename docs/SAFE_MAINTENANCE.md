# Public maintenance: standing rights scope (single maintainer)

The public and internal repositories have **independent Git histories**.
Publication uses only the public checkout. Never mirror the internal
repository, copy raw provider captures, include account information, or
upload `snapshot.json` to Pages.

## No repetitive human rights acknowledgement for this narrow release

For the already reviewed, project-owned subscription supplement, the
rights and distribution boundaries are expressed as **exact machine checks**:

- `tools/standing-release-policy.json`: immutable baseline and five exact
  SHA-256 source versions, limited first-party release infrastructure,
  existing BFCL data license boundary, and both exact Pages digests.
- `tools/standing_release_gate.py`: checks all changed versions since the
  reviewed baseline and **fails closed** if a file, mode, digest, Git history,
  source-rights scope or Pages asset differs.
- `tools/audit_public_distribution.py` and `tools/verify_public_release.py`:
  independently inspect history, private-data patterns and public evidence.

The user delegated routine maintenance for material **already within the
standing rights policy**. Thus neither a local interactive TTY attestation
nor the misleading string `I_HAVE_REVIEWED_RIGHTS_AND_CONTENT` is part of
this release pathway.

The gate does **not** claim that a human reviewed these exact bytes again,
that an AI is a lawyer, or that source-unknown third-party material is
licensed. The original prior owner-attestation path remains available for
exceptional releases *outside* the standing policy, but it is not required
for this exact covered update.

### Publication sequence

1. Confirm the remote public `main` still equals the expected ancestor
   before pushing. No force push, history mirroring or unreviewed merges.
2. Run the standing gate against the full public Git tree, then
   `audit_public_distribution.py --history`, source/BFCL checks, frontend
   test, lint and production build.
3. Build exact Pages in the private frozen staging system and check
   `--site public` and `--site reference` against the policy-pinned
   SHA-256 inventories (17 files each, including only two allowed chunks).
4. Release operations may be delegated to the maintainer. Push only the
   independent **public** repository. Pages use owner-authenticated
   `workflow_dispatch` with the exact public HEAD, and each workflow
   repeats the source-policy and built-artifact checks before upload.
5. Source code, a Pages build, or a repository HEAD not covered by this
   standing policy is a **BLOCK**, not an invitation to bypass a warning.

No workflow deploys automatically from every push. A delegated maintainer
may invoke the workflows without making a false assertion that the owner
personally performed a new rights inspection.

Future new third-party scores, captures, documents, models, licenses or
unknown code must first receive separately documented provenance/rights
decisions and a new explicit policy revision. No wildcard approval is
inferred from the present release.
