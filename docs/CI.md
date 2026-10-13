# Continuous integration: future public repository

CI is defined in .github/workflows/public-ci.yml and runs on pushes, pull requests and manual dispatch. Before publication, the complete equivalent job was verified from a separate, clean local Git repository. Hosted GitHub Actions must also pass on the new public commit.

It uses pinned checkout/setup-python/setup-bun actions, read-only permissions, Python 3.14 and Bun 1.4.3. No provider API credentials are required.

The planned validation includes:

1. Profile counts, route digests, assignment-source SHA-256 verification, reconstruction of source decisions, structural native validation and independent Python compilation tests.
2. No numerical Artificial Analysis or Slopalytics mirror rows in the public benchmark snapshot.
3. Preservation of reviewed recipe evidence identities as link-only without embedded score values.
4. BFCL 3,241 numeric rows, source attribution and exact metric protocol metadata.
5. Browser transport integrity and deterministic rebuilding.
6. Pure Python optimizer/planner tests, frontend unit tests, lint and production build.
7. A release-boundary scan for raw third-party captures, account credentials and private filesystem paths.

A green public CI checks *this distribution*, not the external providers' scores or entitlements. This project does not configure GitHub Pages, automatic deployment, model inference, runtime agent installation or scheduled account polling.

## Local reproduction

    python3 -B tools/verify_public_release.py
    python3 -B scripts/review_objective_equivalences.py --verify
    python3 -B scripts/test_nan_quota_optimizer.py
    cd dashboard
    bun install --frozen-lockfile
    bun run test
    bun run lint
    bun run build

The owner explicitly approved creating this new public repository. Future commits must continue passing source attribution, security and reproducibility gates.
