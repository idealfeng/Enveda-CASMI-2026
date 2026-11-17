"""Export the fixed 500-step gate and score explicit feature rows without labels."""
from pathlib import Path
import argparse
import hashlib
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
def sha(p):
    with Path(p).open('rb') as h:return hashlib.file_digest(h,'sha256').hexdigest()
def save(p,v):Path(p).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--features',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--model',type=Path,default=ROOT/'runs/extlib_gate_train_20261115/last_step_500.pt')
    args=p.parse_args();out=args.output.resolve();model_path=args.model.resolve();source=args.features.resolve()
    if not all(x.is_relative_to(ROOT) for x in [out,model_path,source]) or out==ROOT:raise ValueError('D workspace only')
    proof=json.loads((ROOT/'runs/extlib_gate_train_20261115/verification.json').read_text())
    if sha(model_path)!=proof['model_sha256']:raise ValueError('Fixed training model changed')
    out.mkdir(parents=True,exist_ok=False)
    import numpy as np
    import pandas as pd
    import torch
    torch.set_num_threads(2)
    checkpoint=torch.load(model_path,map_location='cpu',weights_only=True)
    names=checkpoint['feature_names'];frame=pd.read_parquet(source)
    if set(frame.columns)!={'row_id',*names} or not frame.row_id.is_unique:raise ValueError('Explicit feature contract changed')
    weights={k:v.detach().cpu().numpy() for k,v in checkpoint['model_state'].items()}
    if set(weights)!={'0.weight','0.bias','2.weight','2.bias'}:raise ValueError('Unexpected pilot architecture')
    raw=frame[names].to_numpy(dtype=np.float32);missing=~np.isfinite(raw)
    mean=np.asarray(checkpoint['impute_mean'],dtype=np.float32);sd=np.asarray(checkpoint['standard_deviation'],dtype=np.float32)
    X=np.concatenate([(np.where(missing,mean,raw)-mean)/sd,missing.astype(np.float32)],axis=1).astype(np.float32)
    hidden=np.maximum(X@weights['0.weight'].T+weights['0.bias'],np.float32(0))
    logits=(hidden@weights['2.weight'].T+weights['2.bias']).ravel()
    probabilities=np.float32(1)/(np.float32(1)+np.exp(-logits))
    model=torch.nn.Sequential(torch.nn.Linear(len(names)*2,16),torch.nn.ReLU(),torch.nn.Linear(16,1));model.load_state_dict(checkpoint['model_state'],strict=True);model.eval()
    with torch.inference_mode():expected=torch.sigmoid(model(torch.from_numpy(X)).squeeze(1)).numpy()
    error=float(np.max(np.abs(probabilities-expected)))
    if error>1e-6 or not np.isfinite(probabilities).all():raise ValueError('Portable numpy inference differs')
    output=pd.DataFrame(dict(row_id=frame.row_id,probability=probabilities));output.to_parquet(out/'probabilities.parquet',index=False)
    bundle=dict(schema_version=1,architecture=[28,16,1],feature_names=names,impute_mean=mean.tolist(),standard_deviation=sd.tolist(),weights={k:v.tolist() for k,v in weights.items()},configuration=checkpoint['configuration'],source_model_sha256=sha(model_path))
    save(out/'portable_gate.json',bundle)
    result=dict(status='completed_fixed_model_feature_inference',rows=len(frame),model_sha256=sha(model_path),features_sha256=sha(source),probabilities_sha256=sha(out/'probabilities.parquet'),portable_gate_sha256=sha(out/'portable_gate.json'),torch_numpy_max_abs_error=error,labels_read=False,reference_conditions_read=False,new_training=False,source_script_sha256=sha(__file__))
    save(out/'verification.json',result);print(json.dumps(result))

if __name__=='__main__':main()
