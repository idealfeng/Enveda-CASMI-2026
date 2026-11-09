"""Prepare/run generated Flex V56 or V43 reference-isolation diagnostics.

Always use scripts/linux_env.sh first. --prepare-only performs CPU index/mask
checks, writes generated source, and does not load model checkpoints or use GPU.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from validation import pipeline_adapter as adapter


def path_for_runtime(value):
    text = str(value).replace("\\", "/")
    if sys.platform == "linux" and len(text) > 2 and text[1:3] == ":/":
        text = "/mnt/" + text[0].lower() + text[2:]
    return Path(text).expanduser().resolve()


def make_configuration(args):
    import pandas as pd
    import pyarrow.parquet as pq
    manifest_path = args.manifest.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    panel_root = manifest_path.parent
    for name, expected in manifest["artifact_sha256"].items():
        path = panel_root / name
        if adapter.sha(path) != expected:
            raise ValueError("Frozen validation artifact changed: " + str(path))
    queries = panel_root / manifest["queries_file"]
    ids = sorted(pd.read_parquet(queries, columns=["molecule_id"]).molecule_id.astype(str).unique())
    if ids != sorted(manifest["active_ids"]) or len(ids) != manifest["processed_molecules"]:
        raise ValueError("Query cohort differs from frozen manifest")
    train = path_for_runtime(manifest["train"]["path"])
    if train.stat().st_size != manifest["train"]["bytes"] or pq.ParquetFile(train).metadata.num_rows != manifest["train"]["rows"]:
        raise ValueError("Original training table differs from the panel's source")
    cache = args.shared_spec_cache.resolve()
    cache_receipt = json.loads((cache / "cache_complete.json").read_text())
    if cache_receipt.get("status") != "complete" or cache_receipt["rows"] != manifest["train"]["rows"]:
        raise ValueError("Shared cache must cover the original full training row order")
    work = args.work_root.resolve()
    # All artifacts must remain under the D: project workspace.
    for path in (work, cache, queries, train):
        if not path.is_relative_to(ROOT):
            raise ValueError("Validation files/cache must remain within D: workspace: " + str(path))
    if (work / "submission.csv").exists():
        raise ValueError("Fresh work-root required; an output already exists")
    work.mkdir(parents=True, exist_ok=True)
    query_comp = work / "query_comp"
    query_comp.mkdir(exist_ok=True)
    original_test = ROOT / "enveda-CASMI26-molecule-id-mass-spectra/test.parquet"
    columns = pq.read_schema(original_test).names
    table = pq.read_table(queries, columns=columns)
    # Ground-truth/raw keys/source rows remain outside the inference input.
    pq.write_table(table, query_comp / "test.parquet", compression="zstd")
    target = query_comp / "train.parquet"
    if target.exists() or target.is_symlink():
        if target.resolve() != train:
            raise ValueError("query_comp/train.parquet points to another source")
    else:
        target.symlink_to(train)
    pd.DataFrame({"molecule_id": ids, "smiles": ["CCO"] * len(ids)}).to_csv(query_comp / "sample_submission.csv", index=False)
    mode = args.reference_mode
    exclusion_name = manifest["reference_exclusion_rows_file"] if mode == "class2" else manifest["query_duplicate_exclusion_rows_file"]
    exposure = dict(manifest["training_exposure"])
    saner_result = ROOT / "assets/kaggle/sanpier/casmi-spectrum-model-v1/v1/casmi_spectrum_model_v1/training_result.json"
    if args.pipeline == "flex":
        published = json.loads(saner_result.read_text(encoding="utf-8"))
        exposure["Saner_final_model"] = dict(status="declared_full_refit_including_former_validation_identities",
            evidence=str(saner_result), evidence_sha256=adapter.sha(saner_result),
            producer_statement=published.get("final_model_training"),
            clean_holdout_performance_claimed=False)
    config = dict(schema_version=1, pipeline=args.pipeline, work_root=str(work),
        manifest=str(manifest_path), manifest_sha256=adapter.sha(manifest_path),
        queries_file=str(queries), query_comp=str(query_comp), query_test_sha256=adapter.sha(query_comp / "test.parquet"),
        train=str(train), base_train_rows=manifest["train"]["rows"],
        shared_spec_cache=str(cache), reference_mode=mode,
        exclusion_rows_file=str(panel_root / exclusion_name),
        exclusion_keys_file=str(panel_root / manifest["reference_exclusion_keys_file"]),
        processed_molecules=len(ids), active_ids=ids,
        cohort_policy=("global leave-cohort-identity-out; all current pilot query identities removed from every reference path"
                       if mode == "class2" else "global query-spectrum/exact-duplicate exclusion; other spectra of target structures remain"),
        ice_budget_seconds=args.ice_budget or max(300, 60 + 12 * len(ids)),
        gl_budget_seconds=args.gl_budget, n1_budget_seconds=args.n1_budget or max(600, 60 + 12 * len(ids)),
        evaluation_label="reference-isolated diagnostic with known pretrained exposure",
        pretrained_exposure=exposure,
        known_exposure_note="FPNet full1 declares ALL training folds; Flex Saner final_model is declared full-data refit including former validation identities. This is not clean CV.",
        implementation_sha256=adapter.sha(Path(adapter.__file__)),
        pretrained_assets_read_only=True, candidate_truth_retained=True,
        input_truth_columns_exposed_to_source=False, query_columns=columns)
    if args.resume_from:
        if args.pipeline != "flex": raise ValueError("Recovery currently supports Flex only")
        config["resume_from"] = str(args.resume_from.resolve())
        config["recovery_implementation_sha256"] = adapter.sha(ROOT / "validation/recovery.py")
    config_path = work / "validation_config.json"
    adapter.write_json(config_path, config)
    return config_path, config


def cpu_mask_preflight(config_path, config):
    """Exercise real metadata/index masks on CPU; never initialize a model."""
    import numpy as np
    import pandas as pd
    import pyarrow.parquet as pq
    from types import SimpleNamespace
    source_rows, keys = adapter._exclusions(config)
    cache = Path(config["shared_spec_cache"])
    meta = pd.read_parquet(cache / "spec_meta.parquet", columns=["sid"])
    pool = ROOT / "assets/kaggle/ahmedberatozer/casmi26-v2-pool/v1"
    st = pd.read_parquet(pool / "train_structs.parquet", columns=["sid", "inchikey14"])
    blocked_sids = st.loc[st.inchikey14.astype(str).isin(keys), "sid"].to_numpy(dtype=np.int64)
    mask = np.isin(meta.sid.to_numpy(), blocked_sids)
    mask[source_rows] = True
    if config["reference_mode"] == "class2":
        expected = pd.read_parquet(config["exclusion_rows_file"], columns=["source_row"]).source_row.to_numpy()
        assert mask[expected].all()
    # Test production masking with a tiny CSR-backed index fixture. It keeps
    # absolute row IDs, excludes duplicate rows and independently verifies the
    # Engine representatives gate; the full real metadata mask is checked above.
    code = ROOT / "assets/kaggle/ahmedberatozer/casmi26-v4b-models/v4/code"
    sys.path.insert(0, str(ROOT / "scripts"))
    from reproduction_io import install_shared_cache
    install_shared_cache(code, cache, mmap_pool=True)
    adapter.install_e1(code, config_path)
    from casmi.library import Library
    from casmi.engine import Engine, NP_LIBS
    fixture_work = Path(config["work_root"]) / "mask_preflight"
    fixture_work.mkdir(exist_ok=True)
    for name in ("spec_meta.parquet", "spec_off.npy", "spec_mz.npy", "spec_it.npy"):
        destination = fixture_work / name
        if not destination.exists(): destination.symlink_to(cache / name)
    structs = fixture_work / "train_structs.parquet"
    if not structs.exists(): structs.symlink_to(pool / "train_structs.parquet")
    library = Library(str(fixture_work), verbose=False)
    assert np.array_equal(mask, library._validation_excluded)
    assert not mask[library.window(300.0, 1e6)].any()
    reps = library.representatives()
    assert not mask[reps["idx"]].any()
    dummy_engine = SimpleNamespace(L=library)
    engine_reps = Engine._reps(dummy_engine)
    assert not mask[engine_reps["idx"]].any()
    # Exercise the same class on the actual 751-spectrum extension produced by
    # the already completed source reproduction. No extended cache is rebuilt.
    extended_check = dict(status="unavailable", reason="No completed local external-reference cache")
    existing_extensions = sorted((ROOT / "runs/flexonafft_smoke_20261104b").glob("external_reference_*"))
    if existing_extensions:
        extended_library = Library(str(existing_extensions[0]), verbose=False)
        excluded = extended_library._validation_excluded
        assert np.array_equal(excluded[:len(mask)], mask)
        assert len(excluded) == len(mask) + 751
        assert not excluded[extended_library.order].any()
        extended_reps = Engine._reps(SimpleNamespace(L=extended_library))
        assert not excluded[extended_reps["idx"]].any()
        extended_check = dict(status="passed", extra_spectra=751,
            excluded_extra_spectra=int(excluded[len(mask):].sum()),
            all_original_base_exclusions_preserved=True, extended_engine_representatives_checked=True)
        del extended_library, extended_reps
    # Full E2 build_index creates ~3GB raw peak arrays. Its exact source gate is
    # checked structurally here; runtime hooks assert every actual E2 index.
    source = ROOT / "third_party/flexonafft_evidence_gap/v56/embedded/engine2_sources/casmi_engine.py"
    import ast
    text = source.read_text(encoding="utf-8")
    node = next(n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef) and n.name == "build_index")
    body = ast.get_source_segment(text, node)
    assert 'L["row_p"] >= 0' in body and all(f'I["{key}"] = _reps' in body for key in ("all", "pos", "neg"))
    # Execute the original E2 representative/index code on a small adversarial
    # fixture: a blocked identity has the richest spectrum, and another allowed
    # identity's query row is removed while its alternate reference survives.
    fixture = fixture_work / "e2_fixture"
    fixture.mkdir(exist_ok=True)
    pd.DataFrame({"source_row": [2]}).to_parquet(fixture / "rows.parquet", index=False)
    pd.DataFrame({"source_row": [2]}).to_parquet(fixture / "queries.parquet", index=False)
    adapter.write_json(fixture / "keys.json", {"blocked_raw_keys": ["BLOCKED"]})
    fixture_config = dict(config, work_root=str(fixture), base_train_rows=6,
        exclusion_rows_file=str(fixture / "rows.parquet"), exclusion_keys_file=str(fixture / "keys.json"),
        queries_file=str(fixture / "queries.parquet"), reference_mode="class2")
    adapter.write_json(fixture / "config.json", fixture_config)
    engine_file = ROOT / "third_party/flexonafft_evidence_gap/v56/embedded/engine2_sources/pv.py"
    import importlib.util
    pv_spec = importlib.util.spec_from_file_location("validation_fixture_pv", engine_file)
    pv = importlib.util.module_from_spec(pv_spec); pv_spec.loader.exec_module(pv)
    # This tiny source-index fixture exercises Python versions of the exact
    # cleaning functions. Dynamic-module Numba cache imports are not stable
    # across repeated prepare processes; production E2 imports pv normally.
    pv._clean = pv._clean.py_func
    pv.clean_store = pv.clean_store.py_func
    functions = ast.Module(body=[n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef)
                                and n.name in ("_reps", "build_index")], type_ignores=[])
    env = dict(np=np, pd=pd, pv=pv, CFG=pv.CFG, log=lambda *args: None)
    exec(compile(functions, "original_e2_index_fixture", "exec"), env)
    raw_library = dict(prec=np.full(6, 301.0), nm=np.full(6, 300.0),
        ik=np.array(["BLOCKED", "BLOCKED", "ALLOWED", "ALLOWED", "OTHER", "OTHER"], object),
        row_p=np.array([0, 0, 1, 1, 2, 2]), pol=np.array([1, -1, 1, -1, 1, -1]),
        tims=np.ones(6, bool), off=np.arange(7, dtype=np.int64),
        mz=np.full(6, 100.0, np.float32), it=np.ones(6, np.float32))
    engine_fixture = SimpleNamespace(load_library=lambda path: raw_library,
        build_index=env["build_index"], main=lambda *args, **kwargs: None,
        POOL={"keys": np.array(["BLOCKED", "ALLOWED", "OTHER"], object)})
    adapter.install_e2(engine_fixture, fixture / "config.json")
    selected_library = engine_fixture.load_library("fixture")
    fixture_index = engine_fixture.build_index(selected_library)
    assert set(fixture_index["lib_rows"]) == {3, 4, 5}
    assert set(fixture_index["all"]["rep_p"]) == {1, 2}
    assert set(engine_fixture.POOL["keys"]) == {"BLOCKED", "ALLOWED", "OTHER"}
    report = dict(status="passed", models_loaded=False, gpu_used=False,
        base_rows=len(mask), excluded_rows=int(mask.sum()), blocked_sids=len(blocked_sids),
        library_allowed_rows=len(library.order), library_representatives=len(reps["idx"]),
        engine_representatives=len(engine_reps["idx"]),
        existing_751_external_reference_check=extended_check,
        all_direct_and_representative_indices_exclusion_checked=True,
        e2_build_index_source_gate_verified=True, e2_runtime_index_check="required during model run",
        e2_adversarial_fixture_passed=True,
        csr_rows_and_offsets_unchanged=True, candidate_pool_filtered=False)
    adapter.write_json(Path(config["work_root"]) / "validation_mask_preflight.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--pipeline", choices=["flex", "v43"], required=True)
    parser.add_argument("--reference-mode", choices=["class2", "class1"], default="class2")
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--input-root", type=Path, help="Defaults to pinned inputs for the selected pipeline")
    parser.add_argument("--shared-spec-cache", type=Path, default=ROOT / "runs/shared_spec_cache")
    parser.add_argument("--ice-budget", type=int)
    parser.add_argument("--gl-budget", type=int, default=4000)
    parser.add_argument("--n1-budget", type=int)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--resume-from", type=Path, help="Failed Flex run to bind and conservatively reuse E2/PC/forward outputs")
    args = parser.parse_args()
    if sys.platform != "linux" or sys.version_info[:2] != (3, 12):
        parser.error("Use WSL Linux Python3.12 with source scripts/linux_env.sh")
    if any(value is not None and value <= 0 for value in (args.ice_budget, args.gl_budget, args.n1_budget)):
        parser.error("Budgets must be positive seconds")
    config_path, config = make_configuration(args)
    if args.resume_from:
        from validation.recovery import bind
        bind(args.resume_from, config)
    work = Path(config["work_root"])
    input_root = args.input_root or ROOT / ("assets/kaggle" if args.pipeline == "flex" else "runs/inputs/prvsiyan_v43")
    if args.pipeline == "flex":
        notebook, source_receipt = adapter.prepare_flex(input_root.resolve(), work,
            Path(config["query_comp"]), config_path)
        cells = [(i, "".join(c["source"]) if isinstance(c["source"], list) else c["source"])
                 for i, c in enumerate(notebook["cells"]) if c.get("cell_type") == "code"]
        adapter.write_json(work / "adapted_validation_flex.ipynb", notebook)
    else:
        cells, source_receipt = adapter.prepare_v43(input_root.resolve(), work,
            Path(config["query_comp"]), config_path)
    folder = work / "validation_cells"
    folder.mkdir(exist_ok=True)
    for i, text in cells:
        compile(text, f"validation_cell_{i}", "exec")
        (folder / f"cell_{i:02d}.py").write_text(text, encoding="utf-8")
    receipt = dict(status="prepared", config=config, source=source_receipt,
        runner_sha256=adapter.sha(Path(__file__)), cell_results=[])
    receipt_path = work / "validation_run_receipt.json"
    adapter.write_json(receipt_path, receipt)
    if args.prepare_only:
        try:
            receipt["mask_preflight"] = cpu_mask_preflight(config_path, config)
        except BaseException:
            receipt.update(status="failed_prepare", traceback=traceback.format_exc())
            adapter.write_json(receipt_path, receipt)
            raise
        receipt["status"] = "prepared_and_cpu_mask_checked"
        adapter.write_json(receipt_path, receipt)
        print(json.dumps(dict(status=receipt["status"], pipeline=args.pipeline,
                              molecules=config["processed_molecules"], work_root=str(work))))
        return 0
    # A prepare-only process installs test hooks. Actual runs are always a new
    # process, so no mutated module state or fixture masks carry into execution.
    os.environ.pop("KAGGLE_IS_COMPETITION_RERUN", None)
    os.environ.pop("CASMI_LOCAL", None)
    os.chdir(work)
    from IPython.display import display
    scope = dict(__name__="__main__", __file__=str(folder / "validation_runner.py"), display=display,
                 _LOCAL_COMPETITION_ROOT=config["query_comp"])
    receipt["status"] = "running"
    started = time.monotonic()
    adapter.write_json(receipt_path, receipt)
    try:
        for index, text in cells:
            record = dict(cell=index, status="running")
            receipt["cell_results"].append(record)
            adapter.write_json(receipt_path, receipt)
            print("VALIDATION_CELL_START", index, flush=True)
            cell_start = time.monotonic()
            exec(compile(text, str(folder / f"cell_{index:02d}.py"), "exec"), scope)
            record.update(status="complete", elapsed_seconds=round(time.monotonic() - cell_start, 3))
            adapter.write_json(receipt_path, receipt)
        if args.pipeline == "v43": adapter.export_scope(scope, work)
        receipt["runtime_audit"] = adapter.final_audit(config_path)
        receipt["status"] = "complete"
    except BaseException:
        receipt.update(status="failed", traceback=traceback.format_exc())
        if receipt["cell_results"]: receipt["cell_results"][-1]["status"] = "failed"
        traceback.print_exc()
        return 1
    finally:
        receipt["elapsed_seconds"] = round(time.monotonic() - started, 3)
        adapter.write_json(receipt_path, receipt)
    print("VALIDATION_COMPLETE", receipt_path, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
