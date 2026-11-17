"""Two public synthetic-condition SMILES, no spectrum labels or CASMI hidden data."""
from pathlib import Path
import argparse
import hashlib
import importlib.metadata
import json
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
ASSET = ROOT / 'assets/research/fiora_os_20261115'
SOURCE = ASSET / 'source_checkout'
TARGET = ASSET / 'dependencies-linux'
OUT = ROOT / 'runs/fiora_os_canary_20261115/attempt2'
REPORT = ROOT / 'reports/new_paradigm_20261115/fiora_canary_attempt2.json'
sys.path[:0] = [str(SOURCE), str(TARGET)]

def main():
    start = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)
    report = {'status': 'RUNNING', 'device': 'cpu', 'labels_used': False,
              'hidden_data_used': False, 'environment_modified': False,
              'source_commit': 'e19ef82c9a6cb9dbac92bce23e914008f1aeb44e',
              'model': 'FIORA OS v1.0.0', 'dependency_target': str(TARGET),
              'scope': 'component forward only; no ranking or timsTOF domain claim'}
    report['script_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    try:
        import numpy as np
        import pandas as pd
        import torch
        import torch_geometric
        from rdkit import Chem
        from fiora.GNN.FioraModel import FioraModel
        from fiora.cli.predict import build_metabolites
        from fiora.MS.SimulationFramework import SimulationFramework
        report['import_seconds'] = time.perf_counter() - start
        print(json.dumps({'stage': 'imported', 'seconds': report['import_seconds']}), flush=True)
        report['torch_version'] = torch.__version__
        report['torch_geometric_version'] = torch_geometric.__version__
        report['dependency_versions'] = {}
        for name in ['torch-geometric', 'treelib', 'dill', 'aiohttp', 'xxhash', 'regex', 'six']:
            try:
                report['dependency_versions'][name] = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                report['dependency_versions'][name] = None
        torch.set_num_threads(4)
        params_path = SOURCE / 'fiora/resources/models/fiora_OS_v1.0.0_params.json'
        state_path = SOURCE / 'fiora/resources/models/fiora_OS_v1.0.0_state.pt'
        report['state_sha256'] = hashlib.sha256(state_path.read_bytes()).hexdigest()
        assert report['state_sha256'] == '83221e187991f116a8aed1bf272dd656cf31721a177dcbb0239f414c8df31a0e'
        params = json.loads(params_path.read_text())
        assert params['training_library'] == 'MSnLib v7'
        report['model_conditions'] = params['setup_features_categorical_set']
        stage = time.perf_counter()
        state = torch.load(state_path, map_location='cpu', weights_only=True)
        model = FioraModel(params)
        matched = model.load_state_dict(state, strict=True)
        model.eval()
        report['state_load'] = {'strict': True, 'state_keys': len(state),
                                'missing_keys': list(matched.missing_keys),
                                'unexpected_keys': list(matched.unexpected_keys),
                                'parameters': sum(p.numel() for p in model.parameters()),
                                'seconds': time.perf_counter() - stage}
        print(json.dumps({'stage': 'strict_loaded', **report['state_load']}), flush=True)
        # Same-formula positional isomers avoid passing a trivial mass difference canary.
        records = [
            {'Name': 'canary_caffeic_acid', 'SMILES': 'O=C(O)/C=C/c1ccc(O)c(O)c1',
             'Precursor_type': '[M-H]-', 'CE': 35.0, 'Instrument_type': 'HCD'},
            {'Name': 'canary_24_dihydroxycinnamic_acid', 'SMILES': 'O=C(O)/C=C/c1ccc(O)cc1O',
             'Precursor_type': '[M-H]-', 'CE': 35.0, 'Instrument_type': 'HCD'},
        ]
        canonical = [Chem.MolToSmiles(Chem.MolFromSmiles(x['SMILES'])) for x in records]
        assert len(set(canonical)) == 2
        pd.DataFrame(records).to_csv(OUT / 'input.csv', index=False)
        stage = time.perf_counter()
        frame, invalid = build_metabolites(pd.DataFrame(records), params)
        assert len(invalid) == 0 and len(frame) == 2
        report['graph_prepare_seconds'] = time.perf_counter() - stage
        print(json.dumps({'stage': 'graphs_prepared', 'seconds': report['graph_prepare_seconds']}), flush=True)
        framework = SimulationFramework(model, dev='cpu')
        results, raw_vectors, spectra = [], [], []
        with torch.inference_mode():
            for i, row in frame.iterrows():
                stage = time.perf_counter()
                mol = row['Metabolite']
                pred = framework.predict_metabolite_property(mol, model, as_batch=True)
                raw = pred['fragment_probs'].detach().cpu().numpy()
                assert np.isfinite(raw).all()
                setattr(mol, 'canary_pred', pred['fragment_probs'])
                peaks = framework.simulate_spectrum(mol, 'canary_pred',
                    precursor_mode=row['Precursor_type'], min_intensity=0.001)
                elapsed = time.perf_counter() - stage
                mz = np.asarray(peaks['mz'], dtype=float)
                intensity = np.asarray(peaks['intensity'], dtype=float)
                assert len(mz) > 1 and np.isfinite(mz).all() and np.isfinite(intensity).all()
                assert (mz > 0).all() and (intensity >= 0).all() and np.std(intensity) > 0
                np.save(OUT / (row['Name'] + '_raw.npy'), raw, allow_pickle=False)
                result = {'name': row['Name'], 'smiles': row['SMILES'],
                          'canonical_smiles': canonical[i], 'formula': mol.Formula,
                          'raw_shape': list(raw.shape), 'raw_std': float(raw.std()),
                          'raw_min': float(raw.min()), 'raw_max': float(raw.max()),
                          'peaks': len(mz), 'mz': mz.tolist(), 'intensity': intensity.tolist(),
                          'forward_and_peak_seconds': elapsed}
                results.append(result)
                print(json.dumps({'stage': 'predicted', 'name': row['Name'], 'peaks': len(mz), 'seconds': elapsed}), flush=True)
                raw_vectors.append(raw)
                spectra.append(peaks)
        report['queries'] = results
        assert results[0]['formula'] == results[1]['formula']
        report['same_formula'] = results[0]['formula']
        report['raw_shapes_equal'] = raw_vectors[0].shape == raw_vectors[1].shape
        if report['raw_shapes_equal']:
            max_delta = float(np.max(np.abs(raw_vectors[0] - raw_vectors[1])))
            report['max_abs_raw_delta'] = max_delta
            assert max_delta > 1e-6, 'Near-constant response on two structural isomers'
        report['spectra_equal'] = (spectra[0]['mz'] == spectra[1]['mz']
                                   and spectra[0]['intensity'] == spectra[1]['intensity'])
        assert not report['spectra_equal']
        with (OUT / 'predictions.mgf').open('w') as handle:
            for row in results:
                handle.write('BEGIN IONS\nTITLE=' + row['name'] + '\nSMILES=' + row['smiles']
                             + '\nPRECURSORTYPE=[M-H]-\nINSTRUMENTTYPE=HCD\nCOLLISIONENERGY=35\n')
                for mz, intensity in zip(row['mz'], row['intensity']):
                    handle.write(f'{mz:.8f} {intensity:.8f}\n')
                handle.write('END IONS\n')
        report['status'] = 'COMPONENT_FORWARD_PASSED'
    except Exception as exc:
        report['status'] = 'FAILED'
        report['error_type'] = type(exc).__name__
        report['error'] = str(exc)
        report['traceback'] = traceback.format_exc()
    report['total_seconds'] = time.perf_counter() - start
    REPORT.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k not in ['queries', 'traceback']}, indent=2))
    if report['status'] != 'COMPONENT_FORWARD_PASSED':
        raise SystemExit(1)

if __name__ == '__main__':
    main()
