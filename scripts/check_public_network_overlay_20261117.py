"""Actual public-network component checks, without truth or efficacy metrics."""
from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'runs/public_network_canary_20261117'
MODULE = ROOT / 'scripts/public_network_overlay_20261117.py'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def main():
    sys.path.insert(0, str(ROOT / '.cache/rdkit-official-linux-2026033'))
    import pandas as pd
    import numpy as np
    import rdkit
    if rdkit.__version__ != '2026.03.3':
        raise ValueError('Official RDKit required')
    spec = importlib.util.spec_from_file_location('public_network_component', MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if OUT.exists():
        raise FileExistsError('Preserve earlier component execution')
    OUT.mkdir(parents=True)
    results = {}
    cases = []

    # Existing production output, not a rerun of its producing pipeline. Project
    # query observations at the parquet read; never load target metadata fields.
    old = ROOT / 'runs/generation_production_20261113_r2/kaggle/working'
    folder = OUT / 'existing_production2'
    input_root = folder / 'input'
    work = folder / 'working'
    input_root.mkdir(parents=True)
    work.mkdir()
    source = pd.read_csv(old / 'submission.csv', dtype=str, keep_default_na=False)
    queries = pd.read_parquet(old / 'effective_query_spectra.parquet', columns=module.QUERY_COLUMNS)
    queries.to_parquet(input_root / 'test.parquet', index=False)
    shutil.copy2(old / 'submission.csv', work / 'submission.csv')
    save(folder / 'input_provenance.json', dict(
        source_csv=str((old / 'submission.csv').relative_to(ROOT)), source_csv_sha256=sha(old / 'submission.csv'),
        source_queries=str((old / 'effective_query_spectra.parquet').relative_to(ROOT)),
        query_columns_projected=module.QUERY_COLUMNS, labels_read=False,
        historical_generation_output_not_exact_current_champion=True,
        full_producing_pipeline_reexecuted=False))
    cases.append(('existing_production2', folder, input_root, work, source))

    # Deliberately constructed topology fixture: exact measured-peak equality
    # creates an edge. Candidate order is an engineering fixture, not a truth
    # statement and not evidence that public-test ranking will improve.
    folder = OUT / 'synthetic_edge_fixture'
    input_root, work = folder / 'input', folder / 'working'
    input_root.mkdir(parents=True)
    work.mkdir()
    a = ['CCCCCCCC', 'Oc1ccccc1'] + ['C' * count for count in range(2, 26) if count != 8]
    b = ['Oc1ccccc1', 'COc1ccccc1', 'Oc1ccc(O)cc1', 'CCc1ccccc1O', 'CCOc1ccccc1'] + ['C' * count for count in range(2, 22)]
    source = pd.DataFrame([('fixture_a', ';'.join(a)), ('fixture_b', ';'.join(b))], columns=['molecule_id', 'smiles'])
    source.to_csv(work / 'submission.csv', index=False)
    rows = []
    for mid in source.molecule_id:
        rows.append(dict(molecule_id=mid, spectrum_id=mid + '_spectrum', instrument_type='timsTOF',
            adduct='[M+H]+', collision_energy_ev=30., precursor_mz=700.,
            ms2_mzs=np.asarray([50., 75., 100., 125., 150., 175., 200., 250., 300., 350.]),
            ms2_normalized_intensities=np.asarray([.2, .3, .8, .6, .5, 1., .7, .4, .3, .6])))
    pd.DataFrame(rows, columns=module.QUERY_COLUMNS).to_parquet(input_root / 'test.parquet', index=False)
    save(folder / 'input_provenance.json', dict(
        synthetic_engineering_fixture=True, labels_present=False, true_candidate_designation=None,
        tests='Nonzero topology, actual network-score consumption, head movement allowed, exact upstream adapter parity',
        gain_or_model_accuracy_claim=False))
    cases.append(('synthetic_edge_fixture', folder, input_root, work, source))

    for name, folder, input_root, work, source in cases:
        parent = dict(status='passed', mode='hidden_full', csv_sha256=sha(work / 'submission.csv'),
                      scope='Canary-only input-byte binding; not full parent inference validation')
        save(folder / 'parent_component_binding.json', parent)
        audit = module.run(work, input_root, True, source.molecule_id.tolist(), parent,
                           'network_component_check', '0' * 64)
        if audit['status'] != 'passed' or not all(value is True for value in audit['checks'].values()):
            raise ValueError('Actual component audit failed')
        direct = folder / 'direct_original'
        direct.mkdir()
        shutil.copy2(work / 'network_control.csv', direct / 'submission.csv')
        scope = {}
        exec(compile(module.ROGERS_FUNCTION_SOURCE, 'original_rogers_function_control', 'exec'), scope)
        log = io.StringIO()
        with redirect_stdout(log):
            scope['_n1c'](work=str(direct), inp=str(input_root), LAM=.35, TAU=.6)
        (direct / 'stdout.log').write_text(log.getvalue(), encoding='utf-8')
        expected = pd.read_csv(direct / 'submission.csv', dtype=str, keep_default_na=False)
        actual = pd.read_csv(work / 'submission.csv', dtype=str, keep_default_na=False)
        if not actual.equals(expected):
            raise ValueError('Adapter output differs from unchanged upstream algorithm')
        if name == 'synthetic_edge_fixture':
            if audit['actual_network_summary']['edges'] < 1 or audit['changed_queries'] < 1 or audit['changed_top1'] < 1:
                raise ValueError('Synthetic fixture did not exercise actual head movement')
        results[name] = dict(
            summary=audit['actual_network_summary'], changed_queries=audit['changed_queries'],
            changed_top1=audit['changed_top1'], elapsed_seconds=audit['elapsed_seconds'],
            adapter_matches_direct_original=True, component_audit_sha256=sha(work / 'network_audit.json'),
            before_sha256=audit['control_sha256'], output_sha256=audit['csv_sha256'])
    receipt = dict(status='passed_actual_network_component_and_upstream_output_parity',
        module_sha256=sha(MODULE), normalized_utf8_function_sha256=module.ROGERS_FUNCTION_SHA256,
        official_rdkit_version=rdkit.__version__, cases=results,
        truth_labels_read=False, efficacy_metrics_computed=False, full_champion_initialization_executed=False,
        synthetic_fixture_is_not_scientific_evidence=True, threshold_or_coefficient_search=False,
        cloud_runs_or_competition_submissions_performed=False)
    save(OUT / 'verification.json', receipt)
    print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    main()
