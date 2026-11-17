# ===== heliosli M5 part B (after the FRIGID merge): the methane probe's self-check, write-back checks, audit (reports/c3_design_v0.md 11-07 18:07 as amended) =====
# Self-contained (no package import), so it runs even when part A could not open the package.
#   m5d1    : m5_status.json from part A -> exception / missing / unfinished -> the whole submission becomes methane;
#             finished with >= M5_MIN_SELECTED selected lists among the processed ones -> those lists' rank 1 -> methane
#             (in place, only where rank 1 is still the one part A judged; the merge never changes rank 1); otherwise
#             the whole submission becomes methane. Methane goes in here, after the merge, so the merge can neither insert
#             a FRIGID candidate into an all-methane submission nor put back a removed rank 1 at rank 2.
#   swap / reorder : nothing changes here; rt/rulerprobe_body.py's write-back checks run on the final file and the
#             audit records where part A's changes ended up after the merge.
M5_MODE_B = "swap"
M5_MIN_SELECTED = 8
M5_DECOY = "C"


def _m5_b(work="/kaggle/working"):
    import json
    import os
    import time

    import pandas as pd

    t0 = time.monotonic()
    sub_path = os.path.join(work, "submission.csv")
    sub = pd.read_csv(sub_path, dtype=str, keep_default_na=False)
    mids = sub["molecule_id"].astype(str).tolist()
    cur = [str(x) for x in sub["smiles"]]

    def load(name):
        p = os.path.join(work, name)
        try:
            return json.load(open(p)) if os.path.exists(p) else None
        except Exception:
            return None
    status, decisions = load("m5_status.json"), load("m5_decisions.json")
    audit = dict(mode=M5_MODE_B, status_found=status is not None, decisions_found=decisions is not None, action="none")

    def check(smiles):
        parts = [s.split(";") for s in smiles]
        assert len(smiles) == len(mids)
        if "SAMPLE_IDS" in globals():
            assert mids == list(globals()["SAMPLE_IDS"])
        assert max((len(p) for p in parts), default=0) <= 25
        assert all(len(set(p)) == len(p) for p in parts)
        assert all(all(t.strip() for t in p) for p in parts)

    def write(smiles):
        check(smiles)
        res = sub.copy()
        res["smiles"] = smiles
        assert list(res["molecule_id"].astype(str)) == mids
        res.to_csv(os.path.join(work, "submission.m5b.csv"), index=False)
        os.replace(os.path.join(work, "submission.m5b.csv"), sub_path)

    if M5_MODE_B == "m5d1":
        if not status:
            verdict, why = "all_methane", "no part-A status"
        elif status.get("exception"):
            verdict, why = "all_methane", "part A exception"
        elif not status.get("finished"):
            verdict, why = "all_methane", "part A did not finish"
        elif int(status.get("selected", 0)) >= M5_MIN_SELECTED and decisions is not None:
            verdict, why = "keep", "%d selected of %d processed" % (status.get("selected", 0), status.get("processed", 0))
        else:
            verdict, why = "all_methane", "only %s selected of %s processed (< %d)" % (status.get("selected"), status.get("processed"), M5_MIN_SELECTED)
        audit.update(verdict=verdict, why=why)
        new = list(cur)
        if verdict == "keep":
            sel = {d["mid"]: d.get("rank1") for d in decisions if d.get("selected")}
            pos = {m: i for i, m in enumerate(mids)}
            done = moved = 0
            for m, r1 in sel.items():
                if m not in pos:
                    continue
                L = [s for s in new[pos[m]].split(";") if s]
                if not L or L[0] != r1 or M5_DECOY in L:
                    moved += 1
                    continue
                new[pos[m]] = ";".join([M5_DECOY] + L[1:])
                done += 1
            audit.update(methane_lists=done, rank1_changed_or_decoy=moved)
            try:
                write(new)
                audit["action"] = "rank1_methane"
            except Exception as ex:                             # never leave a probe that reads like b = 0 by accident
                audit["write_error"] = repr(ex)[:300]
                write([M5_DECOY] * len(mids))
                audit["action"] = "all_methane_after_write_error"
        else:
            write([M5_DECOY] * len(mids))
            audit["action"] = "all_methane"
    else:
        try:
            check(cur)
            audit["checks"] = "ok"
        except Exception as ex:
            audit["checks"] = "FAILED " + repr(ex)[:300]
        if decisions:
            pos = {m: i for i, m in enumerate(mids)}
            at = {}
            for d in decisions:
                if d.get("action") not in ("swap", "reorder") or d["mid"] not in pos or not d.get("new_top2"):
                    continue
                L = [s for s in cur[pos[d["mid"]]].split(";") if s]
                # swap: where the old rank 1 sits now (2, or 3 when the merge inserted at rank 2);
                # reorder: where part A's new rank 2 sits now (same reading)
                x = d.get("rank1") if d["action"] == "swap" else d["new_top2"][1]
                k = "%s_at_%d" % ("old_rank1" if d["action"] == "swap" else "new_rank2", L.index(x) + 1) if x in L else "gone"
                at[k] = at.get(k, 0) + 1
                if d["action"] == "swap" and (not L or L[0] != d["new_top2"][0]):
                    at["new_rank1_not_first"] = at.get("new_rank1_not_first", 0) + 1
            audit["after_merge"] = at
    audit["seconds"] = round(time.monotonic() - t0, 1)
    with open(os.path.join(work, "m5_b_audit.json"), "w") as f:
        json.dump(audit, f, indent=1)
    print("[m5b] done:", json.dumps(audit))


try:
    _m5_b(**globals().get("M5B_DRYRUN_ARGS", {}))
except Exception:
    import traceback

    traceback.print_exc()
    print("[m5b] failed")
