# CASMI26 private spectrum->structure scorer (ours, v2)

Trained with the public training kit (`sanpier/casmi-spectrum-model-v1`), 80-epoch schedule,
early-stopped at epoch 56 (best epoch 52), on the competition `train.parquet` (2.43M spectra).

* `final_model.pt` — checkpoint (full refit)
* `config_used.json` — training config
* `training_result.json` — training diagnostics

Self-built validation diagnostic MRR@25 = 0.6603 (public kit baseline = 0.4844).

**config_used.json is load-critical**: the kit's `model.py` reads `width/heads/layers/embedding`
from it (here `192 / 6 / 3 / 192`). Keep the shipped file; do not regenerate it from the kit
default, whose 16-epoch values describe the baseline rather than this model.

Usage in the 0.480 pipeline: attach this as a Kaggle dataset; the notebook's
`_discover_private_models()` picks up any `final_model.pt` that has a sibling `config_used.json`
under `/kaggle/input`, and `_swap_to_model()` then scores with it. Neural scores are ENSEMBLED
with the public model scores (0.5/0.5 per-molecule z-scores). Replacing the public model
outright scored 0.460 on the public leaderboard — the ensemble is what gives 0.480.
