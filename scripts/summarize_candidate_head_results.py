"""Summarize fixed-budget known-exposure diagnostics without selecting checkpoints."""
from pathlib import Path
import hashlib,json,random
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'runs/candidate_head_20261108'

def ci(details,seed):
 rng=random.Random(seed);d=[r['delta'] for r in details];n=len(d)
 means=sorted(sum(d[rng.randrange(n)] for _ in range(n))/n for _ in range(5000))
 return [means[125],means[4874]]

result={'status':'completed_fixed_budget_two_seed_training','known_pretrained_exposure':True,
 'full_stack_clean_cv':False,'steps_per_seed':2500,'model_parameters':25986,
 'heads':{}}
full=json.loads((OUT/'full_catalog_eval.json').read_text())
for seed in [20261108,20261109]:
 tr=json.loads((OUT/f'training_receipt_seed{seed}.json').read_text())
 bench=json.loads((OUT/f'benchmark500_seed{seed}.json').read_text())
 mon=json.loads((OUT/f'monitor_seed{seed}_step2500.json').read_text())
 ev=full['results'][str(seed)]
 path=OUT/f'head_seed{seed}_step2500.pt'
 actual=hashlib.sha256(path.read_bytes()).hexdigest()
 assert actual==tr['milestones'][-1]['checkpoint_sha256']==ev['checkpoint_sha256']
 result['heads'][str(seed)]={'checkpoint':str(path.relative_to(ROOT)),'sha256':actual,'bytes':path.stat().st_size,
  'benchmark500':bench,'optimization_seconds':tr['optimization_seconds'],'monitor':mon['summary'],
  'monitor_delta_95pct_query_bootstrap':ci(mon['details'],seed),
  'full_catalog_eval':ev['summary'],'eval_delta_95pct_query_bootstrap':ci(ev['details'],seed+1)}
result['interpretation']='Both seeds lose MRR on Monitor and gain on Eval; evaluation retains known full-refit encoder exposure and engineering selection. No stable generalization or leaderboard gain has been established. Budgets/weights were not selected using these metrics.'
(OUT/'summary.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,indent=2))
