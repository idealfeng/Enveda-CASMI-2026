
# V56 algorithm and priors are unchanged; only the neural score source is replaced.
BATCH_RECIPE = {'branch': 'flex_tri_only', 'target': 'stormseye/casmi26-flex-tri-only-1107', 'version': 1, 'upstream': 'flexonafft/casmi26-closing-the-evidence-gap', 'upstream_version': 56, 'upstream_source_sha256': '0ebc86ad851fe7051e592fb268756e686ee21b9ddbe90012335096a349bd2769', 'weights': {'public': 0.5, 'v2': 0.25, 'v4': 0.25}, 'models': {'v2': {'slug': 'casmi26-scorer-v2-model', 'checkpoint': 'c08d2101154d057890de088be63834eb622468892a3b842512fdc5a65e02ff46', 'config': '5ed9578966792110846b3bf7c11a34d8247fa8e57d168b37124d208924fd9524'}, 'v4': {'slug': 'casmi26-scorer-v4-model', 'checkpoint': '10565a0d8c2c1cc903882ff7ba2a9b7b994ae169228bf0c9b6c4ae055ff4ec51', 'config': '3ee4f2ebe68d21bcd251214ecb23bdf0837b6c4cfae9efc467ca9fcabbdf69a4'}}, 'public_pins': {'features.py': 'a97ad9b3ab3711517864d56e497e1672cb29bb05683c72b52db9f9b0a17b1455', 'model.py': '2547418857386d1c2513fd1ab6c70961e6a96e73d9d495bbfe3052197e69dc39', 'config.json': '563fb2a2a81ca48ea094f9ab78c157a48a6e9a5503e85e6ce8f0fb3615c1cc03', 'final_model.pt': '44436b2daec64373e66f9120dd2389c24fc83dd9430ebeeac18e3cb49dcb9642'}, 'config': {'VARIANT': 'CUSTOM', 'CUSTOM': {'w_top': 0.25, 'w_mid': 0.75, 'rescue': 0}, 'RRF_OFFSET': 3.0, 'COMMIT_MODE': 'fast', 'OUTSIDERS_PER_MOLECULE': 20, 'TIME_GUARD_HOURS': 7.5, 'QUIET_LOGS': True, 'ENABLE_TAIL_SLOT': True, 'PHYSICAL_POST_SECONDS': 1500, 'PHYSICAL': True, 'PROVENANCE': False, 'FRAG_ON_V2': True, 'FINAL_LAYER': True, 'POP_W': 0.1, 'SPEC_W': 0.05, 'NP_W': 0.02, 'LIB_HIT_GATE': 0.87, 'OUTSIDER_FILL': True, 'DISAGREEMENT_RESCUE': False}, 'dataset_sources': ['sanpier/casmi-spectrum-model-v1/1', 'dmitriigluzdov/casmi26-fold-safe-fpnet/5', 'dmitriigluzdov/casmi26-natural-product-knowledge-table/10', 'dmitriigluzdov/casmi26-natural-product-panel-benchmark/10', 'dmitriigluzdov/casmi26-pubchem-popularity-prior/13', 'dmitriigluzdov/casmi26-attributed-v4g-reproduction-assets/9', 'bgunshui/casmi26-scorer-v2-model/1', 'bgunshui/casmi26-scorer-v4-model/1'], 'algorithm_changes': ['Replace only Saner neural scalar/ancillary ensemble scores on existing final and outside candidates.', 'Keep the original V56 consensus, physical layer, m1 merge, low NP/spectral priors, official identity dedup and tail fill.'], 'infrastructure_changes': ['Visible fast commit only; hidden rerun follows original full-input detection.', 'Cells after scheduler are guarded by RUN_PIPELINE with their original code AST inside the true branch.', 'Strict model SHA/coverage/blend assertions and a final observer.'], 'inherited_pretraining_exposure': True, 'clean_cv': False, 'lotus_added': False}
BATCH_RECIPE_SHA256 = '92a6ad3d6133b13cb0789557bebefcac6dcb67bdf3824901e37d2b5878419423'
BATCH_BUNDLE_AUDIT = {}
BATCH_MAIN_ENSEMBLE_AUDIT = None
BATCH_OUTSIDER_ENSEMBLE_AUDIT = None


def _batch_sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1<<20),b''):h.update(block)
    return h.hexdigest()


def _batch_stage_model(name, base_bundle):
    wanted=BATCH_RECIPE['models'][name]
    hits=[p for p in Path(INPUT).rglob('final_model.pt') if wanted['slug'] in p.parts]
    assert len(hits)==1, 'Expected exactly one native model '+name
    native=hits[0].parent
    assert _batch_sha(native/'final_model.pt')==wanted['checkpoint'], 'Checkpoint changed: '+name
    assert _batch_sha(native/'config_used.json')==wanted['config'], 'Config changed: '+name
    dst=ROOT/('batch_bundle_'+name);dst.mkdir(exist_ok=True)
    for filename in ('model.py','features.py'):
        shutil.copy2(Path(base_bundle)/filename,dst/filename)
    shutil.copy2(native/'final_model.pt',dst/'final_model.pt')
    shutil.copy2(native/'config_used.json',dst/'config.json')
    actual={filename:_batch_sha(dst/filename) for filename in BATCH_RECIPE['public_pins']}
    expected=dict(BATCH_RECIPE['public_pins'])
    expected.update({'final_model.pt':wanted['checkpoint'],'config.json':wanted['config']})
    assert actual==expected, 'Staged model bundle differs: '+name
    BATCH_BUNDLE_AUDIT[name]=dict(path=str(dst),pins=actual,native_checkpoint_sha256=wanted['checkpoint'],native_config_sha256=wanted['config'])
    return str(dst)


def _batch_blend(paths, output):
    weights=BATCH_RECIPE['weights']
    frames={name:pd.read_parquet(path).set_index(['molecule_id','smiles']) for name,path in paths.items()}
    public=frames['public']
    assert not public.index.duplicated().any()
    scalar_columns=['neural_score','neural_cos','neural_fp','neural_std','neural_ok']
    stable_columns=[name for name in public.columns if name not in scalar_columns]
    for name,frame in frames.items():
        assert not frame.index.duplicated().any() and set(frame.index)==set(public.index), 'Model candidate keys changed: '+name
        frame=frame.reindex(public.index);frames[name]=frame
        pd.testing.assert_frame_equal(public[stable_columns],frame[stable_columns],check_dtype=False,check_exact=True)
        assert frame.neural_ok.astype(bool).equals(public.neural_ok.astype(bool)), 'Unsupported/usable coverage changed: '+name
        assert np.isfinite(pd.to_numeric(frame.loc[frame.neural_ok.astype(bool),'neural_score'],errors='coerce')).all(), 'Nonfinite usable score: '+name
    def z(values):
        groups=values.groupby(level=0)
        return ((values-groups.transform('mean'))/groups.transform(lambda x:x.std(ddof=0)).clip(lower=1e-6)).fillna(0.0)
    combined=public.copy()
    expected=sum(weights[name]*z(frames[name].neural_score.fillna(0.0)) for name in weights)
    combined['neural_score']=expected
    for column in ('neural_cos','neural_fp','neural_std'):
        combined[column]=weights['public']*public[column]
        for name in weights:
            if name!='public':combined[column]+=weights[name]*frames[name][column].fillna(0.0)
    combined['neural_ok']=public.neural_ok.astype(bool)
    assert np.isfinite(combined.neural_score.to_numpy()).all()
    combined.reset_index().to_parquet(output,index=False)
    saved=pd.read_parquet(output).set_index(['molecule_id','smiles']).reindex(public.index)
    diff=float(np.max(np.abs(saved.neural_score.to_numpy()-expected.to_numpy()))) if len(expected) else 0.0
    assert diff==0.0, 'Ensemble values changed on save'
    active=public.processed.astype(bool) if 'processed' in public else pd.Series(True,index=public.index)
    return dict(status='passed',weights=weights,candidate_rows=len(public),active_candidates=int(active.sum()),
        usable_candidates=int((public.neural_ok.astype(bool)&active).sum()),
        usable_molecules=int(public.loc[public.neural_ok.astype(bool)&active].index.get_level_values(0).nunique()),
        candidate_keys_equal=True,stable_features_equal=True,coverage_equal=True,usable_scores_finite=True,
        combined_score_max_abs_difference=diff,output_sha256=_batch_sha(output),model_sources={name:str(path) for name,path in paths.items()})


BUNDLE=materialise_sources()
PUB_BUNDLE=BUNDLE
_batch_actual_public={name:_batch_sha(Path(PUB_BUNDLE)/name) for name in BATCH_RECIPE['public_pins']}
assert _batch_actual_public==BATCH_RECIPE['public_pins'], 'Public four input pins changed'
BATCH_BUNDLE_AUDIT['public']=dict(path=str(PUB_BUNDLE),pins=_batch_actual_public)
BATCH_BUNDLES={'public':PUB_BUNDLE}
for _batch_name in BATCH_RECIPE['models']:
    BATCH_BUNDLES[_batch_name]=_batch_stage_model(_batch_name,PUB_BUNDLE)
assert len({entry['pins']['final_model.pt'] for entry in BATCH_BUNDLE_AUDIT.values()})==len(BATCH_RECIPE['weights']), 'Model checkpoints must differ'

PIPELINE_DONE=run_public_pipeline()
if not RUN_PIPELINE:
    assert not IS_RERUN and COMMIT_MODE=='fast'
    _batch_fast=pd.read_csv(COMP/'sample_submission.csv',dtype=str,keep_default_na=False)
    _batch_fast['smiles']='CCO'
    _batch_fast.to_csv(ROOT/'submission.csv',index=False)
    SUBMITTED='fast_static_placeholder'
else:
    assert PIPELINE_DONE, 'A real hidden/visible pipeline is required'
    _batch_main={}
    for _batch_name,_batch_bundle in BATCH_BUNDLES.items():
        BUNDLE=_batch_bundle
        assert score_final_lists(), 'Neural scorer failed: '+_batch_name
        _batch_path=ROOT/('batch_neural_'+_batch_name+'.parquet')
        shutil.copy2(ROOT/'neural_candidate_features.parquet',_batch_path)
        _batch_main[_batch_name]=_batch_path
    BATCH_MAIN_ENSEMBLE_AUDIT=_batch_blend(_batch_main,ROOT/'neural_candidate_features.parquet')
    NEURAL_OK=True
    BUNDLE=PUB_BUNDLE
    OUTSIDERS_OK=score_outside_candidates(needed=True)
    if OUTSIDERS_OK and (ROOT/'outsider_neural_features.parquet').is_file():
        _batch_outs={'public':ROOT/'batch_outsider_public.parquet'}
        shutil.copy2(ROOT/'outsider_neural_features.parquet',_batch_outs['public'])
        for _batch_name,_batch_bundle in BATCH_BUNDLES.items():
            if _batch_name=='public':continue
            _batch_path=ROOT/('batch_outsider_'+_batch_name+'.parquet')
            run_stage([sys.executable,CODE/'neural_scores.py',_batch_bundle,'final_model.pt',
                ROOT/'outsider_evidence.parquet',ROOT/'effective_query_spectra.parquet',_batch_path,'cuda'],
                ROOT/('batch_outsiders_'+_batch_name+'.log'),'Neural scorer outsiders '+_batch_name,quiet=True)
            _batch_outs[_batch_name]=_batch_path
        BATCH_OUTSIDER_ENSEMBLE_AUDIT=_batch_blend(_batch_outs,ROOT/'outsider_neural_features.parquet')
    CONSENSUS_OK,REPORT,MOVES=build_consensus()
    assert CONSENSUS_OK, 'Unable to reproduce consensus controls'
    SUBMITTED=choose_and_submit()
    assert SUBMITTED==VARIANT
    shutil.copy2(ROOT/'submission.csv',ROOT/'submission_control_V2.csv')
    print('V56 neural-only branch',BATCH_RECIPE['branch'],BATCH_RECIPE['weights'],flush=True)
