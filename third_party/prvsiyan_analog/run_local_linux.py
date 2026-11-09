"""Run the downloaded V43 source in Linux with recorded path/hardware adaptations.

The original notebook is never edited. This runner preserves source smoke selection,
models, ranking logic, simulator budgets, and the source's stage-health assertions.
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


SOURCE_SHA256 = "a1da86c791cdbcb553254a12cef8bca8b527b991f40953d9dcb2a9c819d3c852"
COMPETITION = "enveda-CASMI26-molecule-id-mass-spectra"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def source_text(cell: dict) -> str:
    value = cell["source"]
    return "".join(value) if isinstance(value, list) else value


def adapt_cells(notebook: dict, input_root: Path, work_root: Path,
                mmap_train_fp: bool = False, reuse_engine_lists: bool = False) -> tuple[list, list]:
    prepared = []
    patches = []
    gpu_guards = 0
    location_guards = 0
    competition_bindings = 0
    fp_loads = 0
    reused_calls = 0
    for index, cell in enumerate(notebook["cells"]):
        if cell["cell_type"] != "code":
            continue
        original = source_text(cell)
        adapted = original
        changes = []
        for before, after in (("/kaggle/input", input_root.as_posix()),
                              ("/kaggle/working", work_root.as_posix())):
            count = adapted.count(before)
            if count:
                adapted = adapted.replace(before, after)
                changes.append({"kind": "path_translation", "before": before,
                                "after": after, "count": count})

        # Keep Python/RDKit/data assertions, while observing the actual local GPU.
        before_gpu = "assert 'T4' in gpu, gpu"
        if before_gpu in adapted:
            gpu_guards += adapted.count(before_gpu)
            adapted = adapted.replace(before_gpu, "print('LOCAL_GPU_OBSERVED', gpu)")
            changes.append({"kind": "hardware_observer", "before": before_gpu,
                            "after": "print('LOCAL_GPU_OBSERVED', gpu)"})

        # os.path.realpath follows an input-directory symlink back to the original
        # local competition data. Compare against that explicitly supplied target.
        location_line = next((line for line in adapted.splitlines()
                              if "assert comp in {" in line), None)
        if location_line is not None:
            location_guards += 1
            replacement = "    assert comp == os.path.realpath(scope['_LOCAL_COMPETITION_ROOT'])"
            adapted = adapted.replace(location_line, replacement)
            changes.append({"kind": "local_competition_path_guard",
                            "before": location_line, "after": replacement})

        if mmap_train_fp:
            before = "np.load('work/train_fp_sel.npy')"
            if before in adapted:
                fp_loads += adapted.count(before)
                after = "np.load('work/train_fp_sel.npy', mmap_mode='c')"
                adapted = adapted.replace(before, after)
                changes.append({"kind": "copy_on_write_train_fingerprint_mmap", "before": before,
                                "after": after})

        before_comp = "COMP = os.path.dirname(find('test.parquet'))"
        if before_comp in adapted:
            competition_bindings += adapted.count(before_comp)
            after_comp = "COMP = _LOCAL_COMPETITION_ROOT"
            adapted = adapted.replace(before_comp, after_comp)
            changes.append({"kind": "explicit_local_competition_binding", "before": before_comp,
                            "after": after_comp})

        if reuse_engine_lists and index == 12:
            calls = []
            for node in ast.walk(ast.parse(adapted)):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and isinstance(node.func.value, ast.Name) and node.func.value.id == "subprocess"
                        and node.func.attr == "run" and node.args
                        and any(isinstance(n, ast.Constant) and n.value == "eng_runner.py"
                                for n in ast.walk(node.args[0]))):
                    calls.append(node)
            if len(calls) != 1:
                raise RuntimeError(f"Unexpected cell12 Engine2 subprocess count: {len(calls)}")
            before = ast.get_source_segment(adapted, calls[0])
            if adapted.count(before) != 1:
                raise RuntimeError("Engine2 subprocess source replacement is ambiguous")
            after = "_LOCAL_REUSE_ENGINE_LISTS(globals())"
            adapted = adapted.replace(before, after, 1)
            reused_calls += 1
            changes.append({"kind": "validated_engine2_output_reuse", "before": before,
                            "after": after, "preserves_ENG_FILES_generation": True})

        ast.parse(adapted, filename=f"prvsiyan_v43.cell_{index:02d}.py")
        prepared.append((index, adapted))
        patches.append({"cell": index, "source_sha256": digest(original.encode()),
                        "adapted_sha256": digest(adapted.encode()), "changes": changes})

    if gpu_guards != 1 or location_guards != 1:
        raise RuntimeError(f"Unexpected source guard counts: GPU={gpu_guards}, location={location_guards}")
    if mmap_train_fp and fp_loads != 1:
        raise RuntimeError(f"Unexpected train fingerprint load count: {fp_loads}")
    if competition_bindings != 1:
        raise RuntimeError(f"Unexpected competition binding count: {competition_bindings}")
    if reuse_engine_lists and reused_calls != 1:
        raise RuntimeError(f"Unexpected reused Engine2 call count: {reused_calls}")

    # N1's embedded code is hash-bound by the source. Translation must not alter it.
    original_n1 = {}
    adapted_n1 = {}
    for target, cells in ((original_n1, [(i, source_text(c)) for i, c in enumerate(notebook["cells"])
                                       if c["cell_type"] == "code"]),
                          (adapted_n1, prepared)):
        for _, text in cells:
            for node in ast.parse(text).body:
                if not (isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)):
                    continue
                name = node.targets[0].id
                if name in ("N1_CORE_SRC", "N1_DRIVER_SRC"):
                    # These are literal ''.join([...]) assignments, never evaluated.
                    target[name] = "".join(ast.literal_eval(node.value.args[0]))
    if original_n1 != adapted_n1 or len(original_n1) != 2:
        raise RuntimeError("Path adaptation changed a hash-bound N1 embedded script")
    return prepared, patches


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", required=True, type=Path,
                        help="Local equivalent of /kaggle/input, with attached dataset subdirectories")
    parser.add_argument("--work-root", required=True, type=Path,
                        help="Dedicated output/cache directory, equivalent to /kaggle/working")
    parser.add_argument("--competition-root", type=Path,
                        help="Actual local directory containing train.parquet/test.parquet/sample_submission.csv")
    parser.add_argument("--prepare-only", action="store_true",
                        help="Write adapted cells and patch receipt; do not execute notebook code")
    parser.add_argument("--shared-spec-cache", type=Path,
                        help="Completed equivalent cache from scripts/build_shared_spec_cache.py")
    parser.add_argument("--mmap-pool", action="store_true",
                        help="Also map pool fingerprints/fragments copy-on-write; requires --shared-spec-cache")
    parser.add_argument("--reuse-engine-lists", type=Path,
                        help="Successful prior V43 run's eng_lists.json; validates source, queries and full input metadata")
    args = parser.parse_args()

    if args.mmap_pool and not args.shared_spec_cache:
        parser.error("--mmap-pool requires --shared-spec-cache")

    if sys.platform != "linux":
        parser.error("Run this adapter in Linux/WSL; bundled simulator wheels target Linux")
    input_root = args.input_root.expanduser().resolve()
    work_root = args.work_root.expanduser().resolve()
    competition_root = (args.competition_root or input_root / "competitions" / COMPETITION).expanduser().resolve()
    if args.shared_spec_cache is not None:
        # Resolve before chdir(work_root); a relative CLI cache path is anchored
        # to the launch directory, just like the other path arguments.
        args.shared_spec_cache = args.shared_spec_cache.expanduser().resolve()
    if args.reuse_engine_lists is not None:
        args.reuse_engine_lists = args.reuse_engine_lists.expanduser().resolve()
        if args.reuse_engine_lists.parent == work_root:
            parser.error("Engine2 recovery requires a new work-root; do not overwrite the prior run")
    for path in (input_root, work_root, competition_root):
        if any(character in str(path) for character in ("'", '"', "\\", "\n", "\r")):
            parser.error("For literal source-path translation, paths cannot contain quotes, backslashes or newlines")

    original_path = Path(__file__).resolve().with_name("prvsiyan_v43.ipynb")
    raw = original_path.read_bytes()
    if digest(raw) != SOURCE_SHA256:
        raise RuntimeError("Original notebook SHA-256 differs from the downloaded V43 snapshot")
    notebook = json.loads(raw)
    cells, patches = adapt_cells(notebook, input_root, work_root,
                                 mmap_train_fp=bool(args.shared_spec_cache),
                                 reuse_engine_lists=bool(args.reuse_engine_lists))
    work_root.mkdir(parents=True, exist_ok=True)
    prepared_dir = work_root / "adapted_cells"
    prepared_dir.mkdir(exist_ok=True)
    for index, text in cells:
        (prepared_dir / f"cell_{index:02d}.py").write_text(text, encoding="utf-8")

    receipt = {
        "notebook_ref": "prvsiyan/analog-propagation-casmi-2026-baseline",
        "notebook_version": 43,
        "script_version_id": 360497306,
        "source_sha256": SOURCE_SHA256,
        "runner_sha256": digest(Path(__file__).read_bytes()),
        "runtime": {"platform": sys.platform, "python": platform.python_version(),
                    "executable": sys.executable, "input_root": str(input_root),
                    "work_root": str(work_root), "competition_root": str(competition_root)},
        "status": "prepared",
        "patches": patches,
        "shared_cache_requested": str(args.shared_spec_cache.resolve()) if args.shared_spec_cache else None,
        "engine2_reuse_requested": str(args.reuse_engine_lists) if args.reuse_engine_lists else None,
        "cell_results": [],
        "notebook_globals": {"display": "IPython.display.display"},
        "limitations": [
            "Path and hardware adaptations mean this is not a byte-identical Kaggle runtime.",
            "The source retains its 12-molecule visible-placeholder smoke and padding behavior.",
            "Visible smoke output and any padded rows are not independent validation or leaderboard reproduction.",
            "Source e004 reports retain ancestor-source identifiers; this receipt identifies the actual downloaded V43.",
            "Public input availability does not certify competition-license eligibility.",
        ],
    }
    receipt_path = work_root / "local_run_receipt.json"
    write_json(receipt_path, receipt)
    reuse_module = None
    reuse_binding = None
    if args.reuse_engine_lists:
        import importlib.util
        module_path = original_path.with_name("reuse_engine_lists.py")
        spec = importlib.util.spec_from_file_location("v43_engine_reuse", module_path)
        reuse_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(reuse_module)
        try:
            reuse_binding = reuse_module.validate_reuse(
                args.reuse_engine_lists, input_root, competition_root, notebook, SOURCE_SHA256)
        except Exception:
            receipt.update(status="reuse_validation_failed", traceback=traceback.format_exc())
            write_json(receipt_path, receipt)
            raise
        write_json(work_root / "engine2_reuse_binding.json", reuse_binding)
        receipt["engine2_reuse"] = {
            "status": "validated", "prior_lists": str(args.reuse_engine_lists),
            "prior_lists_sha256": reuse_binding["prior_lists_sha256"],
            "prior_receipt_sha256": reuse_binding["prior_receipt_sha256"],
            "active_query_sha256": reuse_binding["active_query"]["sha256"],
            "molecules": reuse_binding["molecules"], "input_files": len(reuse_binding["input_files"]),
            "input_metadata_sha256": reuse_binding["input_metadata_sha256"],
            "binding_sha256": reuse_binding["binding_sha256"], "not_cold_start": True,
            "helper_sha256": digest(module_path.read_bytes()),
        }
        receipt["limitations"].append("Engine2 reuse enabled: elapsed times are recovery-run times, not cold-start times.")
        write_json(receipt_path, receipt)
    if args.prepare_only:
        print(f"Prepared {len(cells)} code cells without execution: {receipt_path}", flush=True)
        return 0

    for name in ("train.parquet", "test.parquet", "sample_submission.csv"):
        if not (competition_root / name).is_file():
            raise FileNotFoundError(competition_root / name)
    if not input_root.is_dir():
        raise FileNotFoundError(input_root)
    os.chdir(work_root)
    try:
        from IPython.display import display
    except ImportError:
        def display(*objects, **kwargs):
            for value in objects:
                print(value)
        receipt["notebook_globals"]["display"] = "text fallback (IPython unavailable)"
        write_json(receipt_path, receipt)
    namespace = {"__name__": "__main__", "__file__": str(original_path),
                 "_LOCAL_COMPETITION_ROOT": str(competition_root), "display": display}
    if args.reuse_engine_lists:
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
    started = time.monotonic()
    receipt["status"] = "running"
    write_json(receipt_path, receipt)
    shared_cache_installed = False
    for index, text in cells:
        item = {"cell": index, "status": "running"}
        receipt["cell_results"].append(item)
        write_json(receipt_path, receipt)
        cell_started = time.monotonic()
        print(f"LOCAL_CELL_START {index}", flush=True)
        try:
            if (args.shared_spec_cache and not shared_cache_installed
                    and "from casmi.build import build_spec_cache" in text):
                scripts = original_path.parents[2] / "scripts"
                sys.path.insert(0, str(scripts))
                from reproduction_io import install_shared_cache
                receipt["io_adaptation"] = install_shared_cache(
                    namespace["V4CODE"], args.shared_spec_cache, mmap_pool=args.mmap_pool)
                receipt["io_adaptation"]["helper_sha256"] = digest(
                    (scripts / "reproduction_io.py").read_bytes())
                shared_cache_installed = True
                write_json(receipt_path, receipt)
            exec(compile(text, str(prepared_dir / f"cell_{index:02d}.py"), "exec"), namespace)
            if args.reuse_engine_lists and index == 12:
                if (receipt["engine2_reuse"]["status"] != "copied"
                        or set(namespace.get("ENG", {})) != set(reuse_binding["active_query"]["molecule_ids"])):
                    raise RuntimeError("Engine2 recovery did not load all validated target IDs")
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
    if "te" in namespace:
        processed = set(namespace["te"].molecule_id.astype(str))
        receipt["processed_molecules"] = len(processed)
    if "E004_PREFLIGHT" in namespace:
        receipt["observed_gpu"] = namespace["E004_PREFLIGHT"].get("gpu")
        receipt["input_molecules"] = len(namespace["E004_PREFLIGHT"].get("input_ids", []))
    receipt["outputs"] = [
        {"name": path.name, "bytes": path.stat().st_size, "sha256": digest(path.read_bytes())}
        for path in sorted(work_root.glob("*.csv"))
    ]
    write_json(receipt_path, receipt)
    print(f"LOCAL_RUN_COMPLETE {receipt_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
