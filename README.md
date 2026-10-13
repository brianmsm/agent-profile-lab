# Agent Profile Lab

**Research-informed profile configurations for Gentle Shell/Pi and Oh My Pi (OMP).**

Agent Profile Lab stores baseline agent-role choices, provider access assumptions, workload scenarios, deterministic configuration compilers, and typed benchmark evidence. Its purpose is to make a candidate configuration **traceable, reproducible and explicit about limits**, not to suggest that a published model score proves the performance of an entire agent system.

> **Public source edition:** This is an owner-approved, rights-scoped public repository. It preserves the original 2,496 profile references, 33,414 active assignment slots, and author-owned configuration decisions without reranking them. It includes 3,241 license-reviewed BFCL numerical cells and external links rather than redistributing other publishers' results. The original private research laboratory retains all 72,590 numerical observations.

## Data and evidence boundaries

| Content | Included here | Meaning |
|---|---:|---|
| Original baseline profiles | **2,496** | Same role assignments, efforts, coordinator, fallback metadata and objectives |
| Active assignment slots | **33,414** | Source decision shards, with SHA-256 manifests |
| Retired historical SDD decisions | **16,224** | Preserved as history but not made executable |
| Legacy reference strategies | **160** | Unchanged; reviewed/NaN candidates are separate, opt-in policies |
| License-reviewed BFCL V4 metrics | **3,241** | Source-local numerical results; see Apache-2.0 attribution |
| Original numeric evidence held privately | **72,590** | Not reproduced here |
| Excluded numerical observations | **69,349** | Publisher URLs, source-register entries and review citations, not zero-valued measurements |
| External Artificial Analysis model links | **853** | Direct original source pages without scores |
| Linked source descriptions | **322** | Includes providers, evaluation families and unavailable/context-only sources |

The approved public source-rights policy is versioned in policies/public-evidence-redistribution.json and records the official BFCL statistics license, source and attribution requirements.

The original routing and review recipes are **not recalculated against a smaller evidence sample**. A recommendation can remain a historical decision informed by external information. However, someone cannot reproduce its complete numerical justification solely from this package: open the linked source to check those measurements independently.

## Quick start

Use Python 3.14 (or compatible) and Bun 1.4.x.

    python3 -B tools/verify_public_release.py
    python3 -B tools/rebuild_delivery.py
    cd dashboard
    bun install --frozen-lockfile
    bun run test
    bun run lint
    bun run build
    bun run dev

The dashboard has Spanish UI labels; developer/research documentation is in English. No API key is required. The public data is static, loaded locally from SHA-256-checked compressed chunks. No provider inference, account monitoring, installation or automatic model runtime hook is performed.

### Rebuild profiles from original author-owned decisions

    python3 -B scripts/prepare_data.py
    python3 -B scripts/validate_profiles.py

The 49,638 total source decision rows include 16,224 retired functional precedents, which remain documented but are not deployed. The profile/route source and native outputs are shipped with this distribution. The *full empirical benchmark source pipeline* requires separately licensed third-party raw captures and is **not** claimed to be included.

## Features

- **Full reference profile matrix:** browse 2,496 baselines for two version-pinned harnesses and six task domains.
- **Review of objective equality:** 116 pairs of different objectives have identical complete reference configurations; they are not presented as measured quality differences.
- **Opt-in candidate strategies:** activity complexity, guarded worker/auxiliary delegation, alternative model recipes and hybrid provider planning.
- **Independent NaN monthly allowances:** static proportional allocation and optional pure dynamic subtask planner.
- **Workload customization:** edit all 20 canonical functions' monthly calls and total input/output tokens, with versioned import/export.
- **Native configuration exports and signed manifests:** structural validation and source lineage; no installation or credential handling.
- **Research evidence:** a licensed numeric BFCL subset and link-only external source index including Artificial Analysis.

## Interpretation

Do not conflate published LLM capability, tool use, gateway entitlement, native harness configuration, cost per evaluation and actual task success. Model-version aliases are conditional until verified; quotas are assumed rather than observed. Quality admission precedes proportional optimization.

## Documentation

Read [Architecture](docs/ARCHITECTURE.md), [Evidence and attribution](docs/EVIDENCE_AND_RIGHTS.md), [Reproducibility](docs/REPRODUCIBILITY.md), [Public CI](docs/CI.md), and [Release checklist](docs/RELEASE_CHECKLIST.md).

For the historical 39-commit research development chronology and the distinction between original private Git ancestry and curated public commits, read [Development provenance](docs/DEVELOPMENT_PROVENANCE.md).

## Licensing

Original author-owned code is licensed **MIT** (LICENSE). Separate upstream copyright and Apache-2.0 notices must be retained for the licensed BFCL subset and vendored reference parser. The MIT grant does **not** relicense benchmark results, third-party publications, account data or evaluation task contents. See THIRD_PARTY_NOTICES.md.

**Status:** public MIT-licensed source, rights-scoped BFCL measurements and external-only references to other publishers. This is not a calibrated live agent service or an inference gateway.
