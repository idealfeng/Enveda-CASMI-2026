"""Run original .488 final cell then frozen alias cell on real A/B match records.

Only the final cells execute. Upstream MASS is represented by a constructed
source-bound control fixture; no full model execution or accuracy evaluation.
"""
from pathlib import Path
from collections import Counter
import argparse,ast,base64,hashlib,json,shutil,time,zlib
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]

def read(p):return json.loads(Path(p).read_text())
def sha(p):
    with Path(p).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def src(c):return ''.join(c['source']) if isinstance(c['source'],list) else c['source']
def write(p,v):Path(p).write_text(json.dumps(v,indent=2)+'\n')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--tag',default='final');a=p.parse_args()
    original=ROOT/'runs/external_overlay_actual_canary_20261109';base_stage=ROOT/'submission/optimization_20261109/mass_guarded_extlib';alias_stage=ROOT/'submission/optimization_20261110/extlib_ab_identity_alias'
    base_nb=read(base_stage/'notebook.ipynb');alias_nb=read(alias_stage/'notebook.ipynb');recipe=read(alias_stage/'recipe.json')
    if alias_nb['cells'][:-1]!=base_nb['cells']:raise ValueError('Original .488 cells changed')
    base_source=src(base_nb['cells'][-1]);alias_source=src(alias_nb['cells'][-1]);frozen=sha(alias_stage/'notebook.ipynb')
    control=pd.read_csv(original/'hidden_actual/submission_external_control.csv',dtype=str,keep_default_na=False)
    i=control.index[control.molecule_id=='duplicate_guard'][0];parts=control.at[i,'smiles'].split(';');native=parts[0];parts[0],parts[1]=parts[1],parts[0];control.at[i,'smiles']=';'.join(parts)
    evidence=pd.read_parquet(original/'hidden_actual/frozen_candidate_evidence.parquet')
    out=ROOT/'runs'/('identity_alias_stage_canary_20261111_'+a.tag);out.mkdir(exist_ok=False);cases={}
    for full in (False,True):
        mode='hidden' if full else 'fast';work=out/mode;work.mkdir();code=work/'code';code.mkdir()
        control.to_csv(work/'submission.csv',index=False);evidence.to_parquet(work/'frozen_candidate_evidence.parquet',index=False)
        scope=dict(Path=Path,pd=pd,ROOT=work,INPUT=original/'input',COMP=original/'input/enveda-CASMI26-molecule-id-mass-spectra',CODE=code,
            IS_RERUN=full,SAMPLE_IDS=control.molecule_id.tolist(),GUARDED_TAIL_AUDIT=dict(status='passed',csv_sha256=sha(work/'submission.csv')))
        started=time.monotonic();exec(compile(base_source,'actual_original_488_final_cell','exec'),scope)
        before=pd.read_csv(work/'submission.csv',dtype=str,keep_default_na=False);ab_audit=scope['EXTERNAL_OVERLAY_AUDIT']
        if full:
            old_report=read(work/'external_overlay_runtime.json');row=next(x for x in old_report['details'] if x['molecule_id']=='duplicate_guard')
            if not row['validity_guard_preserved_control'] or before.loc[before.molecule_id=='duplicate_guard','smiles'].iloc[0].split(';')[0]==native:raise ValueError('Positive native-alias fixture did not activate original guard')
        exec(compile(alias_source,'exact_staged_alias_cell','exec'),scope)
        report=scope['IDENTITY_ALIAS_REPORT'];audit=scope['IDENTITY_ALIAS_AUDIT'];after=pd.read_csv(work/'submission.csv',dtype=str,keep_default_na=False)
        checks=dict(actual_original_ab_cell_passed=ab_audit['status']=='passed',actual_alias_cell_passed=audit['status']=='passed',
            installed_source_pin=sha(code/'identity_alias_promotion_20261111.py')==recipe['alias_module_sha256']==audit['installed_module_sha256'],
            all_alias_observer_checks=all(v is True for v in audit['checks'].values()),
            incoming_ab_bound=sha(work/'submission_alias_preinstall_control.csv')==ab_audit['csv_sha256']==report['incoming_ab_sha256'],
            exact_ids=after.molecule_id.tolist()==before.molecule_id.tolist(),
            native_multisets=all(Counter(x.split(';'))==Counter(y.split(';')) for x,y in zip(before.smiles,after.smiles)),
            no_new_scoring_or_candidates=report['matching_performed'] is False and report['new_candidates_inserted']==0,
            actual_prefix33_exact=alias_nb['cells'][:-1]==base_nb['cells'],frozen_source_unchanged=sha(alias_stage/'notebook.ipynb')==frozen)
        if full:
            changed=after.smiles!=before.smiles
            checks.update(actual_native_rank2_promoted=after.loc[after.molecule_id=='duplicate_guard','smiles'].iloc[0].split(';')[0]==native and report['changed_queries']==1,
                original_unblocked_queries_exact=before.loc[before.molecule_id!='duplicate_guard'].equals(after.loc[after.molecule_id!='duplicate_guard']),
                only_approved_alias_query_changed=before.loc[changed,'molecule_id'].tolist()==['duplicate_guard'],actual_original_matches_consumed=audit['checks']['actual_old_matches_consumed'])
        else:checks['fast_original_ab_unchanged']=after.equals(before) and report['changed_queries']==0
        if not all(checks.values()):raise ValueError('Staged alias checks failed: '+repr(checks))
        cases[mode]=dict(status='passed',checks=checks,seconds=time.monotonic()-started,stage_sha256=frozen)
        print(json.dumps(dict(mode=mode,status='passed',seconds=time.monotonic()-started)),flush=True)
    # Corrupted payload is rejected before imported code can execute.
    fast=out/'fast';bad=out/'bad_payload';bad.mkdir();code=bad/'code';code.mkdir();shutil.copy2(fast/'submission_alias_promotion_control.csv',bad/'submission.csv')
    scope=dict(Path=Path,pd=pd,ROOT=bad,CODE=code,IS_RERUN=False,SAMPLE_IDS=control.molecule_id.tolist(),EXTERNAL_OVERLAY_AUDIT={})
    tree=ast.parse(alias_source);call=next(x for x in ast.walk(tree) if isinstance(x,ast.Call) and isinstance(x.func,ast.Attribute) and x.func.attr=='b64decode');call.args=[ast.Constant(base64.b64encode(zlib.compress(b'bad')).decode())];ast.fix_missing_locations(tree)
    try:exec(compile(tree,'corrupt_alias_payload','exec'),scope);closed=False
    except AssertionError:closed=not (bad/'submission.csv').exists() and (bad/'submission_alias_preinstall_control.csv').is_file()
    cases['bad_payload']=dict(status='passed' if closed else 'failed',checks=dict(actual_bad_payload_fails_closed=closed))
    if not closed:raise ValueError('Bad alias payload did not fail closed')
    # Rebinding the old runtime is detected before any native promotion.
    bad=out/'bad_old_runtime';bad.mkdir();code=bad/'code';code.mkdir();full=out/'hidden'
    for name in ['submission_external_control.csv','external_overlay_runtime.json'] :shutil.copy2(full/name,bad/name)
    shutil.copy2(full/'submission_alias_promotion_control.csv',bad/'submission.csv')
    (bad/'external_overlay_runtime.json').write_text((bad/'external_overlay_runtime.json').read_text()+' ')
    old_audit=read(full/'external_overlay_audit.json');scope=dict(Path=Path,pd=pd,ROOT=bad,CODE=code,IS_RERUN=True,SAMPLE_IDS=control.molecule_id.tolist(),EXTERNAL_OVERLAY_AUDIT=old_audit)
    try:exec(compile(alias_source,'bad_old_runtime_alias','exec'),scope);closed=False
    except ValueError:closed=not (bad/'submission.csv').exists() and (bad/'submission_alias_promotion_control.csv').is_file()
    cases['bad_old_runtime']=dict(status='passed' if closed else 'failed',checks=dict(actual_bad_old_runtime_fails_closed=closed))
    if not closed:raise ValueError('Rebound old runtime not rejected')
    result=dict(status='passed',cases=cases,full_upstream_MASS_executed=False,gpu_used=False,cloud_or_submission_writes=False,
        actual_old_AB_matching=True,actual_native_alias_promoted=True,efficacy_or_MRR_evaluation=False,known_pretrained_exposure=True,notebook_sha256=frozen)
    write(out/'verification.json',result);write(ROOT/'reports/identity_alias_stage_canary_20261111.json',dict(status='passed',actual_report=str((out/'verification.json').relative_to(ROOT)),cases={k:v['status'] for k,v in cases.items()},notebook_sha256=frozen))
    print(json.dumps(dict(status='passed',actual_staged_cases=len(cases),report=str(out/'verification.json'))))

if __name__=='__main__':main()
