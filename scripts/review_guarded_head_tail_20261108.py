"""Actual late-tail function and observer fixtures, using no learned-model run."""
from __future__ import annotations
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types

import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
STAGE=ROOT/'submission/optimization_20261108/mass_guarded_head_tail_1108'
BUNDLE=ROOT/'assets/kaggle/sanpier/casmi-spectrum-model-v1/v1/casmi_spectrum_model_v1'


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def write(p,v):Path(p).write_text(json.dumps(v,indent=2)+'\n')
def source(c):return ''.join(c['source']) if isinstance(c['source'],list) else c['source']


def fixture(mode='hidden',scenario='valid'):
    nb=read(STAGE/'notebook.ipynb');observer=source(nb['cells'][-1]);fn=next(n for n in ast.parse(observer).body if isinstance(n,ast.FunctionDef))
    expected=ast.literal_eval(next(n.value for n in fn.body if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='expected'))
    install=next(n for n in ast.parse(source(nb['cells'][-2])).body if isinstance(n,ast.FunctionDef) and n.name=='_install_candidate_head')
    prefix=['C','CC','CCC','CCCC','CCCCC','CCCCCC','CCCCCCC']
    tail=['CCCO','CCCCO','CC(O)C','CCC(O)C','CCOC','CCOCC','CCN','CNC','CCS','CSC']
    candidates=prefix+tail
    with tempfile.TemporaryDirectory(prefix='guarded-tail-fixture-',dir=ROOT/'.cache/tmp-linux') as temporary:
        root=Path(temporary);code=root/'code';code.mkdir()
        (code/'neural_scores.py').write_bytes((ROOT/'runs/validation_flex_c2_20261105d/p2s_code/neural_scores.py').read_bytes())
        tree=ast.Module(body=[install,ast.Expr(value=ast.Call(func=ast.Name(id=install.name,ctx=ast.Load()),args=[],keywords=[]))],type_ignores=[]);ast.fix_missing_locations(tree)
        exec(compile(tree,'actual_late_installer','exec'),{'CODE':code})
        (code/'guarded_head_tail.py').write_bytes((ROOT/'scripts/guarded_head_tail.py').read_bytes())
        spec=importlib.util.spec_from_file_location('_tail_fixture_runtime',code/'guarded_head_tail.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        controls=[('q0',';'.join(candidates)),('q_invalid',';'.join(prefix+tail[:-1]+['badSMILES'])),
                  ('q_nospectrum',';'.join(candidates)),('q_missing',';'.join(candidates)),('q_duplicate',';'.join(prefix+['CCO','OCC']))]
        control=pd.DataFrame(controls,columns=['molecule_id','smiles']);control.to_csv(root/'submission.csv',index=False)
        q=pd.DataFrame([dict(molecule_id=mid,ms2_mzs=[20.,30.,40.],ms2_normalized_intensities=[1.,.7,.4],precursor_mz=100.,adduct='[M+H]+',ionization_mode='positive',collision_energy_ev='20') for mid in ['q0','q_invalid','q_nospectrum','q_duplicate']])
        q.at[2,'ms2_mzs']=[20.];q.at[2,'ms2_normalized_intensities']=[1.]
        if scenario=='no_eligible':
            for i in q.index:q.at[i,'ms2_mzs']=[20.];q.at[i,'ms2_normalized_intensities']=[1.]
        q.to_parquet(root/'effective_query_spectra.parquet',index=False)
        base=dict(status='passed',csv_sha256=sha(root/'submission.csv'))
        if scenario=='bad_control_binding':base['csv_sha256']='0'*64
        def fake_model(cmd,**kwargs):
            if scenario=='model_error':return types.SimpleNamespace(returncode=1,stdout='injected model failure')
            evidence=pd.read_parquet(root/'guarded_tail_evidence.parquet');scores=evidence.copy()
            scores['neural_ok']=True;scores['neural_score']=scores.baseline_rank.astype(float)
            scores.to_parquet(root/'guarded_tail_scores.parquet',index=False)
            audit=dict(status='passed',role='learned_v2',head_applied=True,encoder_sha256=module.V2_SHA,heads=expected['head_receipts'],
                evidence_sha256=sha(root/'guarded_tail_evidence.parquet'),queries_sha256=sha(root/'effective_query_spectra.parquet'),output_sha256=sha(root/'guarded_tail_scores.parquet'),
                input_rows=len(scores),output_rows=len(scores),scored_candidate_rows=len(scores),scored_queries=int(scores.molecule_id.nunique()),errors=[])
            write(root/'guarded_tail_scores.parquet.head_audit.json',audit)
            return types.SimpleNamespace(returncode=0,stdout='synthetic score fixture; no model loaded')
        module.subprocess=types.SimpleNamespace(run=fake_model,PIPE=-1,STDOUT=-2)
        try:report=module.run(root,code,BUNDLE,mode=='hidden',base,expected['head_receipts'],device='cpu')
        except (RuntimeError,ValueError):
            if scenario in ('model_error','bad_control_binding'):return dict(accepted=False,fail_closed=not (root/'submission.csv').exists(),control_preserved=(root/'submission_guarded_tail_control.csv').exists(),report=read(root/'guarded_tail_runtime.json'))
            raise
        after=pd.read_csv(root/'submission.csv',dtype=str,keep_default_na=False)
        direct=dict(prefix_exact=all(a.split(';')[:7]==b.split(';')[:7] for a,b in zip(control.smiles,after.smiles)),
            invalid_preserved=after.iloc[1].smiles==control.iloc[1].smiles,no_spectrum_preserved=after.iloc[2].smiles==control.iloc[2].smiles,
            missing_query_preserved=after.iloc[3].smiles==control.iloc[3].smiles,duplicate_identity_preserved=after.iloc[4].smiles==control.iloc[4].smiles,
            actual_tail_reordered=mode=='fast' or scenario=='no_eligible' or after.iloc[0].smiles!=control.iloc[0].smiles)
        # Mutate evidence while updating final CSV binding where necessary, so
        # invariants are independently exercised rather than only stale-hash tests.
        if scenario in ('bad_prefix','bad_candidate','cross_formula','invalid_query_changed'):
            index=1 if scenario=='invalid_query_changed' else 0;parts=after.at[index,'smiles'].split(';')
            if scenario=='bad_prefix':parts[0],parts[1]=parts[1],parts[0]
            elif scenario=='bad_candidate':parts[-1]='CCCCCCCCO'
            elif scenario=='cross_formula':parts[7],parts[8]=parts[8],parts[7]
            else:parts[7],parts[9]=parts[9],parts[7]
            after.at[index,'smiles']=';'.join(parts);after.to_csv(root/'submission.csv',index=False);report['output_sha256']=sha(root/'submission.csv')
        elif scenario=='empty_checks':report['checks']={}
        elif scenario=='no_model_claim':report['model_invoked']=False
        elif scenario=='bad_head_receipts':report['head_receipts']=[]
        elif scenario=='bad_score_hash':report['scores_sha256']='0'*64
        elif scenario=='bad_head_audit':
            p=root/'guarded_tail_scores.parquet.head_audit.json';a=read(p);a['queries_sha256']='0'*64;write(p,a);report['head_audit_sha256']=sha(p)
        elif scenario=='bad_head_coverage':
            p=root/'guarded_tail_scores.parquet.head_audit.json';a=read(p);a['scored_candidate_rows']=0;write(p,a);report['head_audit_sha256']=sha(p)
        elif scenario=='bad_checkpoint':(code/next(k for k in expected['payload_pins'] if k.endswith('.pt'))).write_bytes(b'wrong')
        elif scenario=='bad_module':(code/'guarded_head_tail.py').write_bytes(b'wrong')
        write(root/'guarded_tail_runtime.json',report)
        scope=dict(Path=Path,pd=pd,ROOT=root,CODE=code,BATCH_VARIANT_AUDIT=base,IS_RERUN=mode=='hidden',RUN_PIPELINE=mode=='hidden',PIPELINE_DONE=mode=='hidden',SAMPLE_IDS=control.molecule_id.tolist(),_guarded_tail=module)
        try:
            exec(compile(observer,'actual_guarded_tail_observer','exec'),scope)
            return dict(accepted=True,direct=direct,report=report,observer=scope['GUARDED_TAIL_AUDIT'])
        except (AssertionError,ValueError,KeyError) as error:return dict(accepted=False,error_type=type(error).__name__,reason=str(error),direct=direct)


def main():
    output=ROOT/'reports/guarded_head_tail_review_20261108';output.mkdir(parents=True,exist_ok=True)
    if (output/'verification.json').exists():raise FileExistsError('Preserve completed review')
    before=sha(STAGE/'notebook.ipynb');fast=fixture('fast');hidden=fixture();none=fixture(scenario='no_eligible');failure=fixture(scenario='model_error');bad_control=fixture(scenario='bad_control_binding')
    names=('bad_prefix','bad_candidate','cross_formula','invalid_query_changed','empty_checks','no_model_claim','bad_head_receipts','bad_score_hash','bad_head_audit','bad_head_coverage','bad_checkpoint','bad_module')
    rejected={name:fixture(scenario=name) for name in names}
    checks=dict(actual_fast=fast['accepted'],actual_hidden=hidden['accepted'],actual_no_eligible=none['accepted'],
        actual_prefix_protection=hidden['direct']['prefix_exact'],actual_tail_same_formula_reorder=hidden['direct']['actual_tail_reordered'],
        invalid_query_preserved=hidden['direct']['invalid_preserved'],no_spectrum_preserved=hidden['direct']['no_spectrum_preserved'],
        missing_query_preserved=hidden['direct']['missing_query_preserved'],duplicate_identity_preserved=hidden['direct']['duplicate_identity_preserved'],
        global_model_failure_closed=failure['fail_closed'] and failure['control_preserved'],global_control_binding_failure_closed=bad_control['fail_closed'] and bad_control['control_preserved'],source_unchanged=sha(STAGE/'notebook.ipynb')==before)
    checks.update({name+'_rejected':not value['accepted'] for name,value in rejected.items()})
    result=dict(status='passed' if all(checks.values()) else 'failed',checks=checks,checks_passed=sum(checks.values()),checks_total=len(checks),notebook_sha256=before,
        fast=fast,hidden=hidden,no_eligible=none,global_failure=failure,control_binding_failure=bad_control,rejected=rejected,no_gpu_cloud_or_model_calls=True)
    write(output/'verification.json',result);print(json.dumps({k:result[k] for k in ('status','checks_passed','checks_total','notebook_sha256')}))
    if not all(checks.values()):raise SystemExit(1)


if __name__=='__main__':main()
