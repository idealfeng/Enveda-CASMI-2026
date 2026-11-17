# Offline champion funnel evaluator

Run only after a replay has finished successfully. This command does not run any
models or submit to Kaggle. Use the existing WSL Python environment containing
the pinned official RDKit 2026.03.3. All inputs and new outputs stay on D.

```bash
python scripts/evaluate_champion_funnel_20261115.py \
  --run-root runs/champion_error_decomposition_20261115/canary_class2_r2 \
  --output reports/champion_error_decomposition_20261115/canary_class2_r2_funnel
```

The example run name is a placeholder until its `verification.json` reports
`completed_original_champion_with_diagnostic_reference_masks`. Failed runs,
missing completion receipts, source/configuration mismatches, incomplete outer
cell coverage, failed original audits, and final prediction SHA mismatches are
rejected. An existing output directory is rejected; preserve prior results.

The evaluator verifies executed source snapshots, original audits and the actual
final AB output SHA. It then seals prediction, trace and source hashes into
`prediction_bindings_before_labels.json` BEFORE opening the fixed old48 truth.
Hashes are checked again after evaluation. Original replay receipts bind source
snapshots, event counts and final CSV; individual trace bytes are first sealed by
this offline evaluator, so the evidence does not claim an earlier trace signature.

Outputs:

- `stages_per_query.csv`: observed truth presence, position/rank, source, scope,
  stage coverage, and reciprocal rank where the original order has meaning.
- `query_summary.csv`: E1all, E2all and PCreturned coverage, raw/accepted
  generation coverage, merged-list loss/recovery transitions, and final rank.
- `verification.json`: exact input bindings, stage statistics and final local
  MRR@25/top1, with scope and inference limitations.
- `failure.json`: retained if a later offline integrity/evaluation check fails.

See [source_stage_map.md](source_stage_map.md) and its JSON companion for exact
champion pins and stage definitions. Inner final25 is not the complete champion:
outer MASS, guarded head and AB final output remain required.

`candidate_recall_known` is an observed viable-candidate lower bound. A missing
truth in PCreturned does not establish absence from PubChem's raw catalog or mass
window. Unobserved raw PC recall stays unknown. First absence in one channel is
not a complete recall failure; late channels and postprocessing can recover truth.
Raw-generation enumeration positions are not interpreted as model ranks. Invalid
SMILES and duplicate identities retain their original submitted rank positions.

Class1/2/3 here are artificial reference/candidate conditions on old training-derived
diagnostics. Runtime installation completion is not independent isolation approval.
The evaluator reports an observation funnel, not a validated class-wise mechanism
or generalization claim. In particular, a one-query canary supplies path evidence;
it does not estimate gains, hidden class proportions or a new Kaggle score.
