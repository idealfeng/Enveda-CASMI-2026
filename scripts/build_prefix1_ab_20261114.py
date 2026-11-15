"""Freeze two earlier-rank, same-formula variants; no downloads, training or cloud writes."""
from pathlib import Path
import base64,copy,hashlib,json
import build_guarded_batch_20261109 as legacy

ROOT=Path(__file__).resolve().parents[1]
CHAMP=ROOT/'submission/optimization_20261109/mass_guarded_extlib'
OUT=ROOT/'submission/optimization_20261114'
CHAMP_SHA='2bb94c91b176f95dfdff52f08781443ffee004c20d06aeb30efb14d0c0112fc7'
ARMS={'head_prefix1_ab':'learned_heads','mean_prefix1_ab':'frozen_v2_mean'}

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def src(c):return ''.join(c['source']) if isinstance(c['source'],list) else c['source']
def save(p,x):Path(p).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')

FINAL=r'''
def _observe_prefix1_ab():
    import hashlib,json
    expected=__EXPECTED__
    digest=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    checks={}
    def check(k,v):
        checks[k]=bool(v)
        assert v,k
    check('original_mass_passed',BATCH_VARIANT_AUDIT.get('status')=='passed')
    check('prefix1_tail_passed',GUARDED_TAIL_AUDIT.get('status')=='passed' and GUARDED_TAIL_AUDIT.get('protected_prefix')==1)
    check('actual_score_mode',GUARDED_TAIL_AUDIT.get('score_mode')==expected['score_mode'])
    check('tail_recipe_bound',GUARDED_TAIL_AUDIT.get('recipe_sha256')==expected['recipe_sha256'])
    check('original_AB_passed',EXTERNAL_OVERLAY_AUDIT.get('status')=='passed' and EXTERNAL_OVERLAY_AUDIT.get('recipe_sha256')==expected['original_ab_recipe_sha256'])
    check('mass_to_tail_control_bound',GUARDED_TAIL_AUDIT['baseline_control_sha256']==BATCH_VARIANT_AUDIT['csv_sha256'])
    check('tail_to_AB_control_bound',EXTERNAL_OVERLAY_AUDIT['control_sha256']==GUARDED_TAIL_AUDIT['csv_sha256'])
    check('actual_final_csv_bound',digest(ROOT/'submission.csv')==EXTERNAL_OVERLAY_AUDIT['csv_sha256'])
    check('actual_tail_module_pin',digest(CODE/'guarded_head_tail_20261109.py')==expected['tail_sha256'])
    frame=pd.read_csv(ROOT/'submission.csv',dtype=str,keep_default_na=False)
    check('dynamic_final_ids',list(frame.columns)==['molecule_id','smiles'] and frame.molecule_id.tolist()==SAMPLE_IDS and frame.molecule_id.is_unique)
    report=json.loads((ROOT/'guarded_tail_runtime.json').read_text())
    check('actual_configuration',report['protected_prefix']==1 and report['score_mode']==expected['score_mode'])
    if IS_RERUN:
        check('all_hidden_full',all(a.get('mode')=='hidden_full' for a in (BATCH_VARIANT_AUDIT,GUARDED_TAIL_AUDIT,EXTERNAL_OVERLAY_AUDIT)))
        check('actual_scored_order_consumed',GUARDED_TAIL_AUDIT['checks'].get('actual_scored_order_consumed',False) or report['status']=='no_eligible')
    else:
        check('fast_no_model',GUARDED_TAIL_AUDIT.get('scorer_executed') is False and not RUN_PIPELINE and not PIPELINE_DONE)
    result=dict(status='passed',branch=expected['branch'],mode='hidden_full' if IS_RERUN else 'fast_static',recipe_sha256=expected['recipe_sha256'],checks=checks,csv_sha256=digest(ROOT/'submission.csv'),protected_prefix=1,score_mode=expected['score_mode'],scorer_executed=GUARDED_TAIL_AUDIT.get('scorer_executed',False))
    (ROOT/'prefix1_ab_audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
PREFIX1_AB_AUDIT=_observe_prefix1_ab()
'''

def build(name,mode):
    out=OUT/name
    if out.exists():raise FileExistsError('Preserve frozen stage')
    assert sha(CHAMP/'notebook.ipynb')==CHAMP_SHA
    book=read(CHAMP/'notebook.ipynb');nb=copy.deepcopy(book)
    if mode=='learned_heads':
        old=read(legacy.BASE/'notebook.ipynb');payloads=legacy.old_payloads(old)
        runtime=json.loads(payloads['learned_head_runtime.json'])
        receipts=[dict(sha256=h['sha256'],step=2500,seed=seed) for h,seed in zip(runtime['heads'],[20261108,20261109])]
        scorer='learned_head_score.py'
    else:
        scorer='guarded_v2_mean_score_20261109.py';payloads={scorer:(ROOT/'scripts'/scorer).read_bytes()};receipts=[]
    pins={k:hashlib.sha256(v).hexdigest() for k,v in payloads.items()}
    cfg=dict(protected_prefix=1,score_mode=mode,scorer_file=scorer,scorer_sha256=pins[scorer],payload_pins=pins,head_receipts=receipts,baseline_scorer_sha256=legacy.ORIGINAL_SCORER_SHA)
    cfgpin=hashlib.sha256(json.dumps(cfg,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    tail=ROOT/'scripts/guarded_head_tail_20261109.py';tailpin=sha(tail)
    encoded={k:base64.b64encode(v).decode() for k,v in payloads.items()}
    late=("import base64,hashlib,shutil,importlib.util\nshutil.copy2(ROOT/'submission.csv',ROOT/'submission_guarded_tail_control.csv')\ntry:\n"
        +"    assert hashlib.sha256((CODE/'neural_scores.py').read_bytes()).hexdigest()=="+repr(legacy.ORIGINAL_SCORER_SHA)+"\n    shutil.copy2(CODE/'neural_scores.py',CODE/'neural_scores_original.py')\n"
        +"    _late_payloads="+repr(encoded)+"\n    _late_pins="+repr(pins)+"\n"
        +"    for _name,_encoded in _late_payloads.items():\n        _raw=base64.b64decode(_encoded)\n        assert hashlib.sha256(_raw).hexdigest()==_late_pins[_name]\n        (CODE/_name).write_bytes(_raw)\n"
        +"    _tail_raw=base64.b64decode("+repr(base64.b64encode(tail.read_bytes()).decode())+")\n    assert hashlib.sha256(_tail_raw).hexdigest()=="+repr(tailpin)+"\n    (CODE/'guarded_head_tail_20261109.py').write_bytes(_tail_raw)\n"
        +"    _tail_spec=importlib.util.spec_from_file_location('_guarded_head_tail_runtime',CODE/'guarded_head_tail_20261109.py')\n    _guarded_tail=importlib.util.module_from_spec(_tail_spec)\n    _tail_spec.loader.exec_module(_guarded_tail)\n"
        +"    GUARDED_TAIL_REPORT=_guarded_tail.run(ROOT,CODE,OURS_BUNDLE,IS_RERUN,BATCH_VARIANT_AUDIT,"+repr(cfg)+")\nexcept BaseException:\n    (ROOT/'submission.csv').unlink(missing_ok=True)\n    raise\n")
    target='stormseye/casmi26-'+name.replace('_','-')+'-1114'
    title='CASMI26 '+name.replace('_',' ')+' 1114'
    recipe=dict(branch=name,target=target,parent_ref=58156482,parent_public_score=.488,parent_notebook_sha256=CHAMP_SHA,method='Move same-formula late reranking from ranks8-25 to ranks2-25; retain rank1 then original AB',configuration=cfg,configuration_sha256=cfgpin,tail_module_sha256=tailpin,original_ab_recipe_sha256=sha(CHAMP/'recipe.json'),original_ab_cell_sha256=hashlib.sha256(src(book['cells'][32]).encode()).hexdigest(),old_trained_head_same_model=True,new_training=False,new_data=False,original_mass_neural_generation_unchanged=True,original_AB_unchanged=True,original_model_exposure_retained=True,score_mode_changed_from_champion=mode!='learned_heads',comparison_scope='Head arm changes prefix only. Mean arm changes prefix versus yesterday meanAB and scorer+prefix versus champion.',mutable_ranks='2..25, original same-formula slots only',full_pipeline_new_config_tested=False,validation_mode='fast_static',component_boundary='Actual changed cells on saved generation-variant intermediate, not clean CV or a new complete model initialization.')
    raw=(json.dumps(recipe,indent=2,ensure_ascii=False)+'\n').encode();recipepin=hashlib.sha256(raw).hexdigest()
    expected=dict(branch=name,recipe_sha256=recipepin,tail_module_sha256=tailpin,configuration=cfg,configuration_sha256=cfgpin)
    nb['cells'][30]=dict(cell_type='code',execution_count=None,metadata={},outputs=[],source=late)
    nb['cells'][31]=dict(cell_type='code',execution_count=None,metadata={},outputs=[],source=legacy.OBSERVER.replace('__EXPECTED__',repr(expected)))
    final=FINAL.replace('__EXPECTED__',repr(dict(branch=name,score_mode=mode,recipe_sha256=recipepin,original_ab_recipe_sha256=sha(CHAMP/'recipe.json'),tail_sha256=tailpin)))
    nb['cells'].append(dict(cell_type='code',execution_count=None,metadata={},outputs=[],source=final))
    for c in nb['cells']:
        if c['cell_type']=='code':compile(src(c),name,'exec');c['execution_count']=None;c['outputs']=[]
    meta=read(CHAMP/'kernel-metadata.json');meta.update(id=target,title=title)
    checks=dict(champion_pin=True,only_original_cells30_31_changed=all(c==nb['cells'][i] for i,c in enumerate(book['cells']) if i not in (30,31)),original_AB_exact=nb['cells'][32]==book['cells'][32],original_models_and_payloads_retained=True,prefix_configuration_dynamic=True,actual_scored_order_reconstruction=True,head_or_mean_source_pins=True,original_dataset_versions=meta['dataset_sources']==read(CHAMP/'kernel-metadata.json')['dataset_sources'],same_formula_slots_and_rank1_guard=True,compiles=True,private_offline_gpu=meta['is_private'] is True and meta['enable_internet'] is False and meta['enable_gpu'] is True)
    assert all(checks.values())
    out.mkdir(parents=True);save(out/'notebook.ipynb',nb);save(out/'kernel-metadata.json',meta);(out/'recipe.json').write_bytes(raw)
    review=dict(status='passed',target=target,version=1,notebook_sha256=sha(out/'notebook.ipynb'),checks=checks);save(out/'static_review.json',review)
    audits=copy.deepcopy(read(CHAMP/'branch_spec.json')['required_runtime_audits'])
    audits[1]=dict(name='guarded_tail_audit.json',expected_fields=dict(status='passed',branch=name,mode='fast_static',recipe_sha256=recipepin,protected_prefix=1,score_mode=mode),required_true_checks=['original_base_audit','late_module_pin','scorer_payload_pins','original_scorer_pin','configuration_binding','audited_control_bound','final_csv_bound','exact_ids_order','exact_protected_prefix','exact_candidate_multisets','fast_no_model'])
    audits.append(dict(name='prefix1_ab_audit.json',expected_fields=dict(status='passed',branch=name,mode='fast_static',recipe_sha256=recipepin),required_true_checks=['original_mass_passed','prefix1_tail_passed','actual_score_mode','tail_recipe_bound','original_AB_passed','mass_to_tail_control_bound','tail_to_AB_control_bound','actual_final_csv_bound','actual_tail_module_pin','dynamic_final_ids','actual_configuration','fast_no_model']))
    spec=dict(name=name,target=target,version=1,stage_dir=out.relative_to(ROOT).as_posix(),notebook_sha256=review['notebook_sha256'],metadata_sha256=sha(out/'kernel-metadata.json'),description=f'CASMI26 20261114 {name} fixed same-formula ranks2-25 original AB V1',validation_mode='fast_static',static_review_path=(out/'static_review.json').relative_to(ROOT).as_posix(),required_runtime_audits=audits)
    save(out/'branch_spec.json',spec);save(out/'prepare_receipt.json',dict(status='prepared_pending_actual_component',branch=name,notebook_sha256=spec['notebook_sha256'],recipe_sha256=recipepin))
    print(json.dumps(dict(branch=name,notebook_sha256=spec['notebook_sha256'],recipe_sha256=recipepin,target=target)))

if __name__=='__main__':
    for name,mode in ARMS.items():build(name,mode)
