"""Prepare exact raw Saner inputs, mine v2 errors, and train a small listwise head.

All evaluations are explicitly known-pretrained-exposure component diagnostics.
The old 48 and all frozen split identities are denied to positives/negatives.
No locked queries/labels, whole Flex execution, network, or Kaggle writes.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import sqlite3
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
SOURCE = ROOT / 'assets/kaggle/sanpier/casmi-spectrum-model-v1/v1/casmi_spectrum_model_v1'
V2 = ROOT / 'assets/kaggle/bgunshui/casmi26-scorer-v2-model/v1'
POOL = ROOT / 'assets/kaggle/ahmedberatozer/casmi26-v2-pool/v1'
TRAIN = ROOT / 'enveda-CASMI26-molecule-id-mass-spectra/train.parquet'
SPLITS = ROOT / 'runs/validation_pilot_v2_20261104/frozen_splits.json'
CKPT_SHA = 'c08d2101154d057890de088be63834eb622468892a3b842512fdc5a65e02ff46'
OFFSETS = {'[M+H]+': (1, 1.007276466621), '[M-H]-': (1, -1.007276466621),
           '[M+Na]+': (1, 22.989218), '[M+K]+': (1, 38.963158),
           '[M+NH4]+': (1, 18.033823), '[M+Cl]-': (1, 34.969402),
           '[M+FA-H]-': (1, 44.998201), '[M+H-H2O]+': (1, -17.003288),
           '[M+2H]2+': (2, 2.014552933242), '[M-2H]2-': (2, -2.014552933242)}


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write(path, value):
    temp = Path(str(path) + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


def stable(key):
    return hashlib.sha256(('head-20261108:' + key).encode()).hexdigest()


def feature_module():
    spec = importlib.util.spec_from_file_location('_head_saner_features', SOURCE / 'features.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def denials():
    values = json.loads(SPLITS.read_text())
    identities, raw = set(), set()
    for panel, rows in values.items():
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict) and row.get('official_identity'):
                    identities.add(row['official_identity'])
                    raw.update(row.get('raw_keys', []))
    return identities, raw


def prepare(out, target=1280):
    import numpy as np
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.parquet as pq
    from rdkit import RDLogger
    from validation.metric import assert_official_rdkit, identity
    RDLogger.DisableLog('rdApp.*')
    assert_official_rdkit()
    started = time.monotonic()
    features = feature_module()
    denied, denied_raw = denials()
    pool = pq.read_table(POOL / 'pool_meta.parquet', columns=['key', 'smiles', 'mass']).to_pydict()
    masses = np.array(pool['mass'])
    assert np.isfinite(masses).all() and np.all(masses[1:] >= masses[:-1])
    structures = pq.read_table(POOL / 'train_structs.parquet',
        columns=['inchikey14', 'smiles', 'n_spec', 'mass', 'n_heavy', 'n_tims']).to_pylist()
    eligible = [r for r in structures if r['n_spec'] >= 3 and 150 <= r['mass'] <= 700
                and 10 <= r['n_heavy'] <= 60 and r['inchikey14'] not in denied_raw]
    eligible.sort(key=lambda r: stable(r['inchikey14']))
    selected, official_seen = {}, set()
    for row in eligible:
        mass = row['mass']; low = np.searchsorted(masses, mass * (1 - 1e-5)); high = np.searchsorted(masses, mass * (1 + 1e-5))
        if not 17 <= high - low <= 96:
            continue
        key = identity(row['smiles'])
        if not key or key in denied or key in official_seen:
            continue
        official_seen.add(key)
        selected[row['inchikey14']] = dict(raw_key=row['inchikey14'], key=key, smiles=row['smiles'])
        if len(selected) >= target + 256:
            break
    if len(selected) < target:
        raise ValueError('Insufficient catalog identities for requested training benchmark')
    print(json.dumps({'stage': 'selected', 'identities': len(selected)}), flush=True)
    source_columns = ['inchikey14', 'normalized_smiles', 'ingest_lib', 'ionization_mode', 'instrument_type',
                      'adduct', 'precursor_mz', 'collision_energy_ev', 'collision_energy_orig_units',
                      'ms2_mzs', 'ms2_normalized_intensities']
    selection_keys = pa.array(sorted(selected))
    spectra = defaultdict(list)
    signatures = defaultdict(set)
    scan_rows = 0
    for batch_index, batch in enumerate(pq.ParquetFile(TRAIN).iter_batches(columns=source_columns, batch_size=32768)):
        mask = pc.is_in(batch.column('inchikey14'), value_set=selection_keys)
        hits = batch.filter(mask).to_pylist()
        for row in hits:
            raw_key = row['inchikey14']
            if len(spectra[raw_key]) >= 12 or row['adduct'] not in OFFSETS:
                continue
            if identity(row['normalized_smiles']) != selected[raw_key]['key']:
                continue
            try:
                pk, length = features.peaks(row['ms2_mzs'], row['ms2_normalized_intensities'], row['precursor_mz'], 96)
                if length < 3:
                    continue
                meta, adduct = features.metadata(row['precursor_mz'], row['adduct'], row['ionization_mode'], row['collision_energy_ev'])
                digest = hashlib.sha256(pk.tobytes() + meta.tobytes() + str(adduct).encode()).hexdigest()
                if digest in signatures[raw_key]:
                    continue
                signatures[raw_key].add(digest)
                row['head_signature'] = digest
                spectra[raw_key].append(row)
            except (ValueError, TypeError):
                pass
        scan_rows += batch.num_rows
        if batch_index % 20 == 0:
            print(json.dumps({'stage': 'raw_scan', 'rows': scan_rows, 'identities_with_spectra': len(spectra)}), flush=True)
    usable = [row for row in selected.values() if spectra[row['raw_key']]]
    usable = usable[:target]
    if len(usable) < target:
        raise ValueError(f'Only {len(usable)} usable identities, need {target}')
    # This fixed assignment is made before any score or outcome is observed.
    for i, row in enumerate(usable):
        row['split'] = 'train' if i < 1024 else 'monitor' if i < 1152 else 'eval'
    independent = {r['key'] for r in usable if r['split'] != 'train'}
    query_rows, spec_arrays = [], []
    for row in usable:
        source = spectra[row['raw_key']]
        # Prefer real different acquisition conditions; then fill from distinct spectra.
        groups = defaultdict(list)
        for spec in source:
            groups[(str(spec['adduct']), str(spec['collision_energy_ev']), str(spec['instrument_type']))].append(spec)
        chosen = []
        for depth in range(12):
            for group in groups.values():
                if depth < len(group):
                    chosen.append(group[depth])
                if len(chosen) == 4:
                    break
            if len(chosen) == 4:
                break
        neutral = [float(s['precursor_mz']) * OFFSETS[s['adduct']][0] - OFFSETS[s['adduct']][1] for s in chosen]
        observed_mass = float(np.median(neutral))
        low = int(np.searchsorted(masses, observed_mass * (1 - 1e-5)))
        high = int(np.searchsorted(masses, observed_mass * (1 + 1e-5)))
        row.update(observed_neutral_mass=observed_mass, pool_indices=list(range(low, high)),
                   spectrum_start=len(spec_arrays), spectrum_count=len(chosen))
        for spec in chosen:
            pk, length = features.peaks(spec['ms2_mzs'], spec['ms2_normalized_intensities'], spec['precursor_mz'], 96)
            meta, adduct = features.metadata(spec['precursor_mz'], spec['adduct'], spec['ionization_mode'], spec['collision_energy_ev'])
            spec_arrays.append((pk, length, meta, adduct))
            query_rows.append(dict(key=row['key'], split=row['split'], raw_key=row['raw_key'],
                source=spec['ingest_lib'], adduct=spec['adduct'], collision_energy_ev=spec['collision_energy_ev'],
                signature=spec['head_signature'], original_precursor_mz=spec['precursor_mz']))
    out.mkdir(parents=True, exist_ok=False)
    np.savez(out / 'spectra_inputs.npz', x=np.stack([r[0] for r in spec_arrays]),
             lengths=np.array([r[1] for r in spec_arrays]), meta=np.stack([r[2] for r in spec_arrays]),
             adduct=np.array([r[3] for r in spec_arrays]))
    pq.write_table(pa.Table.from_pylist(query_rows), out / 'spectrum_provenance.parquet')
    # Canonicalization and fixed fingerprints are computed once for the union.
    used_pool = sorted({i for row in usable for i in row['pool_indices']})
    wanted = {pool['smiles'][i] for i in used_pool} | {r['smiles'] for r in usable}
    catalog, fp_values = [], []
    for i, smiles in enumerate(sorted(wanted)):
        try:
            key, canonical, formula, mass, fp = features.structure(smiles, 2048)
            catalog.append(dict(smiles=smiles, key=key, canonical=canonical, formula=formula, mass=mass, fp_index=len(fp_values)))
            fp_values.append(fp.astype(np.uint8))
        except (ValueError, TypeError, RuntimeError):
            continue
        if (i + 1) % 1000 == 0:
            print(json.dumps({'stage': 'candidate_canonical', 'done': i + 1, 'total': len(wanted)}), flush=True)
    pq.write_table(pa.Table.from_pylist(catalog), out / 'candidate_catalog.parquet')
    np.save(out / 'candidate_fingerprints.npy', np.stack(fp_values))
    mapping = {r['smiles']: r for r in catalog}
    for row in usable:
        candidates, seen = [], set()
        for index in row.pop('pool_indices'):
            item = mapping.get(pool['smiles'][index])
            if item is None or item['key'] in denied or item['key'] in seen:
                continue
            if row['split'] == 'train' and item['key'] in independent:
                continue
            # A monitor target cannot be a negative in Eval, or vice versa.
            if row['split'] != 'train' and item['key'] in independent - {row['key']}:
                continue
            seen.add(item['key']); candidates.append(item['fp_index'])
        row['retrieved_candidates'] = candidates
        row['positive_fp_index'] = mapping[row['smiles']]['fp_index']
    write(out / 'queries.json', usable)
    receipt = dict(status='prepared', created_at_utc=datetime.now(timezone.utc).isoformat(),
        train_identities=sum(r['split']=='train' for r in usable), monitor_identities=128, eval_identities=128,
        raw_train_rows_scanned=scan_rows, spectra=len(spec_arrays), candidate_structures=len(catalog),
        deny_identities=sorted(denied), head_train_ids=sorted(r['key'] for r in usable if r['split']=='train'),
        monitor_ids=sorted(r['key'] for r in usable if r['split']=='monitor'), eval_ids=sorted(r['key'] for r in usable if r['split']=='eval'),
        dataset_selection='hash-ordered training catalog; >=3 original spectra; 17-96 catalog rows within true-mass window for engineering throughput; actual candidate lists use observed precursor/adduct mass only',
        preprocessing='unmodified original Saner features.peaks and metadata on raw train arrays',
        known_pretrained_exposure=True, locked_query_or_truth_read=False,
        candidate_pool_sha256=sha(POOL/'pool_meta.parquet'), encoder_checkpoint_sha256=sha(V2/'final_model.pt'),
        source_features_sha256=sha(SOURCE/'features.py'), source_model_sha256=sha(SOURCE/'model.py'),
        frozen_denials_sha256=sha(SPLITS), script_sha256=sha(__file__),
        prepare_seconds=time.monotonic()-started)
    if receipt['encoder_checkpoint_sha256'] != CKPT_SHA:
        raise ValueError('Unexpected encoder checkpoint')
    write(out / 'prepare_receipt.json', receipt)
    print(json.dumps({k:receipt[k] for k in ['status','train_identities','spectra','candidate_structures','prepare_seconds']}), flush=True)


def load_encoder(device):
    import torch
    spec = importlib.util.spec_from_file_location('_head_saner_model', SOURCE/'model.py')
    module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    cfg = json.loads((V2/'config_used.json').read_text())
    if sha(V2/'final_model.pt') != CKPT_SHA:
        raise ValueError('Wrong frozen encoder')
    model = module.SpectrumCandidateModel(cfg).to(device)
    model.load_state_dict(torch.load(V2/'final_model.pt',map_location=device,weights_only=True)['state_dict'],strict=True)
    model.eval()
    return model,cfg


def export(out, device):
    import numpy as np
    import torch
    import pyarrow.parquet as pq
    started=time.monotonic();torch.set_num_threads(4)
    if device=='cuda':torch.cuda.reset_peak_memory_stats()
    encoder,cfg=load_encoder(device)
    inputs=np.load(out/'spectra_inputs.npz');fingerprints=np.load(out/'candidate_fingerprints.npy',mmap_mode='r')
    zs,ps=[],[]
    with torch.inference_mode():
        for st in range(0,len(inputs['x']),64):
            x=torch.as_tensor(inputs['x'][st:st+64],device=device)
            n=torch.as_tensor(inputs['lengths'][st:st+64],device=device)
            meta=torch.as_tensor(inputs['meta'][st:st+64],device=device)
            adduct=torch.as_tensor(inputs['adduct'][st:st+64],device=device)
            z,p=encoder.encode_spectra(x,n,meta,adduct)
            zs.append(z.cpu());ps.append(p.cpu())
        mol=[]
        for st in range(0,len(fingerprints),512):
            f=torch.tensor(np.array(fingerprints[st:st+512]),device=device,dtype=torch.float32)
            mol.append(encoder.encode_molecules(f).cpu())
    Z,P=torch.cat(zs),torch.cat(ps);M=torch.cat(mol)
    queries=json.loads((out/'queries.json').read_text());catalog=pq.read_table(out/'candidate_catalog.parquet').to_pylist()
    keys={r['fp_index']:r['key'] for r in catalog};formulas={r['fp_index']:r['formula'] for r in catalog}
    rows=[];mining_rows=[]
    for qi,q in enumerate(queries):
        st,n=q['spectrum_start'],q['spectrum_count'];z,p=Z[st:st+n],P[st:st+n]
        candidates=list(q['retrieved_candidates'])
        if candidates:
            f=torch.tensor(np.array(fingerprints[candidates]),dtype=torch.float32)
            cos=z@M[candidates].T;fp_score=p@f.T/cfg['fp_bits']
            baseline=(cos/cfg['temperature']+cfg['fp_score_weight']*fp_score).mean(0)
            order=torch.argsort(baseline,descending=True,stable=True).tolist()
            ranked=[candidates[i] for i in order]
        else:ranked=[]
        positive_key=q['key']
        positive=next((v for v in ranked if keys[v]==positive_key),q['positive_fp_index'])
        positive_was_retrieved=any(keys[v]==positive_key for v in ranked)
        if q['split']=='train':
            wrong=[v for v in ranked if keys[v]!=positive_key]
            candidates=[positive]+wrong[:32]
            label=0
            for rank,index in enumerate(wrong[:32],1):
                mining_rows.append(dict(query_key=positive_key,split='train',negative_key=keys[index],
                    negative_smiles=catalog[index]['smiles'],wrong_rank=rank,
                    same_formula=formulas[index]==formulas[positive],pool_candidate_index=index))
        else:
            candidates=ranked[:128]
            label=next((i for i,v in enumerate(candidates) if keys[v]==positive_key),-1)
        # Keep empty retrieval lists in Monitor/Eval: they must contribute zero,
        # rather than silently disappearing from the recall/MRR denominator.
        c=torch.tensor(candidates,dtype=torch.long)
        f=torch.tensor(np.array(fingerprints[candidates]),dtype=torch.float32)
        rows.append(dict(key=q['key'],split=q['split'],label=label, positive_was_retrieved=positive_was_retrieved,
            candidate_keys=[keys[v] for v in candidates],
            z=z.clone(),m=M[c].clone(),cos=z@M[c].T,fp_score=p@f.T/cfg['fp_bits'],
            metadata=torch.tensor(inputs['meta'][st:st+n]),adduct=torch.tensor(inputs['adduct'][st:st+n]),
            peak_fraction=torch.tensor(inputs['lengths'][st:st+n]/96,dtype=torch.float32)))
        if (qi+1)%128==0:print(json.dumps({'stage':'mine_export','queries':qi+1}),flush=True)
    import pyarrow as pa
    pq.write_table(pa.Table.from_pylist(mining_rows),out/'actual_v2_hard_negatives.parquet')
    torch.save(rows,out/'head_features.pt')
    receipt=dict(status='exported',frozen_encoder=True,query_counts=dict(Counter(r['split'] for r in rows)),
        export_seconds=time.monotonic()-started, peak_gpu_gb=torch.cuda.max_memory_allocated()/2**30 if device=='cuda' else 0,
        hard_negative_rows=len(mining_rows),negative_miner='actual frozen-v2 ranking over measured-neutral-mass pool window',
        train_truth_injected_queries=sum(r['split']=='train' and not r['positive_was_retrieved'] for r in rows),
        eval_recall=sum(r['split']=='eval' and r['positive_was_retrieved'] for r in rows)/128,
        encoder_checkpoint_sha256=CKPT_SHA,features_sha256=sha(out/'head_features.pt'),
        negatives_sha256=sha(out/'actual_v2_hard_negatives.parquet'),known_pretrained_exposure=True,
        mean_spectra=sum(len(r['z']) for r in rows)/len(rows))
    write(out/'export_receipt.json',receipt);print(json.dumps(receipt),flush=True)


def batch(rows,device):
    import torch
    b=len(rows);s=max(len(r['z']) for r in rows);c=max(len(r['m']) for r in rows)
    data=dict(z=torch.zeros(b,s,192),m=torch.zeros(b,c,192),cos=torch.zeros(b,s,c),fp_score=torch.zeros(b,s,c),
              metadata=torch.zeros(b,s,4),adduct=torch.zeros(b,s,dtype=torch.long),peak_fraction=torch.zeros(b,s),
              spectrum_mask=torch.zeros(b,s,dtype=torch.bool))
    cmask=torch.zeros(b,c,dtype=torch.bool)
    for i,r in enumerate(rows):
        si,ci=len(r['z']),len(r['m'])
        for name in ['z','metadata','adduct','peak_fraction']:data[name][i,:si]=r[name]
        data['m'][i,:ci]=r['m']
        for name in ['cos','fp_score']:data[name][i,:si,:ci]=r[name]
        data['spectrum_mask'][i,:si]=True;cmask[i,:ci]=True
    return {k:v.to(device) for k,v in data.items()},cmask.to(device)


def evaluate(model,rows,device):
    import torch
    totals=dict(n=len(rows),recall=0,base_rr=0.,head_rr=0.,base_top1=0,head_top1=0,gains=0,losses=0)
    details=[];model.eval()
    with torch.inference_mode():
        for r in rows:
            data,_=batch([r],device);scores=model(**data)[0]
            base=(r['cos']/0.1+2*r['fp_score']).mean(0)
            label=r['label']
            br=hr=None
            if label>=0:
                totals['recall']+=1
                br=torch.argsort(base,descending=True,stable=True).tolist().index(label)+1
                hr=torch.argsort(scores,descending=True,stable=True).tolist().index(label)+1
            bv=1/br if br and br<=25 else 0.;hv=1/hr if hr and hr<=25 else 0.
            totals['base_rr']+=bv;totals['head_rr']+=hv;totals['base_top1']+=br==1;totals['head_top1']+=hr==1
            totals['gains']+=hv>bv;totals['losses']+=hv<bv
            details.append(dict(key=r['key'],base_rank=br,head_rank=hr,delta=hv-bv,candidates=len(r['m'])))
    n=max(1,len(rows))
    for name in ['recall','base_rr','head_rr','base_top1','head_top1']:totals[name]/=n
    return totals,details


def train(out,device,steps=2500,seed=20261108):
    import numpy as np
    import torch
    from candidate_multispectrum_head import CandidateMultiSpectrumHead,head_config
    torch.set_num_threads(4);torch.manual_seed(seed);random.seed(seed);np.random.seed(seed)
    if device=='cuda':torch.cuda.reset_peak_memory_stats()
    rows=torch.load(out/'head_features.pt',map_location='cpu',weights_only=True)
    training=[r for r in rows if r['split']=='train'];monitor=[r for r in rows if r['split']=='monitor'];evaluation=[r for r in rows if r['split']=='eval']
    if len(training)<1024:raise ValueError('Fewer than1024 training queries')
    head=CandidateMultiSpectrumHead(**head_config()).to(device)
    with torch.no_grad():
        r=training[0];data,_=batch([r],device);old=(r['cos']/0.1+2*r['fp_score']).mean(0)
        zero_delta=float((head(**data)[0].cpu()-old).abs().max())
    if zero_delta>3e-6:raise ValueError('Zero residual head fails original mean reproduction')
    optimizer=torch.optim.AdamW(head.parameters(),lr=2e-4,weight_decay=.01)
    losses=[];gradient=[];step_times=[];started=time.monotonic();finite=True;milestones=[]
    generator=random.Random(seed)
    for step in range(1,steps+1):
        t=time.monotonic();head.train();sample=generator.sample(training,16)
        data,mask=batch(sample,device);scores=head(**data).masked_fill(~mask,-1e4)
        loss=torch.nn.functional.cross_entropy(scores,torch.zeros(len(sample),device=device,dtype=torch.long))
        optimizer.zero_grad(set_to_none=True);loss.backward()
        norm=torch.nn.utils.clip_grad_norm_(head.parameters(),5.0)
        if not torch.isfinite(loss) or not torch.isfinite(norm):finite=False;raise ValueError('Nonfinite training loss or gradient')
        optimizer.step()
        if device=='cuda':torch.cuda.synchronize()
        losses.append(float(loss.detach()));gradient.append(float(norm));step_times.append(time.monotonic()-t)
        if step%100==0:print(json.dumps({'stage':'train','step':step,'loss_last100':float(np.mean(losses[-100:])),
            'seconds':time.monotonic()-started}),flush=True)
        if step in {500,steps}:
            state=dict(state_dict=head.state_dict(),head_config=head_config(),step=step,seed=seed,
                encoder_sha256=CKPT_SHA,feature_cache_sha256=sha(out/'head_features.pt'),
                evaluation_label='known pretrained exposure component diagnostic',
                model_family='candidate-conditioned multispectrum residual and attention listwise head')
            path=out/f'head_seed{seed}_step{step}.pt';torch.save(state,path)
            mon,details=evaluate(head,monitor,device)
            write(out/f'monitor_seed{seed}_step{step}.json',dict(summary=mon,details=details))
            milestones.append(dict(step=step,checkpoint=path.name,checkpoint_sha256=sha(path),monitor=mon))
            if step==500:
                write(out/f'benchmark500_seed{seed}.json',dict(status='passed',steps=step,
                    optimization_seconds=sum(step_times),mean_step_seconds=float(np.mean(step_times)),
                    median_step_seconds=float(np.median(step_times)),initial100_loss=float(np.mean(losses[:100])),
                    final100_loss=float(np.mean(losses[-100:])),gradient_norm_min=min(gradient),gradient_norm_max=max(gradient),
                    nonfinite_steps=0,zero_residual_max_error=zero_delta,parameters=sum(p.numel() for p in head.parameters()),
                    peak_gpu_gb=torch.cuda.max_memory_allocated()/2**30 if device=='cuda' else 0,
                    training_identities=len(training),monitor_identities=len(monitor),known_pretrained_exposure=True))
    result,details=evaluate(head,evaluation,device)
    write(out/f'eval_seed{seed}.json',dict(summary=result,details=details,known_pretrained_exposure=True,
        frozen_encoder=True,full_Flex_MASS_validation=False,truth_injected_in_eval=False))
    receipt=dict(status='trained',steps=steps,seed=seed,milestones=milestones,eval=result,
        optimization_seconds=sum(step_times),total_training_phase_seconds=time.monotonic()-started,
        training_identities=len(training),all_loss_gradient_finite=finite,zero_residual_max_error=zero_delta,
        head_code_sha256=sha(ROOT/'scripts/candidate_multispectrum_head.py'),
        known_pretrained_exposure=True,locked_queries_or_truth_read=False)
    write(out/f'training_receipt_seed{seed}.json',receipt);print(json.dumps(receipt),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=['prepare','export','train'])
    parser.add_argument('--out',type=Path,default=ROOT/'runs/candidate_head_20261108')
    parser.add_argument('--device',choices=['cpu','cuda'],default='cuda')
    parser.add_argument('--steps',type=int,default=2500)
    parser.add_argument('--seed',type=int,default=20261108)
    args=parser.parse_args();out=args.out.resolve()
    if not out.is_relative_to(ROOT):raise ValueError('All artifacts must remain on D workspace')
    if args.phase=='prepare':prepare(out)
    elif args.phase=='export':export(out,args.device)
    else:train(out,args.device,args.steps,args.seed)


if __name__=='__main__':main()
