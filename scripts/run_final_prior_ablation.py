"""Replay the pinned final layer on cached diagnostic outputs; change POP_W only."""
from pathlib import Path
from functools import lru_cache
import argparse
import ast
import glob
import hashlib
import json
import os
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
ORIGINAL_SHA = '0ebc86ad851fe7051e592fb268756e686ee21b9ddbe90012335096a349bd2769'
MANIFEST_SHA = '8e1ab36f2d8b7f800aa88baf845c0ffdc3790d36bdcabbb6d465ace05a571b09'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def cell_source(cell):
    value = cell['source']
    return ''.join(value) if isinstance(value, list) else value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-root', type=Path, default=ROOT/'runs/validation_flex_c2_20261105d')
    parser.add_argument('--output', type=Path, default=ROOT/'runs/exp002_final_pop_prior_20261106')
    args = parser.parse_args()
    run, output = args.run_root.resolve(), args.output.resolve()
    if not run.is_relative_to(ROOT) or not output.is_relative_to(ROOT) or output == run:
        parser.error('Use separate directories inside the D: workspace')
    if output.exists():
        parser.error('A new experiment directory is required; preserve previous evidence')
    import numpy as np
    import pandas as pd
    from validation import metric
    from validation.evaluate import evaluate_frames, audit_fixed_candidates, paired_bootstrap, validate_truth
    metric.assert_official_rdkit()
    started = time.monotonic()
    original = ROOT/'third_party/flexonafft_evidence_gap/v56/original.ipynb'
    manifest_path = ROOT/'runs/validation_pilot_v2_20261104/manifest.json'
    if sha(original) != ORIGINAL_SHA or sha(manifest_path) != MANIFEST_SHA:
        raise ValueError('Pinned source or frozen diagnostic cohort changed')
    notebook, manifest = read(original), read(manifest_path)
    config, receipt = read(run/'validation_config.json'), read(run/'validation_run_receipt.json')
    if receipt['status'] != 'complete' or config != receipt['config'] or config['pipeline'] != 'flex':
        raise ValueError('Expected the completed, bound Flex diagnostic run')
    if read(run/'validation_runtime_audit.json')['status'] != 'passed':
        raise ValueError('Original run isolation audit failed')
    replay_tree = ast.parse(cell_source(notebook['cells'][17]))
    definitions = [node for node in replay_tree.body if isinstance(node, ast.FunctionDef)]
    if {node.name for node in definitions} != {'_fl_sha', '_fl_prior', '_final_layer'}:
        raise ValueError('Unexpected final-layer definitions')
    replay_code = compile(ast.Module(body=definitions, type_ignores=[]), 'original-v56-cell17-functions', 'exec')
    config_tree = ast.parse(cell_source(notebook['cells'][1]))
    if any(not isinstance(node, ast.Assign) for node in config_tree.body):
        raise ValueError('Unexpected configuration statements')
    config_code = compile(config_tree, 'original-v56-cell1-configuration', 'exec')
    sources = {name: run/name for name in ('submission.csv', 'submission_before_final_layer.csv',
        'variants/submission_CUSTOM.csv', 'neural_candidate_features.parquet', 'outsider_neural_features.parquet')}
    before_hashes = {name: sha(path) for name, path in sources.items()}
    expected = pd.read_csv(sources['submission.csv'], dtype=str, keep_default_na=False)
    expected_ids = expected.molecule_id.tolist()
    if len(expected_ids) != 48 or set(expected_ids) != set(config['active_ids']):
        raise ValueError('Unexpected diagnostic query set')
    output.mkdir(parents=True)
    predictions, replay_reports, elapsed = {}, {}, {}
    for arm in ('control', 'pop_zero'):
        arm_root = output/arm
        (arm_root/'variants').mkdir(parents=True)
        shutil.copy2(sources['submission_before_final_layer.csv'], arm_root/'submission.csv')
        for name in ('variants/submission_CUSTOM.csv', 'neural_candidate_features.parquet', 'outsider_neural_features.parquet'):
            shutil.copy2(sources[name], arm_root/name)
        scope = dict(Path=Path, os=os, glob=glob, json=json, hashlib=hashlib, lru_cache=lru_cache,
            np=np, pd=pd, ROOT=arm_root, INPUT=run/'input_view', SAMPLE_IDS=expected_ids,
            identity_map=lambda: {})
        exec(config_code, scope)
        if arm == 'pop_zero':
            scope['POP_W'] = 0.0
        exec(replay_code, scope)
        arm_started = time.monotonic()
        replay_reports[arm] = scope['_final_layer']()
        elapsed[arm] = time.monotonic() - arm_started
        if replay_reports[arm]['status'] != 'applied':
            raise ValueError('Final layer was not applied')
        predictions[arm] = pd.read_csv(arm_root/'submission.csv', dtype=str, keep_default_na=False)
        if arm == 'control' and sha(arm_root/'submission.csv') != before_hashes['submission.csv']:
            raise ValueError('Unchanged source replay did not reproduce the original final CSV byte-for-byte')
    # Check invariants before reading/evaluating truth labels.
    for mid, baseline, current in zip(expected_ids, predictions['control'].smiles, predictions['pop_zero'].smiles):
        if metric.candidate_identity_set(baseline) != metric.candidate_identity_set(current):
            raise ValueError('Candidate identity set changed: ' + mid)
        if baseline.split(';')[0] != current.split(';')[0]:
            raise ValueError('Top1 changed: ' + mid)
    for name, digest in manifest['artifact_sha256'].items():
        path = (manifest_path.parent/name).resolve()
        if not path.is_relative_to(manifest_path.parent) or sha(path) != digest:
            raise ValueError('Frozen diagnostic artifact changed')
    truth = validate_truth(pd.read_parquet(manifest_path.parent/manifest['truth_parquet_file']))
    locked = {item['official_identity'] for item in read(manifest_path.parent/manifest['splits_file'])['cross_final_locked']}
    if set(truth.identity) & locked:
        raise ValueError('Locked final identity entered evaluation')
    metrics = {arm: evaluate_frames(truth, frame) for arm, frame in predictions.items()}
    current, control = metrics['pop_zero'], metrics['control']
    pairs = paired_bootstrap(current['rows'], control['rows'], resamples=2000, seed=20261106)
    panel_by_id = truth.set_index('molecule_id').panel.to_dict()
    per_panel = {str(panel): paired_bootstrap(
        [r for r in current['rows'] if panel_by_id[r['molecule_id']] == panel],
        [r for r in control['rows'] if panel_by_id[r['molecule_id']] == panel], 2000, 20261106)
        for panel in truth.panel.drop_duplicates()}
    baseline_by_id = {r['molecule_id']: r for r in control['rows']}
    rows = []
    for row in current['rows']:
        previous = baseline_by_id[row['molecule_id']]
        rows.append(dict(molecule_id=row['molecule_id'], panel=panel_by_id[row['molecule_id']],
            rank_control=previous['rank'], rank_pop_zero=row['rank'],
            rr_delta=row['mrr_at_25']-previous['mrr_at_25'],
            same_formula_rank_control=previous['truth_formula_only_rank'],
            same_formula_rank_pop_zero=row['truth_formula_only_rank']))
    if before_hashes != {name: sha(path) for name, path in sources.items()}:
        raise ValueError('Immutable original outputs changed')
    report = dict(status='complete', experiment='EXP002', original_source_sha256=ORIGINAL_SHA,
        manifest_sha256=MANIFEST_SHA, only_changed_configuration=dict(POP_W=[0.10, 0.0]),
        control_reproduces_original_csv_exactly=True, top1_fixed=True,
        fixed_candidates=audit_fixed_candidates(truth, predictions['pop_zero'], predictions['control']),
        control_metrics=control['metrics'], treatment_metrics=current['metrics'],
        control_subsets=control['subsets'], treatment_subsets=current['subsets'],
        paired_bootstrap=pairs, paired_bootstrap_by_panel=per_panel,
        changed_truth_ranks=[r for r in rows if r['rank_control'] != r['rank_pop_zero']],
        replay_reports=replay_reports, input_sha256=before_hashes, seconds_by_arm=elapsed,
        elapsed_seconds=time.monotonic()-started, locked_final_evaluated=False,
        new_inference_training_download_or_submission=False,
        identity_mapping='Fresh official RDKit identity; control CSV exact replay proves equivalence on these inputs.',
        scope='Reference-isolated diagnostic with known pretrained exposure; not independent generalization CV.')
    (output/'report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    pd.DataFrame(rows).to_csv(output/'per_molecule.csv', index=False)
    print(json.dumps({key: report[key] for key in ('status','control_metrics','treatment_metrics',
        'changed_truth_ranks','paired_bootstrap','elapsed_seconds')}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
