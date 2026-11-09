"""Local MRR@25, the competition metric, and evaluation helpers."""

from __future__ import annotations

import numpy as np
import pandas as pd

Scores = dict[str, dict[str, float]]  # {molecule_id: {candidate key: score}}


def reciprocal_rank(guess_keys: list[str | None], true_key: str, max_rank: int = 25) -> float:
    """1 / rank of the first correct key among the first `max_rank`, otherwise 0.

    As in the official metric, an invalid guess (key None) still takes up its rank.
    """
    for rank, key in enumerate(guess_keys[:max_rank], 1):
        if key is not None and key == true_key:
            return 1.0 / rank
    return 0.0


def mrr_at_25(predictions: dict[str, list[str | None]], truth: dict[str, str]) -> float:
    """Mean MRR@25 over all molecules of `truth` (a molecule without prediction scores 0).

    predictions: molecule_id -> ordered list of metric keys (already canonicalized)
    truth      : molecule_id -> metric key of the correct answer
    """
    return float(np.mean([reciprocal_rank(predictions.get(m, []), k) for m, k in truth.items()]))


def rank_of_truth(guess_keys: list[str | None], true_key: str) -> int | None:
    """1-based rank of the correct answer in the whole list, None if absent."""
    for rank, key in enumerate(guess_keys, 1):
        if key == true_key:
            return rank
    return None


def rank_candidates(scores: Scores, n: int = 25) -> dict[str, list[str]]:
    """Turn {molecule: {key: score}} into ranked key lists (the n best)."""
    return {m: [k for k, _ in sorted(s.items(), key=lambda kv: -kv[1])[:n]] for m, s in scores.items()}


def evaluate(scores: Scores, val_structures: pd.DataFrame) -> pd.DataFrame:
    """Per-molecule table: rank of the correct answer (whole list) and reciprocal rank @25."""
    full = rank_candidates(scores, n=10**9)
    out = val_structures[["molecule_id", "key", "subset"]].copy()
    out["rank"] = [rank_of_truth(full.get(m, []), k) for m, k in zip(out["molecule_id"], out["key"])]
    out["rr"] = [1.0 / r if r is not None and r <= 25 else 0.0 for r in out["rank"]]
    out["n_candidates"] = [len(full.get(m, [])) for m in out["molecule_id"]]
    return out


def random_mrr(n_candidates: np.ndarray, truth_present: np.ndarray) -> float:
    """Expected MRR@25 of a random ranking among n candidates (0 if the answer is absent)."""
    harmonic = np.concatenate([[0], np.cumsum(1 / np.arange(1, 26))])
    n = np.maximum(np.asarray(n_candidates), 1)
    return float(np.mean(np.where(truth_present, harmonic[np.minimum(n, 25)] / n, 0.0)))
