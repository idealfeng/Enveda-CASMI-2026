"""Verify prepared query/mask/split contracts without evaluating model predictions."""
from pathlib import Path
import argparse
import hashlib
import json
import sys

WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    args = parser.parse_args()
    from collections import Counter
    import pyarrow.parquet as pq
    from validation.datasets import QUERY_ADDUCTS, _digest_json, _raw_key, file_sha256, spectrum_digest
    from validation.metric import assert_official_rdkit, identity

    version = assert_official_rdkit()
    root = args.manifest.resolve().parent
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    query = pq.read_table(root / manifest['queries_file']).to_pylist()
    truth = pq.read_table(root / manifest['truth_parquet_file']).to_pylist()
    splits = json.loads((root / manifest['splits_file']).read_text(encoding='utf-8'))
    blocked = json.loads((root / manifest['reference_exclusion_keys_file']).read_text(encoding='utf-8'))
    exclusion = pq.read_table(root / manifest['reference_exclusion_rows_file']).to_pylist()
    duplicates = pq.read_table(root / manifest['query_duplicate_exclusion_rows_file']).to_pylist()
    final_ids = {row['official_identity'] for row in splits['cross_final_locked']}
    active_ids = {row['official_identity'] for row in truth}
    query_ids = {row['molecule_id'] for row in query}
    truth_by_id = {row['molecule_id']: row for row in truth}
    source_rows = {row['source_row'] for row in query}
    masked = {row['source_row'] for row in exclusion}
    duplicate_masked = {row['source_row'] for row in duplicates}
    assert query_ids == set(manifest['active_ids']) == set(truth_by_id)
    assert len(query_ids) == manifest['processed_molecules']
    assert len(query) == manifest['query_spectra']
    assert source_rows <= masked and source_rows <= duplicate_masked
    assert active_ids.isdisjoint(final_ids)
    assert {row['official_identity'] for row in query}.isdisjoint(final_ids)
    assert all(identity(row['smiles']) == row['official_identity'] for row in truth)
    assert all(identity(row['normalized_smiles']) == row['official_identity'] for row in query)
    assert _digest_json({k: v for k, v in splits.items() if k != 'split_sha256'}) == manifest['split_sha256'] == splits['split_sha256']
    assert set(row['adduct'] for row in query) <= set(QUERY_ADDUCTS)
    assert all(row['official_identity'] == truth_by_id[row['molecule_id']]['official_identity'] for row in query)
    assert all(spectrum_digest(row['ms2_mzs'], row['ms2_normalized_intensities'], row['adduct'], row['precursor_mz'], row['ionization_mode']) == row['spectrum_sha256'] for row in query)
    for name, digest in manifest['artifact_sha256'].items():
        assert file_sha256(root / name) == digest, 'Artifact changed: ' + name
    train = Path(manifest['train']['path'])
    assert train.stat().st_size == manifest['train']['bytes']
    assert train.stat().st_mtime_ns == manifest['train']['mtime_ns']
    # Independently verify all metadata rows belonging to blocked raw families are masked,
    # including unsupported training adducts. No final query peaks or predictions are read.
    reader = pq.ParquetFile(train)
    blocked_raw = set(blocked['blocked_raw_keys'])
    expected = set()
    all_adducts_masked = Counter()
    offset = 0
    for batch in reader.iter_batches(batch_size=16384, columns=['inchikey14', 'normalized_smiles', 'adduct'], use_threads=False):
        data = batch.to_pydict()
        for index, (raw, smiles, adduct) in enumerate(zip(data['inchikey14'], data['normalized_smiles'], data['adduct'])):
            if _raw_key(raw, smiles) in blocked_raw:
                expected.add(offset + index)
                all_adducts_masked[str(adduct)] += 1
        offset += batch.num_rows
    assert expected <= masked
    expected |= duplicate_masked
    assert expected == masked
    # Verify every original field at each frozen source_row, including peaks and CE.
    # Only active query rows are materialized; no locked query dataset is generated.
    query_by_row = {row['source_row']: row for row in query}
    source_verified = set()
    offset = 0
    original_columns = reader.schema_arrow.names
    for batch in reader.iter_batches(batch_size=4096, use_threads=False):
        local_rows = [row - offset for row in source_rows if offset <= row < offset + batch.num_rows]
        for local in local_rows:
            current = offset + local
            original = {column: batch.column(batch.schema.get_field_index(column))[local].as_py() for column in original_columns}
            saved = {column: query_by_row[current][column] for column in original_columns}
            assert _digest_json(original) == _digest_json(saved), 'Original metadata/peaks changed at source_row ' + str(current)
            source_verified.add(current)
        offset += batch.num_rows
    assert source_verified == source_rows
    groups = {}
    for row in query:
        group = groups.setdefault(row['molecule_id'], {'spectra': 0, 'adducts': set(), 'modes': set(), 'energies': set()})
        group['spectra'] += 1; group['adducts'].add(row['adduct']); group['modes'].add(str(row['ionization_mode']))
        group['energies'].add(json.dumps(row['collision_energy_ev']))
    selection = json.loads((root / manifest['query_selection_audit_file']).read_text(encoding='utf-8'))
    report = {'status': 'passed', 'scope': 'Dataset integrity and reference-mask contracts only; no model metric or final-holdout evaluation.',
              'metric_rdkit': version, 'manifest_sha256': file_sha256(args.manifest),
              'molecules': len(query_ids), 'query_spectra': len(query), 'class2_masked_rows': len(masked),
              'class1_query_duplicate_masked_rows': len(duplicate_masked), 'all_raw_family_rows_masked': True,
              'original_source_rows_verified': len(source_verified), 'all_original_columns_and_peaks_exact': True,
              'reference_mask_adduct_counts': dict(all_adducts_masked), 'query_adduct_counts': dict(Counter(row['adduct'] for row in query)),
              'multi_spectrum_molecules': sum(g['spectra'] > 1 for g in groups.values()),
              'multi_adduct_molecules': sum(len(g['adducts']) > 1 for g in groups.values()),
              'dual_polarity_molecules': sum(len(g['modes']) > 1 for g in groups.values()),
              'multi_energy_molecules': sum(len(g['energies']) > 1 for g in groups.values()),
              'selection_cap_dropped_spectra': sum(row['dropped_by_development_cap'] for row in selection['molecules']),
              'selection_dropped_polarity_molecules': sum(row['available_polarities'] != row['selected_polarities'] for row in selection['molecules']),
              'final_locked_identities': len(final_ids), 'final_locked_active_intersection': len(active_ids & final_ids),
              'final_locked_prediction_or_metric_read': False,
              'validation_status': manifest['validation_status'], 'training_exposure': manifest['training_exposure']}
    destination = root / 'dataset_integrity_report.json'
    destination.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
