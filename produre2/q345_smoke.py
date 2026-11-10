"""Smoke test: can we instantiate the real canqiang E006 Engine (Library+Pool+fpnet+ranker)
and run generate off/on on one dev-panel query with the REAL spectral analog channel?"""
import os
import sys

ROOT = "/mnt/d/Paper/casmi"
CODE = f"{ROOT}/third_party/canqiang_e006/engine_source_v4b/code"
sys.path.insert(0, CODE)

# --- build a combined workdir via symlinks (Linux/WSL only) -------------------------------
WORK = f"{ROOT}/runs/q345_workdir"
os.makedirs(WORK, exist_ok=True)
SPEC = f"{ROOT}/runs/shared_spec_cache"
POOL = f"{ROOT}/assets/kaggle/ahmedberatozer/casmi26-v2-pool/v1"
for name in ["spec_off.npy", "spec_mz.npy", "spec_it.npy", "spec_meta.parquet"]:
    dst = f"{WORK}/{name}"
    if not os.path.islink(dst):
        os.symlink(f"{SPEC}/{name}", dst)
for name in ["train_structs.parquet", "pool_meta.parquet", "pool_fp.npy",
             "fp_bits.npy", "pool_frag_off.npy", "pool_frag_mass.npy"]:
    dst = f"{WORK}/{name}"
    if not os.path.islink(dst):
        os.symlink(f"{POOL}/{name}", dst)
print("workdir ready", flush=True)

import numpy as np
import pandas as pd

from casmi.library import Library
from casmi.pool import Pool
from casmi.engine import Engine, EngineCfg

print("loading Library ...", flush=True)
L = Library(WORK)
print("loading Pool ...", flush=True)
P = Pool(WORK)
train_fp = np.load(f"{POOL}/train_fp_sel.npy")
print("train_fp", train_fp.shape, train_fp.dtype, flush=True)

cfg = EngineCfg()
eng = Engine(L, P, train_fp, cfg, bank=None)

# --- load one query ----------------------------------------------------------------------
queries = pd.read_parquet(f"{ROOT}/runs/validation_pilot_v2_20261104/queries.parquet")
print("queries columns:", list(queries.columns), flush=True)
mid = "cross_CBIAKDAYHRWZCU"
q = queries[queries.molecule_id == mid]
print("n spectra for", mid, "=", len(q), flush=True)
row = q.iloc[0]
print("adduct", row.adduct, "ionmode", row.ionization_mode, "prec", row.precursor_mz, flush=True)
print("mz type", type(row.ms2_mzs), "len", len(row.ms2_mzs), flush=True)
