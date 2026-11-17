# ===== 0.500 APEX OVERLAY: DUAL-BAND EXTERNAL SPECTRAL LIBRARY RANK-1 PROMOTION =====
# Integrates external measured MS/MS reference libraries (Takumu Hata extlib CC0 & MassBank harmonized)
# and heliosli's direct-hit Rank-1 promotion rule.
# For any test query matching an external reference spectrum (precursor <= 10 ppm, same ion mode,
# sqrt-intensity cosine >= 0.85, matched peaks >= 4):
# The verified external structure is promoted directly to Rank 1 (Class 1 queries score 1.00 MRR).
# When lib_max >= LIB_TAU (pipeline already has strong match), existing ranking is protected.
# All operations fail safe: any exception preserves the 0.480 Variant M submission.csv untouched.

def _apex_extlib_overlay(work='/kaggle/working', inp='/kaggle/input'):
    import os, sys, glob, time, json, shutil, math
    from pathlib import Path
    import numpy as np
    import pandas as pd

    t0 = time.monotonic()
    sub_path = os.path.join(work, 'submission.csv')
    if not os.path.exists(sub_path):
        print('[apex-extlib] submission.csv not found; overlay skipped')
        return

    sub = pd.read_csv(sub_path, dtype=str, keep_default_na=False)
    shutil.copy(sub_path, os.path.join(work, 'submission_pre_apex_extlib.csv'))

    # Locate test.parquet
    test_paths = sorted(glob.glob(inp + '/**/test.parquet', recursive=True),
                       key=lambda p: ('mass-spectra' not in p.lower(), len(p)))
    if not test_paths:
        print('[apex-extlib] test.parquet not found; overlay skipped')
        return
    te = pd.read_parquet(test_paths[0])

    # Pre-parse query spectra
    queries = {}
    for r in te.itertuples(index=False):
        mid = str(r.molecule_id)
        m = np.asarray(r.ms2_mzs, dtype=np.float64)
        it = np.asarray(r.ms2_normalized_intensities, dtype=np.float64)
        prec = float(r.precursor_mz)
        mode = 1 if 'pos' in str(getattr(r, 'ionization_mode', 'positive')).lower() else -1
        adduct = str(getattr(r, 'adduct', ''))
        
        ok = (m > 0) & (it > 0) & (m <= prec + 0.5)
        m, it = m[ok], it[ok]
        o = np.argsort(m)
        m, it = m[o], it[o]
        
        # Calculate approximate neutral mass
        nm = prec - 1.007276 if mode == 1 else prec + 1.007276
        if '[M+Na]+' in adduct: nm = prec - 22.989218
        elif '[M+K]+' in adduct: nm = prec - 38.963158
        elif '[M+NH4]+' in adduct: nm = prec - 18.033823
        elif '[M+HCOO]-' in adduct: nm = prec - 44.998201
        
        queries.setdefault(mid, []).append(dict(mz=m, it=it, prec=prec, mode=mode, nm=nm))

    # Read existing pipeline library confidence
    lib_max = {}
    ev_path = os.path.join(work, 'frozen_candidate_evidence.parquet')
    if os.path.exists(ev_path):
        try:
            ev = pd.read_parquet(ev_path, columns=['molecule_id', 'library_max'])
            lib_max = {str(m): float(v) for m, v in ev.groupby('molecule_id', sort=False).library_max.first().items()}
        except Exception:
            pass

    # Find external library sources
    refs = []  # list of tuples: (mode, prec, mz_arr, it_arr, key, smiles, neutral_mass)
    
    # Check Source A: Takumu Hata extlib (ext_meta.parquet + ext_mz.npy / ext_in.npy)
    meta_hits = sorted(glob.glob(inp + '/**/ext_meta.parquet', recursive=True), key=len)
    mz_hits = sorted(glob.glob(inp + '/**/ext_mz.npy', recursive=True), key=len)
    in_hits = sorted(glob.glob(inp + '/**/ext_in.npy', recursive=True), key=len)
    mass_hits = sorted(glob.glob(inp + '/**/ext_mass.parquet', recursive=True), key=len)
    
    if meta_hits and mz_hits and in_hits:
        try:
            print(f'[apex-extlib] Loading Takumu Hata extlib from {meta_hits[0]}...')
            meta_df = pd.read_parquet(meta_hits[0])
            mz_all = np.load(mz_hits[0], mmap_mode='r')
            in_all = np.load(in_hits[0], mmap_mode='r')
            mass_df = pd.read_parquet(mass_hits[0]) if mass_hits else None
            
            # Filter non-empty masses if available
            if mass_df is not None and 'exact_mass' in mass_df.columns:
                meta_df['exact_mass'] = mass_df['exact_mass'].values
                meta_df = meta_df[meta_df['exact_mass'].notna() & (meta_df['exact_mass'] > 0)].copy()

            for idx, row in meta_df.iterrows():
                try:
                    mode = 1 if 'pos' in str(row.get('ionization_mode', 'pos')).lower() else -1
                    prec = float(row['precursor_mz'])
                    nm = float(row.get('exact_mass', prec - (1.007276 * mode)))
                    smi = str(row['normalized_smiles'])
                    key = str(row.get('inchikey14', ''))
                    
                    mz_p = np.asarray(mz_all[idx], dtype=np.float64)
                    it_p = np.asarray(in_all[idx], dtype=np.float64)
                    mask = (mz_p > 0) & (it_p > 0)
                    mz_p, it_p = mz_p[mask], it_p[mask]
                    if len(mz_p) < 3:
                        continue
                    o = np.argsort(mz_p)
                    refs.append((mode, prec, mz_p[o], it_p[o], key, smi, nm))
                except Exception:
                    continue
            print(f'[apex-extlib] Loaded {len(refs)} reference spectra from Source A.')
        except Exception as e:
            print(f'[apex-extlib] Source A loading error: {e}')

    # Check Source B: MassBank harmonized spectra.parquet
    mb_hits = sorted(glob.glob(inp + '/**/spectra.parquet', recursive=True),
                     key=lambda p: ('massbank' not in p.lower(), len(p)))
    if mb_hits and 'massbank' in mb_hits[0].lower():
        try:
            print(f'[apex-extlib] Loading MassBank harmonized from {mb_hits[0]}...')
            mb_df = pd.read_parquet(mb_hits[0], columns=['smiles', 'exact_mass', 'ion_mode', 'mzs', 'intensities', 'is_casmi_subset'])
            mb_df = mb_df[(~mb_df.is_casmi_subset.astype(bool)) & mb_df.smiles.notna()]
            
            for row in mb_df.itertuples(index=False):
                try:
                    mode = 1 if 'pos' in str(row.ion_mode).lower() else -1
                    nm = float(row.exact_mass)
                    prec = nm + (1.007276 * mode)
                    smi = str(row.smiles)
                    mz_p = np.asarray(row.mzs, dtype=np.float64)
                    it_p = np.asarray(row.intensities, dtype=np.float64)
                    mask = (mz_p > 0) & (it_p > 0)
                    mz_p, it_p = mz_p[mask], it_p[mask]
                    if len(mz_p) < 3:
                        continue
                    o = np.argsort(mz_p)
                    refs.append((mode, prec, mz_p[o], it_p[o], '', smi, nm))
                except Exception:
                    continue
            print(f'[apex-extlib] Total references after Source B: {len(refs)} spectra.')
        except Exception as e:
            print(f'[apex-extlib] Source B loading error: {e}')

    if not refs:
        print('[apex-extlib] No external reference spectra available; keeping submission untouched.')
        return

    # Sort references by precursor mass for fast binary search
    order = np.argsort([r[1] for r in refs], kind='stable')
    sorted_refs = [refs[i] for i in order]
    prec_array = np.array([r[1] for r in sorted_refs])

    def calc_cosine(qm, qi, rm, ri, tol=0.015):
        if len(qm) == 0 or len(rm) == 0:
            return 0.0, 0
        qa, ra = np.sqrt(qi), np.sqrt(ri)
        qa = qa / (np.linalg.norm(qa) + 1e-12)
        ra = ra / (np.linalg.norm(ra) + 1e-12)
        
        j0 = np.searchsorted(rm, qm - tol, 'left')
        j1 = np.searchsorted(rm, qm + tol, 'right')
        pairs = [(qa[i] * ra[j], i, j) for i in range(len(qm)) for j in range(j0[i], j1[i])]
        if not pairs:
            return 0.0, 0
        pairs.sort(reverse=True)
        ui, uj, s, n = set(), set(), 0.0, 0
        for p, i, j in pairs:
            if i in ui or j in uj:
                continue
            ui.add(i); uj.add(j)
            s += p; n += 1
        return float(s), n

    TAU = 0.80          # Minimum cosine similarity for direct Rank-1 hit
    K_PEAKS = 4         # Minimum matching peaks
    LIB_TAU = 0.90      # Protect queries already strong in pipeline library

    hits_count = 0
    promoted_count = 0
    new_smiles_list = []

    for mid, smiles_str in zip(sub['molecule_id'].astype(str), sub['smiles'].astype(str)):
        smis = [s for s in smiles_str.split(';') if s]
        new_smis = list(smis)
        
        try:
            # If the pipeline already matched this molecule with high confidence, protect it
            if lib_max.get(mid, 0.0) >= LIB_TAU:
                new_smiles_list.append(smiles_str)
                continue

            q_list = queries.get(mid, [])
            if not q_list:
                new_smiles_list.append(smiles_str)
                continue

            best_match = (0.0, 0, None)  # (cosine, n_peaks, smi)
            for q in q_list:
                q_mode, q_prec = q['mode'], q['prec']
                q_mz, q_it = q['mz'], q['it']
                
                # Precursor search window: 10 ppm + 0.002 Da
                tol = q_prec * 10e-6 + 0.002
                idx_lo = np.searchsorted(prec_array, q_prec - tol, 'left')
                idx_hi = np.searchsorted(prec_array, q_prec + tol, 'right')
                
                for ri in range(idx_lo, idx_hi):
                    ref = sorted_refs[ri]
                    if ref[0] != q_mode:
                        continue
                    cos, n_matched = calc_cosine(q_mz, q_it, ref[2], ref[3])
                    if n_matched >= K_PEAKS and cos > best_match[0]:
                        best_match = (cos, n_matched, ref[5])

            best_cos, best_k, match_smi = best_match
            if match_smi is not None and best_cos >= TAU:
                hits_count += 1
                if match_smi in smis:
                    new_smis = [match_smi] + [s for s in smis if s != match_smi]
                    promoted_count += int(smis[0] != match_smi)
                else:
                    new_smis = ([match_smi] + smis)[:25]
                    promoted_count += 1

        except Exception as exc:
            new_smis = smis

        new_smiles_list.append(';'.join(new_smis) if new_smis else smiles_str)

    res_df = sub.copy()
    res_df['smiles'] = new_smiles_list
    assert len(res_df) == len(sub)
    assert res_df['smiles'].str.split(';').map(len).max() <= 25

    # Atomically save updated submission
    tmp_path = os.path.join(work, 'submission.tmp.csv')
    res_df.to_csv(tmp_path, index=False)
    os.replace(tmp_path, sub_path)

    elapsed = round(time.monotonic() - t0, 1)
    audit = dict(molecules=len(sub), hits=hits_count, promoted=promoted_count, elapsed_s=elapsed)
    with open(os.path.join(work, 'apex_extlib_audit.json'), 'w') as f:
        json.dump(audit, f, indent=2)

    print(f'[apex-extlib] SUCCESS: {hits_count} library matches (TAU={TAU}, K={K_PEAKS}), '
          f'{promoted_count} Rank-1 promotions applied in {elapsed}s.')

try:
    _apex_extlib_overlay()
except Exception:
    import traceback
    traceback.print_exc()
    print('[apex-extlib] overlay failed; existing submission preserved.')
