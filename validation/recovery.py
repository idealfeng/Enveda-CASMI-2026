"""Conservative recovery of a failed, reference-isolated Flex validation run.

Preserves the failed directory. Output/source bytes are rehashed. Large immutable
assets use recorded download hashes plus size/mtime binding, explicitly not a
fresh full-content rehash. Forward results are reused only for exact inputs.
"""
from __future__ import annotations

import ast
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""): h.update(block)
    return h.hexdigest()


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=True).encode()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8"); temp.replace(path)


def normalized_script(path, old_root, new_root):
    return Path(path).read_text(encoding="utf-8").replace(str(new_root), "<RUN>").replace(str(old_root), "<RUN>")


def bind(prior_root, config):
    old = Path(prior_root).resolve(); new = Path(config["work_root"])
    previous = read(old / "validation_run_receipt.json"); before = read(old / "validation_config.json")
    if old == new or previous.get("status") != "failed" or before.get("pipeline") != "flex":
        raise ValueError("Recovery requires a separate failed Flex directory")
    if canonical(previous["config"]) != canonical(before):
        raise ValueError("Failed run config differs from its saved receipt")
    original_notebook = ROOT / "third_party/flexonafft_evidence_gap/v56/original.ipynb"
    if digest(original_notebook) != previous["source"]["original_notebook_sha256"]:
        raise ValueError("Original Flex V56 source differs from failed run")
    for key in ("manifest_sha256", "reference_mode", "cohort_policy", "active_ids", "processed_molecules", "query_test_sha256", "base_train_rows"):
        if before[key] != config[key]: raise ValueError("Recovery binding differs: " + key)
    if digest(config["manifest"]) != before["manifest_sha256"]:
        raise ValueError("Frozen manifest changed since failed execution")
    for key in ("exclusion_rows_file", "exclusion_keys_file", "queries_file"):
        if digest(before[key]) != digest(config[key]): raise ValueError("Recovery panel artifact changed: " + key)
    # Preserve the exact implementation that produced the old outputs, rather
    # than relying only on an unauditable historical hash string.
    archived = ROOT / "validation/evidence" / ("pipeline_adapter_" + before["implementation_sha256"] + ".py")
    if not archived.is_file() or digest(archived) != before["implementation_sha256"]:
        raise ValueError("Original failed-run adapter source archive is unavailable")
    current = (ROOT / "validation/pipeline_adapter.py").read_text(encoding="utf-8")
    prior = archived.read_text(encoding="utf-8")
    names = {"_exclusions", "_library_mask", "_clean_spectrum_hash", "_query_clean_hashes", "_engine_reps", "install_e1", "install_e2", "record_e1_candidates"}
    def functions(text):
        return {node.name: ast.dump(node, include_attributes=False) for node in ast.parse(text).body
                if isinstance(node, ast.FunctionDef) and node.name in names}
    if functions(prior) != functions(current): raise ValueError("Reference/candidate hook semantics changed since failed run")
    log = (old / "submission_pipeline.log").read_text(encoding="utf-8")
    for cell in (32, 34, 39, 41):
        if f"PIPELINE CELL {cell} DONE" not in log: raise ValueError("Unfinished prerequisite source cell: " + str(cell))
    e2 = read(old / "validation_e2_reference_audit.json")
    if e2.get("status") != "passed" or not e2.get("no_excluded_direct_or_representative_rows"):
        raise ValueError("Prior E2 reference isolation did not pass")
    for filename, field in (("eng_lists.json", "smiles"), ("pc_lists.json", "pc")):
        payload = read(old / filename)
        if set(payload) != set(config["active_ids"]) or any(not isinstance(v.get(field), list) for v in payload.values()):
            raise ValueError("Prior output is incomplete or malformed: " + filename)
    ice = read(old / "ice_work/ice_out.json.meta.json")
    if ice.get("status") != "budget" or ice.get("errors") or ice.get("n_pred_fail", 0) or ice.get("n_bad_smiles", 0):
        raise ValueError("Only a clean ICE budget stop is supported for this recovery")
    files = ["eng_lists.json", "pc_lists.json", "validation_e2_candidates.jsonl", "validation_e2_reference_audit.json",
             "probe_core2.py", "pc_runner.py", "validation_config.json", "validation_run_receipt.json",
             "adapted_validation_flex.ipynb", "p2s_code/frozen_0465.ipynb", "validation_e1_reference_audit.json",
             "ice_work/ice_in.json", "ice_work/ice_out.json", "ice_work/ice_out.json.meta.json",
             "gl_work/gl_in.json", "gl_work/gl_out.json", "gl_work/gl_out.json.meta.json",
             "n1_work/n1_in.json", "n1_work/n1_out.json", "n1_work/n1_out.json.meta.json", "n1_work/glb_driver.py"]
    files += [str(p.relative_to(old)) for p in (old / "eng").glob("*.py")]
    outputs = {name: dict(bytes=(old/name).stat().st_size, sha256=digest(old/name)) for name in sorted(set(files))}
    notebook = read(old/"adapted_validation_flex.ipynb")
    literals = {}
    for cell in notebook["cells"]:
        if cell.get("cell_type") != "code": continue
        text = cell["source"] if isinstance(cell["source"],str) else "".join(cell["source"])
        for node in ast.parse(text).body:
            if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name) and node.targets[0].id in {"FROZEN_SHA256","MODULE_SHA256"}:
                literals[node.targets[0].id] = ast.literal_eval(node.value)
    if digest(old/"p2s_code/frozen_0465.ipynb") != literals["FROZEN_SHA256"]:
        raise ValueError("Failed frozen pipeline differs from its generated outer notebook pin")
    for name, expected in literals["MODULE_SHA256"].items():
        if digest(old/"p2s_code"/name) != expected: raise ValueError("Prior generated module changed: " + name)
        outputs["p2s_code/"+name] = dict(bytes=(old/"p2s_code"/name).stat().st_size,sha256=expected)
    cutoff = (old / "pc_lists.json").stat().st_mtime_ns
    plan = read(ROOT / "third_party/flexonafft_evidence_gap/minimum_download_plan.json")
    assets = []
    for row in plan["files"]:
        path = old / "input_view/datasets" / row["dataset"] / row["file"]
        stat = path.stat()
        if stat.st_mtime_ns > cutoff: raise ValueError("Pinned inference asset was modified after successful source stage: " + str(path))
        receipt_path = path.resolve().with_name(path.name + ".receipt.json")
        download_hash = read(receipt_path).get("sha256") if receipt_path.is_file() else None
        assets.append(dict(path=str(path.resolve()), logical=f"{row['dataset']}/{row['file']}", bytes=stat.st_size, mtime_ns=stat.st_mtime_ns,
                           download_sha256=download_hash, freshly_rehashed=False))
    payload = dict(status="bound", prior_root=str(old), new_root=str(new),
        old_manifest_sha256=before["manifest_sha256"], old_adapter_sha256=before["implementation_sha256"],
        current_reference_hook_ast_equivalent=True, output_files=outputs,
        assets=assets, assets_binding_sha256=canonical(assets),
        limitation="All reused output/source files freshly SHA256 hashed. Inference assets checked by size/mtime and existing download SHA receipts, not freshly fully rehashed; retrospective binding.")
    write(new / "recovery_binding.json", payload)
    return payload


def binding(config_path):
    config = read(config_path); record = read(Path(config["work_root"]) / "recovery_binding.json")
    for item in record["assets"]:
        path = Path(config["work_root"]) / "input_view/datasets" / item["logical"]
        stat = path.stat()
        receipt = path.resolve().with_name(path.name+".receipt.json")
        current_hash = read(receipt).get("sha256") if receipt.is_file() else None
        if (str(path.resolve()),stat.st_size,stat.st_mtime_ns,current_hash) != (item["path"],item["bytes"],item["mtime_ns"],item["download_sha256"]):
            raise ValueError("Current mounted inference asset differs from recovery binding: " + item["logical"])
    return config, record, Path(record["prior_root"])


def checked_copy(record, old, name, destination):
    source = old / name
    if digest(source) != record["output_files"][name]["sha256"]:
        raise ValueError("Reused output changed after binding: " + name)
    destination = Path(destination); destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    if digest(destination) != record["output_files"][name]["sha256"]: raise ValueError("Copy hash mismatch: " + name)


def checked_read(record, old, name):
    if digest(old/name) != record["output_files"][name]["sha256"]:
        raise ValueError("Bound input/output changed: " + name)
    return read(old/name)


def reuse_subprocess(stage, scope, cmd, *args, **kwargs):
    config, record, old = binding(scope["_VALIDATION_CONFIG"]); new = Path(config["work_root"])
    filenames = {"engine2": ["eng_lists.json", "validation_e2_candidates.jsonl", "validation_e2_reference_audit.json"],
                 "pubchem": ["pc_lists.json"]}[stage]
    scripts = ["eng/eng_runner.py", "eng/casmi_engine.py", "eng/pv.py", "eng/pv_fp.py"] if stage == "engine2" else ["pc_runner.py", "probe_core2.py"]
    for script in scripts:
        if normalized_script(old/script, old, new) != normalized_script(new/script, old, new):
            raise ValueError("Generated stage source differs beyond output paths: " + script)
    for name in filenames: checked_copy(record, old, name, new/name)
    write(new / ("recovery_" + stage + ".json"), dict(status="reused", prior_root=str(old), output_sha256={name:digest(new/name) for name in filenames}, current_gpu_work=False))
    print("VALIDATION_RECOVERY_REUSED", stage, flush=True)
    return subprocess.CompletedProcess(cmd, 0, stdout="Validated prior " + stage + " output reused\n", stderr="")


def inputs_equal(first, second):
    # Jobs are independent by molecule; preserve spectra/candidate order within
    # each molecule while allowing the outer priority order to change.
    def mapping(items):
        result = {str(item["mid"]): item for item in items}
        if len(result) != len(items): raise ValueError("Repeated forward-model molecule ID")
        return result
    return canonical(mapping(first)) == canonical(mapping(second))


def complete_gl_output(items, output):
    if set(output) != {str(item["mid"]) for item in items}: return False
    for item in items:
        values = output[str(item["mid"])]
        if set(values) != set(item["cands"]): return False
        if any(not isinstance(value,(int,float)) or not math.isfinite(value) for value in values.values()): return False
    return True


def complete_n1_output(items, output, meta):
    if meta.get("fake") is not False or set(output) != {str(item["mid"]) for item in items}: return False
    covered = 0
    for item in items:
        value = output[str(item["mid"])]
        if value.get("cands") != item["cands"]: return False
        spectra = {str(s["sid"]) for s in item["spectra"]}
        if not set(value.get("spec",{})) <= spectra: return False
        for record in value.get("spec",{}).values():
            covered += 1
            for name in ("mean","merged"):
                values = record.get(name)
                if not isinstance(values,list) or len(values)!=len(item["cands"]): return False
                if any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in values): return False
    return covered == meta.get("n_spec_covered")


def run_ice(original, pkg, items, **kwargs):
    root = Path(kwargs["workdir"]).parent
    config, record, old = binding(root / "validation_config.json")
    old_input = read(old/"ice_work/ice_in.json"); old_out = read(old/"ice_work/ice_out.json")
    meta = read(old/"ice_work/ice_out.json.meta.json")
    for name in ("ice_work/ice_in.json", "ice_work/ice_out.json", "ice_work/ice_out.json.meta.json"):
        if digest(old/name) != record["output_files"][name]["sha256"]: raise ValueError("Prior ICE artifact changed")
    old_items = {str(item["mid"]): item for item in old_input}
    completed = {}
    for mid, values in old_out.items():
        expected = set(old_items[mid]["cands"])
        if set(values) == expected and expected and all(isinstance(v, (int,float)) and math.isfinite(v) for v in values.values()):
            completed[mid] = values
    if len(completed) != meta["n_mols_scored"] or sum(map(len, completed.values())) != meta["n_scored"]:
        raise ValueError("Prior ICE complete-molecule evidence disagrees with atomic checkpoint counts")
    reused = {str(item["mid"]): completed[str(item["mid"])] for item in items
              if str(item["mid"]) in completed and canonical(item) == canonical(old_items[str(item["mid"])] )}
    pending = [item for item in items if str(item["mid"]) not in reused]
    work = Path(kwargs["workdir"]); work.mkdir(parents=True, exist_ok=True)
    pending_kwargs = dict(kwargs, workdir=str(root / "ice_recovery_pending"))
    start = time.monotonic()
    output = original(pkg, pending, **pending_kwargs)
    fresh = read(root / "ice_recovery_pending/ice_out.json.meta.json")
    if fresh.get("status") != "ok" or fresh.get("errors") or fresh.get("n_pred_fail", 0) or fresh.get("n_bad_smiles", 0) or fresh["n_mols_scored"] != fresh["n_mols_covered"]:
        raise RuntimeError("Recovery ICE remains incomplete: " + json.dumps(fresh))
    merged = {str(item["mid"]): reused.get(str(item["mid"]), output.get(str(item["mid"]), {})) for item in items}
    if any(set(merged[str(item["mid"])]) != set(item["cands"]) for item in items):
        raise ValueError("Merged ICE candidates do not exactly match rebuilt inputs")
    if any(value is not None and (not isinstance(value,(int,float)) or not math.isfinite(value)) for values in merged.values() for value in values.values()):
        raise ValueError("Merged ICE contains nonfinite scores")
    finite_groups = 0
    for item in items:
        values = list(merged[str(item["mid"])].values())
        if values and all(value is not None for value in values):
            finite_groups += 1
        elif all(value is None for value in values) and not item["spectra"]:
            pass  # build_ice_input's covered-only filter left no supported spectrum.
        else:
            raise ValueError("ICE molecule has partial scores or unexplained unsupported coverage: " + str(item["mid"]))
    if finite_groups != len(reused)+fresh["n_mols_scored"]:
        raise ValueError("Merged complete ICE groups disagree with covered/scored counts")
    combined = dict(fresh, status="ok", n_mols=len(items), n_mols_covered=len(reused)+fresh["n_mols_covered"],
        n_mols_scored=len(reused)+fresh["n_mols_scored"], n_cands=sum(len(v) for v in merged.values()),
        n_scored=sum(sum(v is not None for v in values.values()) for values in merged.values()),
        seconds=round(meta["seconds"] + fresh["seconds"], 2),
        recovery=dict(prior_status="budget", old_complete_molecules=len(completed), reused_molecules=len(reused),
            rebuilt_or_pending_molecules=len(pending), newly_scored_molecules=fresh["n_mols_scored"],
            prior_seconds=meta["seconds"], current_seconds=round(time.monotonic()-start,2),
            declared_budget=config["ice_budget_seconds"], prior_output_sha256=record["output_files"]["ice_work/ice_out.json"]["sha256"],
            prior_budget_seconds=read(old/"validation_config.json")["ice_budget_seconds"],
            new_pending_budget_seconds=config["ice_budget_seconds"],
            cumulative_seconds=round(meta["seconds"]+fresh["seconds"],2),
            cumulative_exceeds_new_pending_budget=meta["seconds"]+fresh["seconds"]>config["ice_budget_seconds"],
            cold_start_budget_feasibility="not established", not_a_cold_run=True, source_chunk_atomicity_checked=True))
    write(work/"ice_in.json", items); write(work/"ice_out.json", merged); write(work/"ice_out.json.meta.json", combined)
    write(root/"recovery_ice.json", combined["recovery"])
    print("VALIDATION_RECOVERY_ICE", json.dumps(combined["recovery"]), flush=True)
    return merged


def assert_ice_complete(work_root):
    """Fail outside the upstream catch block before starting GL/N1."""
    meta = read(Path(work_root) / "ice_work/ice_out.json.meta.json")
    if meta.get("status") != "ok" or meta.get("errors") or meta.get("n_pred_fail",0) or meta.get("n_mols_scored") != meta.get("n_mols_covered"):
        raise RuntimeError("ICE validation incomplete; refusing GL/N1 work: " + json.dumps(meta))


def run_gl(original, pkg, items, **kwargs):
    root = Path(kwargs["workdir"]).parent; config, record, old = binding(root / "validation_config.json")
    meta = checked_read(record,old,"gl_work/gl_out.json.meta.json")
    valid = meta.get("status") == "ok" and not meta.get("errors") and not meta.get("n_pred_fail",0) and not meta.get("n_feat_fail",0) and meta.get("n_mols_scored") == meta.get("n_mols_covered")
    old_output = checked_read(record,old,"gl_work/gl_out.json")
    if valid and inputs_equal(items, checked_read(record,old,"gl_work/gl_in.json")) and complete_gl_output(items,old_output):
        for name in ("gl_work/gl_out.json", "gl_work/gl_out.json.meta.json"): checked_copy(record, old, name, root/name)
        write(root/"gl_work/gl_in.json", items)
        write(root/"recovery_gl.json", dict(status="reused", exact_per_molecule_inputs=True, prior_root=str(old), output_sha256=digest(root/"gl_work/gl_out.json")))
        print("VALIDATION_RECOVERY_REUSED GL", flush=True)
        return read(root/"gl_work/gl_out.json")
    write(root/"recovery_gl.json", dict(status="recomputed", reason="Prior input/health not exactly reusable"))
    return original(pkg, items, **kwargs)


def n1_subprocess(scope, cmd, *args, **kwargs):
    config, record, old = binding(scope["_VALIDATION_CONFIG"]); root = Path(config["work_root"])
    meta = checked_read(record,old,"n1_work/n1_out.json.meta.json")
    valid = meta.get("status") == "ok" and not meta.get("errors") and not meta.get("n_pred_fail",0) and not meta.get("n_feat_fail",0) and meta.get("n_mols_done") == meta.get("n_mols")
    script_same = digest(root/"n1_work/glb_driver.py") == record["output_files"]["n1_work/glb_driver.py"]["sha256"]
    new_items = read(root/"n1_work/n1_in.json")
    old_output = checked_read(record,old,"n1_work/n1_out.json")
    if valid and script_same and inputs_equal(new_items, checked_read(record,old,"n1_work/n1_in.json")) and complete_n1_output(new_items,old_output,meta):
        for name in ("n1_work/n1_out.json", "n1_work/n1_out.json.meta.json"): checked_copy(record, old, name, root/name)
        write(root/"recovery_n1.json", dict(status="reused", exact_per_molecule_inputs=True, prior_root=str(old)))
        return subprocess.CompletedProcess(cmd, 0, stdout="Validated prior N1 output reused\n", stderr="")
    write(root/"recovery_n1.json", dict(status="recomputed", reason="Prior input/health/source not exactly reusable"))
    return subprocess.run(cmd, *args, **kwargs)


def patch_cell(text, config_path):
    config = read(config_path)
    if not config.get("resume_from"): return text, []
    changes = []
    if "ENG_FILES = " in text or "PC = {}" in text and "pc_runner.py" in text:
        stage = "engine2" if "ENG_FILES = " in text else "pubchem"
        tree = ast.parse(text)
        calls = [n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
                 and isinstance(n.func.value,ast.Name) and n.func.value.id=="subprocess" and n.func.attr=="run"]
        # Calls within literal embedded scripts are not AST nodes here.
        if len(calls) != 1: raise ValueError("Unexpected stage subprocess calls for " + stage)
        before = ast.get_source_segment(text,calls[0]); after = before.replace("subprocess.run(", f"_validation_recovery.reuse_subprocess({stage!r}, globals(), ",1)
        text=text.replace(before,after,1); changes.append("hash_bound_"+stage+"_reuse")
    if "GL_SCORES, gl_stats, GL_LAM, GL_BUDGET = " in text:
        text=text.replace("ice_fuse.run_ice(ICE_PKG, items,", "_validation_recovery.run_ice(ice_fuse.run_ice, ICE_PKG, items,",1)
        text=text.replace("gl_fuse.run_gl(GL_PKG, gl_items,", "_validation_recovery.run_gl(gl_fuse.run_gl, GL_PKG, gl_items,",1)
        tree=ast.parse(text)
        function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="n1_run")
        call=next(n for n in ast.walk(function) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Name) and n.func.value.id=="subprocess" and n.func.attr=="run")
        before=ast.get_source_segment(text,call);after=before.replace("subprocess.run(","_validation_recovery.n1_subprocess(globals(), ",1)
        text=text.replace(before,after,1);changes.append("exact_input_partial_ice_and_gl_n1_recovery")
    if changes:
        text=(f"import sys as _recovery_sys\n_recovery_sys.path.insert(0, {str(ROOT)!r})\n"
              "from validation import recovery as _validation_recovery\n")+text
    ast.parse(text)
    return text,changes
