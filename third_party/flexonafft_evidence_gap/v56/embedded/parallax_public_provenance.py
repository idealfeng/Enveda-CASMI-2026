from __future__ import annotations
import json
import math
import time
import hashlib
import shutil
from pathlib import Path
from functools import lru_cache

import numpy as np
import pandas as pd
from rdkit import Chem
from rdkit.Chem import rdMolDescriptors
import frag_rescore as frag

@lru_cache(maxsize=40000)
def formula(s):
    m = Chem.MolFromSmiles(str(s))
    return rdMolDescriptors.CalcMolFormula(m) if m is not None else None

def number(x, default=float('nan')):
    try:
        v=float(x)
        return v if math.isfinite(v) else default
    except Exception:
        return default

def member_keys(comp):
    frame=pd.read_parquet(Path(comp)/'train.parquet',columns=['inchikey14'])
    return set(frame.inchikey14.dropna().astype(str))

def balanced_spectra(query, max_groups=12):
    groups={}
    for r in query.itertuples(index=False):
        mz=np.asarray(r.ms2_mzs, dtype=np.float64).ravel()
        it=np.asarray(r.ms2_normalized_intensities, dtype=np.float64).ravel()
        n=min(len(mz),len(it));mz,it=mz[:n],it[:n]
        ok=np.isfinite(mz)&np.isfinite(it)&(it>0)
        if ok.sum()<6:continue
        order=np.argsort(it[ok])[-120:]
        mz,it=mz[ok][order],it[ok][order]
        energy=number(getattr(r,'collision_energy_ev',30.),30.)
        adduct=str(getattr(r,'adduct','[M+H]+'))
        mode=1 if str(getattr(r,'ionization_mode','positive')).lower()=='positive' else -1
        spec={'mz':mz,'it':it,'prec':number(getattr(r,'precursor_mz',None),float(mz.max())),
              'adduct':adduct,'mode':mode}
        bucket=(adduct,int(round(energy/10.)))
        groups.setdefault(bucket,[]).append((int(ok.sum()), spec))
    chosen=[]
    for group in sorted(groups):
        chosen.extend(s for _,s in sorted(groups[group],key=lambda x:-x[0])[:2])
    return chosen[:max_groups]

def evidence_rows(df, order):
    data=df.drop_duplicates('smiles').set_index('smiles',drop=False)
    if any(s not in data.index for s in order):
        return None
    if ('neural_ok' in data and not data.loc[order,'neural_ok'].astype(bool).all()):
        return None
    if ('processed' in data and not data.loc[order,'processed'].astype(bool).all()):
        return None
    return data

def source_votes(candidate, leader):
    good=0;bad=0
    for label in ('engine2_rank','pubchem_rank','main_rank'):
        c=number(candidate.get(label),0.);l=number(leader.get(label),0.)
        if 0<c<=6:good+=1
        if 0<l<=4 and (c<=0 or c>12):bad+=1
    sim=0
    for label in ('ice','gl'):
        c=number(candidate.get(label));l=number(leader.get(label))
        if math.isfinite(c) and math.isfinite(l):
            if c>=l-.025:sim+=1
            elif c<l-.30:sim-=1
    return good,bad,sim

def paired_scores(spectra, smiles, cache):
    matrix=[];matrix_old=[]
    for spectrum in spectra:
        vals=frag.score_molecule([spectrum],smiles,cache=cache)
        old=frag.score_molecule([spectrum],smiles,cfg=frag.BASELINE_CFG,cache=cache)
        if any(x is None or not math.isfinite(float(x)) for x in vals+old):return None
        matrix.append(vals)
        matrix_old.append(old)
    return np.asarray(matrix,dtype=float),np.asarray(matrix_old,dtype=float)

def propose(order, original, data, query, train, cache):
    record={'action':'none','top1_changed':False,'swaps':0,'n_spectra':0,
            'protected_train':False,'physical_gain':None,'neural_gain_sd':None}
    if len(order)<4 or not order or original[0]!=order[0]:
        record['action']='protected_previous_top1';return order,record
    evid=evidence_rows(data,order)
    if evid is None:
        record['action']='incomplete_evidence';return order,record
    keys=[str(evid.loc[s,'metric_key']) if 'metric_key' in evid.columns else '' for s in order]
    trained=np.asarray([k in train for k in keys],dtype=bool)
    record['protected_train']=bool(trained.any())
    leader=order[0]
    if formula(leader) is None:
        return order,record
    lib=number(evid.loc[leader].get('library_max'),0.)
    if lib>=.90:
        record['action']='library_protected';return order,record
    selected=balanced_spectra(query)
    record['n_spectra']=len(selected)
    if len(selected)<3:
        record['action']='insufficient_spectra';return order,record
    head=order[:min(10,len(order))]
    p=paired_scores(selected,head,cache)
    if p is None:
        record['action']='fragment_unavailable';return order,record
    a,b=p
    neu=np.asarray([number(evid.loc[s].get('neural_score')) for s in order],float)
    if not np.isfinite(neu).all():
        record['action']='neural_unavailable';return order,record
    ns=max(float(neu.std()),.00001)
    updated=list(order)
    candidates=[]
    if not trained[0]:
        for i in range(1,min(6,len(head))):
            if trained[i] or formula(head[i])!=formula(leader):continue
            new_margin=a[:,i]-a[:,0]
            old_margin=b[:,i]-b[:,0]
            mean=float(np.mean(new_margin));med=float(np.median(new_margin))
            low=float(np.quantile(new_margin,.25));votes=float((new_margin>.020).mean())
            old=float(np.mean(old_margin))
            nz=float((neu[i]-neu[0])/ns)
            if mean<.095 or med<.070 or low<-.010 or votes<.75 or old<.022 or nz<.18:continue
            ev=evid.loc[head[i]];lv=evid.loc[leader]
            if number(ev.get('neural_cos'),0.)<number(lv.get('neural_cos'),0.)+.002:continue
            if number(ev.get('neural_fp'),0.)<number(lv.get('neural_fp'),0.)-.010:continue
            votes_source,bad,sim=source_votes(ev,lv)
            if votes_source<1 and sim<1:continue
            if bad>=2 or sim<0:continue
            confidence=mean+.045*nz+.020*sim+.010*votes_source+.018*max(0,low)
            candidates.append((confidence,i,mean,nz))
        if candidates:
            _,idx,gain,nz=max(candidates)
            updated.insert(0,updated.pop(idx))
            record.update(action='provenance_spectral_top1',top1_changed=True,
                          physical_gain=round(gain,5),neural_gain_sd=round(nz,4))
    swaps=0
    for pos in range(1,min(8,len(updated)-1)):
        before=updated[pos];after=updated[pos+1]
        if formula(before)!=formula(after):continue
        i,j=head.index(before) if before in head else -1, head.index(after) if after in head else -1
        if i<0 or j<0:continue
        if trained[i] or trained[j]:continue
        d=a[:,j]-a[:,i];do=b[:,j]-b[:,i]
        if float(np.mean(d))<.068 or float(np.median(d))<.045 or float((d>.010).mean())<.67:continue
        if float(np.mean(do))<.015:continue
        if neu[j]-neu[i]<-.04*ns:continue
        c=source_votes(evid.loc[after],evid.loc[before])[0]
        if c<1 and neu[j]<=neu[i]:continue
        updated[pos],updated[pos+1]=updated[pos+1],updated[pos]
        swaps+=1
        if swaps>=2:break
    record['swaps']=swaps
    if swaps and not record['top1_changed']:record['action']='paired_energy_swap'
    # The private 0.475 model freezes known training candidates. This public analogue
    # only allows permutations among untrained structures, preserving every training slot.
    for i,s in enumerate(order):
        if trained[i] and updated[i]!=s:
            return order,dict(record,action='training_slot_guard',top1_changed=False,swaps=0)
    return updated,record

def run(root,comp,time_budget=900):
    root=Path(root);comp=Path(comp)
    path=root/'submission.csv'
    control=root/'submission_control_V2.csv'
    for req in [path,control,root/'neural_candidate_features.parquet',root/'effective_query_spectra.parquet',comp/'train.parquet']:
        if not req.exists():raise FileNotFoundError(req)
    existing=pd.read_csv(path,dtype=str,keep_default_na=False)
    first=pd.read_csv(control,dtype=str,keep_default_na=False)
    assert existing.molecule_id.tolist()==first.molecule_id.tolist()
    assert existing.molecule_id.is_unique
    shutil.copy2(path,root/'submission_physical0472_control.csv')
    nfeatures=pd.read_parquet(root/'neural_candidate_features.parquet')
    spectra=pd.read_parquet(root/'effective_query_spectra.parquet')
    groups={str(m):df for m,df in nfeatures.groupby('molecule_id',sort=False)}
    specgroups={str(m):df for m,df in spectra.groupby('molecule_id',sort=False)}
    known=member_keys(comp)
    frag.warmup()
    t0=time.monotonic();cache={};newrows=[];audits=[]
    for idx,(record,ctrl) in enumerate(zip(existing.itertuples(index=False),first.itertuples(index=False))):
        mid=str(record.molecule_id)
        arr=str(record.smiles).split(';');original=str(ctrl.smiles).split(';')
        if time.monotonic()-t0>time_budget:
            new=arr;meta={'action':'runtime_budget','top1_changed':False,'swaps':0}
        elif mid not in groups or mid not in specgroups:
            new=arr;meta={'action':'no_source_spectra','top1_changed':False,'swaps':0}
        else:
            try:
                new,meta=propose(arr,original,groups[mid],specgroups[mid],known,cache)
            except Exception as e:
                new=arr;meta={'action':'failed_'+type(e).__name__,'top1_changed':False,'swaps':0}
        if set(new)!=set(arr) or len(new)!=len(arr):
            raise AssertionError('Candidate identities may not change')
        newrows.append((mid,';'.join(new)))
        audits.append({'molecule_id':mid,**meta})
        if len(cache)>25000:cache.clear()
        if (idx+1)%50==0:
            print('PROVENANCE',idx+1,'/',len(existing),'elapsed',round(time.monotonic()-t0,1),'s',flush=True)
    result=pd.DataFrame(newrows,columns=['molecule_id','smiles'])
    assert result.molecule_id.tolist()==existing.molecule_id.tolist()
    assert result.molecule_id.is_unique
    assert result.smiles.str.split(';').map(len).between(1,25).all()
    assert result.smiles.str.split(';').map(lambda a:len(set(a))==len(a) and all(a)).all()
    temp=root/'submission.provenance.tmp.csv'
    result.to_csv(temp,index=False)
    assert pd.read_csv(temp,dtype=str,keep_default_na=False).equals(result)
    temp.replace(path)
    report=pd.DataFrame(audits)
    report.to_csv(root/'provenance_tournament_audit.csv',index=False)
    summary={'source':'0.472 physical consensus public pipeline',
             'private_rr3_weights_used':False,'train_structure_keys':len(known),
             'rows':len(result),'changed':int((existing.smiles!=result.smiles).sum()),
             'top1_changed':int(report.top1_changed.fillna(False).astype(bool).sum()),
             'adjacent_swaps':int(report.swaps.fillna(0).sum()),
             'elapsed_seconds':round(time.monotonic()-t0,2),
             'control_hash':hashlib.sha256((root/'submission_physical0472_control.csv').read_bytes()).hexdigest(),
             'final_hash':hashlib.sha256(path.read_bytes()).hexdigest(),
             'note':'Leaderboard improvement not validated'}
    (root/'provenance_tournament_report.json').write_text(json.dumps(summary,indent=2))
    print('PROVENANCE_REPORT',json.dumps(summary),flush=True)
    return summary
