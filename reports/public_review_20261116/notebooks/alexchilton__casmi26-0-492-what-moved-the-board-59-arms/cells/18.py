# ===== N-1c (Fable EK-18): test içi moleküler ağ yeniden sıralaması (λ 0.25, τ 0.6); overlay'den önce; hata -> aynen =====
def _n1c(work='/kaggle/working', inp='/kaggle/input', LAM=0.25, TAU=0.6):
    import glob, os, shutil, time, numpy as np, pandas as pd
    t0 = time.time(); sp = os.path.join(work, 'submission.csv')
    if not os.path.exists(sp): print('[n1c] no submission.csv'); return
    shutil.copy(sp, os.path.join(work, 'submission_pre_n1c.csv'))
    tp = sorted(glob.glob(inp + '/**/test.parquet', recursive=True), key=lambda p: ('mass-spectra' not in p.lower(), len(p)))
    te = pd.read_parquet(tp[0]); sub = pd.read_csv(sp, dtype=str, keep_default_na=False)
    L = {m: [x for x in s.split(';') if x] for m, s in zip(sub.molecule_id.astype(str), sub.smiles)}
    from rdkit import Chem, DataStructs
    from rdkit.Chem import rdFingerprintGenerator
    gen = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048); fpc = {}
    def fp(s):
        if s not in fpc:
            m = Chem.MolFromSmiles(s); fpc[s] = gen.GetFingerprint(m) if m is not None else None
        return fpc[s]
    SP = {}
    for (m, ad), g in te.assign(_m=te.molecule_id.astype(str)).groupby(['_m', 'adduct']):
        if str(ad) not in ('[M+H]+', '[M-H]-') or m not in L: continue
        pr = float(np.median(pd.to_numeric(g.precursor_mz, errors='coerce')))
        mz = np.concatenate([np.asarray(x, float) for x in g.ms2_mzs]); it = np.concatenate([np.asarray(x, float) / max(float(np.max(x)) if len(x) else 1.0, 1e-9) for x in g.ms2_normalized_intensities])
        k = mz < pr - 1.5; mz, it = mz[k], it[k]
        if not len(mz): continue
        kb = np.round(mz, 2); u, inv = np.unique(kb, return_inverse=True); w = np.zeros(len(u)); np.maximum.at(w, inv, it)
        o = np.argsort(-w)[:120]; u, w = u[o], np.sqrt(w[o]); oo = np.argsort(u)
        SP.setdefault(m, {})[str(ad)] = (u[oo], (w / max(np.linalg.norm(w), 1e-12))[oo], pr)
    def mcos(a, b):
        (ma, ia_, pa), (mb, ib, pb) = a, b; sh = pa - pb; cand = []
        for i in range(len(ma)):
            for off in (0.0, sh):
                lo, hi = np.searchsorted(mb, ma[i] - off - 0.0101), np.searchsorted(mb, ma[i] - off + 0.0101, 'right')
                for j in range(lo, hi): cand.append((ia_[i] * ib[j], i, j))
        cand.sort(reverse=True); ui, uj, s, n = set(), set(), 0.0, 0
        for v, i, j in cand:
            if i in ui or j in uj: continue
            ui.add(i); uj.add(j); s += v; n += 1
        return s, n
    K = sorted(SP); E = {}
    for x in range(len(K)):
        for y in range(x + 1, len(K)):
            best = None
            for ad in set(SP[K[x]]) & set(SP[K[y]]):
                s, n = mcos(SP[K[x]][ad], SP[K[y]][ad])
                if n >= 6 and s >= TAU and (best is None or s > best): best = s
            if best is not None: E.setdefault(K[x], []).append((K[y], best)); E.setdefault(K[y], []).append((K[x], best))
    z = lambda v: (v - v.mean()) / (v.std() + 1e-9); nch = nt1 = 0; out = []
    for m, s in zip(sub.molecule_id.astype(str), sub.smiles):
        lst = L[m][:25]; nb_ = E.get(m, [])
        if nb_ and len(lst) > 1:
            base = -np.log(np.arange(1, len(lst) + 1)); N = np.zeros(len(lst))
            for b, w in nb_:
                lb = L.get(b, [])[:5]; p = 1 / np.arange(1, len(lb) + 1); p = p / p.sum() if len(lb) else p
                jf = [(fp(j), pp) for j, pp in zip(lb, p)]
                for i, c in enumerate(lst):
                    fi = fp(c)
                    if fi is None: continue
                    N[i] += w ** 4 * sum(pp * DataStructs.TanimotoSimilarity(fi, fj) for fj, pp in jf if fj is not None)
            o = np.argsort(-(z(base) + LAM * z(N)), kind='stable'); nl = [lst[i] for i in o]
            if nl != lst: nch += 1; nt1 += nl[0] != lst[0]
            out.append(';'.join(nl))
        else: out.append(s)
    sub['smiles'] = out; sub.to_csv(sp, index=False)
    print(f'[n1c] LAM={LAM} TAU={TAU} molecules {len(L)}, with spectra {len(K)}, with neighbors {len(E)}, edges {sum(len(v) for v in E.values()) // 2}, changed lists {nch}, top1 changed {nt1}, {time.time() - t0:.0f}s', flush=True)
try:
    _n1c(LAM=0.35, TAU=0.6)
except Exception:
    import traceback; traceback.print_exc(); print('[n1c] FAILED -> submission unchanged', flush=True)
