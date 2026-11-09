"""Prepare/run a fixed-candidate FPNet fold0 + Saner best-validation experiment.

Default mode only writes a small plan. Prepare scans local labelled spectra;
run executes inference only on prepared artifacts. No network, downloads,
training, reference-spectrum search, full Flex execution or submission occurs.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
import types

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
SANER=ROOT/'assets/kaggle/sanpier/casmi-spectrum-model-v1/v1/casmi_spectrum_model_v1'
FOLD=ROOT/'assets/kaggle/dmitriigluzdov/casmi26-fold-safe-fpnet/v5'
CODE=ROOT/'assets/kaggle/ahmedberatozer/casmi26-v3-models/v4/code'
POOL=ROOT/'assets/kaggle/ahmedberatozer/casmi26-v2-pool/v1'
TRAIN=ROOT/'enveda-CASMI26-molecule-id-mass-spectra/train.parquet'
AUDIT=ROOT/'reports/pretrained_exposure_audit.json'
QUERIES=ROOT/'reports/component_holdout_audit_20261104/component_intersection_queries.csv'
FROZEN=ROOT/'runs/validation_pilot_20261104/frozen_splits.json'
SEED=20261105
ALPHA=0.25
RRF_OFFSET=3.0
MASS_PPM=10.0
MAX_SPECTRA=12
MAX_OUTPUT=25


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def write_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8');temporary.replace(path)


def stable(value,seed=SEED):
    return hashlib.sha256(f'{seed}:{value}'.encode()).hexdigest()


def choose_records(records,limit=MAX_SPECTRA):
    """Round-robin adduct/polarity groups, then collision-energy bins; no labels."""
    grouped=defaultdict(list)
    for row in records:
        grouped[(row['ionization_mode'],row['adduct'])].append(row)
    for group in grouped.values():
        group.sort(key=lambda row:(row['ce_bucket'],stable(row['source_row'])))
    keys=sorted(grouped,key=lambda key:(key[0],stable(key[1])))
    result=[]
    for depth in range(max((len(v) for v in grouped.values()),default=0)):
        for key in keys:
            if depth<len(grouped[key]):result.append(grouped[key][depth])
            if len(result)==limit:return result
    return result


def window_indices(masses,neutral_mass,ppm=MASS_PPM):
    import numpy as np
    if not np.isfinite(neutral_mass) or neutral_mass<=0:raise ValueError('Invalid measured neutral mass')
    tolerance=neutral_mass*ppm*1e-6
    return range(int(np.searchsorted(masses,neutral_mass-tolerance,'left')),
                 int(np.searchsorted(masses,neutral_mass+tolerance,'right')))


def rrf_order(base_scores,neural_scores,alpha=ALPHA,offset=RRF_OFFSET):
    import numpy as np
    a=np.asarray(base_scores);b=np.asarray(neural_scores)
    if a.shape!=b.shape or a.ndim!=1 or not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError('RRF needs aligned finite component scores')
    first=np.argsort(-a,kind='stable');second=np.argsort(-b,kind='stable')
    ra=np.empty(len(a),dtype=int);rb=np.empty(len(a),dtype=int)
    ra[first]=np.arange(1,len(a)+1);rb[second]=np.arange(1,len(a)+1)
    return np.argsort(-(1/(offset+ra)+alpha/(offset+rb)),kind='stable')


def asset_paths():
    return [SANER/name for name in ['best_validation_model.pt','config.json','features.py','model.py','molecules.parquet','validation_candidates.npz']]+[
        FOLD/'fpnet_fold0.pt',FOLD/'MODEL_INPUTS.json',FOLD/'split.parquet',CODE/'casmi/fpnet.py',CODE/'casmi/chem.py',
        POOL/'pool_meta.parquet',POOL/'pool_fp.npy',POOL/'fp_bits.npy',POOL/'train_structs.parquet']


def build_plan(limit=32):
    import pandas as pd
    from validation.metric import assert_official_rdkit,identity
    assert_official_rdkit()
    audit=json.loads(AUDIT.read_text());frozen=json.loads(FROZEN.read_text())
    excluded={row['official_identity'] for row in frozen['cross_final_locked']}
    eligible={row['identity']:row for row in audit['records'] if row['component_intersection_eligible']}
    frame=pd.read_csv(QUERIES,keep_default_na=False)
    before=len(frame)
    frame=frame[~frame.identity.isin(excluded)].copy()
    frame['order']=frame.identity.map(stable)
    frame=frame.sort_values('order',kind='stable').head(limit)
    if frame.empty:raise ValueError('No eligible identities remain after locked-final exclusion')
    selected=[]
    split=pd.read_parquet(FOLD/'split.parquet');np_keys=set(split.loc[split.fold.eq('np'),'key'])
    for item in frame.to_dict('records'):
        key=item['identity'];record=eligible[key]
        if identity(item['normalized_smiles'])!=key:raise ValueError('Candidate query identity changed')
        if record.get('saner_checkpoint_selection_candidate_used',True):raise ValueError('Checkpoint-selection identity leaked into component experiment')
        is_np=any(row['source']=='fold0' and row['declared_key'] in np_keys for row in record['matched_rows'])
        selected.append({'identity':key,'normalized_smiles':item['normalized_smiles'],
                         'molecule_id':'component_'+key,'panel':'np_public_development' if is_np else 'cross_component',
                         'split':'component_development','selection_record':record})
    assets=[]
    for path in asset_paths():
        if not path.is_file():raise FileNotFoundError(f'Required local asset absent; no download is attempted: {path}')
        receipt=path.with_name(path.name+'.receipt.json')
        record=json.loads(receipt.read_text()) if receipt.exists() else {}
        expected=record.get('sha256')
        if not expected:raise ValueError(f'Missing local asset hash receipt: {path}')
        assets.append({'path':str(path),'bytes':path.stat().st_size,'sha256':expected})
    plan={'schema_version':1,'status':'planned_no_inference','seed':SEED,'runner_sha256':sha(__file__),
          'selection_csv_sha256':sha(QUERIES),'exposure_audit_sha256':sha(AUDIT),'frozen_splits_sha256':sha(FROZEN),
          'identities_before_locked_final_exclusion':before,'locked_final_excluded_identities':sorted(set(pd.read_csv(QUERIES).identity)&excluded),
          'molecules':len(selected),'queries':selected,'assets':assets,
          'train':{'path':str(TRAIN),'bytes':TRAIN.stat().st_size,
                   'expected_sha256':json.loads((SANER/'data_audit.json').read_text())['sources'][0]['sha256']},
          'parameters':{'neutral_mass_ppm':MASS_PPM,'query_neutral_mass':'median from observed precursor/adduct, never truth mass',
                        'max_spectra_per_molecule':MAX_SPECTRA,'max_rank':MAX_OUTPUT,'rrf_alpha':ALPHA,'rrf_offset':RRF_OFFSET,
                        'candidate_pool':'pinned public v2 pool; mass-window retrieval with no truth injection',
                        'fixed_candidate_policy':'FPNet ranks all retrieved identities; its top25 are frozen before Saner. Both final arms contain exactly these identities.',
                        'fpnet_aggregation':'arithmetic mean of single-spectrum logits, no reference spectra',
                        'saner_checkpoint':'best_validation_model.pt, never final_model.pt',
                        'saner_aggregation':'published equal-per-spectrum mean score',
                        'precisions':'FPNet public ModelBank autocast policy; Saner float32',
                        'train_preprocessing':'upstream fpnet.prep_peaks and Saner features.peaks'},
          'limitations':['Component experiment only; not the complete Flex/V43 pipeline or a new independent final validation.',
                         'Checkpoint/split artifacts and declared exclusions are audited; exact producer revision/historical minibatches are not fully proven.',
                         'NP examples were public development data and are reported separately.',
                         'No checkpoint training, automatic downloads or Kaggle submission.']}
    return plan


def validate_plan(plan):
    if plan['runner_sha256']!=sha(__file__):raise ValueError('Runner changed after plan freeze; prepare a new output directory')
    for name,path in [('selection_csv_sha256',QUERIES),('exposure_audit_sha256',AUDIT),('frozen_splits_sha256',FROZEN)]:
        if sha(path)!=plan[name]:raise ValueError(f'Frozen provenance input changed: {path}')
    for item in plan['assets']:
        path=Path(item['path'])
        if path.stat().st_size!=item['bytes'] or sha(path)!=item['sha256']:raise ValueError(f'Local asset changed: {path}')
    if TRAIN.stat().st_size!=plan['train']['bytes'] or sha(TRAIN)!=plan['train']['expected_sha256']:
        raise ValueError('Training file does not match the published Saner training-data hash')
    contract=json.loads((FOLD/'MODEL_INPUTS.json').read_text())
    for path,key in [(FOLD/'fpnet_fold0.pt','checkpoint_sha256'),(POOL/'fp_bits.npy','fp_bits_sha256'),(CODE/'casmi/fpnet.py','fpnet_code_sha256')]:
        if sha(path)!=contract[key]:raise ValueError(f'Fold0 input contract mismatch: {path}')


def prepare(plan,out):
    import numpy as np
    import pandas as pd
    import pyarrow.parquet as pq
    from validation.metric import identity
    validate_plan(plan)
    # Importing chemistry helpers does not instantiate a model or access CUDA.
    sys.path.insert(0,str(CODE))
    from casmi import chem
    structs=pd.read_parquet(POOL/'train_structs.parquet',columns=['sid','inchikey14'])
    raw_by_sid=dict(zip(structs.sid,structs.inchikey14))
    target_by_raw=defaultdict(set)
    truth={row['identity']:row for row in plan['queries']}
    for row in plan['queries']:
        for matched in row['selection_record']['matched_rows']:
            if matched['source'].startswith('fold0'):
                raw=raw_by_sid[matched['sid']]
                target_by_raw[raw].add(row['identity'])
    groups=defaultdict(dict);observed=Counter();source_row=0
    fields=['inchikey14','normalized_smiles','ingest_lib','adduct','ionization_mode','precursor_mz','collision_energy_ev','ms2_mzs','ms2_normalized_intensities']
    for batch in pq.ParquetFile(TRAIN).iter_batches(batch_size=4096,columns=fields,use_threads=False):
        frame=batch.to_pandas();mask=frame.inchikey14.isin(target_by_raw)
        for index,row in frame.loc[mask].iterrows():
            key=identity(row.normalized_smiles)
            if key not in truth or key not in target_by_raw[row.inchikey14] or row.adduct not in chem.TEST_ADDUCTS:continue
            mz=np.asarray(row.ms2_mzs,dtype=float);intensity=np.asarray(row.ms2_normalized_intensities,dtype=float)
            if len(mz)!=len(intensity) or np.sum(np.isfinite(mz)&np.isfinite(intensity)&(mz>0)&(intensity>0))<3:continue
            ce=np.asarray(row.collision_energy_ev if row.collision_energy_ev is not None else [],dtype=float).reshape(-1)
            ce=ce[np.isfinite(ce)];bucket=int(float(ce.mean())//25) if len(ce) else -1
            record={'molecule_id':truth[key]['molecule_id'],'source_row':source_row+int(index),
                    'spectrum_id':'train_'+str(source_row+int(index)),'ingest_lib':row.ingest_lib,'adduct':row.adduct,
                    'ionization_mode':row.ionization_mode,'precursor_mz':float(row.precursor_mz),
                    'collision_energy_ev':ce.tolist(),'ce_bucket':bucket,'ms2_mzs':mz.tolist(),
                    'ms2_normalized_intensities':intensity.tolist()}
            group=(row.ionization_mode,row.adduct,bucket)
            # NP records use NP spectra if available. Others prefer deterministic source-name/hash order.
            priority=(0 if row.ingest_lib=='enveda-np-examples' else 1,str(row.ingest_lib),stable(record['source_row']))
            old=groups[key].get(group)
            if old is None or priority<old[0]:groups[key][group]=(priority,record)
            observed[key]+=1
        source_row+=batch.num_rows
        if source_row%131072==0:print(f'PREPARE spectra scanned={source_row} selected_identity_rows={sum(observed.values())}',flush=True)
    selected=[];truth_rows=[];query_summary=[]
    for key,item in truth.items():
        records=choose_records([value[1] for value in groups[key].values()])
        if not records:raise ValueError(f'No usable spectra among the ten supported adducts: {key}')
        selected.extend(records)
        truth_rows.append({name:item[name] for name in ['molecule_id','identity','normalized_smiles','panel','split']})
        truth_rows[-1]['source']=';'.join(sorted({r['ingest_lib'] for r in records}))
        query_summary.append({'molecule_id':item['molecule_id'],'spectra':len(records),'adducts':sorted({r['adduct'] for r in records}),
                              'polarities':sorted({r['ionization_mode'] for r in records}),'ce_buckets':sorted({r['ce_bucket'] for r in records})})
    query=pd.DataFrame(selected);query.to_parquet(out/'queries.parquet',index=False)
    pd.DataFrame(truth_rows).to_csv(out/'truth.csv',index=False)
    pool=pd.read_parquet(POOL/'pool_meta.parquet',columns=['pid','smiles','mass'])
    if not pool.mass.is_monotonic_increasing or not np.array_equal(pool.pid,np.arange(len(pool))):raise ValueError('Pool order is not sorted mass/pid contract')
    candidate_rows=[];empty=[]
    for mid,frame in query.groupby('molecule_id',sort=False):
        masses=chem.neutral_mass(frame.precursor_mz.to_numpy(),frame.adduct.to_numpy())
        masses=masses[np.isfinite(masses)]
        if not len(masses):raise ValueError(f'No finite adduct-derived neutral mass: {mid}')
        neutral=float(np.median(masses));seen=set()
        for pid in window_indices(pool.mass.to_numpy(),neutral):
            key=identity(pool.smiles.iloc[pid])
            if key is None or key in seen:continue
            seen.add(key)
            candidate_rows.append({'molecule_id':mid,'pid':pid,'identity':key,'smiles':pool.smiles.iloc[pid],'observed_neutral_mass':neutral})
        if not seen:empty.append(mid)
    # Empty retrieval is a zero-recall outcome, recorded explicitly; no truth is injected.
    columns=['molecule_id','pid','identity','smiles','observed_neutral_mass']
    pd.DataFrame(candidate_rows,columns=columns).to_parquet(out/'retrieved_candidates.parquet',index=False)
    files={name:{'sha256':sha(out/name),'bytes':(out/name).stat().st_size} for name in ['queries.parquet','truth.csv','retrieved_candidates.parquet']}
    write_json(out/'prepared.json',{'status':'prepared_no_inference','plan_sha256':sha(out/'plan.json'),'files':files,
                                 'molecules':len(truth),'spectra':len(query),'candidate_rows':len(candidate_rows),
                                 'empty_retrieval_ids':empty,'queries':query_summary,
                                 'scope':'Queries and measured-mass candidate windows frozen; labels not used to inject candidates.'})


def load_saner(device):
    import torch
    package='_component_saner';module=types.ModuleType(package);module.__path__=[str(SANER)];sys.modules[package]=module
    for name in ['features','model']:
        spec=importlib.util.spec_from_file_location(package+'.'+name,SANER/(name+'.py'))
        child=importlib.util.module_from_spec(spec);sys.modules[spec.name]=child;spec.loader.exec_module(child)
    cfg=json.loads((SANER/'config.json').read_text())
    model=sys.modules[package+'.model'].SpectrumCandidateModel(cfg).to(device)
    checkpoint=torch.load(SANER/'best_validation_model.pt',map_location='cpu',weights_only=True)
    if checkpoint.get('stage')!='holdout':raise ValueError('Unexpected Saner training stage')
    model.load_state_dict(checkpoint['state_dict'],strict=True);model.eval()
    return model,sys.modules[package+'.features'],cfg


def run(plan,out,device):
    started=time.monotonic()
    import numpy as np
    import pandas as pd
    import torch
    from validation.evaluate import add_candidate_audit,audit_fixed_candidates,evaluate_frames,paired_bootstrap
    validate_plan(plan)
    prepared=json.loads((out/'prepared.json').read_text())
    if prepared['plan_sha256']!=sha(out/'plan.json'):raise ValueError('Plan changed after preparation')
    for name,record in prepared['files'].items():
        if sha(out/name)!=record['sha256']:raise ValueError(f'Prepared artifact changed: {name}')
    if device=='cuda' and not torch.cuda.is_available():raise RuntimeError('CUDA requested but unavailable')
    torch.set_num_threads(4)
    if device=='cuda':torch.cuda.reset_peak_memory_stats()
    query=pd.read_parquet(out/'queries.parquet');candidates=pd.read_parquet(out/'retrieved_candidates.parquet')
    sys.path.insert(0,str(CODE));from casmi import chem,fpnet
    checkpoint=torch.load(FOLD/'fpnet_fold0.pt',map_location='cpu',weights_only=True)
    model=fpnet.FPNet(checkpoint['nbits'],d=checkpoint['d'],layers=checkpoint['layers'],heads=checkpoint.get('heads',8))
    model.load_state_dict(checkpoint['model'],strict=True);model=model.to(device).eval();del checkpoint
    items=[]
    for row in query.itertuples():
        ce=np.asarray(row.collision_energy_ev,dtype=float);ce=ce[np.isfinite(ce)]
        mz,it=fpnet.prep_peaks(row.ms2_mzs,row.ms2_normalized_intensities,row.precursor_mz)
        items.append({'mz':mz,'it':it,'prec':float(row.precursor_mz),'adduct_ix':chem.adduct_index(row.adduct),
                      'ce':float(ce.mean()) if len(ce) else 0.0,'ce_known':float(bool(len(ce))),
                      'n_merged':max(1,len(ce)),'mode':1.0 if row.ionization_mode=='positive' else -1.0})
    logits=[]
    with torch.inference_mode():
        for start in range(0,len(items),16):
            with torch.autocast('cuda',dtype=fpnet.autocast_dtype(device),enabled=device=='cuda'):
                value=model(*fpnet.collate(items[start:start+16],device))[0]
            logits.append(value.float().cpu().numpy())
    logits=np.concatenate(logits);nbits=model.nbits
    fold0_seconds=time.monotonic()-started
    if not np.isfinite(logits).all():raise ValueError('Nonfinite fold0 logits')
    packed=np.load(POOL/'pool_fp.npy',mmap_mode='r')
    if packed.shape[1]*8<nbits:raise ValueError('Fingerprint shape does not match fold0')
    groups=[];baseline=[];retrieval_audit=[]
    for mid,frame in query.groupby('molecule_id',sort=False):
        group=candidates[candidates.molecule_id.eq(mid)].copy()
        retrieval_audit.append({'molecule_id':mid,'candidate_smiles':';'.join(group.smiles)})
        if group.empty:
            baseline.append({'molecule_id':mid,'smiles':'INVALID_NO_MASS_WINDOW_CANDIDATES'});continue
        predicted=logits[frame.index.to_numpy()].mean(0)
        bits=np.unpackbits(np.asarray(packed[group.pid.to_numpy()]),axis=1)[:,:nbits].astype(np.float32)
        group['fold0_score']=bits@predicted
        group=group.sort_values('fold0_score',ascending=False,kind='stable').head(MAX_OUTPUT).copy()
        group['baseline_rank']=range(1,len(group)+1);groups.append(group)
        baseline.append({'molecule_id':mid,'smiles':';'.join(group.smiles)})
    del model,packed,logits
    if device=='cuda':torch.cuda.empty_cache()
    base=pd.DataFrame(baseline);base.to_csv(out/'baseline.csv',index=False)
    pd.DataFrame(retrieval_audit).to_csv(out/'candidate_audit.csv',index=False)
    fixed=pd.concat(groups,ignore_index=True) if groups else candidates.assign(fold0_score=[],baseline_rank=[])
    fixed.to_parquet(out/'fixed_candidates.parquet',index=False)
    model,feat,cfg=load_saner(device)
    saner_started=time.monotonic()
    treatment=[];scored=[];query_by_id={mid:frame for mid,frame in query.groupby('molecule_id',sort=False)}
    with torch.inference_mode():
        for mid in base.molecule_id:
            group=fixed[fixed.molecule_id.eq(mid)].copy()
            if group.empty:
                treatment.append({'molecule_id':mid,'smiles':'INVALID_NO_MASS_WINDOW_CANDIDATES'});continue
            records=[]
            for row in query_by_id[mid].itertuples():
                peaks,length=feat.peaks(row.ms2_mzs,row.ms2_normalized_intensities,row.precursor_mz,cfg['max_peaks'])
                if length<cfg['min_peaks']:continue
                meta,adduct=feat.metadata(row.precursor_mz,row.adduct,row.ionization_mode,row.collision_energy_ev)
                records.append((peaks,length,meta,adduct))
            if not records:raise ValueError(f'Saner has no usable spectra; no silent fallback: {mid}')
            z,p=model.encode_spectra(torch.tensor(np.stack([r[0] for r in records]),device=device),
                torch.tensor([r[1] for r in records],device=device,dtype=torch.long),
                torch.tensor(np.stack([r[2] for r in records]),device=device),torch.tensor([r[3] for r in records],device=device,dtype=torch.long))
            fps=torch.tensor(np.stack([feat.structure(s,cfg['fp_bits'])[-1] for s in group.smiles]),device=device,dtype=torch.float32)
            scores=(model.encode_molecules(fps)@z.mean(0)/cfg['temperature']+cfg['fp_score_weight']*(fps@p.mean(0))/cfg['fp_bits']).cpu().numpy()
            if not np.isfinite(scores).all():raise ValueError(f'Nonfinite Saner scores: {mid}')
            group['saner_score']=scores;order=rrf_order(group.fold0_score.to_numpy(),scores)
            group['treatment_rank']=0;group.iloc[order,group.columns.get_loc('treatment_rank')]=np.arange(1,len(group)+1)
            scored.append(group);treatment.append({'molecule_id':mid,'smiles':';'.join(group.iloc[order].smiles)})
            print(f'COMPONENT scored {mid} candidates={len(group)} spectra={len(records)}',flush=True)
    actual=pd.DataFrame(treatment);actual.to_csv(out/'treatment.csv',index=False)
    saner_seconds=time.monotonic()-saner_started
    if scored:pd.concat(scored,ignore_index=True).to_parquet(out/'component_scores.parquet',index=False)
    truth=pd.read_csv(out/'truth.csv',keep_default_na=False)
    report=evaluate_frames(truth,actual);control=evaluate_frames(truth,base)
    fixed_check=audit_fixed_candidates(truth,actual,base)
    if not fixed_check['equal']:raise ValueError('Fixed output candidate identities changed')
    add_candidate_audit(report,pd.DataFrame(retrieval_audit));report['baseline_metrics']=control['metrics']
    report['baseline_subsets']=control['subsets'];report['fixed_candidate_audit']=fixed_check
    report['paired_bootstrap']=paired_bootstrap(report['rows'],control['rows'])
    panel=dict(zip(truth.molecule_id,truth.panel));report['paired_bootstrap_by_panel']={
        str(value):paired_bootstrap([r for r in report['rows'] if panel[r['molecule_id']]==value],
                                   [r for r in control['rows'] if panel[r['molecule_id']]==value]) for value in truth.panel.unique()}
    report['plan_sha256']=sha(out/'plan.json');report['prepared_sha256']=sha(out/'prepared.json')
    report['scope']=plan['limitations'];write_json(out/'evaluation.json',report)
    write_json(out/'run_receipt.json',{'status':'complete','device':device,'gpu':torch.cuda.get_device_name() if device=='cuda' else None,
               'elapsed_seconds':time.monotonic()-started,'fold0_loading_and_spectra_seconds':fold0_seconds,'saner_scoring_seconds':saner_seconds,
               'peak_gpu_bytes':torch.cuda.max_memory_allocated() if device=='cuda' else None,
               'plan_sha256':sha(out/'plan.json'),'prepared_sha256':sha(out/'prepared.json'),
               'outputs':{name:sha(out/name) for name in ['baseline.csv','treatment.csv','candidate_audit.csv','evaluation.json']}})
    print(json.dumps({'baseline':control['metrics'],'treatment':report['metrics'],'paired':report['paired_bootstrap']},indent=2))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=['plan','prepare','run'],default='plan')
    parser.add_argument('--output-dir',type=Path,default=ROOT/'runs/component_neural_pilot_20261105')
    parser.add_argument('--molecules',type=int,default=32)
    parser.add_argument('--device',choices=['cpu','cuda'],default='cuda')
    args=parser.parse_args();out=args.output_dir.resolve()
    if not out.is_relative_to(ROOT):parser.error('Output must remain inside the D: workspace')
    if args.molecules<1:parser.error('--molecules must be positive')
    out.mkdir(parents=True,exist_ok=True)
    if args.mode=='plan':
        if (out/'prepared.json').exists():raise FileExistsError('Prepared directory is frozen; choose a new output root')
        plan=build_plan(args.molecules);write_json(out/'plan.json',plan)
        print(json.dumps({'status':plan['status'],'molecules':plan['molecules'],'final_locked_excluded':plan['locked_final_excluded_identities'],'path':str(out/'plan.json')},indent=2))
    else:
        plan=json.loads((out/'plan.json').read_text())
        if args.mode=='prepare':
            if (out/'prepared.json').exists():raise FileExistsError('Preparation already exists; use a new output root')
            prepare(plan,out)
        else:
            if (out/'run_receipt.json').exists():raise FileExistsError('Run already completed; use a new output root')
            started=time.monotonic()
            try:run(plan,out,args.device)
            except BaseException:
                import traceback
                write_json(out/'failure.json',{'status':'failed','seconds':time.monotonic()-started,'traceback':traceback.format_exc()})
                raise


if __name__=='__main__':main()
