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
    _s.copy2(_src / 'config_used.json', _dst / 'config_used.json')
    _s.copy2(_src / 'final_model.pt', _dst / 'final_model.pt')
    print('OURS: using private model from', _src, flush=True)
    return str(_dst)

BUNDLE = _swap_to_ours(BUNDLE)
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
    NEURAL_OK = score_final_lists()
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
