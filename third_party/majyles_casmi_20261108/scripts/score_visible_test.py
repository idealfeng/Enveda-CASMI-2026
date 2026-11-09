"""Score a submission file on the visible test set, as a smoke test before submitting.

The visible test (400 molecules) is made of copies of training spectra: its answers are found
by matching each test spectrum to its identical training row. The score should be close to 1
for a pipeline whose identity search works; it says nothing about the hidden test.

Usage: python scripts/score_visible_test.py data/submission_local.csv
"""
import hashlib
import sys

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

import casmi


def signature(mzs, intensities) -> str:
    h = hashlib.blake2b(digest_size=16)
    h.update(np.asarray(mzs, np.float64).tobytes())
    h.update(np.asarray(intensities, np.float64).tobytes())
    return h.hexdigest()


if __name__ == "__main__":
    test = pd.read_parquet(casmi.paths.test)
    wanted = {signature(m, i): mol for m, i, mol in
              zip(test["ms2_mzs"], test["ms2_normalized_intensities"], test["molecule_id"])}
    answers: dict[str, set[str]] = {}
    pf = pq.ParquetFile(casmi.paths.train)
    for rg in range(pf.metadata.num_row_groups):
        df = pf.read_row_group(rg, columns=["normalized_smiles", "ms2_mzs", "ms2_normalized_intensities"]).to_pandas()
        for s, m, i in zip(df["normalized_smiles"], df["ms2_mzs"], df["ms2_normalized_intensities"]):
            mol = wanted.get(signature(m, i))
            if mol:
                answers.setdefault(mol, set()).add(casmi.scorer_key(s))
    print(f"answers found for {len(answers)} / {test['molecule_id'].nunique()} molecules")

    sub = pd.read_csv(sys.argv[1]).set_index("molecule_id")["smiles"]
    rr = []
    for mol, keys in answers.items():
        guesses = [casmi.scorer_key(s) for s in str(sub.get(mol, "")).split(";")]
        rr.append(max(casmi.reciprocal_rank(guesses, k) for k in keys))
    print(f"MRR@25 on the visible test: {np.mean(rr):.4f}")
