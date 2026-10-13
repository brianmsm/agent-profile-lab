# Public release checklist and future distribution safeguards

This new public repository is assembled from the owner-approved, independently verified source tree. The previous demo repository was deleted by the owner, and this publication contains none of the original private Git objects.

## Requirements before a new public repository

- [x] Confirm owner (brianmsm), repository name (agent-profile-lab), public visibility and description.
- [x] Confirm this publication matches the independently tested package aside from explicit publication-status and history-provenance adjustments.
- [x] Preserve the original 39 commits outside the public Git object database and document their real commit chronology in docs/DEVELOPMENT_PROVENANCE.md; stage genuine new public commits instead of fabricating historical ancestry.
- [x] Owner approved MIT on original code; upstream MIT and BFCL Apache-2.0 notices are retained.
- [x] Verify BFCL score CSV redistribution: the publisher BFCL README expressly declares all leaderboard statistics Apache 2.0 and identifies the CSV by name. Preserve license/attribution and mention the unevaluated-category zero convention.
- [x] No Artificial Analysis or Slopalytics numerical values are redistributed, only original source links.
- [x] Reviewed source boundaries; the privacy and credential-pattern scan passed on the exact public candidate tree. Future contributions require review.
- [x] All 2,496 profile routes, 33,414 active assignments, 160 strategies and source manifest SHA-256 identities have been verified.
- [x] All steps of the public CI equivalent passed in an independently created local Git repository.
- [x] The owner deleted the previous public demo repository and authorized creation of this replacement.

## New public repository bootstrap

The new Git history was initialized from the approved sanitized package only, with the source grouped into meaningful new milestones:

    git init -b main
    git add .
    git diff --cached --check
    git commit -m "One genuine public assembly milestone per source group"

Inspect the hosted GitHub workflow after the initial push. Never push the original private research Git history or unreviewed publisher captures.

## How this package differs from the current public demo

The first demonstration showed only 46 sample profiles. This candidate restores the complete 2,496 original profiles and author-owned source decisions, along with a clearly delimited numeric BFCL corpus and direct external evidence links. It does not change recommendations or infer substitute scores for excluded publishers.
