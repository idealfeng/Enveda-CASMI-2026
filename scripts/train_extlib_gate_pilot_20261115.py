"""Train one fixed 500-step match-correctness gate on disjoint query groups.

This is a training/speed pilot, not a candidate-ranker or hidden-score claim.
Development labels never choose a checkpoint, feature set, or threshold.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import os
import resource
import sys
import time

ROOT=Path(__file__).resolve().parents[1]

def sha(p):
    with Path(p).open('rb') as h:return hashlib.file_digest(h,'sha256').hexdigest()
def save(p,v):Path(p).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n',encoding='utf-8')

CONFIG=dict(seed=20261115,steps=500,batch_size=128,learning_rate=.001,weight_decay=.001,
            hidden_width=16,device='cpu',objective='binary_cross_entropy_top_reference_identity_correct',
            deployment_candidate_threshold=.9,diagnostic_thresholds=[.5,.9,.95],
            checkpoint_selection='last_step_only_no_development_selection',
            preprocessing='training_only_mean_std_plus_explicit_missing_indicators',
            feature_scope='Only explicit 14 numeric source-match features; no query identity/condition/split/label')

def metrics(y,p,has_match,cosine):
    import numpy as np
    import pandas as pd
    y=np.asarray(y,dtype=bool);p=np.asarray(p,dtype=float)
    pos=int(y.sum());neg=int((~y).sum())
    auc=float((pd.Series(p).rank(method='average').to_numpy()[y].sum()-pos*(pos+1)/2)/(pos*neg)) if pos and neg else None
    clip=np.clip(p,1e-7,1-1e-7)
    target=y.astype(float)
    result=dict(rows=len(y),positives=pos,negatives=neg,auc=auc,brier=float(np.mean((p-target)**2)),
                log_loss=float(np.mean(-target*np.log(clip)-(1-target)*np.log(1-clip))))
    def acceptance(mask):
        mask=np.asarray(mask,dtype=bool);tp=int((mask&y).sum());fp=int((mask&~y).sum());n=int(mask.sum())
        return dict(accepted=n,correct=tp,incorrect=fp,precision=tp/n if n else None,
                    coverage=n/len(y),correct_match_recall=tp/pos if pos else None,
                    false_accept_rate=fp/neg if neg else None)
    result['fixed_cosine_080']=acceptance(has_match&(cosine>=.8))
    result['learned']={str(t):acceptance(has_match&(p>=t)) for t in CONFIG['diagnostic_thresholds']}
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root',type=Path,default=ROOT/'runs/extlib_gate_pilot_20261115')
    parser.add_argument('--output',type=Path,default=ROOT/'runs/extlib_gate_train_20261115')
    args=parser.parse_args();data=args.data_root.resolve();out=args.output.resolve()
    if not data.is_relative_to(ROOT) or not out.is_relative_to(ROOT) or out==ROOT:raise ValueError('D workspace paths only')
    proof=json.loads((ROOT/'reports/extlib2_execution_20261115/gate_pilot_verification.json').read_text())
    if proof['status']!='completed_disjoint_C_gate_pilot' or not all(proof['checks'].values()):raise ValueError('Completed disjoint dataset required')
    for name,pin in proof['artifact_pins'].items():
        if sha(data/name)!=pin:raise ValueError('Dataset artifact changed: '+name)
    out.mkdir(parents=True,exist_ok=False)
    save(out/'configuration.json',dict(CONFIG,data_root=str(data.relative_to(ROOT)),dataset_verification_sha256=sha(ROOT/'reports/extlib2_execution_20261115/gate_pilot_verification.json'),source_script_sha256=sha(__file__)))
    import numpy as np
    import pandas as pd
    import torch
    torch.set_num_threads(2);torch.manual_seed(CONFIG['seed']);np.random.seed(CONFIG['seed'])
    schema=json.loads((data/'feature_schema.json').read_text());names=schema['feature_columns']
    features=pd.read_parquet(data/'features.parquet');labels=pd.read_parquet(data/'labels.parquet');meta=pd.read_parquet(data/'row_metadata.parquet')
    if set(features.columns)!={'row_id',*names} or len(names)!=14:raise ValueError('Unexpected feature contract')
    for table in (features,labels,meta):
        if not table.row_id.is_unique:raise ValueError('Duplicate learning row key')
    if set(features.row_id)!=set(labels.row_id) or set(features.row_id)!=set(meta.row_id):raise ValueError('Unaligned feature/label rows')
    labels=labels.set_index('row_id').loc[features.row_id];meta=meta.set_index('row_id').loc[features.row_id]
    train=meta['split'].eq('train').to_numpy();dev=meta['split'].eq('development').to_numpy()
    train_groups=set(meta.loc[train,'official_query_identity']);dev_groups=set(meta.loc[dev,'official_query_identity'])
    if train_groups&dev_groups or not train.any() or not dev.any() or not np.all(train|dev):raise ValueError('Non-disjoint split')
    group_counts=meta.groupby('official_query_identity').size()
    if not group_counts.eq(2).all():raise ValueError('Each query must have exactly the fixed two conditions')
    y=labels['label'].to_numpy(dtype=np.float32);raw=features[names].to_numpy(dtype=np.float32)
    raw[~np.isfinite(raw)]=np.nan;missing=np.isnan(raw)
    count=np.isfinite(raw[train]).sum(0);sums=np.nansum(raw[train],axis=0)
    mean=np.divide(sums,count,out=np.zeros(len(names),dtype=np.float32),where=count>0)
    filled=np.where(missing,mean,raw);sd=filled[train].std(0);sd=np.where(sd>1e-6,sd,1.)
    X=np.concatenate([(filled-mean)/sd,missing.astype(np.float32)],axis=1).astype(np.float32)
    if not np.isfinite(X).all():raise ValueError('Nonfinite design matrix')
    xtrain=torch.from_numpy(X[train]);ytrain=torch.from_numpy(y[train]);indices=torch.arange(len(xtrain))
    model=torch.nn.Sequential(torch.nn.Linear(X.shape[1],CONFIG['hidden_width']),torch.nn.ReLU(),torch.nn.Linear(CONFIG['hidden_width'],1))
    optimizer=torch.optim.AdamW(model.parameters(),lr=CONFIG['learning_rate'],weight_decay=CONFIG['weight_decay'])
    loss_fn=torch.nn.BCEWithLogitsLoss();history=[];started=time.monotonic()
    model.train()
    for step in range(1,CONFIG['steps']+1):
        chosen=indices[torch.randint(len(indices),(min(CONFIG['batch_size'],len(indices)),))]
        optimizer.zero_grad(set_to_none=True);logit=model(xtrain[chosen]).squeeze(1);loss=loss_fn(logit,ytrain[chosen]);loss.backward();optimizer.step()
        if step in (1,50,100,250,500):history.append(dict(step=step,training_minibatch_loss=float(loss.detach()),seconds=time.monotonic()-started))
    seconds=time.monotonic()-started;model.eval()
    with torch.inference_mode():p=torch.sigmoid(model(torch.from_numpy(X)).squeeze(1)).numpy()
    if not np.isfinite(p).all():raise ValueError('Nonfinite learned probabilities')
    torch.save(dict(model_state=model.state_dict(),configuration=CONFIG,feature_names=names,impute_mean=mean.tolist(),standard_deviation=sd.tolist(),model_input_width=X.shape[1],dataset_pins=proof['artifact_pins'],train_groups_sha256=hashlib.sha256('\n'.join(sorted(train_groups)).encode()).hexdigest()),out/'last_step_500.pt')
    predictions=pd.DataFrame(dict(row_id=features.row_id,probability=p));predictions.to_parquet(out/'predictions.parquet',index=False)
    has=features['has_match'].to_numpy(dtype=bool);cos=features['best_cosine'].to_numpy(dtype=float)
    results={}
    for split,mask in [('train',train),('development',dev)]:
        results[split]=metrics(y[mask],p[mask],has[mask],cos[mask])
        results[split]['by_reference_condition']={condition:metrics(y[mask&meta.reference_condition.eq(condition).to_numpy()],p[mask&meta.reference_condition.eq(condition).to_numpy()],has[mask&meta.reference_condition.eq(condition).to_numpy()],cos[mask&meta.reference_condition.eq(condition).to_numpy()]) for condition in meta.reference_condition.unique()}
    result=dict(status='completed_500_step_training_pilot',configuration=CONFIG,seconds_500_steps=seconds,steps_per_second=CONFIG['steps']/seconds,
                cpu_peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,train_query_groups=len(train_groups),development_query_groups=len(dev_groups),feature_names=names,expanded_input_width=X.shape[1],
                results=results,history=history,model_sha256=sha(out/'last_step_500.pt'),prediction_sha256=sha(out/'predictions.parquet'),dataset_selection_sha256=proof['selection_sha256'],
                public_score=None,full_champion_pipeline_executed=False,no_development_checkpoint_selection=True,
                decision='Pilot only. Fixed p>=0.9 is the predeclared prospective gate; no threshold chosen by these development results. No automatic production admission.',
                boundary='New C top-reference identity-correctness classifier, not full candidate ranking or hidden MRR. Balanced presence/absence conditions are controlled scenarios, not estimated hidden-class shares. Dataset raw-family MSG exclusions have documented alias limits.')
    save(out/'verification.json',result)
    report=ROOT/'reports/extlib_gate_train_20261115';report.mkdir(parents=True,exist_ok=True);save(report/'verification.json',result)
    print(json.dumps(dict(status=result['status'],seconds_500_steps=seconds,train_queries=len(train_groups),development_queries=len(dev_groups),development=results['development'])))

if __name__=='__main__':main()
