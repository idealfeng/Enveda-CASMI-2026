V43_DATASET_SOURCES = ['dmitriigluzdov/casmi26-attributed-v4g-reproduction-assets', 'dmitriigluzdov/casmi26-pubchem-popularity-prior', 'dmitriigluzdov/casmi26-natural-product-panel-benchmark', 'dmitriigluzdov/casmi26-natural-product-knowledge-table', 'dmitriigluzdov/casmi26-fold-safe-fpnet']
V43_E006_SHA256 = 'ee55b55c7f5bdb08f1a8154396b18fdb0203fb7178b3a52429e0999e69ad7e53'
# Read the final E006 file; validate it without changing its bytes or candidate order.
def _v43_receipt(scope):
    import hashlib
    import json
    import os
    import time
    from pathlib import Path
    import pandas as pd
    import rdkit

    def digest(path):
        path = Path(path)
        h = hashlib.sha256()
        with path.open('rb') as source:
            for block in iter(lambda: source.read(8 * 1024 * 1024), b''):
                h.update(block)
        return dict(path=str(path), bytes=path.stat().st_size, sha256=h.hexdigest())

    final_path = Path('submission.csv')
    final_before = digest(final_path)
    frame = pd.read_csv(final_path, dtype=str, keep_default_na=False)
    sample = pd.read_csv(Path(scope['COMP']) / 'sample_submission.csv', dtype=str)
    assert list(frame.columns) == ['molecule_id', 'smiles']
    assert frame.molecule_id.tolist() == sample.molecule_id.tolist()
    assert frame.molecule_id.is_unique and frame.smiles.notna().all()
    processed = set(scope['te'].molecule_id.astype(str))
    inputs = set(scope['E004_PREFLIGHT']['input_ids'])
    assert processed == (inputs if scope['IS_RERUN'] else set(sorted(inputs)[:scope['SMOKE_N']]))
    for mid, answer in frame.itertuples(index=False):
        guesses = answer.split(';')
        assert 1 <= len(guesses) <= 25, mid
        identities = [scope['metric_identity'](s) for s in guesses]
        assert None not in identities and len(set(identities)) == len(identities), mid
    assert scope['n_err'] == 0
    assert scope['FACTORIAL_REPORT']['same_run_control_reconstructed']
    assert scope['FACTORIAL_REPORT']['submission_sha256'] == scope['RANK2_REPORT']['control_sha256']
    assert scope['RANK2_REPORT']['submission_sha256'] == final_before['sha256']

    # Hash all files of the mounted public datasets plus the competition files read.
    # The inventory records content hashes, including model arrays and source modules.
    roots = {str(Path(scope['E004_PREFLIGHT']['runtime_input_path']).resolve())}
    input_root = Path('/kaggle/input')
    dataset_roots = set()
    for slug in V43_DATASET_SOURCES:
        owner, name = slug.split('/', 1)
        direct = input_root / name
        if direct.is_dir():
            dataset_roots.add(direct.resolve())
        else:
            dataset_roots.update(p.resolve() for p in (input_root / 'datasets' / owner).glob(name) if p.is_dir())
    mounted = sorted({p.resolve() for root in dataset_roots for p in root.rglob('*') if p.is_file()})
    comp_root = Path(scope['E004_PREFLIGHT']['runtime_input_path'])
    mounted = sorted(set(mounted) | {comp_root.joinpath(name).resolve() for name in
                                    ('train.parquet', 'test.parquet', 'sample_submission.csv')})
    def quick_digest(path, limit=32 << 20, edge=4 << 20):
        path = Path(path)
        size = path.stat().st_size
        if size <= limit:
            return dict(digest(path), full=True)
        h = hashlib.sha256()
        with path.open('rb') as source:
            h.update(source.read(edge))
            source.seek(size - edge)
            h.update(source.read(edge))
        return dict(path=str(path), bytes=size, sha256_head_tail=h.hexdigest(), full=False)

    input_hashes = [quick_digest(path) for path in mounted]   # large files: size + head/tail hash (full reads took > 2 h)
    assert len(dataset_roots) == len(V43_DATASET_SOURCES), (len(dataset_roots), len(V43_DATASET_SOURCES))
    Path('v43_mounted_input_hashes.json').write_text(json.dumps(input_hashes, indent=2) + '\n')
    stages = scope['E004_REPORT']['stages']
    result = dict(
        version=49, method='canqiang_E006_window40_ice_fallback_plus_v7c_fragment_gap_plus_e2_rank2_rel150_e2_bags_chebi_lmsd_pubchem_spectral_bonus_np_bonus_pubchemlite_lotus_refs_depth6_poplam015_fold0_n1a_syn050_pcdelta_extlib_n1challenger_jointicegl',
        source_notebook_sha256=V43_E006_SHA256,
        determinism=scope.get('V43_DETERMINISM', {'applied': False}),
        rdkit=rdkit.__version__, output_rows=len(frame), input_molecules=len(inputs),
        processed_molecules=len(processed), processed_ids=sorted(processed),
        scoring_rerun=bool(scope['IS_RERUN']), smoke_n=int(scope['SMOKE_N']),
        placeholder_rows=len(inputs - processed), main_errors=int(scope['n_err']),
        main_lists=len(scope['BASE']), engine2_lists=len(scope['ENG']), pubchem_lists=len(scope['PC']),
        engine2_nonempty=sum(bool(scope['ENG'].get(mid, {}).get('smiles')) for mid in processed),
        pubchem_nonempty=sum(bool(scope['PC'].get(mid, {}).get('pc')) for mid in processed),
        merge=scope['stats'], stages=stages,
        final_overlay=scope['FACTORIAL_REPORT'], rank2_overlay=scope['RANK2_REPORT'],
        pubchem_fpnet_ensemble=dict(models='A+B+fold0', fold0_weight=0.3333333333333333, raw_logit_scale=1.5, fold0_path=scope['FOLD0_PATH']),
        mounted_datasets=V43_DATASET_SOURCES, mounted_files=len(input_hashes),
        mounted_input_inventory=digest('v43_mounted_input_hashes.json'),
        train=digest(comp_root / 'train.parquet'), test=digest(comp_root / 'test.parquet'),
        processed_test=digest(Path(scope['COMP']) / 'test.parquet'),
        submission=final_before, source_manifest=digest(Path(scope['V4MOD']) / 'MANIFEST.json'),
        elapsed_seconds=round(time.time() - scope['T0'], 2),
        notebook_elapsed_seconds=round(time.monotonic() - scope['NOTEBOOK_STARTED'], 2),
    )
    assert digest(final_path)['sha256'] == final_before['sha256']
    Path('v43_execution_receipt.json').write_text(json.dumps(result, indent=2, default=str) + '\n')
    print('V43_EXECUTION_RECEIPT', json.dumps({k: result[k] for k in
          ('output_rows', 'processed_molecules', 'placeholder_rows', 'main_errors', 'elapsed_seconds')}))
    return result

V43_RECEIPT = _v43_receipt(globals())
del _v43_receipt
