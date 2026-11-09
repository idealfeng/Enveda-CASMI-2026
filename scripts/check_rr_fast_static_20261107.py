"""Independent no-model fixture for the private V56 + RR branch."""
from pathlib import Path
from contextlib import redirect_stdout,redirect_stderr
import ast
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
STAGE=ROOT/'submission/aggressive_20261107/flex_rr_aggressive'

def source(cell):
    value=cell['source'];return ''.join(value) if isinstance(value,list) else value
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def dump(node):return ast.dump(node,include_attributes=False)


def main():
    import numpy as np
    import pandas as pd
    original=read(ROOT/'third_party/flexonafft_evidence_gap/v56/original.ipynb')
    stage=read(STAGE/'notebook.ipynb');recipe=read(STAGE/'recipe.json')
    checks={}
    checks['original_config_only_fast_mode']=(source(stage['cells'][1])==source(original['cells'][1]).replace("COMMIT_MODE = 'smoke'","COMMIT_MODE = 'fast'"))
    unchanged=True
    for i in range(12,len(original['cells'])):
        if original['cells'][i]['cell_type']!='code':continue
        wrapped=ast.parse(source(stage['cells'][i]))
        unchanged &= len(wrapped.body)==1 and isinstance(wrapped.body[0],ast.If) and isinstance(wrapped.body[0].test,ast.Name) and wrapped.body[0].test.id=='RUN_PIPELINE'
        unchanged &= dump(ast.Module(body=wrapped.body[0].body,type_ignores=[]))==dump(ast.parse(source(original['cells'][i])))
    checks['original_post_neural_hidden_asts_exact']=unchanged
    current=source(original['cells'][11]);tail=current.split("if not PIPELINE_DONE and not IS_RERUN and COMMIT_MODE == 'fast':",1)[1]
    original_hidden=ast.parse(tail[tail.index('if not PIPELINE_DONE:'):])
    modified=ast.parse(source(stage['cells'][11]))
    checks['original_hidden_neural_schedule_exact']=dump(ast.Module(body=modified.body[-1].orelse,type_ignores=[]))==dump(original_hidden)
    temp_root=ROOT/'.cache/rr-fast-independent';temp_root.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=temp_root) as temporary:
        folder=Path(temporary);work=folder/'work';work.mkdir();comp=folder/'comp';comp.mkdir();code=work/'code';code.mkdir()
        ids=['m'+str(i).zfill(4) for i in range(400)]
        pd.DataFrame({'molecule_id':ids,'smiles':['CCO']*400}).to_csv(comp/'sample_submission.csv',index=False)
        calls=[]
        def pipeline():calls.append('fast_pipeline');return False
        def forbidden(*args,**kwargs):raise AssertionError('Fast fixture reached a model/consensus function')
        bundle=ROOT/'assets/kaggle/sanpier/casmi-spectrum-model-v1/v1/casmi_spectrum_model_v1'
        scope=dict(Path=Path,os=os,shutil=shutil,np=np,pd=pd,json=json,time=time,sys=sys,hashlib=hashlib,
            ROOT=work,CODE=code,COMP=comp,SAMPLE_IDS=ids,INPUT=folder,RUN_PIPELINE=False,IS_RERUN=False,
            NB_T0=time.time(),materialise_sources=lambda:str(bundle),run_public_pipeline=pipeline,
            score_final_lists=forbidden,score_outside_candidates=forbidden,build_consensus=forbidden,choose_and_submit=forbidden)
        with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
            exec(compile(source(stage['cells'][1]),'stage-config','exec'),scope)
            exec(compile(source(stage['cells'][11]),'stage-scheduler','exec'),scope)
            for i in range(12,len(stage['cells'])):
                if stage['cells'][i]['cell_type']=='code':exec(compile(source(stage['cells'][i]),'stage-cell-'+str(i),'exec'),scope)
        audit=read(work/'batch_variant_audit.json')
        checks.update(fast_observer_passed=audit['status']=='passed' and all(v is True for v in audit['checks'].values()),
            fast_mode_declared=audit['mode']=='fast_static',fast_no_runtime_models=audit['visible_model_executed'] is False,
            fast_rr_not_run=scope['RR8_REPORT']['status']=='off: no pipeline answer in this run',
            fast_no_model_or_consensus_calls=calls==['fast_pipeline'],fast_csv_400=len(pd.read_csv(work/'submission.csv'))==400,
            recipe_rr_settings=scope['RR8_ALPHA']==1.5 and scope['RR8_LIB_TAU']==.95 and scope['RR8_BUDGET_SECONDS']==2700 and scope['MASS_ON'] is False)
        overlay=scope['_RR8_OVERLAY']
        checks['rr_allows_top1']=('slots = sorted(pos[s] for s in movable)' in overlay and "movable = [s for s in scores if not frozen.get(s, False)]" in overlay)
        checks['rr_preserves_candidate_sets']='and all(set(x) == set(y)' in source(stage['cells'][-2])
        checks['rr_native_training_structure_freeze']="facts(s)[1] in train_keys" in overlay
        result=dict(status='passed' if all(checks.values()) else 'failed',branch=recipe['branch'],
            notebook_sha256=hashlib.sha256((STAGE/'notebook.ipynb').read_bytes()).hexdigest(),checks=checks,
            fast_fixture_audit=audit,model_executed=False,truth_read=False,external_action_performed=False)
    destination=ROOT/'reports/aggressive_variant_review_20261107/rr_independent.json';destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=result['status'],checks_passed=sum(checks.values()),checks_total=len(checks),failed=[k for k,v in checks.items() if not v]),indent=2))
    return 0 if result['status']=='passed' else 1

if __name__=='__main__':raise SystemExit(main())
