"""Review a prefix0 policy using real pair evidence produced by revision2.

No source library or model is loaded again. The shared evidence producer was
executed in r2; r3 changes only the protected-prefix policy and its observer.
This is fixed-policy replay, not a new full pipeline or a new pair-matching run.
"""
from pathlib import Path
from collections import Counter
import copy
import hashlib
import importlib.util
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.cache/rdkit-official-linux-2026033'))
sys.path.insert(0,str(ROOT/'scripts'))
import pandas as pd
import rdkit
import kaggle_batch as batch

STAGE=ROOT/'submission/optimization_20261114/library_consensus_early/revision3'
RUN=ROOT/'runs/library_consensus_early_20261114_r2'
OUT=ROOT/'runs/library_consensus_early_20261114_r3_replay'

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,x):Path(p).write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
def load(name,p):
    spec=importlib.util.spec_from_file_location(name,p);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def main():
    assert rdkit.__version__=='2026.03.3'
    OUT.mkdir(exist_ok=False,parents=True)
    runtime=read(RUN/'hidden_component/library_consensus_runtime.json')
    actual_audit=read(RUN/'hidden_component/library_consensus_audit.json')
    assert actual_audit['status']=='passed' and all(actual_audit['checks'].values())
    assert actual_audit['runtime_report_sha256']==sha(RUN/'hidden_component/library_consensus_runtime.json')
    old=pd.read_csv(RUN/'hidden_component/submission_library_consensus_control.csv',dtype=str)
    module=load('prefix0_fixed_library',ROOT/'scripts/library_consensus_early_20261114_v3.py')
    original=(ROOT/'scripts/library_consensus_early_20261114_v2.py').read_text()
    adapted=original.replace('support_weight=1., protected_prefix=1,','support_weight=1., protected_prefix=0,').replace("prefix1_protected=all(a.split(';')[0]==b.split(';')[0] for a,b in zip(old.smiles,final.smiles))","configured_prefix_preserved=all(a.split(';')[:CONFIG['protected_prefix']]==b.split(';')[:CONFIG['protected_prefix']] for a,b in zip(old.smiles,final.smiles))")
    assert adapted==(ROOT/'scripts/library_consensus_early_20261114_v3.py').read_text()
    rows=[];final=old.copy();guard=load('official_library_guard',ROOT/'scripts/external_library_overlay_20261109.py')
    for i,((mid,raw),r) in enumerate(zip(old.itertuples(index=False,name=None),runtime['query_rows'])):
        assert mid==r['molecule_id']
        proposal,groups=(raw,[]) if r['protected'] else module.reorder(raw,r['candidate_support'])
        assert Counter(proposal.split(';'))==Counter(raw.split(';'))
        assert guard.valid(proposal)
        assert all(module.formula(a)==module.formula(b) for a,b in zip(raw.split(';'),proposal.split(';')))
        final.loc[i,'smiles']=proposal
        rows.append(dict(molecule_id=mid,changed=proposal!=raw,top1_changed=proposal.split(';')[0]!=raw.split(';')[0],formula_groups=groups,query_spectra=r['query_spectra'],protected=r['protected'],observed_support=[dict(original_rank=j+1,supported_spectra=v['supported_spectra'],consensus=v['consensus']) for j,v in enumerate(r['candidate_support']) if v['supported_spectra']]))
    final.to_csv(OUT/'fixed_policy_replay.csv',index=False)
    # Fixture checks only the explicit existing AB-protected row gate; not a hit
    # observed in these two saved queries, whose actual AB match count was zero.
    protected_fixture={'protected':True,'candidate_support':runtime['query_rows'][0]['candidate_support']}
    raw=old.smiles.iloc[0]
    fixture_output=(raw,[]) if protected_fixture['protected'] else module.reorder(raw,protected_fixture['candidate_support'])
    assert fixture_output[0]==raw
    s=read(STAGE/'branch_spec.json')
    manifest=dict(schema_version=1,competition=batch.COMPETITION,batch_id='library_review_1114',max_submissions=5,baseline_public_score=.488,state_root='reports/optimization_20261114/library_review',branches=[s])
    batch.local_preflight(manifest,s)
    # Execute the frozen appended cell's actual fast branch against the real
    # parent output and pinned local data; no pair matching or neural inference.
    import shutil
    work=OUT/'fast_static';work.mkdir();code=work/'p2s_code';code.mkdir()
    production=ROOT/'runs/generation_production_20261113_r2/kaggle/working'
    for f in ['external_library_overlay_20261109.py','alex_v12_external_function.py']:
        shutil.copy2(production/'p2s_code'/f,code/f)
    shutil.copy2(production/'submission.csv',work/'submission.csv')
    sys.path.insert(0,str(code))
    scope=dict(Path=Path,pd=pd,ROOT=work,CODE=code,INPUT=RUN/'input',COMP=RUN/'input/enveda-CASMI26-molecule-id-mass-spectra',IS_RERUN=False,SAMPLE_IDS=old.molecule_id.tolist(),EXTERNAL_OVERLAY_AUDIT=read(production/'external_overlay_audit.json'))
    book=read(STAGE/'notebook.ipynb');cell=book['cells'][-1]['source'];cell=''.join(cell) if isinstance(cell,list) else cell
    exec(compile(cell,'actual_r3_frozen_fast_cell','exec'),scope)
    fast=read(work/'library_consensus_audit.json');assert fast['status']=='passed' and all(fast['checks'].values())
    report=dict(status='passed_source_bound_fixed_policy_replay',branch='library_consensus_early',notebook_sha256=sha(STAGE/'notebook.ipynb'),recipe_sha256=sha(STAGE/'recipe.json'),module_sha256=sha(ROOT/'scripts/library_consensus_early_20261114_v3.py'),prior_actual_pair_runtime=str((RUN/'hidden_component/library_consensus_runtime.json').relative_to(ROOT)),prior_actual_pair_runtime_sha256=sha(RUN/'hidden_component/library_consensus_runtime.json'),prior_actual_pair_audit_sha256=sha(RUN/'hidden_component/library_consensus_audit.json'),actual_reference_counts=runtime['reference_counts'],actual_pairs_observed=runtime['pairs_observed'],actual_qualified_candidate_pairs=runtime['qualified_candidate_pairs'],actual_scores_unchanged=True,only_new_policy_and_observer_prefix_1_to_0=True,changed_queries=sum(r['changed'] for r in rows),changed_top1=sum(r['top1_changed'] for r in rows),query_rows=rows,all_candidate_multisets_preserved=True,all_official_identities_valid=True,all_formula_slots_preserved=True,actual_AB_protected_rows=len(runtime['protected_ids']),AB_protection_gate_fixture_passed=True,actual_r3_fast_cell_audit=fast,rdkit=rdkit.__version__,new_full_pipeline_executed=False,new_pair_matching_executed=False,truth_metrics_computed=False,truth_metadata_present=False,limitation='Real pair evidence from r2 two-query production intermediates is reused without changing scores. r3 prefix0 is fixed-policy replay plus actual fast appended-cell execution, not a fresh hidden/full model run, not exact champion candidates, and no efficacy claim.')
    save(OUT/'verification.json',report)
    dest=ROOT/'reports/optimization_20261114';dest.mkdir(exist_ok=True)
    save(dest/'library_consensus_release.json',dict(status='released_for_exploratory_cloud_run',branch='library_consensus_early',notebook_sha256=s['notebook_sha256'],recipe_sha256=sha(STAGE/'recipe.json'),stage_dir=s['stage_dir'],evidence=(OUT/'verification.json').relative_to(ROOT).as_posix(),evidence_sha256=sha(OUT/'verification.json'),cloud_write_performed=False,gain_claim=False,boundary=report['limitation']))
    print(json.dumps(dict(status=report['status'],changed_queries=report['changed_queries'],changed_top1=report['changed_top1'],notebook_sha256=s['notebook_sha256'])))


if __name__=='__main__':main()
