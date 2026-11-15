"""Derive candidate evidence from already frozen real matches; no reranking/tuning."""
from pathlib import Path
from collections import defaultdict
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.cache/rdkit-official-linux-2026033'));sys.path.insert(0,str(ROOT))
import numpy as np
import pandas as pd
from validation import metric

RUN=ROOT/'runs/extlib2_matching_20261114_v2';REPORT=ROOT/'reports/extlib2_matching_20261114'
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,v):Path(p).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')

def main():
    inputs={s:read(RUN/(s+'_actual_match_table.json')) for s in ['A','B','C']}
    tables={s:{(r['scope'],r['molecule_id']):r['hits'] for r in t['rows']} for s,t in inputs.items()}
    control={}
    for scope,path in [('diagnostic48',RUN/'diagnostic_identity_deduplicated_control.csv'),('production2',ROOT/'runs/generation_production_20261113_r2/kaggle/working/submission.csv')]:
        frame=pd.read_csv(path,dtype=str,keep_default_na=False)
        for mid,raw in frame.itertuples(index=False,name=None):control[(scope,mid)]=raw.split(';')
    features=[]
    for (scope,mid),candidates in control.items():
        grouped={s:defaultdict(list) for s in inputs}
        allhits=[]
        for source in inputs:
            hh=tables[source].get((scope,mid),[]);allhits.extend(hh)
            for h in hh:grouped[source][h['identity']].append(h)
        for rank,smi in enumerate(candidates,1):
            key=metric.identity(smi);row=dict(scope=scope,molecule_id=mid,smiles=smi,official_identity=key,original_rank=rank)
            for source in inputs:
                hits=grouped[source].get(key,[]);best=max(hits,key=lambda h:h['cosine']) if hits else None
                strong=[h for h in hits if h['cosine']>=.8]
                row.update({source+'_has_observed_score':bool(hits),source+'_max_cosine':best['cosine'] if best else np.nan,
                    source+'_best_matched_peaks':best['matched_peaks'] if best else np.nan,
                    source+'_distinct_support_spectra':len({h['spectrum_id'] for h in strong}),
                    source+'_distinct_strong_references':len({h['row'] for h in strong})})
            features.append(row)
    f=pd.DataFrame(features);f.to_parquet(RUN/'candidate_library_features.parquet',index=False)
    details=read(RUN/'diagnostic_query_details.json')['rows'];extra={}
    for arm in ['references_present','all_truth_references_absent']:
        rows=[r for r in details if r['arm']==arm];hits=[r for r in rows if r['C_hit'] is not None and r['C_hit']['cosine']>=.8]
        extra[arm]=dict(C_above_threshold=len(hits),C_hit_identity_in_original_control=sum(r['C_identity_already_in_control'] for r in hits),C_truth_new_to_control=sum(r['C_truth_new_to_control'] for r in hits),C_wrong_identity_new_to_control=sum(not r['C_identity_already_in_control'] and not r['C_correct_identity'] for r in hits),guard_blocked=sum(r['pipeline_protected'] or r['AB_accepted'] for r in hits),changed_events=[{k:r[k] for k in ['molecule_id','AB_rr','ABC_rr','C_correct_identity','C_identity_already_in_control','C_wrong_same_formula','C_hit']} for r in rows if r['C_changed']])
    result=dict(status='complete_evidence_summary_no_new_model',score_table_sha256={s:sha(RUN/(s+'_actual_match_table.json')) for s in inputs},candidate_feature_rows=len(f),candidate_feature_sha256=sha(RUN/'candidate_library_features.parquet'),feature_columns=f.columns.tolist(),missing_score_policy='NaN plus explicit has_observed_score; no imputed valid zero score',truth_labels_in_features=False,evaluation=extra,pipeline_context_boundary='The previous frozen pipeline library_max was retained in both arms. Truth removal affects all eligible AB/C reference hits, not prior model/engine caches; not a full-stack class2 ablation.',exact_champion_or_clean_CV=False,new_public_score=None)
    save(REPORT/'evidence_summary.json',result);print(json.dumps(result))

if __name__=='__main__':main()
