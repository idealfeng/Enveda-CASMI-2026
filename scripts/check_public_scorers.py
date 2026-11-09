"""Strictly load the two pinned public scorers and run a tiny real-input CPU smoke."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    import numpy as np
    import pandas as pd
    import torch
    torch.set_num_threads(4)
    source = ROOT/'third_party/flexonafft_evidence_gap/v56/embedded/neural_scores.py'
    spec = importlib.util.spec_from_file_location('casmi_scorer_compatibility', source)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    run = ROOT/'runs/validation_flex_c2_20261105d'
    queries = pd.read_parquet(run/'effective_query_spectra.parquet')
    candidates = pd.read_parquet(run/'frozen_candidate_evidence.parquet').drop_duplicates('smiles').head(2)
    report = dict(status='checking', checked_at_utc=datetime.now(timezone.utc).isoformat(),
        scope='Strict CPU load and finite forward on two usable existing spectra/candidates; not performance validation',
        truth_read=False, locked_final_evaluated=False, new_training_or_submission=False, models=[])
    for slug in ('casmi26-scorer-v2-model', 'casmi26-scorer-v4-model'):
        bundle = ROOT/'assets/kaggle/bgunshui'/slug/'v1'
        for name in ('final_model.pt', 'config.json', 'model.py', 'features.py'):
            receipt = json.loads((bundle/(name+'.receipt.json')).read_text())
            if sha(bundle/name) != receipt['sha256']:
                raise ValueError('Staged inference input changed: ' + name)
        started = time.monotonic()
        model, features, config = module.load_model(bundle, 'final_model.pt', 'cpu')
        records = []
        skipped = 0
        for row in queries.itertuples(index=False):
            # Apply the original scorer's min_peaks filter before selecting a smoke sample.
            peaks, count = features.peaks(row.ms2_mzs, row.ms2_normalized_intensities,
                                          row.precursor_mz, config['max_peaks'])
            if count < config['min_peaks']:
                skipped += 1
                continue
            meta, adduct = features.metadata(row.precursor_mz, row.adduct,
                                             row.ionization_mode, row.collision_energy_ev)
            records.append((peaks, count, meta, adduct))
            if len(records) == 2:
                break
        if len(records) != 2 or len(candidates) != 2:
            raise ValueError('Two usable spectra and distinct candidates required')
        fingerprints = torch.tensor(np.stack([features.structure(s, config['fp_bits'])[-1]
                                              for s in candidates.smiles]), dtype=torch.float32)
        with torch.inference_mode():
            embeddings, logits = model.encode_spectra(
                torch.tensor(np.stack([r[0] for r in records])), torch.tensor([r[1] for r in records]),
                torch.tensor(np.stack([r[2] for r in records])), torch.tensor([r[3] for r in records]))
            molecules = model.encode_molecules(fingerprints)
            scores = embeddings @ molecules.T / config['temperature'] + config['fp_score_weight'] * (
                logits @ fingerprints.T / config['fp_bits'])
        if tuple(scores.shape) != (2, 2) or not torch.isfinite(scores).all():
            raise ValueError('Invalid smoke forward shape or nonfinite scores')
        report['models'].append(dict(slug=slug, version=1, width=config['width'], heads=config['heads'],
            embedding=config['embedding'], parameters=sum(p.numel() for p in model.parameters()),
            strict_state_dict_load=True, weights_only_loader=True, real_usable_spectra=2,
            raw_spectra_skipped_by_original_filter=skipped, candidates=2, forward_shape=list(scores.shape),
            all_finite=True, checkpoint_sha256=sha(bundle/'final_model.pt'), seconds=time.monotonic()-started))
        del model
    report['distinct_model_checkpoints'] = len({m['checkpoint_sha256'] for m in report['models']}) == 2
    if not report['distinct_model_checkpoints']:
        raise ValueError('Independent scorers unexpectedly share a checkpoint')
    report['status'] = 'passed'
    (ROOT/'reports/public_scorer_compatibility_20261106.json').write_text(
        json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
