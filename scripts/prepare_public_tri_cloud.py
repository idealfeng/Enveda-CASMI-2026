"""Prepare guarded V30 offline smoke source; never start a model or call Kaggle."""
from pathlib import Path
import argparse
import ast
import copy
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT/'submission/public_neural_review_20261106/tri_v30'
TARGET = 'stormseye/casmi26-public-tri-v30'
ORIGINAL_SHA = '73c8bdc7799ffdad7ef756015c74c90365ee060122f2567f8a3c061ff42cc0df'
SMOKE_SHA = 'b8ebb7ac69f726c191c6888c186b7cdffae72adf474b64c82611137da43a2b15'
LOTUS_SHA = '7684b51f72a2d4c073a8d2435fff14cce0a0e7364ac7904101b8f93990f0ac2f'
CHECKPOINT_SHA = {
    'v2': 'c08d2101154d057890de088be63834eb622468892a3b842512fdc5a65e02ff46',
    'v4': '10565a0d8c2c1cc903882ff7ba2a9b7b994ae169228bf0c9b6c4ae055ff4ec51',
}

PREFLIGHT = '''
# Reproduction observer: file/config checks only, no scoring or ordering changes.
def _public_neural_preflight(public_bundle):
    from pathlib import Path
    import hashlib, json
    expected = __EXPECTED__
    audit = dict(status='checking', observer_version=1,
        upstream_source_sha256=expected['original_source_sha256'],
        smoke_source_sha256=expected['smoke_source_sha256'],
        scoring_or_candidate_changes=False, inputs={}, flags={})
    target = Path(ROOT)/'public_neural_input_audit.json'
    def digest(path):
        h = hashlib.sha256()
        with Path(path).open('rb') as stream:
            for block in iter(lambda: stream.read(1 << 20), b''):
                h.update(block)
        return h.hexdigest()
    def save():
        temporary = target.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(audit, indent=2)+'\\n')
        temporary.replace(target)
    try:
        for name, value in expected['flags'].items():
            observed = globals().get(name)
            audit['flags'][name] = observed
            assert observed == value, 'Unexpected V30 configuration: '+name
        assert globals().get('RUN_PIPELINE') is True, 'A real visible smoke or hidden run is required'
        public_bundle = Path(public_bundle)
        actual = {name: digest(public_bundle/name) for name in expected['public_pins']}
        assert actual == expected['public_pins'], 'Actual public bundle does not match four original pins'
        audit['inputs']['public'] = dict(path=str(public_bundle), pins=actual)
        for name, model in expected['models'].items():
            hits = [p for p in Path(INPUT).rglob('final_model.pt') if model['dataset_slug'] in p.parts]
            assert len(hits) == 1, 'Expected exactly one native '+name+' checkpoint'
            folder = hits[0].parent
            checkpoint_sha = digest(folder/'final_model.pt')
            config_sha = digest(folder/'config_used.json')
            assert checkpoint_sha == model['checkpoint_sha256'], 'Native '+name+' checkpoint differs'
            assert config_sha == model['config_sha256'], 'Native '+name+' config differs'
            config = json.loads((folder/'config_used.json').read_text())
            assert all(config.get(k) == v for k, v in model['config_flags'].items()), 'Native '+name+' config flags differ'
            audit['inputs'][name] = dict(path=str(folder), checkpoint_sha256=checkpoint_sha,
                config_sha256=config_sha, config_flags={k: config.get(k) for k in model['config_flags']})
        checkpoints = [audit['inputs']['public']['pins']['final_model.pt']] + [
            audit['inputs'][name]['checkpoint_sha256'] for name in ('v2','v4')]
        assert len(set(checkpoints)) == 3, 'Three model checkpoints must be distinct'
        lotus = [p for p in Path(INPUT).rglob('candidates_lotus.parquet') if 'casmi26-lotus-candidates' in p.parts]
        assert len(lotus) == 1 and digest(lotus[0]) == expected['lotus_sha256'], 'Native LOTUS V2 input differs'
        audit['inputs']['lotus'] = dict(path=str(lotus[0]), bytes=lotus[0].stat().st_size,
            sha256=expected['lotus_sha256'])
        audit['status'] = 'passed'
        save()
        return audit
    except Exception as error:
        audit.update(status='failed', error_type=type(error).__name__, error_message=str(error)[:500])
        save()
        raise

PUBLIC_NEURAL_INPUT_AUDIT = _public_neural_preflight(BUNDLE)
'''

POSTFLIGHT = '''
# Reproduction observer: do not change scores, CSV bytes, optional budgets, or fallbacks.
def _public_neural_execution_audit():
    from pathlib import Path
    from functools import lru_cache
    import hashlib, json
    import numpy as np
    import pandas as pd
    import rdkit
    expected = __EXPECTED__
    target = Path(ROOT)/'public_neural_execution_audit.json'
    audit = dict(status='checking', observer_version=1,
        upstream_source_sha256=expected['original_source_sha256'],
        smoke_source_sha256=expected['smoke_source_sha256'],
        scoring_or_candidate_changes=False, checks={}, models={})
    def digest(path):
        h = hashlib.sha256()
        with Path(path).open('rb') as stream:
            for block in iter(lambda: stream.read(1 << 20), b''):
                h.update(block)
        return h.hexdigest()
    def save():
        temporary = target.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(audit, indent=2, default=str)+'\\n')
        temporary.replace(target)
    def check(name, condition):
        audit['checks'][name] = bool(condition)
        assert condition, name
    def zscore(series):
        groups = series.groupby(level=0)
        return ((series-groups.transform('mean')) / groups.transform(
            lambda values: values.std(ddof=0)).clip(lower=1e-6)).fillna(0.0)
    def keyed(path):
        frame = pd.read_parquet(path)
        required = {'molecule_id','smiles','neural_score','neural_ok','processed'}
        assert required <= set(frame.columns), 'Missing neural feature columns'
        frame = frame.copy()
        frame['molecule_id'] = frame['molecule_id'].astype(str)
        frame['smiles'] = frame['smiles'].astype(str)
        frame = frame.set_index(['molecule_id','smiles'])
        assert frame.index.is_unique, 'Duplicate molecule/candidate key'
        return frame
    try:
        check('input_preflight', PUBLIC_NEURAL_INPUT_AUDIT.get('status') == 'passed')
        audit['input_audit_sha256'] = digest(Path(ROOT)/'public_neural_input_audit.json')
        check('pipeline_and_three_scoring_calls', all(bool(globals().get(name)) for name in
            ('PIPELINE_DONE','NEURAL_OK','V2_OK','V4_OK')))
        check('metric_rdkit', rdkit.__version__ == '2026.03.3')
        for name, global_name in (('public','PUB_BUNDLE'),('v2','V2_BUNDLE'),('v4','V4_BUNDLE')):
            folder = Path(globals()[global_name])
            wanted = dict(expected['public_pins'])
            if name != 'public':
                wanted['final_model.pt'] = expected['models'][name]['checkpoint_sha256']
                wanted['config.json'] = expected['models'][name]['config_sha256']
            actual = {file: digest(folder/file) for file in wanted}
            check(name+'_actual_bundle_pins', actual == wanted)
            audit['models'][name] = dict(path=str(folder), pins=actual)
        check('three_distinct_checkpoints', len({audit['models'][name]['pins']['final_model.pt']
            for name in ('public','v2','v4')}) == 3)
        source_files = {name: Path(ROOT)/('neural_'+name+'.parquet') for name in ('public','v2','v4')}
        raw = {name: keyed(path) for name, path in source_files.items()}
        main_path = Path(ROOT)/'neural_candidate_features.parquet'
        main = keyed(main_path)
        reference = raw['public']
        keyset = set(reference.index)
        check('three_model_candidate_keys', all(set(frame.index) == keyset for frame in raw.values()))
        check('combined_candidate_keys', set(main.index) == keyset)
        raw = {name: frame.reindex(reference.index) for name, frame in raw.items()}
        main = main.reindex(reference.index)
        queries = pd.read_parquet(Path(ROOT)/'effective_query_spectra.parquet', columns=['molecule_id'])
        active_ids = set(queries.molecule_id.astype(str))
        processed = reference.processed.astype(bool)
        processed_ids = set(reference.index.get_level_values(0)[processed])
        check('processed_ids_match_effective_queries', processed_ids == active_ids)
        check('processed_masks_equal', all(frame.processed.astype(bool).equals(processed)
            for frame in list(raw.values())+[main]))
        public_ok = reference.neural_ok.astype(bool)
        check('new_model_coverage_equals_public', all(raw[name].neural_ok.astype(bool).equals(public_ok)
            for name in ('v2','v4')))
        check('combined_ok_matches_original_and', main.neural_ok.astype(bool).equals(
            raw['public'].neural_ok.astype(bool) & raw['v2'].neural_ok.astype(bool) & raw['v4'].neural_ok.astype(bool)))
        full = bool(globals().get('IS_RERUN'))
        audit.update(is_full_run=full, active_ids=sorted(active_ids), processed_molecules=len(active_ids),
            input_molecules=len(SAMPLE_IDS), placeholder_rows=len(SAMPLE_IDS)-len(active_ids))
        if not full:
            check('visible_smoke12', len(active_ids) == 12)
            check('visible_all_active_usable', bool(public_ok[processed].all()))
        # Hidden unsupported queries follow the original policy: equal coverage is required,
        # while all models may share an unavailable query. No artificial all400 requirement.
        for name, frame in raw.items():
            usable = frame.neural_ok.astype(bool) & processed
            check(name+'_usable_scores_finite', bool(np.isfinite(frame.loc[usable,'neural_score']).all()))
            grouped = frame.loc[processed].neural_ok.astype(bool).groupby(level=0).all()
            audit['models'][name].update(active_candidates=int(processed.sum()),
                usable_candidates=int(usable.sum()), usable_molecules=int(grouped.sum()),
                unsupported_molecules=sorted(grouped.index[~grouped].astype(str)))
        wanted_score = (0.50*zscore(raw['public'].neural_score.fillna(0.0)) +
            0.25*zscore(raw['v2'].neural_score.fillna(0.0)) +
            0.25*zscore(raw['v4'].neural_score.fillna(0.0)))
        check('combined_scores_finite_including_inactive', bool(np.isfinite(main.neural_score).all()))
        check('exact_three_way_combined_scores', np.array_equal(wanted_score.to_numpy(), main.neural_score.to_numpy()))
        audit['combined_score_max_abs_difference'] = float(np.max(np.abs(wanted_score.to_numpy()-main.neural_score.to_numpy()))) if len(main) else 0.0
        audit['feature_files'] = {name: dict(path=str(path), sha256=digest(path)) for name,path in source_files.items()}
        audit['feature_files']['combined'] = dict(path=str(main_path), sha256=digest(main_path))
        # Outsider collection/scoring is optional and budgeted in the source. Observe only.
        outsider = dict(original_OUTSIDERS_OK=bool(globals().get('OUTSIDERS_OK')),
            acceptance_gate=False, original_time_guard_unchanged=True)
        outfiles = {name: Path(ROOT)/('outsider_'+name+'.parquet') for name in ('public','v2','v4')}
        outmain = Path(ROOT)/'outsider_neural_features.parquet'
        outsider['files_present'] = {name: path.is_file() for name,path in outfiles.items()}
        outsider['combined_present'] = outmain.is_file()
        if outsider['original_OUTSIDERS_OK'] and all(path.is_file() for path in outfiles.values()) and outmain.is_file():
            try:
                oframes = {name: keyed(path) for name,path in outfiles.items()}
                oref = oframes['public']
                allkeys = set(oref.index)
                outsider['same_candidate_keys'] = all(set(frame.index) == allkeys for frame in oframes.values())
                if outsider['same_candidate_keys']:
                    oframes = {name: frame.reindex(oref.index) for name,frame in oframes.items()}
                    combined = keyed(outmain).reindex(oref.index)
                    oscore = (0.50*zscore(oframes['public'].neural_score.fillna(0.0)) +
                        0.25*zscore(oframes['v2'].neural_score.fillna(0.0)) +
                        0.25*zscore(oframes['v4'].neural_score.fillna(0.0)))
                    outsider['exact_combined_scores'] = bool(np.array_equal(oscore.to_numpy(), combined.neural_score.to_numpy()))
            except Exception as error:
                outsider.update(observation_error_type=type(error).__name__, observation_error=str(error)[:300])
        audit['outsider_observation'] = outsider
        submission = Path(ROOT)/'submission.csv'
        before_sha = digest(submission)
        frame = pd.read_csv(submission, dtype=str, keep_default_na=False)
        check('csv_columns', list(frame.columns) == ['molecule_id','smiles'])
        check('csv_id_order', frame.molecule_id.tolist() == list(SAMPLE_IDS))
        check('csv_unique_ids', bool(frame.molecule_id.is_unique))
        lists = frame.smiles.str.split(';')
        check('csv_guess_count_and_nonempty', bool(lists.map(lambda values: 1 <= len(values) <= 25 and all(x.strip() for x in values)).all()))
        # Only active predictions need identity diagnostics; inactive LOTUS/dummy rows are not
        # model predictions. Keep original cached keys, canonicalise only missing keys.
        from rdkit import Chem, rdBase
        from rdkit.Chem.MolStandardize import rdMolStandardize
        cached = identity_map()
        canonicalizer = rdMolStandardize.TautomerEnumerator()
        @lru_cache(maxsize=200000)
        def identity(smiles):
            key = cached.get(smiles)
            if isinstance(key,str) and len(key) >= 14:
                return key[:14]
            try:
                with rdBase.BlockLogs():
                    molecule = Chem.MolFromSmiles(smiles)
                    if molecule is None:
                        return None
                    Chem.RemoveStereochemistry(molecule)
                    key = Chem.MolToInchiKey(canonicalizer.Canonicalize(molecule))
                    return key[:14] if key else None
            except (ValueError,RuntimeError,TypeError):
                return None
        invalid, duplicates = [], []
        checked = 0
        for mid, answer in frame.itertuples(index=False):
            if mid not in active_ids:
                continue
            checked += 1
            keys = [identity(s) for s in answer.split(';')]
            if None in keys:
                invalid.append(dict(molecule_id=mid, count=keys.count(None)))
            valid = [key for key in keys if key is not None]
            if len(valid) != len(set(valid)):
                duplicates.append(dict(molecule_id=mid, count=len(valid)-len(set(valid))))
        audit['active_identity_diagnostics'] = dict(checked_molecules=checked,
            invalid_identity_rows=invalid, duplicate_identity_rows=duplicates,
            observations_only=True, csv_or_candidates_modified=False,
            inactive_identity_checks_skipped=True)
        check('csv_bytes_unchanged_by_observer', digest(submission) == before_sha)
        audit['submission'] = dict(rows=len(frame), sha256=before_sha, bytes=submission.stat().st_size)
        audit['status'] = 'passed'
        save()
        return audit
    except Exception as error:
        audit.update(status='failed', error_type=type(error).__name__, error_message=str(error)[:500])
        save()
        raise

PUBLIC_NEURAL_EXECUTION_AUDIT = _public_neural_execution_audit()
print('PUBLIC NEURAL EXECUTION AUDIT', PUBLIC_NEURAL_EXECUTION_AUDIT['status'],
      PUBLIC_NEURAL_EXECUTION_AUDIT.get('processed_molecules'), PUBLIC_NEURAL_EXECUTION_AUDIT.get('submission'))
'''


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source(cell):
    value = cell['source']
    return ''.join(value) if isinstance(value,list) else value


def config_value(node):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'dict' and not node.args:
        return {item.arg: ast.literal_eval(item.value) for item in node.keywords}
    return ast.literal_eval(node)


def expected_inputs(notebook, review):
    wanted_names = {'VARIANT','CUSTOM','RRF_OFFSET','COMMIT_MODE','OUTSIDERS_PER_MOLECULE',
        'TIME_GUARD_HOURS','ENABLE_TAIL_SLOT','PHYSICAL_POST_SECONDS','PHYSICAL','PROVENANCE',
        'FRAG_ON_V2','ENABLE_K14_DEDUP','POP_W','SPEC_W','NP_W','LIB_HIT_GATE','PIN_OLD_LEADER',
        'OUTSIDER_FILL','NP_PROMO_MARGIN'}
    flags = {}
    for cell in notebook['cells']:
        if cell['cell_type'] != 'code' or 'COMMIT_MODE =' not in source(cell):
            continue
        for node in ast.parse(source(cell)).body:
            if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                continue
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id in wanted_names:
                flags[target.id] = config_value(node.value)
            elif isinstance(target, ast.Tuple):
                values = config_value(node.value)
                for name, value in zip(target.elts, values):
                    if isinstance(name, ast.Name) and name.id in wanted_names:
                        flags[name.id] = value
    if set(flags) != wanted_names or flags['COMMIT_MODE'] != 'smoke':
        raise ValueError('Could not bind all expected V30 smoke flags')
    models = {}
    config_keys = ('width','heads','layers','embedding','fp_bits','max_peaks','min_peaks',
        'temperature','fp_score_weight','refit_full','external_paths')
    for name, digest in CHECKPOINT_SHA.items():
        slug = 'casmi26-scorer-'+name+'-model'
        folder = ROOT/'assets/kaggle/bgunshui'/slug/'v1'
        manifest = read(folder/'BUNDLE_MANIFEST.json')
        for item in manifest['files']:
            if sha(folder/item['destination_file']) != item['sha256']:
                raise ValueError('Model package input changed')
        if sha(folder/'final_model.pt') != digest:
            raise ValueError('Unexpected fixed model checkpoint')
        config = read(folder/'config_used.json')
        models[name] = dict(dataset_slug=slug, checkpoint_sha256=digest,
            config_sha256=sha(folder/'config_used.json'), config_flags={key: config[key] for key in config_keys})
    lotus = ROOT/'assets/kaggle/qwertykeypadapple/casmi26-lotus-candidates/v2/candidates_lotus.parquet'
    if sha(lotus) != LOTUS_SHA:
        raise ValueError('LOTUS input changed')
    return dict(original_source_sha256=ORIGINAL_SHA, smoke_source_sha256=SMOKE_SHA,
        public_pins=review['source_pins']['MODEL_PINS'], models=models, lotus_sha256=LOTUS_SHA, flags=flags)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'submission/public_tri_cloud_20261106')
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT) or output == ROOT or output.exists():
        parser.error('Use a new, separate D: workspace stage; never overwrite a prepared stage')
    original, smoke = REVIEW/'notebook.ipynb', REVIEW/'smoke_review/notebook.ipynb'
    if sha(original) != ORIGINAL_SHA or sha(smoke) != SMOKE_SHA:
        raise ValueError('Frozen upstream/review snapshots changed')
    metadata = read(REVIEW/'smoke_review/kernel-metadata.json')
    metadata['title'] = 'CASMI26 public tri V30'
    if metadata['id'] != TARGET or not metadata['is_private'] or metadata['enable_internet']:
        raise ValueError('Expected new private offline target')
    notebook = read(smoke)
    expected = expected_inputs(notebook, read(REVIEW/'review.json'))
    preflight = PREFLIGHT.replace('__EXPECTED__', repr(expected))
    postflight = POSTFLIGHT.replace('__EXPECTED__', repr(expected))
    modified = copy.deepcopy(notebook)
    changed = []
    needle = 'BUNDLE = materialise_sources()'
    for index, cell in enumerate(modified['cells']):
        if cell['cell_type'] != 'code' or needle not in source(cell):
            continue
        text = source(cell)
        if text.count(needle) != 1:
            raise ValueError('Unexpected materialise_sources call count')
        replacement = text.replace(needle, needle+'\n'+preflight+'\n', 1)
        # Removing precisely the observer nodes must recover the untouched cell AST.
        original_tree, guarded_tree = ast.parse(text), ast.parse(replacement)
        guarded_tree.body = [node for node in guarded_tree.body if not (
            isinstance(node, ast.FunctionDef) and node.name == '_public_neural_preflight') and not (
            isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and
                target.id == 'PUBLIC_NEURAL_INPUT_AUDIT' for target in node.targets))]
        if ast.dump(original_tree, include_attributes=False) != ast.dump(guarded_tree, include_attributes=False):
            raise ValueError('Observer insertion changed existing cell semantics')
        cell['source'] = replacement.splitlines(keepends=True)
        changed.append(index)
    if len(changed) != 1:
        raise ValueError('Expected exactly one stage0 observer insertion')
    modified['cells'].append(dict(cell_type='code', execution_count=None, metadata={}, outputs=[],
        source=postflight.splitlines(keepends=True)))
    for index, cell in enumerate(modified['cells']):
        if cell['cell_type'] == 'code':
            compile(source(cell), '<prepared-code-cell-'+str(index)+'>', 'exec')
            cell['outputs'] = []
            cell['execution_count'] = None
            cell.setdefault('metadata', {}).pop('execution', None)
    modified.setdefault('metadata', {}).pop('widgets', None)
    output.mkdir(parents=True)
    notebook_raw = (json.dumps(modified, indent=2, ensure_ascii=False)+'\n').encode('utf-8')
    metadata_raw = (json.dumps(metadata, indent=2)+'\n').encode('utf-8')
    (output/'notebook.ipynb').write_bytes(notebook_raw)
    (output/'kernel-metadata.json').write_bytes(metadata_raw)
    (output/'public_neural_preflight.py').write_text(preflight, encoding='utf-8')
    (output/'public_neural_postflight.py').write_text(postflight, encoding='utf-8')
    receipt = dict(status='prepared', target=TARGET, notebook_sha256=sha(output/'notebook.ipynb'),
        metadata_sha256=sha(output/'kernel-metadata.json'), original_source_sha256=ORIGINAL_SHA,
        smoke_source_sha256=SMOKE_SHA, original_source_preserved=True, smoke_review_preserved=True,
        adaptations=['Visible COMMIT_MODE fast->smoke inherited from isolated smoke review.',
            'Preflight observer inserted immediately after materialise_sources; original cell AST preserved.',
            'Final observation cell checks actual bundles, coverage, exact main blend and CSV without changing scores.',
            'Stored outputs/execution counts and execution timestamps cleared.'],
        original_stage0_cell=changed[0], code_cells_compile=True, stored_code_outputs_cleared=True,
        runtime_artifacts=['public_neural_input_audit.json','public_neural_execution_audit.json','submission.csv'],
        expected_inputs=expected, guard_scoring_or_ordering_changes=False,
        hidden_unsupported_policy='All three models may share an unsupported query; coverage must equal public.',
        outsider_policy='Observation only; source time guard and optional fallback behavior unchanged.',
        identity_policy='Only active rows checked using cache plus official canonical fallback; invalid/duplicates recorded only.',
        cloud_run_or_submission_performed=False)
    (output/'prepare_receipt.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({key: receipt[key] for key in ('status','target','notebook_sha256','metadata_sha256',
        'original_stage0_cell','code_cells_compile','runtime_artifacts')}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
