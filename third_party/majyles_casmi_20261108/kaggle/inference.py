"""CASMI 2026 submission: library search + analog propagation + LightGBM ranker.

Runs on Kaggle (no internet) with the `casmi26-assets` dataset attached, or locally (same
functions, files from data/). Steps:
  1. install RDKit 2026.03.3, ms_entropy, pebble and the casmi package from the dataset's wheels;
  2. clean the 2.5 M training spectra and build the FlashEntropy index (~15 min);
  3. for each test molecule: candidates of the same neutral mass (training set ∪ COCONUT),
     scored by identity and analog searches, ranked by the LightGBM model;
  4. write submission.csv (25 SMILES per molecule, written like the training normalized_smiles).
"""
import glob
import subprocess
import sys
import time
from pathlib import Path

T0 = time.time()
KAGGLE = Path("/kaggle/input").exists()


def log(msg: str) -> None:
    print(f"[{time.time() - T0:6.0f} s] {msg}", flush=True)


def find(name: str) -> Path:
    hits = sorted(glob.glob(f"/kaggle/input/**/{name}", recursive=True))
    if not hits:
        raise FileNotFoundError(f"{name} not found under /kaggle/input")
    return Path(hits[0])


if KAGGLE:
    ASSETS = find("candidate_pool.parquet").parent
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "--no-index", "--no-deps",
                    f"--find-links={ASSETS}",
                    "rdkit==2026.3.3", "ms_entropy==1.5.2", "pebble==5.2.2", "casmi"], check=True)
# Locally, casmi is installed as the project package (uv sync).

import lightgbm as lgb  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import casmi  # noqa: E402

ASSET_FILES = ["candidate_pool.parquet", "candidate_pool_fp.npy", "structures.parquet", "pool_np_scores.npy",
               "pool_np_likeness.npy", "ranker_final.txt"]

if KAGGLE:
    work = Path("/tmp/processed")  # outside the output folder: no need to publish 475 MB
    work.mkdir(parents=True, exist_ok=True)
    for f in ASSET_FILES:
        if not (ASSETS / f).exists():
            raise FileNotFoundError(f"{f} missing from the mounted dataset ({ASSETS}): outdated dataset version?")
        if not (work / f).exists():
            (work / f).symlink_to(ASSETS / f)
    casmi.paths.processed = work
    casmi.paths.train = find("train.parquet")
    casmi.paths.test = find("test.parquet")
    OUT = Path("/kaggle/working/submission.csv")
    INDEX_CACHE = None  # no need to write the index on Kaggle
else:
    OUT = casmi.paths.data / "submission_local.csv"
    INDEX_CACHE = "index_full"

log(f"RDKit {__import__('rdkit').__version__} | train {casmi.paths.train} | test {casmi.paths.test}")

# Training metadata and the metric key of each spectrum
meta = casmi.load_train_meta(["normalized_smiles", "ionization_mode", "ingest_lib"])
structures = pd.read_parquet(casmi.paths.processed / "structures.parquet").set_index("normalized_smiles")
meta["key"] = meta["normalized_smiles"].map(structures["key"])
meta["exact_mass"] = meta["normalized_smiles"].map(structures["exact_mass"])
log(f"metadata: {len(meta):,} spectra")

library = casmi.build_clean_library()
log(f"cleaned library: {len(library['mz']):,} peaks")
index = casmi.SpectralIndex(library, meta, cache_name=INDEX_CACHE)
log("index ready")

pool = casmi.candidate_pool()
fps = casmi.pool_fingerprints(pool)
candidate_mask, analog_mask = casmi.pool_masks(pool, meta, np_scores=casmi.pool_np_scores(pool))
log(f"pool: {len(pool):,} structures | proposable candidates: {candidate_mask.sum():,} "
    f"| allowed analogs: {analog_mask.sum():,}")

test = pd.read_parquet(casmi.paths.test).reset_index(drop=True)
test["row"] = np.arange(len(test))
query_library = casmi.clean_query_spectra(test)
log(f"test: {len(test):,} spectra, {test['molecule_id'].nunique():,} molecules")

allowed = np.ones(len(meta), dtype=bool)  # on the test, the whole library is allowed
booster = lgb.Booster(model_file=str(casmi.paths.processed / "ranker_final.txt"))
scores = casmi.predict_ranker(index, library, meta["key"].to_numpy(), test, allowed, pool, fps, booster,
                              candidate_mask, analog_mask, visible_keys=set(meta["key"].dropna()),
                              np_like=casmi.pool_np_likeness(pool), query_library=query_library)
log("predictions done")

sub = casmi.write_submission(scores, pool, test["molecule_id"].unique(), OUT)
n_guesses = sub["smiles"].str.count(";") + 1
log(f"{OUT}: {len(sub)} molecules, {n_guesses.mean():.1f} guesses on average, "
    f"{(sub['smiles'] == 'C').sum()} without candidates")
