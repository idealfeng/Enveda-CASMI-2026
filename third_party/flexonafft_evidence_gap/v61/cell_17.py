# ── Second neural scorer: Ahmed Berat Özer's long-schedule model on exactly the same final candidates ───────
# Its scores are only used by the final layer for ranks 2-25; rank 1 and the m1 merge never see them.
LONG_OK = False
LONG_FEATURES = ROOT / 'neural_candidate_features_long.parquet'
if NEURAL_ENSEMBLE and PIPELINE_DONE and NEURAL_OK:
    try:
        _roots = sorted({p.parent for p in INPUT.rglob('final_model.pt')
                         if 'spectrum-model-long' in str(p) and all((p.parent / n).is_file()
                                                                    for n in ('config.json', 'features.py', 'model.py'))})
        assert len(_roots) == 1, f'long model bundle found {len(_roots)} times'
        run_stage([sys.executable, CODE / 'neural_scores.py', _roots[0], 'final_model.pt',
                   ROOT / 'frozen_candidate_evidence.parquet', ROOT / 'effective_query_spectra.parquet',
                   LONG_FEATURES, 'cuda'], ROOT / 'submission_neural_long.log', 'Neural scorer · long model')
        LONG_OK = LONG_FEATURES.is_file()
    except Exception as exc:
        print('Long neural scorer skipped:', type(exc).__name__, str(exc)[:300])
print('LONG_OK', LONG_OK)
