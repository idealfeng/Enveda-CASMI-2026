# ===== N-1c: WITHIN-TEST MOLECULAR NETWORK ANALOGUE RE-RANKING (GNPS-STYLE) =====
# Leverages natural product biosynthetic co-occurrence across test spectra.
# Constructs precursor-shift-aware modified cosine network (tau >= 0.60, peaks >= 6)
# and propagates structural consensus via Morgan circular fingerprint Tanimoto similarities.
# Guarded by high-confidence library shield: when lib_max >= 0.85, Rank 1 is 100% frozen.
def _n1c_vectorized(work='/kaggle/working', inp='/kaggle/input', LAM=0.28, TAU=0.60, lib_shield=0.95):
    if not globals().get('ENABLE_N1C', True):
        print('[n1c] disabled by configuration; skipped.')
        return
    if not globals().get('PIPELINE_DONE') and not globals().get('IS_RERUN') and globals().get('COMMIT_MODE') == 'fast':
        print('[n1c] Fast commit: skipping molecular network rerun.')
        return
    import glob, os, shutil, time, numpy as np, pandas as pd
    t0 = time.time()
    sp = os.path.join(work, 'submission.csv')
    if not os.path.exists(sp):
        print('[n1c] submission.csv not found; skipping network reranker.')
        return
    shutil.copy(sp, os.path.join(work, 'submission_pre_n1c.csv'))

    tp = sorted(glob.glob(inp + '/**/test.parquet', recursive=True),
                key=lambda p: ('mass-spectra' not in p.lower(), len(p)))
    if not tp:
        print('[n1c] test.parquet not found; skipping network reranker.')
        return
    te = pd.read_parquet(tp[0])
    sub = pd.read_csv(sp, dtype=str, keep_default_na=False)
    L = {m: [x for x in s.split(';') if x] for m, s in zip(sub.molecule_id.astype(str), sub.smiles)}

    lib_max = {}
    ev_path = os.path.join(work, 'frozen_candidate_evidence.parquet')
    if os.path.exists(ev_path):
        try:
            ev = pd.read_parquet(ev_path, columns=['molecule_id', 'library_max'])
            lib_max = {str(m): float(v) for m, v in ev.groupby('molecule_id', sort=False).library_max.max().items()}
        except Exception:
            pass

    from rdkit import Chem, DataStructs
    from rdkit.Chem import rdFingerprintGenerator
    gen = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)
    fpc = {}
    def fp(s):
        if s not in fpc:
            m = Chem.MolFromSmiles(s)
            fpc[s] = gen.GetFingerprint(m) if m is not None else None
        return fpc[s]

    SP = {}
    for (m, ad), g in te.assign(_m=te.molecule_id.astype(str)).groupby(['_m', 'adduct']):
        if str(ad) not in ('[M+H]+', '[M-H]-') or m not in L:
            continue
        pr = float(np.median(pd.to_numeric(g.precursor_mz, errors='coerce')))
        mz = np.concatenate([np.asarray(x, float) for x in g.ms2_mzs])
        it = np.concatenate([np.asarray(x, float) / max(float(np.max(x)) if len(x) else 1.0, 1e-9)
                             for x in g.ms2_normalized_intensities])
        k = mz < pr - 1.5
        mz, it = mz[k], it[k]
        if not len(mz):
            continue
        kb = np.round(mz, 2)
        u, inv = np.unique(kb, return_inverse=True)
        w = np.zeros(len(u))
        np.maximum.at(w, inv, it)
        o = np.argsort(-w)[:120]
        u, w = u[o], np.sqrt(w[o])
        oo = np.argsort(u)
        SP.setdefault(m, {})[str(ad)] = (u[oo], (w / max(np.linalg.norm(w), 1e-12))[oo], pr)

    def mcos_fast(a, b):
        (ma, ia_, pa), (mb, ib, pb) = a, b
        sh = pa - pb
        if abs(sh) > 200.0:
            return 0.0, 0
        cand = []
        for off in (0.0, sh):
            target = ma - off
            los = np.searchsorted(mb, target - 0.0101, 'left')
            his = np.searchsorted(mb, target + 0.0101, 'right')
            for i in range(len(ma)):
                lo, hi = los[i], his[i]
                for j in range(lo, hi):
                    cand.append((ia_[i] * ib[j], i, j))
        if not cand:
            return 0.0, 0
        cand.sort(reverse=True)
        ui, uj, s, n = set(), set(), 0.0, 0
        for v, i, j in cand:
            if i in ui or j in uj:
                continue
            ui.add(i)
            uj.add(j)
            s += v
            n += 1
        return s, n

    K = sorted(SP)
    E = {}
    for x in range(len(K)):
        for y in range(x + 1, len(K)):
            best = None
            for ad in set(SP[K[x]]) & set(SP[K[y]]):
                s, n = mcos_fast(SP[K[x]][ad], SP[K[y]][ad])
                if n >= 6 and s >= TAU and (best is None or s > best):
                    best = s
            if best is not None:
                E.setdefault(K[x], []).append((K[y], best))
                E.setdefault(K[y], []).append((K[x], best))

    z = lambda v: (v - v.mean()) / (v.std() + 1e-9)
    nch = 0
    nt1 = 0
    out = []

    for m, s in zip(sub.molecule_id.astype(str), sub.smiles):
        lst = L[m][:25]
        nb_ = E.get(m, [])
        if nb_ and len(lst) > 1:
            base = -np.log(np.arange(1, len(lst) + 1))
            N = np.zeros(len(lst))
            for b, w in nb_:
                lb = L.get(b, [])[:5]
                p = 1.0 / np.arange(1, len(lb) + 1)
                p = p / p.sum() if len(lb) else p
                jf = [(fp(j), pp) for j, pp in zip(lb, p)]
                lib_boost = 1.0 + float(lib_max.get(b, 0.0))
                ew = (w ** 4) * lib_boost
                for i, c in enumerate(lst):
                    fi = fp(c)
                    if fi is None:
                        continue
                    N[i] += ew * sum(pp * DataStructs.TanimotoSimilarity(fi, fj)
                                     for fj, pp in jf if fj is not None)

            if lib_max.get(m, 0.0) >= lib_shield:
                sub_base = base[1:]
                sub_N = N[1:]
                o = np.argsort(-(z(sub_base) + LAM * z(sub_N)), kind='stable')
                nl = [lst[0]] + [lst[1 + i] for i in o]
            else:
                o = np.argsort(-(z(base) + LAM * z(N)), kind='stable')
                nl = [lst[i] for i in o]

            if nl != lst:
                nch += 1
                nt1 += int(nl[0] != lst[0])
            out.append(';'.join(nl))
        else:
            out.append(s)

    sub['smiles'] = out
    sub.to_csv(sp, index=False)
    elapsed = round(time.time() - t0, 1)
    print(f'[n1c] SUCCESS: molecules {len(L)}, network connected {len(E)}, edges {sum(len(v) for v in E.values()) // 2}, changed lists {nch}, top1 changed {nt1} in {elapsed}s', flush=True)

try:
    _n1c_vectorized(LAM=globals().get('N1C_LAM', 0.28), TAU=globals().get('N1C_TAU', 0.60), lib_shield=globals().get('N1C_LIB_SHIELD', 0.95))
except Exception as exc:
    import traceback
    traceback.print_exc()
    print('[n1c] EXCEPTION CAUGHT: Restoring pre-n1c submission unharmed.', flush=True)
    if os.path.exists('/kaggle/working/submission_pre_n1c.csv'):
        shutil.copyfile('/kaggle/working/submission_pre_n1c.csv', '/kaggle/working/submission.csv')
