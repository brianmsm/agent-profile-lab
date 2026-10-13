# Safe public maintenance

The public and private repositories already exist. They have independent Git
histories. Routine maintenance preserves public ancestry; it never creates a
replacement repository, imports private commits, or changes data rights.

## Code changes are not evidence releases

The private maintainer has a narrow, explicit path allowlist and a two-phase
patch planner. It reads committed UTF-8 code/documentation, pins both repository
HEADs and the policy, records before/after SHA-256 values, and retains private
old-file backups. Planning and verification do not modify the public checkout.
The maintainer reviews and separately applies the exact patch before committing.

There is no automatic commit, push, merge, cherry-pick, installation, provider
inference, or subscription spending. A hash is a checksum, **not a digital
signature or an independent authorization**. Approvals require a trusted review.

Profiles, assignment shards, snapshots, source-rights policies, licenses, account
inventories, raw captures, and bundles are outside this maintenance channel.
Their modification requires a separate explicit review and reproducibility
checks. Missing external source values remain null/not redistributed, never zero.
The existing reference configurations are not recomputed against public data.

## Checks before publication

In the independent public checkout, inspect `git status`, the exact diff, and
both fetch and push URLs of `origin`. Then run:

```sh
python3 -B tools/test_public_boundary.py
python3 -B tools/audit_public_distribution.py
python3 -B tools/verify_public_release.py
python3 -B scripts/test_profile_compiler.py
python3 -B scripts/test_nan_quota_optimizer.py
python3 -B scripts/review_objective_equivalences.py --verify
```

Run frontend tests, lint and build for the exact candidate. After making the
reviewed local commits, but **before pushing**, run:

```sh
python3 -B tools/audit_public_distribution.py --history
git diff --check
git status -sb
```

The history check requires the approved public baseline
`58a682d6ca6f3ed0b595d7daed5208bc56bd9385` as an ancestor. It inspects every
added/modified blob after that baseline, including a file later deleted.
Private merges, unrelated histories, symbolic links, tracked runtime artifacts,
Git bundles, unreviewed archives, likely secrets, and recognized non-allowlisted
publisher score rows fail the checks. Use linear commits or squash reviewed
public-only branches; merging private Git history is not supported.

Compressed dashboard chunks are decoded with a size cap, checked against their
content-addressed filenames, and scanned as JSON. Only chunks referenced by the
delivery manifest are accepted. The independent release verifier checks the
lossless reconstruction and preserves profile, assignment and evidence contracts.

CI uses read-only repository permissions and full **public** history for the
history check. On pull requests it checks the contributor head, not GitHub's
synthetic merge commit. Checks also run on the checked-out candidate tree.

## Limits and recovery

These controls are not exhaustive secret detection, proof of dataset licensing,
or evidence of empirical agent superiority. Unlabelled, encoded, or cleverly
reformatted publisher numbers still require human review. The original nine
public commits are the pre-existing reviewed baseline, not newly re-audited by
the incremental history scanner. The current tree is checked independently.

Hosted CI runs after upload. It does not prevent the first disclosure from an
unsafe push; local preflight is mandatory. Branch protections are a separate
repository setting, not enabled by these scripts. Avoid concurrency: re-run plan
verification immediately before applying and recheck the exact diff before push.

Keep old-file backups and review receipts privately. For an uncommitted patch,
review `git apply --reverse --check` before any deliberate reversal. For a
published code regression, use a new public revert commit; do not force-push or
copy a private bundle. Reverting leaked data does not remove it from history:
stop publication and handle the incident separately.
