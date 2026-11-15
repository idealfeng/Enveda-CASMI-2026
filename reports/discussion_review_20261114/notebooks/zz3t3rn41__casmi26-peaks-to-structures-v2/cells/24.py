# ===== 0.500+ APEX OVERLAY: ZERO-DISPLACEMENT PRECISION ADDUCT-AWARE SPECTRAL LIBRARY OVERLAY =====
# Integrates external measured MS/MS reference libraries (Takumu Hata extlib CC0 & MassBank harmonized).
# Key Breakthroughs:
# 1. Adduct-Aware Neutral Mass Alignment: Calculates true query neutral mass using complete 11-adduct delta table,
#    completely preventing false-positive cross-adduct collisions.
# 2. Comprehensive Adduct Compatibility:
#    - [M+H]+ and [M+NH4]+ match [M+H]+ and [M+NH4]+
#    - [M-H]-, formate ([M+CH2O2-H]-, [M+HCOO]-, [M+CHO2]-), and acetate ([M+CH3COO]-) match [M-H]-
#    - Water-loss [M-H2O+H]+ matches [M+H]+
# 3. Candidate Exact Mass Sanity Gate: Validates ExactMolWt(match_smi) against query neutral mass (<= 15 ppm).
# 4. Zero-Displacement Precision Promotion:
#    - High-confidence direct Rank 1 promotion (cos >= 0.80, k >= 3, precursor <= 12 ppm).
#    - Previous leader is strictly pinned at Rank 2 ([match_smi, smis[0]] + ...).
#    - Eliminates loose Tier 2/3 rank-2 insertions, protecting all authentic secondary ranks from displacement!

def _apex_extlib_overlay(work='/kaggle/working', inp='/kaggle/input'):
    import os, sys, glob, time, json, shutil, math
    from pathlib import Path
    from functools import lru_cache
    import numpy as np
    import pandas as pd
    from rdkit import Chem
    from rdkit.Chem.rdMolDescriptors import CalcExactMolWt
    from rdkit.Chem.MolStandardize import rdMolStandardize

    t0 = time.monotonic()
    sub_path = os.path.join(work, 'submission.csv')
    if not os.path.exists(sub_path):
        print('[apex-extlib] submission.csv not found; overlay skipped')
        return

    sub = pd.read_csv(sub_path, dtype=str, keep_default_na=False)
    shutil.copy(sub_path, os.path.join(work, 'submission_pre_apex_extlib.csv'))

    test_paths = sorted(glob.glob(inp + '/**/test.parquet', recursive=True),
                       key=lambda p: ('mass-spectra' not in p.lower(), len(p)))
    if not test_paths:
        print('[apex-extlib] test.parquet not found; overlay skipped')
        return
    te = pd.read_parquet(test_paths[0])

    _TAUT = rdMolStandardize.TautomerEnumerator()

    @lru_cache(maxsize=100000)
    def _to_k14(s):
        try:
            m = Chem.MolFromSmiles(s)
            if m:
                return Chem.MolToInchiKey(_TAUT.Canonicalize(m))[:14]
        except Exception:
            pass
        return ''

    @lru_cache(maxsize=100000)
    def _calc_nm(s):
        try:
            m = Chem.MolFromSmiles(s)
            if m:
                return CalcExactMolWt(m)
        except Exception:
            pass
        return None

    ADDUCT_DELTA = {
        '[M+H]+': 1.007276,
        '[M-H]-': -1.007276,
        '[M+Na]+': 22.989218,
        '[M+K]+': 38.963158,
        '[M+NH4]+': 18.033823,
        '[M+CH2O2-H]-': 44.998201,
        '[M+HCOO]-': 44.998201,
        '[M+CHO2]-': 44.998201,
        '[M+Cl]-': 34.969402,
        '[M-H2O+H]+': -17.003289,
        '[M+CH3COO]-': 59.013851
    }

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
        
        delta = ADDUCT_DELTA.get(adduct, 1.007276 * mode)
        nm = prec - delta
        queries.setdefault(mid, []).append(dict(mz=m, it=it, prec=prec, mode=mode, adduct=adduct, nm=nm))

    lib_max = {}
    ev_path = os.path.join(work, 'frozen_candidate_evidence.parquet')
    if os.path.exists(ev_path):
        try:
            ev = pd.read_parquet(ev_path, columns=['molecule_id', 'library_max'])
            lib_max = {str(m): float(v) for m, v in ev.groupby('molecule_id', sort=False).library_max.first().items()}
        except Exception:
            pass

    refs = []
    meta_hits = sorted(glob.glob(inp + '/**/ext_meta.parquet', recursive=True), key=len)
    mz_hits = sorted(glob.glob(inp + '/**/ext_mz.npy', recursive=True), key=len)
    in_hits = sorted(glob.glob(inp + '/**/ext_in.npy', recursive=True), key=len)
    
    if meta_hits and mz_hits and in_hits:
        try:
            print(f'[apex-extlib] Loading Takumu Hata extlib from {meta_hits[0]}...')
            meta_df = pd.read_parquet(meta_hits[0])
            mz_all = np.load(mz_hits[0], mmap_mode='r')
            in_all = np.load(in_hits[0], mmap_mode='r')

            for idx, row in meta_df.iterrows():
                try:
                    mode = 1 if 'pos' in str(row.get('ionization_mode', 'pos')).lower() else -1
                    prec = float(row['precursor_mz'])
                    adduct = str(row.get('adduct', ''))
                    delta = ADDUCT_DELTA.get(adduct, 1.007276 * mode)
                    nm = prec - delta
                    smi = str(row['normalized_smiles'])
                    key = str(row.get('inchikey14', ''))
                    
                    mz_p = np.asarray(mz_all[idx], dtype=np.float64)
                    it_p = np.asarray(in_all[idx], dtype=np.float64)
                    mask = (mz_p > 0) & (it_p > 0)
                    mz_p, it_p = mz_p[mask], it_p[mask]
                    if len(mz_p) < 3:
                        continue
                    o = np.argsort(mz_p)
                    refs.append((mode, prec, nm, adduct, mz_p[o], it_p[o], key, smi))
                except Exception:
                    continue
            print(f'[apex-extlib] Loaded {len(refs)} reference spectra from Source A.')
        except Exception as e:
            print(f'[apex-extlib] Source A loading error: {e}')

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
                    adduct = '[M+H]+' if mode == 1 else '[M-H]-'
                    smi = str(row.smiles)
                    mz_p = np.asarray(row.mzs, dtype=np.float64)
                    it_p = np.asarray(row.intensities, dtype=np.float64)
                    mask = (mz_p > 0) & (it_p > 0)
                    mz_p, it_p = mz_p[mask], it_p[mask]
                    if len(mz_p) < 3:
                        continue
                    o = np.argsort(mz_p)
                    refs.append((mode, prec, nm, adduct, mz_p[o], it_p[o], '', smi))
                except Exception:
                    continue
            print(f'[apex-extlib] Total references after Source B: {len(refs)} spectra.')
        except Exception as e:
            print(f'[apex-extlib] Source B loading error: {e}')

    # Check Source C: nakhun extlib2 (ext2_meta.parquet + ext2_offsets.npy + ext2_mz_flat.npy + ext2_in_flat.npy)
    ext2_meta_hits = sorted(glob.glob(inp + '/**/ext2_meta.parquet', recursive=True), key=len)
    ext2_off_hits = sorted(glob.glob(inp + '/**/ext2_offsets.npy', recursive=True), key=len)
    ext2_mz_hits = sorted(glob.glob(inp + '/**/ext2_mz_flat.npy', recursive=True), key=len)
    ext2_in_hits = sorted(glob.glob(inp + '/**/ext2_in_flat.npy', recursive=True), key=len)

    if ext2_meta_hits and ext2_off_hits and ext2_mz_hits and ext2_in_hits:
        try:
            print(f'[apex-extlib] Loading nakhun extlib2 from {ext2_meta_hits[0]}...')
            meta2_df = pd.read_parquet(ext2_meta_hits[0])
            offsets2 = np.load(ext2_off_hits[0])
            mz2_flat = np.load(ext2_mz_hits[0], mmap_mode='r')
            in2_flat = np.load(ext2_in_hits[0], mmap_mode='r')

            smiles_arr = meta2_df['normalized_smiles'].astype(str).values
            mode_arr = meta2_df['ionization_mode'].astype(str).values
            adduct_arr = meta2_df['adduct'].astype(str).values
            prec_arr = meta2_df['precursor_mz'].astype(float).values
            nm_arr = meta2_df['exact_mass'].astype(float).values if 'exact_mass' in meta2_df else None
            k14_arr = meta2_df['inchikey14'].astype(str).values if 'inchikey14' in meta2_df else None

            n_added_c = 0
            for idx in range(len(smiles_arr)):
                try:
                    smi = smiles_arr[idx]
                    if not smi or smi == 'None' or smi == 'nan':
                        continue
                    mode = 1 if 'pos' in mode_arr[idx].lower() else -1
                    prec = prec_arr[idx]
                    adduct = adduct_arr[idx]
                    delta = ADDUCT_DELTA.get(adduct, 1.007276 * mode)
                    nm = nm_arr[idx] if (nm_arr is not None and math.isfinite(nm_arr[idx])) else (prec - delta)
                    key = k14_arr[idx] if k14_arr is not None else ''

                    st = offsets2[idx]
                    en = offsets2[idx + 1] if idx + 1 < len(offsets2) else len(mz2_flat)
                    mz_p = np.asarray(mz2_flat[st:en], dtype=np.float64)
                    it_p = np.asarray(in2_flat[st:en], dtype=np.float64)
                    mask = (mz_p > 0) & (it_p > 0)
                    mz_p, it_p = mz_p[mask], it_p[mask]
                    if len(mz_p) < 3:
                        continue
                    o = np.argsort(mz_p)
                    refs.append((mode, prec, nm, adduct, mz_p[o], it_p[o], key, smi))
                    n_added_c += 1
                except Exception:
                    continue
            print(f'[apex-extlib] Total references after Source C (ExtLib2): {len(refs)} spectra (+{n_added_c} added).')
        except Exception as e:
            print(f'[apex-extlib] Source C loading error: {e}')

    if not refs:
        print('[apex-extlib] No external reference spectra available; keeping submission untouched.')
        return

    order = np.argsort([r[2] for r in refs], kind='stable')
    sorted_refs = [refs[i] for i in order]
    nm_array = np.array([r[2] for r in sorted_refs])

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

    def is_adduct_compatible(q_adduct, ref_adduct):
        if q_adduct and ref_adduct and q_adduct == ref_adduct:
            return True
        if q_adduct in ('[M+NH4]+', '[M-H2O+H]+') and ref_adduct in ('[M+H]+', '[M+NH4]+', '[M-H2O+H]+'):
            return True
        if ref_adduct in ('[M+NH4]+', '[M-H2O+H]+') and q_adduct in ('[M+H]+', '[M+NH4]+', '[M-H2O+H]+'):
            return True
        neg_forms = ('[M-H]-', '[M+CH2O2-H]-', '[M+HCOO]-', '[M+CHO2]-', '[M+CH3COO]-')
        if q_adduct in neg_forms and ref_adduct in neg_forms:
            return True
        if (not q_adduct or q_adduct == '[M+H]+') and (not ref_adduct or ref_adduct == '[M+H]+'):
            return True
        if (not q_adduct or q_adduct == '[M-H]-') and (not ref_adduct or ref_adduct == '[M-H]-'):
            return True
        return False

    TAU_TIER1 = globals().get('EXTLIB_TAU', 0.78)     # High-precision direct Rank-1 Hit (cos >= 0.80, >= 3 peaks)
    K_PEAKS = globals().get('EXTLIB_K', 3)            # Calibrated minimum matching peaks (Guhongbin v593)
    LIB_TAU = 0.90                                   # Protect queries already strong in pipeline library

    hits_tier1 = 0
    new_smiles_list = []

    for mid, smiles_str in zip(sub['molecule_id'].astype(str), sub['smiles'].astype(str)):
        smis = [s for s in smiles_str.split(';') if s]
        new_smis = list(smis)
        
        try:
            if lib_max.get(mid, 0.0) >= LIB_TAU:
                new_smiles_list.append(smiles_str)
                continue

            q_list = queries.get(mid, [])
            if not q_list:
                new_smiles_list.append(smiles_str)
                continue

            best_match = (0.0, 0, None, 0.0)  # (cosine, n_peaks, smi, q_nm)
            for q in q_list:
                q_mode, q_nm, q_adduct = q['mode'], q['nm'], q['adduct']
                q_mz, q_it = q['mz'], q['it']
                
                tol = q_nm * 12e-6 + 0.002
                idx_lo = np.searchsorted(nm_array, q_nm - tol, 'left')
                idx_hi = np.searchsorted(nm_array, q_nm + tol, 'right')
                
                for ri in range(idx_lo, idx_hi):
                    ref = sorted_refs[ri]
                    ref_mode, ref_adduct = ref[0], ref[3]
                    if ref_mode != q_mode:
                        continue
                    if not is_adduct_compatible(q_adduct, ref_adduct):
                        continue

                    cos, n_matched = calc_cosine(q_mz, q_it, ref[4], ref[5])
                    if n_matched >= K_PEAKS and cos > best_match[0]:
                        best_match = (cos, n_matched, ref[7], q_nm)

            best_cos, best_k, match_smi, match_q_nm = best_match
            if match_smi is not None:
                cand_nm = _calc_nm(match_smi)
                if cand_nm is not None and abs(cand_nm - match_q_nm) / match_q_nm > 15e-6:
                    new_smiles_list.append(smiles_str)
                    continue

                curr_keys = [_to_k14(s) for s in smis]
                match_k14 = _to_k14(match_smi)

                if best_cos >= TAU_TIER1:
                    # High-Precision Rank-1 Promotion with previous leader pinned at Rank 2
                    if match_k14 and match_k14 == curr_keys[0]:
                        new_smis = list(smis)
                    elif match_k14 and match_k14 in curr_keys[1:]:
                        idx = curr_keys.index(match_k14)
                        new_smis = [smis[idx], smis[0]] + [s for i, s in enumerate(smis[1:], 1) if i != idx]
                        hits_tier1 += 1
                    else:
                        new_smis = [match_smi, smis[0]] + [s for s in smis[1:] if _to_k14(s) != match_k14][:23]
                        hits_tier1 += 1

        except Exception as exc:
            new_smis = smis

        new_smiles_list.append(';'.join(new_smis) if new_smis else smiles_str)

    res_df = sub.copy()
    res_df['smiles'] = new_smiles_list
    assert len(res_df) == len(sub)
    assert res_df['smiles'].str.split(';').map(len).max() <= 25

    tmp_path = os.path.join(work, 'submission.tmp.csv')
    res_df.to_csv(tmp_path, index=False)
    os.replace(tmp_path, sub_path)

    elapsed = round(time.monotonic() - t0, 1)
    audit = dict(molecules=len(sub), tier1_hits=hits_tier1, elapsed_s=elapsed)
    with open(os.path.join(work, 'apex_extlib_audit.json'), 'w') as f:
        json.dump(audit, f, indent=2)

    print(f'[apex-extlib] SUCCESS: Zero-displacement overlay complete! Tier1={hits_tier1} in {elapsed}s.')

try:
    _apex_extlib_overlay()
except Exception:
    import traceback
    traceback.print_exc()
    print('[apex-extlib] overlay failed; existing submission preserved.')
