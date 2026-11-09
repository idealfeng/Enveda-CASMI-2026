
# Reproduction observer: do not change scores, CSV bytes, optional budgets, or fallbacks.
def _public_neural_execution_audit():
    from pathlib import Path
    from functools import lru_cache
    import hashlib, json
    import numpy as np
    import pandas as pd
    import rdkit
    expected = {'original_source_sha256': '73c8bdc7799ffdad7ef756015c74c90365ee060122f2567f8a3c061ff42cc0df', 'smoke_source_sha256': 'b8ebb7ac69f726c191c6888c186b7cdffae72adf474b64c82611137da43a2b15', 'public_pins': {'features.py': 'a97ad9b3ab3711517864d56e497e1672cb29bb05683c72b52db9f9b0a17b1455', 'model.py': '2547418857386d1c2513fd1ab6c70961e6a96e73d9d495bbfe3052197e69dc39', 'config.json': '563fb2a2a81ca48ea094f9ab78c157a48a6e9a5503e85e6ce8f0fb3615c1cc03', 'final_model.pt': '44436b2daec64373e66f9120dd2389c24fc83dd9430ebeeac18e3cb49dcb9642'}, 'models': {'v2': {'dataset_slug': 'casmi26-scorer-v2-model', 'checkpoint_sha256': 'c08d2101154d057890de088be63834eb622468892a3b842512fdc5a65e02ff46', 'config_sha256': '5ed9578966792110846b3bf7c11a34d8247fa8e57d168b37124d208924fd9524', 'config_flags': {'width': 192, 'heads': 6, 'layers': 3, 'embedding': 192, 'fp_bits': 2048, 'max_peaks': 96, 'min_peaks': 3, 'temperature': 0.1, 'fp_score_weight': 2.0, 'refit_full': True, 'external_paths': []}}, 'v4': {'dataset_slug': 'casmi26-scorer-v4-model', 'checkpoint_sha256': '10565a0d8c2c1cc903882ff7ba2a9b7b994ae169228bf0c9b6c4ae055ff4ec51', 'config_sha256': '3ee4f2ebe68d21bcd251214ecb23bdf0837b6c4cfae9efc467ca9fcabbdf69a4', 'config_flags': {'width': 256, 'heads': 8, 'layers': 3, 'embedding': 256, 'fp_bits': 2048, 'max_peaks': 96, 'min_peaks': 3, 'temperature': 0.1, 'fp_score_weight': 2.0, 'refit_full': True, 'external_paths': []}}}, 'lotus_sha256': '7684b51f72a2d4c073a8d2435fff14cce0a0e7364ac7904101b8f93990f0ac2f', 'flags': {'VARIANT': 'CUSTOM', 'CUSTOM': {'w_top': 0.25, 'w_mid': 0.75, 'rescue': 0}, 'RRF_OFFSET': 3.0, 'COMMIT_MODE': 'smoke', 'OUTSIDERS_PER_MOLECULE': 20, 'TIME_GUARD_HOURS': 7.5, 'ENABLE_TAIL_SLOT': True, 'PHYSICAL_POST_SECONDS': 1500, 'PHYSICAL': True, 'PROVENANCE': False, 'FRAG_ON_V2': True, 'ENABLE_K14_DEDUP': True, 'POP_W': 0.1, 'SPEC_W': 0.1, 'NP_W': 0.12, 'LIB_HIT_GATE': 0.78, 'PIN_OLD_LEADER': True, 'OUTSIDER_FILL': True, 'NP_PROMO_MARGIN': 0.055}}
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
        temporary.write_text(json.dumps(audit, indent=2, default=str)+'\n')
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
