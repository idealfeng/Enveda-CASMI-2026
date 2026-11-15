"""Fixed AB vs AB+C retrieval experiment using existing spectra and candidate controls.

No model inference or coefficient search. Ground truth is opened only after the
real score table is frozen, for evaluation and all-reference identity exclusion.
"""
from pathlib import Path
from collections import Counter, defaultdict
import ast,csv,gc,hashlib,json,math,os,resource,sys,time,traceback

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.cache/rdkit-official-linux-2026033'))
sys.path.insert(0,str(ROOT))
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from validation import metric

OUT=ROOT/'runs/extlib2_matching_20261114_v2'
REPORT=ROOT/'reports/extlib2_matching_20261114'
PROD=ROOT/'runs/generation_production_20261113_r2/kaggle/working'
OLD=ROOT/'runs/validation_flex_c2_20261105d'
CROOT=ROOT/'assets/kaggle/nakhun/casmi26-extlib2/v1/extlib2'
A=ROOT/'assets/kaggle/takumuhata/casmi26-extlib/v2'
B=ROOT/'assets/kaggle/samartalwar/casmi-2026-spectral-library-massbankharmonized/v1/spectra.parquet'
SOURCE=PROD/'p2s_code/alex_v12_external_function.py'
CONFIG=dict(cosine_threshold=.8,matched_peaks=4,fragment_tolerance=.015,
    precursor_ppm=10.,precursor_da=.002,mode_only=True,source_C_real_recorded_precursor=True,
    original_pipeline_protection=.9,protect_accepted_AB=True,policy='gap_fill_only',new_candidates_allowed=True)
FIELDS=['molecule_id','spectrum_id','precursor_mz','adduct','ionization_mode','ms2_mzs','ms2_normalized_intensities']

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_name(p.name+'.tmp');tmp.write_text(json.dumps(x,indent=2,allow_nan=False)+'\n');tmp.replace(p)
def cosine_source():
    tree=ast.parse(SOURCE.read_text());fn=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='calc_cosine')
    scope={'np':np};exec(compile(ast.Module(body=[fn],type_ignores=[]),'original_AB_cosine','exec'),scope)
    return scope['calc_cosine']

def query_rows(path,scope):
    frame=pd.read_parquet(path,columns=FIELDS)
    result=[]
    for r in frame.itertuples(index=False):
        mz,it=np.asarray(r.ms2_mzs,dtype=np.float64),np.asarray(r.ms2_normalized_intensities,dtype=np.float64)
        prec=float(r.precursor_mz);ok=(mz>0)&(it>0)&(mz<=prec+.5);mz,it=mz[ok],it[ok];order=np.argsort(mz)
        result.append(dict(scope=scope,mid=str(r.molecule_id),spectrum_id=str(r.spectrum_id),prec=prec,
                           mode=1 if 'pos' in str(r.ionization_mode).lower() else -1,adduct=str(r.adduct),mz=mz[order],it=it[order]))
    return result

def eligible(metadata,queries,prec_column='precursor_mz',mode_column='ionization_mode'):
    prec=metadata[prec_column].to_numpy(dtype=np.float64)
    modes=np.where(metadata[mode_column].astype(str).str.lower().str.contains('pos'),1,-1)
    order=np.argsort(prec,kind='stable');mass=prec[order];wanted=set();by_query=[]
    for q in queries:
        tol=q['prec']*1e-5+.002;lo=np.searchsorted(mass,q['prec']-tol,'left');hi=np.searchsorted(mass,q['prec']+tol,'right')
        rows=order[lo:hi];rows=rows[modes[rows]==q['mode']];by_query.append([int(i) for i in rows]);wanted.update(int(i) for i in rows)
    return by_query,wanted

def match_library(label,queries,cosine):
    tick=time.monotonic()
    if label=='A':
        meta=pd.read_parquet(A/'ext_meta.parquet',columns=['precursor_mz','ionization_mode','normalized_smiles'])
        # Mirror the original function: a mono_mass column is NOT an
        # exact_mass column, so this optional filter is only active if named.
        if 'exact_mass' in pq.ParquetFile(A/'ext_mass.parquet').schema_arrow.names:
            masses=pd.read_parquet(A/'ext_mass.parquet',columns=['exact_mass']).exact_mass.to_numpy()
            valid=np.isfinite(masses)&(masses>0)
        else:valid=np.ones(len(meta),dtype=bool)
        meta['_row']=np.arange(len(meta));meta=meta[valid].reset_index(drop=True)
        rows,wanted=eligible(meta,queries)
        mz=np.load(A/'ext_mz.npy',mmap_mode='r',allow_pickle=False);it=np.load(A/'ext_in.npy',mmap_mode='r',allow_pickle=False)
        def ref(i):
            raw=meta.iloc[i];j=int(raw['_row']);return str(raw.normalized_smiles),np.asarray(mz[j],dtype=np.float64),np.asarray(it[j],dtype=np.float64)
        source_files=[A/'ext_meta.parquet',A/'ext_mass.parquet',A/'ext_mz.npy',A/'ext_in.npy']
    elif label=='B':
        raw=pd.read_parquet(B,columns=['smiles','exact_mass','ion_mode','is_casmi_subset'])
        raw['_physical_row']=np.arange(len(raw));raw=raw[(~raw.is_casmi_subset.astype(bool))&raw.smiles.notna()].copy()
        mode=np.where(raw.ion_mode.astype(str).str.lower().str.contains('pos'),1,-1)
        raw['precursor_mz']=raw.exact_mass.to_numpy(dtype=np.float64)+1.007276*mode
        raw['ionization_mode']=np.where(mode==1,'positive','negative');meta=raw.reset_index(drop=True)
        rows,wanted=eligible(meta,queries);physical={int(meta.iloc[i]['_physical_row']):i for i in wanted};spectra={};offset=0
        for batch in pq.ParquetFile(B).iter_batches(columns=['mzs','intensities'],batch_size=4096):
            choices=[j for j in range(batch.num_rows) if offset+j in physical]
            if choices:
                part=batch.take(np.asarray(choices,dtype=np.int64)).to_pydict()
                for local,mzv,itv in zip(choices,part['mzs'],part['intensities']):
                    spectra[physical[offset+local]]=(np.asarray(mzv,dtype=np.float64),np.asarray(itv,dtype=np.float64))
            offset+=batch.num_rows
        def ref(i):return str(meta.iloc[i].smiles),*spectra[i]
        source_files=[B]
    else:
        meta=pd.read_parquet(CROOT/'ext2_meta.parquet',columns=['precursor_mz','ionization_mode','normalized_smiles','source','adduct'])
        rows,wanted=eligible(meta,queries);mz=np.load(CROOT/'ext2_mz_flat.npy',mmap_mode='r',allow_pickle=False);it=np.load(CROOT/'ext2_in_flat.npy',mmap_mode='r',allow_pickle=False);offsets=np.load(CROOT/'ext2_offsets.npy',mmap_mode='r',allow_pickle=False)
        if len(offsets)!=len(meta)+1 or offsets[0]!=0 or offsets[-1]!=len(mz) or len(mz)!=len(it):raise ValueError('C array offsets invalid')
        def ref(i):
            a,z=int(offsets[i]),int(offsets[i+1]);return str(meta.iloc[i].normalized_smiles),np.asarray(mz[a:z],dtype=np.float64),np.asarray(it[a:z],dtype=np.float64)
        source_files=[CROOT/n for n in ['ext2_meta.parquet','ext2_mz_flat.npy','ext2_in_flat.npy','ext2_offsets.npy']]
    prepared={};invalid=0
    for i in sorted(wanted):
        smi,mzv,itv=ref(i);ok=(mzv>0)&(itv>0);mzv,itv=mzv[ok],itv[ok]
        if len(mzv)<3:continue
        order=np.argsort(mzv);key=metric.identity(smi)
        if key is None:invalid+=1;continue
        prepared[i]=(smi,key,mzv[order],itv[order])
    hits=defaultdict(list);pairs=0
    for q,rr in zip(queries,rows):
        for i in rr:
            if i not in prepared:continue
            smi,key,mzv,itv=prepared[i];cos,k=cosine(q['mz'],q['it'],mzv,itv);pairs+=1
            if k>=CONFIG['matched_peaks']:
                hits[(q['scope'],q['mid'])].append(dict(source=label,row=i,spectrum_id=q['spectrum_id'],smiles=smi,identity=key,cosine=float(cos),matched_peaks=int(k),query_adduct=q['adduct'],reference_adduct=str(meta.iloc[i]['adduct']) if label=='C' else None))
    result=dict(source=label,metadata_rows=len(meta),mass_eligible_unique_refs=len(wanted),valid_prepared_refs=len(prepared),invalid_identity_refs=invalid,pairs=pairs,seconds=time.monotonic()-tick,source_files=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p)) for p in source_files],rows=[dict(scope=key[0],molecule_id=key[1],hits=value) for key,value in hits.items()])
    save(OUT/(label+'_actual_match_table.json'),result)
    print(json.dumps({k:v for k,v in result.items() if k not in ['rows','source_files']}),flush=True)
    return result

def dedup(raw):
    seen=set();out=[]
    for s in metric.parse_guesses(raw):
        k=metric.identity(s)
        if k and k not in seen:seen.add(k);out.append(s)
    return ';'.join(out)

def promote(raw,hit):
    if hit is None or hit['cosine']<CONFIG['cosine_threshold']:return raw,False,'no_hit'
    guesses=raw.split(';');keys=[metric.identity(s) for s in guesses];key=hit['identity']
    if key in keys:
        index=keys.index(key);proposal=[guesses[index]]+[s for i,s in enumerate(guesses) if i!=index]
    else:proposal=([hit['smiles']]+guesses)[:25]
    pkeys=[metric.identity(s) for s in proposal]
    if any(k is None for k in pkeys) or len(pkeys)!=len(set(pkeys)):
        return raw,False,'invalid_proposal_guard'
    result=';'.join(proposal);return result,result!=raw,'accepted'

def best(hits,exclude=None):
    items=[h for h in hits if h['identity']!=exclude]
    return max(items,key=lambda h:h['cosine']) if items else None

def rr(raw,key):
    for i,s in enumerate(metric.parse_guesses(raw),1):
        if metric.identity(s)==key:return 1./i
    return 0.

def main():
    OUT.mkdir(parents=True,exist_ok=True);REPORT.mkdir(parents=True,exist_ok=True)
    metric.assert_official_rdkit();started=time.monotonic()
    smoke_test=next((PROD.parent/'input').rglob('test.parquet'))
    old_test=ROOT/'runs/validation_pilot_v2_20261104/queries.parquet'
    queries=query_rows(smoke_test,'production2')+query_rows(old_test,'diagnostic48')
    # Freeze configuration and whitelisted query provenance before opening truth.
    save(OUT/'frozen_policy.json',dict(configuration=CONFIG,original_cosine_source_sha256=sha(SOURCE),query_columns=FIELDS,source_query_files=[dict(path=str(p.relative_to(ROOT)),sha256=sha(p)) for p in [smoke_test,old_test]],truth_used_for_matching=False))
    cosine=cosine_source();tables=[]
    for label in ['A','B','C']:
        target=OUT/(label+'_actual_match_table.json')
        if target.exists():table=json.loads(target.read_text())
        else:table=match_library(label,queries,cosine)
        tables.append(table);gc.collect()
    by_source={t['source']:{(r['scope'],r['molecule_id']):r['hits'] for r in t['rows']} for t in tables}
    frozen_tables={t['source']:sha(OUT/(t['source']+'_actual_match_table.json')) for t in tables}
    # Evaluation-only labels are read after all score artifacts are immutable.
    truth=pd.read_csv(ROOT/'runs/validation_pilot_v2_20261104/truth.csv',dtype=str).set_index('molecule_id')
    old_csv=OLD/'submission_e004_control.csv';raw_control=pd.read_csv(old_csv,dtype=str,keep_default_na=False)
    clean=raw_control.copy();clean.smiles=clean.smiles.map(dedup)
    if not all(clean.smiles.str.len()>0):raise ValueError('No valid diagnostic control candidate')
    clean.to_csv(OUT/'diagnostic_identity_deduplicated_control.csv',index=False)
    lib=pd.read_parquet(OLD/'frozen_candidate_evidence.parquet',columns=['molecule_id','library_max'])
    confidence={str(m):float(v) for m,v in lib.groupby('molecule_id',sort=False).library_max.first().items()}
    evaluation={};details=[]
    for arm in ['references_present','all_truth_references_absent']:
        outAB=[];outABC=[];events=[]
        for mid,raw in clean.itertuples(index=False,name=None):
            key=metric.identity(truth.loc[mid,'smiles']);exclude=key if arm=='all_truth_references_absent' else None
            abhits=by_source['A'].get(('diagnostic48',mid),[])+by_source['B'].get(('diagnostic48',mid),[]);chits=by_source['C'].get(('diagnostic48',mid),[])
            ah=best(abhits,exclude);ch=best(chits,exclude);protected=confidence.get(mid,0.)>=.9
            ab,abchange,abreason=promote(raw,None if protected else ah)
            ab_accepted=(not protected and ah is not None and ah['cosine']>=.8 and abreason=='accepted')
            abc,cchange,creason=promote(ab,None if protected or ab_accepted else ch)
            outAB.append(dict(molecule_id=mid,smiles=ab));outABC.append(dict(molecule_id=mid,smiles=abc))
            candidate_keys={metric.identity(s) for s in raw.split(';')}
            event=dict(arm=arm,molecule_id=mid,pipeline_protected=protected,AB_accepted=ab_accepted,AB_hit=ah,C_hit=ch,C_changed=cchange,C_reason=creason,AB_rr=rr(ab,key),ABC_rr=rr(abc,key),C_correct_identity=ch is not None and ch['identity']==key,C_identity_already_in_control=ch is not None and ch['identity'] in candidate_keys,C_truth_new_to_control=ch is not None and ch['identity']==key and key not in candidate_keys,C_wrong_same_formula=ch is not None and ch['identity']!=key and metric.molecular_formula(ch['smiles'])==metric.molecular_formula(truth.loc[mid,'smiles']),eligible_truth_refs_AB=sum(h['identity']==key for h in abhits),eligible_truth_refs_C=sum(h['identity']==key for h in chits))
            events.append(event)
        baseline=sum(e['AB_rr'] for e in events)/len(events);treatment=sum(e['ABC_rr'] for e in events)/len(events)
        evaluation[arm]=dict(queries=len(events),AB_mrr25=baseline,ABC_mrr25=treatment,delta=treatment-baseline,C_changed_queries=sum(e['C_changed'] for e in events),improved=sum(e['ABC_rr']>e['AB_rr'] for e in events),worsened=sum(e['ABC_rr']<e['AB_rr'] for e in events),C_high_cos_correct=sum(e['C_hit'] is not None and e['C_hit']['cosine']>=.8 and e['C_correct_identity'] for e in events),C_high_cos_wrong=sum(e['C_hit'] is not None and e['C_hit']['cosine']>=.8 and not e['C_correct_identity'] for e in events),C_high_cos_wrong_same_formula=sum(e['C_hit'] is not None and e['C_hit']['cosine']>=.8 and e['C_wrong_same_formula'] for e in events),AB_high_cos=sum(e['AB_hit'] is not None and e['AB_hit']['cosine']>=.8 for e in events),pipeline_protected=sum(e['pipeline_protected'] for e in events))
        pd.DataFrame(outAB).to_csv(OUT/(arm+'_AB.csv'),index=False);pd.DataFrame(outABC).to_csv(OUT/(arm+'_ABC.csv'),index=False);details+=events
    smoke=pd.read_csv(PROD/'submission.csv',dtype=str,keep_default_na=False)
    sb=pd.read_parquet(PROD/'frozen_candidate_evidence.parquet',columns=['molecule_id','library_max']);sc={str(m):float(v) for m,v in sb.groupby('molecule_id',sort=False).library_max.first().items()}
    smoke_rows=[]
    for mid,raw in smoke.itertuples(index=False,name=None):
        hit=best(by_source['C'].get(('production2',mid),[]));protected=sc.get(mid,0.)>=.9
        value,changed,reason=promote(raw,None if protected else hit)
        smoke_rows.append(dict(molecule_id=mid,protected=protected,C_hit=hit,changed=changed,reason=reason,smiles=value))
    save(OUT/'diagnostic_query_details.json',dict(rows=details,pipeline_library_max_context='Original cached first-stage library_max reused unchanged in both arms. Truth-absent AB/C exclusion does not rebuild all original pipeline inputs; not a full-stack class2 ablation.'))
    save(OUT/'production_subset_component.json',dict(scope='Original generated-variant two-query final control, not exact .488 candidate pool; no efficacy metric',queries=smoke_rows,control_sha256=sha(PROD/'submission.csv')))
    checks=dict(official_rdkit=metric.assert_official_rdkit()=='2026.03.3',real_AB_and_C_matching=all(t['pairs']>0 for t in tables),actual_score_artifacts_frozen=all(sha(OUT/(k+'_actual_match_table.json'))==v for k,v in frozen_tables.items()),whitelisted_spectrum_inputs=True,identity_controls_exclude_all_truth_hits=all(e['AB_hit'] is None or e['AB_hit']['identity']!=metric.identity(truth.loc[e['molecule_id'],'smiles']) for e in details if e['arm']=='all_truth_references_absent') and all(e['C_hit'] is None or e['C_hit']['identity']!=metric.identity(truth.loc[e['molecule_id'],'smiles']) for e in details if e['arm']=='all_truth_references_absent'),no_training=True,no_cloud_write=True)
    result=dict(status='passed_real_controlled_matching' if all(checks.values()) else 'failed',checks=checks,configuration=CONFIG,seconds=time.monotonic()-started,max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,source_script_sha256=sha(Path(__file__)),original_control_sha256=sha(old_csv),diagnostic_control_deduplicated_rows=int((clean.smiles!=raw_control.smiles).sum()),baseline_diagnostic_mrr=sum(rr(r.smiles,metric.identity(truth.loc[r.molecule_id,'smiles'])) for r in clean.itertuples(index=False))/len(clean),evaluations=evaluation,score_artifact_sha256=frozen_tables,production_component_changes=sum(r['changed'] for r in smoke_rows),pretrained_exposure='Existing old48 panel has known pretrained exposure; not clean CV. No new labels select policy.',exact_champion_full_pipeline=False,public_score=None,limitation='Old48 class2 stage lists are canonical-identity deduplicated consistently for both arms; AB/C controls reuse fixed matcher and same pipeline confidence. They are not exact current .488 predictions or hidden gains. Exclusion removes every considered reference sharing official truth identity in both AB and C, not just a raw key. 2-query component uses saved generation-variant control; no efficacy metric.')
    save(REPORT/'verification.json',result);print(json.dumps(result),flush=True)
    if not all(checks.values()):raise ValueError('Controlled matching checks failed')

if __name__=='__main__':
    try:main()
    except BaseException as error:
        OUT.mkdir(parents=True,exist_ok=True);save(OUT/'failure.json',dict(error_type=type(error).__name__,traceback=traceback.format_exc()));raise
