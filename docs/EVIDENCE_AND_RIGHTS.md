# Evidence redistribution, attribution and external links

## Evidence used versus evidence redistributed

The complete private research corpus contains **72,590 scalar observations** including historical and superseded records; they are not 72,590 independent trials.

This release candidate **preserves the original 2,496 profile references and reviewed recommendations**, while limiting numerical redistribution to sources under an explicitly reviewed grant. Other publishers are retained as linked evidence; original profile choices are not recomputed against the smaller public subset.

### Initial reviewed numerical subset

| Source | Numeric rows | Release treatment |
|---|---:|---|
| UC Berkeley/Gorilla BFCL V4 | 3,241 | Numeric source-local values, protocol, metric type, unit, exact source and Apache-2.0 attribution |
| Artificial Analysis | 0 | Direct original links, no redistribution of its 59,585 recorded scores |
| Artificial Analysis mirrors / Slopalytics | 0 | Link-only; mirror records are not independent corroboration |
| Cognition, model cards, and other not-yet-cleared sources | 0 | Linked references, pending individual license check |

BFCL observations come from https://gorilla.cs.berkeley.edu/data_overall.csv. The official BFCL README (https://github.com/ShishirPatil/gorilla/blob/main/berkeley-function-call-leaderboard/README.md) explicitly publishes **all leaderboard statistics under Apache 2.0**, and names data_overall.csv as the overall-scores CSV used by the leaderboard. The official Gorilla LLM dataset on Hugging Face also identifies apache-2.0. This is a direct publisher license basis for the normalized BFCL statistics, independent of merely inferring it from the code license.

Methodological caveat: the official evaluator documentation states that summary metrics can count **unevaluated** categories as zero. Thus a BFCL aggregate may incorporate missing-category conventions and should not be interpreted as a complete task-by-task evaluation without checking the published protocol. The License column of the leaderboard refers to evaluated model licenses, not to the results dataset's Apache-2.0 grant.

## Artificial Analysis

The original local corpus includes 59,585 identified Artificial Analysis measurements. The release does not copy their values, original captured JSON or data mirrors. Its **853 direct model page links** are built from source model identifiers, not a copied scoring table. The **42 independently reviewed recipe citations** (19 Artificial Analysis; 23 Cognition) retain stable identities and upstream URLs without numeric scores.

The primary provider's terms govern bulk data distribution separately from its free API attribution rules; see https://artificialanalysis.ai/api-reference . Original publisher pages remain the source of truth for checking scores. Absent numbers are not zero values.

For other registered sources, data/public-evidence/source-links.json stores direct publisher URLs and provenance metadata. The sourceCoverage view contains 322 source descriptions. Aggregate withheld counts reside in data/public-evidence/release-manifest.json; the observations themselves do not.

## What is and is not reproducible

The **configuration and its decision history** are reproducible from unchanged source shards, exact role metadata and native file identities. Source citations remain traceable through IDs, model, metric, protocol and link.

The complete numerical justification using Artificial Analysis and other unredistributed publishers is **not fully reproducible from this offline public package**. Reproducing it requires consulting the publishers under their terms, or working within the separate private research corpus. The public distribution does not pretend that its BFCL-only numerical subset justifies every retained recipe.

## License scope

The original code is MIT. BFCL/Gorilla material retains Apache-2.0 attribution. Narrowly vendored reference-parser files retain their original upstream MIT copyright. Other publishers' observations, PDFs, websites, images and scores are not relicensed under MIT by inclusion of a URL.

See THIRD_PARTY_NOTICES.md and the link registry for the exact sources and restrictions.
