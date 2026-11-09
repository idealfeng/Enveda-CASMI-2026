"""Fixed two-seed same-formula listwise training on already frozen features.

This is a known-pretrained-exposure component diagnostic, not clean full-stack
validation. Never reads locked250, old48, hidden test labels, or the leaderboard.
"""
from __future__ import annotations
import json
from pathlib import Path
import random
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import numpy as np
import pyarrow.parquet as pq
import torch
from isomer_residual_head_20261109 import CandidateMultiSpectrumHead, head_config
from train_candidate_multispectrum_head import batch, evaluate, sha, write, CKPT_SHA

SOURCE = ROOT / 'runs/candidate_head_20261108'
OUT = ROOT / 'runs/isomer_head_20261109'
SEEDS = (20261109, 20261110)
STEPS = 2500
RECIPE = dict(steps=STEPS, seeds=list(SEEDS), batch_size=16, learning_rate=2e-4,
              weight_decay=.01, gradient_clip=5., residual_bound=.5,
              primary='cross entropy restricted to target molecular formula only',
              primary_weight=1., margin_anchor_weight=.5,
              margin_anchor='mean squared change of candidate-minus-positive pretrained mean score margins over full retrieved list',
              residual_center_weight=.1,
              residual_center='squared query-mean residual, prevents uninformative global offsets',
              selection='fixed recipe, seeds, checkpoint budget, and equal-seed ensemble declared before training; no outcome-driven selection')


def masked_mean_base(data):
    weight = data['spectrum_mask'].to(data['cos'].dtype)
    weight = weight / weight.sum(1, keepdim=True).clamp_min(1)
    return ((data['cos']/.1 + 2*data['fp_score'])*weight[..., None]).sum(1)


def prepare():
    if OUT.exists():
        raise FileExistsError('Frozen run already exists; never overwrite trained artifacts')
    OUT.mkdir()
    catalog = pq.read_table(SOURCE/'candidate_catalog.parquet').to_pylist()
    formulas = defaultdict(set)
    for item in catalog:
        formulas[item['key']].add(item['formula'])
    rows = torch.load(SOURCE/'head_features.pt', map_location='cpu', weights_only=True)
    for row in rows:
        candidates = row['candidate_keys']
        if any(len(formulas[key]) != 1 for key in candidates):
            raise ValueError('Missing or ambiguous candidate formula')
        row['candidate_formulas'] = [next(iter(formulas[key])) for key in candidates]
        positive = row['label']
        if positive >= 0:
            positive_formula = row['candidate_formulas'][positive]
            row['same_formula'] = torch.tensor([value == positive_formula for value in row['candidate_formulas']])
        else:
            row['same_formula'] = torch.zeros(len(candidates), dtype=torch.bool)
    assert Counter(row['split'] for row in rows) == {'train':1024, 'monitor':128, 'eval':128}
    assert all(row['label'] == 0 for row in rows if row['split'] == 'train')
    receipt = dict(status='frozen_before_training', created_at_utc=datetime.now(timezone.utc).isoformat(),
                   recipe=RECIPE, feature_cache_sha256=sha(SOURCE/'head_features.pt'),
                   candidate_catalog_sha256=sha(SOURCE/'candidate_catalog.parquet'),
                   old_prepare_receipt_sha256=sha(SOURCE/'prepare_receipt.json'),
                   old_export_receipt_sha256=sha(SOURCE/'export_receipt.json'),
                   encoder_sha256=CKPT_SHA, model_code_sha256=sha(ROOT/'scripts/isomer_residual_head_20261109.py'),
                   train_code_sha256=sha(__file__), splits=dict(Counter(row['split'] for row in rows)),
                   same_formula_eligible={split:sum(row['split']==split and int(row['same_formula'].sum())>=2 for row in rows) for split in ('train','monitor','eval')},
                   known_pretrained_exposure=True, locked_queries_or_truth_read=False,
                   all_features_reused=True, new_external_data=False,
                   original_candidate_restrictions='Inherited engineering candidate restriction removes other Monitor/Eval identities, documented in original run; not full-catalog clean CV',
                   inherited_eval_retrieval='126/128 true structures retrieved; no Eval injection')
    write(OUT/'recipe_frozen_before_training.json', receipt)
    return rows, receipt


def formula_mask(sample, width, device):
    values = torch.zeros(len(sample), width, dtype=torch.bool, device=device)
    for i, row in enumerate(sample):
        values[i, :len(row['m'])] = row['same_formula'].to(device)
    return values


def diagnostic(model, rows, device):
    summary, details = evaluate(model, rows, device)
    by_key = {item['key']:item for item in details}
    formula_rr = base_formula_rr = 0.
    guarded_rr = base_rr = 0.
    tail_changes = 0
    delta_values = []
    model.eval()
    with torch.inference_mode():
        for row in rows:
            data, _ = batch([row], device)
            head = model(**data)[0].cpu()
            base = masked_mean_base(data)[0].cpu()
            delta_values.extend((head-base).tolist())
            label = row['label']
            # Truth-free guarded reordering of base ranks8..25, same-formula slots.
            order = torch.argsort(base, descending=True, stable=True).tolist()
            guarded = list(order)
            slots = defaultdict(list)
            for pos in range(7, min(25, len(order))):
                slots[row['candidate_formulas'][order[pos]]].append(pos)
            for positions in slots.values():
                proposed = sorted((order[pos] for pos in positions), key=lambda i:(-float(head[i]), order.index(i)))
                for pos, index in zip(positions, proposed):
                    guarded[pos] = index
            assert guarded[:7] == order[:7] and sorted(guarded) == sorted(order)
            tail_changes += guarded != order
            if label < 0:
                continue
            base_rank = order.index(label)+1
            guarded_rank = guarded.index(label)+1
            bv = 1/base_rank if base_rank <= 25 else 0.
            gv = 1/guarded_rank if guarded_rank <= 25 else 0.
            base_rr += bv
            guarded_rr += gv
            indices = torch.where(row['same_formula'])[0].tolist()
            base_formula_rank = sorted(indices, key=lambda i:(-float(base[i]), i)).index(label)+1
            head_formula_rank = sorted(indices, key=lambda i:(-float(head[i]), i)).index(label)+1
            base_formula_rr += 1/base_formula_rank if base_formula_rank <= 25 else 0.
            formula_rr += 1/head_formula_rank if head_formula_rank <= 25 else 0.
            by_key[row['key']].update(base_formula_rank=base_formula_rank, head_formula_rank=head_formula_rank,
                                      guarded_rank=guarded_rank, guarded_delta=gv-bv)
    n = len(rows)
    summary.update(base_same_formula_mrr25=base_formula_rr/n, head_same_formula_mrr25=formula_rr/n,
                   base_neural_guard_control_mrr25=base_rr/n, guarded_neural_tail_mrr25=guarded_rr/n,
                   guarded_changed_queries=tail_changes,
                   max_abs_residual=max(abs(value) for value in delta_values),
                   residual_mean=float(np.mean(delta_values)),
                   guarded_scope='same-formula rank8..25 of neural baseline, NOT the full MASS output')
    rng = np.random.default_rng(991109)
    diffs = np.array([item['delta'] for item in details])
    bootstrap = diffs[rng.integers(0, n, size=(10000,n))].mean(1)
    summary['head_mrr_delta_bootstrap95'] = np.quantile(bootstrap,[.025,.975]).tolist()
    return dict(summary=summary, details=details, known_pretrained_exposure=True,
                full_stack_clean_cv=False, eval_truth_injected=False)


def contract_check():
    head = CandidateMultiSpectrumHead(**head_config())
    generator = torch.Generator().manual_seed(1109)
    z = torch.randn(2,3,192,generator=generator)
    m = torch.randn(2,5,192,generator=generator)
    cos = torch.randn(2,3,5,generator=generator)
    fps = torch.rand(2,3,5,generator=generator)
    data = dict(z=z,m=m,cos=cos,fp_score=fps,metadata=torch.randn(2,3,4,generator=generator),
                adduct=torch.zeros(2,3,dtype=torch.long),peak_fraction=torch.ones(2,3),
                spectrum_mask=torch.tensor([[True,True,True],[True,True,False]]))
    base = masked_mean_base(data)
    zero_error = float((head(**data)-base).abs().max())
    assert zero_error < 3e-6
    torch.nn.init.normal_(head.network[-1].weight, std=.2)
    result = head(**data)
    assert float((result-base).abs().max()) <= .50001
    permutation = torch.tensor([3,0,4,1,2])
    pd = dict(data,m=m[:,permutation],cos=cos[:,:,permutation],fp_score=fps[:,:,permutation])
    assert torch.allclose(head(**pd),result[:,permutation],atol=2e-6)
    cropped = dict(data,m=m[:,:3],cos=cos[:,:,:3],fp_score=fps[:,:,:3])
    assert torch.allclose(head(**cropped), result[:,:3], atol=2e-6)
    padded = {key:value.clone() for key,value in data.items()}
    for key in ('z','cos','fp_score','metadata','peak_fraction'):
        padded[key][1,2] = 100
    assert torch.allclose(head(**padded)[1],result[1],atol=2e-6)
    write(OUT/'model_contract.json',dict(status='passed', zero_residual_mean_max_error=zero_error,
          candidate_permutation=True,candidate_subset=True,masked_spectrum_padding=True,
          residual_bound=.5, fixed_spectrum_uniform_mean=True))


def train(rows, recipe_receipt, device, seed):
    torch.manual_seed(seed)
    random.seed(seed)
    np.random.seed(seed)
    training = [row for row in rows if row['split']=='train']
    monitor = [row for row in rows if row['split']=='monitor']
    evaluation = [row for row in rows if row['split']=='eval']
    head = CandidateMultiSpectrumHead(**head_config()).to(device)
    optimizer = torch.optim.AdamW(head.parameters(),lr=RECIPE['learning_rate'],weight_decay=RECIPE['weight_decay'])
    generator = random.Random(seed)
    times, losses, gradients, components = [], [], [], []
    started = time.monotonic()
    if device=='cuda': torch.cuda.reset_peak_memory_stats()
    milestones = []
    for step in range(1,STEPS+1):
        t = time.monotonic()
        head.train()
        sample = generator.sample(training, RECIPE['batch_size'])
        data, candidate_mask = batch(sample, device)
        scores = head(**data)
        base = masked_mean_base(data)
        same_formula = formula_mask(sample, scores.shape[1], device)
        eligible = same_formula.sum(1)>=2
        per_query = torch.nn.functional.cross_entropy(scores.masked_fill(~same_formula,-1e4),
                         torch.zeros(len(sample),dtype=torch.long,device=device),reduction='none')
        primary = per_query[eligible].mean() if eligible.any() else scores.sum()*0
        residual = scores-base
        margin_delta = residual-residual[:,0:1]
        per_query_anchor = ((margin_delta**2)*candidate_mask).sum(1)/candidate_mask.sum(1).clamp_min(1)
        center = ((residual*candidate_mask).sum(1)/candidate_mask.sum(1).clamp_min(1)).square().mean()
        anchor = per_query_anchor.mean()
        loss = primary+.5*anchor+.1*center
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        norm = torch.nn.utils.clip_grad_norm_(head.parameters(),RECIPE['gradient_clip'])
        if not torch.isfinite(loss) or not torch.isfinite(norm):
            raise ValueError('Nonfinite loss or gradient')
        optimizer.step()
        if device=='cuda':torch.cuda.synchronize()
        losses.append(float(loss.detach()));gradients.append(float(norm));times.append(time.monotonic()-t)
        components.append((float(primary.detach()),float(anchor.detach()),float(center.detach())))
        if step%100==0:
            print(json.dumps(dict(seed=seed,step=step,loss_last100=float(np.mean(losses[-100:])),
                                  optimization_seconds=sum(times))),flush=True)
        if step in (500,STEPS):
            checkpoint = dict(state_dict=head.state_dict(),head_config=head_config(),step=step,seed=seed,
                              encoder_sha256=CKPT_SHA,feature_cache_sha256=recipe_receipt['feature_cache_sha256'],
                              evaluation_label='known pretrained exposure component diagnostic',
                              model_family='same-formula bounded residual, frozen spectrum mean',
                              recipe_sha256=sha(OUT/'recipe_frozen_before_training.json'))
            path = OUT/f'head_seed{seed}_step{step}.pt'
            torch.save(checkpoint,path)
            mon = diagnostic(head,monitor,device)
            write(OUT/f'monitor_seed{seed}_step{step}.json',mon)
            milestones.append(dict(step=step,checkpoint=path.name,checkpoint_sha256=sha(path),monitor=mon['summary']))
            if step==500:
                write(OUT/f'benchmark500_seed{seed}.json',dict(status='passed',steps=step,
                      optimization_seconds=sum(times),mean_step_seconds=float(np.mean(times)),
                      initial100_loss=float(np.mean(losses[:100])),last100_loss=float(np.mean(losses[-100:])),
                      loss_components_last100=np.mean(components[-100:],axis=0).tolist(),
                      gradient_norm_min=min(gradients),gradient_norm_max=max(gradients),nonfinite_steps=0,
                      parameters=sum(p.numel() for p in head.parameters()),
                      peak_gpu_gb=torch.cuda.max_memory_allocated()/2**30 if device=='cuda' else 0))
    ev = diagnostic(head,evaluation,device)
    write(OUT/f'eval_seed{seed}.json',ev)
    receipt = dict(status='trained',steps=STEPS,seed=seed,optimization_seconds=sum(times),
                   total_training_seconds=time.monotonic()-started,milestones=milestones,
                   eval=ev['summary'],all_loss_and_gradient_finite=True,
                   recipe_sha256=sha(OUT/'recipe_frozen_before_training.json'),
                   model_source_sha256=sha(ROOT/'scripts/isomer_residual_head_20261109.py'),
                   train_source_sha256=sha(__file__),known_pretrained_exposure=True,
                   locked_queries_or_truth_read=False)
    write(OUT/f'training_receipt_seed{seed}.json',receipt)
    return head,receipt


def main():
    torch.set_num_threads(4)
    device = 'cuda'
    if not torch.cuda.is_available():raise RuntimeError('Requested GPU unavailable')
    rows, recipe_receipt = prepare()
    contract_check()
    models = [];results = {}
    for seed in SEEDS:
        model,result = train(rows,recipe_receipt,device,seed)
        models.append(model);results[str(seed)] = result
    class Ensemble(torch.nn.Module):
        def forward(self,**data):return torch.stack([model(**data) for model in models]).mean(0)
    ensemble = Ensemble()
    ensemble_mon = diagnostic(ensemble,[r for r in rows if r['split']=='monitor'],device)
    ensemble_eval = diagnostic(ensemble,[r for r in rows if r['split']=='eval'],device)
    write(OUT/'ensemble_monitor.json',ensemble_mon)
    write(OUT/'ensemble_eval.json',ensemble_eval)
    summary = dict(status='completed_fixed_recipe_two_seed_training',recipe=RECIPE,heads=results,
                   ensemble_monitor=ensemble_mon['summary'],ensemble_eval=ensemble_eval['summary'],
                   known_pretrained_exposure=True,full_stack_clean_cv=False,
                   selection='Equal two-seed ensemble was prespecified; no leaderboard or diagnostic-based seed selection',
                   inherited_candidate_restriction=True,old_weights_unchanged=True,
                   model_code_sha256=sha(ROOT/'scripts/isomer_residual_head_20261109.py'),
                   train_code_sha256=sha(__file__))
    write(OUT/'summary.json',summary)
    print(json.dumps({k:v for k,v in summary.items() if k not in ('heads',)}),flush=True)


if __name__=='__main__':main()
