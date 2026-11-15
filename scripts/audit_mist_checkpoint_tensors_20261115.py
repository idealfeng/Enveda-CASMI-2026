"""Read verified MIST checkpoint tensor dispersion; no forward or training."""
from pathlib import Path
import hashlib,json,os,time
import torch

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'assets/research/mist_msg_20261114/checkpoints/mist_msg_noaug.ckpt'
OUT=ROOT/'reports/mist_fingerprint_audit_20261115/checkpoint_tensors.json'

def main():
    torch.set_num_threads(4);start=time.monotonic()
    pin=hashlib.sha256(P.read_bytes()).hexdigest()
    if pin!='6f8df582df36aa4a984f120efee14ee0a62f3a7723caa770b856a6e704236727':raise ValueError('Checkpoint changed')
    ckpt=torch.load(P,map_location='cpu',weights_only=True);rows=[]
    for name,value in ckpt['ema_model'].items():
        a=value.float();n=a.numel()
        rows.append(dict(name=name,shape=list(a.shape),elements=n,finite=bool(a.isfinite().all()),
                         min=float(a.min()),max=float(a.max()),mean=float(a.mean()),
                         std=float(a.std(unbiased=False)),l2=float(a.norm()),
                         all_zero=bool((a==0).all()),zeros=int((a==0).sum())))
    result=dict(status='completed_read_only_checkpoint_tensor_audit',checkpoint_sha256=pin,
                checkpoint_step=ckpt.get('step'),checkpoint_kind=ckpt.get('checkpoint_kind'),
                source_checkpoint_sha256=ckpt.get('source_checkpoint_sha256'),
                tensors=len(rows),all_zero_tensors=[r['name'] for r in rows if r['all_zero']],
                tensor_stats=rows,seconds=time.monotonic()-start,model_forward_executed=False,new_training=False)
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(status=result['status'],all_zero_tensors=result['all_zero_tensors'],seconds=result['seconds'])))

if __name__=='__main__':main()
