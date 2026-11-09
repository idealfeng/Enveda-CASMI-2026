"""Chemistry with RDKit: the scorer's identity key, SMILES normalization, fingerprints.

RDKit is imported lazily, inside the functions, so that worker processes and light uses of
the package (metric, spectra) do not pay for it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .paths import paths

_enumerator = None


def _rdkit():
    """Initialize RDKit once per process (each worker has its own)."""
    global _enumerator
    from rdkit import Chem, RDLogger
    from rdkit.Chem.MolStandardize import rdMolStandardize

    if _enumerator is None:
        RDLogger.DisableLog("rdApp.*")
        _enumerator = rdMolStandardize.TautomerEnumerator()
    return Chem, _enumerator


# --------------------------------------------------------------------------------------------
# Identity key of the metric (same as the official casmi-mean-reciprocal-rank notebook)
# --------------------------------------------------------------------------------------------
def scorer_key(smiles: str) -> str | None:
    """InChIKey14 after tautomer canonicalization: exactly what the metric compares."""
    Chem, enumerator = _rdkit()
    if not isinstance(smiles, str):
        return None
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return None
        return Chem.MolToInchiKey(enumerator.Canonicalize(mol))[:14]
    except (ValueError, RuntimeError, TypeError):
        return None


def normalize_smiles(smiles: str) -> str | None:
    """Write a SMILES like the `normalized_smiles` of the training set.

    RDKit cleanup, largest fragment, charge neutralization when possible, **no
    stereochemistry**, canonical SMILES. This chain leaves 100 % of the training SMILES
    unchanged (checked on 20,000), so it is very likely the organizers' own. It matters
    because the metric key can change depending on whether stereochemistry is written.
    """
    Chem, _ = _rdkit()
    from rdkit.Chem.MolStandardize import rdMolStandardize

    try:
        mol = Chem.MolFromSmiles(smiles) if isinstance(smiles, str) else None
        if mol is None:
            return None
        mol = rdMolStandardize.Cleanup(mol)
        # Remove counter-ions first, then neutralize: while the counter-ion is present the salt
        # is globally neutral and nothing gets neutralized (sodium acetate would stay a
        # charged acetate instead of becoming acetic acid).
        mol = rdMolStandardize.Uncharger().uncharge(rdMolStandardize.FragmentParent(mol))
        Chem.RemoveStereochemistry(mol)
        return Chem.MolToSmiles(mol)
    except (ValueError, RuntimeError, TypeError):
        return None


def _normalize_chunk(smiles: list[str]) -> list[str | None]:
    return [normalize_smiles(s) for s in smiles]


def normalize_many(smiles: list[str], n_jobs: int = 7, chunk: int = 2000) -> list[str | None]:
    """`normalize_smiles` in parallel."""
    from pebble import ProcessPool

    smiles = list(smiles)
    chunks = [smiles[i : i + chunk] for i in range(0, len(smiles), chunk)]
    with ProcessPool(max_workers=n_jobs) as pool:
        results = pool.map(_normalize_chunk, chunks).result()
        return [s for part in results for s in part]


# --------------------------------------------------------------------------------------------
# Structure tables: key, formula and mass of many SMILES
# --------------------------------------------------------------------------------------------
def _structure_info(smiles: str) -> tuple:
    """(metric key, formula, monoisotopic mass) of a SMILES."""
    Chem, _ = _rdkit()
    from rdkit.Chem import Descriptors, rdMolDescriptors

    key = scorer_key(smiles)
    mol = Chem.MolFromSmiles(smiles) if isinstance(smiles, str) else None
    if mol is None:
        return key, None, np.nan
    return key, rdMolDescriptors.CalcMolFormula(mol), Descriptors.ExactMolWt(mol)


def _chunk_info(smiles: list[str]) -> list[tuple]:
    return [_structure_info(s) for s in smiles]


def _fallback_info(smiles: str) -> tuple:
    """Like `_structure_info`, without tautomer canonicalization (approximate key)."""
    Chem, _ = _rdkit()
    from rdkit.Chem import Descriptors, rdMolDescriptors

    mol = Chem.MolFromSmiles(smiles) if isinstance(smiles, str) else None
    if mol is None:
        return None, None, np.nan
    return Chem.MolToInchiKey(mol)[:14], rdMolDescriptors.CalcMolFormula(mol), Descriptors.ExactMolWt(mol)


def compute_structure_table(smiles: list[str], n_jobs: int = 7, chunk: int = 50,
                            chunk_timeout: float = 60, mol_timeout: float = 10) -> pd.DataFrame:
    """Metric key, formula and mass of each SMILES, in parallel.

    A few pathological molecules have thousands of tautomers and can block a core for tens
    of minutes. Work is therefore split into small chunks with a time limit: a chunk that is
    too slow is retried molecule by molecule (limit `mol_timeout`), and a molecule that still
    times out gets its InChIKey14 **without** tautomer canonicalization, flagged by
    `key_exact = False`.
    """
    from concurrent.futures import TimeoutError as FuturesTimeout

    from pebble import ProcessPool

    smiles = list(smiles)
    chunks = [smiles[i : i + chunk] for i in range(0, len(smiles), chunk)]
    rows: list[tuple | None] = [None] * len(smiles)
    exact = [True] * len(smiles)
    retry: list[int] = []
    with ProcessPool(max_workers=n_jobs) as pool:
        futures = [pool.schedule(_chunk_info, args=(c,), timeout=chunk_timeout) for c in chunks]
        for ci, future in enumerate(futures):
            try:
                for j, info in enumerate(future.result()):
                    rows[ci * chunk + j] = info
            except FuturesTimeout:
                retry.extend(range(ci * chunk, ci * chunk + len(chunks[ci])))
        singles = {i: pool.schedule(_structure_info, args=(smiles[i],), timeout=mol_timeout) for i in retry}
        for i, future in singles.items():
            try:
                rows[i] = future.result()
            except FuturesTimeout:
                rows[i] = _fallback_info(smiles[i])
                exact[i] = False
    out = pd.DataFrame(rows, columns=["key", "formula", "exact_mass"])
    out.insert(0, "normalized_smiles", smiles)
    out["key_exact"] = exact
    return out


def key_table(smiles_list, name: str, n_jobs: int = 7, batch_size: int = 5000) -> pd.DataFrame:
    """Metric key, formula and mass of a list of SMILES, cached under `name`.

    Tautomer canonicalization costs ~10 ms for an ordinary molecule but can take minutes for
    a very large one. SMILES are therefore processed from shortest to longest, in batches
    saved as they complete (the run can resume after an interruption).
    """
    import time

    path = paths.processed / f"{name}.parquet"
    if path.exists():
        return pd.read_parquet(path)
    parts_dir = paths.processed / f"{name}_parts"
    parts_dir.mkdir(parents=True, exist_ok=True)

    smiles = pd.Series(pd.unique(pd.Series(smiles_list).dropna()))
    smiles = smiles.iloc[np.argsort(smiles.str.len().to_numpy(), kind="stable")].tolist()
    batches = [smiles[i : i + batch_size] for i in range(0, len(smiles), batch_size)]

    start = time.time()
    for i, batch in enumerate(batches):
        part = parts_dir / f"part_{i:04d}.parquet"
        if not part.exists():
            compute_structure_table(batch, n_jobs=n_jobs).to_parquet(part, index=False)
        print(f"batch {i + 1}/{len(batches)} (SMILES up to {len(batch[-1])} characters) "
              f"- {time.time() - start:.0f} s", flush=True)

    table = pd.concat([pd.read_parquet(p) for p in sorted(parts_dir.glob("part_*.parquet"))],
                      ignore_index=True)
    # Batches computed before the time limit was introduced lack the column: their keys are exact
    table["key_exact"] = table.get("key_exact", pd.Series(True, index=table.index)).fillna(True).astype(bool)
    table.to_parquet(path, index=False)
    return table


def structure_table(meta: pd.DataFrame, n_jobs: int = 7, batch_size: int = 5000) -> pd.DataFrame:
    """Structure table of the training set (one row per SMILES), cached on disk."""
    return key_table(meta["normalized_smiles"].unique(), "structures", n_jobs, batch_size)


# --------------------------------------------------------------------------------------------
# Fingerprints and Tanimoto similarity
# --------------------------------------------------------------------------------------------
FP_BITS = 2048


def morgan_fingerprints(smiles: list[str]) -> np.ndarray:
    """Morgan fingerprints (radius 2, 2048 bits), packed into bytes: shape (n, 256).

    An unparsable SMILES gets an all-zero fingerprint.
    """
    Chem, _ = _rdkit()
    from rdkit.Chem import rdFingerprintGenerator

    gen = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=FP_BITS)
    out = np.zeros((len(smiles), FP_BITS // 8), dtype=np.uint8)
    for i, s in enumerate(smiles):
        mol = Chem.MolFromSmiles(s) if isinstance(s, str) else None
        if mol is not None:
            out[i] = np.packbits(gen.GetFingerprintAsNumPy(mol).astype(bool))
    return out


def tanimoto(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Tanimoto similarity between two sets of packed fingerprints: matrix (len(a), len(b)).

    Tanimoto = shared bits / bits set in either (1 = same substructures).
    """
    ua = np.unpackbits(a, axis=1).astype(np.float32)
    ub = np.unpackbits(b, axis=1).astype(np.float32)
    inter = ua @ ub.T
    na, nb = ua.sum(1)[:, None], ub.sum(1)[None, :]
    return inter / np.maximum(na + nb - inter, 1)


def np_likeness_scores(smiles: list[str]) -> np.ndarray:
    """Natural-product likeness (Ertl et al., 2008) from RDKit Contrib; NaN if unparsable."""
    import os
    import sys

    Chem, _ = _rdkit()
    from rdkit import RDConfig

    sys.path.append(os.path.join(RDConfig.RDContribDir, "NP_Score"))
    import npscorer

    model = npscorer.readNPModel()
    scores = np.full(len(smiles), np.nan)
    for i, s in enumerate(smiles):
        mol = Chem.MolFromSmiles(s) if isinstance(s, str) else None
        if mol is not None:
            scores[i] = npscorer.scoreMol(mol, model)
    return scores
