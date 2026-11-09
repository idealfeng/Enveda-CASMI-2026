"""Exercise prepared observers with tiny feature fixtures, never a model or Kaggle call."""
from contextlib import redirect_stdout
from pathlib import Path
import io
import json
import tempfile

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT/'submission/public_tri_cloud_20261106'


def main():
    import numpy as np
    import pandas as pd
    expected = json.loads((STAGE/'prepare_receipt.json').read_text())['expected_inputs']
    preflight = (STAGE/'public_neural_preflight.py').read_text()
    postflight = (STAGE/'public_neural_postflight.py').read_text()
    kit = ROOT/'assets/kaggle/sanpier/casmi-spectrum-model-v1/v1/casmi_spectrum_model_v1'
    with tempfile.TemporaryDirectory(prefix='public-tri-guard-fixture-', dir=ROOT/'.cache/tmp-linux') as temp:
        base = Path(temp)
        results = []
        for kind in ('visible', 'hidden_common_unsupported', 'hidden_coverage_mismatch'):
            work = base/kind
            work.mkdir()
            inputs = work/'input'
            for name, model in expected['models'].items():
                source = ROOT/'assets/kaggle/bgunshui'/model['dataset_slug']/'v1'
                folder = inputs/model['dataset_slug']
                folder.mkdir(parents=True)
                for file in ('final_model.pt','config_used.json'):
                    (folder/file).symlink_to(source/file)
            folder = inputs/'casmi26-lotus-candidates'
            folder.mkdir(parents=True)
            (folder/'candidates_lotus.parquet').symlink_to(ROOT/'assets/kaggle/qwertykeypadapple/casmi26-lotus-candidates/v2/candidates_lotus.parquet')
            active_count = 12 if kind == 'visible' else 2
            count = 13 if kind == 'visible' else 2
            sample = ['fixture_'+str(i) for i in range(count)]
            frames = {}
            for name in ('public','v2','v4'):
                rows = []
                for i, mid in enumerate(sample):
                    processed = i < active_count
                    usable = processed and (kind == 'visible' or i == 0)
                    if kind == 'hidden_coverage_mismatch' and name == 'v2' and i == 0:
                        usable = False
                    scores = {'public': [1.,3.], 'v2': [4.,2.], 'v4': [2.,8.]}[name] if usable else [0.,0.]
                    for smile, value in zip(('CCO','CCC'), scores):
                        rows.append(dict(molecule_id=mid,smiles=smile,processed=processed,
                            neural_ok=usable,neural_score=value))
                frame = pd.DataFrame(rows)
                frame['neural_score'] = frame.neural_score.astype(np.float32)
                frame.to_parquet(work/('neural_'+name+'.parquet'), index=False)
                frames[name] = frame
            main = frames['public'].copy()
            main['neural_ok'] = frames['public'].neural_ok & frames['v2'].neural_ok & frames['v4'].neural_ok
            main['neural_score'] = np.asarray([(-.5 if j%2 == 0 else .5) if bool(main.processed.iloc[j])
                and (kind == 'visible' or j < 2) else 0. for j in range(len(main))], dtype=np.float32)
            main.to_parquet(work/'neural_candidate_features.parquet', index=False)
            pd.DataFrame({'molecule_id': sample[:active_count]}).to_parquet(work/'effective_query_spectra.parquet', index=False)
            pd.DataFrame({'molecule_id': sample, 'smiles': ['CCO;CCC']*count}).to_csv(work/'submission.csv', index=False)
            scope = dict(expected['flags'], ROOT=work, INPUT=inputs, RUN_PIPELINE=True,
                BUNDLE=kit, PUB_BUNDLE=kit,
                V2_BUNDLE=ROOT/'assets/kaggle/bgunshui/casmi26-scorer-v2-model/v1',
                V4_BUNDLE=ROOT/'assets/kaggle/bgunshui/casmi26-scorer-v4-model/v1',
                PIPELINE_DONE=True,NEURAL_OK=True,V2_OK=True,V4_OK=True,OUTSIDERS_OK=False,
                SAMPLE_IDS=sample, IS_RERUN=kind != 'visible',
                identity_map=lambda: {'CCO':'LFQSCWFLJHTTHZ','CCC':'ATUOYWHBWRKTHZ'})
            exec(compile(preflight, '<preflight-fixture>', 'exec'), scope)
            rejected = False
            try:
                with redirect_stdout(io.StringIO()):
                    exec(compile(postflight, '<postflight-fixture>', 'exec'), scope)
            except AssertionError:
                rejected = True
            audit = json.loads((work/'public_neural_execution_audit.json').read_text())
            if kind == 'hidden_coverage_mismatch':
                assert rejected and audit['checks']['new_model_coverage_equals_public'] is False
            else:
                assert not rejected and audit['status'] == 'passed'
                assert audit['combined_score_max_abs_difference'] == 0
                assert audit['active_identity_diagnostics']['checked_molecules'] == active_count
                if kind != 'visible':
                    assert audit['models']['public']['unsupported_molecules'] == ['fixture_1']
            results.append(dict(fixture=kind, passed=True, expected_rejection=rejected))
    report = dict(status='passed', tests=results, model_execution=False, network_or_cloud_write=False)
    (STAGE/'observer_fixture_checks.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
