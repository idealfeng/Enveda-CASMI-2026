# Guarded late ranker preparation, 2026-11-09

All four prepared branches preserve every pre-tail notebook cell from the exact
own 0.482 source (`6de37bec32c8aa8bfb46b2c5e94e374b53fe36137dff1cd7d1c4a295359f56fe`).
Only the final late module and observer differ. No cloud call or submission was
performed by this builder task. No full-day manifest has been assembled by it.

| Prepared branch | Change versus the 0.482 recipe | Notebook SHA-256 |
|---|---|---|
| mass_guarded_oldhead_p3 | Same frozen two heads, protect ranks 1–3 | 1c8eacbd07c1282a2114d558a39a4ad4cf404b5833e8412ae0c51d7fe1ad027f |
| mass_guarded_oldhead_p1 | Same frozen two heads, protect rank 1; spare, not selected for today's final five | 1180cec3c0f6676775066c3a72eefe97b8869eeeabab072b3bd16699e288069c |
| mass_guarded_v2mean_p7 | Replace the trained-head signal with the original frozen v2 uniform mean, protect ranks 1–7 | aa29969bacf47b437a51bab68b1f146ae17bf62058931129d435f1e1fe27311b |
| mass_guarded_isomer_p7 | New fixed-mean, bounded ±0.5 isomer residual, equal two fixed seeds; protect ranks 1–7 | 0ab4a66896ad364e99fe8db2c234e13dc0622085606313a10fccf5c685b88b23 |

These are separate immutable stages in `submission/optimization_20261109`.
The first two are inference-policy changes, not new training. The v2 mean is a
mechanism ablation of an existing public model. The isomer source and weights
are newly trained project assets; its data/encoder exposure limits remain.

The new guard accepts an explicit protected prefix and scorer configuration.
Candidate multiplicities, official metric identities, query order and every
tail formula slot remain exact. Invalid identities, duplicate identities and
queries lacking usable spectra retain their original predictions. Global
model/source/control mismatches remove the final CSV and preserve the control.

The observer independently reads the actual input/output files, checks source
and checkpoint pins, then reconstructs the selected same-formula ordering from
the actual scored candidate table and compares it with the submitted CSV. The
v2 mean adapter calls the exact original scorer and declares `head_applied=false`.

Validation: 20 actual function/observer fixture checks per branch (80 total),
including wrong prefix, candidates, formula exchanges, consumed score order,
configuration, role, coverage and source rejection. Each branch also executed
its exact staged last two cells on three real queries, 36 original spectra and
75 candidate rows. All four invoked their actual scorer CLI, changed three
query tails and passed the runtime and observer checks. This validates the
interface and guards, not leaderboard efficacy or clean generalization.

Evidence: `reports/guarded_batch_review_20261109/verification.json`,
`reports/guarded_batch_actual_canary_20261109.json`, and
`runs/guarded_batch_actual_canary_20261109/<branch>/verification.json`.

Tools: `scripts/build_guarded_batch_20261109.py`,
`scripts/guarded_head_tail_20261109.py`,
`scripts/guarded_v2_mean_score_20261109.py`,
`scripts/review_guarded_batch_20261109.py`,
`scripts/canary_guarded_batch_20261109.py`.

Builder CLI supports `--branch NAME --prefix N --scorer learned_heads|v2_mean`
and optional `--head-spec PATH`. `--assemble-manifest NAME ...` is explicit,
exclusive, bounded to five and includes the required competition field. Root
owns the final selection/manifest and every external action.
