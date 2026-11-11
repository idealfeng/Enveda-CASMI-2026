"""Q4 FULL ranked: run the REAL 160-feature v4b ranker (fe_v4/V1FE) on Class-3 dev queries
with generate ON, and measure whether recovered truths reach top-25 / MRR.

Read-only diagnostic: uses the v4b inference code (fe_v4) + ranker_v4b.pkl; does NOT touch
the official submission path or any frozen notebook.
"""
import json
import os
import pickle
import sys
import time

ROOT = "/mnt/d/Paper/casmi"
CASMI = f"{ROOT}/third_party/canqiang_e006/engine_source_v4b/code"
FEV4 = f"{ROOT}/assets/kaggle/ahmedberatozer/casmi26-v4b-models/v4/code/fe_v4"
V4MOD = f"{ROOT}/assets/kaggle/ahmedberatozer/casmi26-v4b-models/v4"
PROD = f"{ROOT}/produre2"

sys.path.insert(0, CASMI)
sys.path.insert(0, FEV4)
sys.path.insert(0, PROD)

import numpy as np
import torch
import lightgbm as lgb

import q345_lib as H
from casmi.engine import Engine, EngineCfg, FEATURES
from casmi import fpnet
import v1engine

dev = "cuda" if torch.cuda.is_available() else "cpu"
torch.manual_seed(0)

MAN = json.load(open(f"{V4MOD}/MANIFEST.json", encoding="utf-8"))


def rank_score(X, names, RK_FEATS, RK_B):
    pos = {n: i for i, n in enumerate(names)}
    miss = [f for f in RK_FEATS if f not in pos]
    assert not miss, f"ranker features not produced (would be zero-filled): {miss}"
    Xs = np.ascontiguousarray(X[:, [pos[f] for f in RK_FEATS]], dtype=np.float32)
    return np.mean([b.predict(Xs, num_threads=4) for b in RK_B], axis=0)


def main():
    L, P, tfp = H.load_library_pool()
    bank = fpnet.ModelBank([f"{V4MOD}/fpnet_0.pt"], device=dev)
    E = Engine(L, P, tfp, EngineCfg(generate=True), bank)
    V = v1engine.V1FE(E, [f"{V4MOD}/{m['file']}" for m in MAN["fe_models"]], MAN["families"], device=dev)
    if "derivation" in MAN["families"]:
        try:
            n_bad = V.mods["derivation"].self_test()
            print("derivation self-test mismatches:", n_bad, flush=True)
        except Exception as e:
            print("derivation self-test error (non-fatal):", repr(e), flush=True)
    RK = pickle.load(open(f"{V4MOD}/{MAN['ranker']['file']}", "rb"))
    RK_FEATS = list(RK["features"])
    RK_B = [lgb.Booster(model_str=s) for s in RK["boosters"]]
    print(f"engine ready; ranker features={len(RK_FEATS)} boosters={len(RK_B)}", flush=True)

    queries, truth = H.load_queries_truth()
    truth_id = dict(zip(truth.molecule_id, truth.official_identity))
    mids = list(truth.molecule_id)

    rows = []
    t0 = time.time()
    for i, mid in enumerate(mids, 1):
        spectra, target = H.build_query(queries, mid)
        tid = truth_id[mid]
        sid, pid = H.find_truth_sid_pid(E, tid)
        try:
            C, X, F, names, info = V.run(spectra, target, exclude_sid=sid, drop_pid=pid)
            if len(C.pid):
                score = rank_score(np.concatenate([X, F], 1), list(FEATURES) + list(names), RK_FEATS, RK_B)
                order = np.argsort(-score, kind="stable")
                tidx = [j for j, k in enumerate(C.key) if k == tid]
                present = bool(tidx)
                is_gen = bool(present and C.is_gen[tidx[0]] > 0)
                rank = int(np.where(order == tidx[0])[0][0]) + 1 if present else None
            else:
                present, is_gen, rank = False, False, None
            rows.append(dict(molecule_id=mid, n_cand=len(C.pid), n_gen=int(C.is_gen.sum()),
                             truth_present=present, truth_is_gen=is_gen, rank=rank,
                             top25=(rank is not None and rank <= 25)))
        except Exception as e:
            rows.append(dict(molecule_id=mid, error=repr(e)))
            print(f"[{i}/{len(mids)}] {mid} ERROR {e!r}", flush=True)
            continue
        print(f"[{i}/{len(mids)}] {mid} ncand={len(C.pid)} gen={int(C.is_gen.sum())} "
              f"present={present} is_gen={is_gen} rank={rank}", flush=True)

    ok = [r for r in rows if "error" not in r]
    rec = [r for r in ok if r["truth_is_gen"]]
    top25 = [r for r in rec if r["top25"]]
    mrr = float(np.mean([1.0 / r["rank"] if r["rank"] else 0.0 for r in ok]))
    summary = dict(
        step="q4_full_rank_160feat",
        scope="REAL 160-feature v4b ranker (fe_v4/V1FE) on Class-3 dev queries, generate ON",
        queries=len(mids),
        ok_queries=len(ok),
        error_queries=len(rows) - len(ok),
        recovered_by_generation=len(rec),
        recovered_top25=len(top25),
        recovered_top25_rate=round(len(top25) / len(rec), 4) if rec else None,
        mrr_class3_160feat=round(mrr, 4),
        mrr_recovered_only=round(float(np.mean([1.0 / r["rank"] for r in rec])), 4) if rec else None,
        elapsed_s=round(time.time() - t0, 1),
        rows=rows,
        note="160-feature ranker = casmi 94 features + fe_v4 66 family features; read-only diagnostic.",
    )
    out = f"{PROD}/artifacts/q4_full_rank.json"
    with open(out, "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(json.dumps({k: summary[k] for k in ("ok_queries", "error_queries", "recovered_by_generation",
                                               "recovered_top25", "recovered_top25_rate",
                                               "mrr_class3_160feat", "mrr_recovered_only", "elapsed_s")}, indent=2))


if __name__ == "__main__":
    main()
