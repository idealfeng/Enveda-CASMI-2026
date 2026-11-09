# CASMI26 private spectrum->structure scorer (ours, v4)

Wider model: width 256 / 8 heads / 3 layers, trained with the public training kit
(`sanpier/casmi-spectrum-model-v1`), 120 epochs, early stop at 109.

* final_model.pt      - checkpoint (full refit)
* config_used.json    - training config
* training_result.json- diagnostics

Self-built validation diagnostic MRR@25 = 0.7243 (v2 = 0.6603, public kit baseline = 0.4844).

**config_used.json is load-critical**: the kit's `model.py` reads `width/heads/layers/embedding`
from it. For v4 these must be `256 / 8 / 3 / 256` (the checkpoint is width 256; the earlier
file carried the kit default 192 and was fixed on 2026-11-02, verified with a strict
`load_state_dict`). Keep the file exactly as shipped.

Use together with the kit's model.py / features.py. Recommended: ENSEMBLE its z-scored neural
scores with the public model (0.5/0.5, or 0.5 public + 0.25 v2 + 0.25 v4 for three-way);
pure replacement of the public scorer scored 0.460 on the public leaderboard.
