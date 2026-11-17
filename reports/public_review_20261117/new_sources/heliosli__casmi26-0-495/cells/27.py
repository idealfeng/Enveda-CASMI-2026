# ===== heliosli M5 part A (after CV-JOINT, before the FRIGID merge): in-list isomer judgement by M2 + ICE-T + M3 (reports/c3_design_v0.md 11-07 10:15, 18:07, 19:31) =====
# Each list in priority order (P1_LOW by ascending p1, then the other p1-scored lists, then lists without a p1): rank 1
# against each candidate at ranks 2..K. Structure records (MAGMa depth 4 + 1-2 bond cuts) are built in a 3-process pool
# under ICEBERG's RDKit 2025.03 and ICE-T fullT predicts every candidate at every test spectrum on the first T4, both in
# subprocesses while this process scores the lists whose records and views are ready: M2 (heliosli/casmi26-m5) ->
# evidence units -> the five M3 fold models -> z(c) = M3's preference for c over rank 1 (m3_bench.py's computation).
# Mode (M5_MODE): reorder = ranks 2..K by z, rank 1 kept; swap = max z > tau[stratum] -> that candidate to rank 1, the
# old rank 1 to rank 2; m5d1 = the lists swap would change are recorded, part B (after the merge) puts methane at their
# rank 1. Budget = min(package budget, END_H - session time); a list not reached keeps its order; any failure leaves
# submission.csv unchanged. FRIGID guard (frigid_guard 'core'): one physical core is left to FRIGID, part A's threads and
# workers use the rest (workers at nice 19, builder processes = A CPUs - 1), restored at the end; MemAvailable < 3 GB
# stops before the next list (a deadline stop). Status -> m5_status.json (part B reads it), m5_a_audit.json, m5_decisions.json.
M5_MODE = "swap"
M5_CFG_OVERRIDE = {"tau": {"low": 3.376455144882207, "conf": 3.376455144882207, "nop1": None, "np": 5.0}, "duel_min_z": 5.0, "duel_strata": ["np"]}   # 11-10 S1: 0.495 + NP5D rule only on NP lists in P1_LOW (line 129); K by the package rule


def _m5_a(work="/kaggle/working", inp="/kaggle/input", pkg_dir=None, test_path=None, z_override=None):
    import glob
    import json
    import os
    import shutil
    import sys
    import tarfile
    import time
    import traceback

    import pandas as pd

    t0 = time.monotonic()
    st_path = os.path.join(work, "m5_status.json")
    status = dict(mode=M5_MODE, finished=False, exception=None, stage="start", deadline_stop=False, lists=0, actionable=0,
                  processed=0, selected=0, changed=0, written=False, session_h_at_start=None, K=None, budget_s=None)
    audit, decisions = dict(mode=M5_MODE), []

    def save(path, obj):
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(obj, f, indent=1, default=str)
        os.replace(tmp, path)

    def log(*a):
        print("[m5a %6.0fs]" % (time.monotonic() - t0), *a, flush=True)

    if "NB_T0" in globals():
        status["session_h_at_start"] = round((time.time() - float(globals()["NB_T0"])) / 3600, 3)
    save(st_path, status)
    guard = None
    try:
        assert M5_MODE in ("reorder", "swap", "m5d1"), M5_MODE
        # ---- package: heliosli/casmi26-m5 (m5_manifest.json next to isomer.tar, src.tar, fullT.tar and the weights)
        status["stage"] = "package"
        if pkg_dir is None:
            man = sorted(glob.glob(inp + "/**/m5_manifest.json", recursive=True), key=len)
            assert man, "casmi26-m5 dataset not attached (no m5_manifest.json)"
            pkg_dir = os.path.dirname(man[0])
        manifest = json.load(open(os.path.join(pkg_dir, "m5_manifest.json")))
        dst = os.path.join(work, "m5pkg")
        os.makedirs(dst, exist_ok=True)
        members, unpacked = manifest.get("members") or {}, []
        names = ("isomer", "src", "fullT") + (("icerun",) if "icerun.tar" in manifest["sha256"] else ())
        for name in names:
            if os.path.isdir(os.path.join(dst, name)):
                continue
            t = os.path.join(pkg_dir, name + ".tar")
            if os.path.isfile(t):
                with tarfile.open(t) as tf:
                    tf.extractall(dst)
                continue
            # Kaggle unpacks an uploaded tar into a directory (biohub 09-11): find the tree holding this tar's members
            # (the deepest member path, without the top folder, so any nesting Kaggle chose is found) and copy it
            rest = max((m.split("/", 1)[1] for m in (members.get(name) or {}) if "/" in m), key=lambda r: (r.count("/"), r), default=None)
            assert rest, "missing " + t
            hits = sorted(glob.glob(os.path.join(pkg_dir, "**", rest), recursive=True), key=len)
            assert hits, "missing %s (neither the tar nor its unpacked tree)" % t
            shutil.copytree(hits[0][: len(hits[0]) - len(rest)], os.path.join(dst, name))
            unpacked.append(name)
        audit["package_form"] = {n: ("unpacked tree" if n in unpacked else "tar") for n in names}
        sys.path.insert(0, os.path.join(dst, "isomer"))
        import m5_core as M5
        bad = [f for f, h in manifest["sha256"].items()
               if not (f.endswith(".tar") and f[:-4] in unpacked) and M5.sha256(os.path.join(pkg_dir, f)) != h]
        bad += [m for n in unpacked for m, h in members[n].items() if M5.sha256(os.path.join(dst, m)) != h]
        assert not bad, "package files differ from the manifest: %s" % bad
        cfg = dict(manifest["config"])
        cfg.update(globals().get("M5_CFG_OVERRIDE") or {})
        audit["config"] = dict(cfg)
        audit["weights"] = {f: h[:12] for f, h in manifest["sha256"].items() if f.endswith(".pt")}
        # ---- FRIGID CPU guard, before any subprocess starts: one physical core stays FRIGID's (cell 11's watcher keeps
        # its own affinity); every kernel thread -> the other CPUs, inherited by the builder pool and the ICE-T worker
        # (both nice 19); restored in finally, so the merge and part B run unconstrained
        guard = M5.CpuGuard(cfg.get("frigid_guard", "core"))
        a_set = guard.apply()
        if a_set is not None:
            cfg["procs"] = max(1, len(a_set) - 1)
        if cfg.get("frigid_guard", "core") != "off":
            # nice works even where pinning did not (a cgroup quota, a refused cpuset); without pinning keep the pool small
            cfg["nice"] = int(cfg.get("nice_workers", 19))
            if a_set is None and hasattr(os, "sched_getaffinity"):
                cfg["procs"] = max(1, len(os.sched_getaffinity(0)) // 2 - 1)
        audit["frigid_guard"] = dict(guard.info, builder_procs=int(cfg.get("procs", 3)), worker_nice=int(cfg.get("nice") or 0))
        log("FRIGID guard:", json.dumps(audit["frigid_guard"]))
        budget = float(cfg["budget_s"])
        if "NB_T0" in globals():
            budget = max(0.0, min(budget, float(cfg["end_h"]) * 3600 - (time.time() - float(globals()["NB_T0"]))))
        status["budget_s"] = round(budget, 1)
        deadline = time.time() + budget
        # ---- inputs: the list after CV-JOINT, the p1 gate's strata, the test spectra
        status["stage"] = "inputs"
        sub_path = os.path.join(work, "submission.csv")
        sub = pd.read_csv(sub_path, dtype=str, keep_default_na=False)
        mids = sub["molecule_id"].astype(str).tolist()
        full = {m: [s for s in str(x).split(";") if s] for m, x in zip(mids, sub["smiles"].astype(str))}
        p1_low = set(globals().get("P1_LOW") or set())
        p1_of = dict(globals().get("P1_OF") or {})
        strata = {m: M5.stratum_of(m, p1_low, p1_of) for m in mids}
        # natural-product gate (c3 11-08 07:50): M3 is validated on drug-like timsTOF lists only (jt1t has no natural
        # product; on the timsTOF NP panel ICE-T errs 5-10x more), so a list whose rank 1 is in the pipeline's NP table
        # (npdb_np.parquet, the file CV-JOINT reads) is never touched. Table or RDKit missing -> no list is touched.
        np_gate = dict(table=None, gated=0, status="")
        try:
            from rdkit import Chem, RDLogger
            RDLogger.DisableLog("rdApp.*")
            np_hits = sorted(glob.glob(inp + "/**/npdb_np.parquet", recursive=True))
            np_gate["table"] = np_hits[0]
            np_keys = set(pd.read_parquet(np_hits[0], columns=["key14"]).key14)
            for m in mids:
                mol = Chem.MolFromSmiles(full[m][0]) if full[m] else None
                if mol is not None and Chem.MolToInchiKey(mol)[:14] in np_keys:
                    strata[m] = "np" if m in p1_low else "nop1"   # 11-10 NP split by the p1 gate: NP lists in P1_LOW keep "np"; the other NP lists go to "nop1" (off), so only NP lists the base is least sure of can swap
                    np_gate["np_in_p1_low"] = np_gate.get("np_in_p1_low", 0) + int(m in p1_low)
                    np_gate["gated"] += 1
            np_gate["status"] = "ok"
        except Exception as ex:
            np_gate["status"] = "unavailable, nothing touched: " + repr(ex)[:200]
            strata = {m: "np" for m in mids}
        audit["np_gate"] = np_gate
        if test_path is None:
            comp = globals().get("COMP")
            if comp is not None and os.path.exists(os.path.join(str(comp), "test.parquet")):
                test_path = os.path.join(str(comp), "test.parquet")
            else:
                hits = sorted(glob.glob(inp + "/**/test.parquet", recursive=True), key=lambda p: ("mass-spectra" not in p.lower(), len(p)))
                test_path = hits[0]
        te = pd.read_parquet(test_path)
        sys.path.insert(0, os.path.join(dst, "isomer"))
        import m2_data as MD
        T, spec = M5.spectra_by_molecule(te, MD)

        def actionable(s):
            if M5_MODE == "reorder":
                return s in cfg["reorder_strata"]
            return cfg["tau"].get(s) is not None
        usable = [m for m in mids if len(full[m]) >= 2 and actionable(strata[m]) and m in spec]
        order = M5.priority(usable, p1_low, p1_of)
        K = int(cfg["K"])
        est = len(order) * K * float(cfg.get("struct_s_est", 1.2)) / max(1, int(cfg.get("procs", 3)))
        if budget < float(cfg.get("k_full_min_budget_s", 0.0)) or est > float(cfg.get("k_fit_share", 0.7)) * budget:
            K = int(cfg["K_fallback"])
        audit["k_rule"] = dict(est_build_s_at_K=round(est), budget_s=round(budget), share=cfg.get("k_fit_share", 0.7), K=K)
        status.update(lists=len(mids), actionable=len(order), K=K)
        audit["strata"] = {s: sum(1 for m in mids if strata[m] == s) for s in M5.STRATA}
        audit["actionable_by_stratum"] = {s: sum(1 for m in order if strata[m] == s) for s in M5.STRATA}
        lists = {m: full[m][:K] for m in order}
        log("mode", M5_MODE, "| lists", len(mids), "| actionable", len(order), "| K", K, "| budget %.0f s" % budget,
            "| strata", audit["strata"])
        if budget < float(cfg.get("min_budget_s", 600.0)):
            log("no time left: nothing scored")
            Z, info, tim = {}, {}, dict(stop="no time")
        elif z_override is not None:
            zz = json.load(open(z_override))
            Z = {m: {int(i): float(v) for i, v in d.items()} for m, d in zz.items()}
            info, tim = {}, dict(stop="z_override")
        else:
            status["stage"] = "evidence"
            save(st_path, status)
            if not cfg.get("use_icet", True) and not cfg.get("scaffold_allow_no_icet", False):
                raise RuntimeError("use_icet is off: the ICE-T-feature M3 cannot run without ICE-T views")
            runner = cfg.get("ice_runner_dir")
            if not runner and os.path.exists(os.path.join(dst, "icerun", "ice_runner.py")):
                runner = os.path.join(dst, "icerun")          # the package's own runner + Python 3.13 wheels (11-08)
            if not runner:                                   # casmi26-iceberg: ice_runner.py next to ckpt/ (and wheels/)
                hits = [os.path.dirname(p) for p in glob.glob(inp + "/**/ice_runner.py", recursive=True)
                        if os.path.isdir(os.path.join(os.path.dirname(p), "ckpt"))]
                site_ok = os.path.exists(os.path.join(cfg.get("ice_site", "/tmp/ice_site"), ".ice_site_ok"))
                cand = [d for d in hits if os.path.isdir(os.path.join(d, "wheels"))] or (hits if site_ok else [])
                assert cand, "casmi26-iceberg runner not found (ice_runner.py with ckpt/ and wheels/, or an installed site)"
                runner = sorted(cand, key=len)[0]
            audit["ice_runner_dir"] = runner
            pkg = dict(isomer=os.path.join(dst, "isomer"), root=dst, m2=os.path.join(pkg_dir, cfg["m2"]),
                       m3=[os.path.join(pkg_dir, f) for f in cfg["m3"]], d5=os.path.join(pkg_dir, cfg["d5"]),
                       fullT=os.path.join(dst, "fullT"), runner=runner, site=cfg.get("ice_site", "/tmp/ice_site"))
            try:
                import torch
                torch.cuda.empty_cache()
            except Exception:
                pass
            Z, info, tim = M5.collect_z(order, lists, spec, T, pkg, work, deadline, cfg, log)
        status["deadline_stop"] = tim.get("stop") in ("deadline", "memory")   # a memory stop counts as a deadline stop
        status["stop_reason"] = tim.get("stop")
        audit["timings"] = tim
        # ---- decisions
        status["stage"] = "decide"
        new = sub["smiles"].astype(str).tolist()
        pos = {m: i for i, m in enumerate(mids)}
        per = {s: dict(processed=0, selected=0, changed=0) for s in M5.STRATA}
        # 11-13 [2a1230] MEGx prior (c3 11-13 09:5x, target 0.540): in the "np" stratum each challenger's z gets
        # + MEGX_BETA * (megx(c) - megx(rank 1)), megx = key14 in the AnalytiCon MEGx catalogue (COCONUT 2026-11 collection).
        # timsTOF NP panel (not in M3 training, deployed M3 5-fold mean, tau 5): x1.8 hidden-weighted +0.012 -> +0.026 at beta 5.
        # Table or RDKit missing -> no list is adjusted (C* unchanged).
        MEGX_BETA = float(globals().get("MEGX_BETA", 5.0))
        megx_audit = dict(beta=MEGX_BETA, table=None, n_keys=0, adjusted_lists=0, changed_best=0, status="")
        megx_keys, _mk = set(), {}
        try:
            _mh = sorted(glob.glob(inp + "/**/analyticon_megx.parquet", recursive=True))
            megx_audit["table"] = _mh[0]
            megx_keys = set(pd.read_parquet(_mh[0], columns=["key14"]).key14)
            megx_audit["n_keys"] = len(megx_keys)
            megx_audit["status"] = "ok"
        except Exception as ex:
            megx_audit["status"] = "off: " + type(ex).__name__

        def _megx(s):
            if s not in _mk:
                mol = Chem.MolFromSmiles(s)
                _mk[s] = float(mol is not None and Chem.MolToInchiKey(mol)[:14] in megx_keys)
            return _mk[s]
        for m in order:
            z = Z.get(m) or {}
            L = full[m]
            if strata[m] == "np" and z and megx_keys:
                _b0 = max(z, key=lambda i: (z[i], -i))
                _m0 = _megx(L[0])
                z = {i: v + MEGX_BETA * (_megx(L[i]) - _m0) for i, v in z.items()}
                megx_audit["adjusted_lists"] += 1
                megx_audit["changed_best"] += int(max(z, key=lambda i: (z[i], -i)) != _b0)
            out, rec = M5.decide(M5_MODE, m, L, z, strata[m], cfg, duel=(info.get(m) or {}).get("duel"))
            rec.update(info.get(m, {}))
            rec["p1"] = p1_of.get(m)
            rec["rank1"] = L[0]
            if z:
                status["processed"] += 1
                per[strata[m]]["processed"] += 1
            if rec["selected"]:
                status["selected"] += 1
                per[strata[m]]["selected"] += 1
            if out is not None and M5_MODE in ("swap", "reorder"):
                new[pos[m]] = ";".join(out)
                rec["new_top2"] = out[:2]
                status["changed"] += 1
                per[strata[m]]["changed"] += 1
            decisions.append(rec)
        audit["by_stratum"] = per
        audit["megx_prior"] = megx_audit
        audit["duel"] = dict(min_z=cfg.get("duel_min_z"), strata=cfg.get("duel_strata"),
                             computed=sum(1 for m in order if "duel" in (info.get(m) or {})),
                             eligible=sum(1 for d in decisions if (d.get("duel_decision") or {}).get("eligible")),
                             applied=sum(1 for d in decisions if (d.get("duel_decision") or {}).get("applied")))
        # ---- write-back (swap / reorder); m5d1 writes nothing here (part B, after the merge)
        status["stage"] = "write"
        if M5_MODE in ("swap", "reorder") and status["changed"]:
            M5.write_submission(sub, new, sub_path, globals().get("SAMPLE_IDS"))
            status["written"] = True
        status["finished"] = True
        status["stage"] = "done"
    except Exception as ex:
        status["exception"] = repr(ex)[:500]
        traceback.print_exc()
    finally:
        if guard is not None:
            guard.restore()
            audit.setdefault("frigid_guard", {})["restored_tids"] = guard.info.get("restored_tids")
        status["seconds"] = round(time.monotonic() - t0, 1)
        save(st_path, status)
        save(os.path.join(work, "m5_decisions.json"), decisions)
        save(os.path.join(work, "m5_a_audit.json"), dict(audit, status=status))
        log("done:", json.dumps({k: status[k] for k in ("mode", "finished", "exception", "deadline_stop", "actionable", "processed",
                                                        "selected", "changed", "written", "K", "budget_s", "seconds")}))


try:
    _m5_a(**globals().get("M5_DRYRUN_ARGS", {}))
except Exception:
    import traceback

    traceback.print_exc()
    print("[m5a] failed; the submission is unchanged")
