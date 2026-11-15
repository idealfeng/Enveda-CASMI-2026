# ===== heliosli push489 generation, part A (before the FRIGID merge): decoder v3 proposes structures outside the list and the panel-fitted verifier picks one (reports/c3_design_v0.md 38-39) =====
# Per molecule: z = fold-safe FPNet model 0 on the test spectra (engine protocol, as the decoder was trained); formula = the
# current rank 1's; decoder v3 (heliosli/casmi26-denovo-v3) samples PGN_SAMPLES times. Exact-formula structures not in the
# list are ranked by a conditional logit fitted on the 234-NP panel (none seen by FPNet model 0 or the decoder) over
# within-molecule z-scores of: log(1 + sample count), the decoder's log-likelihood (teacher-forced), FPNet's cfp . z and
# the fragment explanation of the test spectra (casmi.frag, MetFrag-lite; credited by sqrt intensity). Panel, 256 samples:
# top = truth 14.0% (count alone 11.7%). The top and its softmax share p go to push_gen.json; part B inserts it.
PGN_SAMPLES = 256
PGN_W = dict(cnt=0.313, ll=1.6047, fpz=1.1329, fr_w=0.8021, fr1h1=-0.2414, fr2h2=-0.2729, fr2h2_top10=0.0375)
PGN_RAW_CHECK = ("CC(=O)Oc1ccccc1C(=O)O", 16551, 431)


def _pushgen_a(work='/kaggle/working', inp='/kaggle/input'):
    import glob
    import json
    import os
    import shutil
    import sys
    import time

    import numpy as np
    import pandas as pd
    import torch
    import torch.nn.functional as F

    t0 = time.monotonic()
    budget = 4.5 * 3600.0
    if "NB_T0" in globals():
        budget = max(0.0, min(budget, 7.9 * 3600 - (time.time() - float(globals()["NB_T0"]))))

    def find(pattern):
        hits = sorted(glob.glob(inp + "/**/" + pattern, recursive=True), key=len)
        return hits[0] if hits else None

    v4 = os.environ.get("PXR_V4") or globals().get("V4CODE")
    if not v4:
        if os.path.isdir(os.path.join(work, "v43_v4code", "casmi")):
            v4 = os.path.join(work, "v43_v4code")
        else:
            h = find("casmi26-v4b-models/**/casmi/engine.py")
            v4 = os.path.dirname(os.path.dirname(h)) if h else None
    fp0 = os.environ.get("PDN_FPNET") or find("casmi26-fold-safe-fpnet/fpnet_fold0.pt") or find("fpnet_fold0.pt")
    dec, zst, dmod = find("denovo_v3.pt"), find("denovo_zstats.npz"), find("denovo_model.py")
    if not (v4 and fp0 and dec and zst and dmod):
        print("[pushgen] skipped: missing", dict(v4=bool(v4), fpnet=bool(fp0), decoder=bool(dec), zstats=bool(zst), code=bool(dmod)))
        return
    code = "/tmp/pushgencode" if os.name != "nt" else os.path.join(work, "_pushgencode")
    os.makedirs(code, exist_ok=True)
    shutil.copy(dmod, code)
    for d in (v4, code):
        if d in sys.path:
            sys.path.remove(d)
        sys.path.insert(0, d)
    from casmi import chem, fpnet
    from casmi import frag as fragmod
    from casmi.spectra import merge_spectra, prep_query
    from rdkit import Chem, RDLogger
    from rdkit.Chem.rdMolDescriptors import CalcMolFormula
    import denovo_model as DM
    RDLogger.DisableLog("rdApp.*")
    bits = np.load(os.path.join(os.path.dirname(fp0), "fp_bits.npy"))
    raw0 = chem.raw_fingerprint(PGN_RAW_CHECK[0])
    if raw0 is None or len(raw0) != PGN_RAW_CHECK[1] or int(raw0.sum()) != PGN_RAW_CHECK[2]:
        print("[pushgen] fingerprint code differs from the offline build: skipped")
        return
    te_df = globals().get("te")
    if not isinstance(te_df, pd.DataFrame) or "ms2_mzs" not in te_df.columns:
        tp = globals().get("TEST_PATH")
        if tp is None or not os.path.exists(str(tp)):
            hits = sorted(glob.glob(inp + "/**/test.parquet", recursive=True), key=lambda p: ("mass-spectra" not in p.lower(), len(p)))
            tp = hits[0]
        te_df = pd.read_parquet(str(tp))
    cols = ["precursor_mz", "ms2_mzs", "ms2_normalized_intensities", "adduct", "ionization_mode", "collision_energy_ev"]
    raw = {}
    for r in te_df.itertuples(index=False):
        raw.setdefault(str(r.molecule_id), []).append({c: getattr(r, c, None) for c in cols})
    sub = pd.read_csv(os.path.join(work, "submission.csv"), dtype=str, keep_default_na=False)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    bank = fpnet.ModelBank([fp0], dev)
    if bank.nbits != len(bits):
        print("[pushgen] FPNet bits %d != %d: skipped" % (bank.nbits, len(bits)))
        return
    model, itos = DM.load(dec, dev)
    stoi = {t: i for i, t in enumerate(itos)}
    dt = DM.amp_dtype(dev)
    zz = np.load(zst)
    mu, sd = zz["mu"].astype(np.float32), zz["sd"].astype(np.float32)

    def fp_logits(rs):
        """engine.py's FPNet queries: every spectrum alone + the spectra of each polarity merged; z = 0.5 (mean + mean)."""
        sp = []
        for s_ in rs[:8]:
            try:
                arr = np.asarray(s_.get("collision_energy_ev"), np.float64).ravel()
                ce = float(np.nanmean(arr)) if arr.size else np.nan
                ce_n = int(np.sum(~np.isnan(arr))) if arr.size else 1
            except Exception:
                ce, ce_n = np.nan, 1
            sp.append(dict(mz=np.asarray(s_["ms2_mzs"], np.float64), it=np.asarray(s_["ms2_normalized_intensities"], np.float64), prec=float(s_["precursor_mz"]),
                           adduct=str(s_["adduct"]), ce=ce, ce_n=max(1, ce_n), mode=1 if str(s_["ionization_mode"]) == "positive" else -1))
        items_s = []
        for s_ in sp:
            pm, pi = fpnet.prep_peaks(s_["mz"], s_["it"], s_["prec"])
            ok = not np.isnan(s_["ce"])
            items_s.append(dict(mz=pm, it=pi, prec=s_["prec"], adduct_ix=chem.adduct_index(s_["adduct"]), ce=s_["ce"] if ok else 0.0,
                                ce_known=1.0 if ok else 0.0, n_merged=min(s_["ce_n"], 8), mode=float(s_["mode"])))
        items_m = []
        for md in (1, -1):
            grp = [s_ for s_ in sp if s_["mode"] == md]
            if not grp:
                continue
            mm, ii = merge_spectra([(s_["mz"], s_["it"]) for s_ in grp])
            prec = float(np.median([s_["prec"] for s_ in grp]))
            pm, pi = fpnet.prep_peaks(mm, ii, prec)
            ces = [s_["ce"] for s_ in grp if not np.isnan(s_["ce"])]
            ads = [s_["adduct"] for s_ in grp]
            items_m.append(dict(mz=pm, it=pi, prec=prec, adduct_ix=chem.adduct_index(max(set(ads), key=ads.count)), ce=float(np.mean(ces)) if ces else 0.0,
                                ce_known=1.0 if ces else 0.0, n_merged=min(sum(s_["ce_n"] for s_ in grp), 8), mode=float(md)))
        zs_ = bank.logits(items_s)
        zm_ = bank.logits(items_m) if items_m else zs_
        return 0.5 * (zs_.mean(0) + zm_.mean(0))

    LEVELS = [(1, 0), (1, 1), (1, 2), (2, 0), (2, 1), (2, 2)]
    CREDIT = {(1, 0): 1.0, (1, 1): 0.8, (2, 0): 0.7, (2, 1): 0.5, (1, 2): 0.4, (2, 2): 0.25}

    def frag_feats(smiles, peaks):
        """denovo_verify.frag_row: fr_w, fr1h1, fr2h2, fr2h2_top10 (max over the molecule's spectra)"""
        f = {1: fragmod.fragments_for_smiles(smiles, max_depth=1), 2: fragmod.fragments_for_smiles(smiles, max_depth=2)}
        per = {lv: [] for lv in LEVELS}
        top10, wsc = [], []
        for mz, it, adduct in peaks:
            w = np.sqrt(np.asarray(it, np.float64))
            tot = w.sum()
            credit = np.zeros(len(mz))
            for d, h in LEVELS:
                ok = np.zeros(len(mz), bool)
                for dl in fragmod.ion_deltas(adduct):
                    ok |= fragmod.explain_peaks(f[d], mz, w, dl, h, 0.01, 15.0)
                per[(d, h)].append(w[ok].sum() / tot)
                credit = np.maximum(credit, CREDIT[(d, h)] * ok)
                if (d, h) == (2, 2):
                    top10.append(ok[np.argsort(-w)[:10]].mean())
            wsc.append((w * credit).sum() / tot)
        return dict(fr_w=max(wsc), fr1h1=max(per[(1, 1)]), fr2h2=max(per[(2, 2)]), fr2h2_top10=max(top10))

    def encode(s):
        t = DM.TOK.findall(s)
        if "".join(t) != s or len(t) > DM.MAXLEN or any(x not in stoi for x in t):
            return None
        return [DM.BOS] + [stoi[x] for x in t] + [DM.EOS]

    @torch.no_grad()
    def loglik(mem1, toks):
        L = max(len(t) for t in toks)
        tk = torch.zeros((len(toks), L), dtype=torch.long, device=dev)
        for i, t in enumerate(toks):
            tk[i, :len(t)] = torch.tensor(t, device=dev)
        with torch.autocast("cuda", dtype=dt, enabled=dev == "cuda"):
            lg = model(mem1.expand(len(toks), -1, -1), tk[:, :-1]).float()
        lp = -F.cross_entropy(lg.reshape(-1, lg.shape[-1]), tk[:, 1:].reshape(-1), ignore_index=DM.PAD, reduction="none")
        return lp.view(len(toks), -1).sum(1).cpu().numpy()

    kcache = {}

    def key14(s):
        if s not in kcache:
            try:
                mm = Chem.MolFromSmiles(s)
                kcache[s] = Chem.MolToInchiKey(mm)[:14] if mm is not None else None
            except Exception:
                kcache[s] = None
        return kcache[s]

    audit = dict(samples=PGN_SAMPLES, molecules=len(sub), processed=0, with_candidate=0, failed=0, timed_out=0, budget_s=round(budget, 1), pool=[], p=[])
    out = {}
    for mid, smiles in zip(sub["molecule_id"].astype(str), sub["smiles"].astype(str)):
        if time.monotonic() - t0 > budget:
            audit["timed_out"] += 1
            continue
        try:
            L = [s for s in smiles.split(";") if s]
            if not L or mid not in raw:
                continue
            r0 = Chem.MolFromSmiles(L[0])
            if r0 is None:
                continue
            f0 = CalcMolFormula(r0)
            lk = {key14(x) for x in L}
            z = fp_logits(raw[mid]).astype(np.float32)
            x = DM.std_input(z, mu, sd)
            audit["processed"] += 1
            cnt, smi_of = {}, {}
            for s in DM.sample(model, itos, x, f0, PGN_SAMPLES, dev):
                m = Chem.MolFromSmiles(s) if s else None
                if m is None or CalcMolFormula(m) != f0:
                    continue
                k = Chem.MolToInchiKey(m)[:14]
                if not k or k in lk:
                    continue
                cnt[k] = cnt.get(k, 0) + 1
                smi_of.setdefault(k, Chem.MolToSmiles(m, isomericSmiles=False))
            if not cnt:
                continue
            ks = list(cnt)
            peaks = []
            for s_ in raw[mid]:
                pm, pv = prep_query(np.asarray(s_["ms2_mzs"], np.float64), np.asarray(s_["ms2_normalized_intensities"], np.float64), 0.002, 128, 1.0, False)
                if len(pm):
                    peaks.append((pm, pv / pv.max(), str(s_["adduct"])))
            feats = {c: np.zeros(len(ks)) for c in PGN_W}
            feats["cnt"] = np.log1p(np.array([cnt[k] for k in ks], np.float64))
            for i, k in enumerate(ks):
                rf = chem.raw_fingerprint(smi_of[k])
                feats["fpz"][i] = float(rf[bits].astype(np.float32) @ z) if rf is not None else np.nan
                if peaks:
                    for c, v in frag_feats(smi_of[k], peaks).items():
                        feats[c][i] = v
            with torch.no_grad(), torch.autocast("cuda", dtype=dt, enabled=dev == "cuda"):
                mem1 = model.memory(torch.from_numpy(x[None]).to(dev), torch.from_numpy(DM.fvec(f0)[None]).to(dev), torch.ones(1, dtype=torch.long, device=dev))
            toks = [encode(smi_of[k]) for k in ks]
            okk = [i for i, t in enumerate(toks) if t is not None]
            ll = np.full(len(ks), np.nan)
            for a in range(0, len(okk), 256):
                ii = okk[a:a + 256]
                ll[ii] = loglik(mem1, [toks[i] for i in ii])
            feats["ll"] = ll
            score = np.zeros(len(ks))
            for c, w in PGN_W.items():
                v = feats[c].astype(np.float64)
                v = np.where(np.isnan(v), np.nanmin(v) if np.isfinite(v).any() else 0.0, v)
                s_d = v.std()
                score += w * ((v - v.mean()) / s_d if s_d > 1e-9 else np.zeros_like(v))
            pr = np.exp(score - score.max())
            pr /= pr.sum()
            i = int(np.argmax(score))
            out[mid] = dict(smiles=smi_of[ks[i]], key=ks[i], p=float(pr[i]), count=int(cnt[ks[i]]), top_count=int(max(cnt.values())), pool=len(ks))
            audit["with_candidate"] += 1
            audit["pool"].append(len(ks))
            audit["p"].append(float(pr[i]))
        except Exception as exc:
            audit["failed"] += 1
            if audit["failed"] <= 3:
                print("[pushgen] molecule failed:", mid, repr(exc)[:200])
    with open(os.path.join(work, "push_gen.json"), "w") as f:
        json.dump(out, f)
    pool, pp = audit.pop("pool"), audit.pop("p")
    audit["pool_median"] = float(np.median(pool)) if pool else 0.0
    audit["p_median"] = float(np.median(pp)) if pp else 0.0
    audit["seconds"] = round(time.monotonic() - t0, 1)
    with open(os.path.join(work, "pushgen_a_audit.json"), "w") as f:
        json.dump(audit, f, indent=1)
    print("[pushgen] part A done:", json.dumps(audit))


try:
    _pushgen_a(**globals().get("PGN_DRYRUN_ARGS", {}))
except Exception:
    import traceback

    traceback.print_exc()
    print("[pushgen] part A failed; nothing will be inserted")
