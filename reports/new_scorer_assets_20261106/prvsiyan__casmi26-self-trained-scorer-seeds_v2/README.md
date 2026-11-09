# CASMI26 self-trained scorer seeds

Two seeds of a spectrum-to-structure candidate scorer for the CASMI 2026 competition, each trained from random weights on Kaggle GPUs using our own Kaggle GPU quota. These are candidate scorers, not submissions: they score supplied candidate structures for a spectrum; they do not retrieve candidates from a database.

## What the models are

Spectrum-to-structure candidate scorers. Input: an MS/MS spectrum (peak m/z and intensities, precursor m/z, adduct, ionization mode, collision energy) and a list of candidate SMILES. Output: one score per candidate, larger ranks first, -inf for invalid SMILES. Scores are uncalibrated. Architecture: a transformer over spectrum peaks, a spectrum-molecule embedding, and a 2048-bit Morgan fingerprint head.

## Credits

- Training recipe: bgunshui/casmi26-scorer-train-public.
- Saner v1 kit: sanpier/casmi-spectrum-model-v1 (model.py, features.py and inference.py come from this kit lineage).
- Our trained models are not a copy of bgunshui's checkpoint (different sha256, see MANIFEST.json).
- Flagship notebook: https://www.kaggle.com/code/prvsiyan/analog-propagation-casmi-2026-baseline

## Contents

One folder per verified seed, named by its actual seed value:

- seed_20261103/ (seed 20261103)
- seed_20261104/ (seed 20261104)

Each folder has final_model.pt (refit on full data; use this for inference), model.py, features.py, config_used.json, training_result.json. MANIFEST.json lists sha256 and bytes for every file.

## Settings (config_used.json)

Identical for both seeds except the seed:

- seed: 20261103 and 20261104
- fp_bits 2048, max_peaks 96, min_peaks 3
- width 192, heads 6, layers 3, embedding 192, dropout 0.1
- temperature 0.1, aux_weight 0.5, fp_score_weight 2.0
- batch_size 96, hard_negatives 16, negative_pool 128
- epochs 80 (maximum), steps_per_epoch 500, patience 4
- lr 0.0002, weight_decay 0.01
- val_fraction 0.1, val_candidates 256, max_validation_molecules 1000
- holdout_hours 5.0, refit_hours 6.0, refit_full true, require_gpu true

Early stopping ended the holdout phase at epoch 61 (best epoch 57) for seed 20261103, and at epoch 66 (best epoch 62) for seed 20261104. The full-data refit then ran 57 and 62 epochs respectively.

## Loading example

Copy inference.py from the Saner v1 kit into the seed folder. It reads config.json, so copy config_used.json to config.json first.

```python
import sys, shutil
from pathlib import Path
BUNDLE = Path("seed_20261103")  # folder holding model.py, features.py, inference.py, final_model.pt
shutil.copy(BUNDLE / "config_used.json", BUNDLE / "config.json")
sys.path.insert(0, str(BUNDLE))
from inference import Scorer
scorer = Scorer(str(BUNDLE))
spectrum = {"mzs": [121.03, 149.02, 205.10], "intensities": [0.4, 1.0, 0.7], "precursor_mz": 301.1,
            "adduct": "[M+H]+", "ionization_mode": "positive", "collision_energy": [20]}
print(scorer.score_candidates([spectrum], ["CCO", "CC(=O)O"]))  # larger = better
```

## Holdout diagnostics (optimistic)

- seed 20261103: best diagnostic MRR@25 = 0.641 (epoch 57)
- seed 20261104: best diagnostic MRR@25 = 0.655 (epoch 62)

Caveat: the best epoch was selected on the same holdout these numbers are reported on, so they are optimistic. The diagnostic is also not leaderboard MRR: the true structure is guaranteed to be in a limited candidate set. final_model.pt was refit on full data including the former holdout identities, so its holdout performance is not measured; do not evaluate it on that holdout.

## Measured result (plain statement)

A private run of the flagship pipeline with these two seeds attached scored 0.479 on the public leaderboard (submission 57987166). Our earlier credited two-scorer reproduction scored 0.480 (submission 57922509). The difference is within noise, and we do not claim the seeds improve the score.

## Why publish them

As of 2026-11-04 the public training kernel bgunshui/casmi26-scorer-train-public can no longer be attached as an input on Kaggle. Notebooks that relied on its output cannot rerun that path. These seeds provide a public, reproducible self-trained scorer trained with the same recipe, so the two-model z-score ensemble can still be run.

## Licence

CC BY-NC-SA 4.0. Non-commercial use only. These models are derived from competition data (enveda CASMI26), so keep attribution, the non-commercial restriction and share-alike on any derivative.
