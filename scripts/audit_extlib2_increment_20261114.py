"""Stream measured-spectrum overlap and official structure identities, all on D.

This is a corpus increment audit, not validation or hidden-test coverage.
Official train membership is reported at raw-key/exact-SMILES resolution unless
the relevant official identities have actually been canonicalized.
"""
from pathlib import Path
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import argparse,hashlib,json,os,sqlite3,sys,time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.cache/rdkit-official-linux-2026033'))
sys.path.insert(0,str(ROOT))
os.environ['OMP_NUM_THREADS']='2';os.environ['OPENBLAS_NUM_THREADS']='2';os.environ['MKL_NUM_THREADS']='2'
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from validation.metric import assert_official_rdkit,identity

OUT=ROOT/'runs/extlib2_increment_20261114'
REPORT=ROOT/'reports/extlib2_increment_20261114'
C=ROOT/'assets/kaggle/nakhun/casmi26-extlib2/v1/extlib2'
A=ROOT/'assets/kaggle/takumuhata/casmi26-extlib/v2'
B=ROOT/'assets/kaggle/samartalwar/casmi-2026-spectral-library-massbankharmonized/v1/spectra.parquet'
TRAIN=ROOT/'enveda-CASMI26-molecule-id-mass-spectra/train.parquet'


def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def save(p,x):
    tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(x,indent=2,allow_nan=False),encoding='utf-8');tmp.replace(p)


def canonical(item):
    return item,identity(item)


def normalize_peaks(mz,intensity,prec):
    m=np.asarray(mz,dtype=np.float64);i=np.asarray(intensity,dtype=np.float64)
    if m.shape!=i.shape:return None
    keep=np.isfinite(m)&np.isfinite(i)&(m>0)&(i>0)
    m=m[keep];i=i[keep]
    if len(m)==0:return None
    order=np.argsort(m,kind='stable');m=m[order];i=i[order]
    i=i/i.max()
    return m,i


def signatures(mz,intensity,prec,mode):
    pair=normalize_peaks(mz,intensity,prec)
    if pair is None:return None,None
    m,i=pair
    # Float32-equivalent normalized peak content: acquisition metadata is bound
    # separately. This equality is not proof of independent or identical runs.
    exact=np.column_stack((m.astype('<f4'),i.astype('<f4'))).astype('<f4',copy=False)
    h=hashlib.blake2b(digest_size=16);h.update(str(mode).encode());h.update(np.asarray([prec],dtype='<f4').tobytes());h.update(exact.tobytes())
    strict=h.digest()
    # A tolerant representation flags possible transformed duplicates. Restrict
    # all sources to their 128 strongest peaks, normalize then quantize.
    if len(m)>128:
        take=np.argsort(-i,kind='stable')[:128];take=np.sort(take);m=m[take];i=i[take]
    quant=np.column_stack((np.rint(m*10000),np.rint(i*100000))).astype('<i8')
    h=hashlib.blake2b(digest_size=16);h.update(str(mode).encode());h.update(np.asarray([round(prec,3)],dtype='<f4').tobytes());h.update(quant.tobytes())
    return strict,h.digest()


def mode(v):return 'positive' if 'pos' in str(v).lower() else 'negative'


def main():
    p=argparse.ArgumentParser();p.add_argument('--identities',action='store_true');p.add_argument('--spectra',action='store_true');p.add_argument('--train-spectra',action='store_true');p.add_argument('--workers',type=int,default=2);args=p.parse_args()
    OUT.mkdir(parents=True,exist_ok=True);REPORT.mkdir(parents=True,exist_ok=True);assert_official_rdkit();started=time.monotonic()
    refs=pq.read_table(C/'ext2_meta.parquet').to_pydict();nc=len(refs['source'])
    am=pq.read_table(A/'ext_meta.parquet').to_pydict()
    mass_schema=pq.read_schema(A/'ext_mass.parquet')
    # Original loader only consumes a column literally named exact_mass. The
    # current A file has mono_mass, so production does not apply this filter.
    mass=pq.read_table(A/'ext_mass.parquet',columns=['exact_mass']).column(0).to_numpy() if 'exact_mass' in mass_schema.names else None
    bt=pq.read_table(B,columns=['smiles','exact_mass','ion_mode','adduct','is_casmi_subset','mzs','intensities'])
    bz=bt.column('mzs').combine_chunks();bi=bt.column('intensities').combine_chunks()
    bm=bt.drop(['mzs','intensities']).to_pydict();del bt
    # Mirror exact production admission rules, without changing the old arrays.
    az=np.load(A/'ext_mz.npy',mmap_mode='r',allow_pickle=False);ai=np.load(A/'ext_in.npy',mmap_mode='r',allow_pickle=False)
    arows=[j for j in range(len(am['normalized_smiles'])) if (mass is None or (np.isfinite(mass[j]) and mass[j]>0)) and np.count_nonzero((az[j]>0)&(ai[j]>0))>=3]
    brows=[]
    for j,(s,sub) in enumerate(zip(bm['smiles'],bm['is_casmi_subset'])):
        if bool(sub) or s is None:continue
        m=bz[j].values.to_numpy();i=bi[j].values.to_numpy()
        if m.shape==i.shape and np.count_nonzero((m>0)&(i>0))>=3:brows.append(j)
    assert len(arows)==200724 and len(brows)==124160,(len(arows),len(brows))
    train_keys=set();train_smiles=set();train_pairs=set();tr=0
    for b in pq.ParquetFile(TRAIN).iter_batches(columns=['inchikey14','normalized_smiles'],batch_size=32768,use_threads=False):
        d=b.to_pydict();tr+=b.num_rows;train_keys.update(d['inchikey14']);train_smiles.update(d['normalized_smiles']);train_pairs.update(zip(d['inchikey14'],d['normalized_smiles']))
    akeys={am['inchikey14'][j] for j in arows};bkeys={str(s)[:14] for s in []}
    # B has no raw-key column in the deployed loader; raw InChIKey is retained
    # here only for explicitly labelled publisher comparisons, not score IDs.
    braw=pq.read_table(B,columns=['inchikey']).column(0).to_pylist();bkeys={str(braw[j])[:14] for j in brows if braw[j]}
    abkeys=akeys|bkeys;ckeys=set(refs['inchikey14']);cs=set(refs['normalized_smiles']);absmi={am['normalized_smiles'][j] for j in arows}|{bm['smiles'][j] for j in brows}
    by=Counter();byad=Counter();rows=[]
    for j,k in enumerate(refs['inchikey14']):
        source=str(refs['source'][j]).split(':')[0];ad=refs['adduct'][j]
        tag='raw_key_in_train' if k in train_keys else 'raw_key_missing_train'
        by[(source,tag)]+=1;byad[(ad,tag)]+=1
        rows.append(dict(row_index=j,publisher_key=k,source=source,adduct=ad,raw_key_in_AB=k in abkeys,raw_key_in_train=k in train_keys,exact_smiles_in_train=refs['normalized_smiles'][j] in train_smiles))
    pq.write_table(pa.Table.from_pylist(rows),OUT/'reference_membership.parquet',compression='zstd')
    result=dict(status='metadata_complete_canonical_pending',created_at_utc=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),metric_rdkit='2026.03.3',sources=dict(C_rows=nc,A_production_rows=len(arows),B_physical_rows=len(braw),B_production_rows=len(brows),official_train_rows=tr,train_raw_keys=len(train_keys),train_raw_smiles=len(train_smiles),train_unique_pairs=len(train_pairs)),publisher_key_overlap=dict(C_keys=len(ckeys),AB_keys=len(abkeys),C_keys_missing_AB=len(ckeys-abkeys),C_keys_missing_train=len(ckeys-train_keys),C_keys_missing_both=len(ckeys-abkeys-train_keys),C_rows_missing_AB=sum(r['raw_key_in_AB'] is False for r in rows),C_rows_missing_train=sum(r['raw_key_in_train'] is False for r in rows)),exact_smiles_overlap=dict(C_unique_smiles=len(cs),AB_unique_smiles=len(absmi),C_smiles_missing_AB=len(cs-absmi),C_smiles_missing_train=len(cs-train_smiles)),by_source_raw_train_membership=[dict(source=s,membership=m,rows=n) for (s,m),n in sorted(by.items())],by_adduct_raw_train_membership=[dict(adduct=a,membership=m,rows=n) for (a,m),n in sorted(byad.items())],limitations=['Publisher InChIKey14/raw-SMILES absence is not official metric-identity absence.','No hidden-test query or truth loaded; counts are corpus increments, not recall or score.'],seconds=round(time.monotonic()-started,3))
    save(REPORT/'metadata_audit.json',result);print(json.dumps(dict(stage='metadata_complete',summary=result['publisher_key_overlap'],seconds=result['seconds'])),flush=True)
    del rows,train_pairs
    if args.spectra or args.train_spectra:
        z=np.load(C/'ext2_mz_flat.npy',mmap_mode='r',allow_pickle=False);it=np.load(C/'ext2_in_flat.npy',mmap_mode='r',allow_pickle=False);off=np.load(C/'ext2_offsets.npy',mmap_mode='r',allow_pickle=False)
        strict_map={};quant_map={}
        for j in range(nc):
            lo,hi=map(int,off[j:j+2]);a,b=signatures(z[lo:hi],it[lo:hi],float(refs['precursor_mz'][j]),mode(refs['ionization_mode'][j]))
            if a is not None:strict_map.setdefault(a,[]).append(j)
            if b is not None:quant_map.setdefault(b,[]).append(j)
        exact_AB=set();quant_AB=set();exact_train=set();quant_train=set()
        for j in arows:
            a,b=signatures(az[j],ai[j],float(am['precursor_mz'][j]),mode(am['ionization_mode'][j]));exact_AB.update(strict_map.get(a,[]));quant_AB.update(quant_map.get(b,[]))
        for j in brows:
            md=mode(bm['ion_mode'][j]);prec=float(bm['exact_mass'][j])+(1.007276 if md=='positive' else -1.007276)
            a,b=signatures(bz[j].values.to_numpy(),bi[j].values.to_numpy(),prec,md);exact_AB.update(strict_map.get(a,[]));quant_AB.update(quant_map.get(b,[]))
        del bz,bi
        def spec_summary():
            return dict(C_rows=nc,C_distinct_strict_signatures=len(strict_map),C_distinct_quantized_signatures=len(quant_map),C_rows_strict_in_AB=len(exact_AB),C_rows_quantized_in_AB=len(quant_AB),C_rows_strict_in_train=len(exact_train),C_rows_quantized_in_train=len(quant_train),C_rows_strict_in_neither=len(set(range(nc))-exact_AB-exact_train),C_rows_quantized_in_neither=len(set(range(nc))-quant_AB-quant_train),official_train_spectra_scanned=train_scanned,signature_definition=dict(strict='Positive finite peaks sorted by mz; max-normalized intensity and mz cast float32; mode and float32 precursor; B uses its ACTUAL deployed synthesized H precursor.',quantized='Top128 by normalized intensity, sorted mz; mz rounded1e-4Da/intensity1e-5; mode and precursor rounded1e-3Da. Equality is a possible transformed duplicate, not proof; inequality is not proof of independent acquisition.'),by_source=[dict(source=s,rows=n,strict_AB=sum(j in exact_AB for j,v in enumerate(refs['source']) if str(v).split(':')[0]==s),quantized_AB=sum(j in quant_AB for j,v in enumerate(refs['source']) if str(v).split(':')[0]==s),strict_train=sum(j in exact_train for j,v in enumerate(refs['source']) if str(v).split(':')[0]==s),quantized_train=sum(j in quant_train for j,v in enumerate(refs['source']) if str(v).split(':')[0]==s)) for s,n in sorted(Counter(str(v).split(':')[0] for v in refs['source']).items())])
        train_scanned=0
        save(REPORT/'spectrum_overlap_AB.json',spec_summary());print(json.dumps(dict(stage='AB_spectra_complete',strict=len(exact_AB),quantized=len(quant_AB),seconds=round(time.monotonic()-started,2))),flush=True)
        if args.train_spectra:
            for bb in pq.ParquetFile(TRAIN).iter_batches(columns=['ms2_mzs','ms2_normalized_intensities','precursor_mz','ionization_mode'],batch_size=2048,use_threads=False):
                dd=bb.to_pydict()
                for mz,ints,prec,md in zip(*(dd[k] for k in ['ms2_mzs','ms2_normalized_intensities','precursor_mz','ionization_mode'])):
                    a,b=signatures(mz,ints,float(prec),mode(md));exact_train.update(strict_map.get(a,[]));quant_train.update(quant_map.get(b,[]))
                train_scanned+=bb.num_rows
                if train_scanned%65536==0:save(REPORT/'spectrum_progress.json',dict(rows=train_scanned,total=tr,seconds=round(time.monotonic()-started,2)));print(json.dumps(dict(stage='train_spectra',rows=train_scanned,strict=len(exact_train),quantized=len(quant_train),seconds=round(time.monotonic()-started,2))),flush=True)
            save(REPORT/'spectrum_overlap_complete.json',spec_summary())
        pq.write_table(pa.Table.from_pylist([dict(row_index=j,strict_in_AB=j in exact_AB,quantized_in_AB=j in quant_AB,strict_in_train=j in exact_train,quantized_in_train=j in quant_train) for j in range(nc)]),OUT/'spectrum_membership.parquet',compression='zstd')
    if args.identities:
        db=sqlite3.connect(OUT/'official_identity_cache.sqlite');db.execute('CREATE TABLE IF NOT EXISTS identities(smiles TEXT PRIMARY KEY,official_identity TEXT)');db.execute('CREATE TABLE IF NOT EXISTS meta(name TEXT PRIMARY KEY,value TEXT NOT NULL)')
        prior=db.execute("SELECT value FROM meta WHERE name='rdkit'").fetchone()
        if prior and prior[0]!='2026.03.3':raise ValueError('Cache RDKit mismatch')
        db.execute("INSERT OR REPLACE INTO meta VALUES('rdkit','2026.03.3')")
        known=dict(db.execute('SELECT smiles,official_identity FROM identities'))
        pending=sorted((cs|absmi)-set(known));total=len(pending)
        with ProcessPoolExecutor(max_workers=max(1,min(args.workers,2))) as executor:
            for n,(s,ik) in enumerate(executor.map(canonical,pending,chunksize=16),1):
                known[s]=ik;db.execute('INSERT INTO identities VALUES(?,?)',(s,ik))
                if n%2048==0:
                    db.commit();save(REPORT/'identity_progress.json',dict(done=n,pending_total=total,total_unique=len(cs|absmi),seconds=round(time.monotonic()-started,2)));print(json.dumps(dict(stage='official_identity',done=n,total=total,seconds=round(time.monotonic()-started,2))),flush=True)
        db.commit()
        cids={known[s] for s in cs if known[s]};abids={known[s] for s in absmi if known[s]};train_confirmed={known[s] for s in (cs|absmi)&train_smiles if known[s]}
        stats=dict(status='complete_C_AB_official_identity_with_partial_train_membership',rdkit='2026.03.3',C_official_identities=len(cids),AB_official_identities=len(abids),C_identities_not_in_AB=len(cids-abids),C_rows_official_identity_not_in_AB=sum(known[s] not in abids for s in refs['normalized_smiles'] if known[s]),C_invalid_unique_smiles=sum(known[s] is None for s in cs),AB_invalid_unique_smiles=sum(known[s] is None for s in absmi),C_publisher_key_mismatch_rows=sum(k!=known[s] for k,s in zip(refs['inchikey14'],refs['normalized_smiles'])),C_ids_confirmed_in_train_via_identical_smiles=len(cids&train_confirmed),C_ids_train_membership_unresolved=len(cids-train_confirmed),train_membership_boundary='Full official train raw-key/SMILES metadata was scanned; only identical-SMILES identities resolved for train. Unresolved IDs must NOT be called train-absent.',by_source=[dict(source=src,official_identities=len({known[s] for s,source in zip(refs['normalized_smiles'],refs['source']) if str(source).split(':')[0]==src and known[s]}),rows_not_AB=sum(known[s] not in abids for s,source in zip(refs['normalized_smiles'],refs['source']) if str(source).split(':')[0]==src and known[s])) for src in sorted({str(v).split(':')[0] for v in refs['source']})],elapsed_seconds=round(time.monotonic()-started,2))
        save(REPORT/'official_identity_audit.json',stats)
        pq.write_table(pa.Table.from_pylist([dict(row_index=j,smiles=s,publisher_key=refs['inchikey14'][j],official_identity=known[s],official_in_AB=known[s] in abids,official_in_train_confirmed=known[s] in train_confirmed) for j,s in enumerate(refs['normalized_smiles'])]),OUT/'official_reference_membership.parquet',compression='zstd')
    print(json.dumps(dict(stage='finished',seconds=round(time.monotonic()-started,2))),flush=True)


if __name__=='__main__':main()
