"""Read-only frozen checkpoint/data binding and actual feature inference audit."""
from pathlib import Path
import json
import sys
from collections import Counter
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import torch
from isomer_residual_head_20261109 import CandidateMultiSpectrumHead
from train_candidate_multispectrum_head import batch, sha, write

SOURCE = ROOT/'runs/candidate_head_20261108'
OUT = ROOT/'runs/isomer_head_20261109'
PINS = {
    'head_seed20261109_step2500.pt':'47fdbb171bf54f6a25fc7d720fc28e14e5c915eccbc585dde66b7c7b68db42eb',
    'head_seed20261110_step2500.pt':'4c020ea62400188c273fb2bf29fc5187d6553a54e784dd26882291bd2f0aa4ca',
}


def main():
    torch.set_num_threads(4)
    recipe = json.loads((OUT/'recipe_frozen_before_training.json').read_text())
    old_export = json.loads((SOURCE/'export_receipt.json').read_text())
    summary = json.loads((OUT/'summary.json').read_text())
    rows = torch.load(SOURCE/'head_features.pt',weights_only=True,map_location='cpu')
    checks = dict(feature_cache_binding=sha(SOURCE/'head_features.pt')==recipe['feature_cache_sha256']==old_export['features_sha256'],
        candidate_formula_binding=sha(SOURCE/'candidate_catalog.parquet')==recipe['candidate_catalog_sha256'],
        source_model_binding=sha(ROOT/'scripts/isomer_residual_head_20261109.py')==recipe['model_code_sha256']==summary['model_code_sha256'],
        training_source_binding=sha(ROOT/'scripts/train_isomer_head_20261109.py')==recipe['train_code_sha256']==summary['train_code_sha256'],
        old_seed0_unchanged=sha(SOURCE/'head_seed20261108_step2500.pt')=='99e63aedb420217c817aeaaebd3d09ffa9620824a8d8833dcf55fd90ae903a53',
        old_seed1_unchanged=sha(SOURCE/'head_seed20261109_step2500.pt')=='f29077ca350e48705cec93ed7a9716b2b718e965ba56cec859bb829bf4b7ba75')
    identities = {split:{r['key'] for r in rows if r['split']==split} for split in ('train','monitor','eval')}
    checks['positive_splits_disjoint'] = all(not identities[a]&identities[b] for a,b in [('train','monitor'),('train','eval'),('monitor','eval')])
    heldout = identities['monitor']|identities['eval']
    denied = set(json.loads((SOURCE/'prepare_receipt.json').read_text())['deny_identities'])
    checks['all_candidates_exclude_locked_and_old_panels'] = all(not set(r['candidate_keys'])&denied for r in rows)
    checks['training_positive_negative_exclude_monitor_eval'] = all(not set(r['candidate_keys'])&heldout for r in rows if r['split']=='train')
    checks['eval_recall_unchanged_no_injection'] = sum(r['label']>=0 for r in rows if r['split']=='eval') == 126
    actual = {}
    for filename, expected in PINS.items():
        path = OUT/filename
        weights = torch.load(path,map_location='cpu',weights_only=True)
        checks[filename+'_sha'] = sha(path)==expected
        checks[filename+'_recipe'] = weights['recipe_sha256']==sha(OUT/'recipe_frozen_before_training.json')
        checks[filename+'_encoder'] = weights['encoder_sha256']==recipe['encoder_sha256']
        checks[filename+'_steps'] = weights['step']==2500 and weights['seed'] in (20261109,20261110)
        model = CandidateMultiSpectrumHead(**weights['head_config'])
        model.load_state_dict(weights['state_dict'],strict=True)
        model.eval()
        maximum = 0.;count=0;rr=Counter();top=Counter()
        with torch.inference_mode():
            for row in rows:
                inputs,_ = batch([row],'cpu')
                learned = model(**inputs)[0]
                base = (row['cos']/.1+2*row['fp_score']).mean(0)
                assert learned.shape == base.shape and bool(torch.isfinite(learned).all())
                if learned.numel():
                    maximum = max(maximum,float((learned-base).abs().max()))
                count += len(learned)
                if row['split']=='train' or row['label']<0:continue
                rank = torch.argsort(learned,descending=True,stable=True).tolist().index(row['label'])+1
                if rank<=25:rr[row['split']] += 1/rank
                top[row['split']] += rank==1
        checks[filename+'_bounded_actual_all_rows'] = maximum <= .50001
        receipt = json.loads((OUT/f'training_receipt_seed{weights["seed"]}.json').read_text())
        mon = json.loads((OUT/f'monitor_seed{weights["seed"]}_step2500.json').read_text())
        checks[filename+'_monitor_reproduced'] = abs(rr['monitor']/128-mon['summary']['head_rr'])<1e-12
        checks[filename+'_eval_reproduced'] = abs(rr['eval']/128-receipt['eval']['head_rr'])<1e-12
        actual[filename] = dict(queries=len(rows),candidate_rows=count,max_abs_residual=maximum,
             monitor_mrr25=rr['monitor']/128,eval_mrr25=rr['eval']/128,
             monitor_top1=top['monitor']/128,eval_top1=top['eval']/128,cpu_inference=True)
    report = dict(status='passed' if all(checks.values()) else 'failed',checks=checks,actual_inference=actual,
                  known_pretrained_exposure=True,full_stack_clean_cv=False,locked_query_or_truth_read=False,
                  read_only_checkpoints=True)
    write(OUT/'independent_verification.json',report)
    print(json.dumps(report))
    if report['status']!='passed':raise ValueError('Binding or actual inference audit failed')


if __name__=='__main__':main()
