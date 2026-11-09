"""Real-spectrum zero-head equivalence fixture; no training or locked evaluation."""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    import numpy as np
    import pandas as pd
    import torch
    from candidate_multispectrum_head import CandidateMultiSpectrumHead, head_config
    import learned_head_score as adapter

    output = ROOT/'reports/learned_head_scorer_fixture_20261108'
    output.mkdir(exist_ok=False)
    old = ROOT/'runs/validation_flex_c2_20261105d/p2s_code/neural_scores.py'
    spec = importlib.util.spec_from_file_location('_fixture_original_scorer', old)
    original = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(original)
    ev = pd.read_parquet(ROOT/'runs/validation_flex_c2_20261105d/frozen_candidate_evidence.parquet')
    q = pd.read_parquet(ROOT/'runs/validation_flex_c2_20261105d/effective_query_spectra.parquet')
    counts = q.groupby('molecule_id').size().sort_values(ascending=False)
    mids = counts.index[:3].tolist()
    ev = ev[ev.molecule_id.isin(mids)].copy()
    q = q[q.molecule_id.isin(mids)].copy()
    ev.to_parquet(output/'evidence.parquet', index=False)
    q.to_parquet(output/'queries.parquet', index=False)
    encoder = ROOT/'assets/kaggle/bgunshui/casmi26-scorer-v2-model/v1/final_model.pt'
    bundle = ROOT/'assets/kaggle/sanpier/casmi-spectrum-model-v1/v1/casmi_spectrum_model_v1'
    zero = CandidateMultiSpectrumHead(**head_config())
    checkpoint = output/'zero_head.pt'
    torch.save(dict(state_dict=zero.state_dict(), head_config=head_config(), step=0, seed=0,
                    encoder_sha256=adapter.V2_SHA), checkpoint)
    runtime = dict(baseline_scorer_file=str(old), baseline_scorer_sha256=sha(old),
                   head_model_file=str(ROOT/'scripts/candidate_multispectrum_head.py'),
                   head_model_sha256=sha(ROOT/'scripts/candidate_multispectrum_head.py'),
                   heads=[dict(file=str(checkpoint), sha256=sha(checkpoint))], required_step=0)
    runtime_path = output/'runtime.json'
    runtime_path.write_text(json.dumps(runtime, indent=2))
    original.score(str(bundle), str(encoder), str(output/'evidence.parquet'),
                   str(output/'queries.parquet'), str(output/'baseline.parquet'), 'cpu')
    adapter.score(str(bundle), str(encoder), str(output/'evidence.parquet'),
                  str(output/'queries.parquet'), str(output/'zero.parquet'), 'cpu', runtime_path=runtime_path)
    a = pd.read_parquet(output/'baseline.parquet').set_index(['molecule_id','smiles'])
    b = pd.read_parquet(output/'zero.parquet').set_index(['molecule_id','smiles']).reindex(a.index)
    differences = {c: float(np.abs(a[c].to_numpy()-b[c].to_numpy()).max()) for c in
                   ['neural_score','neural_cos','neural_fp','neural_std','n_spectra','n_adducts']}
    checks = dict(same_candidate_keys=set(a.index)==set(b.index),
                  same_coverage=a.neural_ok.equals(b.neural_ok),
                  finite_scores=bool(np.isfinite(b.neural_score).all()),
                  zero_head_reproduces_original_mean=differences['neural_score'] <= 2e-6,
                  other_diagnostics_equal=all(differences[c] <= 2e-6 for c in differences if c != 'neural_score'),
                  no_input_errors=not json.loads((output/'zero.parquet.errors.json').read_text()))
    result = dict(status='passed' if all(checks.values()) else 'failed', checks=checks,
                  max_abs_differences=differences, queries=len(mids), spectra=len(q), candidates=len(a),
                  adapter_sha256=sha(ROOT/'scripts/learned_head_score.py'),
                  head_model_sha256=sha(ROOT/'scripts/candidate_multispectrum_head.py'),
                  known_exposure_diagnostic=True, training_performed=False, locked_final_read=False)
    (output/'verification.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    if not all(checks.values()):
        raise RuntimeError('Zero-head equivalence fixture failed')


if __name__ == '__main__':
    main()
