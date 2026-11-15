"""Actual changed cells on saved two-query intermediates; no model training/full rerun."""
from pathlib import Path
import hashlib,json,os,shutil,sys,time,traceback

ROOT=Path(__file__).resolve().parents[1]
SITE=ROOT/'.cache/rdkit-official-linux-2026033'
os.environ['PYTHONPATH']=str(SITE)+os.pathsep+os.environ.get('PYTHONPATH','')
sys.path.insert(0,str(SITE))
import numpy as np
import pandas as pd
import rdkit

PRODUCTION=ROOT/'runs/generation_production_20261113_r2/kaggle/working'
STAGES=ROOT/'submission/optimization_20261114'
OUT=ROOT/'runs/prefix1_ab_20261114'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def source(c):return ''.join(c['source']) if isinstance(c['source'],list) else c['source']
def save(p,x):Path(p).write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')

def run(name):
    out=OUT/name;out.mkdir(parents=True,exist_ok=False)
    code=out/'p2s_code';code.mkdir()
    control=PRODUCTION/'submission_guarded_tail_control.csv'
    shutil.copy2(control,out/'submission.csv')
    for f in ['effective_query_spectra.parquet','frozen_candidate_evidence.parquet']:
        shutil.copy2(PRODUCTION/f,out/f)
    shutil.copy2(PRODUCTION/'p2s_code/neural_scores_original.py',code/'neural_scores.py')
    batch=read(PRODUCTION/'batch_variant_audit.json')
    assert batch['status']=='passed' and batch['csv_sha256']==sha(control)
    inp=PRODUCTION.parent/'input';test=list(inp.rglob('test.parquet'));assert len(test)==1
    before=pd.read_csv(control,dtype=str,keep_default_na=False)
    scope=dict(Path=Path,pd=pd,np=np,ROOT=out,CODE=code,OURS_BUNDLE=PRODUCTION/'ours_bundle',IS_RERUN=True,RUN_PIPELINE=True,PIPELINE_DONE=True,BATCH_VARIANT_AUDIT=batch,SAMPLE_IDS=before.molecule_id.tolist(),INPUT=inp,COMP=test[0].parent)
    nb=read(STAGES/name/'notebook.ipynb');marks=[];start=time.monotonic()
    for i in (30,31,32,33):
        tick=time.monotonic();exec(compile(source(nb['cells'][i]),f'actual_{name}_cell{i}','exec'),scope)
        marks.append(dict(cell=i,seconds=time.monotonic()-tick))
    tail=read(out/'guarded_tail_audit.json');ab=read(out/'external_overlay_audit.json');final=read(out/'prefix1_ab_audit.json')
    runtime=read(out/'guarded_tail_runtime.json');score_audit=read(out/'guarded_tail_scores.parquet.head_audit.json')
    assert all(x['status']=='passed' and x['mode']=='hidden_full' and all(x['checks'].values()) for x in (tail,ab,final))
    assert tail['protected_prefix']==1 and score_audit['errors']==[]
    scores=pd.read_parquet(out/'guarded_tail_scores.parquet')
    p7,details=scope['_guarded_tail'].reorder(before,scores,runtime['skipped_queries'],protected_prefix=7)
    p1=pd.read_csv(out/'submission_external_control.csv',dtype=str,keep_default_na=False)
    after=pd.read_csv(out/'submission.csv',dtype=str,keep_default_na=False)
    actual_p7=(PRODUCTION/'submission_external_control.csv') if name.startswith('head_') else (ROOT/'runs/head_mean_ab_20261113_r3/submission_external_control.csv')
    old_p7=pd.read_csv(actual_p7,dtype=str,keep_default_na=False)
    assert p7.equals(old_p7),'Same-score prefix7 reconstruction differs from existing actual counterpart'
    checks=dict(exact_source_bound=True,actual_models_invoked=runtime['model_invoked'],correct_official_rdkit=rdkit.__version__=='2026.03.3',all_tail_AB_final_checks=True,score_errors_empty=score_audit['errors']==[],prefix1_exact=all(x.split(';')[0]==y.split(';')[0] for x,y in zip(before.smiles,p1.smiles)),same_score_prefix7_matches_prior=p7.equals(old_p7),production_library_context_copied=sha(out/'frozen_candidate_evidence.parquet')==sha(PRODUCTION/'frozen_candidate_evidence.parquet'),actual_AB_matching=ab['checks']['actual_external_matching'])
    assert all(checks.values())
    changed_early=sum(a.split(';')[1:7]!=b.split(';')[1:7] for a,b in zip(p1.smiles,p7.smiles))
    result=dict(status='passed_actual_changed_components',branch=name,notebook_sha256=sha(STAGES/name/'notebook.ipynb'),recipe_sha256=sha(STAGES/name/'recipe.json'),marks=marks,seconds=time.monotonic()-start,checks=checks,queries=len(before),candidate_rows=len(scores),score_mode=tail['score_mode'],learned_heads_applied=score_audit['head_applied'],head_weights=score_audit['heads'],source_control_sha256=sha(control),effective_query_sha256=sha(out/'effective_query_spectra.parquet'),prefix7_comparison_sha256=sha(actual_p7),prefix7_output_reconstructed=True,changed_query_lists_vs_same_score_prefix7=int((p1.smiles!=p7.smiles).sum()),changed_ranks2_7_queries=changed_early,changed_top1_before_AB=0,AB_hits=ab['hits'],AB_reference_counts=ab['reference_counts'],final_csv_sha256=sha(out/'submission.csv'),truth_metrics_computed=False,new_full_pipeline_executed=False,limitation='Actual changed cells30-33 only, on saved two-query generation-variant production intermediates. Same-score prefix7 reconstruction exactly reproduces prior actual trained/mean counterpart. No new complete initialization, no exact champion-candidate efficacy panel, no truth metrics.')
    save(out/'verification.json',result);print(json.dumps({k:result[k] for k in ['status','branch','seconds','changed_query_lists_vs_same_score_prefix7','changed_ranks2_7_queries','AB_hits']}),flush=True)
    return result

def main():
    assert rdkit.__version__=='2026.03.3'
    OUT.mkdir(exist_ok=False)
    rows=[]
    for name in ('head_prefix1_ab','mean_prefix1_ab'):
        try:rows.append(run(name))
        except BaseException as error:
            save(OUT/(name+'_failure.json'),dict(status='failed',error_type=type(error).__name__,traceback=traceback.format_exc()));raise
    report=ROOT/'reports/optimization_20261114';report.mkdir(exist_ok=True,parents=True)
    save(report/'prefix1_ab_components.json',dict(status='passed',branches=rows,all_data_on_D=True))

if __name__=='__main__':main()
