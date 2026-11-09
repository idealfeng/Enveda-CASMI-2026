"""Step 1 — structure tables and the candidate pool.

- metric key, formula and mass of every training SMILES (processed/structures.parquet);
- COCONUT normalized like the training set, and the keys of its distinct SMILES
  (processed/coconut_norm.parquet, coconut_norm_keys.parquet);
- the candidate pool (training set ∪ COCONUT), its fingerprints and NP-likeness arrays.

Every output is cached: rerunning skips what exists. Needs data/train.parquet and the COCONUT
CSV export in data/raw/. About 3 h on 8 cores, mostly tautomer canonicalization.
"""
import time

import pandas as pd

import casmi

if __name__ == "__main__":
    t = time.time()
    meta = casmi.load_train_meta(["normalized_smiles"])
    structures = casmi.structure_table(meta)
    print(f"training structures: {len(structures):,} - {time.time() - t:.0f} s", flush=True)

    coconut = casmi.load_coconut()
    coconut = coconut[coconut["exact_molecular_weight"].between(140, 1250)].copy()
    path = casmi.paths.processed / "coconut_norm.parquet"
    if path.exists():
        coconut = pd.read_parquet(path)
    else:
        coconut["smiles_norm"] = casmi.normalize_many(coconut["canonical_smiles"].tolist())
        coconut.to_parquet(path, index=False)
    keys = casmi.key_table(coconut["smiles_norm"], "coconut_norm_keys")
    print(f"COCONUT: {len(coconut):,} entries, {keys['key'].nunique():,} distinct keys, "
          f"{(~keys['key_exact']).sum()} approximate - {time.time() - t:.0f} s", flush=True)

    pool = casmi.candidate_pool()
    casmi.pool_fingerprints(pool)
    casmi.pool_np_scores(pool)
    casmi.pool_np_likeness(pool)
    print(f"candidate pool: {len(pool):,} structures - {time.time() - t:.0f} s", flush=True)
