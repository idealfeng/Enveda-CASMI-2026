"""Second opinion on the frozen alias-only stage and canonical alias behavior."""
from pathlib import Path
from collections import Counter
import ast,base64,hashlib,json,sys,tempfile,zlib
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(ROOT))
import identity_alias_promotion_20261111 as mod
from validation.metric import assert_official_rdkit,identity

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def text(c):return ''.join(c['source']) if isinstance(c['source'],list) else c['source']

def old_fixture(folder,pre,ref,cos=.99,peaks=5):
    # Independently form the original raw-SMILES proposal and official guard.
    original=pre.split(';');proposal=([ref]+[s for s in original if s!=ref]) if ref in original else ([ref]+original)[:25]
    if cos<.8 or peaks<4:proposal=original
    keys=[identity(s) for s in proposal]
    okay=None not in keys and len(keys)==len(set(keys)) and 1<=len(keys)<=25
    incoming=';'.join(proposal) if okay else pre
    pd.DataFrame([('q',pre)],columns=['molecule_id','smiles']).to_csv(folder/'submission_external_control.csv',index=False)
    pd.DataFrame([('q',incoming)],columns=['molecule_id','smiles']).to_csv(folder/'submission.csv',index=False)
    match=dict(molecule_id='q',cosine=cos,matched_peaks=peaks,smiles=ref,above_threshold=bool(cos>=.8 and peaks>=4))
    runtime=dict(status='applied',mode='hidden_full',rows=1,control_sha256=mod.sha(folder/'submission_external_control.csv'),base_audit_csv_sha256=mod.sha(folder/'submission_external_control.csv'),output_sha256=mod.sha(folder/'submission.csv'),library_matching_performed=True,actual_matches=[match],details=[dict(molecule_id='q',validity_guard_preserved_control=not okay,official_identities_valid=True,accepted_changed=incoming!=pre)],checks={'fixture_input_only':True})
    mod.write(folder/'external_overlay_runtime.json',runtime)
    audit=dict(status='passed',mode='hidden_full',checks={'fixture_input_only':True},runtime_report_sha256=mod.sha(folder/'external_overlay_runtime.json'),csv_sha256=mod.sha(folder/'submission.csv'),control_sha256=mod.sha(folder/'submission_external_control.csv'))
    return audit,incoming

def main():
    assert_official_rdkit();checks={};stage=ROOT/'submission/optimization_20261110/extlib_ab_identity_alias'
    base=ROOT/'submission/optimization_20261109/mass_guarded_extlib'
    old=read(base/'notebook.ipynb');new=read(stage/'notebook.ipynb');recipe=read(stage/'recipe.json');spec=read(stage/'branch_spec.json')
    checks['frozen_module_expected']=mod.sha(ROOT/'scripts/identity_alias_promotion_20261111.py')=='44b1964b9298a794bb303f3ce579c8d06ef8b8047f078fe868bed0154d607c02'
    checks['champion_expected']=mod.sha(base/'notebook.ipynb')=='2bb94c91b176f95dfdff52f08781443ffee004c20d06aeb30efb14d0c0112fc7'
    checks['all_33_original_cell_objects_exact']=len(old['cells'])==33 and new['cells'][:33]==old['cells']
    checks['only_one_late_cell']=len(new['cells'])==34
    checks['spec_source_bound']=mod.sha(stage/'notebook.ipynb')==spec['notebook_sha256']
    checks['spec_metadata_bound']=mod.sha(stage/'kernel-metadata.json')==spec['metadata_sha256']
    late=text(new['cells'][-1]);tree=ast.parse(late);try_node=next(n for n in tree.body if isinstance(n,ast.Try))
    assignment=next(n for n in try_node.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='_alias_raw' for t in n.targets))
    raw=zlib.decompress(base64.b64decode(ast.literal_eval(assignment.value.args[0].args[0])))
    checks['actual_payload_exact']=raw==(ROOT/'scripts/identity_alias_promotion_20261111.py').read_bytes()
    checks['payload_recipe_pin']=hashlib.sha256(raw).hexdigest()==recipe['alias_module_sha256']
    argument=next(n for n in try_node.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='_alias_args' for t in n.targets))
    checks['recipe_literal_bound']=ast.literal_eval(argument.value.elts[-1])==mod.sha(stage/'recipe.json')
    checks['backup_before_decode']='submission_alias_preinstall_control.csv' in ast.unparse(try_node.body[0]) and try_node.body.index(assignment)>0
    checks['preinstall_error_removes_final']="(ROOT/'submission.csv').unlink(missing_ok=True)" in late
    checks['no_new_data_sources']=read(stage/'kernel-metadata.json')['dataset_sources']==read(base/'kernel-metadata.json')['dataset_sources']
    for c in new['cells']:
        if c['cell_type']=='code':compile(text(c),'alias_independent_stage','exec')
    checks['all_code_compiles']=True
    cases=[('tautomer','C;CC(=O)N;CCO','CC(O)=N','CC(=O)N;C;CCO'),
           ('stereo','C;F[C@H](Cl)Br;CCO','F[C@@H](Cl)Br','F[C@H](Cl)Br;C;CCO'),
           ('native_already_first','CC(=O)N;C;CCO','CC(O)=N','CC(=O)N;C;CCO'),
           ('unblocked_existing','C;CC(=O)N;CCO','CC(=O)N','CC(=O)N;C;CCO'),
           ('new_structure_already_AB','C;CC(=O)N;CCO','N','N;C;CC(=O)N;CCO')]
    with tempfile.TemporaryDirectory(prefix='alias-independent-',dir=ROOT/'.cache/tmp-linux') as folder:
        root=Path(folder)
        for name,pre,ref,wanted in cases:
            work=root/name;work.mkdir();audit,incoming=old_fixture(work,pre,ref)
            run=mod.run(work,audit,True,['q'],'independent','fixture_recipe');passed=mod.audit(work,audit,True,['q'],'independent','fixture_recipe')
            got=pd.read_csv(work/'submission.csv').smiles.iloc[0]
            checks[name+'_expected']=got==wanted
            checks[name+'_native_multiset']=Counter(got.split(';'))==Counter(incoming.split(';'))
            checks[name+'_official_valid']=mod.valid(got) and passed['status']=='passed'
            if name in ('tautomer','stereo'):checks[name+'_real_official_alias']=identity(ref)==identity(pre.split(';')[1]) and run['changed_queries']==1
            if name in ('unblocked_existing','new_structure_already_AB'):checks[name+'_module_did_not_change_AB']=run['changed_queries']==0
        # At rank25 the old raw-alias insertion itself removes the native last
        # entry, so its proposal is valid. The new stage must not claim a fix.
        work=root/'rank25';work.mkdir();pre=';'.join(['C'*i for i in range(1,25)]+['CC(=O)N'])
        audit,incoming=old_fixture(work,pre,'CC(O)=N');run=mod.run(work,audit,True,['q'],'independent','fixture_recipe');mod.audit(work,audit,True,['q'],'independent','fixture_recipe')
        checks['rank25_already_legal_AB_preserved']=pd.read_csv(work/'submission.csv').smiles.iloc[0]==incoming and run['eligible_queries']==0
        # Even rebinding a corrupt old runtime hash cannot manufacture a blocked
        # alias opportunity; the original actual proposal is reconstructed.
        work=root/'fake_blocked';work.mkdir();audit,_=old_fixture(work,'C;CC;CCC','N')
        r=mod.read(work/'external_overlay_runtime.json');r['details'][0]['validity_guard_preserved_control']=True;mod.write(work/'external_overlay_runtime.json',r);audit['runtime_report_sha256']=mod.sha(work/'external_overlay_runtime.json')
        try:mod.run(work,audit,True,['q'],'independent','fixture_recipe')
        except ValueError:checks['rebound_false_guard_rejected']=not (work/'submission.csv').exists() and (work/'submission_alias_promotion_control.csv').exists()
        else:checks['rebound_false_guard_rejected']=False
    report=dict(status='passed' if all(checks.values()) else 'failed',checks=checks,checks_passed=sum(checks.values()),checks_total=len(checks),module_sha256=mod.sha(ROOT/'scripts/identity_alias_promotion_20261111.py'),notebook_sha256=mod.sha(stage/'notebook.ipynb'),no_gpu_cloud_or_new_reference_scoring=True,fixture_semantics='Independent original raw-SMILES proposal + official metric guard; no efficacy claim')
    mod.write(ROOT/'reports/alias_independent_review_20261111.json',report)
    print(json.dumps({k:report[k] for k in ['status','checks_passed','checks_total','module_sha256','notebook_sha256']}));assert all(checks.values()),repr([k for k,v in checks.items() if not v])

if __name__=='__main__':main()
