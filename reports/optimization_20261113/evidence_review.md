# 2026-11-13: actual-stage cross-CE evidence replay

**Decision: do not spend today's Kaggle slot on this protected-top1 CE-tail treatment.** The fixed coefficient changed nine real cached query orderings, but changed no true-answer ranks. This is a negative result for this precise treatment, not proof that every cross-spectrum ranking model is useless.

## Result and scope

| Item | Result |
|---|---:|
| Original E004 metric-fusion rows reconstructed exactly | 45 / 45 |
| Queries satisfying the complete common-CE gate on the actual fusion competition set | 10 / 45 |
| Query orderings changed | 9 / 45 |
| Old panel stage MRR@25, control | 0.8478835978835979 |
| Old panel stage MRR@25, fixed treatment | 0.8478835978835979 |
| Paired MRR@25 delta | 0 |
| Original top1 / candidate set preserved | 45 / 45 |

The primary artifacts are [summary.json](evidence_replay_v2/summary.json), [stage_audit.json](evidence_replay_v2/stage_audit.json), [stage_predictions.json](evidence_replay_v2/stage_predictions.json), and [candidate_evidence_features.jsonl](evidence_replay_v2/candidate_evidence_features.jsonl). The executable replay is [evidence_replay_20261113.py](../../scripts/evidence_replay_20261113.py).

The input is the already exposed 45-query H+ subset of the old Flex validation cache. It is **not** a fresh validation split, hidden-test result, or complete rerun of the current .488 champion. The later physical, MASS, neural-head and external-library overlays were not rerun. This work neither retrained a model nor reran produre1/2.

## Frozen treatment

This implements the already documented EXP003 mechanism at weight **0.10**, without a coefficient search. Reconstruct the original 40-candidate metric-identity fusion and the original same-formula GLACIER z-score rerank first. From the observed per-spectrum scores, compute pairwise candidate support within real, finite, distinct collision-energy buckets. Exact duplicate spectra count once. Unknown/mixed CE and incomparable adduct/instrument/units strata do not create independent observations. All candidates in the actual formula group must share at least two usable CE buckets; a missing candidate score stays unobserved.

For each formula group, add `0.10 * centered_pairwise_support` to its original full-group fusion score. Preserve the original top1 and candidate set; only the original ranks 2–25 sharing the control leader's formula can move. The coefficient-zero reconstruction must exactly reproduce the original ordering. Predictions and policy were written before evaluation labels were read.

The older information-only audit had 14 eligible queries over the runner's wider candidate lists. Eligibility here drops to 10 because the exact metric-fusion competition set is different. Using the older 14-query count as a production coverage claim would be incorrect.

## Interpretation

The gate exposes real information: nine actual rankings change. It does not supply measured benefit under the protected-top1 scope. Eight of the ten eligible queries already have the answer at rank 1; the remaining two have rank-2 answers which this fixed perturbation also leaves at rank 2. That is a diagnostic observation after the fixed treatment, not a rule for selecting future queries from truth.

Allowing difficult-query top1 changes would be a different, riskier experiment and needs its own policy. The current result cannot be advertised as an evaluation of that scope. In particular, neither increasing the coefficient until the two exposed errors move nor routing using those query IDs would be acceptable evidence.

## Implementation and provenance

The original frozen notebook's `metric_fusion`, identity helpers and nested `rerank_row` function were extracted by AST and executed without the notebook's drivers. The original `gl_fuse.py` and ICE fuse modules remain authoritative. The original official-2026 identity sidecar is used only as a verified memo table; unknown SMILES still use the original identity code. All 45 saved E004 final rows must match before a treatment is evaluated. Actual score events are reused; no score is inferred from final rank.

The replay reads `runs/validation_flex_c2_20261105d/e004_candidate_inputs.json`, the original ICE/GL outputs and original reference/control submissions. Per-spectrum evidence comes from `runs/exp003_gl_trace_full_20261106/trace/per_spectrum.jsonl`, whose observer replay previously preserved the original aggregate GL output byte for byte. File hashes are recorded in `evidence_replay_v2/provenance.json`.

The first replay attempt was interrupted before any predictions or evaluation were written because it repeated slow tautomer canonicalization. Its original policy remains in `evidence_replay/frozen_policy.json`. Version 2 uses the verified identity memo and completed without altering the policy. No GPU, large-library load, Kaggle write, or central ledger mutation was performed.

## Remaining deployment gap

No Kaggle production wrapper is prepared for this candidate because the fixed actual-stage comparison shows zero measured benefit. If this route is revisited with a distinct justified objective, production must instrument the actual `run_gl` per-spectrum process, bind those events to the exact subsequent `rerank_multi` call and candidates, preserve the original mean GL score, then run the complete .488 pipeline. The old trace alone cannot bind a replacement score to the full current champion. Same-formula CE evidence also does not create any missing Class-3 structure.
