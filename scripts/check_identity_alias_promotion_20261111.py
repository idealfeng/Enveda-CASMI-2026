"""Check persisted real AB receipts and isolated identity-promotion edge cases."""
from pathlib import Path
from collections import Counter
import copy,json,shutil,sys
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import identity_alias_promotion_20261111 as mod

def fixture(folder,scenario):
    folder.mkdir();pre='C;CC;CCC';ref='[CH3:1][CH3:2]';cos=.99;peaks=5
    if scenario=='already_first':pre='CC;C;CCC'
    elif scenario=='invalid_reference':ref='not-a-smiles'
    elif scenario=='outside':ref='N'
    elif scenario=='below_threshold':cos=.7
    preframe=pd.DataFrame([('q',pre)],columns=['molecule_id','smiles']);match=dict(molecule_id='q',cosine=cos,matched_peaks=peaks,smiles=ref,above_threshold=cos>=.8)
    proposal=mod.old_proposal(pre,match);okay=mod.valid(proposal);incoming=proposal if okay else pre
    preframe.to_csv(folder/'submission_external_control.csv',index=False);pd.DataFrame([('q',incoming)],columns=['molecule_id','smiles']).to_csv(folder/'submission.csv',index=False)
    runtime=dict(status='applied',mode='hidden_full',rows=1,control_sha256=mod.sha(folder/'submission_external_control.csv'),
        base_audit_csv_sha256=mod.sha(folder/'submission_external_control.csv'),output_sha256=mod.sha(folder/'submission.csv'),library_matching_performed=True,
        actual_matches=[match],details=[dict(molecule_id='q',validity_guard_preserved_control=not okay,official_identities_valid=True,accepted_changed=incoming!=pre)],checks=dict(actual_fixture=True))
    mod.write(folder/'external_overlay_runtime.json',runtime)
    old=dict(status='passed',mode='hidden_full',checks=dict(actual_fixture=True),runtime_report_sha256=mod.sha(folder/'external_overlay_runtime.json'),csv_sha256=mod.sha(folder/'submission.csv'),control_sha256=mod.sha(folder/'submission_external_control.csv'))
    return old

def main():
    out=ROOT/'runs/identity_alias_promotion_canary_20261111';out.mkdir(exist_ok=False)
    checks={};results={}
    for name,expected in [('rank2','CC;C;CCC'),('already_first','CC;C;CCC'),('invalid_reference','C;CC;CCC'),('outside','N;C;CC;CCC'),('below_threshold','C;CC;CCC')]:
        folder=out/name;old=fixture(folder,name);before=pd.read_csv(folder/'submission.csv',dtype=str,keep_default_na=False)
        runtime=mod.run(folder,old,True,['q'],'fixture','fixture_recipe');audit=mod.audit(folder,old,True,['q'],'fixture','fixture_recipe');after=pd.read_csv(folder/'submission.csv',dtype=str,keep_default_na=False)
        checks[name+'_expected_output']=after.smiles.iloc[0]==expected
        checks[name+'_native_multiset']=Counter(before.smiles.iloc[0].split(';'))==Counter(after.smiles.iloc[0].split(';'))
        checks[name+'_audit_passed']=audit['status']=='passed';results[name]=runtime
    # Actual persisted original .488 receipts and scores, unchanged source files.
    for full in [False,True]:
        original=ROOT/'runs/external_overlay_actual_canary_20261109'/('hidden_actual' if full else 'fast_actual')
        folder=out/('real_hidden' if full else 'real_fast');folder.mkdir()
        for name in ['submission.csv','submission_external_control.csv','external_overlay_runtime.json']:shutil.copy2(original/name,folder/name)
        old=mod.read(original/'external_overlay_audit.json');mids=pd.read_csv(folder/'submission.csv',dtype=str).molecule_id.tolist()
        runtime=mod.run(folder,old,full,mids,'actual_persisted','fixture_recipe');audit=mod.audit(folder,old,full,mids,'actual_persisted','fixture_recipe')
        checks['real_hidden_receipts' if full else 'real_fast_receipts']=audit['status']=='passed'
        checks['real_hidden_unchanged_already_first' if full else 'real_fast_unchanged']=mod.sha(folder/'submission.csv')==old['csv_sha256']
        if full:checks['real_hidden_blocked_alias_eligible']=runtime['eligible_queries']==1 and runtime['details'][3]['reason']=='identity_already_first'
        results['real_hidden' if full else 'real_fast']=runtime
    # Global integrity violations fail closed while retaining the incoming CSV.
    for scenario in ['old_runtime_hash','old_control_hash','incoming_ab_hash','rebound_bad_score']:
        folder=out/scenario;old=fixture(folder,'rank2')
        if scenario=='old_runtime_hash':
            r=mod.read(folder/'external_overlay_runtime.json');r['actual_matches'][0]['cosine']=.2;mod.write(folder/'external_overlay_runtime.json',r)
        elif scenario=='old_control_hash':(folder/'submission_external_control.csv').write_text('wrong')
        elif scenario=='incoming_ab_hash':(folder/'submission.csv').write_text('wrong')
        else:
            r=mod.read(folder/'external_overlay_runtime.json');r['actual_matches'][0]['cosine']=.2;mod.write(folder/'external_overlay_runtime.json',r);old['runtime_report_sha256']=mod.sha(folder/'external_overlay_runtime.json')
        try:mod.run(folder,old,True,['q'],'fixture','fixture_recipe');checks[scenario+'_rejected']=False
        except ValueError:checks[scenario+'_rejected']=not (folder/'submission.csv').exists() and (folder/'submission_alias_promotion_control.csv').is_file()
    # Rebinding a manipulated final hash cannot conceal promotion outside scope.
    folder=out/'wrong_final_scope';old=fixture(folder,'outside');mod.run(folder,old,True,['q'],'fixture','fixture_recipe')
    frame=pd.read_csv(folder/'submission.csv',dtype=str);parts=frame.smiles.iloc[0].split(';');parts[1],parts[2]=parts[2],parts[1];frame.at[0,'smiles']=';'.join(parts);frame.to_csv(folder/'submission.csv',index=False)
    r=mod.read(folder/'alias_promotion_runtime.json');r['output_sha256']=mod.sha(folder/'submission.csv');mod.write(folder/'alias_promotion_runtime.json',r)
    try:mod.audit(folder,old,True,['q'],'fixture','fixture_recipe');checks['unapproved_reordering_rejected']=False
    except ValueError:checks['unapproved_reordering_rejected']=True
    # Self module binding remains an explicit separate check.
    folder=out/'wrong_module_receipt';old=fixture(folder,'rank2');mod.run(folder,old,True,['q'],'fixture','fixture_recipe')
    r=mod.read(folder/'alias_promotion_runtime.json');r['module_sha256']='0'*64;mod.write(folder/'alias_promotion_runtime.json',r)
    try:mod.audit(folder,old,True,['q'],'fixture','fixture_recipe');checks['module_receipt_rejected']=False
    except ValueError:checks['module_receipt_rejected']=True
    report=dict(status='passed' if all(checks.values()) else 'failed',checks=checks,checks_passed=sum(checks.values()),checks_total=len(checks),module_sha256=mod.sha(ROOT/'scripts/identity_alias_promotion_20261111.py'),results=results,
        no_gpu_or_cloud_or_new_reference_scoring=True,persisted_real_receipt_input='runs/external_overlay_actual_canary_20261109',synthetic_identity_cases_explicit=True,efficacy_evaluation=False)
    mod.write(out/'verification.json',report);print(json.dumps({k:report[k] for k in ['status','checks_passed','checks_total','module_sha256','checks']},indent=2));assert all(checks.values())

if __name__=='__main__':main()
