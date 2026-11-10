"""Stream the pinned Enveda-180 library for same-adduct H+/H- queries only.

This module does not apply promotions. It returns actual measured-reference
matches to the outer AB/E policy, which owns official-identity output guards.
The caller passes the exact original Alex cosine implementation.
"""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
import hashlib
import math
from pathlib import Path
import time

import numpy as np
import pyarrow.parquet as pq

SOURCE_REF = 'egehseyinca/enveda180-casmi26-reference-ccby4'
SOURCE_VERSION = 1
SOURCE_FILE = 'enveda180_hplus_hminus_references.parquet'
SOURCE_BYTES = 218514313
SOURCE_SHA256 = '37b8f37c5f5f536ed804d4d0456e20f183fa32388f30ae1c1712928471146069'
ALLOWED_ADDUCTS = {'[M+H]+': 1, '[M-H]-': -1}
CARRIER = 1.007276
PPM = 10e-6
DA = .002
MIN_COSINE = .80
MIN_MATCHED_PEAKS = 4
PROTECT_LIBRARY_AT = .90
MAX_BATCH_SIZE = 8192
REQUIRED_COLUMNS = ('reference_key', 'smiles', 'neutral_mass', 'adduct',
                    'ms2_mzs', 'ms2_normalized_intensities')


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _peak_arrays(record):
    try:
        mz = np.asarray(record['mz'], dtype=np.float64)
        intensity = np.asarray(record['it'], dtype=np.float64)
    except (ValueError, TypeError):
        return None
    if mz.ndim != 1 or intensity.ndim != 1 or len(mz) != len(intensity):
        return None
    # Original query preparation already applies these filters. Requiring finite
    # arrays here prevents a malformed query from manufacturing a library hit.
    if not np.isfinite(mz).all() or not np.isfinite(intensity).all():
        return None
    if len(mz) < 1 or not (mz > 0).all() or not (intensity > 0).all():
        return None
    if (mz[1:] < mz[:-1]).any():
        return None
    return mz, intensity


def prepare_queries(queries, library_max):
    """Return eligible rows and explicit skip reasons without synthesizing ions."""
    prepared = {adduct: [] for adduct in ALLOWED_ADDUCTS}
    skipped = Counter()
    protected = []
    molecule_counts = {}
    input_rows = 0
    for raw_mid, records in queries.items():
        mid = str(raw_mid)
        if mid in molecule_counts:
            raise ValueError('Duplicate molecule ID after string conversion')
        molecule_counts[mid] = len(records)
        input_rows += len(records)
        try:
            confidence = float(library_max.get(mid, 0.))
        except (ValueError, TypeError):
            skipped['invalid_library_confidence'] += len(records)
            continue
        if not math.isfinite(confidence):
            skipped['invalid_library_confidence'] += len(records)
            continue
        if confidence >= PROTECT_LIBRARY_AT:
            protected.append(mid)
            skipped['strong_original_library'] += len(records)
            continue
        for index, record in enumerate(records):
            adduct = str(record.get('adduct', ''))
            if adduct not in ALLOWED_ADDUCTS:
                skipped['unsupported_query_adduct'] += 1
                continue
            try:
                precursor = float(record['prec'])
                mode = int(record['mode'])
            except (ValueError, TypeError, OverflowError):
                skipped['invalid_query_metadata'] += 1
                continue
            if not math.isfinite(precursor) or precursor <= 0:
                skipped['invalid_query_precursor'] += 1
                continue
            if mode != ALLOWED_ADDUCTS[adduct]:
                skipped['query_adduct_mode_mismatch'] += 1
                continue
            arrays = _peak_arrays(record)
            if arrays is None:
                skipped['invalid_query_peaks'] += 1
                continue
            mz, intensity = arrays
            tolerance = precursor * PPM + DA
            prepared[adduct].append(dict(molecule_id=mid, query_index=index,
                prec=precursor, mode=mode, adduct=adduct, mz=mz, it=intensity,
                low=precursor-tolerance, high=precursor+tolerance))
    for rows in prepared.values():
        rows.sort(key=lambda row: row['prec'])  # stable for same-precursor spectra
    summary = dict(input_queries=len(molecule_counts), input_spectra=input_rows,
        eligible_queries=len({r['molecule_id'] for rows in prepared.values() for r in rows}),
        eligible_spectra=sum(len(rows) for rows in prepared.values()),
        eligible_by_adduct={a:len(rows) for a,rows in prepared.items()},
        skipped_spectra=dict(skipped), protected_queries=protected)
    return prepared, summary


def merge_windows(rows):
    intervals = sorted((row['low'], row['high']) for row in rows)
    merged = []
    for low, high in intervals:
        if merged and low <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], high)
        else:
            merged.append([low, high])
    return (np.array([x[0] for x in merged], dtype=np.float64),
            np.array([x[1] for x in merged], dtype=np.float64))


def window_membership(values, lows, highs):
    if not len(lows):
        return np.zeros(len(values), dtype=bool)
    location = np.searchsorted(lows, values, side='right')-1
    safe_location = np.maximum(location, 0)
    return (location >= 0) & (values <= highs[safe_location])


def _better(candidate, previous):
    if previous is None:
        return True
    if candidate['cosine'] != previous['cosine']:
        return candidate['cosine'] > previous['cosine']
    # Match the natural ordering of original Alex query-first, then a stable
    # precursor-sorted reference loop, independent of parquet batch boundaries.
    key = lambda x:(x['query_index'], x['precursor_mz'], x['reference_index'])
    return key(candidate) < key(previous)


def score_enveda(queries, library_max, path, calc_cosine, *, expected_sha256=SOURCE_SHA256,
                 expected_bytes=SOURCE_BYTES, batch_size=MAX_BATCH_SIZE,
                 min_cosine=MIN_COSINE, min_peaks=MIN_MATCHED_PEAKS):
    """Return (threshold-passing best matches, JSON-serializable binding audit).

    ``queries`` has original, preprocessed arrays under mz/it/prec/mode/adduct.
    No query truth, structure labels, catalogue membership or alias subset is used.
    Explicit expected hash/size arguments exist for isolated fixture libraries;
    the deployed caller binds them to the published full-source manifest.
    """
    started = time.monotonic()
    path = Path(path)
    if type(min_cosine) not in (int,float) or min_cosine != MIN_COSINE or type(min_peaks) is not int or min_peaks != MIN_MATCHED_PEAKS:
        raise ValueError('E matching thresholds must remain the fixed .80/four-peak recipe')
    if type(batch_size) is not int or not 1 <= batch_size <= MAX_BATCH_SIZE:
        raise ValueError('Bounded batch size required')
    if type(expected_bytes) is not int or expected_bytes <= 0:
        raise ValueError('Expected library size required')
    if path.stat().st_size != expected_bytes or sha(path) != expected_sha256:
        raise ValueError('Enveda reference bytes/SHA mismatch')
    parquet = pq.ParquetFile(path)
    if not set(REQUIRED_COLUMNS) <= set(parquet.schema_arrow.names):
        raise ValueError('Enveda reference schema mismatch')
    prepared, query_audit = prepare_queries(queries, library_max)
    audit = dict(status='passed', source='E', source_ref=SOURCE_REF,
        source_version=SOURCE_VERSION, path=str(path), bytes=expected_bytes,
        sha256=expected_sha256, source_rows_total=parquet.metadata.num_rows,
        query_preparation=query_audit, scan_performed=False, rows_scanned=0,
        selected_reference_rows=0, usable_selected_reference_rows=0,
        scored_pairs=0, invalid_scored_pairs=0, max_batch_rows=0,
        reference_skip_reasons={}, query_best=[],
        rules=dict(allowed_query_reference_adducts=list(ALLOWED_ADDUCTS),
            exact_adduct=True, exact_mode=True, neutral_carrier=CARRIER,
            precursor_ppm=10, precursor_da=DA, min_cosine=MIN_COSINE,
            min_matched_peaks=MIN_MATCHED_PEAKS,
            original_library_protection=PROTECT_LIBRARY_AT,
            tie_policy='highest score; earliest query row; lowest reference precursor; original reference row'),
        no_truth_or_alias_filter=True, training_performed=False,
        peak_audit_scope='all reference metadata; peak arrays only inside actual eligible query windows')
    if query_audit['eligible_spectra'] == 0:
        audit.update(no_eligible_queries=True, returned_hits=0,
                     elapsed_seconds=time.monotonic()-started)
        return {}, audit
    audit['scan_performed'] = True
    windows = {a:merge_windows(rows) for a,rows in prepared.items()}
    query_precursors = {a:[r['prec'] for r in rows] for a,rows in prepared.items()}
    best, per_spectrum = {}, {}
    skips = Counter()
    row_offset = 0
    for batch in parquet.iter_batches(batch_size=batch_size, columns=list(REQUIRED_COLUMNS), use_threads=False):
        count = batch.num_rows
        audit['rows_scanned'] += count
        audit['max_batch_rows'] = max(audit['max_batch_rows'], count)
        adducts = np.asarray(batch.column('adduct').to_pylist(), dtype=object)
        neutral = np.asarray(batch.column('neutral_mass').to_pylist(), dtype=np.float64)
        finite_mass = np.isfinite(neutral) & (neutral > 0)
        skips['invalid_reference_neutral_mass'] += int((~finite_mass).sum())
        supported = np.isin(adducts, list(ALLOWED_ADDUCTS))
        skips['unsupported_reference_adduct'] += int((~supported).sum())
        for adduct, mode in ALLOWED_ADDUCTS.items():
            rows = prepared[adduct]
            if not rows:
                continue
            precursors = neutral + mode*CARRIER
            lows, highs = windows[adduct]
            selected = finite_mass & (adducts == adduct) & (precursors > 0)
            selected &= window_membership(precursors, lows, highs)
            selected_indices = np.flatnonzero(selected)
            audit['selected_reference_rows'] += len(selected_indices)
            qp = query_precursors[adduct]
            for local_index in selected_indices:
                j = int(local_index)
                precursor = float(precursors[j])
                lower = (precursor-DA)/(1+PPM)
                upper = (precursor+DA)/(1-PPM)
                # Widen only the algebraic inverse search by one ULP, then
                # enforce the exact original q +/- tolerance inequality below.
                start = bisect_left(qp, math.nextafter(lower, -math.inf))
                end = bisect_right(qp, math.nextafter(upper, math.inf))
                candidates = [q for q in rows[start:end] if q['low'] <= precursor <= q['high']]
                if not candidates:
                    skips['window_boundary_without_query'] += 1
                    continue
                smiles = batch.column('smiles')[j].as_py()
                if not isinstance(smiles, str) or not smiles.strip():
                    skips['empty_reference_smiles'] += 1
                    continue
                try:
                    mz = np.asarray(batch.column('ms2_mzs')[j].as_py(), dtype=np.float64)
                    intensity = np.asarray(batch.column('ms2_normalized_intensities')[j].as_py(), dtype=np.float64)
                except (ValueError, TypeError):
                    skips['invalid_reference_peaks'] += 1
                    continue
                if mz.ndim != 1 or intensity.ndim != 1 or len(mz) != len(intensity):
                    skips['invalid_reference_peaks'] += 1
                    continue
                mask = np.isfinite(mz) & np.isfinite(intensity) & (mz > 0) & (intensity > 0)
                mz, intensity = mz[mask], intensity[mask]
                if len(mz) < 3:
                    skips['short_reference_peaks'] += 1
                    continue
                order = np.argsort(mz)
                mz, intensity = mz[order], intensity[order]
                audit['usable_selected_reference_rows'] += 1
                reference_key = batch.column('reference_key')[j].as_py()
                for query in candidates:
                    cosine, peaks = calc_cosine(query['mz'], query['it'], mz, intensity)
                    cosine, peaks = float(cosine), int(peaks)
                    audit['scored_pairs'] += 1
                    if not math.isfinite(cosine) or cosine < 0 or cosine > 1.000001 or peaks < 0:
                        audit['invalid_scored_pairs'] += 1
                        continue
                    if peaks < MIN_MATCHED_PEAKS:
                        continue
                    match = dict(molecule_id=query['molecule_id'], cosine=cosine,
                        matched_peaks=peaks, smiles=smiles, source='E',
                        reference_index=row_offset+j, reference_key=str(reference_key or ''),
                        adduct=adduct, mode=mode, precursor_mz=precursor,
                        query_index=query['query_index'], query_precursor_mz=query['prec'],
                        above_threshold=cosine >= MIN_COSINE)
                    mid = query['molecule_id']
                    if _better(match, best.get(mid)):
                        best[mid] = match
                    key = (mid, query['query_index'])
                    if _better(match, per_spectrum.get(key)):
                        per_spectrum[key] = match
        row_offset += count
    if audit['rows_scanned'] != parquet.metadata.num_rows:
        raise RuntimeError('Incomplete Enveda reference scan')
    hits = {}
    for mid, candidate in best.items():
        value = dict(candidate)
        value['same_smiles_winning_spectra'] = sum(
            m['smiles'] == value['smiles'] and m['above_threshold']
            for (other_mid,_),m in per_spectrum.items() if other_mid == mid)
        value['support_scope'] = 'raw-SMILES agreement of per-query-spectrum top E hits; not official-identity grouping'
        audit['query_best'].append(value)
        if value['above_threshold']:
            hits[mid] = value
    audit.update(reference_skip_reasons=dict(skips), returned_hits=len(hits),
        no_eligible_queries=False, elapsed_seconds=time.monotonic()-started)
    try:
        import resource
        audit['process_peak_rss_kb'] = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    except ImportError:
        audit['process_peak_rss_kb'] = None
    return hits, audit
