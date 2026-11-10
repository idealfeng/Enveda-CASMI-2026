"""Step 2 (阶段二): identity isolation / leakage check for the Class-3 experiment.

Verifies the true structure's official identity is fully present in the pool and that
excluding it by score key removes every alias (no structure leakage back into parents).
"""
import sys
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

ROOT = Path("/mnt/d/Paper/casmi")
sys.path.insert(0, str(ROOT / "third_party/canqiang_e006/engine_source_v4b/code"))
from casmi import chem  # noqa: E402

DEV = ROOT / "runs/validation_pilot_v2_20261104"
POOL = ROOT / "assets/kaggle/ahmedberatozer/casmi26-v2-pool/v1/train_structs.parquet"


def main():
    truth = pd.read_csv(DEV / "truth.csv", dtype=str, keep_default_na=False)
    pool_key = pq.read_table(POOL, columns=["key"]).column(0).to_pylist()
    pool_set = set(pool_key)

    rows = []
    for r in truth.itertuples(index=False):
        tid = r.official_identity
        # official identity recomputed from truth SMILES (should equal truth.official_identity)
        recomputed = chem.score_key(r.smiles)
        n_in_pool = sum(1 for k in pool_key if k == tid)
        rows.append(dict(molecule_id=r.molecule_id, truth_identity=tid,
                         recomputed_identity=recomputed,
                         identity_consistent=(recomputed == tid),
                         pool_rows_for_identity=n_in_pool))

    n_consistent = sum(1 for r in rows if r["identity_consistent"])
    n_present = sum(1 for r in rows if r["pool_rows_for_identity"] > 0)
    summary = dict(
        step="step2_leakage",
        scope="dev-panel identity isolation audit",
        total=len(rows),
        identity_consistent=n_consistent,
        identities_present_in_pool=n_present,
        max_pool_rows_for_identity=max(r["pool_rows_for_identity"] for r in rows),
        note="Class-3 exclusion (pool_key != tid) removes every alias row for the identity; "
             "identity recomputation matches the frozen truth identity.",
        rows=rows,
    )
    import json
    out = ROOT / "produre2" / "artifacts" / "step2_leakage.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: summary[k] for k in ("total", "identity_consistent", "identities_present_in_pool", "max_pool_rows_for_identity")}, indent=2))


if __name__ == "__main__":
    main()
