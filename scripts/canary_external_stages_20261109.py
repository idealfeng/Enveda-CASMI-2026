"""Execute actual staged late cells on real libraries; no main-model inference."""
from pathlib import Path
import hashlib,json,os,sys,time
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def src(c):return ''.join(c['source']) if isinstance(c['source'],list) else c['source']
def main():
    original=ROOT/'runs/external_overlay_actual_canary_20261109';out=ROOT/'runs/external_stages_actual_canary_20261109';out.mkdir(exist_ok=False)
    control=pd.read_csv(original/'hidden_actual/submission_external_control.csv',dtype=str,keep_default_na=False)
    pub=ROOT/'assets/kaggle/sanpier/casmi-spectrum-model-v1/v1/casmi_spectrum_model_v1';records={}
    for name,full in [('public_alex_extlib',False),('mass_guarded_extlib',False),('mass_guarded_extlib',True)]:
        stage=ROOT/'submission/optimization_20261109'/name;nb=read(stage/'notebook.ipynb');index=24 if name=='public_alex_extlib' else len(nb['cells'])-1
        work=out/(name+('_actual' if full else '_fast'));work.mkdir();code=work/'code';code.mkdir()
        control.to_csv(work/'submission.csv',index=False)
        pd.read_parquet(original/'hidden_actual/frozen_candidate_evidence.parquet').to_parquet(work/'frozen_candidate_evidence.parquet',index=False)
        base=dict(status='passed',csv_sha256=sha(work/'submission.csv'))
        scope=dict(Path=Path,pd=pd,ROOT=work,INPUT=original/'input',COMP=original/'input/enveda-CASMI26-molecule-id-mass-spectra',CODE=code,
            PUB_BUNDLE=pub,OURS_BUNDLE=pub,POP_W=.12,SPEC_W=.12,NP_W=.12,LIB_HIT_GATE=.78,V8='MASS',MASS_ON=True,RR8=False,
            IS_RERUN=full,SAMPLE_IDS=control.molecule_id.tolist(),RUN_PIPELINE=False,PIPELINE_DONE=False,GUARDED_TAIL_AUDIT=base)
        started=time.monotonic();exec(compile(src(nb['cells'][index]),'actual_staged_external_cell','exec'),scope)
        report=scope['EXTERNAL_OVERLAY_REPORT'];audit=scope['EXTERNAL_OVERLAY_AUDIT']
        checks=dict(actual_staged_cell_passed=audit['status']=='passed',actual_helper_pin=sha(code/'external_library_overlay_20261109.py')==read(stage/'recipe.json')['helper_sha256'],
            matching_performed_as_requested=report['library_matching_performed']==full,real_both_sources=(not full) or all(report['reference_counts'][x]>0 for x in ['A','B']),
            base_binding=report['control_sha256']==base['csv_sha256'])
        assert all(checks.values());records[work.name]=dict(status='passed',checks=checks,elapsed_seconds=time.monotonic()-started,stage_sha256=sha(stage/'notebook.ipynb'))
    result=dict(status='passed',branches=records,full_upstream_MASS_inference_performed=False,actual_external_matching=True,gpu_used=False,efficacy_evaluation=False)
    (out/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
