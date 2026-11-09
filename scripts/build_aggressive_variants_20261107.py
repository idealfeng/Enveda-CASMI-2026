"""Prepare two private V56 neural-only variants. No Kaggle/network/model execution."""
from pathlib import Path
import ast
import copy
import hashlib
import json

ROOT=Path(__file__).resolve().parents[1]
ORIGINAL=ROOT/'third_party/flexonafft_evidence_gap/v56/original.ipynb'
ORIGINAL_SHA='0ebc86ad851fe7051e592fb268756e686ee21b9ddbe90012335096a349bd2769'
OUT=ROOT/'submission/aggressive_20261107'
PUBLIC_PINS={
    'features.py':'a97ad9b3ab3711517864d56e497e1672cb29bb05683c72b52db9f9b0a17b1455',
    'model.py':'2547418857386d1c2513fd1ab6c70961e6a96e73d9d495bbfe3052197e69dc39',
    'config.json':'563fb2a2a81ca48ea094f9ab78c157a48a6e9a5503e85e6ce8f0fb3615c1cc03',
    'final_model.pt':'44436b2daec64373e66f9120dd2389c24fc83dd9430ebeeac18e3cb49dcb9642',
}
MODELS={
    'v2':dict(slug='casmi26-scorer-v2-model',checkpoint='c08d2101154d057890de088be63834eb622468892a3b842512fdc5a65e02ff46',config='5ed9578966792110846b3bf7c11a34d8247fa8e57d168b37124d208924fd9524'),
    'v4':dict(slug='casmi26-scorer-v4-model',checkpoint='10565a0d8c2c1cc903882ff7ba2a9b7b994ae169228bf0c9b6c4ae055ff4ec51',config='3ee4f2ebe68d21bcd251214ecb23bdf0837b6c4cfae9efc467ca9fcabbdf69a4'),
}
BASE_DATASETS=[
    'sanpier/casmi-spectrum-model-v1/1',
    'dmitriigluzdov/casmi26-fold-safe-fpnet/5',
    'dmitriigluzdov/casmi26-natural-product-knowledge-table/10',
    'dmitriigluzdov/casmi26-natural-product-panel-benchmark/10',
    'dmitriigluzdov/casmi26-pubchem-popularity-prior/13',
    'dmitriigluzdov/casmi26-attributed-v4g-reproduction-assets/9',
]


def sha(raw):return hashlib.sha256(raw).hexdigest()
def source(cell):
    value=cell.get('source','');return ''.join(value) if isinstance(value,list) else value
def tree(text):return ast.dump(ast.parse(text),include_attributes=False)
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def write_json(path,value):path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')


SCHEDULER=r'''
# V56 algorithm and priors are unchanged; only the neural score source is replaced.
BATCH_RECIPE = __RECIPE__
BATCH_RECIPE_SHA256 = '__RECIPE_SHA__'
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
'''


OBSERVER=r'''
# Observation only. This cell never changes candidates, weights or submission.csv.
def _batch_variant_audit():
    checks={}
    expected=BATCH_RECIPE
    checks['recipe_sha256']=BATCH_RECIPE_SHA256=='__RECIPE_SHA__'
    checks['configuration_exact']=all(globals().get(name)==value for name,value in expected['config'].items())
    checks['public_input_pins']=BATCH_BUNDLE_AUDIT['public']['pins']==expected['public_pins']
    checks['all_native_models_staged']=set(BATCH_BUNDLE_AUDIT)==set(expected['weights'])
    checks['distinct_model_checkpoints']=len({entry['pins']['final_model.pt'] for entry in BATCH_BUNDLE_AUDIT.values()})==len(expected['weights'])
    checks['no_lotus_dependency']='lotus' not in ' '.join(expected['dataset_sources']).lower()
    checks['v56_original_priors']=POP_W==0.10 and SPEC_W==0.05 and NP_W==0.02 and LIB_HIT_GATE==0.87
    frame=pd.read_csv(ROOT/'submission.csv',dtype=str,keep_default_na=False)
    checks['csv_columns']=list(frame.columns)==['molecule_id','smiles']
    checks['csv_ids']=frame.molecule_id.tolist()==SAMPLE_IDS and frame.molecule_id.is_unique
    checks['csv_nonempty_counts']=bool(frame.smiles.str.split(';').map(lambda guesses:1<=len(guesses)<=25 and all(guesses)).all())
    mode='full_runtime' if RUN_PIPELINE else 'fast_static'
    processed=0
    if not RUN_PIPELINE:
        checks['fast_mode_explicit']=COMMIT_MODE=='fast' and not IS_RERUN and not PIPELINE_DONE
        checks['no_runtime_claim']=BATCH_MAIN_ENSEMBLE_AUDIT is None and BATCH_OUTSIDER_ENSEMBLE_AUDIT is None
    else:
        receipt=json.loads((ROOT/'execution_receipt.json').read_text())
        processed=int(receipt['processed_molecules'])
        checks['pipeline_complete']=bool(PIPELINE_DONE and NEURAL_OK and CONSENSUS_OK)
        checks['main_runtime_ensemble']=BATCH_MAIN_ENSEMBLE_AUDIT.get('status')=='passed' and BATCH_MAIN_ENSEMBLE_AUDIT.get('combined_score_max_abs_difference')==0.0
        checks['main_combined_file_unchanged']=_batch_sha(ROOT/'neural_candidate_features.parquet')==BATCH_MAIN_ENSEMBLE_AUDIT['output_sha256']
        checks['main_runtime_weights']=BATCH_MAIN_ENSEMBLE_AUDIT['weights']==expected['weights']
        if IS_RERUN:
            checks['hidden_full_input']=receipt.get('is_full_run') is True and processed==len(SAMPLE_IDS)
            checks['hidden_400_rows']=len(frame)==400
        if OUTSIDERS_OK:
            checks['outsider_runtime_ensemble']=BATCH_OUTSIDER_ENSEMBLE_AUDIT is not None and BATCH_OUTSIDER_ENSEMBLE_AUDIT['status']=='passed'
        checks['final_layer_applied']=FINAL_REPORT.get('status')=='applied'
        checks['merge_applied']=MERGE_REPORT.get('status')=='applied'
    result=dict(status='passed' if all(checks.values()) else 'failed',mode=mode,branch=expected['branch'],
        target=expected['target'],version=1,recipe_sha256=BATCH_RECIPE_SHA256,checks=checks,
        config=expected['config'],expected_dataset_sources=expected['dataset_sources'],model_bundles=BATCH_BUNDLE_AUDIT,
        main_ensemble=BATCH_MAIN_ENSEMBLE_AUDIT,outsider_ensemble=BATCH_OUTSIDER_ENSEMBLE_AUDIT,
        processed_molecules=processed,submission_rows=len(frame),submission_sha256=_batch_sha(ROOT/'submission.csv'),
        fast_static_only=not RUN_PIPELINE,hidden_score_proven=False,scoring_changes=expected['algorithm_changes'])
    (ROOT/'batch_variant_audit.json').write_text(json.dumps(result,indent=2)+'\n')
    assert result['status']=='passed', 'Variant audit failed: '+','.join(k for k,v in checks.items() if not v)
    return result

BATCH_VARIANT_AUDIT=_batch_variant_audit()
print('BATCH_VARIANT_AUDIT',BATCH_VARIANT_AUDIT['mode'],BATCH_VARIANT_AUDIT['branch'],BATCH_VARIANT_AUDIT['status'],flush=True)
'''


def literal(node):
    if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='dict':
        return {item.arg:literal(item.value) for item in node.keywords}
    return ast.literal_eval(node)


def config_of(text):
    result={}
    for node in ast.parse(text).body:
        if not isinstance(node,ast.Assign):raise ValueError('Unexpected config statement')
        value=literal(node.value)
        for target in node.targets:
            if isinstance(target,ast.Name):result[target.id]=value
            elif isinstance(target,ast.Tuple):
                for item,val in zip(target.elts,value):result[item.id]=val
            else:raise ValueError('Unexpected configuration target')
    return result


def build(branch,weights):
    if sha(ORIGINAL.read_bytes())!=ORIGINAL_SHA:raise ValueError('Original V56 source changed')
    original=read(ORIGINAL);notebook=copy.deepcopy(original)
    target='stormseye/casmi26-'+branch.replace('_','-')+'-1107'
    folder=OUT/branch
    if folder.exists():raise FileExistsError('Never overwrite an existing reviewed branch')
    config_text=source(original['cells'][1])
    if config_text.count("COMMIT_MODE = 'smoke'")!=1:raise ValueError('Original smoke flag changed')
    config_text=config_text.replace("COMMIT_MODE = 'smoke'","COMMIT_MODE = 'fast'",1)
    models={name:MODELS[name] for name in weights if name!='public'}
    for name,wanted in models.items():
        path=ROOT/'assets/kaggle/bgunshui'/wanted['slug']/'v1'
        for filename,key in [('final_model.pt','checkpoint'),('config_used.json','config')]:
            if sha((path/filename).read_bytes())!=wanted[key]:raise ValueError('Frozen native model changed')
    datasets=BASE_DATASETS+['bgunshui/'+model['slug']+'/1' for model in models.values()]
    recipe=dict(branch=branch,target=target,version=1,upstream='flexonafft/casmi26-closing-the-evidence-gap',
        upstream_version=56,upstream_source_sha256=ORIGINAL_SHA,weights=weights,models=models,public_pins=PUBLIC_PINS,
        config=config_of(config_text),dataset_sources=datasets,
        algorithm_changes=['Replace only Saner neural scalar/ancillary ensemble scores on existing final and outside candidates.',
            'Keep the original V56 consensus, physical layer, m1 merge, low NP/spectral priors, official identity dedup and tail fill.'],
        infrastructure_changes=['Visible fast commit only; hidden rerun follows original full-input detection.',
            'Cells after scheduler are guarded by RUN_PIPELINE with their original code AST inside the true branch.',
            'Strict model SHA/coverage/blend assertions and a final observer.'],
        inherited_pretraining_exposure=True,clean_cv=False,lotus_added=False)
    recipe_raw=(json.dumps(recipe,indent=2,ensure_ascii=False)+'\n').encode('utf-8');recipe_sha=sha(recipe_raw)
    scheduler=SCHEDULER.replace('__RECIPE__',repr(recipe)).replace('__RECIPE_SHA__',recipe_sha)
    observer=OBSERVER.replace('__RECIPE_SHA__',recipe_sha)
    notebook['cells'][1]['source']=config_text.splitlines(keepends=True)
    notebook['cells'][11]['source']=scheduler.splitlines(keepends=True)
    guarded=[]
    for index,cell in enumerate(notebook['cells']):
        if cell['cell_type']!='code':continue
        if index>=12:
            text=source(cell)
            if not text.strip():continue
            wrapped='if RUN_PIPELINE:\n'+''.join('    '+line if line.strip() else line for line in text.splitlines(keepends=True))
            if not wrapped.endswith('\n'):wrapped+='\n'
            wrapper=ast.parse(wrapped)
            if len(wrapper.body)!=1 or not isinstance(wrapper.body[0],ast.If) or tree(ast.unparse(ast.Module(body=wrapper.body[0].body,type_ignores=[])))!=tree(text):
                raise ValueError('Guard wrapper changed hidden code AST')
            cell['source']=wrapped.splitlines(keepends=True);guarded.append(index)
        compile(source(cell),'<'+branch+':cell'+str(index)+'>','exec')
        cell['outputs']=[];cell['execution_count']=None
        cell.setdefault('metadata',{}).pop('execution',None)
    notebook['cells'].append(dict(cell_type='code',source=observer.splitlines(keepends=True),execution_count=None,outputs=[],metadata={}))
    compile(observer,'<observer>','exec')
    notebook.setdefault('metadata',{}).pop('widgets',None)
    metadata=dict(id=target,title=target.split('/')[-1].replace('-',' '),
        code_file='notebook.ipynb',language='python',kernel_type='notebook',is_private=True,
        enable_gpu=True,enable_internet=False,machine_shape='NvidiaTeslaT4',
        docker_image='gcr.io/kaggle-private-byod/python@sha256:9a6bcfda6d03b2cd9aa347ee8c1bae62043328ed0f4afe9bda014e4f8bbf9435',
        competition_sources=['enveda-CASMI26-molecule-id-mass-spectra'],dataset_sources=datasets,kernel_sources=[])
    folder.mkdir(parents=True)
    (folder/'recipe.json').write_bytes(recipe_raw)
    write_json(folder/'notebook.ipynb',notebook);write_json(folder/'kernel-metadata.json',metadata)
    (folder/'scheduler.py').write_text(scheduler,encoding='utf-8');(folder/'observer.py').write_text(observer,encoding='utf-8')
    checks=dict(original_v56_sha=True,all_code_compile=True,all_hidden_post_scheduler_asts_unchanged=True,
        config_only_commit_mode_changed=config_of(config_text)=={**config_of(source(original['cells'][1])),'COMMIT_MODE':'fast'},
        all_other_pre_scheduler_sources_unchanged=all(source(original['cells'][i])==source(notebook['cells'][i]) for i in range(11) if i!=1),
        original_low_priors=recipe['config']['NP_W']==0.02 and recipe['config']['SPEC_W']==0.05 and recipe['config']['LIB_HIT_GATE']==0.87,
        native_model_pins_verified=True,no_lotus=True,private_offline=True,version_pinned_datasets=True,
        no_kernel_dependencies=True,no_stored_outputs=all(not c.get('outputs') and c.get('execution_count') is None for c in notebook['cells'] if c['cell_type']=='code'))
    static=dict(status='passed' if all(checks.values()) else 'failed',target=target,version=1,branch=branch,
        notebook_sha256=sha((folder/'notebook.ipynb').read_bytes()),recipe_sha256=recipe_sha,checks=checks,
        original_source_sha256=ORIGINAL_SHA,guarded_original_code_cells=guarded,actual_hidden_runtime_proven=False)
    write_json(folder/'static_review.json',static)
    receipt=dict(status='prepared',target=target,version=1,branch=branch,notebook_sha256=static['notebook_sha256'],
        metadata_sha256=sha((folder/'kernel-metadata.json').read_bytes()),recipe_sha256=recipe_sha,
        static_review_path=str((folder/'static_review.json').relative_to(ROOT)),
        static_review_sha256=sha((folder/'static_review.json').read_bytes()),
        expected_runtime_artifact='batch_variant_audit.json',fast_expected_mode='fast_static',
        cloud_run_or_submission_performed=False,model_execution_performed=False)
    write_json(folder/'prepare_receipt.json',receipt)
    return receipt


def main():
    results=[build('flex_tri_only',{'public':0.50,'v2':0.25,'v4':0.25}),
             build('flex_dual_only',{'public':0.50,'v2':0.50})]
    print(json.dumps(results,indent=2));return 0


if __name__=='__main__':raise SystemExit(main())
