"""Prepare public Alex V12 reproduction and .482 + identical measured-library overlay.

No cloud calls. All downloads must already be pinned on D. Original library match
math is unchanged; fast-visible skip, observations and official-ID validity guard
are explicitly recorded adaptations.
"""
from __future__ import annotations
import ast,base64,copy,hashlib,json,zlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ALEX=ROOT/'third_party/public_scan_alexchilton__casmi26-lb-0-484-peaks-to-structures-extlib_20261109/source.ipynb'
ALEX_SHA='5ca30854be8f92e84a1510996ba71504537b849d3e7e2e77fd7c50ae2c1bf69c'
GUARDED=ROOT/'submission/optimization_20261108/mass_guarded_head_tail_1108'
GUARDED_SHA='6de37bec32c8aa8bfb46b2c5e94e374b53fe36137dff1cd7d1c4a295359f56fe'
OUT=ROOT/'submission/optimization_20261109'
PUBLIC_PINS={'features.py':'a97ad9b3ab3711517864d56e497e1672cb29bb05683c72b52db9f9b0a17b1455','model.py':'2547418857386d1c2513fd1ab6c70961e6a96e73d9d495bbfe3052197e69dc39','config.json':'563fb2a2a81ca48ea094f9ab78c157a48a6e9a5503e85e6ce8f0fb3615c1cc03','final_model.pt':'44436b2daec64373e66f9120dd2389c24fc83dd9430ebeeac18e3cb49dcb9642'}

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def source(c):return ''.join(c['source']) if isinstance(c['source'],list) else c['source']
def write(p,v):Path(p).write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
def code(s):return dict(cell_type='code',execution_count=None,metadata={},outputs=[],source=s)


BASE_AUDIT=r'''
def _observe_alex_base():
    import hashlib,json,rdkit
    expected=__PUBLIC_PINS__;checks={}
    def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
    def check(k,v):checks[k]=bool(v);assert v,k
    check('public_model_pins',all(digest(Path(PUB_BUNDLE)/k)==v for k,v in expected.items()))
    check('faithful_public_fallback',all(digest(Path(OURS_BUNDLE)/k)==v for k,v in expected.items()))
    check('original_priors',POP_W==.12 and SPEC_W==.12 and NP_W==.12 and LIB_HIT_GATE==.78)
    check('mass_only',V8=='MASS' and MASS_ON and RR8 is False)
    check('official_rdkit',rdkit.__version__=='2026.03.3')
    f=pd.read_csv(ROOT/'submission.csv',dtype=str,keep_default_na=False)
    check('ids_schema',list(f.columns)==['molecule_id','smiles'] and f.molecule_id.tolist()==SAMPLE_IDS and f.molecule_id.is_unique)
    if IS_RERUN:
        check('full_pipeline',PIPELINE_DONE and NEURAL_OK and CONSENSUS_OK and SUBMITTED==VARIANT)
        receipt=json.loads((ROOT/'execution_receipt.json').read_text())
        check('dynamic_hidden_scope',receipt.get('is_full_run') is True and receipt.get('processed_molecules')==len(SAMPLE_IDS)>0)
        check('mass_executed',MASS_REPORT.get('status')=='on' and MASS_LEAD_REPORT.get('status')=='ran')
        a=pd.read_parquet(ROOT/'neural_public.parquet').set_index(['molecule_id','smiles'])
        b=pd.read_parquet(ROOT/'neural_ours.parquet').set_index(['molecule_id','smiles'])
        c=pd.read_parquet(ROOT/'neural_candidate_features.parquet').set_index(['molecule_id','smiles'])
        check('same_candidate_keys',a.index.is_unique and b.index.is_unique and c.index.is_unique and set(a.index)==set(b.index)==set(c.index))
        b,c=b.reindex(a.index),c.reindex(a.index)
        def z(v):
            g=v.groupby(level=0);return (v-g.transform('mean'))/g.transform(lambda x:x.std(ddof=0)).clip(lower=1e-6)
        wanted=.5*z(a.neural_score.fillna(0.))+.5*z(b.neural_score.fillna(0.))
        check('actual_original_ensemble',__import__('numpy').array_equal(wanted.to_numpy(),c.neural_score.to_numpy()))
    else:check('fast_no_model',not RUN_PIPELINE and not PIPELINE_DONE)
    result=dict(status='passed',mode='hidden_full' if IS_RERUN else 'fast_static',checks=checks,csv_sha256=digest(ROOT/'submission.csv'),models='public/public: no second checkpoint in original attachments')
    (ROOT/'base_external_audit.json').write_text(json.dumps(result,indent=2)+'\n');return result
BASE_EXTLIB_AUDIT=_observe_alex_base()
'''


def prepare(name,kind,original_function,files):
    target='stormseye/casmi26-'+name.replace('_','-')+'-1109';stage=OUT/name
    if stage.exists():raise FileExistsError('Preserve prepared stages '+name)
    helper=ROOT/'scripts/external_library_overlay_20261109.py';helper_raw=helper.read_bytes();helper_sha=sha(helper)
    fn_raw=original_function.encode();fn_sha=hashlib.sha256(fn_raw).hexdigest()
    if kind=='public_alex':
        original=read(ALEX);nb=copy.deepcopy(original);base_raw_sha=ALEX_SHA
        metadata=read(ROOT/'submission/aggressive_20261107/public_mass_repro/kernel-metadata.json')
        metadata['dataset_sources']=[x for x in metadata['dataset_sources'] if not x.startswith('bgunshui/')]
        metadata['dataset_sources']+=['takumuhata/casmi26-extlib/2','samartalwar/casmi-2026-spectral-library-massbankharmonized/1','sanpier/catalogue-experiment-saner/1','metric/rdkit-2026-3-3-wheel/1']
        base_audit_source=BASE_AUDIT.replace('__PUBLIC_PINS__',repr(PUBLIC_PINS));base_audit_variable='BASE_EXTLIB_AUDIT'
        base_audits=[dict(name='base_external_audit.json',expected_fields=dict(status='passed',mode='fast_static'),required_true_checks=['public_model_pins','faithful_public_fallback','original_priors','mass_only','official_rdkit','ids_schema','fast_no_model'])]
        # Replace just the external overlay invocation with the observed copy.
        install_index=24
        if '_apex_extlib_overlay' not in source(nb['cells'][install_index]):raise ValueError('Alex overlay cell moved')
    else:
        original=read(GUARDED/'notebook.ipynb');nb=copy.deepcopy(original);base_raw_sha=GUARDED_SHA
        metadata=read(GUARDED/'kernel-metadata.json');metadata['dataset_sources']+=['takumuhata/casmi26-extlib/2','samartalwar/casmi-2026-spectral-library-massbankharmonized/1']
        base_audit_source='';base_audit_variable='GUARDED_TAIL_AUDIT';base_audits=copy.deepcopy(read(GUARDED/'branch_spec.json')['required_runtime_audits']);install_index=len(nb['cells'])
    metadata.update(id=target,title=target.split('/')[1].replace('-',' '),kernel_sources=[],is_private=True,enable_internet=False,enable_gpu=True)
    recipe=dict(branch=name,target=target,method='Alex V12 exact external-library match function with output-validity guard',
        kind=kind,base_source_sha256=base_raw_sha,upstream='alexchilton/casmi26-lb-0-484-peaks-to-structures-extlib',upstream_version=12,
        upstream_source_sha256=ALEX_SHA,upstream_self_reported_public_score=.484,own_public_score=None,
        base_own_public_score=.482 if kind!='public_alex' else None,
        original_function_sha256=fn_sha,helper_sha256=helper_sha,files=files,
        ranking_constants=dict(TAU=.80,K_PEAKS=4,LIB_TAU=.90,precursor_ppm=10,precursor_da=.002,fragment_da=.015),
        adaptations=['Skip external spectral matching on fast visible dummy path, but hash every required library.',
            'Insert two observed reference-append counters and one observed actual best-match record into original function AST; matching mathematics unchanged.',
            'Preserve a query control if a proposal has invalid or duplicate official metric identities; record each such proposal.',
            'Fail closed on global library/source/control binding failure; preserve original control artifact.',
            'Append source/output/score-consumption observer; clear original saved outputs; lossless source-cell compression where used.'],
        encoder_selection='Original public/public fallback; no new encoder added' if kind=='public_alex' else 'Unchanged .482 original v1/v2 upstream + trained late guarded heads',
        new_training=False,locked_final_used=False,validation_mode='fast_static',license_sources=[750330,748363,745615,749217])
    recipe_raw=(json.dumps(recipe,indent=2,ensure_ascii=False)+'\n').encode();recipe_sha=hashlib.sha256(recipe_raw).hexdigest()
    payloads={'external_library_overlay_20261109.py':base64.b64encode(helper_raw).decode(),'alex_v12_external_function.py':base64.b64encode(fn_raw).decode()}
    pins={'external_library_overlay_20261109.py':helper_sha,'alex_v12_external_function.py':fn_sha}
    late=base_audit_source+'\n'+r'''
import base64,hashlib,importlib.util,json
_external_payloads=__PAYLOADS__
_external_pins=__PINS__
try:
    for _name,_encoded in _external_payloads.items():
        _raw=base64.b64decode(_encoded)
        assert hashlib.sha256(_raw).hexdigest()==_external_pins[_name],_name
        (CODE/_name).write_bytes(_raw)
    _external_spec=importlib.util.spec_from_file_location('_external_library_overlay_runtime',CODE/'external_library_overlay_20261109.py')
    _external_overlay=importlib.util.module_from_spec(_external_spec);_external_spec.loader.exec_module(_external_overlay)
    _external_args=(ROOT,INPUT,COMP/'test.parquet',IS_RERUN,SAMPLE_IDS,__BASE_AUDIT__,CODE/'alex_v12_external_function.py',__FUNCTION_SHA__,__FILES__)
    EXTERNAL_OVERLAY_REPORT=_external_overlay.run(*_external_args)
    EXTERNAL_OVERLAY_AUDIT=_external_overlay.audit(*_external_args,__NAME__,__RECIPE_SHA__)
    assert hashlib.sha256((CODE/'external_library_overlay_20261109.py').read_bytes()).hexdigest()==__HELPER_SHA__
except BaseException:
    (ROOT/'submission.csv').unlink(missing_ok=True)
    raise
'''
    for key,value in {'__PAYLOADS__':repr(payloads),'__PINS__':repr(pins),'__BASE_AUDIT__':base_audit_variable,'__FUNCTION_SHA__':repr(fn_sha),'__FILES__':repr(files),'__NAME__':repr(name),'__RECIPE_SHA__':repr(recipe_sha),'__HELPER_SHA__':repr(helper_sha)}.items():late=late.replace(key,value)
    if kind=='public_alex':
        nb['cells'][install_index]=code(late)
        # The original source installer is large. Decode and execute exact bytes.
        old=source(nb['cells'][12]).encode();packed=base64.b64encode(zlib.compress(old,9)).decode()
        nb['cells'][12]['source']="import base64,zlib,hashlib\n_external_core=zlib.decompress(base64.b64decode("+repr(packed)+"))\nassert hashlib.sha256(_external_core).hexdigest()=="+repr(hashlib.sha256(old).hexdigest())+"\nexec(compile(_external_core.decode('utf-8'),'pinned_alex_sources_lossless','exec'),globals())\n"
    else:nb['cells'].append(code(late))
    for c in nb['cells']:
        if c['cell_type']=='code':compile(source(c),'external_overlay_stage','exec');c['execution_count']=None;c['outputs']=[]
    untouched=all(source(a)==source(b) for i,(a,b) in enumerate(zip(original['cells'],nb['cells'])) if kind!='public_alex' or i not in [12,24])
    if not untouched:raise ValueError('An unintended original source cell changed')
    stage.mkdir(parents=True);write(stage/'notebook.ipynb',nb);write(stage/'kernel-metadata.json',metadata);(stage/'recipe.json').write_bytes(recipe_raw)
    static=dict(status='passed',target=target,version=1,notebook_sha256=sha(stage/'notebook.ipynb'),checks=dict(
        all_original_unadapted_cells_exact=untouched,original_overlay_function_pinned=True,only_observation_ast_additions=True,
        explicit_official_identity_output_guard=True,exact_ranking_constants=True,all_required_library_hashes_local=True,
        dynamic_hidden_ids=True,fast_visible_no_models_or_matching=True,private_offline_gpu=True,versioned_dataset_sources=True,
        source_compiles=True,never_executes_external_pickle=True,global_errors_fail_closed=True))
    write(stage/'static_review.json',static)
    receipt=dict(status='prepared',branch=name,target=target,version=1,notebook_sha256=sha(stage/'notebook.ipynb'),metadata_sha256=sha(stage/'kernel-metadata.json'),recipe_sha256=recipe_sha,static_review_path=str((stage/'static_review.json').relative_to(ROOT)).replace('\\','/'),validation_mode='fast_static')
    write(stage/'prepare_receipt.json',receipt)
    base_audits.append(dict(name='external_overlay_audit.json',expected_fields=dict(status='passed',branch=name,recipe_sha256=recipe_sha,mode='fast_static'),required_true_checks=['base_audit_passed','control_bound','final_bound','source_function_pin','exact_ids_schema','official_identities_valid','library_file_pins','runtime_checks','fast_no_matching']))
    branch=dict(name=name,target=target,version=1,stage_dir=str(stage.relative_to(ROOT)).replace('\\','/'),notebook_sha256=receipt['notebook_sha256'],metadata_sha256=receipt['metadata_sha256'],description='CASMI26 20261109 '+('AlexV12 measured library reproduction' if kind=='public_alex' else 'our .482 plus measured library only')+' audited V1',validation_mode='fast_static',static_review_path=receipt['static_review_path'],required_runtime_audits=base_audits)
    write(stage/'branch_spec.json',branch);print(json.dumps(receipt,indent=2));return receipt


def main():
    if sha(ALEX)!=ALEX_SHA or sha(GUARDED/'notebook.ipynb')!=GUARDED_SHA:raise ValueError('Base source changed')
    nb=read(ALEX);text=source(nb['cells'][24]);tree=ast.parse(text)
    fn=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='_apex_extlib_overlay')
    original_function=ast.get_source_segment(text,fn)+'\n'
    constants={n.targets[0].id:ast.literal_eval(n.value) for n in fn.body if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id in ('TAU','K_PEAKS','LIB_TAU')}
    if constants!=dict(TAU=.80,K_PEAKS=4,LIB_TAU=.90):raise ValueError('Original match constants differ')
    downloads=read(ROOT/'reports/public_baseline_scan_20261109_design/library_downloads.json')
    if downloads.get('all_verified') is not True or len(downloads['files'])!=5:raise ValueError('Missing downloaded source pins')
    files=[]
    for item in downloads['files']:
        path=ROOT/item['path']
        if path.stat().st_size!=item['bytes'] or sha(path)!=item['sha256']:raise ValueError('Local library changed')
        files.append({k:item[k] for k in ['ref','version','file','bytes','sha256']})
    prepare('public_alex_extlib','public_alex',original_function,files)
    prepare('mass_guarded_extlib','guarded_482',original_function,files)


if __name__=='__main__':main()
