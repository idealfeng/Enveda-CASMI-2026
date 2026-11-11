"""Read metadata and artifacts only; never load models or rerun generation."""
from collections import Counter
from pathlib import Path
import hashlib,json,sys
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from validation.metric import assert_official_rdkit,identity

def sha(p):
    with Path(p).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def main():
    assert_official_rdkit()
    user=ROOT/'produre2';art=user/'artifacts';pool=ROOT/'assets/kaggle/ahmedberatozer/casmi26-v2-pool/v1'
    paths=[user/n for n in ['q345_lib.py','q3_ablation.py','q4_full_rank.py','q5_templates.py','Q345_RESULTS.md']]+[art/n for n in ['q3_ablation.json','q4_full_rank.json','q5_real_paths.json']]
    before={str(p.relative_to(ROOT)):sha(p) for p in paths}
    truth=pd.read_csv(ROOT/'runs/validation_pilot_v2_20261104/truth.csv',dtype=str)
    st=pq.read_table(pool/'train_structs.parquet',columns=['key','sid','smiles']).to_pydict()
    pm=pq.read_table(pool/'pool_meta.parquet',columns=['key','smiles']).to_pydict()
    scount=Counter(st['key']);pcount=Counter(pm['key'])
    wanted=set(truth.official_identity)
    bykey={k:[] for k in wanted}
    for i,k in enumerate(st['key']):
        if k in bykey:bykey[k].append(i)
    pool_smi={k:[] for k in wanted}
    for k,s in zip(pm['key'],pm['smiles']):
        if k in pool_smi:pool_smi[k].append(s)
    sidvalues=np.asarray(pq.read_table(ROOT/'runs/shared_spec_cache/spec_meta.parquet',columns=['sid']).column('sid').to_numpy(),dtype=np.int64)
    spectrum_counts=np.bincount(sidvalues)
    q4=json.loads((art/'q4_full_rank.json').read_text());recovered={r['molecule_id'] for r in q4['rows'] if r.get('truth_is_gen')}
    rows=[]
    for r in truth.itertuples(index=False):
        idx=bykey[r.official_identity];sids=[int(st['sid'][i]) for i in idx]
        official=[identity(st['smiles'][i]) for i in idx]
        remaining=[sid for sid,k in zip(sids,official) if sid!=sids[0] and k==r.official_identity] if sids else []
        rows.append(dict(molecule_id=r.molecule_id,official_identity=r.official_identity,
            exact_key_train_sids=sids,train_sid_official_keys=official,
            remaining_same_official_sids_after_first_exclusion=remaining,
            remaining_same_official_spectra=sum(int(spectrum_counts[sid]) for sid in remaining),
            exact_key_pool_entries=pcount[r.official_identity],pool_smiles_official_keys=[identity(s) for s in pool_smi[r.official_identity]],
            recovered_in_q4=r.molecule_id in recovered))
    ranks=[r['rank'] for r in q4['rows'] if r.get('truth_is_gen')]
    denom=len(q4['rows'])
    scores=[1/r['rank'] if r.get('rank') and r['rank']<=25 else 0. for r in q4['rows']]
    source=ROOT/'third_party/canqiang_e006/engine_source_v4b/code/casmi'
    attributed=ROOT/'assets/kaggle/dmitriigluzdov/casmi26-attributed-v4g-reproduction-assets/v9/casmi26-v4b-models'
    oldmodel=ROOT/'assets/kaggle/ahmedberatozer/casmi26-v4b-models/v4'
    source_equal={n:sha(source/n)==sha(attributed/'code/casmi'/n) for n in ['engine.py','derive.py','chem.py','pool.py','library.py']}
    asset_equal={n:sha(oldmodel/n)==sha(attributed/n) for n in ['ranker_v4b.pkl','fpnet_0.pt','fe_A.pt','fe_B.pt','fe_D.pt','code/fe_v4/v1engine.py','code/fe_v4/hooks_v1.py']}
    q3=json.loads((art/'q3_ablation.json').read_text())
    report=dict(status='completed_read_only',source_equal_to_formal_v9=source_equal,asset_equal_to_formal_v9=asset_equal,
        q4_recomputed=dict(queries=denom,recovered=len(ranks),rank_histogram=dict(Counter(ranks)),mrr25=sum(scores)/denom,
            recall25=sum(bool(r.get('rank')) and r['rank']<=25 for r in q4['rows'])/denom,
            top1=sum(r.get('rank')==1 for r in q4['rows'])/denom,errors=sum('error' in r for r in q4['rows'])),
        isolation=dict(queries_with_multiple_exact_key_train_sids=sum(len(r['exact_key_train_sids'])>1 for r in rows),
            queries_with_remaining_same_official_sid=sum(bool(r['remaining_same_official_sids_after_first_exclusion']) for r in rows),
            recovered_queries_with_remaining_same_official_sid=sum(r['recovered_in_q4'] and bool(r['remaining_same_official_sids_after_first_exclusion']) for r in rows),
            queries_with_multiple_exact_key_pool_entries=sum(r['exact_key_pool_entries']>1 for r in rows),
            scope='Only exact label-key train SIDs and exact-key pool rows checked. Other canonical aliases outside those keys are not exhaustively audited.'),
        q3_counts=q3['recovered_counts'],rows=rows,user_file_sha256=before,
        no_model_gpu_or_generation_execution=True)
    report['user_files_unchanged']=before=={str(p.relative_to(ROOT)):sha(p) for p in paths}
    out=ROOT/'reports/produre_review_20261111';out.mkdir(parents=True,exist_ok=True)
    (out/'q345_metadata_audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['q4_recomputed','isolation','source_equal_to_formal_v9','asset_equal_to_formal_v9','user_files_unchanged']},indent=2))

if __name__=='__main__':main()
