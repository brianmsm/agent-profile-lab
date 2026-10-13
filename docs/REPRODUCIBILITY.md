# Rebuilding and verifying the proposed public release

## Source layers

- Original author-owned decision shards under data/assignment-shards with SHA-256 manifest, **49,638 total historic decisions** and **33,414 active roles**.
- Profile index, portfolios, domain policies, OMP runtime policies, catalog and versioned harness contracts.
- Original native Gentle Shell/OMP reference files under profiles/.
- Public typed BFCL subset in dashboard/public/data/snapshot.json, plus a 322-source link register and 853 direct Artificial Analysis model pages.
- Compressed browser transport under dashboard/public/data with a manifest and SHA-256 checksums.

## Basic validation without provider requests

    python3 -B tools/verify_public_release.py
    python3 -B tools/rebuild_delivery.py
    python3 -B scripts/prepare_data.py
    python3 -B scripts/validate_profiles.py

The public verifier checks reference/profile/role cardinalities, source-shard hashes, licensed numeric inclusion, missing Artificial Analysis numerical observations and preservation of externally reviewed recipe references.

The approved publisher allowlist and explicit official BFCL statistics license evidence are stored in policies/public-evidence-redistribution.json and pinned by SHA-256 in the release manifest. No external API call is required to check this provenance contract.

**BFCL limitation:** the publisher documents a zero-valued treatment of unevaluated categories within certain overall summary scores. Preserve this as a source protocol limitation; the public release does not reinterpret zero-valued publisher aggregates as proof a category was actually run.

Frontend commands:

    cd dashboard
    bun install --frozen-lockfile
    bun run test
    bun run lint
    bun run build
    bun run dev

The original check_project.py --rebuild attempts to normalize *raw external source captures*. Those captures are intentionally absent; use the public verifier and public CI rather than claiming a complete public reproduction of the private 49-step research workflow.

## No hidden recommendation recalculation

The public and original private source profile routing/metadata digests are identical and recorded in the release manifest. The assignment-shard manifest hash also matches. Stored candidate policies keep exactly the same selection rules, referenced roles and model offerings even though their review data are now source links without scores.

## Updating evidence

Include new publisher numerical data only after verifying its exact license scope, version, metric meaning and task denominators. Review the source-level allowlist and validate the full public package. Do not treat null scores as zero or cached mirror values as independent trials.
