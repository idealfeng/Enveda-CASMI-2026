"""Independent cache/label contract audit; no model or dev predictions loaded."""
from pathlib import Path
from collections import Counter
import ast,hashlib,json,sys,time
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'assets/research/fiora_os_20261115/source_checkout'
TARGET=ROOT/'assets/research/fiora_os_20261115/dependencies-linux'
DATA=ROOT/'runs/fiora_tims_pilot_20261115'
sys.path[:0]=[str(SOURCE),str(TARGET),str(ROOT)]
started=time.perf_counter()
import numpy as np
import torch
torch.set_num_threads(1)
def sha(p):
    with Path(p).open('rb') as h:return hashlib.file_digest(h,'sha256').hexdigest()
index=json.loads((DATA/'index.json').read_text());selection=json.loads((DATA/'selection.json').read_text())
if index['status']!='completed_native_graph_and_label_cache':raise ValueError('Cache not complete')
if index['selection_sha256']!=sha(DATA/'selection.json'):raise ValueError('Selection changed')
ready=[r for r in index['rows'] if r['status']=='cache_ready']
counts=Counter();issues=[]
for row in ready:
    gp=DATA/row['graph_path'];ep=DATA/row['eval_path']
    if sha(gp)!=row['graph_sha256'] or sha(ep)!=row['eval_sha256']:raise ValueError('Frozen cache file changed')
    g=torch.load(gp,map_location='cpu',weights_only=True);y=g['compiled_probsALL']
    if not torch.isfinite(y).all() or (y<0).any() or y.sum()<=0:issues.append(dict(spectrum_id=row['spectrum_id'],issue='invalid_target'))
    if y[:-2].sum()<=0:issues.append(dict(spectrum_id=row['spectrum_id'],issue='zero_nonprecursor_target'))
    if g['static_graph_features'].shape[-1]!=19 or not torch.equal(g['static_graph_features'][0,6:9],torch.tensor([0.,1.,0.])):issues.append(dict(spectrum_id=row['spectrum_id'],issue='instrument_encoding'))
    forbidden={'official_identity','raw_key','source_row','split','query_mz','query_intensity','compiled_mz'}
    if forbidden&set(g):issues.append(dict(spectrum_id=row['spectrum_id'],issue='metadata_in_graph_features'))
    with np.load(ep,allow_pickle=False) as z:
        mz=z['compiled_mz'];mask=z['compiled_forward_mask'].astype(bool);qm=z['query_mz'];qi=z['query_intensity'];prec=float(z['precursor_mz'][0])
        if len(mz)!=y.numel() or mask.shape!=mz.shape:issues.append(dict(spectrum_id=row['spectrum_id'],issue='mass_target_shape'))
        forward=np.repeat((g['edge_index'][0]<g['edge_index'][1]).numpy(),10)&np.isfinite(mz[:-2])
        if not np.array_equal(mask,np.r_[forward,False,True]):issues.append(dict(spectrum_id=row['spectrum_id'],issue='forward_ring_or_precursor_mask'))
        qnp=np.abs(qm-prec)>max(abs(prec)*.0001,.01)
        if not np.array_equal(z['query_nonprecursor_mask'],qnp):issues.append(dict(spectrum_id=row['spectrum_id'],issue='query_nonprecursor_mask'))
        if not (mz[-1]==prec and mz[-2]==prec):issues.append(dict(spectrum_id=row['spectrum_id'],issue='duplicate_precursor_mass'))
    counts[row['split']+'_ready']+=1
    counts['validated_graphs']+=1
# Exact value/gradient parity using extracted frozen source, no model scores.
loss_path=SOURCE/'fiora/GNN/Losses.py'
node=next(x for x in ast.parse(loss_path.read_text()).body if isinstance(x,ast.ClassDef) and x.name=='GraphwiseKLLoss')
namespace={'torch':torch};exec(compile(ast.Module(body=[node],type_ignores=[]),str(loss_path),'exec'),namespace)
trainer=ROOT/'scripts/train_fiora_tims_500_20261115.py'
fn=next(x for x in ast.parse(trainer.read_text()).body if isinstance(x,ast.FunctionDef) and x.name=='graphwise_kl')
scope={'TORCH':torch};exec(compile(ast.Module(body=[fn],type_ignores=[]),str(trainer),'exec'),scope)
q=torch.tensor([.1,.2,.7,.4,.6],dtype=torch.float64);target=torch.tensor([0.,2.,1.,5.,0.],dtype=torch.float64);ptr=torch.tensor([0,3,5])
q1=q.clone().requires_grad_();q2=q.clone().requires_grad_()
l1=namespace['GraphwiseKLLoss']()(q1,target,ptr);l2=scope['graphwise_kl'](q2,target,ptr);l1.backward();l2.backward()
parity=bool(torch.equal(l1,l2) and torch.equal(q1.grad,q2.grad))
if not parity:issues.append(dict(issue='native_loss_value_or_gradient_differs'))
result=dict(status='passed_independent_native_supervision_contract' if not issues else 'failed',counts=dict(counts),issues=issues,original_selected_denominator=len(selection['groups']),zero_nonprecursor_targets=sum(x.get('issue')=='zero_nonprecursor_target' for x in issues),all_ready_examined=len(ready)==counts['validated_graphs'],native_graphwise_kl_value_gradient_exact=parity,selection_sha256=sha(DATA/'selection.json'),index_sha256=sha(DATA/'index.json'),preparer_source_sha256=sha(ROOT/'scripts/prepare_fiora_tims_pilot_20261115.py'),trainer_source_sha256=sha(trainer),model_loaded=False,development_model_scores_read=False,training_performed=False,seconds=time.perf_counter()-started)
out=ROOT/'reports/new_paradigm_20261115/fiora_graph_target_contract_review.json'
if out.exists():raise FileExistsError('Preserve prior audit')
out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if issues:raise ValueError('Cache target contract audit failed')
