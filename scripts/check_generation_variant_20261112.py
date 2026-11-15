"""Bounded deployment canary: two real queries, no truth/exclusion/accuracy evaluation."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import pickle
import shutil
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
STAGE=ROOT/'submission/optimization_20261112/generation_expand/revision2'
BASE=ROOT/'submission/optimization_20261109/mass_guarded_extlib'


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def src(c):return ''.join(c['source']) if isinstance(c['source'],list) else c['source']
def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def save(path,v):Path(path).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')


def stage_route(out):
    import generation_runtime_patch_20261112 as patch
    original=read(BASE/'notebook.ipynb');book=read(STAGE/'notebook.ipynb');recipe=read(STAGE/'recipe.json')
    code=out/'code';code.mkdir();root=out
    setup=src(book['cells'][12])[len(src(original['cells'][12])):]
    calls=[]
    def run_stage(args,log,name,quiet=None):
        calls.append(dict(args=[str(x) for x in args],name=name))
        return 17
    scope=dict(CODE=code,ROOT=root,Path=Path,run_stage=run_stage)
    exec(compile(setup,'exact_staged_generation_setup','exec'),scope)
    from build_generation_variant_20261112 import original_runner
    (code/'runner.py').write_text(original_runner(original))
    result=scope['run_stage']([sys.executable,code/'runner.py','frozen_original.ipynb','pin',root],root/'pipeline.log','Public 0.465 pipeline')
    checks=dict(actual_staged_setup=True,only_cell12_changed=[i for i,(a,b) in enumerate(zip(original['cells'],book['cells'])) if a!=b]==[12],
                original_runner_stays_original=sha(code/'runner.py')==recipe['original_runner_sha256'],
                new_runner_actual_argument=calls[0]['args'][1]==str(code/'generation_runner.py'),
                actual_runner_pin=sha(code/'generation_runner.py')==recipe['runner_sha256'],
                actual_module_pin=sha(code/'generation_runtime_patch_20261112.py')==recipe['module_sha256'],
                original_run_stage_return=result==17)
    # Exercise the exact appended final observer on visible no-inference branch.
    (root/'generation_launch.json').unlink()
    (root/'submission.csv').write_text('molecule_id,smiles\ncanary,C\n')
    scope.update(hashlib=hashlib,IS_RERUN=False,SAMPLE_IDS=['canary'],EXTERNAL_OVERLAY_AUDIT=dict(status='passed',csv_sha256=sha(root/'submission.csv')))
    exec(compile(src(book['cells'][-1]),'exact_staged_generation_final','exec'),scope)
    checks['exact_staged_fast_audit']=all(scope['GENERATION_VARIANT_AUDIT']['checks'].values())
    # Installed-source tampering must remove the submit CSV.
    with (code/'generation_runtime_patch_20261112.py').open('a') as stream:stream.write('\n# tampered\n')
    rejected=False
    try:exec(compile(src(book['cells'][-1]),'bad_source_generation_final','exec'),scope)
    except AssertionError:rejected=True
    checks['tampered_source_rejected_no_final']=rejected and not (root/'submission.csv').exists()
    if not all(checks.values()):raise AssertionError(checks)
    return checks


def real_queries(out):
    import numpy as np,pandas as pd,torch,lightgbm as lgb
    source=ROOT/'assets/kaggle/dmitriigluzdov/casmi26-attributed-v4g-reproduction-assets/v9/casmi26-v4b-models/code'
    models=source.parent
    sys.path.insert(0,str(source));sys.path.insert(0,str(source/'fe_v4'))
    from casmi.library import Library
    from casmi.pool import Pool
    from casmi.engine import Engine,EngineCfg,FEATURES
    from casmi import chem,fpnet
    import v1engine
    import generation_runtime_patch_20261112 as patch
    work=out/'work';work.mkdir()
    for name in ('spec_mz.npy','spec_it.npy','spec_off.npy','spec_meta.parquet'):
        (work/name).symlink_to(ROOT/'runs/shared_spec_cache'/name)
    pool=ROOT/'assets/kaggle/ahmedberatozer/casmi26-v2-pool/v1'
    for name in ('train_structs.parquet','pool_meta.parquet','pool_fp.npy','fp_bits.npy','pool_frag_off.npy','pool_frag_mass.npy'):
        (work/name).symlink_to(pool/name)
    L=Library(str(work));P=Pool(str(work));tfp=np.load(pool/'train_fp_sel.npy')
    device='cuda' if torch.cuda.is_available() else 'cpu';torch.manual_seed(0)
    full=ROOT/'assets/kaggle/dmitriigluzdov/casmi26-attributed-v4g-reproduction-assets/v9/casmi26-fpnet-full1/fpnet_full1.pt'
    bank=fpnet.ModelBank([str(full)],device=device)
    E=Engine(L,P,tfp,EngineCfg(generate=True),bank)
    man=read(models/'MANIFEST.json')
    V=v1engine.V1FE(E,[str(models/m['file']) for m in man['fe_models']],man['families'],device=device)
    rk=pickle.load((models/man['ranker']['file']).open('rb'));boosters=[lgb.Booster(model_str=s) for s in rk['boosters']]
    def rank_score(X,names):
        ix={n:i for i,n in enumerate(names)}
        matrix=np.ascontiguousarray(X[:,[ix[n] for n in rk['features']]],dtype=np.float32)
        return np.mean([b.predict(matrix,num_threads=4) for b in boosters],axis=0)
    # Use two pre-existing query IDs only to exercise real new candidates; never load truth.
    existing=read(ROOT/'produre2/artifacts/q4_full_rank.json')
    mids=[r['molecule_id'] for r in sorted(existing['rows'],key=lambda r:-r.get('n_gen',0))[:2]]
    queries=pd.read_parquet(ROOT/'runs/validation_pilot_v2_20261104/queries.parquet')
    queries=queries[queries.molecule_id.isin(mids)].copy()
    queries['nm']=chem.neutral_mass(queries.precursor_mz.values.astype(float),queries.adduct.values)
    ordered=list(queries.molecule_id.drop_duplicates().astype(str))
    def build(mid):
        q=queries[queries.molecule_id==mid];spectra=[]
        for r in q.itertuples():
            ce=np.asarray(r.collision_energy_ev,dtype=float).reshape(-1)
            spectra.append(dict(mz=np.asarray(r.ms2_mzs,np.float64),it=np.asarray(r.ms2_normalized_intensities,np.float64),
                                mode=1 if r.ionization_mode=='positive' else -1,adduct=r.adduct,prec=float(r.precursor_mz),
                                ce=float(ce.mean()) if len(ce) else float('nan'),ce_n=len(ce) if len(ce) else 1))
        return spectra,float(np.nanmedian(q.nm))
    control={}
    t=time.monotonic()
    for mid in ordered:
        C,X,F,names,info=V.run(*build(mid));score=rank_score(np.concatenate([X,F],1),list(FEATURES)+list(names))
        control[mid]=dict(keys=set(C.key),n_generated=int(C.is_gen.sum()),top25=[C.smiles[i] for i in np.argsort(-score,kind='stable')[:25]])
        print('CONTROL',mid,'generated',int(C.is_gen.sum()),flush=True)
    save(out/'control_candidate_sets.json',{k:dict(keys=sorted(v['keys']),n_generated=v['n_generated'],top25=v['top25']) for k,v in control.items()})
    scope=dict(E=E,V=V,rank_score=rank_score,te=queries,IS_RERUN=False,RK_FEATS=list(rk['features']))
    patch.install(scope,out)
    changed=[];records=[]
    for mid in ordered:
        scope['mid']=mid
        try:
            C,X,F,names,info=V.run(*build(mid));score=scope['rank_score'](np.concatenate([X,F],1),list(FEATURES)+list(names))
        except BaseException:
            save(out/'failed_runtime_trace.json',patch.STATE)
            raise
        keys=set(C.key);difference=len(keys.symmetric_difference(control[mid]['keys']))
        changed.append(difference)
        top=[C.smiles[i] for i in np.argsort(-score,kind='stable')[:25]]
        records.append(dict(molecule_id=mid,n_candidates=len(C.pid),n_generated=int(C.is_gen.sum()),control_n_generated=control[mid]['n_generated'],
                            changed_candidate_identities=difference,added_candidate_identities=len(keys-control[mid]['keys']),
                            removed_candidate_identities=len(control[mid]['keys']-keys),features=int(X.shape[1]+F.shape[1]),top25=top))
        print('VARIANT',mid,'generated',int(C.is_gen.sum()),'changed',difference,flush=True)
    pd.DataFrame([dict(molecule_id=r['molecule_id'],smiles=';'.join(r['top25'])) for r in records]).to_csv(out/'submission.csv',index=False)
    patch.finish(scope,out)
    runtime=read(out/'generation_runtime.json')
    checks=dict(actual_160_feature_ranker=len(rk['features'])==160,source_pins_exact=runtime['installed_source_pins']==patch.SOURCE_PINS,
                actual_configuration=E.cfg.gen_n_analog==12 and E.cfg.gen_max_total==300,
                actual_runtime_checks=all(runtime['checks'].values()),actual_candidate_changes=any(changed),
                actual_parent7_12_used=any(r['parents_used']>6 for r in runtime['rows']),no_truth_or_exclusion=True)
    save(out/'real_query_results.json',dict(checks=checks,seconds=time.monotonic()-t,device=device,rows=records,
        scope='Two real deployment-interface queries with full production pool/features/ranker, no truth or identity exclusion. No efficacy claim. Production external reference delta/full later layers are not replayed here.'))
    if not all(checks.values()):raise AssertionError(checks)
    return checks


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--real',action='store_true');p.add_argument('--tag',default='final');a=p.parse_args()
    out=ROOT/'runs'/('generation_prod_canary_20261112_'+a.tag);out.mkdir(exist_ok=False)
    if a.real:checks=real_queries(out)
    else:checks=stage_route(out)
    record=dict(status='passed',checks=checks,checks_passed=sum(checks.values()),checks_total=len(checks),
                notebook_sha256=sha(STAGE/'notebook.ipynb'),module_sha256=sha(ROOT/'scripts/generation_runtime_patch_20261112.py'),
                no_kaggle_or_produre_rerun=True)
    save(out/'verification.json',record);print(json.dumps(record,indent=2))


if __name__=='__main__':main()
