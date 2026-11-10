"""Shared harness for Q3/Q4/Q5: the REAL canqiang E006 Engine (spectral analog channel,
identity exclusion, fpnet bank, LightGBM ranker) driven on the dev panel with generate off/on.
"""
import os
import sys

ROOT = "/mnt/d/Paper/casmi"
CODE = f"{ROOT}/third_party/canqiang_e006/engine_source_v4b/code"
sys.path.insert(0, CODE)

WORK = f"{ROOT}/runs/q345_workdir"
SPEC = f"{ROOT}/runs/shared_spec_cache"
POOLD = f"{ROOT}/assets/kaggle/ahmedberatozer/casmi26-v2-pool/v1"
MODELS = f"{ROOT}/assets/kaggle/ahmedberatozer/casmi26-v4b-models/v4"
DEV = f"{ROOT}/runs/validation_pilot_v2_20261104"

import numpy as np
import pandas as pd
from casmi import chem
from casmi.library import Library
from casmi.pool import Pool
from casmi.engine import Engine, EngineCfg, FEATURES


def ensure_workdir():
    os.makedirs(WORK, exist_ok=True)
    for name in ["spec_off.npy", "spec_mz.npy", "spec_it.npy", "spec_meta.parquet"]:
        dst = f"{WORK}/{name}"
        if not os.path.islink(dst):
            os.symlink(f"{SPEC}/{name}", dst)
    for name in ["train_structs.parquet", "pool_meta.parquet", "pool_fp.npy",
                 "fp_bits.npy", "pool_frag_off.npy", "pool_frag_mass.npy"]:
        dst = f"{WORK}/{name}"
        if not os.path.islink(dst):
            os.symlink(f"{POOLD}/{name}", dst)


_CACHE = {}


def load_library_pool():
    if "L" not in _CACHE:
        ensure_workdir()
        _CACHE["L"] = Library(WORK)
        _CACHE["P"] = Pool(WORK)
        _CACHE["train_fp"] = np.load(f"{POOLD}/train_fp_sel.npy")
    return _CACHE["L"], _CACHE["P"], _CACHE["train_fp"]


def load_engine(cfg=None, bank=False, xscorer=None):
    L, P, train_fp = load_library_pool()
    cfg = cfg or EngineCfg()
    bank_obj = None
    if bank:
        from casmi.fpnet import ModelBank
        paths = [f"{MODELS}/fpnet_0.pt", f"{MODELS}/fe_A.pt", f"{MODELS}/fe_B.pt", f"{MODELS}/fe_D.pt"]
        bank_obj = ModelBank([p for p in paths if os.path.exists(p)])
    return Engine(L, P, train_fp, cfg, bank=bank_obj, xscorer=xscorer)


def load_rankbag():
    from casmi.ranker import RankerBag
    return RankerBag.load(f"{MODELS}/ranker_v4b.pkl")


def load_queries_truth():
    queries = pd.read_parquet(f"{DEV}/queries.parquet")
    truth = pd.read_csv(f"{DEV}/truth.csv", dtype=str, keep_default_na=False)
    return queries, truth


def build_query(queries, mid):
    q = queries[queries.molecule_id == mid]
    spectra = []
    for _, r in q.iterrows():
        mz = np.asarray(r.ms2_mzs, np.float64)
        it = np.asarray(r.ms2_normalized_intensities, np.float64)
        mode = 1 if str(r.ionization_mode) == "positive" else -1
        adduct = r.adduct
        if not isinstance(adduct, str):
            adduct = str(np.asarray(adduct).reshape(-1)[0])
        prec = float(np.asarray(r.precursor_mz).reshape(-1)[0])
        ce_raw = np.asarray(r.collision_energy_ev, np.float64).reshape(-1)
        ce_raw = ce_raw[~np.isnan(ce_raw)]
        ce = float(ce_raw.mean()) if len(ce_raw) else None
        ce_n = int(len(ce_raw))
        spectra.append(dict(mz=mz, it=it, mode=mode, adduct=adduct, prec=prec, ce=ce, ce_n=ce_n))
    masses = chem.neutral_mass(np.array([s["prec"] for s in spectra], np.float64),
                               np.array([s["adduct"] for s in spectra], dtype=object))
    target = float(np.nanmedian(masses))
    return spectra, target


def top25_from(C, score):
    """Rank candidates by score desc -> list of (rank, smiles, key, is_gen)."""
    order = np.argsort(-score, kind="stable")
    out = []
    for rank, i in enumerate(order[:25], 1):
        out.append(dict(rank=rank, smiles=C.smiles[i], key=C.key[i], is_gen=bool(C.is_gen[i] > 0),
                        pid=int(C.pid[i])))
    return out


def mrr_top1(ranked, truth_identity):
    for r in ranked:
        if r["key"] == truth_identity:
            return 1.0 / r["rank"], 1.0, r["rank"]
    return 0.0, 0.0, None


def find_truth_sid_pid(eng, truth_key):
    """Return (library structure sid, pool pid) for a truth InChIKey14, or (-1, -1)."""
    L = eng.L; P = eng.pool
    sids = np.flatnonzero(L.struct_key == truth_key)
    sid = int(sids[0]) if len(sids) else -1
    pid = P.key2pid.get(truth_key, -1)
    return sid, pid


def class3_analogs_window(eng, spectra, target, truth_key):
    """True Class-3: hide truth reference spectra from the analog channel, and remove the
    truth pool entry so generation is allowed to produce it. Returns (analogs, exclude_keys)."""
    sid, pid = find_truth_sid_pid(eng, truth_key)
    analogs = eng.analogs(spectra, target, exclude_sid=sid)
    win = eng.pool.window(target, eng.cfg.ppm_win)
    if pid >= 0:
        win = win[win != pid]
    exclude_keys = set(eng.pool.key[c] for c in win)
    return analogs, exclude_keys
