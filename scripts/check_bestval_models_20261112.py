"""Tiny actual original-scorer CPU canary; no quality evaluation or truth access."""
from pathlib import Path
import gc
import hashlib
import importlib.util
import json
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    import pandas as pd
    import numpy as np
    import torch
    torch.set_num_threads(4)
    out = ROOT / 'runs/bestval_models_canary_20261112'
    out.mkdir(parents=True, exist_ok=False)
    pub = ROOT / 'assets/kaggle/sanpier/casmi-spectrum-model-v1/v1/casmi_spectrum_model_v1'
    v2 = ROOT / 'assets/kaggle/bgunshui/casmi26-scorer-v2-model/v1'
    pop = ROOT / 'assets/kaggle/popwenman/casmi26-scorer-train-v80/v1/casmi_spectrum_model_ours_v80'
    source = ROOT / 'third_party/flexonafft_evidence_gap/v56/embedded/neural_scores.py'
    spec = importlib.util.spec_from_file_location('actual_original_scorer', source)
    scorer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scorer)
    old = ROOT / 'runs/validation_flex_c2_20261105d'
    evidence = pd.read_parquet(old / 'frozen_candidate_evidence.parquet')
    ids = evidence.molecule_id.astype(str).drop_duplicates().iloc[:3].tolist()
    evidence = evidence[evidence.molecule_id.astype(str).isin(ids)].groupby('molecule_id', sort=False).head(5)
    queries = pd.read_parquet(old / 'effective_query_spectra.parquet')
    queries = queries[queries.molecule_id.astype(str).isin(ids)]
    evidence.to_parquet(out / 'evidence.parquet', index=False)
    queries.to_parquet(out / 'queries.parquet', index=False)
    models = [('public_final', pub / 'final_model.pt'), ('v2_final', v2 / 'final_model.pt'),
              ('popwenman_best', pop / 'best_validation_model.pt'), ('saner_best', pub / 'best_validation_model.pt')]
    reports = []
    outputs = {}
    for name, checkpoint in models:
        bundle = out / name
        bundle.mkdir()
        for filename in ('model.py', 'features.py', 'config.json'):
            shutil.copy2(pub / filename, bundle / filename)
        shutil.copy2(checkpoint, bundle / 'final_model.pt')
        started = time.monotonic()
        scorer.score(bundle, 'final_model.pt', out / 'evidence.parquet', out / 'queries.parquet', out / (name + '.parquet'), 'cpu')
        frame = pd.read_parquet(out / (name + '.parquet'))
        assert frame.neural_ok.all() and np.isfinite(frame.neural_score).all()
        assert not json.loads((out / (name + '.parquet.errors.json')).read_text())
        outputs[name] = frame.neural_score.to_numpy()
        reports.append(dict(name=name, checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
                            rows=len(frame), seconds=time.monotonic() - started, strict_load_and_actual_scoring=True))
        gc.collect()
    assert len({row['checkpoint_sha256'] for row in reports}) == 4
    differences = {name:float(np.max(np.abs(values - outputs['v2_final']))) for name,values in outputs.items() if name != 'v2_final'}
    assert all(value > 0 for value in differences.values())
    record = dict(status='passed', models=reports, candidate_rows=len(evidence), query_spectra=len(queries),
                  max_score_difference_vs_v2=differences, truth_read=False, quality_gain_claim=False, gpu_used=False)
    (out / 'verification.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    (ROOT / 'reports/optimization_20261112/v80_bestval_compatibility.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    main()
