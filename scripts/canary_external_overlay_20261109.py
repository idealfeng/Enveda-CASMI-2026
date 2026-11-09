"""Actual CPU inference canary against both pinned measured libraries; no GPU/cloud."""
from __future__ import annotations
from pathlib import Path
import ast,copy,hashlib,importlib.util,json,os,sys,time
import numpy as np,pandas as pd
from rdkit import Chem

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import external_library_overlay_20261109 as overlay

def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    out=ROOT/'runs/external_overlay_actual_canary_20261109';out.mkdir(exist_ok=False)
    recipe=read(ROOT/'submission/optimization_20261109/public_alex_extlib/recipe.json');files=recipe['files']
    inp=out/'input';inp.mkdir();sources={}
    for item in files:
        src=ROOT/'assets/kaggle'/item['ref']/('v'+str(item['version']))/item['file']
        target=inp/item['ref'].split('/')[1]/item['file'];target.parent.mkdir(exist_ok=True)
        os.link(src,target);sources[item['file']]=src
    meta=pd.read_parquet(sources['ext_meta.parquet']);mz=np.load(sources['ext_mz.npy'],mmap_mode='r');it=np.load(sources['ext_in.npy'],mmap_mode='r')
    ai=next(i for i,r in meta.head(500).iterrows() if np.count_nonzero((mz[i]>0)&(it[i]>0))>=6 and overlay.identity(r.normalized_smiles))
    a=meta.iloc[ai];a_mask=(mz[ai]>0)&(it[ai]>0);a_query=dict(ms2_mzs=np.asarray(mz[ai][a_mask],float),ms2_normalized_intensities=np.asarray(it[ai][a_mask],float),precursor_mz=float(a.precursor_mz),ionization_mode=a.ionization_mode,adduct=a.adduct)
    mb=pd.read_parquet(sources['spectra.parquet']);b=next(r for r in mb.itertuples(index=False) if not r.is_casmi_subset and r.adduct=='[M+H]+' and len(r.mzs)>=6 and overlay.identity(r.smiles))
    b_query=dict(ms2_mzs=np.asarray(b.mzs,float),ms2_normalized_intensities=np.asarray(b.intensities,float),precursor_mz=float(b.exact_mass)+1.007276,ionization_mode='positive',adduct='[M+H]+')
    del mb
    rows=[dict(molecule_id='real_source_a',**a_query),dict(molecule_id='real_source_b',**b_query),dict(molecule_id='protected',**a_query),dict(molecule_id='duplicate_guard',**a_query)]
    competition=inp/'enveda-CASMI26-molecule-id-mass-spectra';competition.mkdir()
    pd.DataFrame(rows).to_parquet(competition/'test.parquet',index=False)
    mids=['real_source_a','real_source_b','protected','duplicate_guard','missing_query']
    guesses=['C'*(i+1)+'O' for i in range(25)]
    alt=Chem.MolToSmiles(Chem.MolFromSmiles(a.normalized_smiles),isomericSmiles=False)
    assert alt!=a.normalized_smiles and overlay.identity(alt)==overlay.identity(a.normalized_smiles)
    control=pd.DataFrame(dict(molecule_id=mids,smiles=[';'.join(guesses)]*3+[';'.join([alt]+guesses[:24]),';'.join(guesses)]))
    evidence=pd.DataFrame(dict(molecule_id=mids,library_max=[0.,0.,.95,0.,0.]))
    alex=read(ROOT/'third_party/public_scan_alexchilton__casmi26-lb-0-484-peaks-to-structures-extlib_20261109/source.ipynb')
    text=alex['cells'][24]['source'];text=''.join(text) if isinstance(text,list) else text
    fn=next(x for x in ast.parse(text).body if isinstance(x,ast.FunctionDef) and x.name=='_apex_extlib_overlay')
    original=out/'alex_function.py';original.write_text(ast.get_source_segment(text,fn)+'\n');assert sha(original)==recipe['original_function_sha256']
    checks={};results={}
    for full in [False,True]:
        work=out/('hidden_actual' if full else 'fast_actual');work.mkdir();control.to_csv(work/'submission.csv',index=False);evidence.to_parquet(work/'frozen_candidate_evidence.parquet',index=False)
        base=dict(status='passed',csv_sha256=sha(work/'submission.csv'));args=(work,inp,competition/'test.parquet',full,mids,base,original,sha(original),files)
        started=time.monotonic();result=overlay.run(*args);audit=overlay.audit(*args,'actual_canary','fixture_recipe')
        results['hidden' if full else 'fast']=dict(runtime=result,observer=audit,elapsed_seconds=time.monotonic()-started)
        checks['hidden_actual_passed' if full else 'fast_actual_passed']=audit['status']=='passed'
        final=pd.read_csv(work/'submission.csv')
        if full:
            checks['both_actual_sources']=all(result['reference_counts'][x]>0 for x in ['A','B'])
            checks['real_query_leader_changed']=result['changed_top1']>=1
            checks['protected_preserved']=final.smiles.iloc[2]==control.smiles.iloc[2]
            checks['duplicate_identity_guard_exercised']=result['invalid_proposals_preserved']>=1 and final.smiles.iloc[3]==control.smiles.iloc[3]
            checks['missing_query_preserved']=final.smiles.iloc[4]==control.smiles.iloc[4]
            original_runtime=read(work/'external_overlay_runtime.json');tampered=copy.deepcopy(original_runtime);tampered['actual_matches'][0]['cosine']=0.
            (work/'external_overlay_runtime.json').write_text(json.dumps(tampered))
            try:overlay.audit(*args,'actual_canary','fixture_recipe');checks['reject_changed_observed_score']=False
            except ValueError:checks['reject_changed_observed_score']=True
            (work/'external_overlay_runtime.json').write_text(json.dumps(original_runtime,indent=2)+'\n')
        else:checks['fast_no_matching']=not result['library_matching_performed'] and final.equals(control)
    failure=out/'bad_binding';failure.mkdir();control.to_csv(failure/'submission.csv',index=False)
    try:overlay.run(failure,inp,competition/'test.parquet',False,mids,dict(status='passed',csv_sha256='bad'),original,sha(original),files);checks['bad_control_fail_closed']=False
    except ValueError:checks['bad_control_fail_closed']=not (failure/'submission.csv').exists() and (failure/'submission_external_control.csv').is_file()
    report=dict(status='passed' if all(checks.values()) else 'failed',checks=checks,results=results,
        efficacy_evaluation=False,labels_or_hidden_queries_used=False,model_training=False,gpu_used=False)
    (out/'verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(status=report['status'],checks=checks,seconds={k:v['elapsed_seconds'] for k,v in results.items()}),indent=2));assert all(checks.values())

if __name__=='__main__':main()
