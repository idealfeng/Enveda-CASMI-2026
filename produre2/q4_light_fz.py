"""Q4 lightweight: for the Class-3 queries where generation recovers the truth, can the
recovered truth be ranked into top-25 by the Engine's own fz (fingerprint Bayes) score?
fz is a single 94-feature score, NOT the 160-feature ranker -> a LOWER bound on rankability.
"""
import json
import sys
import time

sys.path.insert(0, "/mnt/d/Paper/casmi/produre2")
import numpy as np

import q345_lib as H
from casmi.engine import COL, EngineCfg


def main():
    eng = H.load_engine(cfg=EngineCfg(generate=True), bank=True)   # generate ON + GPU fpnet (fz)
    queries, truth = H.load_queries_truth()
    truth_id = dict(zip(truth.molecule_id, truth.official_identity))
    mids = list(truth.molecule_id)

    rows = []
    t0 = time.time()
    for i, mid in enumerate(mids, 1):
        spectra, target = H.build_query(queries, mid)
        tid = truth_id[mid]
        sid, pid = H.find_truth_sid_pid(eng, tid)
        # True Class-3 + generate ON
        C, X, info = eng.run(spectra, target, exclude_sid=sid, drop_pid=pid)
        if len(C.pid) == 0:
            rows.append(dict(molecule_id=mid, n_cand=0, truth_present=False,
                             truth_is_gen=False, fz_rank=None, top25=False))
            print(f"[{i}/{len(mids)}] {mid} ncand=0", flush=True)
            continue
        fz = X[:, COL['fz']]
        order = np.argsort(-fz, kind='stable')
        tidx = [j for j, k in enumerate(C.key) if k == tid]
        present = bool(tidx)
        is_gen = bool(present and C.is_gen[tidx[0]] > 0)
        rank = int(np.where(order == tidx[0])[0][0]) + 1 if present else None
        rows.append(dict(molecule_id=mid, n_cand=len(C.pid), n_gen=int(C.is_gen.sum()),
                         truth_present=present, truth_is_gen=is_gen, fz_rank=rank,
                         top25=(rank is not None and rank <= 25)))
        print(f"[{i}/{len(mids)}] {mid} ncand={len(C.pid)} gen={int(C.is_gen.sum())} "
              f"present={present} is_gen={is_gen} fz_rank={rank}", flush=True)

    rec = [r for r in rows if r['truth_is_gen']]
    top25 = [r for r in rec if r['top25']]
    summary = dict(
        step="q4_light_fz",
        scope="Class-3 generate-ON: recovered truth ranked by Engine fz score (lower-bound proxy for 160-feature ranker)",
        queries=len(rows),
        recovered_by_generation=len(rec),
        recovered_top25_fz=len(top25),
        recovered_top25_rate=round(len(top25) / len(rec), 4) if rec else None,
        mrr_fz_class3=round(float(np.mean([1.0 / r['fz_rank'] if r['fz_rank'] else 0.0 for r in rows])), 4),
        mrr_fz_recovered_only=round(float(np.mean([1.0 / r['fz_rank'] for r in rec])), 4) if rec else None,
        elapsed_s=round(time.time() - t0, 1),
        rows=rows,
        note="fz is ONE of 94 engine features, not the 160-feature ranker; rankability lower bound.",
    )
    out = "/mnt/d/Paper/casmi/produre2/artifacts/q4_light_fz.json"
    with open(out, "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(json.dumps({k: summary[k] for k in ("recovered_by_generation", "recovered_top25_fz",
                                               "recovered_top25_rate", "mrr_fz_class3",
                                               "mrr_fz_recovered_only", "elapsed_s")}, indent=2))


if __name__ == "__main__":
    main()
