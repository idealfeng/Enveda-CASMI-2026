"""Freeze actual precursor-only candidate windows before any label evaluation.

No model/checkpoint/step0/step500 metrics are opened. This is an eight-query
component development probe drawn from the already-used training development
split, never a new holdout or champion-stack validation.
"""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import csv
import hashlib
import json
import math
import os
import resource
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[1]
PILOT=ROOT/'runs/fiora_tims_pilot_20261115'
POOL=ROOT/'assets/kaggle/ahmedberatozer/casmi26-v2-pool/v1/pool_meta.parquet'
CODE=ROOT/'assets/kaggle/ahmedberatozer/casmi26-v3-models/v4/code'
OUT=ROOT/'runs/fiora_candidate_pilot_20261115'
SEED=20261115
EXPECTED_INDEX='622f87ad8098ac98318d326eddb5288cc2bd3ea6a1c69f37de5abc477ff6a8a5'
EXPECTED_SELECTION='2b4ecd92fbf0f175b8533c1678bf693831e9ef1f75bb48084cf32f0169c2213d'
CONFIG=dict(seed=SEED, queries=8, original_dev_structure_denominator=100,
            selected_from_cache_ready_only=True, query_hash='sha256(str(seed)+"|"+official_identity)',
            initial_ppm=10., empty_window_fallback_ppm=30., cap=128,
            cap_sort='absolute measured-neutral-mass error, then pool pid',
            output_candidate_order='original pool row order after any cap',
            formula_filter=False, truth_candidate_injection=False, candidate_identity_deduplication=False,
            model_scores_used=False, pretraining_exposure='MSnLib v7 unknown',
            scope='small component development pilot; same existing100dev, not new holdout, not full champion pipeline',
            workers=1,rss_limit_bytes=512*1024**2)
sys.path[:0]=[str(ROOT/'.cache/rdkit-official-linux-2026033'),str(ROOT),str(CODE)]

def sha(path):
    with Path(path).open('rb') as handle:return hashlib.file_digest(handle,'sha256').hexdigest()

def save(path,value):
    Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def memory():
    current=next(int(line.split()[1])*1024 for line in Path('/proc/self/status').read_text().splitlines() if line.startswith('VmRSS:'))
    if current>CONFIG['rss_limit_bytes']:raise MemoryError(f'RSS budget exceeded: {current}')
    return dict(current_rss_bytes=current,peak_rss_bytes=int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)*1024)

def stamp():return datetime.now(timezone.utc).isoformat()

def write_csv(path,rows,fields):
    with Path(path).open('w',newline='',encoding='utf-8') as handle:
        writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader()
        for row in rows:
            writer.writerow({k:json.dumps(row[k],separators=(',',':')) if isinstance(row[k],(list,dict)) else row[k] for k in fields})

def pool_smiles(pool_positions):
    """Read candidate structures only for the already-frozen numeric windows."""
    import pyarrow as pa
    import pyarrow.parquet as pq
    wanted=set(pool_positions);result={};offset=0
    for batch in pq.ParquetFile(POOL).iter_batches(columns=['pid','smiles'],batch_size=8192,use_threads=False):
        within=sorted(p-offset for p in wanted if offset<=p<offset+batch.num_rows)
        if within:
            take=batch.take(pa.array(within,type=pa.int64())).to_pydict()
            for i,local in enumerate(within):result[offset+local]=dict(pid=int(take['pid'][i]),smiles=take['smiles'][i])
        offset+=batch.num_rows
        memory()
    if set(result)!=wanted:raise ValueError('Frozen candidate pool positions missing')
    return result

def main():
    import numpy as np
    import pyarrow as pa
    import pyarrow.parquet as pq
    from casmi import chem
    pa.set_cpu_count(1)
    start=time.perf_counter()
    if OUT.exists():raise FileExistsError('Preserve frozen pilot; choose a new revision for changes')
    OUT.mkdir(parents=True)
    if sha(PILOT/'index.json')!=EXPECTED_INDEX or sha(PILOT/'selection.json')!=EXPECTED_SELECTION:
        raise ValueError('Source pilot index/selection changed')
    index=json.loads((PILOT/'index.json').read_text())
    # Target identity is used only for the explicitly prescribed random selection.
    # No model scores/coverage/performance/candidate recall participates here.
    development=[r for r in index['rows'] if r['split']=='development']
    ready=[r for r in development if r['status']=='cache_ready']
    assert len(development)==100 and len(ready)==98
    selected=sorted(ready,key=lambda r:(hashlib.sha256((str(SEED)+'|'+r['official_identity']).encode()).hexdigest(),r['official_identity']))[:8]
    assert len(selected)==8
    selected_ids={r['spectrum_id'] for r in selected}
    source_rows=json.loads((PILOT/'input_spectra_index.json').read_text())
    input_by_id={r['spectrum_id']:r for r in source_rows['rows']}
    # This source selection supplies actual recorded CE, never truth formula/mass.
    source_selection=json.loads((PILOT/'selection.json').read_text())
    meta_by_id={r['spectrum_id']:r for r in source_selection['groups'] if r['spectrum_id'] in selected_ids}
    plan=dict(status='eight_queries_selected_before_candidates_or_labels',configuration=CONFIG,
              source_index_sha256=EXPECTED_INDEX,source_selection_sha256=EXPECTED_SELECTION,
              source_spectrum_index_sha256=sha(PILOT/'input_spectra_index.json'),
              selected=[dict(molecule_id=r['molecule_id'],spectrum_id=r['spectrum_id'],official_identity=r['official_identity'],
                             selection_hash=hashlib.sha256((str(SEED)+'|'+r['official_identity']).encode()).hexdigest()) for r in selected],
              model_checkpoints_or_development_metrics_read=False,created_at_utc=stamp())
    save(OUT/'selection.json',plan)
    queries=[]
    for selected_row in selected:
        sid=selected_row['spectrum_id'];meta=meta_by_id[sid];pin=input_by_id[sid];path=PILOT/pin['path']
        assert sha(path)==pin['sha256']
        with np.load(path,allow_pickle=False) as arrays:
            # Only the real measured precursor saved from official train is used.
            precursor=float(arrays['precursor_mz'].reshape(-1)[0])
            mz=np.asarray(arrays['ms2_mzs'],dtype=np.float64)
            intensity=np.asarray(arrays['ms2_normalized_intensities'],dtype=np.float64)
            if not math.isfinite(precursor) or precursor<=chem.PROTON:raise ValueError('Invalid measured precursor')
            if not np.isfinite(mz).all() or not np.isfinite(intensity).all():raise ValueError('Nonfinite original query peaks')
            queries.append(dict(molecule_id=selected_row['molecule_id'],spectrum_id=sid,
                instrument_type='timsTOF',adduct='[M+H]+',collision_energy_ev=float(meta['collision_energy_ev']),
                measured_precursor_mz=precursor,observed_neutral_mass=precursor-chem.PROTON,
                ms2_mzs=mz.tolist(),ms2_normalized_intensities=intensity.tolist(),
                source_input_sha256=pin['sha256']))
    # Pool masses/IDs can be read as compact columns. No pool fingerprint index.
    parquet=pq.ParquetFile(POOL)
    numeric=pq.read_table(POOL,columns=['pid','mass'],use_threads=False).to_pydict()
    pids=np.asarray(numeric['pid'],dtype=np.int64)
    masses=np.asarray(numeric['mass'],dtype=np.float64)
    del numeric
    if not np.isfinite(masses).all() or np.any(masses[1:]<masses[:-1]):raise ValueError('Pool masses not sorted finite')
    if not np.array_equal(pids,np.arange(len(pids))):raise ValueError('Pool pid/row-order contract changed')
    windows=[];selected_positions=set();full_positions=set()
    for q in queries:
        neutral=q['observed_neutral_mass']
        def window(ppm):
            delta=neutral*ppm*1e-6
            return np.arange(np.searchsorted(masses,neutral-delta,side='left'),np.searchsorted(masses,neutral+delta,side='right'),dtype=np.int64)
        original=window(10.);fallback=len(original)==0
        positions=window(30.) if fallback else original
        keep=positions.tolist()
        if len(keep)>128:
            keep=sorted(keep,key=lambda at:(abs(float(masses[at])-neutral),int(pids[at])))[:128]
        keep.sort() # Restore exact original pool ordering after the deterministic cap.
        selected_positions.update(keep);full_positions.update(positions.tolist())
        windows.append(dict(molecule_id=q['molecule_id'],spectrum_id=q['spectrum_id'],
            observed_neutral_mass=neutral,candidates_10ppm=len(original),fallback_30ppm_used=fallback,
            window_ppm_used=30. if fallback else 10.,uncapped_candidates=len(positions),
            cap_applied=len(positions)>128,final_candidates=len(keep),
            uncapped_pool_positions=positions.tolist(),selected_pool_positions=keep))
    candidate_structures=pool_smiles(selected_positions)
    candidates=[]
    for w in windows:
        for order,at in enumerate(w['selected_pool_positions']):
            candidate=candidate_structures[at]
            candidates.append(dict(molecule_id=w['molecule_id'],spectrum_id=w['spectrum_id'],
                candidate_index=order,pid=candidate['pid'],pool_position=at,smiles=candidate['smiles'],
                pool_neutral_mass=float(masses[at]),observed_neutral_mass=w['observed_neutral_mass'],
                absolute_mass_error_da=abs(float(masses[at])-w['observed_neutral_mass']),
                signed_mass_error_ppm=(float(masses[at])-w['observed_neutral_mass'])/w['observed_neutral_mass']*1e6))
    query_fields=['molecule_id','spectrum_id','instrument_type','adduct','collision_energy_ev','measured_precursor_mz',
                  'observed_neutral_mass','ms2_mzs','ms2_normalized_intensities','source_input_sha256']
    candidate_fields=['molecule_id','spectrum_id','candidate_index','pid','pool_position','smiles','pool_neutral_mass',
                      'observed_neutral_mass','absolute_mass_error_da','signed_mass_error_ppm']
    save(OUT/'queries.json',queries);write_csv(OUT/'queries.csv',queries,query_fields)
    save(OUT/'candidates.json',candidates);write_csv(OUT/'candidates.csv',candidates,candidate_fields)
    save(OUT/'candidate_windows.json',windows)
    files={name:dict(sha256=sha(OUT/name),bytes=(OUT/name).stat().st_size) for name in
           ['selection.json','queries.json','queries.csv','candidates.json','candidates.csv','candidate_windows.json']}
    freeze=dict(status='candidates_and_query_inputs_frozen_before_truth_coverage_or_model_scores',
                created_at_utc=stamp(),configuration=CONFIG,files=files,queries=8,candidate_rows=len(candidates),
                empty_queries=sum(w['final_candidates']==0 for w in windows),
                capped_queries=sum(w['cap_applied'] for w in windows),fallback_queries=sum(w['fallback_30ppm_used'] for w in windows),
                pool_path=str(POOL),pool_rows=len(masses),pool_schema=parquet.schema_arrow.names,
                pool_sha256=sha(POOL),native_chem_sha256=sha(CODE/'casmi/chem.py'),proton_mass=chem.PROTON,
                source_script_sha256=sha(__file__),elapsed_seconds=time.perf_counter()-start,**memory())
    save(OUT/'candidate_freeze.json',freeze)
    freeze_sha=sha(OUT/'candidate_freeze.json')
    # ---------------------------------------------------------------
    # ONLY NOW evaluate target identity coverage. No candidate mutation
    # occurs after this boundary; truth identity is not an inference input.
    # ---------------------------------------------------------------
    from validation.metric import assert_official_rdkit,identity
    assert_official_rdkit()
    all_structures=pool_smiles(full_positions)
    identities={at:identity(row['smiles']) for at,row in all_structures.items()}
    truths={r['spectrum_id']:r['official_identity'] for r in selected}
    evaluation=[]
    for w in windows:
        truth=truths[w['spectrum_id']]
        uncapped_hits=[at for at in w['uncapped_pool_positions'] if identities[at]==truth]
        capped_hits=[at for at in w['selected_pool_positions'] if identities[at]==truth]
        evaluation.append(dict(molecule_id=w['molecule_id'],spectrum_id=w['spectrum_id'],truth_official_identity=truth,
            uncapped_true_identity_present=bool(uncapped_hits),final_true_identity_present=bool(capped_hits),
            uncapped_true_pool_positions=uncapped_hits,final_true_pool_positions=capped_hits,
            cap_removed_all_true_candidates=bool(uncapped_hits and not capped_hits),
            final_candidates=w['final_candidates'],cap_applied=w['cap_applied']))
    # Verify label evaluation has not modified a single frozen candidate/input file.
    assert all(sha(OUT/name)==pin['sha256'] for name,pin in freeze['files'].items())
    coverage=dict(status='coverage_evaluated_only_after_candidate_freeze',candidate_freeze_sha256=freeze_sha,
                  evaluated_at_utc=stamp(),rows=evaluation,denominator_queries=8,
                  uncapped_coverage=sum(r['uncapped_true_identity_present'] for r in evaluation),
                  final_coverage=sum(r['final_true_identity_present'] for r in evaluation),
                  cap_removed_true_identity_queries=sum(r['cap_removed_all_true_candidates'] for r in evaluation),
                  all_eight_queries_retained=True,inference_inputs_unchanged=True,
                  ranking_or_model_scores_evaluated=False,pretraining_exposure='MSnLib v7 unknown',
                  rdkit_version=assert_official_rdkit(),**memory())
    save(OUT/'coverage_evaluation_only.json',coverage)
    final=dict(status='prepared_frozen_eight_query_candidate_development_pilot_no_inference',
               candidate_freeze_sha256=freeze_sha,coverage_evaluation_sha256=sha(OUT/'coverage_evaluation_only.json'),
               queries=8,candidate_rows=len(candidates),uncapped_coverage=coverage['uncapped_coverage'],
               final_coverage=coverage['final_coverage'],cap_removed_true_identity_queries=coverage['cap_removed_true_identity_queries'],
               total_seconds=time.perf_counter()-start,source_script_sha256=sha(__file__),**memory())
    save(OUT/'prepared.json',final)
    print(json.dumps(final,indent=2),flush=True)

if __name__=='__main__':
    os.environ['OMP_NUM_THREADS']='1';os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1'
    try:main()
    except Exception as exc:
        if OUT.exists():save(OUT/'failure.json',dict(status='failed',error_type=type(exc).__name__,error=str(exc),traceback=traceback.format_exc(),source_script_sha256=sha(__file__)))
        raise
