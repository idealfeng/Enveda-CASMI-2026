"""Localize input variation through one fixed official-native MIST batch."""
from pathlib import Path
import hashlib
import json
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
SITE=ROOT/'.cache/rdkit-official-linux-2026033'
sys.path.insert(0,str(SITE));sys.path.insert(0,str(ROOT/'assets/research/mist_msg_20261114/source/src'))

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    import numpy as np
    import torch
    from mist.models.scaled_mist import ScaledMIST
    torch.set_num_threads(4);torch.manual_seed(0)
    if not torch.cuda.is_available():raise RuntimeError('Expected available bounded GPU canary')
    device=torch.device('cuda')
    parent=ROOT/'runs/mist_fingerprint_audit_20261115/native_val/part_00000'
    n=len(np.load(parent/'lengths.npy',mmap_mode='r',allow_pickle=False))
    indices=np.linspace(0,n-1,16,dtype=np.int64)
    mapping=dict(form_vec='form_vec',ion_vec='ion_vec',intens='intens',types='peak_type',num_peaks='lengths',instruments='instruments')
    batch={}
    for target,source in mapping.items():
        raw=np.load(parent/(source+'.npy'),mmap_mode='r',allow_pickle=False)
        dtype=np.float32 if target in ('form_vec','intens') else np.int64
        batch[target]=torch.from_numpy(np.array(raw[indices],dtype=dtype)).to(device)
    cls=batch['types']==3
    if not torch.all(cls.sum(1)==1):raise ValueError('Invalid native CLS')
    path=ROOT/'assets/research/mist_msg_20261114/checkpoints/mist_msg_noaug.ckpt'
    pin=sha(path)
    if pin!='6f8df582df36aa4a984f120efee14ee0a62f3a7723caa770b856a6e704236727':raise ValueError('Wrong fixed checkpoint')
    ckpt=torch.load(path,map_location='cpu',weights_only=True)
    model=ScaledMIST(**ckpt['config']['model']);model.load_state_dict(ckpt['ema_model'],strict=True);model.to(device).eval()
    def stats(t):
        value=t.detach().float()
        return dict(shape=list(value.shape),mean_abs=float(value.abs().mean()),max_abs=float(value.abs().max()),
                    mean_std_across_samples=float(value.std(dim=0,unbiased=False).mean()),
                    maximum_difference_from_first_sample=float((value-value[:1]).abs().max()),
                    finite=bool(torch.isfinite(value).all()),minimum=float(value.min()),maximum=float(value.max()),
                    fraction_below_1e_6=float((value<1e-6).float().mean()),fraction_above_1_minus_1e_6=float((value>1-1e-6).float().mean()))
    observations={};hooks=[]
    observations['input_cls_formula']=stats(batch['form_vec'][cls])
    observations['input_intensity']=stats(batch['intens'])
    def capture(name,mode):
        def hook(module,args,result):
            if isinstance(result,tuple):result=result[0]
            if mode=='sequence_first':result=result.transpose(0,1)[cls]
            elif mode=='batch_sequence':result=result[cls]
            observations[name]=stats(result)
        return hook
    hooks.append(model.encoder.intermediate_layer.register_forward_hook(capture('encoder.stem_cls','batch_sequence')))
    for i,layer in enumerate(model.encoder.peak_attn_layers):
        hooks.append(layer.register_forward_hook(capture(f'encoder.attention_{i}_cls','sequence_first')))
    hooks.append(model.encoder.register_forward_hook(capture('encoder.pooled','plain')))
    hooks.append(model.decoder.initial_predict[0].register_forward_hook(capture('decoder.initial_logits','plain')))
    hooks.append(model.decoder.initial_predict.register_forward_hook(capture('decoder.initial_probabilities','plain')))
    for i,brick in enumerate(model.decoder.gate_bricks):
        hooks.append(brick[0].register_forward_hook(capture(f'decoder.gate_{i}_logits','plain')))
        hooks.append(brick.register_forward_hook(capture(f'decoder.gate_{i}_probabilities','plain')))
    for i,brick in enumerate(model.decoder.predict_bricks):
        hooks.append(brick.register_forward_hook(capture(f'decoder.predict_{i}_probabilities','plain')))
    started=time.monotonic()
    with torch.inference_mode():output,aux=model(batch)
    torch.cuda.synchronize();seconds=time.monotonic()-started
    observations['final_fingerprint']=stats(output)
    for h in hooks:h.remove()
    out=ROOT/'reports/mist_contract_audit_20261115';out.mkdir(exist_ok=True,parents=True)
    result=dict(status='completed_one_native_batch_layer_hooks',checkpoint_sha256=pin,checkpoint_step=ckpt.get('step'),
                source_checkpoint_sha256=ckpt.get('source_checkpoint_sha256'),native_val_indices=indices.tolist(),
                device=str(device),forward_seconds=seconds,observations=observations,
                training_performed=False,source_modified=False,hyperparameters_searched=False,
                boundary='One actual native MSG validation batch, fixed first-party release and model source. Layer-hook localization only, not a CASMI evaluation or corrected model.')
    (out/'layer_contraction.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=result['status'],forward_seconds=seconds,layer_std={k:v['mean_std_across_samples'] for k,v in observations.items()})))

if __name__=='__main__':main()
