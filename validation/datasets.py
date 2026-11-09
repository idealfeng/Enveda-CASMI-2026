"""Bounded-memory preparation of identity-isolated diagnostic queries.

No model code is imported. The input train file and existing shared caches are
read-only; every generated artifact belongs to a new output directory.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import gc
import hashlib
import json
import struct
import time

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from .metric import assert_official_rdkit, heavy_atom_composition, identity

NP_SOURCE = 'enveda-np-examples'
CROSS_SOURCES = ('riken', 'gnps', 'massbank', 'mona', 'pluskal_ms2', 'spectraverse', 'msdial', 'enveda-180')
META_COLUMNS = ['inchikey14', 'normalized_smiles', 'molecular_formula', 'ingest_lib', 'instrument_type']
# The competition's supported query adducts. Reference masks never use this filter.
QUERY_ADDUCTS = ('[M+H]+', '[M+NH4]+', '[M-H2O+H]+', '[M-2H2O+H]+', '[M+Na]+',
                 '[M+K]+', '[M-H]-', '[M-H2O-H]-', '[M+CH2O2-H]-', '[M+Cl]-')


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def _digest_json(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def training_exposure() -> dict:
    """Producer declarations; reference isolation does not undo trained weights."""
    return {'FPNet_full1': {'status': 'declared_seen_all_train',
                'evidence': 'third_party/prvsiyan_analog/dataset_metadata/ahmedberatozer__casmi26-fpnet-full1__view.json'},
            'Saner_final_model': {'status': 'declared_full_data_refit_including_former_validation',
                'evidence': 'assets/kaggle/sanpier/casmi-spectrum-model-v1/v1/casmi_spectrum_model_v1/training_result.json',
                'evidence_field': 'final_model_training',
                'declaration': 'full data, including former validation identities; DO NOT evaluate this model on that holdout',
                'checkpoint': 'final_model.pt',
                'checkpoint_sha256': '44436b2daec64373e66f9120dd2389c24fc83dd9430ebeeac18e3cb49dcb9642'},
            'fold0_FPNet': {'status': 'declared_np_panel_excluded_only', 'does_not_establish_full_stack_cleanliness': True},
            'other_public_models_rankers': {'status': 'unknown_membership'}}


def _raw_key(raw, smiles) -> str:
    if isinstance(raw, str) and raw:
        return raw
    return 'missing:' + hashlib.sha256(str(smiles).encode()).hexdigest()[:24]


def _stable_sort(value: str, seed: int) -> str:
    return hashlib.sha256(f'{seed}:{value}'.encode()).hexdigest()


def scan_structure_catalog(train: Path, batch_size: int = 16384) -> tuple[dict, dict]:
    """Keep unique structural strings and small counts, never all spectra in RAM."""
    catalog = {}
    sources = Counter()
    rows = 0
    reader = pq.ParquetFile(train)
    for batch_index, batch in enumerate(reader.iter_batches(batch_size=batch_size, columns=META_COLUMNS + ['adduct'], use_threads=False)):
        data = batch.to_pydict()
        for raw, smiles, formula, source, instrument, adduct in zip(*(data[c] for c in META_COLUMNS + ['adduct'])):
            token = _raw_key(raw, smiles)
            record = catalog.setdefault(token, {'variants': {}, 'sources': Counter(), 'query_eligible_sources': Counter()})
            variant = record['variants'].setdefault(smiles or '', {'sources': Counter(), 'formulas': set(), 'query_eligible_sources': Counter()})
            variant['sources'][source or '<missing>'] += 1
            if adduct in QUERY_ADDUCTS:
                variant['query_eligible_sources'][source or '<missing>'] += 1
                record['query_eligible_sources'][source or '<missing>'] += 1
            if formula:
                variant['formulas'].add(formula)
            record['sources'][source or '<missing>'] += 1
            sources[source or '<missing>'] += 1
        rows += batch.num_rows
        if batch_index % 32 == 0:
            print(f'METADATA rows={rows} raw_structures={len(catalog)}', flush=True)
    return catalog, {'rows': rows, 'raw_keys': len(catalog), 'unique_raw_smiles_pairs': sum(len(r['variants']) for r in catalog.values()), 'source_counts': dict(sources)}


def freeze_splits(catalog: dict, seed: int, cross_dev: int = 200, cross_final: int = 250) -> dict:
    """Freeze NP identities plus source-balanced cross-library development/final IDs."""
    np_records = {}
    for raw, record in catalog.items():
        if NP_SOURCE not in record['sources']:
            continue
        for smiles, variant in record['variants'].items():
            if NP_SOURCE not in variant['sources']:
                continue
            key = identity(smiles)
            if key is None:
                raise ValueError(f'NP truth is invalid under official identity: {raw}')
            item = np_records.setdefault(key, {'official_identity': key, 'smiles': smiles, 'query_source': NP_SOURCE, 'raw_keys': [], 'panel': 'np'})
            if raw not in item['raw_keys']:
                item['raw_keys'].append(raw)
    np_keys = set(np_records)
    by_source = {source: [] for source in CROSS_SOURCES}
    for raw, record in catalog.items():
        if NP_SOURCE in record['sources']:
            continue
        available = [source for source in CROSS_SOURCES if source in record['sources']]
        if not available:
            continue
        # A unique source assignment avoids favoring structures represented in many libraries.
        source = min(available, key=lambda s: _stable_sort(raw + ':' + s, seed))
        by_source[source].append(raw)
    for source, raw_keys in by_source.items():
        raw_keys.sort(key=lambda raw: _stable_sort(raw, seed))
    offsets = Counter()
    selected = []
    seen = set(np_keys)
    while len(selected) < cross_dev + cross_final:
        progress = False
        for source in CROSS_SOURCES:
            raw_keys = by_source[source]
            while offsets[source] < len(raw_keys):
                raw = raw_keys[offsets[source]]
                offsets[source] += 1
                candidates = [smiles for smiles, v in catalog[raw]['variants'].items() if source in v['sources']]
                smiles = min(candidates)
                key = identity(smiles)
                if key is None or key in seen:
                    continue
                selected.append({'official_identity': key, 'smiles': smiles, 'query_source': source, 'raw_keys': [raw], 'panel': 'cross'})
                seen.add(key)
                progress = True
                break
            if len(selected) == cross_dev + cross_final:
                break
        if not progress:
            raise ValueError('Insufficient distinct valid cross-library structures')
    selected.sort(key=lambda item: _stable_sort(item['official_identity'] + ':role', seed))
    np_order = sorted(np_records.values(), key=lambda item: _stable_sort(item['official_identity'], seed))
    result = {'schema_version': 1, 'seed': seed, 'np_diagnostic': np_order,
              'cross_development': selected[:cross_dev], 'cross_final_locked': selected[cross_dev:],
              'final_policy': 'Identity/source manifest only. Do not evaluate or tune on final_locked.'}
    result['split_sha256'] = _digest_json(result)
    return result


def expand_identity_family(catalog: dict, target_ids: set[str], target_smiles: list[str], out: Path) -> tuple[dict, dict]:
    """Heavy composition is computed from every SMILES, never trusted from stored formula.

    Equal official connectivity identities must have equal heavy atom composition.
    H count, charge and stereochemistry are intentionally not prefilters. Unparseable
    structural strings are conservatively blocked from diagnostic references.
    """
    compositions = {heavy_atom_composition(smiles) for smiles in target_smiles}
    if None in compositions:
        raise ValueError('Target heavy composition unavailable')
    blocked = {}
    unknown = []
    checked = 0
    matching_pairs = []
    summary = Counter()
    schema = pa.schema([('raw_inchikey14', pa.string()), ('smiles', pa.string()), ('heavy_composition', pa.string()), ('official_identity', pa.string()), ('canonical_checked', pa.bool_()), ('reference_blocked', pa.bool_())])
    with pq.ParquetWriter(out / 'structure_identity_audit.parquet', schema, compression='zstd') as writer:
        buffer = []
        for index, (raw, record) in enumerate(catalog.items()):
            for smiles, variant in record['variants'].items():
                comp = heavy_atom_composition(smiles)
                key = None
                canonical_checked = comp is not None and comp in compositions
                if comp is None:
                    unknown.append({'raw_inchikey14': raw, 'smiles': smiles})
                    blocked.setdefault(raw, set())
                    summary['unparseable_pairs_conservatively_blocked'] += 1
                elif canonical_checked:
                    checked += 1
                    key = identity(smiles)
                    if key in target_ids:
                        blocked.setdefault(raw, set()).add(key)
                        matching_pairs.append({'raw_inchikey14': raw, 'official_identity': key, 'smiles': smiles})
                        summary['matching_pairs'] += 1
                buffer.append({'raw_inchikey14': raw, 'smiles': smiles, 'heavy_composition': json.dumps(comp) if comp is not None else None,
                               'official_identity': key, 'canonical_checked': canonical_checked, 'reference_blocked': raw in blocked})
                if len(buffer) >= 8192:
                    writer.write_table(pa.Table.from_pylist(buffer, schema=schema)); buffer.clear()
            if index % 25000 == 0:
                print(f'IDENTITY raw_structures={index} canonical_checked={checked} blocked_keys={len(blocked)}', flush=True)
        if buffer:
            writer.write_table(pa.Table.from_pylist(buffer, schema=schema))
    mapping = {'blocked_raw_keys': sorted(blocked), 'blocked_official_identities': sorted(target_ids),
               'identity_by_raw_key': {k: sorted(v) for k, v in blocked.items()}, 'unknown_raw_keys': sorted({x['raw_inchikey14'] for x in unknown}),
               'policy': 'Block official identity families and all unparseable structural keys. Keep true structures in candidate pool.'}
    audit = {'raw_structures_scanned': len(catalog), 'canonical_checked_pairs': checked,
             'heavy_atom_composition_from': 'RDKit parsing of every unique raw-key/SMILES pair; stored molecular_formula is not a correctness gate',
             'full_formula_filter_used': False, 'blocked_raw_keys': len(blocked), 'unknown_pairs': unknown,
             'matching_pairs': matching_pairs, 'exclusion_completeness': 'All parsable structural strings checked by heavy composition; only matching-composition strings need official canonicalization. Unparseable keys conservatively excluded.'}
    return mapping, audit


def _spectrum_metadata_key(adduct, precursor, mode) -> tuple:
    return (str(adduct), struct.pack('<d', float(precursor)) if precursor is not None else b'<null>', str(mode))


def spectrum_digest(mz, intensity, adduct, precursor, mode) -> str:
    """Exact float64 peak-pair multiset and metadata, with no decimal rounding."""
    x = np.asarray(mz if mz is not None else [], dtype='<f8')
    y = np.asarray(intensity if intensity is not None else [], dtype='<f8')
    if x.shape != y.shape:
        raise ValueError('Mismatched peak arrays')
    order = np.lexsort((y, x))
    digest = hashlib.sha256()
    for item in _spectrum_metadata_key(adduct, precursor, mode):
        payload = item if isinstance(item, bytes) else item.encode()
        digest.update(struct.pack('<Q', len(payload))); digest.update(payload)
    digest.update(struct.pack('<Q', len(x)))
    digest.update(x[order].tobytes()); digest.update(y[order].tobytes())
    return digest.hexdigest()


def _batch_peak(batch: pa.RecordBatch, column: str, row: int):
    return batch.column(batch.schema.get_field_index(column))[row].as_py()


def prepare_validation(train: Path, output: Path, *, np_count: int = 24, cross_count: int = 24,
                       cross_dev: int = 200, cross_final: int = 250, seed: int = 20261104,
                       max_spectra: int = 12, batch_size: int = 4096, frozen_splits: Path | None = None) -> dict:
    start = time.monotonic()
    version = assert_official_rdkit()
    train = train.resolve(); output = output.resolve()
    if output.exists():
        raise FileExistsError('Use a fresh output directory to preserve frozen manifests')
    if min(np_count, cross_count) < 0 or np_count + cross_count == 0 or max_spectra < 1 or cross_count > cross_dev or batch_size < 1:
        raise ValueError('Invalid query or split sizes')
    pa.set_cpu_count(4); pa.set_io_thread_count(2)
    output.mkdir(parents=True)
    catalog, inventory = scan_structure_catalog(train)
    if frozen_splits is None:
        splits = freeze_splits(catalog, seed, cross_dev, cross_final)
    else:
        splits = json.loads(frozen_splits.read_text(encoding='utf-8'))
        original_hash = splits['split_sha256']
        if _digest_json({k: v for k, v in splits.items() if k != 'split_sha256'}) != original_hash:
            raise ValueError('Frozen split content hash does not match')
        if splits['seed'] != seed or len(splits['cross_development']) != cross_dev or len(splits['cross_final_locked']) != cross_final:
            raise ValueError('Frozen split sizes/seed differ from requested configuration')
    if np_count > len(splits['np_diagnostic']):
        raise ValueError('np_count exceeds the available official NP identities')
    skipped_query_identities = []
    def eligible_active(pool, count):
        chosen = []
        for item in pool:
            if len(chosen) >= count:
                break
            allowed = False
            for raw in item['raw_keys']:
                record = catalog[raw]
                for smiles, variant in record['variants'].items():
                    if variant['query_eligible_sources'].get(item['query_source'], 0) and identity(smiles) == item['official_identity']:
                        allowed = True
                        break
                if allowed:
                    break
            if allowed:
                chosen.append(dict(item))
            else:
                skipped_query_identities.append({'official_identity': item['official_identity'], 'query_source': item['query_source'],
                                                 'panel': item['panel'], 'reason': 'No spectrum with an official supported query adduct in the frozen query source'})
        if len(chosen) != count:
            raise ValueError('Insufficient eligible query identities in frozen development panel')
        return chosen
    active = eligible_active(splits['np_diagnostic'], np_count) + eligible_active(splits['cross_development'], cross_count)
    active_ids = {item['official_identity'] for item in active}
    final_ids = {item['official_identity'] for item in splits['cross_final_locked']}
    assert not active_ids & final_ids
    for item in active:
        item['molecule_id'] = item['panel'] + '_' + item['official_identity']
    by_identity = {item['official_identity']: item for item in active}
    family, family_audit = expand_identity_family(catalog, active_ids, [x['smiles'] for x in active], output)
    _write_json(output / 'frozen_splits.json', splits)
    _write_json(output / 'class2_exclusion_keys.json', family)
    _write_json(output / 'identity_family_audit.json', family_audit)
    del catalog; gc.collect()
    print('IDENTITY_FAMILIES_READY', len(family['blocked_raw_keys']), flush=True)
    blocked_keys = set(family['blocked_raw_keys'])
    query_candidates = defaultdict(list)
    unsupported_query_rows = Counter()
    unsupported_by_molecule = defaultdict(Counter)
    blocked_rows = {}
    reader = pq.ParquetFile(train)
    columns = META_COLUMNS + ['adduct', 'ionization_mode', 'precursor_mz', 'collision_energy_ev']
    source_row = 0
    for batch in reader.iter_batches(batch_size=16384, columns=columns, use_threads=False):
        data = batch.to_pydict()
        for j in range(batch.num_rows):
            raw = _raw_key(data['inchikey14'][j], data['normalized_smiles'][j])
            if raw not in blocked_keys:
                continue
            current = source_row + j
            source = data['ingest_lib'][j]
            official = identity(data['normalized_smiles'][j])
            blocked_rows[current] = {'source_row': current, 'raw_inchikey14': raw, 'official_identity': official,
                                     'ingest_lib': source, 'reason': 'official_identity' if official in active_ids else 'conservative_unknown_or_raw_family'}
            item = by_identity.get(official)
            if item is not None and source == item['query_source']:
                if data['adduct'][j] not in QUERY_ADDUCTS:
                    unsupported_query_rows[str(data['adduct'][j])] += 1
                    unsupported_by_molecule[item['molecule_id']][str(data['adduct'][j])] += 1
                    continue
                query_candidates[official].append({'source_row': current, 'adduct': data['adduct'][j],
                                                  'ionization_mode': data['ionization_mode'][j],
                                                  'collision_energy_ev': data['collision_energy_ev'][j]})
        source_row += batch.num_rows
    selected = {}
    selection_audit = []
    for official, item in by_identity.items():
        candidates = query_candidates[official]
        if not candidates:
            raise ValueError('Missing query spectra for ' + official)
        # Keep one spectrum from each actual adduct/energy bucket before filling.
        candidates.sort(key=lambda r: _stable_sort(str(r['source_row']), seed))
        buckets = defaultdict(list)
        for row in candidates:
            bucket = (str(row['adduct']), json.dumps(row['collision_energy_ev']))
            buckets[bucket].append(row)
        diverse = []
        for bucket in sorted(buckets):
            diverse.append(buckets[bucket].pop(0))
        remaining = [r for bucket in sorted(buckets) for r in buckets[bucket]]
        chosen = (diverse + remaining)[:max_spectra]
        for row in chosen:
            selected[row['source_row']] = item
        actual_buckets = {(str(row['adduct']), json.dumps(row['collision_energy_ev'])) for row in chosen}
        selection_audit.append({'molecule_id': item['molecule_id'], 'supported_source_spectra': len(candidates),
                                'selected_spectra': len(chosen), 'dropped_by_development_cap': len(candidates) - len(chosen),
                                'unsupported_adduct_spectra': dict(unsupported_by_molecule[item['molecule_id']]),
                                'available_adduct_ce_buckets': len(buckets), 'selected_adduct_ce_buckets': len(actual_buckets),
                                'available_polarities': sorted({str(r['ionization_mode']) for r in candidates}),
                                'selected_polarities': sorted({str(r['ionization_mode']) for r in chosen}),
                                'selected_adducts': sorted({str(r['adduct']) for r in chosen}),
                                'selected_energy_lists': sorted({json.dumps(r['collision_energy_ev']) for r in chosen})})
    _write_json(output / 'query_selection_audit.json', {'query_adduct_whitelist': QUERY_ADDUCTS,
                'whitelist_scope': 'Queries only; identity and exact-duplicate reference exclusions cover every training adduct.',
                'unsupported_adduct_spectra_dropped': dict(unsupported_query_rows),
                'skipped_frozen_development_identities': skipped_query_identities,
                'max_spectra_is_official_limit': False, 'cap_purpose': 'Development runtime only; hidden input may contain more spectra.',
                'molecules': selection_audit})
    output_tables = []
    query_hashes = defaultdict(list)
    metadata_keys = set()
    source_row = 0
    for batch in reader.iter_batches(batch_size=batch_size, use_threads=False):
        local = [row - source_row for row in selected if source_row <= row < source_row + batch.num_rows]
        if local:
            table = pa.Table.from_batches([batch]).take(pa.array(local, type=pa.int64()))
            records = table.to_pylist()
            for row, local_row in zip(records, local):
                global_row = source_row + local_row
                item = selected[global_row]
                row.update(molecule_id=item['molecule_id'], spectrum_id=f'train_row_{global_row:09d}',
                           source_row=global_row, panel=item['panel'], official_identity=item['official_identity'])
                digest = spectrum_digest(row['ms2_mzs'], row['ms2_normalized_intensities'], row['adduct'], row['precursor_mz'], row['ionization_mode'])
                row['spectrum_sha256'] = digest
                query_hashes[digest].append({'source_row': global_row, 'molecule_id': item['molecule_id'], 'ingest_lib': row['ingest_lib']})
                metadata_keys.add(_spectrum_metadata_key(row['adduct'], row['precursor_mz'], row['ionization_mode']))
            output_tables.extend(records)
        source_row += batch.num_rows
    query_table = pa.Table.from_pylist(output_tables)
    query_table = query_table.sort_by([('molecule_id', 'ascending'), ('source_row', 'ascending')])
    pq.write_table(query_table, output / 'queries.parquet', compression='zstd')
    truth = [{'molecule_id': item['molecule_id'], 'smiles': item['smiles'], 'official_identity': item['official_identity'],
              'panel': item['panel'], 'query_source': item['query_source']} for item in active]
    truth_table = pa.Table.from_pylist(truth).sort_by([('molecule_id', 'ascending')])
    pq.write_table(truth_table, output / 'truth.parquet', compression='zstd')
    import pyarrow.csv as pacsv
    pacsv.write_csv(truth_table, output / 'truth.csv')
    print('QUERIES_WRITTEN', query_table.num_rows, len(active), flush=True)
    # Full train coverage with an exact metadata prefilter; only matching rows' peaks are materialized.
    duplicate_rows = []
    duplicate_columns = ['inchikey14', 'normalized_smiles', 'ingest_lib', 'adduct', 'ionization_mode', 'precursor_mz', 'ms2_mzs', 'ms2_normalized_intensities']
    source_row = 0
    for batch_index, batch in enumerate(reader.iter_batches(batch_size=batch_size, columns=duplicate_columns, use_threads=False)):
        data = {column: batch.column(batch.schema.get_field_index(column)).to_pylist() for column in duplicate_columns if not column.startswith('ms2_')}
        for j in range(batch.num_rows):
            if _spectrum_metadata_key(data['adduct'][j], data['precursor_mz'][j], data['ionization_mode'][j]) not in metadata_keys:
                continue
            digest = spectrum_digest(_batch_peak(batch, 'ms2_mzs', j), _batch_peak(batch, 'ms2_normalized_intensities', j), data['adduct'][j], data['precursor_mz'][j], data['ionization_mode'][j])
            if digest not in query_hashes:
                continue
            current = source_row + j
            raw = _raw_key(data['inchikey14'][j], data['normalized_smiles'][j])
            official = identity(data['normalized_smiles'][j])
            entry = {'source_row': current, 'raw_inchikey14': raw, 'official_identity': official,
                     'ingest_lib': data['ingest_lib'][j], 'reason': 'exact_query_spectrum_duplicate', 'spectrum_sha256': digest}
            duplicate_rows.append(entry)
            if current in blocked_rows:
                blocked_rows[current]['reason'] += '+exact_query_spectrum_duplicate'
            else:
                blocked_rows[current] = {k: v for k, v in entry.items() if k != 'spectrum_sha256'}
        source_row += batch.num_rows
        if batch_index % 128 == 0:
            print(f'DUPLICATES rows_scanned={source_row} exact_matches={len(duplicate_rows)}', flush=True)
    exclusion_schema = pa.schema([('source_row', pa.int64()), ('raw_inchikey14', pa.string()), ('official_identity', pa.string()), ('ingest_lib', pa.string()), ('reason', pa.string())])
    duplicate_schema = exclusion_schema.append(pa.field('spectrum_sha256', pa.string()))
    pq.write_table(pa.Table.from_pylist(sorted(blocked_rows.values(), key=lambda r: r['source_row']), schema=exclusion_schema), output / 'class2_exclusion_rows.parquet', compression='zstd')
    pq.write_table(pa.Table.from_pylist(duplicate_rows, schema=duplicate_schema), output / 'query_duplicate_exclusion_rows.parquet', compression='zstd')
    matched_by_hash = defaultdict(list)
    for row in duplicate_rows:
        matched_by_hash[row['spectrum_sha256']].append(row)
    cross_library = []
    for digest, matches in matched_by_hash.items():
        source_names = sorted({str(row['ingest_lib']) for row in matches})
        if len(source_names) > 1:
            cross_library.append({'spectrum_sha256': digest, 'sources': source_names, 'matches': matches, 'queries': query_hashes[digest]})
    _write_json(output / 'spectrum_duplicate_audit.json', {'hash_definition': 'sha256(exact float64 precursor + adduct + mode + sorted original float64 (mz,intensity) peak multiset); no rounding',
                'coverage_rows': source_row, 'source_total_rows': inventory['rows'], 'full_train_coverage': source_row == inventory['rows'],
                'query_spectra': len(selected), 'query_unique_hashes': len(query_hashes), 'matched_train_rows': len(duplicate_rows),
                'cross_library_duplicate_groups': len(cross_library), 'cross_library_groups': cross_library,
                'near_duplicate_detection': 'Not performed; exact duplicates only. Float rounding, shifted/adduct-transformed spectra are not considered exact duplicates.'})
    active_query_ids = set(query_table.column('molecule_id').to_pylist())
    assert active_query_ids == {item['molecule_id'] for item in active}
    assert set(selected).issubset(blocked_rows)
    assert all(identity(item['smiles']) == item['official_identity'] for item in truth)
    assert set(query_table.column('official_identity').to_pylist()).isdisjoint(final_ids)
    assert set(query_table.column('adduct').to_pylist()).issubset(QUERY_ADDUCTS)
    manifest = {'schema_version': 1, 'created_utc': datetime.now(timezone.utc).isoformat(), 'status': 'prepared',
                'validation_status': 'reference-isolated diagnostic with known pretrained exposure', 'metric_rdkit': version,
                'train': {'path': str(train), 'bytes': train.stat().st_size, 'mtime_ns': train.stat().st_mtime_ns, **inventory},
                'queries_file': 'queries.parquet', 'truth_file': 'truth.csv', 'truth_parquet_file': 'truth.parquet',
                'reference_exclusion_rows_file': 'class2_exclusion_rows.parquet', 'reference_exclusion_keys_file': 'class2_exclusion_keys.json',
                'query_duplicate_exclusion_rows_file': 'query_duplicate_exclusion_rows.parquet', 'splits_file': 'frozen_splits.json',
                'split_sha256': splits['split_sha256'], 'seed': seed, 'processed_molecules': len(active),
                'active_ids': sorted(active_query_ids), 'query_spectra': query_table.num_rows,
                'active_panels': {'np': np_count, 'cross': cross_count},
                'frozen_panels': {'np_diagnostic': len(splits['np_diagnostic']), 'cross_development': cross_dev, 'cross_final_locked': cross_final},
                'final_locked_evaluated': False, 'max_query_spectra_per_molecule': max_spectra,
                'final_locked_query_spectra_extracted': False, 'final_locked_query_ids_in_active': 0,
                'frozen_split_source': str(frozen_splits.resolve()) if frozen_splits is not None else 'newly_frozen',
                'query_adduct_whitelist': list(QUERY_ADDUCTS), 'query_selection_audit_file': 'query_selection_audit.json',
                'unsupported_query_adduct_spectra_dropped': dict(unsupported_query_rows),
                'skipped_frozen_development_identities': skipped_query_identities,
                'max_spectra_is_official_limit': False,
                'query_selection': 'supported query adduct/CE buckets prioritized, then deterministic source-row fill; development cap max_spectra only, original metadata retained; masks cover ALL adducts',
                'class2_policy': 'Remove every blocked raw-key/official-identity family and every exact query-spectrum duplicate from ALL reference and analog paths; retain truth in structural candidates.',
                'candidate_truth_policy': 'Retain true official identities. Candidate-source membership must be measured by the runner; dataset preparation does not claim retrieval recall.',
                'reference_exclusion_rows': len(blocked_rows), 'reference_exclusion_raw_keys': len(blocked_keys),
                'training_exposure': training_exposure(),
                'limitations': ['These are labeled training-derived diagnostic queries, not a clean held-out model-generalization test.',
                    'NP public panel has been used by public authors; do not tune on it without a separate locked set.',
                    'No fixed precursor range is imposed from the visible placeholder; the query-only whitelist uses the official supported adduct list, while masks cover every adduct.',
                    'Known training exposure of FPNet full1 and Saner final_model prevents independent generalization claims even after perfect reference masks.',
                    'Class3 candidate-removal proxy is not prepared here; no de novo generalization is claimed.'],
                'elapsed_seconds': round(time.monotonic() - start, 3)}
    manifest['artifact_sha256'] = {path.name: file_sha256(path) for path in sorted(output.iterdir()) if path.is_file()}
    _write_json(output / 'manifest.json', manifest)
    print('PREPARATION_COMPLETE', json.dumps({k: manifest[k] for k in ['processed_molecules', 'query_spectra', 'reference_exclusion_rows', 'elapsed_seconds', 'validation_status']}), flush=True)
    return manifest
