# Adversarial audit remediation — 14 October 2026

## What changed, and what did not

The owner requested remediation of R00–R10 on the reference revision. This is a
reviewed **metadata/contract release**, not an empirical reranking. Original
reference files and decision history remain in each repository's own Git ancestry.
No private history is transferred to the public repository.

**Unchanged:** 2,496 reference profile IDs; 33,414 active slots; 16,224 retired
source precedents; model identities, efforts, fallback selections, native runtime
parameters; all 3,744 native files including critical-review variants; 160 stored
reference strategies. No publisher observation is re-scored or newly published.

**Corrected:** canonical domain/objective/portfolio labels, historical Claude
statements explicitly dated and superseded, OMP `judge` taxonomy, and claims about
what a native model map actually implements. The shard hashes change because the
source descriptions were corrected. They must no longer be described as the exact
original CSV bytes. `policies/source-metadata-amendment.json` keeps original/current
hashes, normalized non-label field hashes and all native file hashes. Run:

```sh
python3 -B scripts/verify_source_amendment.py
python3 -B scripts/test_metadata_contracts.py
```

`prepare_data.py` and the standalone profile validator now reject blank or
contradictory labels. They do not silently guess or repair newly corrupted input.

## Finding dispositions

| Finding | Implemented disposition | Remaining limit |
|---|---|---|
| CR-01 labels | Corrected at source, fail-closed validation, complete differential receipt | Native choices were not reranked |
| CR-02 declarative gates | Per-profile UI and exported assurance distinguish configured/declared from installed; offline preflight never grants operational permission | Actual tool permissions, isolation and human-review hooks must be verified in the deployment |
| CR-03 OMP judge | `auxiliary-classification`, excluded from independent review counts and automatic offload | A selector does not install a classifier agent |
| CR-04 review/effort uniformity | Explicit per-profile warning, active-only reviewer/route counts, paired trial-plan generator | No independent-error or latency measurements yet |
| CR-05 Apps-derived cybersecurity | Per-profile provenance warning and explicit external-control requirements | No cyber calibration or real security execution performed |
| CR-06 equivalent objectives | Same-resource/domain/harness native equivalence shown across objectives, independently of the current filter | Declared fallback/conditions may still differ |
| CR-07 reserves | Separate effort alternative, same-access different model, different resource; catalog supersession warning | Dispatch and provider availability are not verified by the manifest |
| CR-08 runtime drift | Exact expected and supplied runtime versions checked; mismatch blocks current-artifact preflight | OMP 18.9.2 is not silently declared equivalent to target 18.8.7 |
| CR-09 evidence transfer | Every one of the 13 recipes has an explicit mapping per function: claim, sources, analogy limit and acceptance criterion | An external score does not measure this role/endpoint/harness |
| CR-10 visual coverage | Active-primary and fallback capability warnings, no invented vision route | Tools or image-capable external route require separate testing |
| CR-11 outdated justification | Historical Claude note retained with supersession date; max efforts flagged unmeasured | No automatic low/max replacement |
| CR-12 stale generated examples | Native + input hashes checked, historical-only mode explicit; old examples preserved | Regenerate separately for the selected current revision |
| CR-13 quality/quotas | Single-access concentration and unmeasured cost/latency explicit; no arbitrary provider quota | Model performance comparison remains an approved future experiment |

These dispositions are not evidence that every underlying model performs well.
A warning or preflight gate resolves misleading acceptance, not an unrun experiment.

## Native artifact and runtime preflight

```sh
python3 scripts/preflight_profile.py \
  --manifest generated/path/profile.manifest.json \
  --native generated/path/profile.yaml \
  --runtime-version 18.8.7
```

Checks native hash, current input hashes, role semantics and declared target
version. It never reads credential files, makes provider requests, installs an
agent or certifies tool access. `readyForOperation` remains false: operational
controls and route acceptance are outside a static artifact check. Runtime version
input is explicitly user-declared, not proof of a successful startup.

The old `compile_profile.py --verify-manifest ... --native ...` now checks source
currency by default as well. `--native-only` is for **historical forensic integrity**
only, never a way to certify a stale artifact for deployment. Original examples in
ignored `generated/` are not overwritten to make an old receipt appear current.

## Classifier taxonomy and existing custom workloads

There are now **21 explicit functions**, not 20: classification is separate from
review. Its initial hypothetical calls/tokens copy the prior review burden, so
relabeling does not manufacture quota savings for the existing judge role.

Existing 20-function JSON files retain their original fingerprint and bytes.
Migration checks that historical revision and fingerprint, keeps every original
row and requires acknowledgement before copying the review hypothesis to the
classifier. It writes only a **new file**:

```sh
python3 scripts/migrate_nan_workload.py --input old-workload.json \
  --output migrated-workload.json --confirm-inherited-assumption
```

The browser uses a new storage key and leaves the old one untouched. Its recovery
panel can export an acknowledged migrated copy without applying it automatically.
New assumptions must be inspected before selecting **Apply**. The catalogue-wide
sum gains a distinct function instance; per-profile totals still count actual
configured roles and must not be conflated with that catalogue sum.

## Paired role-effort experiments prepared, not executed

```sh
python3 scripts/build_adversarial_trial_plan.py \
  --profile omp--nan-agent-use-balanced \
  --roles commit tiny memory plan slow judge \
  --repetitions 5 --output validation/new-trial-plan.json
```

The plan randomizes effort arms within matched role/fixture/repetition pairs;
keeps model, origin and target explicit; fixes oracle identity by hash; and leaves
results, tokens, latency, attempts, monetary cost and currency **null**. Inference
and spending are **not authorized** by creating a plan. The included seven owned
synthetic falsification fixtures are not a representative benchmark or full
computer-use evaluation. Functions without appropriate domain-specific fixtures
are reported as unmapped, not counted as tested.

Before running paid or quota-consuming trials, approve a bounded budget and exact
access/runtime, hold out evaluation material, predefine acceptance and stop rules,
record failures and retries, and measure time/cost through **accepted output**, not
just the first answer. Test review diversity with defects and negative controls;
different model names alone do not establish independent errors. No selection is
promoted to empirical evidence by oracle unit tests.

## Public release boundary

The public amendment renews hashes only for reviewed owner-authored metadata,
code and policy changes. All original publication/rights records are retained;
the release verifier requires the amendment rather than rewriting the original
source-manifest hash. Numerical inclusion remains BFCL-only. Private captures,
research scores, raw audit reports and source backups are not copied into Pages.
The non-indexed reference Pages site still builds the safe public source only.
