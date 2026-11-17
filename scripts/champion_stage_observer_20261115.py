"""Read-only observation of the pinned .488 production recipe.

No labels, identity canonicalisation, model calls, score changes, or cfg writes.
The runner calls before_cell/after_cell around ORIGINAL inner cell execution,
after_outer_cell after ORIGINAL outer cells, and finish in both processes.
Optional: install_engine2(E, root) immediately after eng_runner imports E.
All wrapped functions return the original object and propagate exceptions.
"""
from __future__ import annotations

import dataclasses
import functools
import hashlib
import inspect
import json
import math
import os
from pathlib import Path
import shutil

CHAMPION_SHA256 = "2bb94c91b176f95dfdff52f08781443ffee004c20d06aeb30efb14d0c0112fc7"
FROZEN_SHA256 = "d1e757c2b71b46e6e8a5777f14302a4737d0fdbcd56d8365093c039b93c5fd88"
PATCHED_ENGINE_SHA256 = "e4943fb26a8141f47ea95e744910c2d0f4746e36e72ef43e3263e7f327cfc0b5"
INNER_STAGES = {32, 34, 37, 39, 41, 43, 45, 48, 49, 50, 51, 52, 53, 54}
OUTER_STAGES = {14, 15, 17, 19, 20, 22, 29, 30, 31, 32}
LIST_NAMES = ("BASE", "ENG", "PC", "PREFUSION_LISTS", "FUSION_OVERFLOW", "BASE_TAIL_CANDIDATES")
FILES = ("submission.csv", "pubchem_promotion_audit.csv", "experiment_audit.csv",
         "candidate_audit.csv", "experiment_audit_factorial.csv", "run_manifest.json",
         "frozen_run_info.json", "batch_variant_audit.json", "v8_report.json",
         "guarded_tail_runtime.json", "guarded_tail_audit.json", "external_overlay_runtime.json",
         "external_overlay_audit.json", "pxm_report.json", "physical_report.json",
         "spectral_parallax_report.json", "variant_M_report.json")
_STATES = {}


def _clean(value):
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else {"nonfinite": repr(value)}
    if dataclasses.is_dataclass(value):
        return _clean(dataclasses.asdict(value))
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_clean(v) for v in value]
    if hasattr(value, "tolist"):
        return _clean(value.tolist())
    if hasattr(value, "item"):
        return _clean(value.item())
    if isinstance(value, Path):
        return str(value)
    return {"type": type(value).__name__, "repr": repr(value)}


def _sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def _json(path, value):
    Path(path).write_text(json.dumps(_clean(value), ensure_ascii=False,
                                    allow_nan=False, indent=2) + "\n", encoding="utf-8")


def _state(root, role):
    key = (str(Path(root).resolve()), role)
    if key not in _STATES:
        out = Path(root) / "champion_stage_observer" / role
        out.mkdir(parents=True, exist_ok=True)
        trace = out / "events.jsonl"
        if trace.exists():
            raise RuntimeError("Observer requires a fresh output directory: " + str(trace))
        _STATES[key] = dict(root=str(root), role=role, out=out, sequence=0, current=None,
                            installed=False, candidate=None, source_pins={}, cfg_before=None)
    return _STATES[key]


def _event(state, kind, **fields):
    state["sequence"] += 1
    row = dict(sequence=state["sequence"], kind=kind, process_id=os.getpid(),
               molecule_id=state.get("current"), **fields)
    with (state["out"] / "events.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_clean(row), ensure_ascii=False, allow_nan=False) + "\n")


def _cfg(engine):
    cfg = engine.cfg
    return _clean(dataclasses.asdict(cfg) if dataclasses.is_dataclass(cfg) else vars(cfg))


def _candidates(C):
    return {name: _clean(getattr(C, name)) for name in
            ("pid", "key", "smiles", "formula", "mass", "is_gen", "gen_sim", "gen_steps", "gen_tan")
            if hasattr(C, name)}


def _products(rows):
    return [{k: _clean(v) for k, v in row.items() if k not in ("fp", "frags")} for row in rows]


def _matrix(value):
    import numpy as np
    arr = np.ascontiguousarray(value)
    return dict(shape=list(arr.shape), dtype=str(arr.dtype), sha256=hashlib.sha256(arr.tobytes()).hexdigest())


def _source(callable_):
    path = inspect.getsourcefile(callable_)
    return dict(path=path, sha256=_sha(path) if path and Path(path).is_file() else None,
                qualname=getattr(callable_, "__qualname__", None))


def install(scope, root):
    """After inner cell 37, after determinism patch and original V1FE hooks."""
    import numpy as np
    import hooks_v1
    from casmi import engine as engine_module
    state = _state(root, "inner")
    if state["installed"]:
        raise RuntimeError("Production observer may only install once")
    E, V = scope["E"], scope["V"]
    if V.E is not E:
        raise RuntimeError("V1FE/Engine instance binding differs")
    actual_engine = _sha(engine_module.__file__)
    if actual_engine != PATCHED_ENGINE_SHA256:
        raise RuntimeError("Expected the exact champion's patched Engine source")
    original = dict(analogs=E.analogs, generate=E.generate, candidates=E.candidates,
                    run=V.run, rank_score=scope["rank_score"], derive_rec=hooks_v1.derive_rec)
    state["source_pins"] = {k: _source(v) for k, v in original.items()}
    state["cfg_before"] = _cfg(E)
    state["engine"] = E
    state["installed"] = True
    _event(state, "install", engine_source_sha256=actual_engine, source_pins=state["source_pins"],
           configuration=state["cfg_before"], ranker_features=list(scope.get("RK_FEATS", [])),
           pool_size=len(E.pool.key), library_structures=len(E.L.struct_smiles),
           champion_sha256=CHAMPION_SHA256, frozen_sha256=FROZEN_SHA256)

    @functools.wraps(original["analogs"])
    def analogs(*args, **kwargs):
        result = original["analogs"](*args, **kwargs)
        entries = []
        for sid, sim, shift, is_np in result:
            entries.append(dict(sid=int(sid), similarity=sim, shift=shift, is_np=is_np,
                                smiles=E.L.struct_smiles[int(sid)], mass=E.L.struct_mass[int(sid)]))
        _event(state, "engine.analogs", entries=entries)
        return result

    @functools.wraps(original["derive_rec"])
    def derive_rec(*args, **kwargs):
        try:
            result = original["derive_rec"](*args, **kwargs)
        except BaseException as exc:
            _event(state, "engine.derive_rec.error", parent_smiles=args[0] if args else None,
                   error_type=type(exc).__name__, error=str(exc))
            raise
        _event(state, "engine.derive_rec", parent_smiles=args[0] if args else kwargs.get("smiles"),
               delta=args[1] if len(args) > 1 else kwargs.get("delta"), parameters=kwargs,
               raw_product_smiles=result)
        return result

    @functools.wraps(original["generate"])
    def generate(*args, **kwargs):
        result = original["generate"](*args, **kwargs)
        _event(state, "engine.generate", accepted_products=_products(result),
               actual_duplicate_rejections=getattr(E, "_derlog", []),
               target=args[1] if len(args) > 1 else kwargs.get("target"))
        return result

    @functools.wraps(original["candidates"])
    def candidates(*args, **kwargs):
        result = original["candidates"](*args, **kwargs)
        _event(state, "engine.candidates", candidates=_candidates(result),
               target=args[0] if args else kwargs.get("target"),
               drop_pid=args[1] if len(args) > 1 else kwargs.get("drop_pid", -1))
        return result

    @functools.wraps(original["run"])
    def run(*args, **kwargs):
        state["current"] = str(scope.get("mid", ""))
        state["candidate"] = None
        _event(state, "v1fe.run.begin", target=args[1] if len(args) > 1 else kwargs.get("target"),
               spectrum_count=len(args[0]) if args else len(kwargs.get("spectra", [])),
               configuration=_cfg(E), simulation_parameters=kwargs)
        try:
            result = original["run"](*args, **kwargs)
        except BaseException as exc:
            _event(state, "v1fe.run.error", error_type=type(exc).__name__, error=str(exc))
            raise
        C, X, F, names, info = result[:5]
        state["candidate"] = _candidates(C)
        _event(state, "v1fe.run.end", candidates=state["candidate"], engine_features=_matrix(X),
               additional_features=_matrix(F), additional_feature_names=names, info=info)
        return result

    @functools.wraps(original["rank_score"])
    def rank_score(*args, **kwargs):
        result = original["rank_score"](*args, **kwargs)
        X = args[0] if args else kwargs["X"]
        names = args[1] if len(args) > 1 else kwargs["names"]
        order = np.argsort(-np.asarray(result), kind="stable")
        candidate = state["candidate"]
        smiles = candidate.get("smiles", []) if candidate else []
        _event(state, "rank_score", candidates=candidate, scores=result, rank_order_indices=order,
               ranked_smiles=[smiles[int(i)] for i in order] if len(smiles) == len(order) else None,
               features=_matrix(X), feature_names=list(names))
        return result

    E.analogs, E.generate, E.candidates = analogs, generate, candidates
    V.run, scope["rank_score"], hooks_v1.derive_rec = run, rank_score, derive_rec


def _snapshot(scope, index, root, role, position):
    state = _state(root, role)
    tag = f"cell_{index:03d}_{position}"
    lists = {name: scope[name] for name in LIST_NAMES if name in scope}
    flags = {name: scope[name] for name in
             ("IS_RERUN", "PIPELINE_DONE", "NEURAL_OK", "CONSENSUS_OK", "OUTSIDERS_OK",
              "V8", "MASS_ON", "MASS_CENTER", "MASS_W", "RR8", "N1_COMPLEMENT") if name in scope}
    records = dict(cell=index, role=role, position=position, lists=lists, flags=flags,
                   identity_computed_by_observer=False)
    records["scores_and_reports"] = {name: scope[name] for name in
                                    ("ICE_SCORES", "GL_SCORES", "MASS_PEN", "MASS_PPM", "LIB_MAX",
                                     "MASS_REPORT", "MASS_LEAD_REPORT", "MERGE_REPORT", "RR8_REPORT",
                                     "PARALLAX_DIAGNOSTICS", "PROVENANCE_REPORT", "GUARDED_TAIL_REPORT",
                                     "EXTERNAL_OVERLAY_REPORT", "EXTERNAL_OVERLAY_AUDIT") if name in scope}
    if "te" in scope and "molecule_id" in getattr(scope["te"], "columns", []):
        records["processed_ids"] = list(dict.fromkeys(scope["te"].molecule_id.astype(str).tolist()))
    _json(state["out"] / f"{tag}.json", records)
    files = {}
    destination = state["out"] / tag
    for name in FILES:
        source = Path(root) / name
        if source.is_file():
            destination.mkdir(exist_ok=True)
            target = destination / name
            shutil.copyfile(source, target)
            files[name] = dict(sha256=_sha(source), snapshot=str(target))
    _event(state, "cell.snapshot", cell=index, position=position, files=files,
           list_names=list(lists), flags=flags)


def before_cell(scope, index, root):
    _event(_state(root, "inner"), "cell.begin", cell=index)
    if index in INNER_STAGES:
        _snapshot(scope, index, root, "inner", "before")


def after_cell(scope, index, root):
    if index == 37:
        install(scope, root)
    if index in INNER_STAGES:
        _snapshot(scope, index, root, "inner", "after")
    _event(_state(root, "inner"), "cell.end", cell=index)


def after_outer_cell(scope, index, root):
    if index in OUTER_STAGES:
        _snapshot(scope, index, root, "outer", "after")


def install_engine2(engine_module, root):
    """Optional eng_runner hook: after import casmi_engine, before original E.main."""
    state = _state(root, "engine2")
    if state["installed"]:
        raise RuntimeError("Engine2 observer may only install once")
    original_main = engine_module.main
    original_blend = engine_module.blend_scores
    state["installed"] = True
    _event(state, "install", source=_source(original_main),
           configuration={name: getattr(engine_module.CFG, name) for name in dir(engine_module.CFG)
                          if name.isupper()}, ranking_configuration={name: getattr(engine_module.RANK, name)
                          for name in dir(engine_module.RANK) if name.isupper()})

    @functools.wraps(original_blend)
    def blend_scores(*args, **kwargs):
        result = original_blend(*args, **kwargs)
        _event(state, "engine2.blend_scores", scores=result,
               weight=args[2] if len(args) > 2 else kwargs)
        return result

    @functools.wraps(original_main)
    def main(*args, **kwargs):
        result = original_main(*args, **kwargs)
        subs, recs, scores = result
        pool = engine_module.POOL
        for rec in recs:
            state["current"] = str(rec["mid"])
            cand = rec["cand"]
            _event(state, "engine2.main.candidates_and_scores", candidate_indices=cand,
                   candidate_smiles=[pool["smiles"][int(i)] for i in cand],
                   candidate_masses=[pool["mass"][int(i)] for i in cand] if "mass" in pool else None,
                   scores={k: v.get(rec["mid"], v.get(str(rec["mid"]))) for k, v in scores.items()
                           if isinstance(v, dict)})
        state["current"] = None
        return result

    engine_module.blend_scores, engine_module.main = blend_scores, main


def finish(scope, root, role="inner"):
    state = _state(root, role)
    checks = dict(no_truth_read=True, configuration_written_by_observer=False,
                  original_return_objects_preserved=True)
    if role == "inner":
        checks["installed_after_original_cell37"] = state["installed"]
        if state["installed"]:
            checks["configuration_unchanged"] = _cfg(state["engine"]) == state["cfg_before"]
    final = Path(root) / "submission.csv"
    report = dict(role=role, event_count=state["sequence"], checks=checks,
                  champion_sha256=CHAMPION_SHA256, frozen_sha256=FROZEN_SHA256,
                  source_pins=state["source_pins"],
                  final_csv_sha256=_sha(final) if final.is_file() else None,
                  score_claim="none; offline official-identity evaluation is separate",
                  visibility_limits=["Engine2 internal trace requires install_engine2 in its child process",
                                     "PubChem raw search is a separate subprocess; PC captures its returned proposals",
                                     "raw derivation rejection reasons beyond existing duplicate log are not inferred"])
    _json(state["out"] / "verification.json", report)
    if any(value is False for key, value in checks.items() if key not in
           ("configuration_written_by_observer",)):
        raise RuntimeError("Read-only production observer checks failed")
    return report
