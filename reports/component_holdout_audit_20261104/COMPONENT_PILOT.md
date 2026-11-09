# Component pilot protocol

Entry point: `scripts/run_component_neural_pilot.py`. The frozen initial plan is `runs/component_neural_pilot_20261105/plan.json` (plan only; no inference). This is separate from the full Flex pipeline's final-25 reranking experiment.

The audited intersection contains 32 identities after excluding Saner training identities, FPNet fold0 training identities, and **all** candidates used for Saner checkpoint selection. None overlaps the existing locked 250 final identities. Three are public NP development examples; 29 are other component queries. These counts are fixed before any prediction or truth-in-window check.

```bash
source scripts/linux_env.sh
.venv-linux/bin/python scripts/run_component_neural_pilot.py --mode prepare --output-dir runs/component_neural_pilot_20261105
.venv-linux/bin/python scripts/run_component_neural_pilot.py --mode run --output-dir runs/component_neural_pilot_20261105 --device cuda
```

Run `prepare` and `run` only when scheduled by the root agent, sequentially with other full inference jobs. Preparation scans local training spectra and keeps at most 12 spectra per query over the ten supported adducts, balancing adduct/polarity and collision-energy bins. It then retrieves the pinned candidate pool in a ±10 ppm window around measured adduct-derived median neutral mass. True structure/mass is never used for candidate injection or query acceptance. Empty retrieval remains a zero-recall case.

Fold0 scores the full retrieved pool, averaging single-spectrum fingerprint logits. Its best 25 valid metric identities are frozen. Saner **best_validation_model.pt** scores those exact candidates, using the published equal-spectrum score average. Treatment applies fixed RRF `1/(3+fold_rank) + 0.25/(3+saner_rank)`. Both final arms contain exactly the same identity set; this experiment cannot recover truth truncated out of the fixed top25. Pre-ranking recall and final top25 hits are reported separately.

Outputs include frozen queries/truth, retrieved candidates, the fixed top25, aligned component scores, baseline/treatment CSVs, candidate audit, paired molecule bootstrap intervals (overall and by panel), SHA-bound receipts and failures. There is no reference-library search, model training, automatic download or Kaggle submission.

The source/split declarations are audited but the exact historical Saner producer revision remains unresolved. This supports a conservative component experiment, not a claim of full-stack clean CV or an untouched independent final holdout. Three deterministic protocol tests pass; the complete preparation/inference path has not yet been executed.
