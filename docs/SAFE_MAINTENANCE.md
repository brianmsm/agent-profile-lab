# Safe maintenance — current single-maintainer workflow

The two repositories have **independent histories**. Only reviewed, explicitly
mapped code/documentation changes may transfer from the private repository.
Never push the private history, copy full directories, or widen the scientific
or rights-scoped public dataset through routine sync.

**Canonical operational procedure:** the private checkout's
`republication/SAFE_SYNC.md`. Earlier R3b–R3j adversarial instructions and the
initial new-repository checklist are retained as history, not required work on
every ordinary change. There is no automatic publication authorization.

## Local public preflight, after a reviewed commit and before ANY public push

```sh
python3 -B tools/audit_public_distribution.py --release-inventory > /path/to/private/ignored/review.json
python3 -B tools/verify_public_release.py
python3 -B tools/test_public_boundary.py
python3 -B tools/test_bfcl_anchor.py
python3 -B scripts/test_r3b_contracts.py
git diff --check
git status --short --branch
cd dashboard && bun install --frozen-lockfile && bun run test && bun run lint && bun run build
```

The inventory uses a **live read-only** `ls-remote` of the public `main` and
refuses unknown/divergent ancestry. Examine `releaseInventory.newReachableGitObjects`
and every `historicalChangedFileVersions` record, including paths deleted later
in Git history. Every changed version is review-required; a scanner passing
means neither semantic JS exhaustiveness nor third-party redistribution rights.
The live main comparison does not enumerate every other possible public ref.
If the network is unavailable, this step does **not** pass offline.

For each *exact* built Pages distribution, run:

```sh
python3 -B tools/audit_public_distribution.py --built /path/to/new/dist \
  --compare-pages-to /path/to/private/verified/R3j/historical/pages/public
# Repeat for reference, with its OWN historical 17-file Pages directory.
```

The comparison pins the 17+17 historical byte inventories: changed, added or
removed assets require explicit source/content/rights review. Unchanged hashes
prove only identical bytes, not legal clearance. The public repository must
still pass `tools/audit_public_distribution.py --history` and
`tools/verify_public_release.py` in CI. Never include raw snapshot.json in Pages.

### What blocks publication

Any changed or historically added byte not reviewed, suspected secret/private
path or prohibited data, unproven redistribution permission, failed science or
frontend check, unexpected Git ancestry/remote, or changed Pages content without
review. The **existing externally installed Ed25519 exact-HEAD/Pages authority**
and separate signed human rights gate still apply: absent permission means **STOP**.
A real owner decision to replace that authority would require a separate
migration; no change is active. Passing checks never grants a push or merge.

Routine CI covers the data, BFCL, provenance, Git/DLP boundary, frontend and
actual Pages bytes. Historical deep SHA/JS red-team suites remain available by
manual workflow dispatch, not as a regular development cycle. A solo maintainer
may inspect changes with AI assistance but must not claim institutional
independence or legal review performed by the model.
