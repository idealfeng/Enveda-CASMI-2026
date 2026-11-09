"""Validate and copy a frozen public notebook's Engine2 output into a recovery run.

Original runs did not snapshot every input at Engine2 completion. Recovery binds
their immutable inputs retrospectively: resolved files, sizes, mtimes, downloaded
hash receipts, and payload mtimes preceding the successful output. This limitation
is recorded explicitly, rather than claiming a historical full-file rehash.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess


def sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


def sha_file(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def canonical_hash(value):
    return sha_bytes(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def query_fingerprint(frame):
    import pyarrow as pa
    # Preserve row order, column values/types and the pandas index. Remove package
    # bookkeeping metadata so the semantic content, not a Parquet encoder, binds it.
    table = pa.Table.from_pandas(frame, preserve_index=True).combine_chunks().replace_schema_metadata(None)
    sink = pa.BufferOutputStream()
    with pa.ipc.new_stream(sink, table.schema) as writer:
        writer.write_table(table)
    return {"sha256": sha_bytes(sink.getvalue().to_pybytes()), "rows": len(frame),
            "molecule_ids": sorted(set(frame.molecule_id.astype(str))),
            "columns": list(frame.columns), "arrow_schema": str(table.schema)}


def projected_query(competition_root):
    """Source cell10's data-only selection, for prepare-only validation."""
    import pandas as pd
    frame = pd.read_parquet(Path(competition_root) / "test.parquet")
    signature = hashlib.md5(",".join(sorted(frame.spectrum_id.astype(str))).encode()).hexdigest()
    rerun = bool(os.getenv("KAGGLE_IS_COMPETITION_RERUN")) or signature != "654e030e4173780e945252b4a5adf70b"
    if not rerun:
        keep = sorted(frame.molecule_id.unique())[:12]
        frame = frame[frame.molecule_id.isin(keep)]
    return frame


def file_metadata(path, logical_name):
    path = Path(path)
    info = path.stat()
    receipt_path = path.with_name(path.name + ".receipt.json")
    saved_hash = None
    if receipt_path.is_file():
        saved_hash = json.loads(receipt_path.read_text(encoding="utf-8")).get("sha256")
    return {"name": logical_name, "resolved_path": str(path.resolve()), "bytes": info.st_size,
            "mtime_ns": info.st_mtime_ns, "download_receipt_sha256": saved_hash}


def input_metadata(input_root):
    root = Path(input_root).resolve()
    result = []
    for directory, names, filenames in os.walk(root, followlinks=True):
        names[:] = sorted(name for name in names
                          if name != "__pycache__" and not name.endswith(".ranges"))
        for name in sorted(filenames):
            if (name == "input_receipt.json" or name.endswith((".receipt.json", ".part", ".tmp", ".pyc", ".pyo", ".range.lock"))):
                continue
            path = Path(directory) / name
            if path.is_file():
                result.append(file_metadata(path, path.relative_to(root).as_posix()))
    if not result:
        raise ValueError("Engine2 reuse input view is empty")
    return sorted(result, key=lambda item: item["name"])


def competition_metadata(root):
    return [file_metadata(Path(root) / name, name)
            for name in ("train.parquet", "test.parquet", "sample_submission.csv")]


def validate_generated_source(old_root, prior_receipt, source_notebook, engine_cell=12):
    old_adapted = old_root / f"adapted_cells/cell_{engine_cell:02d}.py"
    patch = next(item for item in prior_receipt["patches"] if item["cell"] == engine_cell)
    original = source_notebook["cells"][engine_cell]["source"]
    original = "".join(original) if isinstance(original, list) else original
    if sha_bytes(original.encode()) != patch["source_sha256"]:
        raise ValueError("Prior Engine2 cell does not descend from the frozen source")
    text = old_adapted.read_text(encoding="utf-8")
    if sha_bytes(text.encode()) != patch["adapted_sha256"]:
        raise ValueError("Prior adapted Engine2 cell differs from its run receipt")
    tree = ast.parse(text)
    files = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "ENG_FILES" for t in node.targets):
            files = ast.literal_eval(node.value)
    if not isinstance(files, dict) or "casmi_engine.py" not in files:
        raise ValueError("Prior Engine2 literal source dictionary is missing")
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "write" and node.args
                and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
            if "eng_runner.py" in ast.unparse(node.func.value):
                files["eng_runner.py"] = node.args[0].value
    if "eng_runner.py" not in files:
        raise ValueError("Prior Engine2 runner source is missing")
    checks = []
    for name, expected in sorted(files.items()):
        if Path(name).name != name:
            raise ValueError("Unexpected embedded-source filename")
        path = old_root / "eng" / name
        expected_hash = sha_bytes(expected.encode())
        if not path.is_file() or sha_file(path) != expected_hash:
            raise ValueError(f"Prior generated Engine2 source differs: {name}")
        checks.append({"name": name, "sha256": expected_hash})
    return checks


def validate_reuse(prior_lists, current_input_root, current_competition_root,
                   source_notebook, expected_source_sha256, current_frame=None,
                   notebook_version=43, engine_cell=12):
    import pandas as pd
    prior_lists = Path(prior_lists).resolve()
    old_root = prior_lists.parent
    prior_receipt_path = old_root / "local_run_receipt.json"
    raw_receipt = prior_receipt_path.read_bytes()
    prior = json.loads(raw_receipt)
    if prior.get("source_sha256") != expected_source_sha256 or prior.get("notebook_version") != notebook_version:
        raise ValueError("Prior output is not bound to this exact notebook/version")
    if Path(prior["runtime"]["work_root"]).resolve() != old_root or prior_lists.name != "eng_lists.json":
        raise ValueError("Prior output is outside its recorded run work directory")
    if (prior["runtime"].get("python") is not None
            and prior["runtime"].get("python") != platform.python_version()):
        raise ValueError("Python version differs from the successful prior Engine2 run")
    if not any(item.get("cell") == engine_cell and item.get("status") == "complete"
               for item in prior.get("cell_results", [])):
        raise ValueError("Prior run has no successful Engine2 cell")
    generated_sources = validate_generated_source(old_root, prior, source_notebook, engine_cell)
    raw_lists = prior_lists.read_bytes()
    lists = json.loads(raw_lists)
    if not isinstance(lists, dict) or not lists:
        raise ValueError("Prior Engine2 candidate output is empty")
    old_query_path = old_root / "smoke_comp/test.parquet"
    if not old_query_path.is_file():
        old_query_path = Path(prior["runtime"]["competition_root"]) / "test.parquet"
    old_query = query_fingerprint(pd.read_parquet(old_query_path))
    if current_frame is None:
        current_frame = projected_query(current_competition_root)
    current_query = query_fingerprint(current_frame)
    if old_query != current_query:
        raise ValueError("Engine2 reuse query content, order, metadata or target IDs differ")
    if set(lists) != set(current_query["molecule_ids"]):
        raise ValueError("Engine2 candidate target IDs differ from the active query IDs")
    for molecule_id, row in lists.items():
        smiles, keys = row.get("smiles"), row.get("keys")
        if (not isinstance(smiles, list) or not smiles or not isinstance(keys, list)
                or len(smiles) != len(keys) or not all(isinstance(s, str) and s for s in smiles + keys)):
            raise ValueError(f"Invalid prior Engine2 candidate row: {molecule_id}")
    prior_input_root = prior["runtime"].get("input_view") or prior["runtime"]["input_root"]
    old_inputs = input_metadata(prior_input_root)
    current_inputs = (old_inputs if Path(prior_input_root).resolve() == Path(current_input_root).resolve()
                      else input_metadata(current_input_root))
    if old_inputs != current_inputs:
        raise ValueError("Full attached input-file metadata differs from the prior run")
    old_competition = competition_metadata(prior["runtime"]["competition_root"])
    current_competition = competition_metadata(current_competition_root)
    if old_competition != current_competition:
        raise ValueError("Full competition-file metadata differs from the prior run")
    cutoff = prior_lists.stat().st_mtime_ns
    newer = [item["name"] for item in old_inputs + old_competition if item["mtime_ns"] > cutoff]
    if newer:
        raise ValueError(f"Inputs changed after prior Engine2 output was written: {newer[:5]}")
    payload = {
        "version": 1, "state": "validated", "prior_lists": str(prior_lists),
        "prior_lists_sha256": sha_bytes(raw_lists), "prior_lists_bytes": len(raw_lists),
        "prior_receipt": str(prior_receipt_path), "prior_receipt_sha256": sha_bytes(raw_receipt),
        "source_sha256": expected_source_sha256, "prior_generated_source_hashes": generated_sources,
        "notebook_version": notebook_version, "engine_cell": engine_cell,
        "active_query": current_query, "prior_query_file": str(old_query_path),
        "input_root": str(Path(current_input_root).resolve()), "input_files": current_inputs,
        "competition_root": str(Path(current_competition_root).resolve()),
        "competition_files": current_competition, "input_metadata_sha256": canonical_hash(current_inputs),
        "competition_metadata_sha256": canonical_hash(current_competition),
        "molecules": len(lists), "candidate_counts": {mid: len(row["smiles"]) for mid, row in lists.items()},
        "not_cold_start": True,
        "limitations": [
            "Prior source run did not snapshot input metadata at Engine2 completion; binding is retrospective.",
            "Requires current input payload mtimes to precede prior output and identical resolved-file metadata.",
            "Downloaded content hashes are recorded from download receipts; large inputs are not rehashed here.",
            "Only Engine2 candidates are reused. Subsequent stages and their failure checks execute normally.",
        ],
    }
    payload["binding_sha256"] = canonical_hash(payload)
    return payload


def copy_reused_lists(binding, scope, work_root):
    import pandas as pd
    prior_lists = Path(binding["prior_lists"])
    if sha_file(binding["prior_receipt"]) != binding["prior_receipt_sha256"]:
        raise ValueError("Prior run receipt changed after reuse validation")
    if sha_file(prior_lists) != binding["prior_lists_sha256"]:
        raise ValueError("Prior Engine2 output changed after reuse validation")
    query = query_fingerprint(pd.read_parquet(Path(scope["COMP"]) / "test.parquet"))
    if query != binding["active_query"]:
        raise ValueError("Actual cell12 query differs from the validated recovery query")
    if canonical_hash(input_metadata(binding["input_root"])) != binding["input_metadata_sha256"]:
        raise ValueError("Attached input-file metadata changed before Engine2 reuse")
    if canonical_hash(competition_metadata(binding["competition_root"])) != binding["competition_metadata_sha256"]:
        raise ValueError("Competition input-file metadata changed before Engine2 reuse")
    destination = Path(work_root) / "eng_lists.json"
    if destination.exists() and sha_file(destination) != binding["prior_lists_sha256"]:
        raise FileExistsError("New work root already has a different Engine2 candidate output")
    destination.write_bytes(prior_lists.read_bytes())
    if sha_file(destination) != binding["prior_lists_sha256"]:
        raise ValueError("Copied Engine2 output hash mismatch")
    message = json.dumps({"ENGINE2_REUSED": True, "from": str(prior_lists),
                          "molecules": binding["molecules"], "not_cold_start": True}) + "\n"
    return subprocess.CompletedProcess(args=["reuse-engine-lists", str(prior_lists)], returncode=0,
                                       stdout=message, stderr="")
