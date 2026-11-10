"""Step 3+4: bounded Class-3 generation-capability experiment.

For each dev query with a known true structure T (removed from the pool = Class 3),
find pool structures whose mass difference matches a derive template combo, run the
real derive() generator, and check whether T is recovered (official score key).
No hidden test, no GPU, no network; bounded by --max-parents and --max-queries.
"""
import argparse, json, sys, time
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path("/mnt/d/Paper/casmi")
sys.path.insert(0, str(ROOT / "third_party/canqiang_e006/engine_source_v4b/code"))
from casmi import derive, chem  # noqa: E402

DEV = ROOT / "runs/validation_pilot_v2_20261104"
POOL = ROOT / "assets/kaggle/ahmedberatozer/casmi26-v2-pool/v1/train_structs.parquet"
OUT = ROOT / "produre2" / "artifacts"


def load_truth():
    df = pd.read_csv(DEV / "truth.csv", dtype=str, keep_default_na=False)
    rows = []
    for r in df.itertuples(index=False):
        p = chem.mol_props(r.smiles)
        if p is None:
            continue
        rows.append(dict(molecule_id=r.molecule_id, smiles=r.smiles,
                         identity=r.official_identity, mass=p[1]))
    return rows


def load_pool():
    t = pq.read_table(POOL, columns=["smiles", "mass", "key"]).to_pandas()
    return dict(smiles=t.smiles.tolist(), mass=t.mass.to_numpy(np.float64), key=t.key.tolist())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-queries", type=int, default=48)
    ap.add_argument("--max-parents", type=int, default=500)
    ap.add_argument("--query-timeout", type=float, default=20.0)
    ap.add_argument("--tol", type=float, default=0.004)
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    combos = derive._combos(2)                      # ((names), mass_delta)
    combo_deltas = np.sort(np.array([m for _, m in combos], dtype=np.float64))
    truth = load_truth()[: args.max_queries]
    pool = load_pool()
    pool_key = pool["key"]
    pool_mass = pool["mass"]
    pool_smiles = pool["smiles"]
    pool_key_set = set(pool_key)

    combo_hits = Counter()
    per_query = []
    t0 = time.monotonic()
    for item in truth:
        mid = item["molecule_id"]
        M_T = item["mass"]
        tid = item["identity"]
        # Class 3: exclude the true structure's own identity from the parent pool
        keep = np.array([k != tid for k in pool_key])
        delta = M_T - pool_mass
        delta = np.where(keep, delta, np.nan)
        idx = np.searchsorted(combo_deltas, delta)
        idx = np.clip(idx, 0, len(combo_deltas) - 1)
        left = np.clip(idx - 1, 0, len(combo_deltas) - 1)
        near = np.minimum(np.abs(delta - combo_deltas[idx]), np.abs(delta - combo_deltas[left]))
        cand = np.where(np.isfinite(near) & (near <= args.tol))[0]
        if len(cand) > args.max_parents:
            cand = cand[np.argsort(near[cand])[: args.max_parents]]

        recovered = False
        timed_out = False
        hit_templates = set()
        total_gen = valid_gen = novel_gen = 0
        q0 = time.monotonic()
        for ci in cand:
            if time.monotonic() - q0 > args.query_timeout:
                timed_out = True
                break
            parent = pool_smiles[ci]
            d = float(M_T - pool_mass[ci])
            try:
                prods = derive.derive(parent, d, tol=args.tol, max_steps=2, max_per_analog=60,
                                      allow_isomerisation=False)
            except Exception:
                prods = []
            for s in prods:
                total_gen += 1
                std = chem.standardize_smiles(s)
                if std is None:
                    continue
                valid_gen += 1
                k = chem.score_key(std)
                if k is None:
                    continue
                if k not in pool_key_set:
                    novel_gen += 1
                if k == tid:
                    recovered = True
                    for combo_names, cd in combos:
                        if abs(cd - d) <= args.tol:
                            for cn in combo_names:
                                hit_templates.add(cn)

        print(f"  [{per_query.__len__()+1}/{len(truth)}] {mid} recovered={recovered} timeout={timed_out} parents={len(cand)} gen={total_gen}", flush=True)

        per_query.append(dict(molecule_id=mid, identity=tid, mass=round(M_T, 4),
                              parents=len(cand), recovered=recovered, timed_out=timed_out,
                              total_generated=total_gen, valid_generated=valid_gen,
                              novel_generated=novel_gen,
                              hit_templates=";".join(sorted(hit_templates))))
        for cn in hit_templates:
            combo_hits[cn] += 1

    n = len(per_query)
    recovered = sum(1 for r in per_query if r["recovered"])
    total_g = sum(r["total_generated"] for r in per_query)
    valid_g = sum(r["valid_generated"] for r in per_query)
    novel_g = sum(r["novel_generated"] for r in per_query)
    summary = dict(
        step="step3_generation",
        scope="bounded Class-3 derive-only recovery test on dev panel",
        queries=n,
        generation_coverage=(recovered / n) if n else None,
        recovered_queries=recovered,
        timed_out_queries=sum(1 for r in per_query if r["timed_out"]),
        total_generated=total_g, valid_generated=valid_g, novel_generated=novel_g,
        valid_structure_rate=(valid_g / total_g) if total_g else None,
        novel_rate=(novel_g / valid_g) if valid_g else None,
        top_templates=combo_hits.most_common(25),
        parents_cap=args.max_parents, tol=args.tol, elapsed_s=round(time.monotonic() - t0, 1),
        caveats=["Parent = pool structure whose mass delta matches a template combo (bounded proxy for the spectral analog channel).",
                 "derive-only; ranking / Recall / MRR not measured here.",
                 "Class 3 = true identity removed from the parent pool."],
    )
    (OUT / "step3_generation_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    pd.DataFrame(per_query).to_csv(OUT / "step3_per_query.csv", index=False)
    print(json.dumps({k: summary[k] for k in ("generation_coverage", "recovered_queries",
                                              "valid_structure_rate", "novel_rate",
                                              "total_generated", "top_templates", "elapsed_s")},
                     indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

