"""Recheck exact AB cells with every consumed saved production context artifact.

The first successful changed-component test omitted frozen_candidate_evidence,
which disabled AB's existing-library protection. Preserve that evidence and
replay only AB plus the final observer after restoring the actual context.
"""
from pathlib import Path
import hashlib,json,os,shutil,sys,time

ROOT=Path(__file__).resolve().parents[1]
PRODUCTION=ROOT/'runs/generation_production_20261113_r2/kaggle/working'
MEAN_RUN=ROOT/'runs/head_mean_ab_20261113_r2'
OUT=ROOT/'runs/head_mean_ab_20261113_r3'
STAGE=ROOT/'submission/optimization_20261113/head_mean_ab'
SITE=ROOT/'.cache/rdkit-official-linux-2026033'
os.environ['PYTHONPATH']=str(SITE)+os.pathsep+os.environ.get('PYTHONPATH','')
sys.path.insert(0,str(SITE))
import numpy as np
import pandas as pd
import rdkit

def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def source(c):return ''.join(c['source']) if isinstance(c['source'],list) else c['source']

def main():
    assert rdkit.__version__=='2026.03.3'
    prior=read(MEAN_RUN/'verification.json')
    assert prior['status']=='passed_actual_changed_components' and prior['actual_mean_scorer_executed']
    shutil.copytree(MEAN_RUN,OUT)
    shutil.copy2(MEAN_RUN/'submission_external_control.csv',OUT/'submission.csv')
    shutil.copy2(PRODUCTION/'frozen_candidate_evidence.parquet',OUT/'frozen_candidate_evidence.parquet')
    inp=PRODUCTION.parent/'input';tests=list(inp.rglob('test.parquet'));assert len(tests)==1
    batch=read(PRODUCTION/'batch_variant_audit.json');mean=read(MEAN_RUN/'guarded_tail_audit.json')
    assert sha(OUT/'submission.csv')==mean['csv_sha256']
    scope=dict(Path=Path,pd=pd,np=np,ROOT=OUT,CODE=OUT/'p2s_code',IS_RERUN=True,RUN_PIPELINE=True,PIPELINE_DONE=True,BATCH_VARIANT_AUDIT=batch,GUARDED_TAIL_AUDIT=mean,SAMPLE_IDS=pd.read_csv(OUT/'submission.csv').molecule_id.tolist(),INPUT=inp,COMP=tests[0].parent)
    nb=read(STAGE/'notebook.ipynb');started=time.monotonic()
    for i in (32,33):exec(compile(source(nb['cells'][i]),f'actual_AB_context_cell{i}','exec'),scope)
    external=read(OUT/'external_overlay_audit.json');last=read(OUT/'head_mean_ab_audit.json')
    assert all(a['status']=='passed' and a['mode']=='hidden_full' and all(a['checks'].values()) for a in (external,last))
    score=read(OUT/'guarded_tail_scores.parquet.head_audit.json')
    assert score['role']=='frozen_v2_mean' and score['head_applied'] is False and score['errors']==[]
    result=dict(status='passed_actual_changed_components_with_production_context',notebook_sha256=sha(STAGE/'notebook.ipynb'),recipe_sha256=sha(STAGE/'recipe.json'),actual_mean_execution_receipt=str((MEAN_RUN/'verification.json').relative_to(ROOT)),actual_mean_execution_receipt_sha256=sha(MEAN_RUN/'verification.json'),actual_mean_seconds=prior['marks'][0]['seconds'],AB_replay_seconds=time.monotonic()-started,actual_AB_matching=external['checks']['actual_external_matching'],AB_reference_counts=external['reference_counts'],AB_hits=external['hits'],production_library_evidence_sha256=sha(PRODUCTION/'frozen_candidate_evidence.parquet'),copied_library_evidence_sha256=sha(OUT/'frozen_candidate_evidence.parquet'),queries=prior['queries'],candidate_rows=prior['candidate_rows'],mean_changed_queries=prior['mean_changed_queries'],actual_mean_scorer_executed=True,trained_tail_heads_applied=False,csv_sha256=sha(OUT/'submission.csv'),all_final_checks=last['checks'],full_pipeline_executed=False,truth_metrics_computed=False,limitation='Exact changed mean cells executed in r2; exact AB and final cells rerun in r3 with actual production library_max context. Saved intermediates use generation-variant candidates, not exact champion, and no efficacy claim.')
    (OUT/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))

if __name__=='__main__':main()
