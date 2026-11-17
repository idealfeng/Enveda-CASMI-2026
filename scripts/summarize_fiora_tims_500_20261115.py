"""Summarize fixed pilot paired spectrum changes, without changing a model."""
from pathlib import Path
import hashlib
import json
import random
import statistics

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'runs/fiora_tims_model_20261115/pilot500'
OUT=ROOT/'reports/new_paradigm_20261115/tims500_paired_evaluation.json'

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

proof=read(RUN/'verification.json')
if proof['status']!='completed_fixed500_real_fiora_graphwise_kl' or proof['optimizer_steps']!=500:
    raise ValueError('No completed500-step model')
if sha(RUN/'last_checkpoint.pt')!=proof['checkpoint_sha256']:raise ValueError('Final checkpoint changed')
a,b=[read(RUN/f'development_step{n:03d}.json') for n in (0,500)]
old={r['official_identity']:r for r in a['rows']};new={r['official_identity']:r for r in b['rows']}
if old.keys()!=new.keys() or len(old)!=98:raise ValueError('Frozen development scope differs')
rows=[]
for key in old:
    before=old[key]['physical_sqrt_spectral_cosine_without_precursor']
    after=new[key]['physical_sqrt_spectral_cosine_without_precursor']
    rows.append(dict(official_identity=key,before=before,after=after,delta=after-before,
                     kl_before=old[key]['kl'],kl_after=new[key]['kl']))
delta=[r['delta'] for r in rows]+[0.,0.]
rng=random.Random(20261115)
boot=sorted(sum(rng.choices(delta,k=100))/100 for _ in range(10000))
result=dict(status='completed_paired_forward_spectrum_development_analysis',
    optimizer_steps=500,checkpoint_sha256=proof['checkpoint_sha256'],
    step0_prediction_sha256=sha(RUN/'development_step000.json'),step500_prediction_sha256=sha(RUN/'development_step500.json'),
    original_development_identities=100,evaluated_identities=98,zero_fragment_unusable_identities=2,
    metric='actual reconstructed m/z sqrt spectral cosine without precursor; native adjacent-bin chaining, 0.01Da; unscored two queries count zero in both arms',
    before= sum(r['before'] for r in rows)/100,after=sum(r['after'] for r in rows)/100,
    delta=sum(delta)/100,paired_bootstrap95=[boot[249],boot[9749]],bootstrap_samples=10000,bootstrap_seed=20261115,
    improved=sum(r['delta']>1e-8 for r in rows),worsened=sum(r['delta'] < -1e-8 for r in rows),
    unchanged_usable=sum(abs(r['delta'])<=1e-8 for r in rows),
    median_usable_delta=statistics.median(r['delta'] for r in rows),rows=rows,
    new_public_score=None,candidate_ranking_mrr=None,clean_pretraining_holdout=False,
    decision_boundary='Paired spectrum fidelity on a fixed small-molecule single-CE tims panel, not candidate rank improvement or Kaggle efficacy. No threshold, checkpoint or hyperparameter selected by this analysis.')
OUT.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='rows'}))
