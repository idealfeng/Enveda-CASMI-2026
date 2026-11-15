BUNDLE = materialise_sources()

# ---- private-model swap: use our own longer-trained spectrum model ----
def _swap_to_ours(base_bundle):
    """Find our private scorer bundle and use it as the neural scorer.

    Accepts any attached data source that contains final_model.pt + config_used.json
    (works for a Kaggle dataset or for a kernel output), while ignoring the public
    kit bundle and the staged copy of it.
    """
    import shutil as _s
    from pathlib import Path as _P
    _hits = []
    for _p in _P('/kaggle/input').rglob('final_model.pt'):
        _par = _p.parent
        if 'casmi-spectrum-model-v1' in str(_p) or 'kit_staged' in str(_p):
            continue
        if (_par / 'config_used.json').is_file() or 'casmi_spectrum_model_ours' in str(_p) or 'scorer-v2-model' in str(_p):
            _hits.append(_p)
    if not _hits:
        print('OURS: private model not found under /kaggle/input, keeping the public bundle')
        return base_bundle
    _src = _hits[0].parent
    _dst = _P('/kaggle/working/ours_bundle'); _dst.mkdir(parents=True, exist_ok=True)
    _s.copy2(_P(base_bundle) / 'model.py', _dst / 'model.py')
    _s.copy2(_P(base_bundle) / 'features.py', _dst / 'features.py')
    _cfg = _src / 'config_used.json'
    if _cfg.is_file():
        _s.copy2(_cfg, _dst / 'config_used.json')
    _s.copy2(_P(base_bundle) / 'config.json', _dst / 'config.json')
    _s.copy2(_src / 'final_model.pt', _dst / 'final_model.pt')
    print('OURS BUNDLE READY:', sorted(p.name for p in _dst.iterdir()), 'from', _src)
    return str(_dst)


PUB_BUNDLE = BUNDLE
OURS_BUNDLE = _swap_to_ours(PUB_BUNDLE)
BUNDLE = OURS_BUNDLE
PIPELINE_DONE = run_public_pipeline()
if not PIPELINE_DONE and not IS_RERUN and COMMIT_MODE == 'fast':
    sub_df = pd.read_csv(COMP / 'sample_submission.csv')
    sub_df['smiles'] = ';'.join(['C' + 'C'*i + 'O' for i in range(25)])
    sub_df.to_csv(ROOT / 'submission.csv', index=False)
    sub_df.to_csv(ROOT / 'submission_control_V2.csv', index=False)
    (ROOT / 'variants').mkdir(exist_ok=True)
    sub_df.to_csv(ROOT / 'variants/submission_V2.csv', index=False)
    sub_df.to_csv(ROOT / 'variants/submission_CUSTOM.csv', index=False)
    NEURAL_OK = False
    OUTSIDERS_OK = False
    CONSENSUS_OK = False
    SUBMITTED = 'sample (fast commit)'
    print('Fast commit: unique dummy SMILES written cleanly; scoring rerun runs full pipeline.')
else:
    if not PIPELINE_DONE:
        raise RuntimeError('A real baseline run is required; no placeholder-only submission')
    BUNDLE = PUB_BUNDLE
    NEURAL_OK = score_final_lists()
    shutil.copyfile(ROOT / 'neural_candidate_features.parquet', ROOT / 'neural_public.parquet')
    BUNDLE = OURS_BUNDLE
    if score_final_lists():
        shutil.copyfile(ROOT / 'neural_candidate_features.parquet', ROOT / 'neural_ours.parquet')
        import pandas as _pd
        _a = _pd.read_parquet(ROOT / 'neural_public.parquet').set_index(['molecule_id', 'smiles'])
        _b = _pd.read_parquet(ROOT / 'neural_ours.parquet').set_index(['molecule_id', 'smiles']).reindex(_a.index)
        def _z(_s):
            _g = _s.groupby(level=0)
            return (_s - _g.transform('mean')) / _g.transform(lambda x: x.std(ddof=0)).clip(lower=1e-6)
        _a['neural_score'] = 0.5 * _z(_a['neural_score'].fillna(0.0)) + 0.5 * _z(_b['neural_score'].fillna(0.0))
        _a['neural_cos'] = 0.5 * _a['neural_cos'] + 0.5 * _b['neural_cos'].fillna(0.0)
        _a['neural_fp'] = 0.5 * _a['neural_fp'] + 0.5 * _b['neural_fp'].fillna(0.0)
        _a['neural_std'] = 0.5 * _a['neural_std'] + 0.5 * _b['neural_std'].fillna(0.0)
        _a['neural_ok'] = _a['neural_ok'].astype(bool) & _b['neural_ok'].fillna(False).astype(bool)
        _a.reset_index().to_parquet(ROOT / 'neural_candidate_features.parquet', index=False)
        print('ENSEMBLE neural = 0.5*z(public) + 0.5*z(ours)', flush=True)
    BUNDLE = OURS_BUNDLE
    if not NEURAL_OK:
        raise RuntimeError('The 0.468 V2 neural checkpoint is required; refusing silent 0.465 fallback')
    OUTSIDERS_OK = score_outside_candidates(needed=True)
    CONSENSUS_OK, REPORT, MOVES = build_consensus()
    if not CONSENSUS_OK:
        raise RuntimeError('Unable to reproduce the V2 control')
    SUBMITTED = choose_and_submit()
    if SUBMITTED != VARIANT:
        raise RuntimeError(f'Expected {VARIANT}, got {SUBMITTED}')
    shutil.copy2(ROOT/'submission.csv', ROOT/'submission_control_V2.csv')
    print('Exact V2 control:', hashlib.sha256((ROOT/'submission_control_V2.csv').read_bytes()).hexdigest()[:16])
