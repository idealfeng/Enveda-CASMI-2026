# ===== heliosli overlay v3 on the 0.468 notebook: same-formula isomer reranker with the training-structure correction =====
# Criteria reports/rr3_on468_criteria.md (v16 version: reports/reranker_criteria_v3.md). The reranker (peaks matched to
# each candidate's 1-2-cut fragments, graph network + transformer) scores training-set structures about 0.34 SD below
# the other candidates of the same list; FREEZE (rr3_config.json: mode / alpha / delta, see rr_v3.py) keeps every
# training-set candidate in its slot and reorders only the others. Lists with a strong library match (lib_max >=
# LIB_TAU) are untouched. A self-test on three bench molecules must reproduce the offline scores (correlation >= 0.999)
# or the overlay is skipped. Any error leaves the submission unchanged.
# Differences from the v16 cell (same rule, same model): this notebook runs the pinned pipeline in a subprocess, so the
# pipeline's globals are not here. lib_max comes from the pipeline's export frozen_candidate_evidence.parquet
# (library_max = BASE[mid][2] of the pipeline), and the casmi code from the pipeline's work copy of the v4b code
# (/kaggle/working/v43_v4code = the pipeline's V4CODE).
def _rr3_overlay(work='/kaggle/working', inp='/kaggle/input'):
    import glob
    import json
    import math
    import os
    import shutil
    import sys
    import time

    import numpy as np
    import pandas as pd
    import torch

    t0 = time.monotonic()

    def find(pattern):
        hits = sorted(glob.glob(inp + "/**/" + pattern, recursive=True), key=len)
        return hits[0] if hits else None

    cfg_file = find("rr3_config.json")
    if cfg_file is None:
        print("[rr3] skipped: dataset with rr3_config.json not attached")
        return
    pkg = os.path.dirname(cfg_file)
    cfg = json.load(open(cfg_file))
    cfg.update(globals().get("RR3_OVERRIDE") or {})   # a variant notebook may set e.g. RR3_OVERRIDE = dict(alpha=2.0)
    code_dir = "/tmp/rr3code"
    os.makedirs(code_dir, exist_ok=True)
    for f in os.listdir(pkg):
        if f.endswith(".py"):
            shutil.copy(os.path.join(pkg, f), code_dir)
    v4 = globals().get("V4CODE")
    if not v4:
        if os.path.isdir(os.path.join(work, "v43_v4code", "casmi")):
            v4 = os.path.join(work, "v43_v4code")
        else:
            hit = find("casmi26-v4b-models/**/casmi/engine.py")
            v4 = os.path.dirname(os.path.dirname(hit)) if hit else None
    for d in (code_dir, v4, globals().get("V3CODE")):
        if d and d not in sys.path:
            sys.path.insert(0, d)
    import rr_deploy as RDp
    import rr_v3 as V3

    te_df = globals().get("te")
    if not isinstance(te_df, pd.DataFrame) or "ms2_mzs" not in te_df.columns:
        tp = globals().get("TEST_PATH")
        if tp is None or not os.path.exists(str(tp)):
            paths = sorted(glob.glob(inp + "/**/test.parquet", recursive=True), key=lambda p: ("mass-spectra" not in p.lower(), len(p)))
            tp = paths[0]
        te_df = pd.read_parquet(str(tp))

    def ce_of(v):
        try:
            if v is None:
                return None
            if isinstance(v, (list, tuple, np.ndarray)):
                xs = [float(x) for x in v if x is not None and not (isinstance(x, float) and math.isnan(x))]
                return float(np.mean(xs)) if xs else None
            x = float(v)
            return None if math.isnan(x) else x
        except Exception:
            return None

    spectra = {}
    for r in te_df.itertuples(index=False):
        mid = str(r.molecule_id)
        spectra.setdefault(mid, []).append(dict(mz=np.asarray(r.ms2_mzs, np.float64), it=np.asarray(r.ms2_normalized_intensities, np.float64),
                                                prec=float(r.precursor_mz), adduct=str(r.adduct), mode=getattr(r, "ionization_mode", "positive"),
                                                ce=ce_of(getattr(r, "collision_energy_ev", None))))
    base = globals().get("BASE") if isinstance(globals().get("BASE"), dict) else {}
    if not base and os.path.exists(os.path.join(work, "frozen_candidate_evidence.parquet")):
        ev = pd.read_parquet(os.path.join(work, "frozen_candidate_evidence.parquet"), columns=["molecule_id", "library_max"])
        base = {str(m): (None, None, float(v)) for m, v in ev.groupby("molecule_id", sort=False).library_max.first().items()}
    tau = float(globals().get("LIB_TAU", cfg.get("lib_tau", 0.9)))
    mode, alpha, delta = str(cfg["mode"]), float(cfg["alpha"]), float(cfg.get("delta", 0.0))
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    dep = RDp.Deploy(os.path.join(pkg, cfg["encoder"]), os.path.join(pkg, cfg["ckpt"]), device=dev)
    print("[rr3] mode %s, alpha %.2f, delta %.2f, lib_tau %.2f, device %s, BASE %d molecules, casmi code %s" % (mode, alpha, delta, tau, dev, len(base), v4))

    st = json.load(open(os.path.join(pkg, cfg["selftest"])))
    for case in st["cases"]:
        sp = [dict(mz=np.asarray(x["mz"], np.float64), it=np.asarray(x["it"], np.float64), prec=float(x["prec"]), adduct=x["adduct"],
                   mode=x["mode"], ce=x["ce"]) for x in case["spectra"]]
        s = dep.score(sp, case["smiles"])
        r = float(np.corrcoef(np.asarray(s, np.float64), np.asarray(case["scores"], np.float64))[0, 1]) if s is not None else float("nan")
        print("[rr3] self-test %s: correlation with the offline scores %.5f" % (case["molecule_id"], r))
        if not r >= 0.999:
            print("[rr3] self-test failed: overlay skipped, submission unchanged")
            return

    train_path = globals().get("TRAIN_PATH")
    if train_path is None or not os.path.exists(str(train_path)):
        train_path = sorted(glob.glob(inp + "/**/train.parquet", recursive=True), key=len)[0]
    train_ik = set(pd.read_parquet(str(train_path), columns=["inchikey14"]).inchikey14.astype(str))

    sub_path = os.path.join(work, "submission.csv")
    sub = pd.read_csv(sub_path, dtype=str, keep_default_na=False)
    shutil.copy(sub_path, os.path.join(work, "submission_pre_rr3.csv"))
    out, audit = [], dict(molecules=len(sub), reranked=0, changed=0, top1_changed=0, top1_train_lists=0, skipped_library=0,
                          skipped_short=0, no_spectra=0, failed=0, timed_out=0, mode=mode, alpha=alpha, delta=delta, lib_known=len(base))
    for mid, smiles in zip(sub["molecule_id"].astype(str), sub["smiles"].astype(str)):
        smis = [s for s in smiles.split(";") if s]
        new = smis
        lib = 0.0
        if mid in base:
            try:
                lib = float(base[mid][2])
            except Exception:
                lib = 0.0
        if lib >= tau:
            audit["skipped_library"] += 1
        elif len(smis) < 2:
            audit["skipped_short"] += 1
        elif mid not in spectra:
            audit["no_spectra"] += 1
        elif time.monotonic() - t0 > float(cfg.get("budget_s", 2400)):
            audit["timed_out"] += 1
        else:
            try:
                s = dep.score(spectra[mid], smis)
                tr = V3.train_flags(smis, train_ik)
                audit["top1_train_lists"] += int(tr[0])
                new = V3.rerank_v3(smis, s, alpha, mode, tr, delta)
                audit["reranked"] += 1
            except Exception as e:
                audit["failed"] += 1
                if audit["failed"] <= 3:
                    print("[rr3] molecule %s failed: %s %s" % (mid, type(e).__name__, e))
                new = smis
        if new != smis:
            audit["changed"] += 1
            audit["top1_changed"] += int(new[0] != smis[0])
        out.append(";".join(new) if new else smiles)
    res = sub.copy()
    res["smiles"] = out
    assert len(res) == len(sub) and list(res["molecule_id"]) == list(sub["molecule_id"])
    assert res["smiles"].str.split(";").map(len).max() <= 25
    res.to_csv(os.path.join(work, "submission.tmp.csv"), index=False)
    os.replace(os.path.join(work, "submission.tmp.csv"), sub_path)
    audit["seconds"] = round(time.monotonic() - t0, 1)
    with open(os.path.join(work, "rr3_overlay_audit.json"), "w") as f:
        json.dump(audit, f, indent=1)
    print("[rr3] done:", json.dumps(audit))


try:
    _rr3_overlay(**globals().get("RR3_DRYRUN_ARGS", {}))
except Exception:
    import traceback

    traceback.print_exc()
    print("[rr3] overlay failed; the public submission is unchanged")
