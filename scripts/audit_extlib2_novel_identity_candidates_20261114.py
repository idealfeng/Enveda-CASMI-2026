"""Resolve only C publisher-key families absent from both A/B and official train.

Heavy-atom composition is recomputed or drawn from an independently verified
current-train structure catalog, then all possible same-composition references
are canonicalized. This can prove identities absent for this bounded subset.
"""
from pathlib import Path
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime,timezone
import hashlib,json,os,sqlite3,sys,time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.cache/rdkit-official-linux-2026033'));sys.path.insert(0,str(ROOT))
os.environ['OMP_NUM_THREADS']='2';os.environ['OPENBLAS_NUM_THREADS']='2'
import pyarrow as pa
import pyarrow.parquet as pq
from validation.metric import assert_official_rdkit,identity,heavy_atom_composition
OUT=ROOT/'runs/extlib2_increment_20261114';REPORT=ROOT/'reports/extlib2_increment_20261114'

def save(p,x):
    tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(x,indent=2,allow_nan=False),encoding='utf-8');tmp.replace(p)
def canonical(s):return s,identity(s)

def main():
    assert_official_rdkit();started=time.monotonic()
    membership=pq.read_table(OUT/'reference_membership.parquet').to_pylist()
    chosen={r['publisher_key'] for r in membership if not r['raw_key_in_AB'] and not r['raw_key_in_train']}
    cm=pq.read_table(ROOT/'assets/kaggle/nakhun/casmi26-extlib2/v1/extlib2/ext2_meta.parquet').to_pydict()
    targetrows=[i for i,k in enumerate(cm['inchikey14']) if k in chosen]
    targetsmiles={cm['normalized_smiles'][i] for i in targetrows}
    targetcomps={heavy_atom_composition(s) for s in targetsmiles};targetcomps.discard(None)
    trainpath=ROOT/'enveda-CASMI26-molecule-id-mass-spectra/train.parquet';trainpairs=set();rows=0
    for b in pq.ParquetFile(trainpath).iter_batches(columns=['inchikey14','normalized_smiles'],batch_size=32768,use_threads=False):
        d=b.to_pydict();trainpairs.update(zip(d['inchikey14'],d['normalized_smiles']));rows+=b.num_rows
    catpath=ROOT/'runs/validation_pilot_v2_20261104/structure_identity_audit.parquet';cat=pq.read_table(catpath).to_pydict()
    if trainpairs!=set(zip(cat['raw_inchikey14'],cat['smiles'])):raise ValueError('Existing train catalog differs from independently rescanned current train')
    cachedcomp={s:(tuple(tuple(v) for v in json.loads(h)) if h else None) for s,h in zip(cat['smiles'],cat['heavy_composition'])}
    tcandidates={s for s,c in cachedcomp.items() if c in targetcomps}
    a=pq.read_table(ROOT/'assets/kaggle/takumuhata/casmi26-extlib/v2/ext_meta.parquet',columns=['normalized_smiles']).column(0).to_pylist()
    # A admission was independently exact-count checked in the main audit.
    b=pq.read_table(ROOT/'assets/kaggle/samartalwar/casmi-2026-spectral-library-massbankharmonized/v1/spectra.parquet',columns=['smiles','is_casmi_subset','mzs','intensities'])
    bd=b.drop(['mzs','intensities']).to_pydict();z=b.column('mzs').combine_chunks();it=b.column('intensities').combine_chunks()
    import numpy as np
    ab=set(a)
    kept=0
    for j,(s,sub) in enumerate(zip(bd['smiles'],bd['is_casmi_subset'])):
        if sub or s is None:continue
        mz=z[j].values.to_numpy();ii=it[j].values.to_numpy()
        if mz.shape==ii.shape and np.count_nonzero((mz>0)&(ii>0))>=3:ab.add(s);kept+=1
    if kept!=124160:raise ValueError('Production B scope differs')
    del b,z,it
    abcandidates=set();invalid_ab=set()
    for n,s in enumerate(ab):
        c=cachedcomp.get(s) if s in cachedcomp else heavy_atom_composition(s)
        if c is None:invalid_ab.add(s)
        elif c in targetcomps:abcandidates.add(s)
    needed=targetsmiles|tcandidates|abcandidates
    info=dict(status='safe_heavy_composition_scope_complete',target_publisher_keys=len(chosen),target_rows=len(targetrows),target_unique_smiles=len(targetsmiles),target_heavy_compositions=len(targetcomps),train_rows=rows,train_unique_pairs=len(trainpairs),train_catalog_exact_match=True,all_AB_unique_smiles=len(ab),AB_invalid_composition_smiles=len(invalid_ab),same_composition_train_smiles=len(tcandidates),same_composition_AB_smiles=len(abcandidates),canonical_needed=len(needed),seconds=round(time.monotonic()-started,2))
    save(REPORT/'bounded_identity_scope.json',info);print(json.dumps(info),flush=True)
    # Keep a durable, new identity cache. No old audit cache is mutated.
    db=sqlite3.connect(OUT/'novel_candidate_identity_cache.sqlite');db.execute('CREATE TABLE IF NOT EXISTS identity(smiles TEXT PRIMARY KEY,official_identity TEXT)');db.execute('CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT)')
    previous=db.execute("SELECT value FROM meta WHERE key='rdkit'").fetchone()
    if previous and previous[0]!='2026.03.3':raise ValueError('Cache RDKit differs')
    db.execute("INSERT OR REPLACE INTO meta VALUES('rdkit','2026.03.3')")
    known=dict(db.execute('SELECT smiles,official_identity FROM identity'));pending=sorted(needed-set(known))
    with ProcessPoolExecutor(max_workers=2) as executor:
        for n,(s,ik) in enumerate(executor.map(canonical,pending,chunksize=16),1):
            known[s]=ik;db.execute('INSERT INTO identity VALUES(?,?)',(s,ik))
            if n%1024==0:
                db.commit();save(REPORT/'bounded_identity_progress.json',dict(done=n,total=len(pending),seconds=round(time.monotonic()-started,2)))
    db.commit()
    tids={known[s] for s in tcandidates if known[s]};aids={known[s] for s in abcandidates if known[s]};targetids={known[s] for s in targetsmiles if known[s]}
    output=[]
    for j in targetrows:
        s=cm['normalized_smiles'][j];ik=known[s]
        output.append(dict(row_index=j,publisher_key=cm['inchikey14'][j],smiles=s,official_identity=ik,source=cm['source'][j],adduct=cm['adduct'][j],official_in_train=ik in tids if ik else None,official_in_AB=ik in aids if ik else None))
    pq.write_table(pa.Table.from_pylist(output),OUT/'novel_candidate_identity_rows.parquet',compression='zstd')
    result=dict(info,status='complete_official_identity_audit_of_raw_key_novel_subset',completed_at_utc=datetime.now(timezone.utc).isoformat(),metric_rdkit='2026.03.3',target_official_ids=len(targetids),target_invalid_smiles=sum(known[s] is None for s in targetsmiles),publisher_key_mismatch_rows=sum(r['official_identity']!=r['publisher_key'] for r in output),official_ids_present_in_train=len(targetids&tids),official_ids_present_in_AB=len(targetids&aids),official_ids_absent_from_train_and_AB=len(targetids-tids-aids),official_rows_absent_from_both=sum(r['official_identity'] is not None and not r['official_in_train'] and not r['official_in_AB'] for r in output),by_source={source:dict(rows=sum(r['source'].split(':')[0]==source for r in output),official_absent_both_rows=sum(r['source'].split(':')[0]==source and r['official_identity'] is not None and not r['official_in_train'] and not r['official_in_AB'] for r in output)) for source in sorted({r['source'].split(':')[0] for r in output})},scope_boundary='This exactly resolves only publisher keys absent from AB and train (115 families), not every C identity. Safe heavy-atom composition prefilter; no complete-formula gate. Whole-corpus official novel count can be larger and is not asserted.',no_queries_or_hidden_truth_loaded=True,hidden_recall_or_score_claim=False,seconds=round(time.monotonic()-started,2))
    save(REPORT/'bounded_official_identity_audit.json',result);print(json.dumps(result),flush=True)

if __name__=='__main__':main()
