# Pretrained component exposure audit

Completed 2026-11-05, Asia/Shanghai. Evidence and query manifests remain under D:/Paper/casmi. No model inference, GPU use, training or large spectra/cache download was performed by this audit.

Saner `final_model.pt` is **declared_seen** for the published processed training identities, including former validation identities. `training_result.json` explicitly records a successful full-data refit. The checkpoint's stage metadata is `{'epoch': 16, 'stage': 'full_refit'}`. It cannot establish unseen validation performance on those identities.

Saner `best_validation_model.pt` has stage metadata `{'epoch': 16, 'stage': 'holdout'}`. The published training source restricts positives, hard negatives and auxiliary statistics to the training split. However, checkpoint selection evaluates the first 1,000 validation identities in `molecules.parquet` row order every epoch. We explicitly remove those identities before selecting the component experiment. The remaining selection exclusion is source-declared and content-audited, not reconstructed historical minibatches.

## Available component experiment

- Exact assets: [Saner V1](https://www.kaggle.com/datasets/sanpier/casmi-spectrum-model-v1/versions/1) and [Fold-safe FPNet V5](https://www.kaggle.com/datasets/dmitriigluzdov/casmi26-fold-safe-fpnet/versions/5), using `fpnet_fold0.pt` and `best_validation_model.pt`.
- Saner split: 246,450 train identities and 27,383 validation identities; 2,430,327 processed spectra. All published spectrum-manifest split labels match the molecule table.
- Fold0 exclusions: 55,367 structure rows, split reasons {'hold': 55102, 'np': 265}. Every published split sid/raw key/key matches the pinned 275,810-row structure table.
- Declared-key intersection: 5,449. Of these, 210 are in Saner's explicit checkpoint-selection set, leaving 5,239 proposed candidates. This count is only a declared-key count, not proof for all identities.
- A frozen hash sample plus NP intersections was independently checked by official RDKit 2026.03.3 identity. The checked training-unseen intersection initially contains 78 identities. We also exclude every identity scored as query OR decoy during checkpoint selection, using the actual SHA-bound `validation_candidates.npz` (1,000 query lists; 161,747 unique molecule indices). **32 selected identities remain eligible** after all checks. Query manifest: `reports/component_holdout_audit_20261104/component_intersection_queries.csv`. This is a component-level exclusion audit, not proof of an untouched independent final test.
- Fix candidate identities and ordering protocol before scoring. Compare fold0 alone with an added fixed-weight Saner best-validation score; retain an unchanged baseline, paired molecular uncertainty, and source/panel strata. No validation result is yet claimed for this proposed experiment.

## Integrity and limits

Saner hashes matched for all locally present files listed by its published `sha256.json`; mismatches: []. Best-validation SHA-256: `969d13443fcf168eae1e00e56a8e0ae87dcb16f337cb6dbac959e7cd218f089c`. Fold0 checkpoint matches `MODEL_INPUTS.json`; exact hashes are recorded in JSON. Historical fold manifests contain stale entries, mismatches among locally available files: {"MANIFEST_20261019.json": ["README.md", "SOURCE_CHECK_20261019.md", "SPLIT_AUDIT.json"], "MANIFEST_FIVEFOLD.json": []}. A stale manifest is not used to silently certify those individual files.

The Saner V1 `prepare.py` does not accept the `normalized_smiles` column named by its published data audit. Its dataset card acknowledges a later schema-compatibility repair and distinguishes that repair from exact checkpoint reproduction. Therefore the exact producer revision remains unresolved even though checkpoint/split artifacts and declared training scopes are auditable.

This is a **component-level, training-identity-exclusion experiment**. It does not certify the complete Flex/V43 stack, other FPNet checkpoints, ICEBERG, GLACIER or rankers as unseen, and does not certify unrecorded architecture/hyperparameter decisions as untouched by validation. The current 48-query pilot remains diagnostic. Same-formula filtering is never used as an identity gate: protonation/charge variants are checked by heavy composition and official canonical identity.

## Licence sources

Saner V1's author dataset card states Apache-2.0 for original checkpoints/scripts, retaining third-party and competition-data terms. Fold-safe V5's dataset card and `MODEL_INPUTS.json` state non-commercial competition-data terms with attribution for checkpoint/derived data; author training/audit scripts are Apache-2.0. This audit records the source declarations and does not establish competition-prize eligibility for the full stack.
