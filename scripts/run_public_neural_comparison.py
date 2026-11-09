"""Compare pinned public/dual/tri scorers on one frozen candidate set; no submissions."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import ast
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
ORIGINAL_SHA = '0ebc86ad851fe7051e592fb268756e686ee21b9ddbe90012335096a349bd2769'
MANIFEST_SHA = '8e1ab36f2d8b7f800aa88baf845c0ffdc3790d36bdcabbb6d465ace05a571b09'
CHECKPOINTS = {
    'public': '44436b2daec64373e66f9120dd2389c24fc83dd9430ebeeac18e3cb49dcb9642',
    'v2': 'c08d2101154d057890de088be63834eb622468892a3b842512fdc5a65e02ff46',
    'v4': '10565a0d8c2c1cc903882ff7ba2a9b7b994ae169228bf0c9b6c4ae055ff4ec51',
}
ARMS = {'public': {'public': 1.0}, 'dual': {'public': .5, 'v2': .5},
        'tri': {'public': .5, 'v2': .25, 'v4': .25}}
SCORER_OUTPUT_COLUMNS = ('neural_ok', 'neural_score', 'neural_cos', 'neural_fp',
                         'neural_std', 'n_spectra', 'n_adducts')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def save(path, value):
    temp = path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')
    temp.replace(path)


def align_frame(reference, current, core_columns):
    """Reject missing/duplicate candidates and changed upstream evidence before alignment."""
    import numpy as np
    import pandas as pd
    keys = ['molecule_id', 'smiles']
    for frame in (reference, current):
        if frame.duplicated(keys).any() or frame[keys].isna().any().any():
            raise ValueError('Duplicate or missing candidate identity keys')
    first, second = reference.set_index(keys), current.set_index(keys)
    if len(first) != len(second) or set(first.index) != set(second.index):
        raise ValueError('Scorers evaluated different candidate rows')
    second = second.reindex(first.index)
    columns = [c for c in core_columns if c not in keys]
    if not second.neural_ok.eq(True).all() or not second.processed.eq(True).all():
        raise ValueError('Missing model coverage or inactive query: fallback is forbidden')
    pd.testing.assert_frame_equal(first[columns], second[columns], check_dtype=False, check_exact=True)
    values = pd.to_numeric(second.neural_score, errors='coerce').to_numpy(dtype=float)
    if not np.isfinite(values).all() or not (second.n_spectra > 0).all():
        raise ValueError('Nonfinite scores or no usable spectra')
    return second.reset_index()


def query_zscore(frame):
    import numpy as np
    score = frame.neural_score.astype(float)
    groups = score.groupby(frame.molecule_id, sort=False)
    scale = groups.transform(lambda x: x.std(ddof=0)).clip(lower=1e-6)
    result = (score-groups.transform('mean'))/scale
    if not np.isfinite(result.to_numpy()).all():
        raise ValueError('Nonfinite per-query normalized scores')
    return result


def pinned_modules(original):
    notebook = read(original)
    source = notebook['cells'][8]['source']
    source = ''.join(source) if isinstance(source, list) else source
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'MODULE_SHA256' for t in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError('Original helper pins not found')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-root', type=Path, default=ROOT/'runs/validation_flex_c2_20261105d')
    parser.add_argument('--output', type=Path, default=ROOT/'runs/exp004_public_neural_20261106')
    parser.add_argument('--device', choices=('cuda', 'cpu'), default='cuda')
    args = parser.parse_args()
    run, output = args.run_root.resolve(), args.output.resolve()
    if not run.is_relative_to(ROOT) or not output.is_relative_to(ROOT) or output == ROOT or output == run:
        parser.error('Use separate paths inside the D: workspace')
    if output.exists():
        parser.error('A fresh output directory is required; do not overwrite experiment evidence')
    import numpy as np
    import pandas as pd
    from validation import metric
    from validation.evaluate import evaluate_frames, audit_fixed_candidates, paired_bootstrap, validate_truth
    metric.assert_official_rdkit()
    started = time.monotonic()
    original = ROOT/'third_party/flexonafft_evidence_gap/v56/original.ipynb'
    manifest_path = ROOT/'runs/validation_pilot_v2_20261104/manifest.json'
    if sha(original) != ORIGINAL_SHA or sha(manifest_path) != MANIFEST_SHA:
        raise ValueError('Pinned source or frozen diagnostic manifest changed')
    manifest, config, receipt = read(manifest_path), read(run/'validation_config.json'), read(run/'validation_run_receipt.json')
    if receipt['status'] != 'complete' or config != receipt['config'] or config['pipeline'] != 'flex':
        raise ValueError('Expected a completed and bound Flex control run')
    if read(run/'validation_runtime_audit.json')['status'] != 'passed':
        raise ValueError('Original isolation audit did not pass')
    for name, expected in manifest['artifact_sha256'].items():
        path = (manifest_path.parent/name).resolve()
        if not path.is_relative_to(manifest_path.parent) or sha(path) != expected:
            raise ValueError('Frozen diagnostic artifact changed')
    helpers = ROOT/'third_party/flexonafft_evidence_gap/v56/embedded'
    module_pins = pinned_modules(original)
    for name in ('neural_scores.py', 'consensus.py', 'ranking.py'):
        if sha(helpers/name) != module_pins[name]:
            raise ValueError('Pinned original helper changed: ' + name)
    sources = {name: run/name for name in ('frozen_candidate_evidence.parquet', 'effective_query_spectra.parquet',
        'neural_candidate_features.parquet', 'submission_baseline0465.csv', 'variants/submission_CUSTOM.csv')}
    input_hashes = {name: sha(path) for name, path in sources.items()}
    evidence = pd.read_parquet(sources['frozen_candidate_evidence.parquet'])
    public = pd.read_parquet(sources['neural_candidate_features.parquet'])
    queries = pd.read_parquet(sources['effective_query_spectra.parquet'])
    expected_ids = set(config['active_ids'])
    if len(expected_ids) != 48 or set(evidence.molecule_id) != expected_ids or set(queries.molecule_id) != expected_ids:
        raise ValueError('Unexpected frozen query cohort')
    core_columns = [c for c in evidence.columns if c not in SCORER_OUTPUT_COLUMNS]
    # Compare cached public evidence with the frozen model input as well as new arms.
    public = align_frame(public, public, core_columns)
    pd.testing.assert_frame_equal(evidence.set_index(['molecule_id','smiles'])[ [c for c in core_columns if c not in ('molecule_id','smiles')] ],
        public.set_index(['molecule_id','smiles']).reindex(pd.MultiIndex.from_frame(evidence[['molecule_id','smiles']]))[
            [c for c in core_columns if c not in ('molecule_id','smiles')]], check_dtype=False, check_exact=True)
    bundles = {'public': ROOT/'assets/kaggle/sanpier/casmi-spectrum-model-v1/v1/casmi_spectrum_model_v1',
        'v2': ROOT/'assets/kaggle/bgunshui/casmi26-scorer-v2-model/v1',
        'v4': ROOT/'assets/kaggle/bgunshui/casmi26-scorer-v4-model/v1'}
    model_records = {}
    for name, bundle in bundles.items():
        if sha(bundle/'final_model.pt') != CHECKPOINTS[name]:
            raise ValueError('Unexpected or duplicate checkpoint: ' + name)
        if name != 'public':
            for filename in ('model.py', 'features.py', 'config.json'):
                if sha(bundle/filename) != read(bundle/(filename+'.receipt.json'))['sha256']:
                    raise ValueError('New scorer code/config changed')
        model_records[name] = dict(path=str(bundle.relative_to(ROOT)), checkpoint_sha256=CHECKPOINTS[name],
                                  configuration=read(bundle/'config.json'))
    for name in ('v2', 'v4'):
        for key in ('fp_bits', 'max_peaks', 'min_peaks'):
            if model_records[name]['configuration'][key] != model_records['public']['configuration'][key]:
                raise ValueError('Query/structure preprocessing configuration changed: ' + key)
        if sha(bundles[name]/'features.py') != sha(bundles['public']/'features.py'):
            raise ValueError('Query/structure preprocessing code changed')
    if len(set(CHECKPOINTS.values())) != 3:
        raise ValueError('Three distinct model checkpoints required')
    output.mkdir(parents=True)
    state = dict(status='running', experiment='EXP004', started_at_utc=datetime.now(timezone.utc).isoformat(),
        arms=ARMS, frozen_input_sha256=input_hashes, models=model_records, scoring_results={})
    save(output/'receipt.json', state)
    frames = {'public': public}
    try:
        for name in ('v2', 'v4'):
            path = output/(name+'_features.parquet')
            command = [sys.executable, str(helpers/'neural_scores.py'), str(bundles[name]), 'final_model.pt',
                       str(sources['frozen_candidate_evidence.parquet']), str(sources['effective_query_spectra.parquet']),
                       str(path), args.device]
            stage_started = time.monotonic()
            with (output/(name+'.log')).open('w') as log:
                result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=False)
            if result.returncode != 0:
                raise RuntimeError('Scorer failed; inspect the local log: ' + name)
            if read(Path(str(path)+'.errors.json')):
                raise ValueError('Scorer input failure: ' + name)
            frames[name] = align_frame(public, pd.read_parquet(path), core_columns)
            for column in ('n_spectra', 'n_adducts'):
                if not np.array_equal(frames[name][column].to_numpy(), public[column].to_numpy()):
                    raise ValueError('Observed query coverage differs from public control: ' + column)
            state['scoring_results'][name] = dict(seconds=time.monotonic()-stage_started,
                rows=len(frames[name]), queries=frames[name].molecule_id.nunique(), all_neural_ok=True,
                sha256=sha(path), fallback_used=False)
            save(output/'receipt.json', state)
            print(json.dumps(dict(stage=name, status='scored', **state['scoring_results'][name])), flush=True)
        sys.path.insert(0, str(helpers))
        spec = importlib.util.spec_from_file_location('_casmi_exp004_consensus', helpers/'consensus.py')
        consensus = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(consensus)
        prediction_paths = {}
        normalized = {name: query_zscore(frame) for name, frame in frames.items()}
        for arm, weights in ARMS.items():
            arm_root = output/arm
            arm_root.mkdir()
            combined = public.copy()
            if arm != 'public':
                combined['neural_score'] = sum(weight*normalized[name] for name, weight in weights.items())
            evidence_path = arm_root/'features.parquet'
            combined.to_parquet(evidence_path, index=False)
            reports, _ = consensus.build_variants(evidence_path, sources['submission_baseline0465.csv'], arm_root,
                {'CUSTOM': dict(w_top=.25, w_mid=.75, rescue=0, label='EXP004 fixed-candidate neural comparison')}, 3.0)
            if reports['CUSTOM']['active_rows'] != 48 or reports['CUSTOM']['rescued'] != 0:
                raise ValueError('Inactive query or changed candidate policy')
            prediction_paths[arm] = arm_root/'submission_CUSTOM.csv'
            if arm == 'public' and sha(prediction_paths[arm]) != input_hashes['variants/submission_CUSTOM.csv']:
                raise ValueError('Public control failed byte-identical replay')
        # Freeze all predictions and verify invariant candidate identities before evaluating labels.
        predictions = {arm: pd.read_csv(path, dtype=str, keep_default_na=False) for arm, path in prediction_paths.items()}
        for arm, frame in predictions.items():
            if frame.molecule_id.tolist() != predictions['public'].molecule_id.tolist():
                raise ValueError('Prediction IDs/order changed')
            for baseline, current in zip(predictions['public'].smiles, frame.smiles):
                if metric.candidate_identity_set(baseline) != metric.candidate_identity_set(current):
                    raise ValueError('Candidate metric-identity set changed: ' + arm)
        save(output/'predictions_frozen.json', dict(arms={arm:dict(path=str(path.relative_to(ROOT)),sha256=sha(path))
            for arm,path in prediction_paths.items()}, truth_evaluation_started=False))
        truth = validate_truth(pd.read_parquet(manifest_path.parent/manifest['truth_parquet_file']))
        locked = {r['official_identity'] for r in read(manifest_path.parent/manifest['splits_file'])['cross_final_locked']}
        if set(truth.identity) & locked:
            raise ValueError('Locked final identity entered evaluation')
        metrics = {arm:evaluate_frames(truth,frame) for arm,frame in predictions.items()}
        panel_lookup = truth.set_index('molecule_id').panel.to_dict()
        comparisons = {}
        for arm, baseline in (('dual','public'), ('tri','public'), ('tri','dual')):
            current_rows, base_rows = metrics[arm]['rows'], metrics[baseline]['rows']
            old = {r['molecule_id']:r for r in base_rows}
            comparisons[arm+'_minus_'+baseline] = dict(
                fixed_candidates=audit_fixed_candidates(truth,predictions[arm],predictions[baseline]),
                paired_bootstrap=paired_bootstrap(current_rows,base_rows,2000,20261106),
                by_panel={str(panel):paired_bootstrap(
                    [r for r in current_rows if panel_lookup[r['molecule_id']]==panel],
                    [r for r in base_rows if panel_lookup[r['molecule_id']]==panel],2000,20261106)
                    for panel in truth.panel.drop_duplicates()},
                changed_truth_ranks=[dict(molecule_id=r['molecule_id'],panel=panel_lookup[r['molecule_id']],
                    rank_before=old[r['molecule_id']]['rank'],rank_after=r['rank'],
                    rr_delta=r['mrr_at_25']-old[r['molecule_id']]['mrr_at_25'],
                    same_formula_rank_before=old[r['molecule_id']]['truth_formula_only_rank'],
                    same_formula_rank_after=r['truth_formula_only_rank']) for r in current_rows
                    if r['rank']!=old[r['molecule_id']]['rank']])
        if input_hashes != {name:sha(path) for name,path in sources.items()}:
            raise ValueError('Original immutable inputs changed')
        report = dict(status='complete', experiment='EXP004', source_sha256=ORIGINAL_SHA, manifest_sha256=MANIFEST_SHA,
            scoring_layer='CUSTOM consensus before physical/merge/final prior; not complete V56/V30 output',
            scope='Fixed-candidate reference-isolated diagnostic with known full-refit pretrained exposure; not clean CV.',
            arm_weights=ARMS, consensus=dict(w_top=.25,w_mid=.75,rescue=0,offset=3.0),
            metrics={arm:value['metrics'] for arm,value in metrics.items()},
            subsets={arm:value['subsets'] for arm,value in metrics.items()}, comparisons=comparisons,
            public_control_byte_identical=True, original_inputs_unchanged=True, locked_final_evaluated=False,
            new_training_or_download_or_kaggle_submission=False, full_new_baseline_reproduced=False,
            model_health=state['scoring_results'], elapsed_seconds=time.monotonic()-started,
            limitations=['All three neural models have official-train full refits; these development identities may be seen.',
                'This isolates neural consensus. Physical reranking, priors, candidate expansion and full public-notebook recipes are not evaluated.',
                'Positive paired differences on this panel do not prove hidden-test or leaderboard improvement.'])
        save(output/'report.json', report)
        state.update(status='complete',finished_at_utc=datetime.now(timezone.utc).isoformat(),elapsed_seconds=report['elapsed_seconds'])
        save(output/'receipt.json', state)
        print(json.dumps(dict(status='complete',metrics=report['metrics'],
            paired_deltas={k:v['paired_bootstrap']['metrics']['mrr_at_25'] for k,v in comparisons.items()},
            elapsed_seconds=report['elapsed_seconds']),indent=2))
        return 0
    except BaseException as error:
        state.update(status='failed',error_type=type(error).__name__,error=str(error)[:350],
                     finished_at_utc=datetime.now(timezone.utc).isoformat())
        save(output/'receipt.json', state)
        raise


if __name__ == '__main__':
    raise SystemExit(main())
