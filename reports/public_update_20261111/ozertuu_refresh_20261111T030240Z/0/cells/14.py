BUNDLE = materialise_sources()

# ---- Multi-Model Neural Consensus: Ensemble All Available Long-Trained Checkpoints ----
def _find_extra_bundles(base_bundle):
    """Find all distinct trained spectrum model checkpoints under /kaggle/input."""
    import shutil as _s
    from pathlib import Path as _P
    _hits = []
    for _p in sorted(_P('/kaggle/input').rglob('final_model.pt')):
        if 'casmi-spectrum-model-v1' in str(_p) or 'kit_staged' in str(_p):
            continue
        if _p.parent not in _hits:
            _hits.append(_p.parent)
    
    bundles = []
    for i, src in enumerate(_hits):
        dst = _P(f'/kaggle/working/extra_bundle_{i}')
        dst.mkdir(parents=True, exist_ok=True)
        _s.copy2(_P(base_bundle) / 'model.py', dst / 'model.py')
        _s.copy2(_P(base_bundle) / 'features.py', dst / 'features.py')
        _cfg = src / 'config_used.json'
        if _cfg.is_file():
            _s.copy2(_cfg, dst / 'config_used.json')
        _s.copy2(_P(base_bundle) / 'config.json', dst / 'config.json')
        _s.copy2(src / 'final_model.pt', dst / 'final_model.pt')
        bundles.append(str(dst))
        print(f'EXTRA BUNDLE {i} READY from {src}')
    return bundles

PUB_BUNDLE = BUNDLE
EXTRA_BUNDLES = _find_extra_bundles(PUB_BUNDLE)
OURS_BUNDLE = EXTRA_BUNDLES[0] if EXTRA_BUNDLES else PUB_BUNDLE
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
    
    import pandas as _pd
    def _z(_s):
        _g = _s.groupby(level=0)
        return (_s - _g.transform('mean')) / _g.transform(lambda x: x.std(ddof=0)).clip(lower=1e-6)

    # 1. Score with Public Baseline Model
    BUNDLE = PUB_BUNDLE
    NEURAL_OK = score_final_lists()
    shutil.copyfile(ROOT / 'neural_candidate_features.parquet', ROOT / 'neural_public.parquet')
    _pub = _pd.read_parquet(ROOT / 'neural_public.parquet').set_index(['molecule_id', 'smiles'])

    # 2. Score with Extra Trained Bundles
    extra_dfs = []
    for i, b in enumerate(EXTRA_BUNDLES):
        BUNDLE = b
        if score_final_lists():
            p = ROOT / f'neural_extra_{i}.parquet'
            shutil.copyfile(ROOT / 'neural_candidate_features.parquet', p)
            extra_dfs.append(_pd.read_parquet(p).set_index(['molecule_id', 'smiles']).reindex(_pub.index))

    if len(extra_dfs) == 1:
        _b = extra_dfs[0]
        _pub['neural_score'] = 0.5 * _z(_pub['neural_score'].fillna(0.0)) + 0.5 * _z(_b['neural_score'].fillna(0.0))
        _pub['neural_cos'] = 0.5 * _pub['neural_cos'] + 0.5 * _b['neural_cos'].fillna(0.0)
        _pub['neural_fp'] = 0.5 * _pub['neural_fp'] + 0.5 * _b['neural_fp'].fillna(0.0)
        _pub['neural_std'] = 0.5 * _pub['neural_std'] + 0.5 * _b['neural_std'].fillna(0.0)
        _pub['neural_ok'] = _pub['neural_ok'].astype(bool) & _b['neural_ok'].fillna(False).astype(bool)
        print('ENSEMBLE neural: 0.50*z(public) + 0.50*z(extra_0)', flush=True)
    elif len(extra_dfs) >= 2:
        _b = extra_dfs[0]
        _c = extra_dfs[1]
        _pub['neural_score'] = 0.50 * _z(_pub['neural_score'].fillna(0.0)) + 0.25 * _z(_b['neural_score'].fillna(0.0)) + 0.25 * _z(_c['neural_score'].fillna(0.0))
        _pub['neural_cos'] = 0.50 * _pub['neural_cos'] + 0.25 * _b['neural_cos'].fillna(0.0) + 0.25 * _c['neural_cos'].fillna(0.0)
        _pub['neural_fp'] = 0.50 * _pub['neural_fp'] + 0.25 * _b['neural_fp'].fillna(0.0) + 0.25 * _c['neural_fp'].fillna(0.0)
        _pub['neural_std'] = 0.50 * _pub['neural_std'] + 0.25 * _b['neural_std'].fillna(0.0) + 0.25 * _c['neural_std'].fillna(0.0)
        _pub['neural_ok'] = _pub['neural_ok'].astype(bool) & _b['neural_ok'].fillna(False).astype(bool) & _c['neural_ok'].fillna(False).astype(bool)
        print('ENSEMBLE neural: 0.50*z(public) + 0.25*z(extra_0) + 0.25*z(extra_1)', flush=True)

    _pub.reset_index().to_parquet(ROOT / 'neural_candidate_features.parquet', index=False)

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
