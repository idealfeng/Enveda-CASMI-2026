"""Neural scorer adapter: public passthrough, frozen-v2 learned multi-spectrum head.

The CLI matches the original neural_scores.py. A source-bound runtime manifest
beside this file selects immutable head checkpoints; no training occurs here.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import torch

PUBLIC_SHA = '44436b2daec64373e66f9120dd2389c24fc83dd9430ebeeac18e3cb49dcb9642'
V2_SHA = 'c08d2101154d057890de088be63834eb622468892a3b842512fdc5a65e02ff46'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@torch.inference_mode()
def score(bundle, checkpoint, evidence, queries, output, device='cuda', *, runtime_path=None):
    torch.set_num_threads(4)
    here = Path(__file__).resolve().parent
    runtime_path = Path(runtime_path) if runtime_path else here/'learned_head_runtime.json'
    runtime = json.loads(runtime_path.read_text())
    baseline_path = here/runtime['baseline_scorer_file']
    model_path = here/runtime['head_model_file']
    if sha(baseline_path) != runtime['baseline_scorer_sha256']:
        raise ValueError('Original neural scorer source mismatch')
    if sha(model_path) != runtime['head_model_sha256']:
        raise ValueError('Learned head source mismatch')
    base_module = load_module('_casmi_original_neural_scorer', baseline_path)
    encoder_sha = sha(Path(bundle)/checkpoint)
    if encoder_sha == PUBLIC_SHA:
        base_module.score(bundle, checkpoint, evidence, queries, output, device)
        Path(str(output)+'.head_audit.json').write_text(json.dumps(dict(
            status='passed', encoder_sha256=encoder_sha, role='public_passthrough',
            head_applied=False, training_performed=False), indent=2))
        return
    if encoder_sha != V2_SHA:
        raise ValueError('Only the pinned v2 encoder may use the learned head')
    if device == 'cuda' and not torch.cuda.is_available():
        raise RuntimeError('GPU required for the requested scorer')
    head_module = load_module('_casmi_candidate_multispectrum_head', model_path)
    heads, head_receipts = [], []
    if not 1 <= len(runtime['heads']) <= 2:
        raise ValueError('Expected one trained head or two-head ensemble')
    for item in runtime['heads']:
        path = here/item['file']
        if sha(path) != item['sha256']:
            raise ValueError('Learned head checkpoint SHA mismatch')
        weights = torch.load(path, map_location='cpu', weights_only=True)
        if weights['encoder_sha256'] != V2_SHA or weights['step'] != runtime['required_step']:
            raise ValueError('Head encoder/training budget mismatch')
        head = head_module.CandidateMultiSpectrumHead(**weights['head_config']).to(device)
        head.load_state_dict(weights['state_dict'], strict=True)
        head.eval()
        heads.append(head)
        head_receipts.append(dict(sha256=item['sha256'], step=weights['step'], seed=weights['seed']))
    model, feat, cfg = base_module.load_model(bundle, checkpoint, device)
    if cfg['embedding'] != 192 or cfg['max_peaks'] != 96 or cfg['temperature'] != .1 or cfg['fp_score_weight'] != 2.:
        raise ValueError('Scorer configuration differs from head training')
    frame = pd.read_parquet(evidence)
    q = pd.read_parquet(queries)
    q['molecule_id'] = q.molecule_id.astype(str)
    query = {str(mid): group for mid, group in q.groupby('molecule_id', sort=False)}
    cache, parts, errors, audits = {}, [], [], []
    for index, (mid, group) in enumerate(frame.groupby('molecule_id', sort=False)):
        mid = str(mid)
        g = group.sort_values('baseline_rank', kind='stable').copy()
        g['neural_ok'] = False
        if not g.processed.iloc[0]:
            for col in ('neural_cos', 'neural_fp', 'neural_score', 'neural_std', 'n_spectra', 'n_adducts'):
                g[col] = 0.
            parts.append(g)
            continue
        try:
            if mid not in query:
                raise ValueError('Missing observed query spectra')
            records = []
            for row in query[mid].itertuples(index=False):
                try:
                    pk, n = feat.peaks(row.ms2_mzs, row.ms2_normalized_intensities,
                                       row.precursor_mz, cfg['max_peaks'])
                    if n < cfg['min_peaks']:
                        continue
                    metadata, adduct = feat.metadata(row.precursor_mz, row.adduct,
                                                    row.ionization_mode, row.collision_energy_ev)
                    records.append((pk, n, metadata, adduct))
                except (ValueError, TypeError):
                    continue
            if not records:
                raise ValueError('No usable spectra under the unchanged original preprocessing')
            fingerprints = []
            for smiles in g.smiles:
                if smiles not in cache:
                    cache[smiles] = feat.structure(smiles, cfg['fp_bits'])[-1]
                fingerprints.append(cache[smiles])
            F = torch.tensor(np.stack(fingerprints), device=device, dtype=torch.float32)
            M = model.encode_molecules(F)
            z_all, cos_all, fp_all = [], [], []
            for start in range(0, len(records), 64):
                batch = records[start:start+64]
                x = torch.tensor(np.stack([v[0] for v in batch]), device=device)
                lengths = torch.tensor([v[1] for v in batch], device=device, dtype=torch.long)
                metadata = torch.tensor(np.stack([v[2] for v in batch]), device=device)
                adduct = torch.tensor([v[3] for v in batch], device=device, dtype=torch.long)
                Z, P = model.encode_spectra(x, lengths, metadata, adduct)
                z_all.append(Z)
                cos_all.append(Z@M.T)
                fp_all.append(P@F.T/cfg['fp_bits'])
            Z = torch.cat(z_all)
            cosine, fp_scores = torch.cat(cos_all), torch.cat(fp_all)
            old_per_spectrum = cosine/cfg['temperature']+cfg['fp_score_weight']*fp_scores
            meta = torch.tensor(np.stack([v[2] for v in records]), device=device)
            adduct = torch.tensor([v[3] for v in records], device=device, dtype=torch.long)
            peak_fraction = torch.tensor([v[1]/cfg['max_peaks'] for v in records], device=device)
            mask = torch.ones((1, len(records)), device=device, dtype=torch.bool)
            values = [head(Z[None], M[None], cosine[None], fp_scores[None], meta[None],
                           adduct[None], peak_fraction[None], mask)[0] for head in heads]
            learned = torch.stack(values).mean(0).cpu().numpy()
            cos_np, fp_np = cosine.cpu().numpy(), fp_scores.cpu().numpy()
            old_np = old_per_spectrum.cpu().numpy()
            if not np.isfinite(learned).all() or not np.isfinite(old_np).all():
                raise ValueError('Non-finite learned score')
            # Keep all original diagnostics/physical guards on their original scale.
            # The learned candidate-conditioned aggregate replaces only neural_score.
            g['neural_cos'], g['neural_fp'] = cos_np.mean(0), fp_np.mean(0)
            g['neural_score'], g['neural_std'] = learned, old_np.std(0)
            g['n_spectra'], g['n_adducts'], g['neural_ok'] = len(records), query[mid].adduct.nunique(), True
            audits.append(dict(molecule_id=mid, candidates=len(g), spectra=len(records),
                               max_abs_delta_from_mean=float(np.max(np.abs(learned-old_np.mean(0))))))
            parts.append(g)
        except (ValueError, TypeError) as error:
            # Preserve the original per-query invalid-input fallback, with evidence.
            errors.append(dict(molecule_id=mid, error=str(error)))
            for col in ('neural_cos', 'neural_fp', 'neural_score', 'neural_std', 'n_spectra', 'n_adducts'):
                g[col] = 0.
            parts.append(g)
        if (index+1) % 25 == 0:
            print('LEARNED HEAD SCORED', index+1, 'molecules', flush=True)
    result = pd.concat(parts, ignore_index=True)
    if len(result) != len(frame) or result.duplicated(['molecule_id', 'smiles']).any():
        raise ValueError('Candidate keys changed or duplicated')
    if not audits:
        raise RuntimeError('Learned head did not score any query')
    result.to_parquet(output, index=False)
    Path(str(output)+'.errors.json').write_text(json.dumps(errors, indent=2))
    Path(str(output)+'.head_audit.json').write_text(json.dumps(dict(
        status='passed', role='learned_v2', head_applied=True, encoder_sha256=encoder_sha,
        heads=head_receipts, preprocessing='unchanged original Saner features.peaks/metadata/structure',
        evidence_sha256=sha(evidence), queries_sha256=sha(queries), output_sha256=sha(output),
        input_rows=len(frame), output_rows=len(result), scored_queries=len(audits),
        scored_candidate_rows=sum(x['candidates'] for x in audits), per_query=audits,
        errors=errors, training_performed=False,
        checkpoint_evaluation_label='known-pretrained-exposure engineering diagnostic'), indent=2))
    print('LEARNED HEAD FEATURES', result.shape, 'heads', len(heads), 'input failures', len(errors), flush=True)


if __name__ == '__main__':
    score(*sys.argv[1:])
