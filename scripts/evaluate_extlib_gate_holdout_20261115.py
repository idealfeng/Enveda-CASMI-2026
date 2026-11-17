"""Evaluate the predeclared gate only after frozen model inference on old holdout rows."""
from pathlib import Path
import argparse
from collections import Counter
import csv
import hashlib
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.cache/rdkit-official-linux-2026033'));sys.path.insert(0,str(ROOT))
from validation import metric

def sha(p):
    with Path(p).open('rb') as h:return hashlib.file_digest(h,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,v):Path(p).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def frame(p):
    with Path(p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def promote(raw,smiles,key):
    guesses=raw.split(';');keys=[metric.identity(s) for s in guesses]
    if key in keys:
        i=keys.index(key);new=[guesses[i]]+[s for j,s in enumerate(guesses) if j!=i]
    else:new=([smiles]+guesses)[:25]
    identities=[metric.identity(s) for s in new]
    if any(k is None for k in identities) or len(set(identities))!=len(identities):raise ValueError('Promotion invalid official identities')
    return ';'.join(new)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();data=args.data_root.resolve();out=args.output.resolve()
    if not all(p.is_relative_to(ROOT) for p in [data,out]) or out==ROOT:raise ValueError('D workspace only')
    metric.assert_official_rdkit()
    import numpy as np
    import pandas as pd
    pred=data/'scored';proof=read(pred/'verification.json')
    if proof['status']!='completed_fixed_model_feature_inference' or sha(pred/'probabilities.parquet')!=proof['probabilities_sha256'] or sha(data/'features.parquet')!=proof['features_sha256']:
        raise ValueError('Unbound completed scoring')
    released=ROOT/'reports/extlib2_execution_20261115'
    release=read(released/'release.json');capped=read(released/'gate_holdout48_capped_verification.json')
    if data!=ROOT/release['holdout_data_root'] or sha(released/'gate_holdout48_capped_verification.json')!=release['evidence']['gate_holdout48_capped_verification.json']:
        raise ValueError('Primary capped holdout release differs')
    if not all(capped['checks'].values()):raise ValueError('Capped exporter did not pass')
    for name,pin in capped['artifact_pins'].items():
        if sha(data/name)!=pin:raise ValueError('Capped artifact changed: '+name)
    old_root=ROOT/'runs/extlib2_matching_20261114_v2'
    matching=read(ROOT/'reports/extlib2_matching_20261114/verification.json')
    if sha(old_root/'C_actual_match_table.json')!=capped['source_C_match_sha256'] or capped['source_C_match_sha256']!=matching['score_artifact_sha256']['C']:
        raise ValueError('Frozen C matching differs')
    if sha(ROOT/'runs/validation_pilot_v2_20261104/truth.csv')!=capped['truth_control_metadata_sha256']:
        raise ValueError('Frozen evaluation truth changed')
    if sha(old_root/'diagnostic_query_details.json')!='2991584010200c07786cae7d71b9acbf45e960cb69008f2dbf221888f876359d':
        raise ValueError('Original protection context changed')
    c_source=ROOT/'assets/kaggle/nakhun/casmi26-extlib2/v1/extlib2/ext2_meta.parquet'
    c_source_pin=next(r['sha256'] for r in read(old_root/'C_actual_match_table.json')['source_files'] if r['path'].endswith('ext2_meta.parquet'))
    if sha(c_source)!=c_source_pin:raise ValueError('C proposal metadata changed')
    out.mkdir(parents=True,exist_ok=False)
    bound=[data/'features.parquet',data/'row_metadata.parquet',data/'feature_schema.json',data/'query_selection.json',
           old_root/'references_present_AB.csv',old_root/'all_truth_references_absent_AB.csv',old_root/'diagnostic_query_details.json']
    save(out/'input_bindings_before_evaluation.json',{p.relative_to(ROOT).as_posix():sha(p) for p in bound})
    features=pd.read_parquet(data/'features.parquet');meta=pd.read_parquet(data/'row_metadata.parquet');prob=pd.read_parquet(pred/'probabilities.parquet')
    if set(features.row_id)!=set(meta.row_id) or set(meta.row_id)!=set(prob.row_id):raise ValueError('Unaligned scored rows')
    table=meta.merge(features,on='row_id',validate='one_to_one').merge(prob,on='row_id',validate='one_to_one')
    if table.query_spectra.max()>3:raise ValueError('Primary deployment contract cap3 violated')
    # Labels are first opened here, after fixed probabilities were saved.
    truth={r['molecule_id']:r['official_identity'] for r in frame(ROOT/'runs/validation_pilot_v2_20261104/truth.csv')}
    context={(r['arm'],r['molecule_id']):r for r in read(old_root/'diagnostic_query_details.json')['rows']}
    cmeta=pd.read_parquet(c_source,columns=['normalized_smiles'])
    evaluations={};allrows=[]
    for arm,oldarm in [('references_present','references_present'),('all_true_identity_references_absent','all_truth_references_absent')]:
        baseline=frame(old_root/(oldarm+'_AB.csv'));by_mid=table.loc[table.reference_condition.eq(arm)].set_index('molecule_id')
        if set(by_mid.index)!=set(r['molecule_id'] for r in baseline):raise ValueError('Scored identity scope differs')
        before=[];fixed=[];learned=[];accepted=Counter();rows=[]
        for base in baseline:
            mid=base['molecule_id'];r=by_mid.loc[mid];ctx=context[(oldarm,mid)]
            raw=base['smiles'];a=raw;b=raw;key=r.proposed_identity
            has=bool(r.has_match) and isinstance(key,str) and bool(key)
            protected=bool(ctx['pipeline_protected'] or ctx['AB_accepted'])
            fixed_accept=has and not protected and float(r.best_cosine)>=.8
            learned_accept=has and not protected and float(r.probability)>=.9
            if fixed_accept or learned_accept:
                refrow=int(r.reference_row);smiles=str(cmeta.iloc[refrow]['normalized_smiles'])
                if metric.identity(smiles)!=key:raise ValueError('Predicted proposal and actual library row differ')
                if fixed_accept:a=promote(raw,smiles,key)
                if learned_accept:b=promote(raw,smiles,key)
            t=truth[mid];rank=lambda s:metric.first_correct_rank(t,s)
            rr=lambda k:0. if k is None else 1/k
            ranks=[rank(s) for s in [raw,a,b]];values=[rr(k) for k in ranks]
            before.append(dict(base));fixed.append(dict(molecule_id=mid,smiles=a));learned.append(dict(molecule_id=mid,smiles=b))
            for policy,take in [('fixed',fixed_accept),('learned',learned_accept)]:
                if take:accepted[policy+'_accepted']+=1;accepted[policy+('_correct' if key==t else '_incorrect')]+=1
            rows.append(dict(molecule_id=mid,arm=arm,protected=protected,has_match=has,probability=float(r.probability),
                             best_cosine=float(r.best_cosine) if np.isfinite(r.best_cosine) else None,
                             proposal_identity=key if isinstance(key,str) else None,fixed_accept=bool(fixed_accept),learned_accept=bool(learned_accept),
                             ranks=ranks,rr=values,learned_delta_vs_AB=values[2]-values[0],learned_delta_vs_fixed=values[2]-values[1]))
        for name,items in [('AB',before),('C_cap3_fixed080',fixed),('C_cap3_gate090',learned)]:
            with (out/(arm+'_'+name+'.csv')).open('w',encoding='utf-8',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=['molecule_id','smiles']);writer.writeheader();writer.writerows(items)
        mrr=[sum(r['rr'][j] for r in rows)/len(rows) for j in range(3)]
        if abs(mrr[0]-matching['evaluations'][oldarm]['AB_mrr25'])>1e-12:raise ValueError('Original AB metric does not replay')
        evaluations[arm]=dict(queries=len(rows),AB_mrr25=mrr[0],C_cap3_fixed080_mrr25=mrr[1],C_cap3_gate090_mrr25=mrr[2],
                              learned_delta_vs_AB=mrr[2]-mrr[0],learned_delta_vs_fixed=mrr[2]-mrr[1],accepted=dict(accepted),
                              gate_improved_vs_AB=sum(r['learned_delta_vs_AB']>0 for r in rows),gate_worsened_vs_AB=sum(r['learned_delta_vs_AB']<0 for r in rows))
        allrows.extend(rows)
    result=dict(status='completed_frozen_gate_component_holdout',threshold=.9,query_spectra_cap=3,
                evaluations=evaluations,rows=allrows,model_sha256=proof['model_sha256'],prediction_sha256=proof['probabilities_sha256'],
                data_feature_sha256=sha(data/'features.parquet'),no_training_on_holdout=True,no_parameter_or_threshold_selection=True,
                public_score=None,exact_champion_full_pipeline=False,
                boundary='C-component holdout on old48 candidate/AB controls, legacy model pretraining exposure remains. Gate fit uses 500 disjoint query structures. C alone uses fixed max3 spectra to stay inside training count support; original AB pipeline retains all spectra. Artificial reference presence/absence conditions do not reveal hidden class shares.')
    save(out/'verification.json',result);print(json.dumps(dict(status=result['status'],evaluations=evaluations)))

if __name__=='__main__':main()
