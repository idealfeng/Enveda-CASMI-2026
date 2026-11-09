"""The candidate pool (training structures ∪ COCONUT) and its precomputed properties.

The pool has one row per metric key, sorted by mass. Arrays computed on it (fingerprints,
natural-product scores, masks) are aligned on its rows.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .chem import morgan_fingerprints, np_likeness_scores
from .paths import paths

# Libraries made of synthetic compounds (drugs, screening libraries) rather than natural products
SYNTHETIC_LIBS = {"enveda-180", "drug_plus"}
NP_THRESHOLD = 0.5


def candidate_pool() -> pd.DataFrame:
    """Proposable structures: training set ∪ normalized COCONUT, one row per metric key.

    Columns: key, smiles (written like the training set, without stereochemistry),
    exact_mass, in_train, in_coconut. Sorted by mass, to find the candidates of a given mass
    quickly.
    """
    path = paths.processed / "candidate_pool.parquet"
    if path.exists():
        return pd.read_parquet(path)
    train = pd.read_parquet(paths.processed / "structures.parquet")
    train = train.rename(columns={"normalized_smiles": "smiles"})[["key", "smiles", "exact_mass"]]
    coco = pd.read_parquet(paths.processed / "coconut_norm_keys.parquet")
    coco = coco.rename(columns={"normalized_smiles": "smiles"})[["key", "smiles", "exact_mass"]]
    pool = pd.concat([train.assign(src="train"), coco.assign(src="coconut")]).dropna(subset=["key"])
    flags = pool.groupby("key")["src"].agg(lambda s: set(s))
    # For the proposed spelling, prefer the training set's when it exists
    pool = pool.sort_values("src", key=lambda s: s.map({"train": 0, "coconut": 1})).drop_duplicates("key")
    pool["in_train"] = pool["key"].map(flags).map(lambda f: "train" in f)
    pool["in_coconut"] = pool["key"].map(flags).map(lambda f: "coconut" in f)
    pool = pool.drop(columns="src").sort_values("exact_mass").reset_index(drop=True)
    pool.to_parquet(path, index=False)
    return pool


def pool_fingerprints(pool: pd.DataFrame, n_jobs: int = 7, chunk: int = 5000) -> np.ndarray:
    """Fingerprints of every pool structure (aligned on its rows), cached on disk."""
    from pebble import ProcessPool

    path = paths.processed / "candidate_pool_fp.npy"
    if path.exists():
        return np.load(path)
    smiles = pool["smiles"].tolist()
    chunks = [smiles[i : i + chunk] for i in range(0, len(smiles), chunk)]
    with ProcessPool(max_workers=n_jobs) as p:
        fps = np.concatenate(list(p.map(morgan_fingerprints, chunks).result()))
    np.save(path, fps)
    return fps


def candidates_in_window(pool_mass: np.ndarray, mass: float, ppm: float = 10.0) -> np.ndarray:
    """Indices (in the mass-sorted pool) of the structures within ±ppm of `mass`."""
    tol = mass * ppm * 1e-6
    lo, hi = np.searchsorted(pool_mass, [mass - tol, mass + tol])
    return np.arange(lo, hi)


def pool_np_scores(pool: pd.DataFrame) -> np.ndarray:
    """NP-likeness of the pool structures **outside COCONUT** (NaN for COCONUT ones, not needed).

    Cached in processed/pool_np_scores.npy.
    """
    path = paths.processed / "pool_np_scores.npy"
    if path.exists():
        return np.load(path)
    scores = np.full(len(pool), np.nan)
    outside = np.flatnonzero(~pool["in_coconut"].to_numpy())
    scores[outside] = np_likeness_scores(pool["smiles"].to_numpy()[outside].tolist())
    np.save(path, scores)
    return scores


def pool_np_likeness(pool: pd.DataFrame) -> pd.Series:
    """NP-likeness score published by COCONUT, per pool row; NaN outside COCONUT.

    Cached in processed/pool_np_likeness.npy, so that the Kaggle run does not need the
    COCONUT files.
    """
    path = paths.processed / "pool_np_likeness.npy"
    if path.exists():
        return pd.Series(np.load(path), index=pool.index)
    coco = pd.read_parquet(paths.processed / "coconut_norm.parquet", columns=["smiles_norm", "np_likeness"])
    keys = pd.read_parquet(paths.processed / "coconut_norm_keys.parquet").set_index("normalized_smiles")["key"]
    coco["key"] = coco["smiles_norm"].map(keys)
    out = coco.groupby("key")["np_likeness"].max().reindex(pool["key"]).set_axis(pool.index)
    np.save(path, out.to_numpy())
    return out


def pool_masks(pool: pd.DataFrame, meta: pd.DataFrame, np_scores: np.ndarray | None = None,
               np_threshold: float = NP_THRESHOLD) -> tuple[np.ndarray, np.ndarray]:
    """(candidate_mask, analog_mask), as selected by validation (notebook 04).

    - candidates: COCONUT structures (the test contains natural products; training
      structures outside COCONUT mostly add same-mass decoys). If `np_scores` is given,
      structures outside COCONUT with NP-likeness >= `np_threshold` are proposable too
      (a safety net for natural products of the training set missing from COCONUT);
    - analogs: every training structure, except those found only in synthetic libraries
      (enveda-180, drug_plus) and not in COCONUT: their spectra point to wrong candidates.

    A structure confirmed by a strong identity match stays proposable even outside the
    candidate mask (see `combine_scores` and `candidate_features`), so class 1 is not lost.
    `meta` must contain `key` and `ingest_lib`.
    """
    libs = meta.groupby("key")["ingest_lib"].agg(set)
    synthetic_only = set(libs[libs.map(lambda s: s <= SYNTHETIC_LIBS)].index)
    candidate_mask = pool["in_coconut"].to_numpy().copy()
    if np_scores is not None:
        candidate_mask |= np.nan_to_num(np_scores, nan=-99.0) >= np_threshold
    analog_mask = (~(pool["key"].isin(synthetic_only) & ~pool["in_coconut"])).to_numpy()
    return candidate_mask, analog_mask
