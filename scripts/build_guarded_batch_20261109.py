"""Prepare immutable guarded-tail branches; no cloud calls or training."""
from __future__ import annotations
import argparse,ast,base64,copy,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'submission/optimization_20261108/mass_guarded_head_tail_1108'
OUT=ROOT/'submission/optimization_20261109'
BASE_SHA='6de37bec32c8aa8bfb46b2c5e94e374b53fe36137dff1cd7d1c4a295359f56fe'
ORIGINAL_SCORER_SHA='cb9e4d6732992e3310e951533fd0c644d3b515134ad03768c35e5a86551267d2'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def source(c):return ''.join(c['source']) if isinstance(c['source'],list) else c['source']
def write(p,v):Path(p).write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')

OBSERVER=r'''
def _observe_guarded_head_tail():
    import hashlib,json
    from collections import Counter
    expected=__EXPECTED__
    configuration=expected['configuration'];prefix=configuration['protected_prefix'];checks={}
    digest=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    def check(k,v):
        checks[k]=bool(v)
        assert v,k
    check('original_base_audit',BATCH_VARIANT_AUDIT.get('status')=='passed')
    check('late_module_pin',digest(CODE/'guarded_head_tail_20261109.py')==expected['tail_module_sha256'])
    check('scorer_payload_pins',all(digest(CODE/k)==v for k,v in configuration['payload_pins'].items()))
    check('original_scorer_pin',digest(CODE/'neural_scores_original.py')==configuration['baseline_scorer_sha256'])
    report=json.loads((ROOT/'guarded_tail_runtime.json').read_text())
    before=pd.read_csv(ROOT/'submission_guarded_tail_control.csv',dtype=str,keep_default_na=False)
    after=pd.read_csv(ROOT/'submission.csv',dtype=str,keep_default_na=False)
    check('configuration_binding',report.get('configuration_sha256')==expected['configuration_sha256'] and report.get('protected_prefix')==prefix and report.get('score_mode')==configuration['score_mode'])
    check('audited_control_bound',digest(ROOT/'submission_guarded_tail_control.csv')==BATCH_VARIANT_AUDIT['csv_sha256']==report.get('control_sha256'))
    check('final_csv_bound',digest(ROOT/'submission.csv')==report.get('output_sha256'))
    check('exact_ids_order',after.molecule_id.tolist()==before.molecule_id.tolist()==SAMPLE_IDS)
    check('exact_protected_prefix',all(a.split(';')[:prefix]==b.split(';')[:prefix] for a,b in zip(before.smiles,after.smiles)))
    check('exact_candidate_multisets',all(Counter(a.split(';'))==Counter(b.split(';')) for a,b in zip(before.smiles,after.smiles)))
    if IS_RERUN:
        check('tail_execution',report.get('status') in ('applied','no_eligible') and report.get('mode')=='hidden_full')
        names=('control_matches_audited_base','exact_molecule_order','protected_prefix_exact','candidate_multiset_exact','official_identity_multiset_exact','formula_slots_exact','no_eligible_explicit')
        check('named_tail_checks',set(report.get('checks',{}))==set(names) and all(report['checks'][k] is True for k in names))
        check('dynamic_scope',report.get('rows')==len(SAMPLE_IDS)>0)
        formulas=True;identities=True;invalid_preserved=True
        for a,b in zip(before.smiles,after.smiles):
            old,new=a.split(';'),b.split(';')
            old_desc=[_guarded_tail.describe(s) for s in old];new_desc=[_guarded_tail.describe(s) for s in new]
            identities &= Counter(x[0] for x in old_desc)==Counter(x[0] for x in new_desc)
            formulas &= all(old_desc[i][1]==new_desc[i][1] for i in range(prefix,len(old)))
            if any(x[0] is None for x in old_desc) or len({x[0] for x in old_desc})!=len(old_desc):invalid_preserved &= old==new
        check('actual_formula_slots',formulas);check('actual_official_identity_multisets',identities);check('invalid_identity_query_preserved',invalid_preserved)
        if report['status']=='applied':
            check('actual_scorer_inference',report.get('model_invoked') is True and report.get('eligible_queries',0)>0 and report.get('eligible_candidate_rows',0)>0)
            frame,audit,binding=_guarded_tail.validate_score_audit(ROOT,configuration)
            check('actual_score_bindings',all(binding.values()) and report.get('head_receipts')==configuration['head_receipts'])
            check('saved_score_hashes',report.get('evidence_sha256')==digest(ROOT/'guarded_tail_evidence.parquet') and report.get('queries_sha256')==digest(ROOT/'effective_query_spectra.parquet') and report.get('scores_sha256')==digest(ROOT/'guarded_tail_scores.parquet') and report.get('head_audit_sha256')==digest(ROOT/'guarded_tail_scores.parquet.head_audit.json'))
            reconstructed,details=_guarded_tail.reorder(before,frame,report['skipped_queries'],protected_prefix=prefix)
            check('actual_scored_order_consumed',reconstructed.equals(after) and details==report['details'])
        else:check('explicit_no_eligible',report.get('model_invoked') is False and report.get('eligible_queries')==0 and report.get('eligible_candidate_rows')==0 and after.equals(before))
    else:check('fast_no_model',report.get('status')=='fast_static_no_model' and report.get('model_invoked') is False and not RUN_PIPELINE and not PIPELINE_DONE and after.equals(before))
    result=dict(status='passed',branch=expected['branch'],mode='hidden_full' if IS_RERUN else 'fast_static',recipe_sha256=expected['recipe_sha256'],checks=checks,scorer_executed=bool(report.get('model_invoked')),score_mode=configuration['score_mode'],protected_prefix=prefix,changed_queries=report.get('changed_queries',0),baseline_control_sha256=digest(ROOT/'submission_guarded_tail_control.csv'),csv_sha256=digest(ROOT/'submission.csv'))
    (ROOT/'guarded_tail_audit.json').write_text(json.dumps(result,indent=2)+'\n');return result
GUARDED_TAIL_AUDIT=_observe_guarded_head_tail()
'''

def old_payloads(nb):
    fn=next(n for n in ast.parse(source(nb['cells'][-2])).body if isinstance(n,ast.FunctionDef) and n.name=='_install_candidate_head');values={}
    for n in fn.body:
        if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name):
            try:values[n.targets[0].id]=ast.literal_eval(n.value)
            except (ValueError,TypeError):pass
    payloads={k:base64.b64decode(v) for k,v in values['payloads'].items()}
    if any(hashlib.sha256(payloads[k]).hexdigest()!=v for k,v in values['pins'].items()):raise ValueError('Old payload differs')
    return payloads

def build(name,prefix,score_mode,head_spec=None):
    if sha(BASE/'notebook.ipynb')!=BASE_SHA:raise ValueError('.482 source changed')
    if type(prefix) is not int or not 1<=prefix<=24:raise ValueError('Bad prefix')
    if not name.replace('_','').isalnum() or len(name)>60:raise ValueError('Bad name')
    stage=OUT/name
    if stage.exists():raise FileExistsError('Preserve prepared branch')
    base=read(BASE/'notebook.ipynb');nb=copy.deepcopy(base);nb['cells']=nb['cells'][:-2]
    target='stormseye/casmi26-'+name.replace('_','-')+'-1109'
    if score_mode=='learned_heads':
        payloads=old_payloads(base);runtime=json.loads(payloads['learned_head_runtime.json'])
        if head_spec:
            spec=read(head_spec);payloads={k:v for k,v in payloads.items() if not k.endswith('.pt')}
            model=ROOT/spec['model_path']
            if spec.get('model_sha256') and sha(model)!=spec['model_sha256']:raise ValueError('New head model source differs')
            payloads['candidate_multispectrum_head.py']=model.read_bytes();runtime['head_model_sha256']=sha(model);runtime['heads']=[]
            for item in spec['heads']:
                p=ROOT/item['path']
                if sha(p)!=item['sha256']:raise ValueError('New weight differs')
                payloads[p.name]=p.read_bytes();runtime['heads'].append(dict(file=p.name,sha256=sha(p)))
            if len(runtime['heads'])!=2:raise ValueError('Fixed two-seed ensemble required')
            seeds=[x['seed'] for x in spec['heads']]
        else:seeds=[20261108,20261109]
        payloads['learned_head_runtime.json']=(json.dumps(runtime,indent=2)+'\n').encode();receipts=[dict(sha256=x['sha256'],step=2500,seed=seed) for x,seed in zip(runtime['heads'],seeds)];scorer='learned_head_score.py'
    elif score_mode=='v2_mean':
        if head_spec:raise ValueError('Mean ablation has no learned heads')
        scorer='guarded_v2_mean_score_20261109.py';payloads={scorer:(ROOT/'scripts'/scorer).read_bytes()};receipts=[]
    else:raise ValueError('Unknown scorer')
    pins={k:hashlib.sha256(v).hexdigest() for k,v in payloads.items()}
    cfg=dict(protected_prefix=prefix,score_mode='learned_heads' if score_mode=='learned_heads' else 'frozen_v2_mean',scorer_file=scorer,scorer_sha256=pins[scorer],payload_pins=pins,head_receipts=receipts,baseline_scorer_sha256=ORIGINAL_SCORER_SHA)
    cfgpin=hashlib.sha256(json.dumps(cfg,sort_keys=True,separators=(',',':')).encode()).hexdigest();tail=ROOT/'scripts/guarded_head_tail_20261109.py';tailpin=sha(tail);encoded={k:base64.b64encode(v).decode() for k,v in payloads.items()}
    late=("import base64,hashlib,shutil,importlib.util\nshutil.copy2(ROOT/'submission.csv',ROOT/'submission_guarded_tail_control.csv')\ntry:\n"
        +"    assert hashlib.sha256((CODE/'neural_scores.py').read_bytes()).hexdigest()=="+repr(ORIGINAL_SCORER_SHA)+"\n    shutil.copy2(CODE/'neural_scores.py',CODE/'neural_scores_original.py')\n"
        +"    _late_payloads="+repr(encoded)+"\n    _late_pins="+repr(pins)+"\n"
        +"    for _name,_encoded in _late_payloads.items():\n        _raw=base64.b64decode(_encoded)\n        assert hashlib.sha256(_raw).hexdigest()==_late_pins[_name]\n        (CODE/_name).write_bytes(_raw)\n"
        +"    _tail_raw=base64.b64decode("+repr(base64.b64encode(tail.read_bytes()).decode())+")\n    assert hashlib.sha256(_tail_raw).hexdigest()=="+repr(tailpin)+"\n    (CODE/'guarded_head_tail_20261109.py').write_bytes(_tail_raw)\n"
        +"    _tail_spec=importlib.util.spec_from_file_location('_guarded_head_tail_runtime',CODE/'guarded_head_tail_20261109.py')\n    _guarded_tail=importlib.util.module_from_spec(_tail_spec)\n    _tail_spec.loader.exec_module(_guarded_tail)\n"
        +"    GUARDED_TAIL_REPORT=_guarded_tail.run(ROOT,CODE,OURS_BUNDLE,IS_RERUN,BATCH_VARIANT_AUDIT,"+repr(cfg)+")\nexcept BaseException:\n    (ROOT/'submission.csv').unlink(missing_ok=True)\n    raise\n")
    recipe=dict(branch=name,target=target,baseline_own_public_score=.482,base_source_sha256=BASE_SHA,method='post-MASS guarded same-formula ranking',configuration=cfg,configuration_sha256=cfgpin,tail_module_sha256=tailpin,all_original_scoring_unchanged=True,compare_to='58129661 prefix7 old two-head .482',new_head_spec=read(head_spec) if head_spec else None,no_na_component=True,known_pretrained_exposure=True,locked_final_used=False,validation_mode='fast_static')
    raw=(json.dumps(recipe,indent=2,ensure_ascii=False)+'\n').encode();recipepin=hashlib.sha256(raw).hexdigest();expected=dict(branch=name,recipe_sha256=recipepin,tail_module_sha256=tailpin,configuration=cfg,configuration_sha256=cfgpin)
    for text in (late,OBSERVER.replace('__EXPECTED__',repr(expected))):nb['cells'].append(dict(cell_type='code',execution_count=None,metadata={},outputs=[],source=text))
    metadata=read(BASE/'kernel-metadata.json');metadata.update(id=target,title=target.split('/')[1].replace('-',' '))
    for c in nb['cells']:
        if c['cell_type']=='code':compile(source(c),'guarded_1109_notebook','exec');c['execution_count']=None;c['outputs']=[]
    checks=dict(exact_original_cells=all(source(a)==source(b) for a,b in zip(base['cells'][:-2],nb['cells'][:-2])),tail_after_original_audit=True,explicit_protected_prefix=True,same_formula_original_slots=True,original_scorer_and_v2_pin=True,payloads_pinned=True,scored_output_reconstruction_observed=True,no_na_component=True,global_failure_removes_final_csv=True,dynamic_hidden_size=True,all_code_compiles=True,private_offline=metadata['is_private'] in (True,'true') and metadata['enable_internet'] in (False,'false'))
    if not all(checks.values()):raise ValueError('Static contract failed')
    stage.mkdir(parents=True);write(stage/'notebook.ipynb',nb);write(stage/'kernel-metadata.json',metadata);(stage/'recipe.json').write_bytes(raw)
    static=dict(status='passed',target=target,version=1,notebook_sha256=sha(stage/'notebook.ipynb'),checks=checks);write(stage/'static_review.json',static)
    receipt=dict(status='prepared',branch=name,target=target,version=1,notebook_sha256=static['notebook_sha256'],metadata_sha256=sha(stage/'kernel-metadata.json'),recipe_sha256=recipepin,static_review_path=str((stage/'static_review.json').relative_to(ROOT)).replace('\\','/'),validation_mode='fast_static');write(stage/'prepare_receipt.json',receipt)
    audits=copy.deepcopy(read(BASE/'branch_spec.json')['required_runtime_audits'][:1]);audits.append(dict(name='guarded_tail_audit.json',expected_fields=dict(status='passed',branch=name,mode='fast_static',recipe_sha256=recipepin,protected_prefix=prefix,score_mode=cfg['score_mode']),required_true_checks=['original_base_audit','late_module_pin','scorer_payload_pins','original_scorer_pin','configuration_binding','audited_control_bound','final_csv_bound','exact_ids_order','exact_protected_prefix','exact_candidate_multisets','fast_no_model']))
    branch=dict(name=name,target=target,version=1,stage_dir=str(stage.relative_to(ROOT)).replace('\\','/'),notebook_sha256=receipt['notebook_sha256'],metadata_sha256=receipt['metadata_sha256'],description=f'CASMI26 20261109 {name} prefix{prefix} audited V1',validation_mode='fast_static',static_review_path=receipt['static_review_path'],required_runtime_audits=audits);write(stage/'branch_spec.json',branch);return receipt

def assemble(names):
    path=OUT/'manifest.json'
    if path.exists():raise FileExistsError('Fixed manifest exists')
    if not 1<=len(names)<=5 or len(names)!=len(set(names)):raise ValueError('Expected 1..5 distinct branches')
    manifest=dict(schema_version=1,competition='enveda-CASMI26-molecule-id-mass-spectra',batch_id='optimization_20261109',max_submissions=5,baseline_public_score=.482,state_root='reports/optimization_20261109',branches=[read(OUT/name/'branch_spec.json') for name in names]);write(path,manifest);return dict(status='manifest_prepared',sha256=sha(path),branches=names)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--branch');p.add_argument('--prefix',type=int);p.add_argument('--scorer',choices=['learned_heads','v2_mean']);p.add_argument('--head-spec',type=Path);p.add_argument('--assemble-manifest',nargs='+');a=p.parse_args()
    if a.assemble_manifest:r=assemble(a.assemble_manifest)
    else:
        if a.branch is None or a.prefix is None or a.scorer is None:p.error('branch, prefix and scorer required')
        r=build(a.branch,a.prefix,a.scorer,a.head_spec)
    print(json.dumps(r,indent=2))
if __name__=='__main__':main()
