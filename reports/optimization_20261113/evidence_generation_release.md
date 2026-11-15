# Generation production stage: independent release review

**Recommendation: release the unchanged `generation_production` stage for one Kaggle submission.** The previous source-pin/runtime-path failure is closed on the tested local production subset. No leaderboard gain is established.

The actual run completed all 20 outer code cells in 2,327 seconds, including the original FROZEN Engine2 initialization, PubChem, Engine1/V1FE generation, actual 160-feature ranker projection, GLACIER/ICEBERG, dual neural scoring, MASS, guarded heads, both external libraries, and final CSV. It did not skip cells or substitute cached candidate scores. The original .488 parent's cells are unchanged except the explicit runner setup in cell12, plus the appended generation audit.

Independent review script: [evidence_generation_review_20261113.py](../../scripts/evidence_generation_review_20261113.py). Detailed machine-readable review: [evidence_generation_review.json](evidence_generation_review.json). Original execution: [verification.json](../../runs/generation_production_20261113_r2/verification.json).

- Notebook SHA: `a9debc93f59213d3c80a8b3ee0e4808ee930d6ada34c3ee908f1469fa35cfa2c`.
- Patched engine SHA: `e4943fb26a8141f47ea95e744910c2d0f4746e36e72ef43e3263e7f327cfc0b5`, independently reproduced from the original asset and the original FROZEN27 one-line determinism patch, then checked against the installed runtime source.
- Final CSV: exactly two IDs in sample order, 25 nonempty unique candidates each; SHA `e58cde08da50a70a28b35484ef34e62917b56bd3ad648c3a54a594b6aa519416`.
- Both Engine2 and PubChem produced two nonempty lists, main errors and placeholder rows are zero. ICE and GL each scored all 136 candidates with no prediction failures; neural error lists are empty. The old `CLAW STAGE HEALTH ... NOT RUN` banner is stale; actual model metadata, outputs and the execution receipt confirm scoring.
- Both queries actually use 12 parents. Generation produces 8 and 300 candidates; the actual Engine25 contains 15 generated candidates in total and the final25 lists contain 14. These are raw-SMILES diagnostic counts, **not** incremental recall, Class-3 recovery, or a score improvement.

The input accidentally retains 12 extra fields from the old validation table, including `normalized_smiles`, `inchikey14` and `official_identity`. Thus the original verification text calling the two queries “unlabelled” is wrong. Preparation and input-schema records now disclose this. Manual source review of the actual Engine2, PubChem, FROZEN39/41, neural scorer, guarded-head and external-library query consumers found no query-label reads into prediction features. They consume spectra and candidate structures. `export_evidence.py` does persist the entire query frame, so labels remain in the exported evidence file. This is source review, not dynamic field-access instrumentation; the run is only a deployment-path smoke test and is not clean validation or evidence of generalization.

Full hidden-test resource use on Kaggle T4 and scoring remain untested. Both external libraries loaded and actually matched, but found zero hits here, so this subset does not exercise the promotion branch. N1 proxy is inapplicable to the two H+ queries. There is no same-run default-generation control, and this review does not infer an algorithm gain from generated-candidate counts.
