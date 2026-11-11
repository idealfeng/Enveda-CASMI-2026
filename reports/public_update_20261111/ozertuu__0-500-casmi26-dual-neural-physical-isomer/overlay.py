# ===== 0.500+ APEX OVERLAY: ADDUCT-AWARE CALIBRATED SPECTRAL LIBRARY RANK-1 PROMOTION =====
# Integrates external measured MS/MS reference libraries (Takumu Hata extlib CC0 & MassBank harmonized).
# Key Breakthroughs:
# 1. Adduct-Aware Neutral Mass Alignment: Calculates true query neutral mass using adduct delta table,
#    completely preventing false-positive cross-adduct collisions (e.g. [M+Na]+ colliding with [M+H]+ of unrelated compounds).
# 2. Strict Adduct Compatibility: [M+Na]+ queries match [M+Na]+ references; [M+H]+ and [M+NH4]+ match [M+H]+;
#    [M-H]- and formate match [M-H]-.
# 3. Candidate Exact Mass Sanity Gate: Validates ExactMolWt(match_smi) against query neutral mass (<= 15 ppm).
# 4. InChIKey-14 Deduplication & Structural Rank Protection:
#    - If match_smi has the same InChIKey-14 as the current leader: Rank 1 is already correct, zero disruption.
#    - If match_smi is in candidate pool at rank k > 1: promotes that exact candidate to Rank 1.
#    - If match_smi is an outside candidate: promotes to Rank 1 and deduplicates top 25 InChIKey-14.

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

    # Locate test.parquet
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
        
        delta = ADDUCT_DELTA.get(adduct, 1.007276 * mode)
        nm = prec - delta
        
        queries.setdefault(mid, []).append(dict(mz=m, it=it, prec=prec, mode=mode, adduct=adduct, nm=nm))

    # Read existing pipeline library confidence
    lib_max = {}
    ev_path = os.path.join(work, 'frozen_candidate_evidence.parquet')
    if os.path.exists(ev_path):
        try:
            ev = pd.read_parquet(ev_path, columns=['molecule_id', 'library_max'])
            lib_max = {str(m): float(v) for m, v in ev.groupby('molecule_id', sort=False).library_max.first().items()}
        except Exception:
            pass

    # Reference tuples: (mode, prec, nm, adduct, mz_arr, it_arr, key, smiles)
    refs = []
    
    # Check Source A: Takumu Hata extlib (ext_meta.parquet + ext_mz.npy / ext_in.npy)
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

    if not refs:
        print('[apex-extlib] No external reference spectra available; keeping submission untouched.')
        return

    # Sort references by neutral mass for fast, accurate binary search
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
        # Same adduct always compatible
        if q_adduct and ref_adduct and q_adduct == ref_adduct:
            return True
        # Ammonium adduct [M+NH4]+ readily loses neutral NH3 in CID to form [M+H]+ fragments
        if q_adduct == '[M+NH4]+' and ref_adduct == '[M+H]+':
            return True
        if q_adduct == '[M+H]+' and ref_adduct == '[M+NH4]+':
            return True
        # Formate adduct [M+CH2O2-H]- or [M+HCOO]-
        if q_adduct in ('[M+CH2O2-H]-', '[M+HCOO]-', '[M+CHO2]-') and ref_adduct in ('[M+CH2O2-H]-', '[M+HCOO]-', '[M+CHO2]-'):
            return True
        # Default [M+H]+ or [M-H]-
        if (not q_adduct or q_adduct == '[M+H]+') and (not ref_adduct or ref_adduct == '[M+H]+'):
            return True
        if (not q_adduct or q_adduct == '[M-H]-') and (not ref_adduct or ref_adduct == '[M-H]-'):
            return True
        return False

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

            best_match = (0.0, 0, None, 0.0)  # (cosine, n_peaks, smi, q_nm)
            for q in q_list:
                q_mode, q_nm, q_adduct = q['mode'], q['nm'], q['adduct']
                q_mz, q_it = q['mz'], q['it']
                
                # Search window on neutral mass: 12 ppm + 0.002 Da
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
            if match_smi is not None and best_cos >= TAU:
                # Candidate Exact Mass Sanity Check (<= 15 ppm against query neutral mass)
                cand_nm = _calc_nm(match_smi)
                if cand_nm is not None and abs(cand_nm - match_q_nm) / match_q_nm > 15e-6:
                    # Reject cross-adduct isobaric collision
                    new_smiles_list.append(smiles_str)
                    continue

                hits_count += 1
                curr_keys = [_to_k14(s) for s in smis]
                match_k14 = _to_k14(match_smi)

                # InChIKey-14 Deduplication & Structural Rank Protection
                if match_k14 and match_k14 == curr_keys[0]:
                    # Rank 1 already has this exact connectivity skeleton!
                    new_smis = list(smis)
                elif match_k14 and match_k14 in curr_keys[1:]:
                    # Candidate exists in pool at rank k > 1: promote native candidate to Rank 1
                    idx = curr_keys.index(match_k14)
                    new_smis = [smis[idx]] + [s for i, s in enumerate(smis) if i != idx]
                    promoted_count += 1
                else:
                    # True outside candidate: promote to Rank 1 and deduplicate top 25
                    seen = {match_k14} if match_k14 else set()
                    new_smis = [match_smi]
                    for s, k in zip(smis, curr_keys):
                        if k not in seen:
                            seen.add(k)
                            new_smis.append(s)
                        if len(new_smis) == 25:
                            break
                    if len(new_smis) < 25:
                        for s in smis:
                            if s not in new_smis:
                                new_smis.append(s)
                            if len(new_smis) == 25:
                                break
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
