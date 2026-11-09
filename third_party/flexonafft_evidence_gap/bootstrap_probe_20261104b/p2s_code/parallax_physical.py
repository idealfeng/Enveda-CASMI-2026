from __future__ import annotations
import hashlib
import json
import math
import os
import time
from functools import lru_cache
from pathlib import Path
import numpy as np
import pandas as pd
from rdkit import Chem
from rdkit.Chem import rdMolDescriptors

@lru_cache(maxsize=30000)
def mol_formula(s):
    try:
        m = Chem.MolFromSmiles(str(s))
        return rdMolDescriptors.CalcMolFormula(m) if m is not None else None
    except Exception:
        return None

def finite(x,default=np.nan):
    try:
        t=float(x)
        return t if np.isfinite(t) else default
    except (ValueError,TypeError):
        return default

def select_spectra(frame,max_n=12):
    out=[]
    by_bucket={}
    for r in frame.itertuples(index=False):
        mz=np.asarray(r.ms2_mzs,dtype=float).ravel()
        it=np.asarray(r.ms2_normalized_intensities,dtype=float).ravel()
        n=min(len(mz),len(it));mz,it=mz[:n],it[:n]
        good=np.isfinite(mz)&np.isfinite(it)&(it>0)
        if good.sum()<5:continue
        order=np.argsort(it[good])[-120:]
        mz,it=mz[good][order],it[good][order]
        e=finite(getattr(r,'collision_energy_ev',30),30.)
        adduct=str(getattr(r,'adduct','[M+H]+'))
        mode=1 if str(getattr(r,'ionization_mode','positive')).lower()=='positive' else -1
        item={'mz':mz,'it':it,'adduct':adduct,'prec':finite(getattr(r,'precursor_mz',None),float(mz.max())),'mode':mode}
        bucket=(adduct,round(e/10))
        by_bucket.setdefault(bucket,[]).append((int(good.sum()),item))
    for key in sorted(by_bucket):
        out += [v for _,v in sorted(by_bucket[key],key=lambda x:-x[0])[:2]]
    return out[:max_n]

def support(payload,mid,s):
    eng=(payload.get('engine2',{}).get(mid) or {}).get('smiles') or []
    pc=(payload.get('pubchem',{}).get(mid) or {}).get('pc') or []
    main=payload.get('base_tail',{}).get(mid) or []
    fusion=payload.get('fusion_overflow',{}).get(mid) or []
    def rank(v):return v.index(s)+1 if s in v else 0
    return dict(engine2=rank(eng),pubchem=rank(pc),main=rank(main),fusion=rank(fusion))

def score_candidates(frag,spec,candidates,cache):
    if not spec:return None
    opt=np.asarray([np.nan if a is None else a for a in frag.score_molecule(spec,candidates,cache=cache)],float)
    old=np.asarray([np.nan if a is None else a for a in frag.score_molecule(spec,candidates,cfg=frag.BASELINE_CFG,cache=cache)],float)
    if not np.isfinite(opt).all() or not np.isfinite(old).all():return None
    chunks=[spec[i:i+2] for i in range(0,len(spec),2)]
    group=np.array([[np.nan if v is None else v for v in frag.score_molecule(ch,candidates,cache=cache)] for ch in chunks],float)
    return opt,old,group

def decision(mid,control,listed,outs,query,payload,frag,cache,allow_tail=True,allow_top=True):
    diag={'molecule_id':mid,'top1_changed':False,'tail_changed':False,'local_swaps':0,'reason':'unchanged','n_spectra':0,
          'candidate_count':len(control),'top1_frag_margin':0.,'top1_neural_margin':0.,'new_candidate_source':''}
    bysmiles=listed.set_index('smiles',drop=False)
    if len(bysmiles)!=len(listed) or any(s not in bysmiles.index for s in control):
        diag['reason']='evidence_mismatch';return control,diag
    if not bool(listed.neural_ok.all()) or not bool(listed.processed.all()):
        diag['reason']='unscored';return control,diag
    n=len(control)
    if n<3:return control,diag
    anchor=mol_formula(control[0])
    if anchor is None:
        diag['reason']='formula_missing';return control,diag
    cand=list(control[:min(12,n)])
    outrows=[]
    if allow_tail and outs is not None and len(outs) and n>=20:
        for row in outs.sort_values('baseline_rank').itertuples(index=False):
            if not bool(row.neural_ok) or not bool(row.processed):continue
            s=str(row.smiles)
            if s in control or mol_formula(s)!=anchor:continue
            ev=support(payload,mid,s)
            sources=int(bool(ev['engine2']))+int(bool(ev['pubchem']))+int(bool(ev['main']))
            if sources<2 and not (0<ev['fusion']<=3):continue
            outrows.append(row)
            cand.append(s)
            if len(outrows)>=8:break
    spec=select_spectra(query)
    diag['n_spectra']=len(spec)
    if len(spec)<2:
        diag['reason']='few_spectra';return control,diag
    data=score_candidates(frag,spec,cand,cache)
    if data is None:
        diag['reason']='frag_unavailable';return control,diag
    frag_new,frag_old,energy=data
    pos={s:i for i,s in enumerate(cand)}
    leader=control[0];lp=pos[leader]
    neu_vals=np.asarray([finite(x) for x in listed.neural_score],float)
    neural_sd=max(float(np.nanstd(neu_vals)),1e-6)
    result=list(control)
    lib=finite(bysmiles.loc[leader,'library_max'],0.)
    if allow_top and lib<.87 and len(spec)>=3:
        contenders=[]
        for ix,s in enumerate(control[1:min(6,n)],1):
            if mol_formula(s)!=anchor:continue
            j=pos[s]; ev=bysmiles.loc[s]; lead_ev=bysmiles.loc[leader]
            if not np.isfinite(frag_new[j]) or frag_new[j]<.27:continue
            margin=float(frag_new[j]-frag_new[lp]); oldmargin=float(frag_old[j]-frag_old[lp])
            if margin<.095 or oldmargin<.028:continue
            votes=float((energy[:,j]>energy[:,lp]+.025).mean())
            if votes<.70:continue
            nmargin=(finite(ev.neural_score)-finite(lead_ev.neural_score))/neural_sd
            if not np.isfinite(nmargin) or nmargin<.23:continue
            if finite(ev.neural_cos)<finite(lead_ev.neural_cos)+.003 or finite(ev.neural_fp)<finite(lead_ev.neural_fp)-.012:continue
            supports=0
            for col in ('engine2_rank','pubchem_rank','main_rank'):
                rank=finite(ev.get(col),0)
                if 0<rank<=5:supports+=1
            simulator_vote=0
            for col in ('ice','gl'):
                a,b=finite(ev.get(col)),finite(lead_ev.get(col))
                if np.isfinite(a) and np.isfinite(b):
                    if a>=b:simulator_vote+=1
                    elif a<b-.35:simulator_vote-=1
            if supports<1 and simulator_vote<1:continue
            if simulator_vote<=-1:continue
            contenders.append((margin+.05*nmargin+.025*simulator_vote+.01*supports,s,margin,nmargin))
        if contenders:
            _,winner,margin,nmargin=max(contenders,key=lambda v:v[0])
            result.remove(winner);result.insert(0,winner)
            diag.update(top1_changed=True,top1_frag_margin=round(margin,5),top1_neural_margin=round(nmargin,5),reason='fragment_neural_top1')
    swaps=0
    for i in range(2,min(11,n)):
        prev,s=result[i-1],result[i]
        if mol_formula(prev)!=mol_formula(s):continue
        j,k=pos.get(s),pos.get(prev)
        if j is None or k is None:continue
        if frag_new[j]-frag_new[k]<.085 or frag_old[j]-frag_old[k]<.015:continue
        if (energy[:,j]>energy[:,k]+.010).mean()<.65:continue
        neui,neup=finite(bysmiles.loc[s,'neural_score']),finite(bysmiles.loc[prev,'neural_score'])
        if not np.isfinite(neui) or neui<neup-.08*neural_sd:continue
        result[i-1],result[i]=result[i],result[i-1]
        swaps+=1
        if swaps>=2:break
    diag['local_swaps']=swaps
    if not diag['top1_changed'] and swaps:diag['reason']='adjacent_fragment_consensus'
    if allow_tail and outrows and len(result)==25:
        last=result[-1]
        if last in pos:
            lastp=pos[last]
            eligible=[]
            listed_keys=set(listed.metric_key.dropna().astype(str))
            for row in outrows:
                s=str(row.smiles);j=pos[s]
                if not isinstance(row.metric_key,str) or row.metric_key in listed_keys:continue
                if not np.isfinite(frag_new[j]) or frag_new[j]<.28:continue
                fm=float(frag_new[j]-frag_new[lastp])
                if fm<.065 or frag_old[j]-frag_old[lastp]<.02:continue
                if (energy[:,j]>energy[:,lastp]+.01).mean()<.65:continue
                if finite(row.neural_score)<finite(bysmiles.loc[last,'neural_score'])+.22*neural_sd:continue
                if finite(row.neural_cos)<=finite(bysmiles.loc[last,'neural_cos']) or finite(row.neural_fp)<=finite(bysmiles.loc[last,'neural_fp']):continue
                ev=support(payload,mid,s)
                supports=int(bool(ev['main']))+int(bool(ev['engine2']))+int(bool(ev['pubchem']))
                eligible.append((fm,s,ev,supports))
            if eligible:
                margin,s,ev,supports=max(eligible,key=lambda q:q[0]+.015*q[3])
                result[-1]=s
                diag.update(tail_changed=True,new_candidate_source='+' .join(k for k in ('main','engine2','pubchem','fusion') if ev[k]),reason='tail_supported' if not diag['top1_changed'] and not swaps else diag['reason'])
    assert len(result)==len(control) and len(set(result))==len(result)
    assert set(result[:-1]).issubset(set(control)) and not (diag['top1_changed'] and result[0]==control[0])
    return result,diag

def apply(root,comp,max_seconds=1500,allow_tail=True,allow_top=True):
    import frag_rescore as frag
    root=Path(root);comp=Path(comp)
    control=root/'variants/submission_V2.csv'
    if not control.is_file():raise FileNotFoundError(control)
    src=pd.read_csv(control,dtype=str,keep_default_na=False)
    need=['molecule_id','smiles','metric_key','processed','neural_ok','neural_score','neural_cos','neural_fp','baseline_rank']
    listed=pd.read_parquet(root/'neural_candidate_features.parquet')
    if not set(need).issubset(listed.columns):raise ValueError('Neural evidence columns missing')
    outsiders_path=root/'outsider_neural_features.parquet'
    outsider=pd.read_parquet(outsiders_path) if outsiders_path.is_file() else pd.DataFrame()
    q=pd.read_parquet(root/'effective_query_spectra.parquet')
    payload=json.loads((root/'e004_candidate_inputs.json').read_text())
    lmap={str(mid):g.sort_values('baseline_rank') for mid,g in listed.groupby('molecule_id',sort=False)}
    omap={str(mid):g for mid,g in outsider.groupby('molecule_id',sort=False)} if len(outsider) else {}
    qmap={str(mid):g for mid,g in q.groupby('molecule_id',sort=False)}
    start=time.monotonic()
    cache={}; rows=[];audits=[];expired=False
    frag.warmup()
    for i,(mid,smiles) in enumerate(src.itertuples(index=False)):
        mid=str(mid);old=smiles.split(';')
        if time.monotonic()-start>max_seconds:
            expired=True
            rows.append((mid,smiles));audits.append(dict(molecule_id=mid,reason='time_budget',top1_changed=False,tail_changed=False,local_swaps=0))
            continue
        if mid not in lmap or mid not in qmap:
            rows.append((mid,smiles));audits.append(dict(molecule_id=mid,reason='not_processed',top1_changed=False,tail_changed=False,local_swaps=0))
            continue
        try:
            new,meta=decision(mid,old,lmap[mid],omap.get(mid),qmap[mid],payload,frag,cache,allow_tail=allow_tail,allow_top=allow_top)
        except Exception as exc:
            new,meta=old,dict(molecule_id=mid,reason='error:'+type(exc).__name__,top1_changed=False,tail_changed=False,local_swaps=0)
        rows.append((mid,';'.join(new)));audits.append(meta)
        if (i+1)%40==0:print('PARALLAX',i+1,'/',len(src),'elapsed',round(time.monotonic()-start,1),'s',flush=True)
        if len(cache)>35000:cache.clear()
    dest=pd.DataFrame(rows,columns=['molecule_id','smiles'])
    ids=pd.read_parquet(comp/'test.parquet',columns=['molecule_id']).molecule_id.astype(str).unique().tolist()
    if dest.molecule_id.tolist()!=src.molecule_id.tolist() or set(ids)!=set(dest.molecule_id):raise AssertionError('Molecule coverage changed')
    for initial,new in zip(src.smiles,dest.smiles):
        before=initial.split(';');after=new.split(';')
        if not 1<=len(after)<=25 or len(after)!=len(set(after)) or any(not k for k in after):raise AssertionError('Submission format')
        if after[0] not in before or not set(after[:-1]).issubset(set(before)):raise AssertionError('Unsafe candidate replacement')
        if len(set(after)-set(before))>1:raise AssertionError('Too many outsiders')
    out=root/'submission.csv';temp=root/'submission.parallax.tmp'
    dest.to_csv(temp,index=False)
    reread=pd.read_csv(temp,dtype=str,keep_default_na=False)
    if not reread.equals(dest):raise AssertionError('CSV roundtrip failed')
    temp.replace(out)
    report=pd.DataFrame(audits)
    report.to_csv(root/'spectral_parallax_audit.csv',index=False)
    diagnostics={'control_sha256':hashlib.sha256(control.read_bytes()).hexdigest(),
        'submission_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),
        'rows':len(dest),'changed_rows':int((src.smiles!=dest.smiles).sum()),
        'top1_changed':int(sum(bool(r.get('top1_changed')) for r in audits)),
        'tail_changed':int(sum(bool(r.get('tail_changed')) for r in audits)),
        'adjacent_swaps':int(sum(int(r.get('local_swaps',0)) for r in audits)),
        'time_budget_exceeded':expired,'elapsed_seconds':round(time.monotonic()-start,2),
        'outcome':'experimental_unvalidated','baseline':'V2_0.468_user_reported'}
    (root/'spectral_parallax_report.json').write_text(json.dumps(diagnostics,indent=2))
    print('PARALLAX REPORT',json.dumps(diagnostics),flush=True)
    return diagnostics
