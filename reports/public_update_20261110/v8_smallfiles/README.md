# CASMI26 scorer v8 (ours — width 384 / 4 layers / hard negatives)

Diagnostic MRR@25 = 0.6756 on the standard 8h holdout — the best of our models
(v7 0.6672, v5 0.6484, v2h 0.6486, v2 0.6603 on a different 5h split).

* final_model.pt — full refit, best epoch 120 of 140
* config_used.json — LOAD-CRITICAL architecture: 384 / 12 / 4 / 384
* model.py, features.py — kit files it was trained with
