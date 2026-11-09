# Discussion 743254 review — 2026-11-04

Primary URL: https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/743254

Title: Lessons from ~30 submissions: where the MRR actually goes. Author: Udam Liyanage.

## Access and evidence boundary

The live page produced no readable lines in the web tool. Direct anonymous GETs of the page, the official topic/comments endpoints, and an internal topic endpoint returned HTTP 404; small receipts are retained beside this file. The Kaggle URL's search-index snapshot supplied the author's nine-point original post. A later query on 2026-11-04 also exposed the comment thread directly under that original URL; these are indexed author comments, not a third-party summary. The snapshot was labeled crawled two weeks ago, so current edits remain unverified.

## Author observations, paraphrased

- The visible test file cannot establish hidden performance; candidate identities must follow scorer tautomer canonicalization.
- On the author's holdout, roughly 8% had truth-tautomer duplicates. About 98% of database-route wrong winners, conditional on truth being recalled, shared its formula. A truth-plus-hard-isomers panel was more sensitive than overall MRR.
- Their instrument-matched precursor errors mostly lay within 5 ppm; 8.5 versus 10 ppm scarcely changed candidates.
- Curated databases added no missing-structure coverage in their tested subset. Membership features improved public holdouts but hurt leaderboard results.
- Artificially deleting known structures overstated generation reach about threefold versus genuinely absent molecules. Generated candidates had not helped their leaderboard.
- GBDT seed changes moved their holdout MRR by up to ±0.007. They advised several seeds and caution below roughly 0.005.
- Their public-library class-2 proxy and small timsTOF NP panel disagreed on different changes; chemistry-specific changes tracked the latter better. Structure-dependent fragmentation evidence yielded gains for them.

All numerical values above are the author's reports, without independently reproduced splits, counts, uncertainty or isolated causal estimates. They are not universal thresholds or hidden-test statistics.

## Actions for our project — our proposed experiments

1. Keep both identity-disjoint public-library and same-instrument NP validation. Record both deltas and molecular paired uncertainty; do not select changes using a single weighted proxy fitted to LB.
2. Freeze candidates and define a same-formula hard-negative panel. Compare the frozen baseline with an added structure-dependent score; report recall separately so a ranking experiment cannot hide recall changes.
3. Repeat ranker experiments across fixed seeds; estimate our own variability rather than accepting the author's ±0.007 or 0.005 as constants.
4. Audit metric-identity duplicates and verify generation on genuinely absent identities before investing in a larger generation/database download.
5. Multi-view or collision-energy pooling is a separate hypothesis from our plan. The retrieved post and comments contain no specific multi-view improvement experiment.

The post is an experiment-design resource, with no downloadable code/model recipe in the retrieved body. It does not justify a new dataset or checkpoint download by itself.

## Indexed comment follow-up

NeckBeard reported that selecting four fragmentation hyperparameters on the reported 241-molecule NP panel inflated the selected +0.065 panel-MRR improvement. With parameters frozen, four additional library panels totaling 1,000 molecules gave +0.023 ± 0.007. These are the commenter's measurements, not reproduced results. Udam clarified that his approximate 0.03 visibility threshold concerns end-to-end full-list leaderboard scale; it is not a required isomer-panel improvement. Panel effects can shrink when only some molecules are isomer-limited and when new features overlap existing evidence. Thus we freeze tuning versus evaluation identities, test across sources, and measure incremental whole-pipeline benefit before projecting medal performance.

## Related host correction: discussion 741404

Primary URL: https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/discussion/741404

The original-URL search snapshot includes David Healey's comment, explicitly labeled **Competition Host**. He clarifies that the public leaderboard is evaluated on the hidden test set's public split, not the downloadable dummy test file. Short exact excerpt:

> but rather on the public split of the Hidden test set provided to your submission notebook.

Therefore the EDA author's inference that public LB measures the downloadable Enveda-180 dummy is directly contradicted by the host. Placeholder exploration remains useful for schema/runtime checks; it does not determine LB composition or justify ignoring LB. No comment ID/permalink was exposed, so the discussion URL is the precise supported source link.
