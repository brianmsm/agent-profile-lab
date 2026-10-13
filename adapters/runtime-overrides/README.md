# Runtime overrides

Baseline OMP profiles now include reviewed runtime usage settings:

- advisor.enabled=false
- advisor.syncBacklog=off
- task.eager=default
- a domain/objective-specific task.maxConcurrency ceiling

This prevents the user's global advisor activation and task-delegation preference from silently changing Economy/Balanced/Speed behavior.

Optional OMP overrides:

- `omp/advisor-on.yaml`: deliberately enable the configured advisor role.
- `omp/delegation-preferred.yaml`: deliberately nudge the main model toward task delegation.

Gentle RDD criticality is handled with full profile variants under:

`profiles/gentle-shell-variants/critical-review/`

Those variants raise risk, reliability, resilience, refuter, and validator to high while preserving every other routing decision from the corresponding base profile.
