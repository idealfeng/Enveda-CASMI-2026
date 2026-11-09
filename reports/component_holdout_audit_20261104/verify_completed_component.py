"""Independent CPU verification of a completed frozen component experiment."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import numpy as np
import pandas as pd
from validation.metric import identity,molecular_formula,assert_official_rdkit

RUN=ROOT/'runs/component_neural_pilot_20261105'

def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def main():
    assert_official_rdkit()
    receipt=json.loads((RUN/'run_receipt.json').read_text())
    evaluation=json.loads((RUN/'evaluation.json').read_text())
    plan=json.loads((RUN/'plan.json').read_text());prepared=json.loads((RUN/'prepared.json').read_text())
    assert receipt['status']=='complete'
    assert receipt['plan_sha256']==sha(RUN/'plan.json')==prepared['plan_sha256']
    assert receipt['prepared_sha256']==sha(RUN/'prepared.json')
    for name,value in receipt['outputs'].items():assert sha(RUN/name)==value,name
    for name,value in prepared['files'].items():assert sha(RUN/name)==value['sha256'],name
    truth=pd.read_csv(RUN/'truth.csv',keep_default_na=False)
    baseline=pd.read_csv(RUN/'baseline.csv',keep_default_na=False)
    treatment=pd.read_csv(RUN/'treatment.csv',keep_default_na=False)
    retrieved=pd.read_parquet(RUN/'retrieved_candidates.parquet')
    fixed=pd.read_parquet(RUN/'fixed_candidates.parquet')
    scores=pd.read_parquet(RUN/'component_scores.parquet')
    nbpath=ROOT/'validation/evidence/official_metric_20261104/source.ipynb'
    nb=json.loads(nbpath.read_text());source=nb['cells'][0]['source'];scope={'__name__':'archived_official_component_verifier'}
    exec(compile(''.join(source) if isinstance(source,list) else source,str(nbpath),'exec'),scope)
    official_solution=truth.rename(columns={'normalized_smiles':'smiles'})[['molecule_id','smiles']]
    official={'baseline':scope['score'](official_solution.copy(),baseline.copy(),'molecule_id'),
              'treatment':scope['score'](official_solution.copy(),treatment.copy(),'molecule_id')}
    assert np.isclose(official['baseline'],evaluation['baseline_metrics']['mrr_at_25'])
    assert np.isclose(official['treatment'],evaluation['metrics']['mrr_at_25'])
    b=baseline.set_index('molecule_id').smiles.to_dict();t=treatment.set_index('molecule_id').smiles.to_dict()
    per=[];changed=[]
    for row in truth.itertuples():
        first=b[row.molecule_id].split(';');second=t[row.molecule_id].split(';')
        bk=[identity(s) for s in first];tk=[identity(s) for s in second]
        assert set(bk)==set(tk),row.molecule_id
        assert set(scores.loc[scores.molecule_id.eq(row.molecule_id),'identity'])==set(bk),row.molecule_id
        br=next((i for i,key in enumerate(bk,1) if key==row.identity),None)
        tr=next((i for i,key in enumerate(tk,1) if key==row.identity),None)
        pooled=retrieved[retrieved.molecule_id.eq(row.molecule_id)]
        hit=row.identity in set(pooled.identity)
        delta=(1/tr if tr else 0)-(1/br if br else 0)
        item={'molecule_id':row.molecule_id,'identity':row.identity,'panel':row.panel,'source':row.source,
              'baseline_rank':br,'treatment_rank':tr,'delta_rr':delta,'retrieved':hit,
              'retrieved_candidates':len(pooled),'fixed_candidates':len(first),
              'truth_formula':molecular_formula(row.normalized_smiles),
              'baseline_top1_formula':molecular_formula(first[0]),'treatment_top1_formula':molecular_formula(second[0]),
              'ranking_changed':bk!=tk,'top1_changed':bk[0]!=tk[0]}
        per.append(item)
        if br!=tr:changed.append(item)
    contributions={}
    for name,value in [('overall',per),('cross_component',[r for r in per if r['panel']=='cross_component']),
                       ('np_public_development',[r for r in per if r['panel']=='np_public_development'])]:
        value=sorted(value,key=lambda row:row['molecule_id'])
        delta=np.array([r['delta_rr'] for r in value]);rng=np.random.default_rng(20261104)
        draws=np.array([delta[rng.integers(0,len(delta),len(delta))].mean() for _ in range(2000)])
        contributions[name]={'n':len(value),'improved':int((delta>0).sum()),'worsened':int((delta<0).sum()),'unchanged_truth_rank':int((delta==0).sum()),
                             'delta':float(delta.mean()),'ci':list(np.quantile(draws,[.025,.975]))}
    model_input=json.loads((ROOT/'assets/kaggle/dmitriigluzdov/casmi26-fold-safe-fpnet/v5/MODEL_INPUTS.json').read_text())
    plan_by_name={Path(row['path']).name:row for row in plan['assets']}
    for name,key in [('fpnet_fold0.pt','checkpoint_sha256'),('fp_bits.npy','fp_bits_sha256'),('fpnet.py','fpnet_code_sha256')]:
        assert plan_by_name[name]['sha256']==model_input[key]
    assert plan_by_name['best_validation_model.pt']['sha256']=='969d13443fcf168eae1e00e56a8e0ae87dcb16f337cb6dbac959e7cd218f089c'
    assert all(not row['selection_record']['saner_checkpoint_selection_candidate_used'] for row in plan['queries'])
    sys.path.insert(0,str(ROOT/'assets/kaggle/ahmedberatozer/casmi26-v3-models/v4/code'))
    from casmi import chem
    from rdkit import Chem
    from rdkit.Chem import rdMolDescriptors
    pool=pd.read_parquet(ROOT/'assets/kaggle/ahmedberatozer/casmi26-v2-pool/v1/pool_meta.parquet')
    query=pd.read_parquet(RUN/'queries.parquet')
    recall_diagnostics=[]
    for row in truth.itertuples():
        detail=next(r for r in per if r['molecule_id']==row.molecule_id)
        if detail['retrieved']:continue
        frame=query[query.molecule_id.eq(row.molecule_id)]
        observed=chem.neutral_mass(frame.precursor_mz.to_numpy(),frame.adduct.to_numpy())
        mass=rdMolDescriptors.CalcExactMolWt(Chem.MolFromSmiles(row.normalized_smiles))
        exact=pool[pool.key.eq(row.identity)]
        recall_diagnostics.append({'molecule_id':row.molecule_id,'truth_exact_mass':mass,
                                   'observed_neutral_mass_median':float(np.median(observed)),
                                   'median_mass_error_ppm':float((np.median(observed)-mass)/mass*1e6),
                                   'query_observed_precursors':frame[['adduct','precursor_mz','ingest_lib']].to_dict('records'),
                                   'exact_declared_identity_pool_rows':exact[['key','mass','smiles']].to_dict('records'),
                                   'scope':'Pool key check is declared-key lookup, not exhaustive equivalence search over the entire pool.'})
    result={'status':'verified','official_metric_source_sha256':sha(nbpath),'official_scores':official,
            'all_output_hashes_match_run_receipt':True,'fixed_top25_identity_sets_equal':True,
            'candidate_recall':sum(r['retrieved'] for r in per)/len(per),
            'missing_from_retrieval':[r for r in per if not r['retrieved']],
            'retrieved_but_truncated_out_of_fixed25':[r for r in per if r['retrieved'] and r['baseline_rank'] is None],
            'truth_rank_changes':changed,'ranking_changed_molecules':sum(r['ranking_changed'] for r in per),
            'top1_changed_molecules':sum(r['top1_changed'] for r in per),'paired_contributions':contributions,
            'spectrum_source_counts':pd.read_parquet(RUN/'queries.parquet').ingest_lib.value_counts().to_dict(),
            'model_input_contract_matches_frozen_plan':True,'per_molecule':per}
    result['recall_miss_mass_diagnostics']=recall_diagnostics
    (ROOT/'reports/component_neural_pilot_independent_verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ['per_molecule','truth_rank_changes']},indent=2))
    print('CHANGED',json.dumps(changed,indent=2))

if __name__=='__main__':main()
