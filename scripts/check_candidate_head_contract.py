"""Numerical contracts of the new candidate-conditioned head, using synthetic tensors."""
import json
from pathlib import Path
import torch
from candidate_multispectrum_head import CandidateMultiSpectrumHead

torch.manual_seed(20261108)
torch.set_num_threads(4)
b,s,c,d=3,4,7,192
data=dict(z=torch.nn.functional.normalize(torch.randn(b,s,d),dim=-1),
          m=torch.nn.functional.normalize(torch.randn(b,c,d),dim=-1),
          cos=torch.randn(b,s,c),fp_score=torch.randn(b,s,c),metadata=torch.randn(b,s,4),
          adduct=torch.randint(0,11,(b,s)),peak_fraction=torch.rand(b,s),
          spectrum_mask=torch.tensor([[True,False,False,False],[True,True,False,False],[True,True,True,True]]))
head=CandidateMultiSpectrumHead()
base=data['cos']/.1+2*data['fp_score']
expected=(base*data['spectrum_mask'][...,None]).sum(1)/data['spectrum_mask'].sum(1)[:,None]
actual=head(**data)
checks={'zero_residual_reproduces_original_mean':bool(torch.allclose(actual,expected,atol=3e-6,rtol=1e-6)),
        'parameter_count_under_30000':sum(p.numel() for p in head.parameters())<30000}
with torch.no_grad():
 head.network[-1].weight.normal_(0,.01)
 original=head(**data)
 changed={k:v.clone() for k,v in data.items()}
 for k in ['z','metadata','adduct','peak_fraction']:
  changed[k][0,1:]=0
 for k in ['cos','fp_score']:changed[k][0,1:]=123.
 checks['masked_spectra_do_not_change_output']=bool(torch.allclose(original[0],head(**changed)[0],atol=1e-6))
 permutation=torch.tensor([6,0,5,1,4,2,3])
 permuted=dict(data);permuted['m']=data['m'][:,permutation]
 for k in ['cos','fp_score']:permuted[k]=data[k][:,:,permutation]
 checks['candidate_permutation_equivariant']=bool(torch.allclose(original[:,permutation],head(**permuted),atol=1e-6))
 extra=dict(data);extra['m']=torch.cat([data['m'],torch.randn(b,2,d)],1)
 for k in ['cos','fp_score']:extra[k]=torch.cat([data[k],torch.randn(b,s,2)],2)
 checks['adding_candidates_does_not_rescale_originals']=bool(torch.allclose(original,head(**extra)[:,:c],atol=1e-6))
head.zero_grad();loss=torch.nn.functional.cross_entropy(head(**data),torch.zeros(b,dtype=torch.long));loss.backward()
checks['finite_loss_and_gradients']=bool(torch.isfinite(loss) and all(torch.isfinite(p.grad).all() for p in head.parameters() if p.grad is not None))
checks['nonzero_learning_gradient']=any(bool(p.grad.abs().sum()>0) for p in head.parameters() if p.grad is not None)
checks['score_is_candidate_conditional']=bool(original.std(1).min()>0)
assert all(checks.values()),checks
report=dict(status='passed',checks=checks,parameters=sum(p.numel() for p in head.parameters()),
            max_zero_error=float((actual-expected).abs().max()))
out=Path(__file__).resolve().parents[1]/'reports/candidate_head_contract_20261108.json'
out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report))
