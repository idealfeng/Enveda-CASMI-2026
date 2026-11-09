"""Validation design: query draws and the reference spectra allowed in each test class.

The hidden test mixes three classes of molecules: (1) with public reference spectra,
(2) known structures without any public spectrum, (3) structures absent from every database.
Validation simulates classes 1 and 2 by hiding reference spectra of the validation molecules.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .paths import paths


def load_validation() -> tuple[pd.DataFrame, pd.DataFrame]:
    """(val_structures, val_queries) built by notebook 02."""
    return (pd.read_parquet(paths.processed / "val_structures.parquet"),
            pd.read_parquet(paths.processed / "val_queries.parquet"))


def spectra_count_distribution() -> np.ndarray:
    """Number of spectra per molecule in the visible test (1,213 spectra / 400 molecules).

    The hidden test announces 1 to 16 spectra, median 3: validation queries are resampled
    from this distribution so that validation does not get more information than the test.
    """
    test = pd.read_parquet(paths.test, columns=["molecule_id"])
    return test.groupby("molecule_id").size().to_numpy()


def sample_queries(val_rows: pd.DataFrame, counts: np.ndarray, seed: int) -> pd.DataFrame:
    """Draw, for each validation molecule, k spectra among its query spectra.

    k is drawn from the values of `counts` that are feasible for the molecule (k <= available
    spectra). Capping after the draw instead would lower the mean (2.45 instead of ~3).
    Returns the selected rows of `val_rows`.
    """
    rng = np.random.default_rng(seed)
    picked = []
    for _, group in val_rows.groupby("molecule_id", sort=True):
        feasible = counts[counts <= len(group)]
        k = int(rng.choice(feasible)) if len(feasible) else len(group)
        picked.append(group.sample(n=k, random_state=int(rng.integers(1 << 31))))
    return pd.concat(picked)


def reference_mask(meta: pd.DataFrame, val_queries: pd.DataFrame, condition: str) -> np.ndarray:
    """Training rows allowed as references under a simulated condition.

    - "class1": for each validation molecule, hide the spectra of **its query source** (same
      library and instrument family). Its spectra from other sources remain: this is classic
      library search.
    - "class1x": cross-instrument class 1. Also hide every spectrum of the molecule measured on
      the same instrument family as its query (all libraries), as in the test, where a timsTOF
      query only finds references from other instruments. Needs `instrument_family`.
    - "class2" / "class3": hide **all** spectra of the validation molecules. (Class 3 differs
      only by the candidate pool, not by the references.)

    `meta` must contain the `key` and `source` columns, and must be indexed by position.
    """
    assert isinstance(meta.index, pd.RangeIndex) and meta.index.start == 0, "meta must be indexed by position"
    in_val = meta["key"].isin(set(val_queries["key"])).to_numpy()
    if condition in ("class2", "class3"):
        return ~in_val
    if condition == "class1x":
        query_family = val_queries.drop_duplicates("key").set_index("key")["instrument_family"]
        same_family = (meta["instrument_family"] == meta["key"].map(query_family)).to_numpy()
        return ~(in_val & same_family)
    if condition != "class1":
        raise ValueError(condition)
    query_source = val_queries.drop_duplicates("key").set_index("key")["source"]
    same_source = (meta["source"] == meta["key"].map(query_source)).to_numpy()
    return ~(in_val & same_source)
