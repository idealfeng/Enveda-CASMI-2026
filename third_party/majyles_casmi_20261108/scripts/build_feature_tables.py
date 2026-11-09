"""Step 5 — feature tables of the ranker, from the cached searches of steps 3 and 4.

One table per (query set, condition): processed/cache/features_v2_<name>.pkl, one row per
(molecule, candidate). Training: class1x_rank and class2_rank; validation: class1_s{0,1} and
class2_s{0,1}.

`has_visible_spectra` is computed on the references **allowed** under the simulated
condition, never on the full training set (see `casmi.candidate_features`).
"""
import time

import pandas as pd

import casmi


def feature_table(name: str, structures: pd.DataFrame, queries: pd.DataFrame, draw: pd.DataFrame,
                  cond: str) -> pd.DataFrame:
    def compute():
        allowed = casmi.reference_mask(meta, queries, cond)
        truth = structures.set_index("molecule_id")["key"].to_dict()
        return casmi.candidate_features(
            casmi.cached(f"hits_identity_{name}", None), casmi.cached(f"hits_hybrid_{name}", None),
            draw, pool, fps, set(meta.loc[allowed, "key"]), np_like, truth=truth,
            candidate_mask=candidate_mask, analog_mask=analog_mask)
    return casmi.cached(f"features_v2_{name}", compute)


if __name__ == "__main__":
    t = time.time()
    meta = casmi.load_reference_meta()
    pool = casmi.candidate_pool()
    fps = casmi.pool_fingerprints(pool)
    np_like = casmi.pool_np_likeness(pool)
    candidate_mask, analog_mask = casmi.pool_masks(pool, meta, np_scores=casmi.pool_np_scores(pool))

    rank_structures = pd.read_parquet(casmi.paths.processed / "rank_structures.parquet")
    rank_queries = pd.read_parquet(casmi.paths.processed / "rank_queries.parquet")
    rank_draw = pd.read_parquet(casmi.paths.processed / "rank_draw.parquet")
    for cond in ["class1x", "class2"]:
        table = feature_table(f"{cond}_rank", rank_structures, rank_queries, rank_draw, cond)
        print(f"{cond}_rank: {len(table):,} rows - {time.time() - t:.0f} s", flush=True)

    val_structures, val_queries = casmi.load_validation()
    counts = casmi.spectra_count_distribution()
    for seed in [0, 1]:
        draw = casmi.sample_queries(val_queries, counts, seed)
        for cond in ["class1", "class2"]:
            table = feature_table(f"{cond}_s{seed}", val_structures, val_queries, draw, cond)
            print(f"{cond}_s{seed}: {len(table):,} rows - {time.time() - t:.0f} s", flush=True)
