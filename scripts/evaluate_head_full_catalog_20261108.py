"""Add back other heldout identities to frozen Eval lists; never change training."""
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import numpy as np
import pyarrow.parquet as pq
import torch
from candidate_multispectrum_head import CandidateMultiSpectrumHead
from train_candidate_multispectrum_head import load_encoder,evaluate,sha,write,POOL
OUT=ROOT/'runs/candidate_head_20261108'
torch.set_num_threads(4)
rows=torch.load(OUT/'head_features.pt',weights_only=True,map_location='cpu')
queries={q['key']:q for q in json.loads((OUT/'queries.json').read_text())}
catalog=pq.read_table(OUT/'candidate_catalog.parquet').to_pylist()
mapping={r['smiles']:r for r in catalog};by_index={r['fp_index']:r for r in catalog}
denied=set(json.loads((OUT/'prepare_receipt.json').read_text())['deny_identities'])
restriction=json.loads((ROOT/'reports/candidate_head_candidate_restriction_audit_20261108.json').read_text())
changes={r['key']:r for r in restriction['rows'] if r['split']=='eval' and r['removed']}
fp=np.load(OUT/'candidate_fingerprints.npy',mmap_mode='r')
arrays=np.load(OUT/'spectra_inputs.npz')
pool=pq.read_table(POOL/'pool_meta.parquet',columns=['smiles','mass']).to_pydict();masses=np.array(pool['mass'])
encoder,cfg=load_encoder('cpu')
full_eval=[];added=0;max_z_difference=0.
with torch.inference_mode():
 for row in rows:
  if row['split']!='eval':continue
  if row['key'] not in changes:full_eval.append(row);continue
  q=queries[row['key']];mass=q['observed_neutral_mass'];lo=np.searchsorted(masses,mass*(1-1e-5));hi=np.searchsorted(masses,mass*(1+1e-5))
  full_indices=[];seen=set()
  for i in range(lo,hi):
   item=mapping.get(pool['smiles'][i])
   if item and item['key'] not in denied|seen:seen.add(item['key']);full_indices.append(item['fp_index'])
  removed={r['key']:r['fp_index'] for r in changes[row['key']]['removed']}
  assert {by_index[i]['key'] for i in full_indices}==set(row['candidate_keys'])|set(removed)
  st,n=q['spectrum_start'],q['spectrum_count']
  z,p=encoder.encode_spectra(torch.tensor(arrays['x'][st:st+n]),torch.tensor(arrays['lengths'][st:st+n]),
    torch.tensor(arrays['meta'][st:st+n]),torch.tensor(arrays['adduct'][st:st+n]))
  max_z_difference=max(max_z_difference,float((z-row['z']).abs().max()))
  missing=list(removed.values());f=torch.tensor(np.array(fp[missing]),dtype=torch.float32);m=encoder.encode_molecules(f)
  cos=row['z']@m.T;fps=p@f.T/cfg['fp_bits'];extra={by_index[index]['key']:j for j,index in enumerate(missing)}
  original={k:i for i,k in enumerate(row['candidate_keys'])}
  value=dict(row);value['candidate_keys']=[by_index[i]['key'] for i in full_indices]
  value['label']=next((i for i,k in enumerate(value['candidate_keys']) if k==row['key']),-1)
  mm=[];cc=[];ff=[]
  for key in value['candidate_keys']:
   if key in original:j=original[key];mm.append(row['m'][j]);cc.append(row['cos'][:,j]);ff.append(row['fp_score'][:,j])
   else:j=extra[key];mm.append(m[j]);cc.append(cos[:,j]);ff.append(fps[:,j]);added+=1
  value['m']=torch.stack(mm).clone();value['cos']=torch.stack(cc,1).clone();value['fp_score']=torch.stack(ff,1).clone()
  # Persist normal tensors, not tensors created in inference_mode.
  full_eval.append(value)
del encoder
results={}
for seed in [20261108,20261109]:
 path=OUT/f'head_seed{seed}_step2500.pt';before=sha(path);checkpoint=torch.load(path,weights_only=True,map_location='cpu')
 model=CandidateMultiSpectrumHead(**checkpoint['head_config']);model.load_state_dict(checkpoint['state_dict'])
 summary,details=evaluate(model,full_eval,'cpu');assert sha(path)==before
 results[str(seed)]=dict(summary=summary,details=details,checkpoint_sha256=before)
report=dict(status='passed',evaluation_scope='same frozen128 Eval identities, candidate lists include other Eval/Monitor identities; frozen700 deny identities remain excluded',
 affected_queries=len(changes),added_candidates=added,encoder_max_abs_z_cpu_gpu_difference=max_z_difference,
 training_and_checkpoint_unchanged=True,known_pretrained_exposure=True,results=results)
write(OUT/'full_catalog_eval.json',report)
print(json.dumps({k:v for k,v in report.items() if k!='results'}))
for seed,result in results.items():print(json.dumps({'seed':seed,'summary':result['summary']}))
