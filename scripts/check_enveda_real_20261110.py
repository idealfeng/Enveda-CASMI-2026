"""Use real published E spectra as interface canaries, never an efficacy panel."""
from pathlib import Path
import json
import sys
import time

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(ROOT))
import enveda_matching_20261110 as E
from review_enveda_matching_20261110 import original_cosine
from validation.metric import assert_official_rdkit,identity

def main():
    assert_official_rdkit();started=time.monotonic()
    out=ROOT/'runs/enveda_matching_canary_20261110'
    if (out/'verification.json').exists():raise FileExistsError('Preserve completed real canary')
    out.mkdir(parents=True,exist_ok=True)
    source=ROOT/'assets/kaggle/egehseyinca/enveda180-casmi26-reference-ccby4/v1'/E.SOURCE_FILE
    aliases=ROOT/'reports/external_reference_pilot_20261107/alias_related_reference_rows.parquet'
    candidates=sorted(pq.read_table(aliases).to_pylist(),key=lambda r:int(r['row_index']))
    source_pf=pq.ParquetFile(source);group_starts=[];total=0
    for group in range(source_pf.num_row_groups):
        group_starts.append(total);total+=source_pf.metadata.row_group(group).num_rows
    cached_group=None;cached_table=None
    distractors=['C'*n for n in range(1,26)]
    dkeys=[identity(s) for s in distractors]
    assert None not in dkeys and len(set(dkeys))==25
    picked=[];counts={'[M+H]+':0,'[M-H]-':0};seen=set()
    for row in candidates:
        a=row['adduct'];want=2 if a=='[M+H]+' else 1
        if a not in counts or counts[a]>=want:continue
        k=identity(row['smiles'])
        if not k or k in seen or k in dkeys:continue
        index=int(row['row_index'])
        group=max(g for g,start in enumerate(group_starts) if start<=index)
        if cached_group!=group:
            cached_table=source_pf.read_row_group(group,columns=list(E.REQUIRED_COLUMNS));cached_group=group
        actual=cached_table.slice(index-group_starts[group],1).to_pylist()[0]
        if actual['reference_key']!=row['publisher_reference_key'] or actual['adduct']!=a:
            raise ValueError('Alias row index/source binding changed')
        mode=E.ALLOWED_ADDUCTS[a];prec=float(row['neutral_mass'])+mode*E.CARRIER
        mz=np.asarray(actual['ms2_mzs'],dtype=np.float64);it=np.asarray(actual['ms2_normalized_intensities'],dtype=np.float64)
        valid=np.isfinite(mz)&np.isfinite(it)&(mz>0)&(it>0)&(mz<=prec+.5)
        mz,it=mz[valid],it[valid];o=np.argsort(mz);mz,it=mz[o],it[o]
        if len(mz)<4:continue
        mid='actual_e_'+str(len(picked))
        picked.append(dict(molecule_id=mid,ms2_mzs=mz,ms2_normalized_intensities=it,
            precursor_mz=prec,ionization_mode='positive' if mode==1 else 'negative',
            adduct=a,collision_energy_ev=np.array([],dtype=np.float64),
            canary_source_smiles=row['smiles'],canary_source_identity=k))
        counts[a]+=1;seen.add(k)
        if len(picked)==3:break
    del cached_table,source_pf
    if counts!={'[M+H]+':2,'[M-H]-':1}:raise ValueError('Cannot prepare both-adduct real E canary')
    extra=dict(picked[0]);extra['molecule_id']='actual_e_protected';picked.append(extra)
    extra=dict(picked[0]);extra.update(molecule_id='actual_e_unsupported_na',adduct='[M+Na]+');picked.append(extra)
    frame=pd.DataFrame(picked)
    frame.drop(columns=['canary_source_smiles','canary_source_identity']).to_parquet(out/'queries.parquet',index=False)
    control=pd.DataFrame([(r['molecule_id'],';'.join(distractors)) for r in picked],columns=['molecule_id','smiles'])
    control.to_csv(out/'submission_control.csv',index=False)
    evidence=pd.DataFrame([dict(molecule_id=r['molecule_id'],library_max=.95 if r['molecule_id']=='actual_e_protected' else 0.) for r in picked])
    evidence.to_parquet(out/'frozen_candidate_evidence.parquet',index=False)
    queries={r['molecule_id']:[dict(mz=r['ms2_mzs'],it=r['ms2_normalized_intensities'],
        prec=r['precursor_mz'],adduct=r['adduct'],mode=1 if r['ionization_mode']=='positive' else -1)] for r in picked}
    hits,audit=E.score_enveda(queries,{'actual_e_protected':.95},source,original_cosine())
    checks=dict(full_published_pin=audit['sha256']==E.SOURCE_SHA256 and audit['bytes']==E.SOURCE_BYTES,
        full_metadata_scanned=audit['rows_scanned']==audit['source_rows_total']==730252,
        all_three_real_queries_hit=all('actual_e_'+str(i) in hits for i in range(3)),
        same_adduct_mode_only=all(v['adduct']==queries[mid][0]['adduct'] and v['mode']==queries[mid][0]['mode'] for mid,v in hits.items()),
        protected_query_preserved='actual_e_protected' not in hits,
        unsupported_na_preserved='actual_e_unsupported_na' not in hits,
        real_cosine_finite=all(np.isfinite(v['cosine']) and v['cosine']>=.8 for v in hits.values()),
        real_matched_peaks=all(v['matched_peaks']>=4 for v in hits.values()),
        bounded_batch=audit['max_batch_rows']<=8192,
        no_full_reference_objects=audit['usable_selected_reference_rows']<audit['source_rows_total'],
        control_valid=all(identity(s) for s in distractors) and len(set(dkeys))==25,
        no_truth_metric_computed=True)
    report=dict(status='passed' if all(checks.values()) else 'failed',checks=checks,
        source_sha256=E.sha(ROOT/'scripts/enveda_matching_20261110.py'),
        queries=5,eligible_real_queries=3,returned_hits=len(hits),
        actual_scan_seconds=audit['elapsed_seconds'],total_seconds=time.monotonic()-started,
        selected_reference_rows=audit['selected_reference_rows'],process_peak_rss_kb=audit['process_peak_rss_kb'],
        interface_self_match_canary=True,independent_validation_or_hidden_coverage=False,
        query_provenance='Three rows from published E alias-related references; protected and unsupported-adduct copies for interface checks',
        source_records=[dict(molecule_id=r['molecule_id'],source_smiles=r['canary_source_smiles'],official_identity=r['canary_source_identity']) for r in picked])
    for name,value in [('matches.json',hits),('audit.json',audit),('verification.json',report)]:
        (out/name).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:report[k] for k in ['status','eligible_real_queries','returned_hits','actual_scan_seconds','selected_reference_rows','process_peak_rss_kb']},indent=2))
    if not all(checks.values()):raise ValueError(repr(checks))

if __name__=='__main__':main()
