"""Freeze old48 top-C gate inputs from cached matches, never re-match or fit.

The existing official truth identities are used only to construct the declared
reference-absence condition and separate evaluation labels. Model features
contain neither identity, reference condition nor label.
"""
from pathlib import Path
from collections import defaultdict,Counter
import csv,hashlib,importlib.util,json,sys
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

ROOT=Path(__file__).resolve().parents[1]
PILOT=ROOT/'runs/extlib_gate_pilot_20261115_r2'
OUT=ROOT/'runs/extlib_gate_holdout48_20261115'
CROOT=ROOT/'assets/kaggle/nakhun/casmi26-extlib2/v1/extlib2'
MATCH=ROOT/'runs/extlib2_matching_20261114_v2'
REPORT=ROOT/'reports/extlib2_execution_20261115'

def sha(p):
    with Path(p).open('rb') as h:return hashlib.file_digest(h,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,v):Path(p).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')

def main():
    OUT.mkdir(parents=True,exist_ok=False)
    source=ROOT/'scripts/build_extlib_gate_pilot_20261115_r2.py'
    sp=importlib.util.spec_from_file_location('frozen_gate_pilot_features',source);core=importlib.util.module_from_spec(sp);sp.loader.exec_module(core)
    core.metric.assert_official_rdkit()
    expected=read(REPORT/'gate_pilot_verification.json')
    if sha(source)!=expected['source_script_sha256']:raise ValueError('Pilot feature implementation changed')
    ctable=read(MATCH/'C_actual_match_table.json')
    oldproof=read(ROOT/'reports/extlib2_matching_20261114/verification.json')
    if sha(MATCH/'C_actual_match_table.json')!=oldproof['score_artifact_sha256']['C']:raise ValueError('Actual C match table changed')
    hit_rows={r['molecule_id']:r['hits'] for r in ctable['rows'] if r['scope']=='diagnostic48'}
    query_path=ROOT/'runs/validation_pilot_v2_20261104/queries.parquet'
    frame=pq.read_table(query_path,columns=['molecule_id','spectrum_id','precursor_mz','adduct','ionization_mode','ms2_mzs','ms2_normalized_intensities']).to_pydict()
    queries=defaultdict(list);by_spec={}
    for i,mid in enumerate(frame['molecule_id']):
        prec=float(frame['precursor_mz'][i]);mz=np.asarray(frame['ms2_mzs'][i],dtype=float);it=np.asarray(frame['ms2_normalized_intensities'][i],dtype=float)
        ok=(mz>0)&(it>0)&(mz<=prec+.5);mz,it=mz[ok],it[ok];order=np.argsort(mz,kind='stable');mz,it=mz[order],it[order]
        q=dict(spectrum_id=str(frame['spectrum_id'][i]),prec=prec,mode=core.ionmode(frame['ionization_mode'][i]),adduct=str(frame['adduct'][i]),mz=mz,it=it)
        key=(mid,q['spectrum_id'])
        if key in by_spec:raise ValueError('Repeated query spectrum ID in cached matching scope')
        queries[mid].append(q);by_spec[key]=q
    cm=pq.read_table(CROOT/'ext2_meta.parquet',columns=['precursor_mz','adduct']).to_pydict()
    mzflat=np.load(CROOT/'ext2_mz_flat.npy',mmap_mode='r',allow_pickle=False);itflat=np.load(CROOT/'ext2_in_flat.npy',mmap_mode='r',allow_pickle=False);offset=np.load(CROOT/'ext2_offsets.npy',mmap_mode='r',allow_pickle=False)
    ref_peaks={};hits={}
    for mid,events in hit_rows.items():
        converted=[]
        for h in events:
            row=int(h['row']);q=by_spec[(mid,h['spectrum_id'])]
            if row not in ref_peaks:
                a,z=int(offset[row]),int(offset[row+1]);ref_peaks[row]=int(np.count_nonzero((mzflat[a:z]>0)&(itflat[a:z]>0)))
            converted.append(dict(molecule_id=mid,spectrum_id=h['spectrum_id'],reference_row=row,identity=h['identity'],cosine=float(h['cosine']),matched_peaks=int(h['matched_peaks']),same_adduct=q['adduct']==cm['adduct'][row],ppm_error=abs(float(cm['precursor_mz'][row])-q['prec'])/q['prec']*1e6,reference_peak_count=ref_peaks[row]))
        hits[mid]=converted
    # Existing validation identities are control metadata, not model features.
    truth_path=ROOT/'runs/validation_pilot_v2_20261104/truth.csv'
    with truth_path.open(encoding='utf-8-sig',newline='') as f:truth={r['molecule_id']:r['official_identity'] for r in csv.DictReader(f)}
    old_details=read(MATCH/'diagnostic_query_details.json')['rows'];details={(r['arm'],r['molecule_id']):r for r in old_details}
    pilot_ids={g['official_identity'] for g in read(PILOT/'selection.json')['groups']}
    if pilot_ids&set(truth.values()):raise ValueError('Held-out identity was used in training pilot')
    rows=[];labels=[];metadata=[];checks={};counts=Counter()
    for mid,qs in queries.items():
        for arm in core.CONFIG['conditions']:
            eligible=hits.get(mid,[]) if arm=='references_present' else [h for h in hits.get(mid,[]) if h['identity']!=truth[mid]]
            features,best=core.feature(eligible,qs);row_id=hashlib.sha256((mid+'|'+arm).encode()).hexdigest()[:24]
            rows.append(dict(row_id=row_id,**features));labels.append(dict(row_id=row_id,label=bool(best and best['identity']==truth[mid]),has_recalled_truth=any(h['identity']==truth[mid] for h in eligible)))
            metadata.append(dict(row_id=row_id,molecule_id=mid,official_query_identity=truth[mid],reference_condition=arm,split='heldout48',proposed_identity=best['identity'] if best else None,reference_row=best['reference_row'] if best else None))
            old=details[(arm,mid)]['C_hit'];counts['best_reference_identity_equal_to_frozen_old_matcher']+=int((best['identity'] if best else None)==(old['identity'] if old else None));counts['rows']+=1
    for name,data in [('features',rows),('labels',labels),('row_metadata',metadata)]:pq.write_table(pa.Table.from_pylist(data),OUT/(name+'.parquet'),compression='zstd')
    schema=read(PILOT/'feature_schema.json');schema['dataset_role']='heldout48_only_do_not_fit';save(OUT/'feature_schema.json',schema)
    checks=dict(no_train_holdout_identity_overlap=not(pilot_ids&set(truth.values())),same_feature_implementation=True,feature_columns_exact=set(rows[0])=={'row_id',*core.FEATURE_NAMES},labels_and_reference_condition_not_features=True,each_query_two_arms=len(rows)==96,source_matches_unchanged=sha(MATCH/'C_actual_match_table.json')==oldproof['score_artifact_sha256']['C'],best_identity_replays_original=counts['best_reference_identity_equal_to_frozen_old_matcher']==96)
    result=dict(status='completed_frozen_old48_gate_features' if all(checks.values()) else 'failed',checks=checks,queries=len(queries),rows=len(rows),matching_rerun=False,training_performed=False,source_script_sha256=sha(source),query_file_sha256=sha(query_path),source_C_match_sha256=sha(MATCH/'C_actual_match_table.json'),truth_control_metadata_sha256=sha(truth_path),train_pilot_selection_sha256=sha(PILOT/'selection.json'),feature_columns=core.FEATURE_NAMES,counters=dict(counts),artifact_pins={n:sha(OUT/n) for n in ['features.parquet','labels.parquet','row_metadata.parquet','feature_schema.json']},new_public_score=None,boundary='Old48 labels are isolated from model input and fit. They construct the predefined reference-absence condition and evaluation targets only. Prior pipeline library_max/context remains unchanged; this is a component holdout with known legacy-model pretraining exposure, not exact .488 clean CV.')
    save(REPORT/'gate_holdout48_verification.json',result);print(json.dumps(dict(status=result['status'],queries=len(queries),rows=len(rows),all_checks=all(checks.values()))))
    if not all(checks.values()):raise ValueError('Heldout feature checks failed')

if __name__=='__main__':main()
