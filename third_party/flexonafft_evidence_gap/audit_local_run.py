"""Read existing Flex outputs and audit execution without running any models.

Only --output is written. Missing or ambiguous evidence remains unknown. This
checks local execution health, not leaderboard performance or ranking parity.
"""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
from pathlib import Path
import re


def audit(root: Path) -> dict:
    checks, unreadable = [], {}

    def check(name, status, evidence, *, required=True):
        checks.append(dict(name=name, status=status, required=required, evidence=evidence))

    def read(name):
        path = root / name
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            unreadable[name] = f"{type(exc).__name__}: {exc}"
            return None

    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    run = read("local_reproduction_status.json")
    check("runner_complete", "unknown" if run is None else
          "pass" if run.get("status") == "complete" else
          "fail" if run.get("status") == "failed" else "unknown",
          {k: (run or {}).get(k) for k in
           ("status", "error", "last_completed_cell", "elapsed_seconds", "execution_mode")})

    # Read literal configuration only. Never execute the adapted notebook.
    config = {}
    source = sorted(root.glob("adapted_v*.ipynb"))
    if len(source) == 1:
        try:
            nb = json.loads(source[0].read_text(encoding="utf-8"))
            for cell in nb["cells"]:
                if cell.get("cell_type") != "code":
                    continue
                text = cell["source"]
                tree = ast.parse("".join(text) if isinstance(text, list) else text)
                for node in tree.body:
                    if isinstance(node, ast.Assign):
                        for target in node.targets:
                            if isinstance(target, ast.Name) and target.id in {
                                "VARIANT", "PHYSICAL", "PROVENANCE", "FINAL_LAYER", "FRAG_ON_V2"}:
                                config[target.id] = ast.literal_eval(node.value)
        except (OSError, ValueError, SyntaxError, KeyError) as exc:
            unreadable["adapted_notebook_config"] = str(exc)

    base = read("e004_verification.json")
    execution = read("v43_execution_receipt.json")
    pipeline = read("execution_receipt.json")
    check("frozen_pipeline_complete", "pass" if pipeline is not None else "unknown", pipeline)
    if base is None:
        check("baseline_coverage", "unknown", "e004_verification.json missing or unreadable")
    else:
        expected = base.get("processed_molecules")
        fields = ("base_nonempty", "engine2_nonempty", "pubchem_nonempty")
        complete_fields = isinstance(expected, int) and all(k in base for k in fields)
        # Full-run policy permits empty candidate branches. The visible smoke
        # explicitly asserts nonempty branches for each processed molecule.
        ok = base.get("base_errors") == 0 and complete_fields and (
            base.get("is_full_run") is True or all(base[k] == expected for k in fields))
        check("baseline_coverage", "pass" if ok else "fail" if complete_fields else "unknown",
              {k: base.get(k) for k in ("is_full_run", "processed_molecules", "input_molecules",
               "placeholder_fill_rows", "base_errors", *fields)})
        check("official_metric_rdkit", "pass" if base.get("main_rdkit") == "2026.03.3" else
              "unknown" if "main_rdkit" not in base else "fail", base.get("main_rdkit"))
    if execution is not None:
        check("baseline_final_receipt", "pass" if execution.get("main_errors") == 0 else
              "unknown" if "main_errors" not in execution else "fail",
              {k: execution.get(k) for k in ("main_errors", "processed_molecules", "placeholder_rows")})
    else:
        check("baseline_final_receipt", "unknown", "v43_execution_receipt.json absent")

    for stage in ("ice", "gl", "n1"):
        name = f"{stage}_work/{stage}_out.json.meta.json"
        meta = read(name)
        if meta is None and stage != "n1":
            meta = (base or {}).get("stages", {}).get(stage)
        if meta is None:
            check(f"{stage}_model", "unknown", name + " missing or unreadable")
            continue
        status = meta.get("status")
        errors = meta.get("errors") or []
        failed_counts = any(meta.get(k, 0) for k in ("n_pred_fail", "n_feat_fail"))
        covered, scored = meta.get("n_mols_covered"), meta.get("n_mols_scored")
        uncovered = isinstance(covered, int) and covered > 0 and (
            not isinstance(scored, int) or scored < covered or meta.get("n_scored", 0) <= 0)
        if status == "ok":
            health = "fail" if errors or failed_counts or uncovered else "pass"
            if stage == "n1":
                done = meta.get("n_mols_done")
                if isinstance(done, int) and isinstance(meta.get("n_mols"), int) and done < meta["n_mols"]:
                    health = "fail"
        elif status == "nothing to score":
            health = "allowed_skip"
        elif status == "budget" and (base or {}).get("is_full_run") is True:
            health = "allowed_skip"  # Upstream full-run policy accepts partial budget output.
        elif status in ("error", "failed", "budget"):
            health = "fail"
        else:
            health = "unknown"
        if health == "pass" and not str(meta.get("device", "")).startswith("cuda"):
            health = "unknown"
        if health == "pass" and meta.get("rdkit") != "2025.03.6":
            health = "unknown" if "rdkit" not in meta else "fail"
        if health == "pass" and ("errors" not in meta or "n_pred_fail" not in meta):
            health = "unknown"
        check(f"{stage}_model", health, {k: meta.get(k) for k in (
            "status", "device", "rdkit", "n_mols", "n_mols_done", "n_mols_covered",
            "n_mols_scored", "n_scored", "n_pred_fail", "n_feat_fail", "n_bad_smiles", "errors", "seconds")})

    def neural(name, *, required):
        path = root / name
        errors = read(name + ".errors.json")
        if not path.is_file():
            check(name, "unknown", "Feature file absent; optional-stage skip cannot be inferred from absence.", required=required)
            return
        try:
            import pandas as pd
            frame = pd.read_parquet(path, columns=["molecule_id", "processed", "neural_ok"])
            active = frame[frame.processed.astype(bool)]
            count = int(active.molecule_id.nunique())
            expected = (base or {}).get("processed_molecules")
            ok = bool(active.neural_ok.astype(bool).all()) and (count == expected if required and expected is not None else True)
            outcome = "pass" if ok and errors == [] else "unknown" if errors is None else "fail"
            if not required and outcome == "fail":
                outcome = "allowed_skip"
            check(name, outcome, dict(active_molecules=count, candidate_rows=len(active),
                all_active_neural_ok=bool(active.neural_ok.astype(bool).all()), errors=errors), required=required)
        except (ImportError, OSError, ValueError, KeyError) as exc:
            check(name, "unknown", f"Cannot inspect parquet: {type(exc).__name__}: {exc}", required=required)

    neural("neural_candidate_features.parquet", required=True)
    neural("outsider_neural_features.parquet", required=False)
    consensus = read("variants/consensus_report.json")
    variant = config.get("VARIANT")
    check("selected_consensus_available", "unknown" if consensus is None or variant is None else
          "pass" if variant in consensus else "fail", dict(variant=variant, report=consensus))

    physical = read("spectral_parallax_report.json")
    if config.get("PHYSICAL") is False:
        state = "allowed_skip"
    elif physical is None:
        state = "unknown"
    elif physical.get("error") or physical.get("control_restored"):
        state = "fail"
    elif physical.get("time_budget_exceeded") or "skipped" in str(physical.get("status", "")):
        state = "allowed_skip"
    elif "submission_sha256" in physical:
        state = "pass"
    else:
        state = "unknown"
    check("physical_overlay", state, physical)

    provenance = read("provenance_tournament_report.json")
    check("provenance_overlay", "allowed_skip" if config.get("PROVENANCE") is False else
          "unknown" if provenance is None else "pass" if not provenance.get("error") else "fail",
          dict(configured=config.get("PROVENANCE"), report=provenance), required=config.get("PROVENANCE") is True)

    for name, flag in (("merge_report.json", "FRAG_ON_V2"), ("final_layer_report.json", "FINAL_LAYER")):
        report = read(name)
        enabled = config.get(flag)
        if enabled is False:
            status = "allowed_skip"
        elif report is None:
            status = "unknown"
        elif report.get("status") == "applied":
            status = "pass"
        elif "restored" in str(report.get("status", "")) or report.get("exception") or report.get("restore_error"):
            status = "fail"
        elif "skipped" in str(report.get("status", "")) or report.get("status") == "disabled":
            status = "allowed_skip"
        else:
            status = "unknown"
        check(name, status, report)

    final = root / "submission.csv"
    if final.is_file():
        try:
            with final.open(encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                rows = list(reader)
                header = reader.fieldnames
            ids = [row["molecule_id"] for row in rows]
            ok = header == ["molecule_id", "smiles"] and len(ids) == len(set(ids)) and all(
                1 <= len(parts := row["smiles"].split(";")) <= 25 and len(parts) == len(set(parts)) and all(parts) for row in rows)
            check("final_csv_format", "pass" if ok else "fail", dict(rows=len(rows), sha256=sha(final)))
            report = read("final_layer_report.json")
            expected_sha = (report or {}).get("output_sha256")
            check("final_layer_output_binding", "unknown" if expected_sha is None else
                  "pass" if expected_sha == sha(final) else "fail", dict(recorded=expected_sha, actual=sha(final)))
        except (OSError, KeyError, ValueError, csv.Error) as exc:
            check("final_csv_format", "fail", str(exc))
    else:
        check("final_csv_format", "unknown", "submission.csv absent")

    excerpts = []
    logs = {}
    for name in ("console.log", "submission_pipeline.log", "submission_neural.log", "outsiders.log", "outsiders_neural.log"):
        path = root / name
        if path.is_file():
            logs[name] = path.read_text(encoding="utf-8", errors="replace")
            for line in logs[name].splitlines():
                if any(token in line for token in ("Traceback (most recent call last)", "FAILED ->", "restored_after_error", "NEURAL input failures")):
                    excerpts.append(dict(file=name, line=line[:800]))
    pipeline_log = logs.get("submission_pipeline.log", "")
    external = re.findall(r"external reference spectra: (\d+) added for (\d+) structures", pipeline_log)
    disabled = [line for line in pipeline_log.splitlines() if "external reference spectra disabled:" in line]
    check("external_reference_spectra", "fail" if disabled else
          "pass" if external and external[-1] == ("751", "469") else "fail" if external else "unknown",
          dict(added_and_structures=external, expected=[751, 469], disabled_messages=disabled))
    coverage = []
    for line in pipeline_log.splitlines():
        if line.startswith("N1_CHALLENGER_COVERAGE "):
            try:
                coverage.append(json.loads(line.split(" ", 1)[1]))
            except ValueError:
                pass
    n1_health = (coverage[-1] if coverage else {}).get("health", "")
    check("n1_coverage_policy", "pass" if n1_health.startswith("N1 OK:") else
          "fail" if n1_health.startswith("N1 FAILED:") else "unknown", coverage[-1] if coverage else None)
    failed = [c["name"] for c in checks if c["status"] == "fail"]
    unknown = [c["name"] for c in checks if c["required"] and c["status"] == "unknown"]
    skipped = [c["name"] for c in checks if c["status"] == "allowed_skip"]
    status = "failed" if failed else "unknown" if unknown else "passed_with_allowed_skips" if skipped else "passed"
    return dict(work_root=str(root), status=status, checks=checks, failed_checks=failed,
                required_unknown_checks=unknown, allowed_skips=skipped, config=config,
                unreadable_files=unreadable, diagnostic_log_excerpts=excerpts,
                limitations=["Read-only execution audit; only the requested report is written.",
                    "Missing evidence remains unknown; optional-stage absence alone is not proof of a skip.",
                    "Allowed budget/optional skips can mean partial execution; inspect individual checks.",
                    "This is not upstream ranking parity, independent validation, or a hidden-test score."])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.work_root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("status", "failed_checks", "required_unknown_checks", "allowed_skips")}))


if __name__ == "__main__":
    main()
