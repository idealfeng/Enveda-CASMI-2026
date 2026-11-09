'''v1 engine code (the 0.358 model's engine) + fe_v4; pool symlinks; spectrum cache from train.parquet'''
sys.path.insert(0, V4CODE)
os.makedirs('work', exist_ok=True)
for f in ['pool_meta.parquet', 'pool_fp.npy', 'pool_frag_off.npy', 'pool_frag_mass.npy', 'fp_bits.npy', 'train_structs.parquet', 'train_fp_sel.npy']:
    src = os.path.join(POOL_DIR, f)
    dst = f'work/{f}'
    if not os.path.exists(dst):
        os.symlink(src, dst)
from casmi.build import build_spec_cache
build_spec_cache(os.path.join(COMP, 'train.parquet'), 'work')

"""Notebook-embedded, trained-SID-only extension. No runtime structure chemistry."""

def _build_external_reference_cache(base, table, pins):
    import hashlib, os, shutil, tempfile
    from pathlib import Path
    import numpy as np
    import pyarrow as pa
    import pyarrow.parquet as pq
    from casmi import chem
    from casmi.build import LIB_IX, instr_family
    from casmi.spectra import clean_peaks

    def check(ok, reason):
        if not ok:
            raise ValueError(reason)

    def digest(path):
        h = hashlib.sha256()
        with open(path, 'rb') as f:
            for block in iter(lambda: f.read(4 << 20), b''):
                h.update(block)
        return h.hexdigest()

    target = None
    try:
        check(table is not None, 'knowledge table unavailable')
        source = Path(table) / 'external_reference_spectra'
        base = Path(base)
        for name, expected in pins['files'].items():
            path = source / name
            check(path.is_file() and path.stat().st_size <= 32 << 20, 'external file unavailable or too large')
            check(digest(path) == expected, 'external file checksum differs')
        for name, expected in pins['base_files'].items():
            check(digest(base / name) == expected, 'training structure/pool version differs')
        links = pq.read_table(source / 'external_scorer_sid_links.parquet').to_pylist()
        check(len(links) == pins['keys'], 'link count differs')
        k2link = {r['scorer_key']: r for r in links}
        check(len(k2link) == len(links), 'duplicate scorer links')
        quality = pq.read_table(source / 'external_record_quality.parquet').to_pylist()
        pf = pq.ParquetFile(source / 'external_delta.parquet')
        check(pf.metadata.num_rows == len(quality) == pins['delta_rows'], 'delta/quality length differs')
        off = np.load(base / 'spec_off.npy', mmap_mode='r')
        mz = np.load(base / 'spec_mz.npy', mmap_mode='r')
        it = np.load(base / 'spec_it.npy', mmap_mode='r')
        meta = pq.ParquetFile(base / 'spec_meta.parquet')
        n = meta.metadata.num_rows
        check(off.dtype == np.int64 and mz.dtype == it.dtype == np.float32, 'CSR dtype differs')
        check(len(off) == n + 1 and off[0] == 0 and off[-1] == len(mz) == len(it), 'CSR size differs')
        for start in range(0, n, 1 << 18):
            check(np.all(np.diff(off[start:min(n, start + (1 << 18)) + 1]) >= 0), 'CSR offsets decrease')
        for start in range(0, len(mz), 1 << 20):
            a, b = mz[start:start + (1 << 20)], it[start:start + (1 << 20)]
            check(np.all(np.isfinite(a)) and np.all(np.isfinite(b)) and np.all(a > 0) and np.all(b >= 0), 'invalid base peaks')
        required = {'sid','lib','instr','adduct_ix','mode','precursor_mz','n_clean','nm','adduct',
                    'precursor_error_ppm','collision_energy_orig_units','base_peak_intensity','num_peaks',
                    'ce_mean','ce_min','ce_max','ce_n'}
        check(set(meta.schema_arrow.names) == required, 'cache metadata schema differs')
        meta_row = 0
        for batch in meta.iter_batches(batch_size=65536, columns=['sid','n_clean']):
            sids = np.asarray(batch.column(0))
            check(np.all((sids >= 0) & (sids < pins['structure_rows'])), 'base SID out of range')
            check(np.array_equal(np.asarray(batch.column(1)), np.diff(off[meta_row:meta_row + len(sids) + 1])), 'base peak counts differ')
            meta_row += len(sids)
        extra_meta, extra_mz, extra_it, used_keys = [], [], [], set()
        sources = {'MassBank':'massbank', 'MoNA':'mona', 'GNPS':'gnps', 'MSnLib':'pluskal_ms2'}
        row = 0
        for batch in pf.iter_batches(batch_size=128):
            for r in batch.to_pylist():
                q = quality[row]
                check(q['delta_row'] == row and all(q[c] == r[c] for c in ['source','record_id','scorer_key','spectrum_sha256','licence']), 'quality join differs')
                row += 1
                link = k2link.get(r['scorer_key'])
                check(link is not None, 'scorer link missing')
                if link['sid'] is None or not r['in_train_structure'] or q['mass_check_status'] != 'within_diagnostic_threshold':
                    continue
                check(0 <= link['sid'] < pins['structure_rows'] and r['formal_charge'] == 0, 'invalid linked SID/charge')
                check(abs(r['neutral_mono_mass'] - link['mass']) < 1e-5, 'linked structure mass differs')
                check(r['adduct'] in chem.ADDUCTS and r['ionization_mode'] in ['positive','negative'], 'unsupported ion metadata')
                check(bool(r['licence']), 'record licence missing')
                mode = 1 if r['ionization_mode'] == 'positive' else -1
                if chem.ADDUCTS[r['adduct']][3] != mode:
                    continue
                x, y = np.asarray(r['ms2_mzs'], np.float64), np.asarray(r['ms2_normalized_intensities'], np.float64)
                check(len(x) == len(y) and np.all(np.isfinite(x)) and np.all(np.isfinite(y)) and np.all(x > 0) and np.all(y >= 0), 'invalid external peaks')
                prec = float(r['precursor_mz'])
                check(np.isfinite(prec) and prec > 0, 'invalid precursor')
                x, y = clean_peaks(x, y, prec, 0.001, 512, 2.0)
                if not len(x):
                    continue
                check(np.all(np.diff(x) >= 0) and np.all(np.isfinite(y)) and len(x) <= 512, 'cleaned peaks invalid')
                ce = r['collision_energy_ev']
                known_ce = ce is not None and np.isfinite(ce) and r['collision_energy_units'] == 'eV'
                ce = float(ce) if known_ce else None
                d = dict(adduct=r['adduct'], precursor_mz=prec, precursor_error_ppm=None,
                         collision_energy_orig_units=r['collision_energy_units'], base_peak_intensity=None,
                         num_peaks=len(r['ms2_mzs']), ce_mean=ce, ce_min=ce, ce_max=ce,
                         ce_n=1 if known_ce else 0, sid=int(link['sid']), lib=LIB_IX[sources[r['source']]],
                         instr=instr_family(r['instrument_type']), adduct_ix=chem.adduct_index(r['adduct']),
                         mode=mode, nm=float(chem.neutral_mass([prec], [r['adduct']])[0]), n_clean=len(x))
                extra_meta.append(d); extra_mz.append(x); extra_it.append(y); used_keys.add(r['scorer_key'])
        check(len(extra_meta) == pins['added_rows'] and len(used_keys) == pins['added_keys'], 'eligible extension count differs')
        check(len(extra_meta) > 0, 'no eligible external references')
        target = Path(tempfile.mkdtemp(prefix='external_reference_', dir=base.parent))
        os.symlink((base / 'train_structs.parquet').resolve(), target / 'train_structs.parquet')
        counts = np.array([len(x) for x in extra_mz], np.int64)
        eo = np.r_[0, np.cumsum(counts)]
        for name, original, additions in [('spec_mz.npy', mz, extra_mz), ('spec_it.npy', it, extra_it)]:
            out = np.lib.format.open_memmap(target / name, mode='w+', dtype=np.float32, shape=(len(original) + int(eo[-1]),))
            for start in range(0, len(original), 1 << 20):
                end = min(len(original), start + (1 << 20))
                out[start:end] = original[start:end]
            for j, values in enumerate(additions):
                out[len(original) + eo[j]:len(original) + eo[j + 1]] = values
            out.flush(); del out
        out = np.lib.format.open_memmap(target / 'spec_off.npy', mode='w+', dtype=np.int64, shape=(n + len(extra_meta) + 1,))
        for start in range(0, len(off), 1 << 20):
            out[start:min(len(off), start + (1 << 20))] = off[start:start + (1 << 20)]
        out[n + 1:] = eo[1:] + off[-1]
        out.flush(); del out
        with pq.ParquetWriter(target / 'spec_meta.parquet', meta.schema_arrow) as writer:
            for batch in meta.iter_batches(batch_size=65536):
                writer.write_batch(batch)
            writer.write_table(pa.Table.from_pylist(extra_meta, schema=meta.schema_arrow))
        # Verify every copied base byte by bounded array comparison; no second full CSR in RAM.
        for name, original in [('spec_off.npy',off), ('spec_mz.npy',mz), ('spec_it.npy',it)]:
            extended = np.load(target / name, mmap_mode='r')
            for start in range(0, len(original), 1 << 20):
                end = min(len(original), start + (1 << 20))
                check(np.array_equal(original[start:end], extended[start:end]), 'base CSR changed')
            if name == 'spec_off.npy':
                check(extended[-1] == len(mz) + eo[-1] and np.all(np.diff(extended[n:]) > 0), 'appended offsets invalid')
            del extended
        check(pq.ParquetFile(target / 'spec_meta.parquet').metadata.num_rows == n + len(extra_meta), 'extended metadata size differs')
        return dict(path=str(target), added=len(extra_meta), keys=len(used_keys), base_rows=n, error=None)
    except Exception as exc:
        if target is not None:
            shutil.rmtree(target, ignore_errors=True)
        return dict(path=None, added=0, keys=0, error=f'{type(exc).__name__}: ' + ' '.join(str(exc).split())[:200])


def _external_reference_library(state):
    import gc
    import numpy as np
    from casmi.library import Library
    if state['path'] is not None:
        try:
            library = Library(state['path'])
            if len(library.sid) != state['base_rows'] + state['added'] or not np.all(np.diff(library.smass_sorted) >= 0):
                raise ValueError('extended Library index differs')
            if np.any(library.sid < 0) or np.any(library.sid >= len(library.struct_mass)):
                raise ValueError('structure/SID alignment differs')
            return library
        except Exception as exc:
            state['error'] = f'{type(exc).__name__}: ' + ' '.join(str(exc).split())[:200]
            state['path'] = None
            library = None
            gc.collect()
    return Library('work')


def _external_reference_engine(state, library, pool, train_fp, bank):
    import gc
    from casmi.library import Library
    from casmi.engine import Engine, EngineCfg
    if state['path'] is not None:
        try:
            if len(train_fp) != len(library.struct_mass):
                raise ValueError('fingerprint/SID alignment differs')
            engine = Engine(library, pool, train_fp, EngineCfg(generate=True), bank)
            print(f"external reference spectra: {state['added']} added for {state['keys']} structures", flush=True)
            return library, engine
        except Exception as exc:
            state['error'] = f'{type(exc).__name__}: ' + ' '.join(str(exc).split())[:200]
            state['path'] = None
            library = engine = None
            gc.collect()
        library = Library('work')
    print('external reference spectra disabled: ' + str(state['error']), flush=True)
    return library, Engine(library, pool, train_fp, EngineCfg(generate=True), bank)

_EXTERNAL_REFERENCE_PINS = {'files': {'external_delta.parquet': 'e75558832935f28e85a5419022c4cfba4d0d4b49f1063544c317c8ae61c2ac41', 'external_record_quality.parquet': '4f5b227d1c874624182c76e8f8406ba3ee86521744831cb461d6198c898b6c9e', 'external_scorer_sid_links.parquet': '8cd61b8f110bfd6686684d330609a1d0f0d7cc96eab32b9cdd3352939ef443ef'}, 'base_files': {'train_structs.parquet': 'f20aa1cac23af42e430a6633707fda34e48dea97114bdc3e443897f692df3656', 'pool_meta.parquet': '82b8c40315611289b9a4004b3af18d6d3402b3cd5baa4ee5723da07b7e2f6bb0'}, 'keys': 782, 'delta_rows': 1384, 'structure_rows': 275810, 'added_rows': 751, 'added_keys': 469}
_EXTERNAL_REFERENCE_STATE = _build_external_reference_cache('work', TABLE, _EXTERNAL_REFERENCE_PINS)

import casmi; print('casmi from', casmi.__file__)
sys.path.insert(1, os.path.join(V4CODE, 'fe_v4'))
print(f'cache built {time.time()-T0:.0f}s')
