"""Run the changed mean-tail plus unchanged AB cells on saved production intermediates.

This is a component integration smoke, not a new full production or efficacy run.
The input intermediate comes from the two-query generation production smoke and
therefore is not the exact champion candidate set.
"""
from pathlib import Path
import hashlib,json,os,shutil,sys,time,traceback

ROOT=Path(__file__).resolve().parents[1]
PRODUCTION=ROOT/'runs/generation_production_20261113_r2/kaggle/working'
OFFICIAL_SITE=ROOT/'.cache/rdkit-official-linux-2026033'
os.environ['PYTHONPATH']=str(OFFICIAL_SITE)+os.pathsep+os.environ.get('PYTHONPATH','')
sys.path.insert(0,str(OFFICIAL_SITE))
import numpy as np
import pandas as pd
import rdkit

OUT=ROOT/'runs/head_mean_ab_20261113_r2'
STAGE=ROOT/'submission/optimization_20261113/head_mean_ab'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def source(c):return ''.join(c['source']) if isinstance(c['source'],list) else c['source']
def save(p,x):Path(p).write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')

def main():
    OUT.mkdir(exist_ok=False,parents=True)
    assert rdkit.__version__=='2026.03.3'
    code=OUT/'p2s_code';code.mkdir()
    control=PRODUCTION/'submission_guarded_tail_control.csv'
    shutil.copy2(control,OUT/'submission.csv')
    shutil.copy2(PRODUCTION/'effective_query_spectra.parquet',OUT/'effective_query_spectra.parquet')
    shutil.copy2(PRODUCTION/'p2s_code/neural_scores_original.py',code/'neural_scores.py')
    base=read(PRODUCTION/'batch_variant_audit.json')
    assert base['status']=='passed' and base['csv_sha256']==sha(control)
    inp=PRODUCTION.parent/'input'
    tests=list(inp.rglob('test.parquet'));assert len(tests)==1
    sample=pd.read_csv(control,dtype=str,keep_default_na=False)
    nb=read(STAGE/'notebook.ipynb')
    scope=dict(Path=Path,pd=pd,np=np,ROOT=OUT,CODE=code,OURS_BUNDLE=PRODUCTION/'ours_bundle',IS_RERUN=True,RUN_PIPELINE=True,PIPELINE_DONE=True,BATCH_VARIANT_AUDIT=base,SAMPLE_IDS=sample.molecule_id.tolist(),INPUT=inp,COMP=tests[0].parent)
    started=time.monotonic();marks=[]
    for i in (30,31,32,33):
        tick=time.monotonic()
        exec(compile(source(nb['cells'][i]),f'actual_head_mean_ab_cell{i}','exec'),scope)
        marks.append(dict(cell=i,seconds=time.monotonic()-tick))
    final=pd.read_csv(OUT/'submission.csv',dtype=str,keep_default_na=False)
    mean=read(OUT/'guarded_tail_audit.json');external=read(OUT/'external_overlay_audit.json');last=read(OUT/'head_mean_ab_audit.json')
    assert all(a['status']=='passed' and a['mode']=='hidden_full' for a in (mean,external,last))
    assert last['mean_scorer_executed'] is True and last['trained_tail_heads_applied'] is False
    assert final.molecule_id.tolist()==sample.molecule_id.tolist()
    score=read(OUT/'guarded_tail_scores.parquet.head_audit.json')
    assert score['head_applied'] is False and score['heads']==[] and score['errors']==[]
    result=dict(status='passed_actual_changed_components',seconds=time.monotonic()-started,marks=marks,notebook_sha256=sha(STAGE/'notebook.ipynb'),recipe_sha256=sha(STAGE/'recipe.json'),queries=len(final),candidate_rows=score['output_rows'],mean_changed_queries=mean['changed_queries'],actual_mean_scorer_executed=last['mean_scorer_executed'],actual_AB_matching=external['checks']['actual_external_matching'],AB_reference_counts=external['reference_counts'],AB_hits=external['hits'],all_checks=last['checks'],csv_sha256=sha(OUT/'submission.csv'),source_production_control_sha256=sha(control),source_effective_queries_sha256=sha(PRODUCTION/'effective_query_spectra.parquet'),rdkit_version=rdkit.__version__,truth_metrics_computed=False,full_pipeline_executed=False,limitation='Only exact changed cells30-33 on saved actual generation-variant intermediates; not a new full initialisation, not exact champion candidates, and no efficacy/recall comparison.')
    save(OUT/'verification.json',result)
    print(json.dumps(result))

if __name__=='__main__':
    try:main()
    except BaseException as error:
        if OUT.exists():save(OUT/'failure.json',dict(status='failed',error_type=type(error).__name__,traceback=traceback.format_exc()))
        raise
