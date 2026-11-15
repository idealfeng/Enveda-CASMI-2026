"""Build a disjoint measured-library gate pilot, without fitting or cloud writes.

Selection and group split are frozen before matching. Train labels are used for
the two controlled reference conditions and separate targets, never features.
"""
from pathlib import Path
from collections import Counter, defaultdict
import ast,csv,hashlib,json,math,os,resource,sys,time,traceback

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.cache/rdkit-official-linux-2026033'))
sys.path.insert(0,str(ROOT))
os.environ['OMP_NUM_THREADS']='2';os.environ['OPENBLAS_NUM_THREADS']='2';os.environ['MKL_NUM_THREADS']='2'
import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from validation import metric

OUT=ROOT/'runs/extlib_gate_pilot_20261115_r2'
REPORT=ROOT/'reports/extlib2_execution_20261115'
TRAIN=ROOT/'enveda-CASMI26-molecule-id-mass-spectra/train.parquet'
CROOT=ROOT/'assets/kaggle/nakhun/casmi26-extlib2/v1/extlib2'
OFFICIAL=ROOT/'runs/generation_production_20261113_r2/kaggle/working/p2s_code/alex_v12_external_function.py'
QUERY_COLUMNS=['molecule_id','spectrum_id','ms2_mzs','ms2_normalized_intensities','base_peak_intensity','adduct','ionization_mode','instrument_type','precursor_mz','collision_energy_orig','collision_energy_ev','collision_energy_orig_units']
ADDUCTS={'[M+H]+','[M+NH4]+','[M-H2O+H]+','[M-2H2O+H]+','[M+Na]+','[M+K]+','[M-H]-','[M-H2O-H]-','[M+CH2O2-H]-','[M+Cl]-'}
CONFIG=dict(seed=20261115,target_structures=500,max_spectra=3,precursor_error_ppm_cap=10.,minimum_query_peaks=6,
            precursor_ppm=10.,precursor_da=.002,fragment_da=.015,matched_peaks_minimum=4,strong_cosine=.8,
            no_old48_or_mist17_training=True,reference_policy='same_mode_precursor_window',
            duplicate_policy='remove_float32_or_quantized_query_content_in_both_conditions_reference_ID_unavailable',
            conditions=['references_present','all_true_identity_references_absent'])

def sha(p):
    with Path(p).open('rb') as h:return hashlib.file_digest(h,'sha256').hexdigest()
def save(p,v):
    p.parent.mkdir(parents=True,exist_ok=True);t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n',encoding='utf-8');t.replace(p)
def keyhash(value):return hashlib.sha256((str(CONFIG['seed'])+'|'+value).encode()).hexdigest()
def finite(v):return v is not None and math.isfinite(float(v))
def ionmode(v):return 1 if 'pos' in str(v).lower() else -1

def exclusions():
    raw=set();official=set()
    splitpath=ROOT/'runs/validation_pilot_v2_20261104/frozen_splits.json'
    def visit(value):
        if isinstance(value,dict):
            if 'official_identity' in value:official.add(value['official_identity'])
            raw.update(value.get('raw_keys',[]))
            for v in value.values():visit(v)
        elif isinstance(value,list):
            for v in value:visit(v)
    visit(json.loads(splitpath.read_text()))
    known=json.loads((ROOT/'runs/validation_pilot_v2_20261104/class2_exclusion_keys.json').read_text())
    raw.update(known['blocked_raw_keys']);official.update(known['blocked_official_identities'])
    msg=set();pins={}
    for p in (ROOT/'assets/research/mist_msg_20261114/exposure/metadata').rglob('structure_ids.npy'):
        msg.update(np.load(p,allow_pickle=False,mmap_mode='r').tolist());pins[p.relative_to(ROOT).as_posix()]=sha(p)
    if not msg:raise ValueError('Official MSG split identities required')
    return raw,official,msg,dict(frozen_splits_sha256=sha(splitpath),frozen_raw_keys=len(raw),frozen_official_ids=len(official),msg_raw_keys=len(msg),msg_identity_pins=pins)

def select_queries(cmeta):
    frozen_raw,frozen_ids,msg,exclude_proof=exclusions();ckeys=set(cmeta['inchikey14'].to_pylist())
    columns=['inchikey14','normalized_smiles','ingest_lib','instrument_type','adduct','precursor_mz','ionization_mode','precursor_error_ppm','num_peaks']
    pools={};offset=0;rows_seen=0;selected_stat=Counter()
    for batch in pq.ParquetFile(TRAIN).iter_batches(columns=columns,batch_size=32768,use_threads=False):
        d=batch.to_pydict()
        for i,rawkey in enumerate(d['inchikey14']):
            if rawkey not in ckeys or rawkey in frozen_raw or rawkey in msg:continue
            ad=d['adduct'][i]
            if ad not in ADDUCTS or not finite(d['precursor_mz'][i]) or not finite(d['precursor_error_ppm'][i]) or abs(float(d['precursor_error_ppm'][i]))>CONFIG['precursor_error_ppm_cap']:continue
            if d['num_peaks'][i] is None or int(d['num_peaks'][i])<CONFIG['minimum_query_peaks']:continue
            source=str(d['ingest_lib'][i]);instrument=str(d['instrument_type'][i])
            priority=0 if source=='enveda-180' and 'tims' in instrument.lower() else 1 if 'tims' in instrument.lower() else 2
            group=pools.setdefault(rawkey,dict(raw_key=rawkey,smiles=d['normalized_smiles'][i],priority=priority,spectra=[]))
            if priority<group['priority']:group.update(priority=priority,spectra=[])
            if priority>group['priority']:continue
            row=dict(source_row=offset+i,spectrum_id='train_row_'+str(offset+i).zfill(9),source=source,instrument=instrument,adduct=ad)
            group['spectra'].append(row);group['spectra'].sort(key=lambda r:keyhash(r['spectrum_id']+'|'+str(r['source_row'])))
            del group['spectra'][CONFIG['max_spectra']:]
        offset+=batch.num_rows;rows_seen+=batch.num_rows
    groups=sorted(pools.values(),key=lambda g:(g['priority'],keyhash(g['raw_key'])))
    chosen=[];seen=set();reject=Counter()
    for group in groups:
        identity=metric.identity(group['smiles'])
        if not identity:reject['invalid_official_identity']+=1;continue
        if identity in frozen_ids or identity in frozen_raw or identity in msg:reject['excluded_official_or_msg_identity']+=1;continue
        if identity in seen:reject['same_official_identity_alias']+=1;continue
        seen.add(identity);group['official_identity']=identity;group['molecule_id']='fit_'+identity;chosen.append(group)
        if len(chosen)==CONFIG['target_structures']:break
    if len(chosen)<128:raise ValueError('Not enough disjoint query structures for minimum pilot')
    chosen.sort(key=lambda g:keyhash('split|'+g['official_identity']))
    train_n=400 if len(chosen)==500 else int(.8*len(chosen))
    for i,g in enumerate(chosen):g['split']='train' if i<train_n else 'development'
    receipt=dict(status='selection_frozen_before_matching',configuration=CONFIG,exclusions=exclude_proof,source_train_rows_scanned=rows_seen,
                 eligible_raw_structure_pool=len(groups),selected_structures=len(chosen),train_structures=train_n,development_structures=len(chosen)-train_n,
                 selected_source_priority=dict(Counter(g['priority'] for g in chosen)),rejected_during_canonical_selection=dict(reject),groups=chosen,
                 no_final_locked_queries_extracted=True,model_training_performed=False,
                 exposure_boundary='Exclude all available frozen-panel raw families and official IDs, plus every MSG train/val/test raw key and candidate official-ID equality. Unknown MSG tautomer aliases remain possible; not universal absence proof.')
    save(OUT/'selection.json',receipt)
    wanted={r['source_row']:(g['molecule_id'],g['raw_key']) for g in chosen for r in g['spectra']}
    parts=[];trace=[];offset=0;fields=[c for c in QUERY_COLUMNS if c not in ('molecule_id','spectrum_id')]+['inchikey14']
    for batch in pq.ParquetFile(TRAIN).iter_batches(columns=fields,batch_size=16384,use_threads=False):
        positions=[r-offset for r in wanted if offset<=r<offset+batch.num_rows]
        if positions:
            positions.sort();take=batch.take(pa.array(positions,type=pa.int64()));data=take.to_pydict();mids=[]
            for j,position in enumerate(positions):
                mid,raw=wanted[offset+position]
                if data['inchikey14'][j]!=raw:raise ValueError('Selected source row raw identity changed')
                mids.append(mid);trace.append(dict(molecule_id=mid,spectrum_id='train_row_'+str(offset+position).zfill(9),source_row=offset+position))
            table=pa.Table.from_batches([take]).drop(['inchikey14']);table=table.add_column(0,'molecule_id',pa.array(mids));table=table.add_column(1,'spectrum_id',pa.array(['train_row_'+str(offset+pos).zfill(9) for pos in positions]));parts.append(table.select(QUERY_COLUMNS))
        offset+=batch.num_rows
    table=pa.concat_tables(parts)
    if table.num_rows!=len(wanted):raise ValueError('Missing selected spectra')
    pq.write_table(table,OUT/'queries.parquet',compression='zstd');save(OUT/'selected_spectrum_rows.json',dict(rows=trace,queries_sha256=sha(OUT/'queries.parquet')))
    return chosen,table

def signatures(mz,it,prec,mode):
    m=np.asarray(mz,dtype=np.float64);v=np.asarray(it,dtype=np.float64);ok=np.isfinite(m)&np.isfinite(v)&(m>0)&(v>0);m,v=m[ok],v[ok]
    if not len(m):return None,None
    order=np.argsort(m,kind='stable');m,v=m[order],v[order];v=v/v.max()
    h=hashlib.blake2b(digest_size=16);h.update(str(mode).encode());h.update(np.asarray([prec],dtype='<f4').tobytes());h.update(np.column_stack((m.astype('<f4'),v.astype('<f4'))).astype('<f4',copy=False).tobytes());exact=h.digest()
    if len(m)>128:
        use=np.sort(np.argsort(-v,kind='stable')[:128]);m,v=m[use],v[use]
    h=hashlib.blake2b(digest_size=16);h.update(str(mode).encode());h.update(np.asarray([round(prec,3)],dtype='<f4').tobytes());h.update(np.column_stack((np.rint(m*10000),np.rint(v*100000))).astype('<i8').tobytes())
    return exact,h.digest()

def matcher():
    tree=ast.parse(OFFICIAL.read_text());fn=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='calc_cosine')
    scope={'np':np};exec(compile(ast.Module(body=[fn],type_ignores=[]),'original_frozen_AB_cosine','exec'),scope);return scope['calc_cosine']

FEATURE_NAMES=['has_match','best_cosine','second_identity_cosine','identity_margin','best_matched_peaks','support_spectra','support_fraction','distinct_references','same_adduct_fraction','ppm_error_min','query_spectra','query_peak_count_mean','reference_peak_count','positive_query_fraction']

def feature(hits,qs):
    grouped=defaultdict(list)
    for h in hits:grouped[h['identity']].append(h)
    leaders=sorted([(max(v,key=lambda h:h['cosine']),v) for v in grouped.values()],key=lambda x:(-x[0]['cosine'],x[0]['identity']))
    base=dict(query_spectra=len(qs),query_peak_count_mean=float(np.mean([len(q['mz']) for q in qs])),positive_query_fraction=float(np.mean([q['mode']==1 for q in qs])))
    if not leaders:
        return dict(base,has_match=False,**{k:np.nan for k in ['best_cosine','second_identity_cosine','identity_margin','best_matched_peaks','same_adduct_fraction','ppm_error_min','reference_peak_count']},support_spectra=0,support_fraction=0.,distinct_references=0),None
    best,events=leaders[0];second=leaders[1][0]['cosine'] if len(leaders)>1 else np.nan
    support={h['spectrum_id'] for h in events if h['cosine']>=CONFIG['strong_cosine']}
    return dict(base,has_match=True,best_cosine=best['cosine'],second_identity_cosine=second,identity_margin=best['cosine']-second if math.isfinite(second) else np.nan,best_matched_peaks=best['matched_peaks'],support_spectra=len(support),support_fraction=len(support)/max(1,len(qs)),distinct_references=len({h['reference_row'] for h in events if h['cosine']>=CONFIG['strong_cosine']}),same_adduct_fraction=sum(h['same_adduct'] for h in events)/len(events),ppm_error_min=min(h['ppm_error'] for h in events),reference_peak_count=best['reference_peak_count']),best

def run():
    OUT.mkdir(parents=True,exist_ok=False);REPORT.mkdir(parents=True,exist_ok=True);started=time.monotonic();metric.assert_official_rdkit()
    save(OUT/'feature_schema.json',dict(feature_columns=FEATURE_NAMES,feature_row_key='row_id',label_column='label',
         label_path='labels.parquet',feature_path='features.parquet',metadata_path='row_metadata.parquet',
         group_key='official_query_identity',split_column='split',no_arm_or_identity_as_model_feature=True,
         missing_policy='NaN for unavailable scores/margins; has_match flag and observed counts remain explicit.'))
    cmeta=pq.read_table(CROOT/'ext2_meta.parquet',columns=['inchikey14','normalized_smiles','precursor_mz','ionization_mode','adduct','source'])
    selected,table=select_queries(cmeta);selection_pin=sha(OUT/'selection.json')
    d=table.to_pydict();queries=defaultdict(list)
    for i,mid in enumerate(d['molecule_id']):
        prec=float(d['precursor_mz'][i]);mz=np.asarray(d['ms2_mzs'][i],dtype=float);it=np.asarray(d['ms2_normalized_intensities'][i],dtype=float);ok=(mz>0)&(it>0)&(mz<=prec+.5);mz,it=mz[ok],it[ok];order=np.argsort(mz,kind='stable');mz,it=mz[order],it[order]
        queries[mid].append(dict(spectrum_id=str(d['spectrum_id'][i]),prec=prec,mode=ionmode(d['ionization_mode'][i]),adduct=str(d['adduct'][i]),mz=mz,it=it,signature=signatures(mz,it,prec,ionmode(d['ionization_mode'][i]))))
    cm=cmeta.to_pydict();prec=np.asarray(cm['precursor_mz'],dtype=float);modes=np.asarray([ionmode(x) for x in cm['ionization_mode']],dtype=np.int8);order=np.argsort(prec,kind='stable');sorted_mass=prec[order]
    mzflat=np.load(CROOT/'ext2_mz_flat.npy',mmap_mode='r',allow_pickle=False);itflat=np.load(CROOT/'ext2_in_flat.npy',mmap_mode='r',allow_pickle=False);offset=np.load(CROOT/'ext2_offsets.npy',mmap_mode='r',allow_pickle=False)
    cosine=matcher();cache={};rows=[];labels=[];metadata=[];count=Counter();truth={g['molecule_id']:g for g in selected}
    with (OUT/'match_events.jsonl').open('w',encoding='utf-8') as trace:
        for n,(mid,qs) in enumerate(queries.items(),1):
            hits=[];duplicate_content=set(sig for q in qs for sig in q['signature'] if sig);spectrum_ids={q['spectrum_id'] for q in qs}
            for q in qs:
                tol=q['prec']*CONFIG['precursor_ppm']*1e-6+CONFIG['precursor_da'];lo=np.searchsorted(sorted_mass,q['prec']-tol,'left');hi=np.searchsorted(sorted_mass,q['prec']+tol,'right')
                for row in order[lo:hi]:
                    row=int(row)
                    if modes[row]!=q['mode']:continue
                    if row not in cache:
                        a,z=int(offset[row]),int(offset[row+1]);m=np.asarray(mzflat[a:z],dtype=float);v=np.asarray(itflat[a:z],dtype=float);ok=(m>0)&(v>0);m,v=m[ok],v[ok];sort=np.argsort(m,kind='stable');m,v=m[sort],v[sort]
                        cache[row]=(metric.identity(cm['normalized_smiles'][row]),m,v,signatures(m,v,prec[row],modes[row]))
                    ik,m,v,sig=cache[row]
                    if not ik or len(m)<3:continue
                    if any(s in duplicate_content for s in sig if s):count['duplicate_reference_pairs_removed']+=1;continue
                    cos,k=cosine(q['mz'],q['it'],m,v);count['actual_cosine_pairs']+=1
                    if k<CONFIG['matched_peaks_minimum']:continue
                    h=dict(molecule_id=mid,spectrum_id=q['spectrum_id'],reference_row=row,identity=ik,cosine=float(cos),matched_peaks=int(k),same_adduct=q['adduct']==cm['adduct'][row],ppm_error=abs(float(prec[row])-q['prec'])/q['prec']*1e6,reference_peak_count=len(m))
                    hits.append(h);trace.write(json.dumps(h)+'\n');count['observed_four_peak_matches']+=1
            actual_truth=truth[mid]['official_identity']
            for arm in CONFIG['conditions']:
                usable=hits if arm=='references_present' else [h for h in hits if h['identity']!=actual_truth]
                f,best=feature(usable,qs);row_id=hashlib.sha256((mid+'|'+arm).encode()).hexdigest()[:24]
                rows.append(dict(row_id=row_id,**f));labels.append(dict(row_id=row_id,label=bool(best and best['identity']==actual_truth),has_recalled_truth=any(h['identity']==actual_truth for h in usable)))
                metadata.append(dict(row_id=row_id,molecule_id=mid,official_query_identity=actual_truth,reference_condition=arm,split=truth[mid]['split'],proposed_identity=best['identity'] if best else None,reference_row=best['reference_row'] if best else None))
            if n%25==0:save(REPORT/'gate_pilot_progress.json',dict(queries_processed=n,queries_total=len(queries),seconds=round(time.monotonic()-started,2),counters=dict(count),peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024))
    feature_table=pa.Table.from_pylist(rows);label_table=pa.Table.from_pylist(labels);meta_table=pa.Table.from_pylist(metadata)
    pq.write_table(feature_table,OUT/'features.parquet',compression='zstd');pq.write_table(label_table,OUT/'labels.parquet',compression='zstd');pq.write_table(meta_table,OUT/'row_metadata.parquet',compression='zstd')
    source_pins={p.relative_to(ROOT).as_posix():sha(p) for p in [CROOT/n for n in ['ext2_meta.parquet','ext2_mz_flat.npy','ext2_in_flat.npy','ext2_offsets.npy']]}
    checks=dict(selection_unchanged=sha(OUT/'selection.json')==selection_pin,source_queries_12_fields=table.column_names==QUERY_COLUMNS,no_labels_or_arm_in_features=set(feature_table.column_names)=={'row_id',*FEATURE_NAMES},separate_labels=True,each_query_two_conditions=len(rows)==2*len(selected),train_development_group_disjoint=not({r['molecule_id'] for r in metadata if r['split']=='train'}&{r['molecule_id'] for r in metadata if r['split']=='development'}),absent_condition_all_labels_false=not any(l['label'] for l,m in zip(labels,metadata) if m['reference_condition']=='all_true_identity_references_absent'),real_cosine_calls=count['actual_cosine_pairs']>0,no_model_training=True,no_cloud_write=True)
    result=dict(status='completed_disjoint_C_gate_pilot' if all(checks.values()) else 'failed',checks=checks,configuration=CONFIG,queries=len(selected),spectra=table.num_rows,feature_rows=len(rows),feature_names=FEATURE_NAMES,split_queries=dict(Counter(g['split'] for g in selected)),labels_by_split_condition={split+'|'+arm:dict(rows=sum(m['split']==split and m['reference_condition']==arm for m in metadata),correct=sum(l['label'] for l,m in zip(labels,metadata) if m['split']==split and m['reference_condition']==arm)) for split in ['train','development'] for arm in CONFIG['conditions']},counters=dict(count),seconds=time.monotonic()-started,peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,source_pins=source_pins,selection_sha256=selection_pin,artifact_pins={n:sha(OUT/n) for n in ['features.parquet','labels.parquet','row_metadata.parquet','queries.parquet','match_events.jsonl']},source_script_sha256=sha(Path(__file__)),parent_baseline_ref=58156482,public_score=None,limitation='Disjoint training pilot for top-reference correctness, not full candidate ranking or hidden MRR. Both controlled conditions share an official query group and split. C reference truth identity removed only to simulate absence; reference condition and query truth identity are metadata, excluded from model features. Known raw-family exclusions cannot prove exclusion of every unknown MSG tautomer alias.')
    save(REPORT/'gate_pilot_verification.json',result)
    print(json.dumps({k:result[k] for k in ['status','queries','spectra','feature_rows','split_queries','labels_by_split_condition','counters','seconds','peak_rss_mib']}),flush=True)
    if not all(checks.values()):raise ValueError('Gate pilot verification failed')

if __name__=='__main__':
    try:run()
    except BaseException as error:
        if OUT.exists():save(OUT/'failure.json',dict(error_type=type(error).__name__,traceback=traceback.format_exc()))
        raise
