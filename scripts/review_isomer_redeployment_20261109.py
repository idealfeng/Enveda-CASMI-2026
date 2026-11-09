"""Prove fresh isomer target differs only in deployment identifiers; CPU only."""
from pathlib import Path
import ast,copy,hashlib,json,shutil,sys
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from review_guarded_batch_20261109 import fixture
from build_guarded_batch_20261109 import source
OLD='mass_guarded_isomer_p7';NEW='mass_guarded_iso_p7b'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def expected(observer):
    fn=next(n for n in ast.parse(observer).body if isinstance(n,ast.FunctionDef))
    assignment=next(n for n in fn.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='expected' for t in n.targets))
    return ast.literal_eval(assignment.value)
def normalized_observer(observer):
    tree=ast.parse(observer);fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef))
    assignment=next(n for n in fn.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='expected' for t in n.targets))
    value=ast.literal_eval(assignment.value);value.pop('branch');value.pop('recipe_sha256');assignment.value=ast.parse(repr(value),mode='eval').body
    return ast.dump(tree,include_attributes=False)

def main():
    oldstage=ROOT/'submission/optimization_20261109'/OLD;newstage=ROOT/'submission/optimization_20261109'/NEW
    oldnb=read(oldstage/'notebook.ipynb');newnb=read(newstage/'notebook.ipynb');oldrecipe=read(oldstage/'recipe.json');newrecipe=read(newstage/'recipe.json')
    out=ROOT/'reports/isomer_redeployment_20261109';out.mkdir(exist_ok=False)
    oldclaim=ROOT/'reports/optimization_20261109'/OLD/'cloud.json'
    oldclaimpin=sha(oldclaim);oldsourcepin=sha(oldstage/'notebook.ipynb')
    oldrun=ROOT/'runs/guarded_batch_actual_canary_20261109'/OLD
    reused=out/'reused_actual_artifacts';shutil.copytree(oldrun,reused)
    # Retain the original run record as historical evidence, without claiming a
    # fresh model invocation against the new deployment identifier.
    (reused/'verification.json').rename(reused/'original_canary_record.json')
    before=pd.read_csv(reused/'submission_guarded_tail_control.csv',dtype=str,keep_default_na=False)
    import importlib.util
    spec=importlib.util.spec_from_file_location('_reused_isomer_tail',reused/'code/guarded_head_tail_20261109.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    base=dict(status='passed',csv_sha256=sha(reused/'submission_guarded_tail_control.csv'))
    scope=dict(ROOT=reused,CODE=reused/'code',Path=Path,pd=pd,BATCH_VARIANT_AUDIT=base,IS_RERUN=True,RUN_PIPELINE=True,PIPELINE_DONE=True,SAMPLE_IDS=before.molecule_id.tolist(),_guarded_tail=module)
    exec(compile(source(newnb['cells'][-1]),'new_deployment_observer_existing_actual_artifacts','exec'),scope)
    newobserver=scope['GUARDED_TAIL_AUDIT']
    oldnormalized=copy.deepcopy(oldrecipe);newnormalized=copy.deepcopy(newrecipe)
    for obj in (oldnormalized,newnormalized):obj.pop('branch');obj.pop('target')
    checks=dict(old_declined_receipt_preserved=sha(oldclaim)==oldclaimpin and read(oldclaim)['status']=='server_response_requires_review_no_retry',
        old_source_preserved=sha(oldstage/'notebook.ipynb')==oldsourcepin,
        fresh_target_not_old=oldrecipe['target']!=newrecipe['target'],
        exact_original_pipeline_cells=[source(c) for c in oldnb['cells'][:-2]]==[source(c) for c in newnb['cells'][:-2]],
        exact_late_installer_and_runtime_cell=source(oldnb['cells'][-2])==source(newnb['cells'][-2]),
        exact_configuration=oldrecipe['configuration']==newrecipe['configuration'],
        exact_payload_pins=oldrecipe['configuration']['payload_pins']==newrecipe['configuration']['payload_pins'],
        exact_recipe_except_deployment_identifiers=oldnormalized==newnormalized,
        exact_observer_except_branch_and_recipe_hash=normalized_observer(source(oldnb['cells'][-1]))==normalized_observer(source(newnb['cells'][-1])),
        existing_actual_canary_passed=read(oldrun/'verification.json')['status']=='passed',
        new_observer_on_exact_existing_actual_scores=newobserver['status']=='passed' and all(newobserver['checks'].values()),
        actual_score_source_bound=all(sha(reused/'code'/k)==v for k,v in newrecipe['configuration']['payload_pins'].items()))
    valid=fixture(newstage);fast=fixture(newstage,fast=True);empty=fixture(newstage,'no_eligible');failed=fixture(newstage,'model_fail');badcontrol=fixture(newstage,'bad_control')
    rejected={n:fixture(newstage,n) for n in ('bad_prefix','bad_candidate','cross_formula','wrong_score_order','bad_config','bad_coverage','bad_role','bad_source','bad_weights')}
    fixturechecks=dict(valid=valid['accepted'],fast=fast['accepted'],no_eligible=empty['accepted'],model_closed=failed.get('closed') and failed.get('control'),control_closed=badcontrol.get('closed') and badcontrol.get('control'),**valid['direct'],**{k+'_rejected':not v['accepted'] for k,v in rejected.items()})
    checks['new_fixture_checks']=all(fixturechecks.values())
    result=dict(status='passed' if all(checks.values()) else 'failed',old_branch=OLD,new_branch=NEW,old_target=oldrecipe['target'],new_target=newrecipe['target'],old_notebook_sha256=oldsourcepin,new_notebook_sha256=sha(newstage/'notebook.ipynb'),old_cloud_claim_sha256=oldclaimpin,checks=checks,fixture_checks=fixturechecks,new_observer_checks=newobserver['checks'],
        original_actual_canary=read(oldrun/'verification.json'),actual_model_rerun_performed=False,
        evidence_reuse='Exact byte-identical late inference cell and payloads; only branch/target/recipe observer identifiers changed. New observer independently consumed the saved real score/input/output files.',
        old_target_retried=False,cloud_or_competition_write_performed=False,early_manifest_mutated=False)
    (out/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ('status','old_branch','new_branch','new_notebook_sha256','actual_model_rerun_performed')}));assert all(checks.values())
if __name__=='__main__':main()
