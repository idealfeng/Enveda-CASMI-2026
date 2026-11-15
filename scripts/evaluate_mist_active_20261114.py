"""Score frozen MIST predictions only after inference, on the declared active subset."""
from pathlib import Path
from collections import Counter
import csv
import hashlib
import json
import random
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from validation import metric

def read_csv(p):
    with Path(p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    metric.assert_official_rdkit()
    work=ROOT/'runs/mist_active_evaluation_20261114'
    control=work/'control_candidates.csv';prediction=work/'inference/submission_mist_component.csv'
    proof=json.loads((work/'inference/verification.json').read_text())
    if proof['status']!='passed_actual_mist_casmi_component' or sha(prediction)!=proof['output_csv_sha256']:
        raise ValueError('Predictions not bound to completed actual inference')
    old=read_csv(control);new=read_csv(prediction)
    if [r['molecule_id'] for r in old]!=[r['molecule_id'] for r in new]:raise ValueError('Query order changed')
    truth={r['molecule_id']:r for r in read_csv(ROOT/'runs/validation_pilot_v2_20261104/truth.csv')}
    rows=[]
    for a,b in zip(old,new):
        mid=a['molecule_id'];left=a['smiles'].split(';');right=b['smiles'].split(';')
        if Counter(left)!=Counter(right):raise ValueError('Fixed candidate multiset violated')
        if any(metric.molecular_formula(x)!=metric.molecular_formula(y) for x,y in zip(left,right)):
            raise ValueError('Original same-formula slots violated')
        key=truth[mid]['official_identity']
        r0=metric.first_correct_rank(key,left);r1=metric.first_correct_rank(key,right)
        before=0. if r0 is None else 1/r0;after=0. if r1 is None else 1/r1
        rows.append(dict(molecule_id=mid,panel=truth[mid]['panel'],control_rank=r0,mist_rank=r1,
                         control_rr=before,mist_rr=after,delta=after-before,
                         candidate_truth_recalled=r0 is not None,top1_changed=left[0]!=right[0]))
    n=len(rows);deltas=[r['delta'] for r in rows];rng=random.Random(20261114)
    samples=sorted(sum(rng.choices(deltas,k=n))/n for _ in range(10000))
    result=dict(status='completed_post_inference_component_evaluation',queries=n,
        control_mrr25=sum(r['control_rr'] for r in rows)/n,mist_mrr25=sum(r['mist_rr'] for r in rows)/n,
        delta_mrr25=sum(deltas)/n,paired_bootstrap95=[samples[250],samples[9749]],
        control_top1=sum(r['control_rank']==1 for r in rows)/n,mist_top1=sum(r['mist_rank']==1 for r in rows)/n,
        candidate_recall=sum(r['candidate_truth_recalled'] for r in rows)/n,
        improved=sum(d>0 for d in deltas),worsened=sum(d<0 for d in deltas),unchanged=sum(d==0 for d in deltas),
        panel_counts=dict(Counter(r['panel'] for r in rows)),rows=rows,
        control_sha256=sha(control),prediction_sha256=sha(prediction),actual_model_sha256=proof['checkpoint_sha256'],
        no_parameter_search=True,new_training=False,public_score=None,exact_champion_parent=False,
        exposure='Outside all MSG train/val/test known raw identity families; unlisted tautomer aliases remain possible. Existing baseline models have known pretrained exposure.',
        boundary='17 existing exposed-development cross-library queries and old Flex candidate lists, not exact .488 CV or hidden-test gain. Inference did not consume truth; labels read only in this post-hoc fixed-policy evaluation.')
    out=ROOT/'reports/mist_evaluation_20261114';out.mkdir(parents=True,exist_ok=True)
    (out/'fixed_policy_evaluation.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['status','queries','control_mrr25','mist_mrr25','delta_mrr25','paired_bootstrap95','control_top1','mist_top1','candidate_recall','improved','worsened']}))

if __name__=='__main__':main()
