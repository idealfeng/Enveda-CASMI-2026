"""Step 3 — library searches of the validation set, cached.

Needs the validation set built by notebook 02 (processed/val_structures.parquet and
val_queries.parquet). For query draws 0 and 1 and conditions class 1 and class 2, runs the
identity and hybrid searches and caches them (processed/cache/hits_*). Tuning how the scores
are combined then takes seconds instead of hours. About 75 min.
"""
import time

import casmi

if __name__ == "__main__":
    meta = casmi.load_reference_meta()
    library = casmi.build_clean_library()
    index = casmi.SpectralIndex(library, meta)
    _, val_queries = casmi.load_validation()
    counts = casmi.spectra_count_distribution()
    keys = meta["key"].to_numpy()
    for seed in [0, 1]:
        draw = casmi.sample_queries(val_queries, counts, seed)
        for cond in ["class1", "class2"]:
            allowed = casmi.reference_mask(meta, val_queries, cond)
            for method, top in [("identity", 50), ("hybrid", 100)]:
                t = time.time()
                casmi.cached(f"hits_{method}_{cond}_s{seed}",
                             lambda: casmi.spectrum_hits(index, library, keys, draw, allowed, method=method, top_hits=top))
                print(f"draw {seed} {cond} {method}: {time.time() - t:.0f} s", flush=True)
