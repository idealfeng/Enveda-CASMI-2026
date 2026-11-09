"""Bounded metadata/identity-sample audit; no full train scan, GPU or network."""
from pathlib import Path
from collections import Counter,defaultdict
from datetime import datetime,timezone
import hashlib,json,sqlite3,sys,time
import numpy as np
import pyarrow.parquet as pq
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from validation.metric import identity,assert_official_rdkit

def digest(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def records(p,cols):return pq.read_table(p,columns=cols).to_pylist()
def main():
    started=time.monotonic();assert_official_rdkit()
    aroot=ROOT/'assets/kaggle/takumuhata/casmi26-extlib/v2';broot=ROOT/'assets/kaggle/samartalwar/casmi-2026-spectral-library-massbankharmonized/v1';bpath=broot/'spectra.parquet'
    catalog=ROOT/'runs/validation_pilot_v2_20261104/structure_identity_audit.parquet';pool=ROOT/'assets/kaggle/ahmedberatozer/casmi26-v2-pool/v1/train_structs.parquet'
    pool_keys=set(pq.read_table(pool,columns=['inchikey14']).column(0).to_pylist())
    train=records(catalog,['raw_inchikey14','smiles','official_identity','canonical_checked'])
    train_keys={x['raw_inchikey14'] for x in train};train_smiles={x['smiles'] for x in train};checked_ids={x['official_identity'] for x in train if x['canonical_checked'] and x['official_identity']}
    checked_smiles={x['smiles'] for x in train if x['canonical_checked']};complete=len(checked_smiles)==len(train_smiles)
    amap=records(aroot/'ext_meta.parquet',['inchikey14','normalized_smiles','adduct','ionization_mode','instrument_type','precursor_mz'])
    bmap=records(bpath,['inchikey','smiles','adduct','ion_mode','instrument_type','is_casmi_subset','source','source_institution','spectrum_id','license'])
    normalized={
        'A':[dict(key=str(r['inchikey14'])[:14],smiles=r['normalized_smiles'],adduct=r['adduct'],mode=r['ionization_mode'],instrument=r['instrument_type'],row=i) for i,r in enumerate(amap)],
        'B':[dict(key=str(r['inchikey'])[:14],smiles=r['smiles'],adduct=r['adduct'],mode=r['ion_mode'],instrument=r['instrument_type'],row=i) for i,r in enumerate(bmap) if not r['is_casmi_subset'] and isinstance(r['smiles'],str) and r['smiles']]}
    exact_adducts={'[M+H]+','[M-H]-','[M+Na]+','[M+K]+','[M+NH4]+','[M+Cl]-','[M+FA-H]-','[M+H-H2O]+','[M+2H]2+','[M-2H]2-'}
    alias={'[M+HCOO]-':'[M+FA-H]-'}
    summaries={};new=[]
    for label,rows in normalized.items():
        keys={r['key'] for r in rows if len(r['key'])==14};smiles={r['smiles'] for r in rows if isinstance(r['smiles'],str) and r['smiles']}
        outside=keys-train_keys;pick={}
        for r in rows:
            if r['key'] in outside and r['key'] not in pick and isinstance(r['smiles'],str):pick[r['key']]=r
        chosen=sorted(pick.values(),key=lambda r:hashlib.sha256(('external-meta-1109:'+r['key']).encode()).hexdigest())[:1024]
        new.extend((label,r) for r in chosen)
        summaries[label]=dict(rows=len(rows),publisher_keys=len(keys),raw_key_overlap_train=len(keys&train_keys),raw_keys_outside_train=len(outside),
            raw_key_overlap_pool=len(keys&pool_keys),exact_smiles_overlap_train=len(smiles&train_smiles),unique_smiles=len(smiles),
            rows_by_adduct=dict(Counter(str(r['adduct']) for r in rows)),rows_by_mode=dict(Counter(str(r['mode']) for r in rows)),
            rows_exact_official_adduct=sum(r['adduct'] in exact_adducts for r in rows),rows_official_or_alias_adduct=sum(alias.get(r['adduct'],r['adduct']) in exact_adducts for r in rows),
            instrument_top20=Counter(str(r['instrument']) for r in rows).most_common(20),rows_instrument_contains_tims=sum('tims' in str(r['instrument']).lower() for r in rows),
            sampled_outside_raw_keys=len(chosen))
    cache_path=ROOT/'reports/external_reference_pilot_20261107/official_identity_cache.sqlite';db=sqlite3.connect('file:'+str(cache_path)+'?mode=ro',uri=True)
    cache_meta=dict(db.execute('select * from meta'));cache=dict(db.execute('select smiles,official_identity from identities'));db.close()
    if cache_meta.get('rdkit')!='2026.03.3':raise ValueError('Existing identity cache RDKit differs')
    sampled=[]
    for label,r in new:
        if time.monotonic()-started>85:break
        key=cache.get(r['smiles']) if r['smiles'] in cache else identity(r['smiles'])
        sampled.append(dict(library=label,publisher_key=r['key'],smiles=r['smiles'],official_identity=key,
            identity_from_existing_cache=r['smiles'] in cache,positive_train_membership_proven=key in checked_ids if key else False,
            exact_smiles_in_train=r['smiles'] in train_smiles,
            absence_from_full_train_proven=bool(complete and key and key not in checked_ids)))
    # Bounded processed-spectrum signatures: first 2048 A and first eligible 2048 B.
    (ROOT/'reports/external_metadata_identity_sample_20261109.json').write_text(json.dumps(dict(rows=sampled,elapsed_seconds=time.monotonic()-started),indent=2)+'\n')
    sigs=defaultdict(list);signature_skips=Counter()
    def sign(label,index,mz,it,adduct,mode,prec):
        if prec is None or not np.isfinite(float(prec)):
            signature_skips[label+'_missing_precursor']+=1;return
        m=np.asarray(mz,dtype=np.float32).ravel();v=np.asarray(it,dtype=np.float32).ravel();n=min(len(m),len(v));m,v=m[:n],v[:n]
        okay=np.isfinite(m)&np.isfinite(v)&(m>0)&(v>0);m,v=m[okay],v[okay]
        if not len(m):return
        order=np.argsort(m,kind='stable');m,v=m[order],v[order];v=(v/v.max()).astype(np.float32)
        raw=m.tobytes()+v.tobytes()+str(adduct).encode()+str(mode).lower().encode()+f'{float(prec):.6f}'.encode()
        sigs[hashlib.sha256(raw).hexdigest()].append((label,int(index)))
    mz=np.load(aroot/'ext_mz.npy',mmap_mode='r');ints=np.load(aroot/'ext_in.npy',mmap_mode='r')
    for i,r in enumerate(amap[:2048]):sign('A',i,mz[i],ints[i],r['adduct'],r['ionization_mode'],r['precursor_mz'])
    bcount=0
    for batch in pq.ParquetFile(bpath).iter_batches(batch_size=2048,columns=['mzs','intensities','adduct','ion_mode','precursor_mz','is_casmi_subset']):
        for i,r in enumerate(batch.to_pylist()):
            if r['is_casmi_subset']:continue
            sign('B',bcount,r['mzs'],r['intensities'],r['adduct'],r['ion_mode'],r['precursor_mz']);bcount+=1
            if bcount>=2048:break
        if bcount>=2048:break
    suspicious=[]
    for i,r in enumerate(bmap):
        fields={c:str(r[c]) for c in ['source','source_institution','spectrum_id','license'] if 'nist' in str(r[c]).lower()}
        if fields:suspicious.append(dict(row=i,fields=fields))
    existing=json.loads((ROOT/'reports/external_reference_pilot_20261107/partial_audit.json').read_text())
    result=dict(status='bounded_metadata_and_sample_completed',created_at_utc=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-started,
        source_catalog=dict(path=str(catalog.relative_to(ROOT)),sha256=digest(catalog),matches_previously_full_train_verified_catalog=digest(catalog)==existing['train']['catalog_sha256'],
            pairs=len(train),raw_keys=len(train_keys),canonical_checked_pairs=sum(bool(x['canonical_checked']) for x in train),checked_unique_smiles=len(checked_smiles),all_train_smiles_canonical_checked=complete,checked_official_identities=len(checked_ids),pool_raw_keys=len(pool_keys)),
        libraries=summaries,raw_publisher_key_union=len({r['key'] for rows in normalized.values() for r in rows}),raw_publisher_key_overlap_A_B=len({r['key'] for r in normalized['A']}&{r['key'] for r in normalized['B']}),
        official_identity_sample=dict(maximum=2048,processed=len(sampled),existing_cache_rows=len(cache),cache_read_only=True,
            positive_train_membership_proven=sum(x['positive_train_membership_proven'] for x in sampled),exact_smiles_in_train=sum(x['exact_smiles_in_train'] for x in sampled),
            invalid_identity=sum(x['official_identity'] is None for x in sampled),absence_from_full_train_proven=sum(x['absence_from_full_train_proven'] for x in sampled),
            not_found_in_checked_subset_unverified=sum(x['official_identity'] is not None and not x['positive_train_membership_proven'] and not x['absence_from_full_train_proven'] for x in sampled),rows=sampled),
        bounded_spectrum_duplicates=dict(rows_A=min(2048,len(amap)),rows_B=bcount,skipped=dict(signature_skips),signature='finite positive sorted float32 m/z + max-normalized intensity float32 + exact adduct/lowercase mode + precursor rounded6dp',
            duplicate_groups=sum(len(x)>1 for x in sigs.values()),duplicate_extra_rows=sum(len(x)-1 for x in sigs.values()),cross_library_groups=sum(len({a for a,_ in x})>1 for x in sigs.values()),full_train_spectrum_comparison=False),
        provenance_screen=dict(A_source_columns_absent=True,A_NIST_absence_verified=False,B_scanned_fields=['source','source_institution','spectrum_id','license'],B_NIST_string_rows=len(suspicious),B_flagged_examples=suspicious[:10],NIST_free_training_proven=False),
        limits=['Raw publisher keys and exact SMILES overlap are not official scoring-identity increment.','An identity absent from an incomplete checked catalog is unverified, not a new structure.','Spectrum duplication is a bounded normalized-byte sample, not full libraries or train overlap.','No hidden test coverage, performance or causal gain measured.'],
        full_train_scanned=False,new_downloads=False,network_writes=False,gpu_used=False)
    dest=ROOT/'reports/EXTERNAL_METADATA_AUDIT_2026-11-09.json';dest.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ['official_identity_sample']},indent=2));print(json.dumps({k:v for k,v in result['official_identity_sample'].items() if k!='rows'},indent=2))
if __name__=='__main__':main()
