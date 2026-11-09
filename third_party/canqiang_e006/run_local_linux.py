"""Run original E006 V1 cells in Linux with recorded path and GPU observations.

Original source, ranking, weights, smoke selection and simulator budgets remain
unchanged. An isolated input view makes source globbing deterministic. Attached
datasets are distinguished from files actually needed by this notebook at runtime.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import time
import traceback


SOURCE_SHA256 = "ee55b55c7f5bdb08f1a8154396b18fdb0203fb7178b3a52429e0999e69ad7e53"
COMPETITION = "enveda-CASMI26-molecule-id-mass-spectra"
OPTIONAL_ATTACHED = {
    "hengck23/hengck23-dreams-enveda-casmi26": (
        "The historical V2 listing has no dreams_np_mass.npy/dreams_np_smiles.npy; "
        "the notebook's guarded tail branch does not read its embedding payloads."),
    "eveliaveldrine/rdkit-wheels": (
        "Historical V3 contains cp313 wheels. Python 3.12 uses compatible wheels "
        "bundled in the ICEBERG package instead; the original compatibility checks remain."),
}
FILE_SUBSETS = {
    "prvsiyan/casmi26-ranker-features": {"rank_train.npz"},
    "prvsiyan/casmi26-fp-models-v2": {"fp_single_s2.pt", "fp_merged_m1.pt"},
    "dmitriigluzdov/casmi26-pubchem-popularity-prior": {
        "pc_lsid.npy", "pc_lpmid.npy", "pool_lsid.npy", "pool_lpmid.npy"},
    "megayak/casmi26-simulated-ranker-rows": {"sim_rank_rows_nofp.npz"},
    "ahmedberatozer/casmi26-fpnet-full1": {"fpnet_full1.pt"},
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def source_text(cell: dict) -> str:
    value = cell["source"]
    return "".join(value) if isinstance(value, list) else value


def version_number(path: Path) -> int:
    return int(path.name[1:]) if path.name.startswith("v") and path.name[1:].isdigit() else -1


def required_files(ref: str, files: list[dict]) -> list[dict]:
    if ref in OPTIONAL_ATTACHED:
        return []
    if ref in FILE_SUBSETS:
        found = [item for item in files if item["name"] in FILE_SUBSETS[ref]]
        if {item["name"] for item in found} != FILE_SUBSETS[ref]:
            raise RuntimeError(f"Historical file inventory does not support runtime policy: {ref}")
        return found
    if ref == "metric/rdkit-2026-3-3-wheel":
        # Do not demand unrelated interpreters' wheels. The source still installs
        # and verifies the actual compatible wheel itself.
        from pip._vendor.packaging.tags import sys_tags
        from pip._vendor.packaging.utils import parse_wheel_filename
        tags = set(sys_tags())
        selected = []
        for item in files:
            if not item["name"].startswith("rdkit-2026.3.3-"):
                continue
            _, _, _, wheel_tags = parse_wheel_filename(Path(item["name"]).name)
            if tags.intersection(wheel_tags):
                selected.append(item)
        if not selected:
            raise RuntimeError("Historical official-wheel listing has no compatible runtime wheel")
        return selected
    return files


def inspect_inputs(input_root: Path, inventory: dict, mode: str) -> tuple[list, list]:
    bindings = []
    blockers = []
    for ref, reference in inventory.items():
        expected_version = int(reference["version"])
        dataset_root = input_root.joinpath(*ref.split("/"))
        selected_root = dataset_root / f"v{expected_version}"
        selected_version = expected_version
        differences = []
        if not selected_root.is_dir() and mode == "available" and dataset_root.is_dir():
            alternatives = sorted((path for path in dataset_root.iterdir()
                                   if path.is_dir() and version_number(path) >= 0), key=version_number)
            if alternatives:
                selected_root = alternatives[-1]
                selected_version = version_number(selected_root)
                differences.append({"kind": "version_substitution", "expected": expected_version,
                                    "selected": selected_version})
        required = required_files(ref, reference["files"])
        observed_files = []
        for item in required:
            path = selected_root / item["name"]
            observed = {"name": item["name"], "historical_bytes": item["bytes"],
                        "exists": path.is_file()}
            if path.is_file():
                observed["actual_bytes"] = path.stat().st_size
                if observed["actual_bytes"] != item["bytes"]:
                    differences.append({"kind": "file_size_difference", **observed})
                    if selected_version == expected_version or mode == "exact":
                        blockers.append({"ref": ref, "kind": "file_size_difference", **observed})
            else:
                blockers.append({"ref": ref, "kind": "missing_runtime_file", **observed})
            observed_files.append(observed)
        if not selected_root.is_dir():
            differences.append({"kind": "attached_dataset_absent", "expected_version": expected_version})
        optional_present_files = []
        if ref in OPTIONAL_ATTACHED and selected_root.is_dir():
            optional_present_files = [item["name"] for item in reference["files"]
                                      if (selected_root / item["name"]).is_file()]
        bindings.append({
            "ref": ref, "historical_version": expected_version,
            "selected_version": selected_version if selected_root.is_dir() else None,
            "selected_root": str(selected_root), "attached_directory_exists": selected_root.is_dir(),
            "runtime_required": bool(required), "required_files": observed_files,
            "optional_reason": OPTIONAL_ATTACHED.get(ref),
            "optional_present_files": optional_present_files, "differences": differences,
            "verification_scope": "version directory and file size; source retains package-MANIFEST checks",
        })
    return bindings, blockers


def link_directory(link: Path, target: Path) -> None:
    if link.is_symlink():
        if link.resolve() == target.resolve():
            return
        raise RuntimeError(f"Input view has an existing link to a different target: {link}")
    if link.exists():
        raise RuntimeError(f"Refusing to replace existing input-view path: {link}")
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(target, target_is_directory=True)


def make_input_view(view: Path, bindings: list, competition_root: Path) -> None:
    view.mkdir(parents=True, exist_ok=True)
    for binding in bindings:
        if binding["attached_directory_exists"]:
            link_directory(view.joinpath(*binding["ref"].split("/")), Path(binding["selected_root"]))
    if competition_root.is_dir():
        link_directory(view / "competitions" / COMPETITION, competition_root)


def adapt_cells(notebook: dict, input_view: Path, work_root: Path,
                shared_cache: Path | None = None,
                reuse_engine_lists: bool = False) -> tuple[list, list]:
    prepared = []
    patches = []
    gpu_guards = 0
    location_guards = 0
    cache_hooks = 0
    train_fp_mmaps = 0
    reused_calls = 0
    original_asserts = adapted_asserts = 0
    for index, cell in enumerate(notebook["cells"]):
        if cell["cell_type"] != "code":
            continue
        original = source_text(cell)
        original_asserts += sum(isinstance(node, ast.Assert) for node in ast.walk(ast.parse(original)))
        adapted = original
        changes = []
        for before, after in (("/kaggle/input", input_view.as_posix()),
                              ("/kaggle/working", work_root.as_posix())):
            count = adapted.count(before)
            if count:
                adapted = adapted.replace(before, after)
                changes.append({"kind": "path_translation", "before": before,
                                "after": after, "count": count})
        before_gpu = "assert 'T4' in gpu, gpu"
        if before_gpu in adapted:
            gpu_guards += adapted.count(before_gpu)
            adapted = adapted.replace(before_gpu, "print('LOCAL_GPU_OBSERVED', gpu)")
            changes.append({"kind": "hardware_observer", "before": before_gpu,
                            "after": "print('LOCAL_GPU_OBSERVED', gpu)"})
        location_line = next((line for line in adapted.splitlines()
                              if "assert comp in {" in line), None)
        if location_line is not None:
            location_guards += 1
            replacement = "    assert comp == os.path.realpath(scope['_LOCAL_COMPETITION_ROOT'])"
            adapted = adapted.replace(location_line, replacement)
            changes.append({"kind": "local_competition_path_guard",
                            "before": location_line, "after": replacement})
        if shared_cache is not None:
            cache_import = "from casmi.build import build_spec_cache"
            if cache_import in adapted:
                cache_hooks += adapted.count(cache_import)
                replacement = (
                    "from reproduction_io import install_shared_cache as _install_shared_cache\n"
                    "_LOCAL_IO_RECEIPT = _install_shared_cache(V4CODE, _LOCAL_SHARED_CACHE, mmap_pool=True)\n"
                    + cache_import)
                adapted = adapted.replace(cache_import, replacement)
                changes.append({"kind": "verified_shared_cache", "before": cache_import,
                                "after": replacement, "shared_cache": str(shared_cache),
                                "algorithm_changes": False})
            before_fp = "tfp = np.load('work/train_fp_sel.npy')"
            if before_fp in adapted:
                train_fp_mmaps += adapted.count(before_fp)
                after_fp = "tfp = np.load('work/train_fp_sel.npy', mmap_mode='c')"
                adapted = adapted.replace(before_fp, after_fp)
                changes.append({"kind": "copy_on_write_train_fingerprint_mapping",
                                "before": before_fp, "after": after_fp,
                                "algorithm_changes": False})
        if reuse_engine_lists and index == 11:
            calls = []
            for node in ast.walk(ast.parse(adapted)):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and isinstance(node.func.value, ast.Name) and node.func.value.id == "subprocess"
                        and node.func.attr == "run" and node.args
                        and any(isinstance(value, ast.Constant) and value.value == "eng_runner.py"
                                for value in ast.walk(node.args[0]))):
                    calls.append(node)
            if len(calls) != 1:
                raise RuntimeError(f"Unexpected Engine2 subprocess count: {len(calls)}")
            before = ast.get_source_segment(adapted, calls[0])
            if adapted.count(before) != 1:
                raise RuntimeError("Ambiguous Engine2 subprocess replacement")
            after = "_LOCAL_REUSE_ENGINE_LISTS(globals())"
            adapted = adapted.replace(before, after, 1)
            reused_calls += 1
            changes.append({"kind": "validated_engine2_output_reuse", "before": before,
                            "after": after, "preserves_ENG_FILES_generation": True})
        tree = ast.parse(adapted, filename=f"canqiang_e006_v1.cell_{index:02d}.py")
        adapted_asserts += sum(isinstance(node, ast.Assert) for node in ast.walk(tree))
        prepared.append((index, adapted))
        patches.append({"cell": index, "source_sha256": digest(original.encode()),
                        "adapted_sha256": digest(adapted.encode()), "changes": changes})
    if gpu_guards != 1 or location_guards != 1 or adapted_asserts != original_asserts - 1:
        raise RuntimeError("Unexpected source guard/assertion counts; refusing unreviewed adaptation")
    if len(prepared) != 30:
        raise RuntimeError(f"Expected 30 code cells, got {len(prepared)}")
    if shared_cache is not None and (cache_hooks != 1 or train_fp_mmaps != 1):
        raise RuntimeError("Unexpected shared-cache hook counts; refusing unreviewed adaptation")
    if reuse_engine_lists and reused_calls != 1:
        raise RuntimeError("Unexpected Engine2 reuse hook count")
    return prepared, patches


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", required=True, type=Path,
                        help="Dataset store: owner/slug/vN directories, e.g. assets/kaggle")
    parser.add_argument("--work-root", required=True, type=Path,
                        help="Dedicated output/cache directory; use a fresh directory for a different input mode")
    parser.add_argument("--competition-root", required=True, type=Path)
    parser.add_argument("--shared-spec-cache", type=Path,
                        help="Verified full cache built with the same casmi cleaning code and train-structure order")
    parser.add_argument("--reuse-engine-lists", type=Path,
                        help="Prior E006 eng_lists.json; requires successful Engine2 and unchanged source/query/input metadata")
    parser.add_argument("--input-mode", choices=["exact", "available"], default="exact",
                        help="exact requires historical runtime versions; available explicitly permits other local versions")
    parser.add_argument("--prepare-only", action="store_true",
                        help="Write adapted cells, input differences and blockers without executing notebook code")
    args = parser.parse_args()
    if sys.platform != "linux":
        parser.error("Use Linux/WSL; bundled simulator wheels and this full runner target Linux")
    input_root = args.input_root.expanduser().resolve()
    work_root = args.work_root.expanduser().resolve()
    competition_root = args.competition_root.expanduser().resolve()
    shared_cache = args.shared_spec_cache.expanduser().resolve() if args.shared_spec_cache else None
    prior_engine_lists = args.reuse_engine_lists.expanduser().resolve() if args.reuse_engine_lists else None
    if prior_engine_lists and prior_engine_lists.parent == work_root:
        parser.error("Use a new work root when reusing a prior Engine2 output")
    if input_root == work_root or input_root.is_relative_to(work_root):
        parser.error("The dedicated work root must not contain the dataset store")
    for path in (input_root, work_root, competition_root, *([shared_cache] if shared_cache else [])):
        if any(character in str(path) for character in ("'", '"', "\\", "\n", "\r")):
            parser.error("Source-path translation requires paths without quotes, backslashes or newlines")
    here = Path(__file__).resolve().parent
    original_path = here / "original/canqiang_e006_v1.ipynb"
    raw = original_path.read_bytes()
    if digest(raw) != SOURCE_SHA256:
        raise RuntimeError("Original notebook SHA-256 differs from the downloaded E006 V1")
    notebook = json.loads(raw)
    inventory = json.loads((here / "dataset_file_inventory.json").read_text(encoding="utf-8"))
    bindings, blockers = inspect_inputs(input_root, inventory, args.input_mode)
    io_helper = here.parent.parent / "scripts/reproduction_io.py"
    if shared_cache is not None:
        if not (shared_cache / "cache_complete.json").is_file():
            blockers.append({"kind": "missing_shared_cache_receipt", "root": str(shared_cache)})
        if not io_helper.is_file():
            blockers.append({"kind": "missing_shared_cache_adapter", "path": str(io_helper)})
    for name in ("train.parquet", "test.parquet", "sample_submission.csv"):
        if not (competition_root / name).is_file():
            blockers.append({"kind": "missing_competition_file", "name": name})
    work_root.mkdir(parents=True, exist_ok=True)
    input_view = work_root / "attached_input"
    make_input_view(input_view, bindings, competition_root)
    cells, patches = adapt_cells(notebook, input_view, work_root, shared_cache,
                                 reuse_engine_lists=bool(prior_engine_lists))
    prepared_dir = work_root / "adapted_cells"
    prepared_dir.mkdir(exist_ok=True)
    for index, text in cells:
        (prepared_dir / f"cell_{index:02d}.py").write_text(text, encoding="utf-8")
    receipt = {
        "notebook_ref": "canqiang/casmi26-e006-window-40-ice-fallback-true",
        "notebook_version": 1, "source_sha256": SOURCE_SHA256,
        "runner_sha256": digest(Path(__file__).read_bytes()),
        "runtime": {"platform": sys.platform, "python": platform.python_version(),
                    "executable": sys.executable, "input_root": str(input_root),
                    "input_view": str(input_view), "work_root": str(work_root),
                    "competition_root": str(competition_root)},
        "input_mode": args.input_mode, "attached_inputs": bindings,
        "engine2_reuse_requested": str(prior_engine_lists) if prior_engine_lists else None,
        "shared_spec_cache": str(shared_cache) if shared_cache else None,
        "io_helper_sha256": digest(io_helper.read_bytes()) if shared_cache and io_helper.is_file() else None,
        "runtime_input_blockers": blockers, "status": "prepared", "patches": patches,
        "cell_results": [],
        "limitations": [
            "This local runtime is not byte-identical to the original Kaggle T4 runtime.",
            "Source rankers, candidate rules, model logic, stage-health assertions and budgets are unchanged.",
            "Optional shared-cache mode verifies cleaning-code/structure provenance and changes only array storage IO.",
            "The source retains its 12-molecule visible-placeholder smoke and padding behavior.",
            "Optional attached data can be absent only where the unmodified source already guards that branch.",
            "available input mode is an explicitly different-input reproduction, not historical-score reproduction.",
            "Source E004/ancestor identifiers remain unchanged; this receipt identifies actual E006 V1.",
            "No hidden-test score or competition-license eligibility is established by local execution.",
        ],
    }
    receipt_path = work_root / "local_run_receipt.json"
    write_json(receipt_path, receipt)
    reuse_module = reuse_binding = None
    if prior_engine_lists:
        import importlib.util
        module_path = here.parent / "prvsiyan_analog/reuse_engine_lists.py"
        spec = importlib.util.spec_from_file_location("e006_engine_reuse", module_path)
        reuse_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(reuse_module)
        try:
            reuse_binding = reuse_module.validate_reuse(
                prior_engine_lists, input_view, competition_root, notebook, SOURCE_SHA256,
                notebook_version=1, engine_cell=11)
        except Exception:
            receipt.update(status="reuse_validation_failed", traceback=traceback.format_exc())
            write_json(receipt_path, receipt)
            raise
        write_json(work_root / "engine2_reuse_binding.json", reuse_binding)
        receipt["engine2_reuse"] = {
            "status": "validated", "prior_lists": str(prior_engine_lists),
            "prior_lists_sha256": reuse_binding["prior_lists_sha256"],
            "prior_receipt_sha256": reuse_binding["prior_receipt_sha256"],
            "active_query_sha256": reuse_binding["active_query"]["sha256"],
            "molecules": reuse_binding["molecules"], "input_files": len(reuse_binding["input_files"]),
            "input_metadata_sha256": reuse_binding["input_metadata_sha256"],
            "binding_sha256": reuse_binding["binding_sha256"], "not_cold_start": True,
            "helper_sha256": digest(module_path.read_bytes()),
        }
        receipt["limitations"].append("Engine2 reuse makes elapsed time a recovery-run time, not a cold-start time.")
        write_json(receipt_path, receipt)
    print(f"INPUT_AUDIT mode={args.input_mode} required_blockers={len(blockers)}", flush=True)
    if args.prepare_only:
        print(f"Prepared {len(cells)} code cells without execution: {receipt_path}", flush=True)
        return 0
    if blockers:
        receipt["status"] = "blocked_before_execution"
        write_json(receipt_path, receipt)
        print(json.dumps(blockers, indent=2), flush=True)
        return 2
    if not input_root.is_dir():
        raise FileNotFoundError(input_root)
    try:
        from IPython.display import display as notebook_display
        display_implementation = "IPython.display.display"
    except ImportError:
        # The source uses display only for presentation. Keep command-line runs
        # usable without an extra notebook UI dependency.
        def notebook_display(*objects, **_options):
            for value in objects:
                print(value, flush=True)
        display_implementation = "plain_text_fallback"
    os.chdir(work_root)
    namespace = {"__name__": "__main__", "__file__": str(original_path),
                 "_LOCAL_COMPETITION_ROOT": str(competition_root),
                 "_LOCAL_SHARED_CACHE": str(shared_cache) if shared_cache else None,
                 "display": notebook_display}
    receipt["notebook_display_compatibility"] = {
        "implementation": display_implementation, "scope": "presentation only", "algorithm_changes": False}
    if prior_engine_lists:
        def copy_engine2(scope):
            try:
                result = reuse_module.copy_reused_lists(reuse_binding, scope, work_root)
            except Exception:
                receipt["engine2_reuse"].update(status="copy_failed", traceback=traceback.format_exc())
                write_json(receipt_path, receipt)
                raise
            receipt["engine2_reuse"]["status"] = "copied"
            write_json(receipt_path, receipt)
            return result
        namespace["_LOCAL_REUSE_ENGINE_LISTS"] = copy_engine2
    if shared_cache is not None:
        sys.path.insert(0, str(io_helper.parent))
    started = time.monotonic()
    receipt["status"] = "running"
    write_json(receipt_path, receipt)
    for index, text in cells:
        item = {"cell": index, "status": "running"}
        receipt["cell_results"].append(item)
        write_json(receipt_path, receipt)
        cell_started = time.monotonic()
        print(f"LOCAL_CELL_START {index}", flush=True)
        try:
            exec(compile(text, str(prepared_dir / f"cell_{index:02d}.py"), "exec"), namespace)
            if prior_engine_lists and index == 11:
                if (receipt["engine2_reuse"]["status"] != "copied"
                        or set(namespace.get("ENG", {})) != set(reuse_binding["active_query"]["molecule_ids"])):
                    raise RuntimeError("Engine2 reuse was caught or produced unexpected target IDs")
                item["reused_engine2"] = True
        except BaseException:
            item.update(status="failed", elapsed_seconds=round(time.monotonic() - cell_started, 3))
            receipt.update(status="failed", failed_cell=index, traceback=traceback.format_exc(),
                           elapsed_seconds=round(time.monotonic() - started, 3))
            write_json(receipt_path, receipt)
            traceback.print_exc()
            return 1
        item.update(status="complete", elapsed_seconds=round(time.monotonic() - cell_started, 3))
        receipt["elapsed_seconds"] = round(time.monotonic() - started, 3)
        write_json(receipt_path, receipt)
        print(f"LOCAL_CELL_END {index} {item['elapsed_seconds']}s", flush=True)
    receipt["status"] = "complete"
    receipt["elapsed_seconds"] = round(time.monotonic() - started, 3)
    receipt["is_full_run"] = bool(namespace.get("IS_RERUN"))
    receipt["processed_molecules"] = len(set(namespace["te"].molecule_id.astype(str)))
    receipt["observed_gpu"] = namespace.get("E004_PREFLIGHT", {}).get("gpu")
    receipt["input_molecules"] = len(namespace.get("E004_PREFLIGHT", {}).get("input_ids", []))
    receipt["dreams_tail_candidates_added"] = namespace.get("_dreams_used")
    receipt["shared_cache_runtime"] = namespace.get("_LOCAL_IO_RECEIPT")
    receipt["outputs"] = [
        {"name": path.name, "bytes": path.stat().st_size, "sha256": digest(path.read_bytes())}
        for path in sorted(work_root.glob("*.csv"))
    ]
    write_json(receipt_path, receipt)
    print(f"LOCAL_RUN_COMPLETE {receipt_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
