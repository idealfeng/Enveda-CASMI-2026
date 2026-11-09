# Experiment log

Validation scores are local MRR@25, averaged over two query draws (see the README for the
validation design). "Expected" = 0.16 × class 1 + 0.45 × class 2: the weights are an early
forum estimate of the test mix, and class 3 scores 0 with this approach. Public scores were
recomputed by the hosts after a metric fix (October 2026); the original value is in brackets.

## Submissions

| # | Date | Commit | Pipeline | Class 1 (A / B) | Class 2 (A / B) | Public LB |
|---|---|---|---|---|---|---|
| v1 | 2026-09-30 | 5a4285e | identity search (threshold 0.8) + analog propagation (power 8); pool = training ∪ normalized COCONUT | 0.845 / 0.688 | 0.570 / 0.510 | **0.263** (0.269) |
| v2 | 2026-10-06 | 8302eb7 | candidates restricted to COCONUT (+ NP-likeness ≥ 0.5, + strong identity matches); analogs without synthetic-only compounds; free slots filled from the full pool | 0.881 / 0.724 | 0.613 / 0.545 | **0.295** (0.294): +0.025 on the original scale, the gain validation predicted |
| v3 | 2026-10-06 | 0e4e321 | LightGBM lambdarank ranker (cross-instrument class 1, subset A included) + identity guard ≥ 0.97 | 0.857\* / 0.758 | 0.673\* / 0.618 | **0.313** (0.305): +0.011, within the leaderboard noise (±0.016) |

\* cross-validated on A, since A is part of the final model's training set.

The v1 pipeline was first checked on the visible test (score 1.0, expected since those
spectra are copies of training rows). Kaggle run time: 28 min (cleaning 11 min, index 6.5 min,
predictions 10.5 min).

## What was measured, and what it changed

| Question | Result | Decision |
|---|---|---|
| Add the identity score to the analog score with a weight of 10? | class 2 collapsed: same-mass isomers with a vaguely similar spectrum (similarity 0.3–0.6) jumped ahead | identity only counts above a threshold (0.9) |
| Power applied to analog similarities (1, 4, 8, 16, 32) | higher is better up to 16: a few very similar analogs carry most of the information | power 16 |
| Candidates: training ∪ COCONUT, or COCONUT only? | training structures outside COCONUT are mostly same-mass decoys for natural products | COCONUT only, plus strong identity matches |
| Use synthetic-only compounds (enveda-180, drug_plus) as analogs? | they point to wrong candidates | excluded as analogs |
| Filter PubChem by NP-likeness to extend the pool? | weak filter: COCONUT median 1.25, correct answers spread over 0.9–1.4 | not used; 8.8 M PubChem molecules scored and parked |
| Train the ranker on class 1 within the same instrument? | identity similarity of correct answers 0.99 in training vs 0.90 on A (timsTOF vs other instruments) | cross-instrument class 1 (class1x) |
| Let the ranker reorder exact identity matches? | visible test fell to 0.13: trained on natural products, it distrusts perfect matches outside COCONUT | guard: identity ≥ 0.97 always ranks first |

## Known limitations

- Class 3 (structures in no database, about half of the test by later forum estimates) scores 0.
- About 98 % of the ranking errors are same-formula isomers; positional isomers may be
  indistinguishable from their spectra alone.
- Validation molecules all belong to COCONUT, which favors a COCONUT-based pool.
- The class-2 training tables of the submitted ranker were built without the NP-likeness
  extension of the candidate mask, unlike inference; `scripts/build_feature_tables.py` now
  uses the inference masks for every table.
- A SMILES normalization fix (counter-ions removed before neutralization) affects 173 COCONUT
  keys (0.02 %); the candidate pool has not been rebuilt since.

The exploratory scripts behind these measurements (pool ablations, threshold and power tuning,
PubChem scoring) were removed from the tree to keep it readable; they remain in the git history.
