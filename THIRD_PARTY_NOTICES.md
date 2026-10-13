# Third-party rights and attribution

Agent Profile Lab's original author-owned software source is provided under the root MIT license. This MIT grant **does not relicense third-party data, upstream software or publications**.

## Berkeley Function Calling Leaderboard (BFCL)

- Publisher: UC Berkeley / Gorilla project; authors and contributors to the Berkeley Function Calling Leaderboard.
- Official repository: https://github.com/ShishirPatil/gorilla
- Official leaderboard source: https://gorilla.cs.berkeley.edu/data_overall.csv
- Project license: Apache License, Version 2.0 (see licenses/GORILLA_APACHE_2.0_LICENSE.txt and the upstream LICENSE).
- Local scope: a normalized, source-attributed set of 3,241 numerical BFCL V4 cells; these are publisher scores with original units, methods, source identifiers and protocol caveats. No model weights, source-site HTML or evaluation trajectories are redistributed.
- **Explicit statistical-data grant:** the official BFCL README (https://github.com/ShishirPatil/gorilla/blob/main/berkeley-function-call-leaderboard/README.md) states under Contributing that **all leaderboard statistics** are released under Apache 2.0. The same README identifies data_overall.csv under Output Structure as the overall-score file used to update the leaderboard. This documents the statistical-data licensing basis beyond the repository-wide code license.
- **Dataset corroboration:** the official Gorilla LLM dataset card (https://huggingface.co/datasets/gorilla-llm/Berkeley-Function-Calling-Leaderboard) independently declares apache-2.0.
- Reuse conditions: retain notices and upstream attribution, identify adapted/normalized measurements, and do not misattribute the evaluated third-party models' own licenses. The official BFCL evaluation documentation warns that summary scores may treat unexecuted categories as zero; such scores are publisher aggregates, not measured success on every category.

## Upstream native-parser reference code

Some tests vendor narrowly scoped reference parser code under tests/vendor/gentle-shell-4.0.0. Its original MIT notice is retained in that directory, including the upstream copyright notice. Do not replace this notice with the project's own copyright.

## Artificial Analysis

- Publisher: https://artificialanalysis.ai/
- Research references: direct original pages, model labels, benchmark names and reviewed observation identities, **without the publisher's 59,585 score records**.
- These records and associated Slopalytics mirrors are **link-only**: no numeric scores, raw JSON captures or mirrored rehosted tables are distributed.
- Relevant terms / API and attribution: https://artificialanalysis.ai/api-reference
- Our analytical profile assignments and historical candidate rationales remain unchanged. Reusing our project MIT source code does not grant any right to the underlying Artificial Analysis dataset.

## Other external research and benchmark publishers

Additional indexed sources remain external link references pending verified rights for their particular datasets. These include Cognition FrontierCode, published model cards, system cards, security benchmarks, historical public aggregators and other mirrors.

The file data/public-evidence/source-links.json identifies the original publisher URLs and the fact that scores have not been redistributed. No absent score should be interpreted as zero, and a hyperlink is not a license to scrape or reproduce the linked dataset.
