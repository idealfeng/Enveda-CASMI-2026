"""Data locations, gathered in one mutable object so that a run can redirect them.

Locally, everything lives under `data/` at the repository root. On Kaggle, the inference
script points `paths.train`, `paths.test` and `paths.processed` to the mounted inputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Paths:
    data: Path = ROOT / "data"
    processed: Path = ROOT / "data" / "processed"
    train: Path = ROOT / "data" / "train.parquet"
    test: Path = ROOT / "data" / "test.parquet"
    coconut_zip: Path = ROOT / "data" / "raw" / "coconut_csv_lite-09-2026.zip"


paths = Paths()


def cached(name: str, compute):
    """Result of `compute()`, pickled under `processed/cache/<name>.pkl` on first call."""
    import pickle

    path = paths.processed / "cache" / f"{name}.pkl"
    if path.exists():
        with open(path, "rb") as f:
            return pickle.load(f)
    result = compute()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(result, f)
    return result
