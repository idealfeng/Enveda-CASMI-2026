"""Small-scale Q4 upper-bound: does adding recovered generated structures improve MRR?

Base = Flex48 V0 ranking (baseline_submission.csv). For queries where derive recovered
the true structure, promote the true structure to rank-1 (best case) and measure the
MRR delta. This is an UPPER BOUND on the ranked gain; the real ranker may place the
generated candidate anywhere, not necessarily rank-1.
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path("/mnt/d/Paper/casmi")
sys.path.insert(0, str(ROOT))
from validation.metric import assert_official_rdkit, identity  # noqa: E402

RUN = ROOT / "runs/validation_flex_c2_20261105d"
DEV = ROOT / "runs/validation_pilot_v2_20261104"
Q5 = ROOT / "produre2/artifacts/q5_real_paths.json"


def mrr(ranked, tid):
    keys = [identity(s) for s in ranked]
    rank = next((i for i, k in enumerate(keys, 1) if k == tid), None)
    return (1.0 / rank if rank else 0.0), rank


def main():
    assert_official_rdkit()
    base = pd.read_csv(RUN / "baseline_submission.csv", dtype=str, keep_default_na=False)
    truth = pd.read_csv(DEV / "truth.csv", dtype=str, keep_default_na=False)
    import json
    gen = json.loads(Q5.read_text())
    recovered = {r["molecule_id"] for r in gen["per_query"] if r["recovered"]}

    base_list = {str(m): s.split(";") for m, s in zip(base.molecule_id, base.smiles)}
    truth_smi = dict(zip(truth.molecule_id, truth.smiles))
    truth_id = dict(zip(truth.molecule_id, truth.official_identity))

    base_scores, gen_scores = [], []
    rows = []
    for mid, bl in base_list.items():
        tid = truth_id[mid]
        b_mrr, b_rank = mrr(bl, tid)
        g_mrr = b_mrr
        promoted = False
        # 用官方身份判断，而不是 raw SMILES 字符串；避免把"已存在但写法不同"误判为新增。
        base_ids = {identity(s) for s in bl}
        if mid in recovered and tid not in base_ids:
            new = ([truth_smi[mid]] + bl)[:25]
            g_mrr, g_rank = mrr(new, tid)
            promoted = True
        base_scores.append(b_mrr)
        gen_scores.append(g_mrr)
        rows.append(dict(molecule_id=mid, base_rank=b_rank, recovered=(mid in recovered),
                         promoted=promoted, base_mrr=round(b_mrr, 4), gen_mrr=round(g_mrr, 4)))

    base_mean = sum(base_scores) / len(base_scores)
    gen_mean = sum(gen_scores) / len(gen_scores)
    summary = dict(
        step="q4_smallscale_upper_bound",
        scope="Flex48 V0 base + derive recovery promoted to rank-1 (best case)",
        molecules=len(base_scores),
        recovered_queries=len(recovered),
        promoted_queries=sum(1 for r in rows if r["promoted"]),
        base_mrr=round(base_mean, 4),
        gen_mrr_upper_bound=round(gen_mean, 4),
        mrr_delta=round(gen_mean - base_mean, 4),
        note="UPPER BOUND: assumes every recovered structure is promoted to rank-1. "
             "The real LightGBM ranker would place generated candidates by score, not necessarily rank-1.",
        rows=rows,
    )
    import json
    out = ROOT / "produre2/artifacts/q4_smallscale.json"
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: summary[k] for k in ("base_mrr", "gen_mrr_upper_bound", "mrr_delta",
                                              "recovered_queries", "promoted_queries")}, indent=2))


if __name__ == "__main__":
    main()
