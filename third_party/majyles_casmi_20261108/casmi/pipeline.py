"""End-to-end prediction for a set of query spectra, and the submission file."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .data import molecule_masses
from .metric import Scores, rank_candidates
from .ranking import (DERIVED_FEATURES, FEATURES, add_derived_features, analog_propagation,
                      candidate_features, combine_scores, fill_slots, scores_from_table)
from .spectra import SpectralIndex, aggregate_hits, spectrum_hits


def _searches(index, library, row_keys, queries, allowed, query_library):
    """Identity search (same neutral mass) and hybrid search (analogs, any mass)."""
    kw = dict(query_library=query_library)
    identity = spectrum_hits(index, library, row_keys, queries, allowed, **kw)
    hybrid = spectrum_hits(index, library, row_keys, queries, allowed, method="hybrid", top_hits=100, **kw)
    return identity, hybrid


def predict(index: SpectralIndex, library: dict, row_keys: np.ndarray, queries: pd.DataFrame,
            allowed: np.ndarray, pool: pd.DataFrame, fps: np.ndarray,
            query_library: dict | None = None, excluded: dict | None = None,
            power: float = 16.0, threshold: float = 0.9,
            candidate_mask: np.ndarray | None = None, analog_mask: np.ndarray | None = None) -> Scores:
    """Hand-tuned pipeline (submission v2): gated identity + analog propagation."""
    identity, hybrid = _searches(index, library, row_keys, queries, allowed, query_library)
    masses = molecule_masses(queries)
    analogs = analog_propagation(hybrid, masses, pool, fps, power=power, excluded=excluded,
                                 candidate_mask=candidate_mask, analog_mask=analog_mask)
    main = combine_scores(aggregate_hits(identity, "max"), analogs, threshold=threshold)
    if candidate_mask is None:
        return main
    # Free slots (fewer than 25 proposable candidates) are filled with the best candidates of
    # the full pool: they may recover a correct answer outside the main pool.
    full = analog_propagation(hybrid, masses, pool, fps, power=power, excluded=excluded, analog_mask=analog_mask)
    return fill_slots(main, full)


def predict_ranker(index: SpectralIndex, library: dict, row_keys: np.ndarray, queries: pd.DataFrame,
                   allowed: np.ndarray, pool: pd.DataFrame, fps: np.ndarray, booster,
                   candidate_mask: np.ndarray, analog_mask: np.ndarray, visible_keys: set,
                   np_like: pd.Series, query_library: dict | None = None,
                   identity_guard: float = 0.97) -> Scores:
    """Pipeline with the LightGBM ranker (submission v3): same searches as `predict`, then
    candidates are ranked by the model from their features. Free slots are filled as in
    `predict`.
    """
    identity, hybrid = _searches(index, library, row_keys, queries, allowed, query_library)
    table = candidate_features(identity, hybrid, queries, pool, fps, visible_keys, np_like,
                               candidate_mask=candidate_mask, analog_mask=analog_mask)
    table = add_derived_features(table)
    table["score"] = booster.predict(table[FEATURES + DERIVED_FEATURES])
    # Guard: a near-perfect identity match always goes first (the ranker, trained on natural
    # products, wrongly distrusts candidates outside COCONUT even when they match perfectly).
    table["score"] = table.groupby("molecule_id")["score"].rank(pct=True) + np.where(
        table["id_max"] >= identity_guard, 10 * table["id_max"], 0.0)
    main = scores_from_table(table, "score")
    full = analog_propagation(hybrid, molecule_masses(queries), pool, fps, power=16, analog_mask=analog_mask)
    return fill_slots(main, full)


def write_submission(scores: Scores, pool: pd.DataFrame, molecule_ids, path: str | Path,
                     fallback: str = "C") -> pd.DataFrame:
    """Write submission.csv: 25 SMILES (distinct keys) per molecule, best first.

    The proposed SMILES are the pool's (written like the training set, without
    stereochemistry). A molecule without candidates gets `fallback` (a row must never be empty).
    """
    key_to_smiles = pool.set_index("key")["smiles"]
    ranked = rank_candidates(scores, n=25)
    rows = []
    for mol in molecule_ids:
        smiles = [key_to_smiles[k] for k in ranked.get(mol, []) if k in key_to_smiles.index][:25]
        rows.append((mol, ";".join(smiles) if smiles else fallback))
    sub = pd.DataFrame(rows, columns=["molecule_id", "smiles"])
    sub.to_csv(path, index=False)
    return sub
