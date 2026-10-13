# Contributing

Keep model evidence, provider access, harness capability, quota assumptions and real execution results separate.

- Add a source-licensing disposition before incorporating a new external numerical dataset.
- Preserve original reference routes and never relabel profile objectives to fabricate meaningful differences.
- Mirror captures do not count as independent experiments.
- Null source values mean **not redistributed**, never zero.
- Maintain protected coordinator/review roles, bounded task-oracle requirements and explicit experimental opt-in.
- Retain MIT on original author code and appropriate attribution notices for third-party data/software.
- Run the release verifier, relevant Python tests, TypeScript frontend tests, lint and build.

Raw publisher data or account-specific materials must not enter the public repository without explicit rights and privacy review.

## Safe maintenance and Git history

Read [Safe maintenance](docs/SAFE_MAINTENANCE.md) before transferring code from
another repository. Public commits must descend from the approved public
baseline without importing private Git objects. Use linear public commits or
squash a reviewed public-only branch; do not merge private ancestry.

Run `python3 -B tools/test_public_boundary.py` and
`python3 -B tools/audit_public_distribution.py --history` **before pushing**.
Hosted CI is a second check, not a way to discover leaked data after upload.
