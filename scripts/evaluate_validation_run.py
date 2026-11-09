"""Evaluate one completed diagnostic run and fixed-candidate Saner ablations."""
from pathlib import Path
import argparse
import hashlib
import json
import sys

WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE))


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--run-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--shape-only', action='store_true', help='Read artifact schemas only; no truth or performance evaluation')
    parser.add_argument('--allow-incomplete', action='store_true', help='Report partial recorded artifacts explicitly; do not claim successful end-to-end validation')
    parser.add_argument('--bootstrap-resamples', type=int, default=2000)
    parser.add_argument('--seed', type=int, default=20261104)
    args = parser.parse_args()
    from validation import metric
    from validation.evaluate import evaluate_frames, paired_bootstrap, audit_fixed_candidates, validate_truth
    from validation.stages import collect_stages, inspect_run_shapes, read_predictions, read_empty_stage_coverage, summarize_stages
    import pandas as pd

    root = args.run_root.resolve(); output = args.output.resolve()
    if not root.is_relative_to(WORKSPACE) or not output.is_relative_to(WORKSPACE):
        raise ValueError('All inputs/outputs must stay in the D-drive workspace')
    output.mkdir(parents=True, exist_ok=True)
    if args.shape_only:
        result = inspect_run_shapes(root)
        (output / 'schema_sanity.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(result, indent=2)); return 0
    if args.manifest is None:
        parser.error('--manifest is required for evaluation')
    metric.assert_official_rdkit()
    manifest_path = args.manifest.resolve()
    manifest = json.loads(manifest_path.read_text(encoding='utf-8')); panel_root = manifest_path.parent
    for name, digest in manifest['artifact_sha256'].items():
        if _sha(panel_root / name) != digest:
            raise ValueError('Frozen dataset artifact changed: ' + name)
    config = json.loads((root / 'validation_config.json').read_text(encoding='utf-8'))
    receipt_path = root / 'validation_run_receipt.json'
    receipt = json.loads(receipt_path.read_text(encoding='utf-8')) if receipt_path.is_file() else {'status': 'missing'}
    if receipt.get('config') != config:
        raise ValueError('Runtime receipt configuration differs from the saved configuration')
    if receipt.get('status') != 'complete' and not args.allow_incomplete:
        raise ValueError('The model run has not completed successfully')
    query_test = root / 'query_comp' / 'test.parquet'
    if _sha(query_test) != config['query_test_sha256']:
        raise ValueError('Inference query artifact changed after configuration')
    current_manifest_sha = _sha(manifest_path)
    ancestor = {revision['previous_manifest_sha256'] for revision in manifest.get('metadata_revisions', [])}
    if config['manifest_sha256'] != current_manifest_sha and config['manifest_sha256'] not in ancestor:
        raise ValueError('Run configuration is not bound to the current manifest or documented metadata-only predecessor')
    truth = validate_truth(pd.read_parquet(panel_root / manifest['truth_parquet_file']))
    expected = set(truth.molecule_id)
    if set(config['active_ids']) != expected or set(manifest['active_ids']) != expected:
        raise ValueError('Run cohort differs from frozen active query IDs')
    frozen = json.loads((panel_root / manifest['splits_file']).read_text(encoding='utf-8'))
    final_locked = {row['official_identity'] for row in frozen['cross_final_locked']}
    if set(truth.identity) & final_locked:
        raise ValueError('Locked final identity entered the active evaluation')
    audit_path = root / 'validation_runtime_audit.json'
    runtime = json.loads(audit_path.read_text(encoding='utf-8')) if audit_path.is_file() else {'status': 'missing'}
    if runtime.get('status') != 'passed' and not args.allow_incomplete:
        raise ValueError('Completed runtime isolation/model-health audit required; --allow-incomplete is only for explicitly partial diagnostics')
    if runtime.get('status') == 'passed' and (runtime.get('processed_molecules') != len(expected) or runtime.get('cohort_policy') != config['cohort_policy']):
        raise ValueError('Runtime audit belongs to a different query cohort/policy')
    predictions = {}; metrics = {}; input_records = []
    files = {'final': root / 'submission.csv', 'baseline0465': root / 'submission_baseline0465.csv'}
    for name in ('V0', 'V1', 'V2', 'V4', 'CUSTOM'):
        files[name] = root / 'variants' / f'submission_{name}.csv'
    for name, path in files.items():
        if path.is_file():
            predictions[name] = read_predictions(path)
            metrics[name] = evaluate_frames(truth, predictions[name])
            input_records.append({'name': name, 'path': str(path), 'sha256': _sha(path)})
    if 'final' not in metrics and not args.allow_incomplete:
        raise ValueError('Missing final predictions')
    ablations = {}
    baseline_integrity = None
    if config['pipeline'] == 'flex':
        required = {'V0', 'V1', 'CUSTOM'}
        if not required <= set(metrics) and not args.allow_incomplete:
            raise ValueError('Missing fixed-candidate variants: ' + str(required - set(metrics)))
        if 'V0' in metrics:
            if 'baseline0465' in metrics:
                baseline_integrity = audit_fixed_candidates(truth, predictions['V0'], predictions['baseline0465'])
                baseline_keys = {row['molecule_id']: row['candidate_identities'] for row in metrics['baseline0465']['rows']}
                same_order = all(row['candidate_identities'] == baseline_keys[row['molecule_id']] for row in metrics['V0']['rows'])
                baseline_integrity['same_official_identity_order'] = same_order
                if not baseline_integrity['equal'] or not same_order:
                    raise ValueError('V0 is not the unchanged frozen baseline; reject the fixed-candidate experiment')
            for name in ('V1', 'CUSTOM'):
                if name not in metrics:
                    continue
                fixed = audit_fixed_candidates(truth, predictions[name], predictions['V0'])
                if not fixed['equal']:
                    raise ValueError('Fixed-candidate ablation rejected; official identity sets differ for ' + name)
                result = {'fixed_candidate_audit': fixed,
                          'paired_bootstrap': paired_bootstrap(metrics[name]['rows'], metrics['V0']['rows'], args.bootstrap_resamples, args.seed)}
                if 'panel' in truth:
                    panel_by_id = truth.set_index('molecule_id').panel.to_dict()
                    result['paired_bootstrap_by_panel'] = {str(panel): paired_bootstrap(
                        [row for row in metrics[name]['rows'] if panel_by_id[row['molecule_id']] == panel],
                        [row for row in metrics['V0']['rows'] if panel_by_id[row['molecule_id']] == panel], args.bootstrap_resamples, args.seed)
                        for panel in truth.panel.drop_duplicates()}
                ablations[name + '_vs_V0'] = result
    candidates, stage_inputs = collect_stages(root, expected)
    for item in stage_inputs:
        item['sha256'] = _sha(item['path'])
    explicit_empty, empty_audit = read_empty_stage_coverage(root, expected, candidates)
    if empty_audit is not None:
        empty_audit['sha256'] = _sha(empty_audit['path'])
    stage_report = summarize_stages(truth, candidates, metrics.get('final', {}).get('rows'), explicit_empty)
    pd.DataFrame(stage_report['summaries']).to_csv(output / 'candidate_stage_summary.csv', index=False)
    pd.DataFrame(stage_report['transitions']).to_csv(output / 'candidate_stage_transitions.csv', index=False)
    pd.DataFrame(stage_report['rows']).to_parquet(output / 'candidate_stage_per_molecule.parquet', index=False)
    if not candidates.empty:
        candidates.to_parquet(output / 'materialized_candidate_identities.parquet', index=False)
    report = {'status': 'complete_diagnostic' if runtime.get('status') == 'passed' and receipt.get('status') == 'complete' else 'partial_diagnostic',
              'scope': manifest['validation_status'], 'clean_generalization_or_hidden_score_claimed': False,
              'metric_rdkit': metric.assert_official_rdkit(), 'official_source_sha256': metric.OFFICIAL_SOURCE_SHA256,
              'manifest': str(manifest_path), 'manifest_sha256': current_manifest_sha,
              'run_manifest_sha256': config['manifest_sha256'], 'metadata_only_predecessor_binding': config['manifest_sha256'] != current_manifest_sha,
              'split_sha256': manifest['split_sha256'], 'runtime_audit': runtime,
              'run_receipt_status': receipt.get('status'),
              'implementation_sha256': {str(path.relative_to(WORKSPACE)): _sha(path) for path in [WORKSPACE / 'validation/metric.py', WORKSPACE / 'validation/evaluate.py', WORKSPACE / 'validation/stages.py', Path(__file__).resolve()]},
              'training_exposure': manifest['training_exposure'], 'cohort_policy': config['cohort_policy'],
              'pipeline': config['pipeline'],
              'component_applicability': {'FPNet_full1': True,
                  'Saner_final_model': config['pipeline'] == 'flex',
                  'fold0_FPNet': config['pipeline'] == 'flex',
                  'other_public_models_rankers': 'Applies to the remaining components actually loaded by this pipeline; exact membership unknown.'},
              'final_locked_evaluated': False, 'final_locked_active_intersection': 0,
              'inputs': input_records, 'stage_inputs': stage_inputs, 'predictions': metrics,
              'fixed_candidate_baseline_integrity': baseline_integrity,
              'empty_candidate_audit': empty_audit,
              'fixed_candidate_ablations': ablations, 'candidate_stages': stage_report,
              'limitations': ['This training-derived pilot has known pretrained target exposure; reference isolation is a diagnostic only.',
                  'Small developer panels and paired bootstrap do not establish medal performance.',
                  'Candidate-stage recall is scoped to materialized observations; absent rows are unknown and PubChem full-window recall was not measured.']}
    (output / 'evaluation_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    for name, result in metrics.items():
        pd.DataFrame([{key: value for key, value in row.items() if key != 'candidate_identities'} for row in result['rows']]).to_csv(output / f'metrics_{name}_per_molecule.csv', index=False)
    print(json.dumps({'status': report['status'], 'scope': report['scope'], 'metrics': {name: result['metrics'] for name, result in metrics.items()},
                      'stage_files': len(stage_inputs), 'ablations': list(ablations)}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
