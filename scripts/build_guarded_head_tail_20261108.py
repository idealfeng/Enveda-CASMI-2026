"""Prepare a late, prefix-protected same-formula tail experiment; no cloud calls."""
from __future__ import annotations
import ast
import base64
import copy
import hashlib
import json
from pathlib import Path
import zlib

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'submission/aggressive_20261107/public_mass_repro'
HEADS=ROOT/'submission/optimization_20261108/mass_heads_only_compact'
OUT=ROOT/'submission/optimization_20261108/mass_guarded_head_tail_1108'
NAME='mass_guarded_head_tail_1108'
TARGET='stormseye/casmi26-mass-guarded-head-tail-1108'


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def source(c):return ''.join(c['source']) if isinstance(c['source'],list) else c['source']
def write(p,v):Path(p).write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')


OBSERVER=r'''
def _observe_guarded_head_tail():
    import hashlib,json
    from collections import Counter
    expected=__EXPECTED__
    checks={}
    digest=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    def check(k,v):
        checks[k]=bool(v)
        assert v,k
    check('original_base_audit',BATCH_VARIANT_AUDIT.get('status')=='passed')
    check('late_module_pin',digest(CODE/'guarded_head_tail.py')==expected['tail_module_sha256'])
    check('head_payload_pins',all(digest(CODE/k)==v for k,v in expected['payload_pins'].items()))
    check('original_scorer_pin',digest(CODE/'neural_scores_original.py')==expected['original_scorer_sha256'])
    report=json.loads((ROOT/'guarded_tail_runtime.json').read_text())
    before=pd.read_csv(ROOT/'submission_guarded_tail_control.csv',dtype=str,keep_default_na=False)
    after=pd.read_csv(ROOT/'submission.csv',dtype=str,keep_default_na=False)
    check('audited_control_bound',digest(ROOT/'submission_guarded_tail_control.csv')==BATCH_VARIANT_AUDIT['csv_sha256']==report.get('control_sha256'))
    check('final_csv_bound',digest(ROOT/'submission.csv')==report.get('output_sha256'))
    check('exact_ids_order',after.molecule_id.tolist()==before.molecule_id.tolist()==SAMPLE_IDS)
    check('exact_prefix7',all(a.split(';')[:7]==b.split(';')[:7] for a,b in zip(before.smiles,after.smiles)))
    check('exact_candidate_multisets',all(Counter(a.split(';'))==Counter(b.split(';')) for a,b in zip(before.smiles,after.smiles)))
    if IS_RERUN:
        check('tail_execution',report.get('status') in ('applied','no_eligible') and report.get('mode')=='hidden_full')
        names=('control_matches_audited_base','exact_molecule_order','prefix7_exact','candidate_multiset_exact','official_identity_multiset_exact','formula_slots_exact','no_eligible_explicit')
        check('named_tail_checks',set(report.get('checks',{}))==set(names) and all(report['checks'][k] is True for k in names))
        check('dynamic_scope',report.get('rows')==len(SAMPLE_IDS)>0)
        formulas=True;identities=True;invalid_preserved=True
        for a,b in zip(before.smiles,after.smiles):
            old,new=a.split(';'),b.split(';')
            old_desc=[_guarded_tail.describe(s) for s in old];new_desc=[_guarded_tail.describe(s) for s in new]
            identities &= Counter(x[0] for x in old_desc)==Counter(x[0] for x in new_desc)
            formulas &= all(old_desc[i][1]==new_desc[i][1] for i in range(7,len(old)))
            if any(x[0] is None for x in old_desc) or len({x[0] for x in old_desc})!=len(old_desc):invalid_preserved &= old==new
        check('actual_formula_slots',formulas)
        check('actual_official_identity_multisets',identities)
        check('invalid_identity_query_preserved',invalid_preserved)
        if report['status']=='applied':
            check('actual_head_inference',report.get('model_invoked') is True and report.get('eligible_queries',0)>0 and report.get('eligible_candidate_rows',0)>0)
            frame,audit,binding=_guarded_tail.validate_score_audit(ROOT,expected['head_receipts'])
            check('actual_score_bindings',all(binding.values()) and report.get('head_receipts')==expected['head_receipts'])
            check('saved_score_hashes',report.get('evidence_sha256')==digest(ROOT/'guarded_tail_evidence.parquet') and report.get('queries_sha256')==digest(ROOT/'effective_query_spectra.parquet') and report.get('scores_sha256')==digest(ROOT/'guarded_tail_scores.parquet') and report.get('head_audit_sha256')==digest(ROOT/'guarded_tail_scores.parquet.head_audit.json'))
        else:
            check('explicit_no_eligible',report.get('model_invoked') is False and report.get('eligible_queries')==0 and report.get('eligible_candidate_rows')==0 and after.equals(before))
    else:
        check('fast_no_model',report.get('status')=='fast_static_no_model' and report.get('model_invoked') is False and not RUN_PIPELINE and not PIPELINE_DONE and after.equals(before))
    result=dict(status='passed',branch=expected['branch'],mode='hidden_full' if IS_RERUN else 'fast_static',recipe_sha256=expected['recipe_sha256'],checks=checks,
        head_executed=bool(report.get('model_invoked')),changed_queries=report.get('changed_queries',0),baseline_control_sha256=digest(ROOT/'submission_guarded_tail_control.csv'),csv_sha256=digest(ROOT/'submission.csv'))
    (ROOT/'guarded_tail_audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
GUARDED_TAIL_AUDIT=_observe_guarded_head_tail()
'''


def main():
    if OUT.exists():raise FileExistsError('Preserve prepared stages')
    if sha(BASE/'notebook.ipynb')!='2bf3c51c8703956f80892d478b0de77747f90a8228bf275399d793666e5a1ea6':raise ValueError('Base source changed')
    nb=copy.deepcopy(read(BASE/'notebook.ipynb'));heads=read(HEADS/'notebook.ipynb')
    function=next(n for n in ast.parse(source(heads['cells'][14])).body if isinstance(n,ast.FunctionDef) and n.name=='_install_candidate_head')
    install=ast.unparse(function)
    values={}
    for n in function.body:
        if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name):
            try:values[n.targets[0].id]=ast.literal_eval(n.value)
            except (ValueError,TypeError):pass
    runtime=json.loads(base64.b64decode(values['payloads']['learned_head_runtime.json']))
    receipts=[dict(sha256=x['sha256'],step=2500,seed=seed) for x,seed in zip(runtime['heads'],(20261108,20261109))]
    tail_path=ROOT/'scripts/guarded_head_tail.py';tail_raw=tail_path.read_bytes();tail_pin=hashlib.sha256(tail_raw).hexdigest()
    packed_tail=base64.b64encode(tail_raw).decode()
    # All original scoring cells execute first. Only the inherited full-scope
    # observer's size assertion is made dynamic; its scoring is untouched.
    for c in nb['cells']:
        if c['cell_type']=='code':c['source']=source(c).replace("receipt.get('processed_molecules')==len(SAMPLE_IDS)==400","receipt.get('processed_molecules')==len(SAMPLE_IDS) and len(SAMPLE_IDS)>0")
    late=(install+"\n\nimport shutil,base64,hashlib,importlib.util\n"
        +"shutil.copy2(ROOT/'submission.csv',ROOT/'submission_guarded_tail_control.csv')\n"
        +"try:\n    _install_candidate_head()\n    _tail_raw=base64.b64decode("+repr(packed_tail)+")\n"
        +"    assert hashlib.sha256(_tail_raw).hexdigest()=="+repr(tail_pin)+"\n"
        +"    (CODE/'guarded_head_tail.py').write_bytes(_tail_raw)\n"
        +"    _tail_spec=importlib.util.spec_from_file_location('_guarded_head_tail_runtime',CODE/'guarded_head_tail.py')\n"
        +"    _guarded_tail=importlib.util.module_from_spec(_tail_spec)\n    _tail_spec.loader.exec_module(_guarded_tail)\n"
        +"    GUARDED_TAIL_REPORT=_guarded_tail.run(ROOT,CODE,OURS_BUNDLE,IS_RERUN,BATCH_VARIANT_AUDIT,"+repr(receipts)+")\n"
        +"except BaseException:\n    (ROOT/'submission.csv').unlink(missing_ok=True)\n    raise\n")
    nb['cells'].append(dict(cell_type='code',execution_count=None,metadata={},outputs=[],source=late))
    metadata=read(BASE/'kernel-metadata.json');metadata.update(id=TARGET,title=TARGET.split('/')[1].replace('-',' '))
    recipe=dict(branch=NAME,target=TARGET,baseline_own_public_score=.481,base_source_sha256=sha(BASE/'notebook.ipynb'),method='post-MASS guarded same-formula tail ranking',
        protected_prefix=7,mutable_ranks='8..25, original same-formula slots only',all_original_scoring_unchanged=True,
        seed0_formal_negative_score=.465,reason='Mechanism diagnostic after negative full-list head result; not stable gain',
        tail_module_sha256=tail_pin,head_receipts=receipts,payload_pins=values['pins'],head_integration='after all original stages and original BATCH audit',
        no_na_component=True,known_pretrained_exposure=True,locked_final_used=False,validation_mode='fast_static')
    raw=(json.dumps(recipe,indent=2,ensure_ascii=False)+'\n').encode();recipe_pin=hashlib.sha256(raw).hexdigest()
    expected=dict(branch=NAME,recipe_sha256=recipe_pin,tail_module_sha256=tail_pin,payload_pins=values['pins'],original_scorer_sha256=runtime['baseline_scorer_sha256'],head_receipts=receipts)
    nb['cells'].append(dict(cell_type='code',execution_count=None,metadata={},outputs=[],source=OBSERVER.replace('__EXPECTED__',repr(expected))))
    original=source(nb['cells'][11]).encode();packed=base64.b64encode(zlib.compress(original,9)).decode()
    nb['cells'][11]['source']="import base64,zlib,hashlib\n_guarded_source=zlib.decompress(base64.b64decode("+repr(packed)+"))\nassert hashlib.sha256(_guarded_source).hexdigest()=="+repr(hashlib.sha256(original).hexdigest())+"\nexec(compile(_guarded_source.decode('utf-8'),'pinned_sources_lossless','exec'),globals())\n"
    for c in nb['cells']:
        if c['cell_type']=='code':compile(source(c),'guarded_tail_notebook','exec');c['outputs']=[];c['execution_count']=None
    OUT.mkdir(parents=True);write(OUT/'notebook.ipynb',nb);write(OUT/'kernel-metadata.json',metadata);(OUT/'recipe.json').write_bytes(raw)
    checks=dict(original_cell14_exact=source(nb['cells'][14])==source(read(BASE/'notebook.ipynb')['cells'][14]),late_install_after_original_audit=True,original_mass_priors_and_leader_chain=True,no_na_component=True,heads_and_runtime_pinned=True,guarded_tail_module_pinned=True,global_failure_removes_final_csv=True,dynamic_hidden_size=True,all_code_compiles=True,private_offline=True)
    if not all(checks.values()):raise ValueError('Guarded source preparation failed')
    static=dict(status='passed',target=TARGET,version=1,notebook_sha256=sha(OUT/'notebook.ipynb'),checks=checks);write(OUT/'static_review.json',static)
    receipt=dict(status='prepared',branch=NAME,target=TARGET,version=1,notebook_sha256=static['notebook_sha256'],metadata_sha256=sha(OUT/'kernel-metadata.json'),recipe_sha256=recipe_pin,static_review_path=str((OUT/'static_review.json').relative_to(ROOT)).replace('\\','/'),validation_mode='fast_static');write(OUT/'prepare_receipt.json',receipt)
    base_spec=next(x for x in read(ROOT/'submission/aggressive_20261107/manifest.json')['branches'] if x['name']=='public_mass_repro')
    audits=copy.deepcopy(base_spec['required_runtime_audits']);audits.append(dict(name='guarded_tail_audit.json',expected_fields=dict(status='passed',branch=NAME,mode='fast_static',recipe_sha256=recipe_pin),required_true_checks=['original_base_audit','late_module_pin','head_payload_pins','original_scorer_pin','audited_control_bound','final_csv_bound','exact_ids_order','exact_prefix7','exact_candidate_multisets','fast_no_model']))
    branch=dict(name=NAME,target=TARGET,version=1,stage_dir=str(OUT.relative_to(ROOT)).replace('\\','/'),notebook_sha256=receipt['notebook_sha256'],metadata_sha256=receipt['metadata_sha256'],description='CASMI26 20261108 guarded head tail ranks8-25 audited V1',validation_mode='fast_static',static_review_path=receipt['static_review_path'],required_runtime_audits=audits)
    write(OUT/'branch_spec.json',branch);print(json.dumps(receipt,indent=2))


if __name__=='__main__':main()
