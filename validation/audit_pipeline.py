"""Read a completed validation pipeline's stage reports; never run models."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def audit(root):
    spec = importlib.util.spec_from_file_location("read_flex_audit", ROOT / "third_party/flexonafft_evidence_gap/audit_local_run.py")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    result = module.audit(root)
    receipt = json.loads((root / "validation_run_receipt.json").read_text())
    config = receipt["config"]
    by_name = {item["name"]: item for item in result["checks"]}
    by_name["runner_complete"].update(status="pass" if receipt["status"] == "complete" else
        "fail" if receipt["status"] == "failed" else "unknown",
        evidence={key: receipt.get(key) for key in ("status", "elapsed_seconds", "traceback")})
    # Visible-smoke source required nonempty channels for its particular 12
    # examples. Here retrieval misses are data and never execution failures.
    base = json.loads((root / "e004_verification.json").read_text())
    baseline_ok = base.get("base_errors") == 0 and base.get("processed_molecules") == config["processed_molecules"]
    by_name["baseline_coverage"].update(status="pass" if baseline_ok else "fail",
        evidence={key: base.get(key) for key in ("processed_molecules", "base_errors", "base_nonempty", "engine2_nonempty", "pubchem_nonempty")})
    result["checks"].append(dict(name="actual_query_cohort", required=True,
        status="pass" if set(base.get("processed_ids", [])) == set(config["active_ids"]) and base.get("placeholder_fill_rows") == 0 else "fail",
        evidence=dict(processed=base.get("processed_molecules"), placeholder_rows=base.get("placeholder_fill_rows"),
                      cohort_policy=config["cohort_policy"])))
    for name in ("validation_e1_reference_audit.json", "validation_e2_reference_audit.json"):
        value = json.loads((root / name).read_text())
        good = value.get("status") in ("passed", "installed")
        if name.startswith("validation_e2"):
            good = good and value.get("no_excluded_direct_or_representative_rows") and value.get("candidate_pool_filtered") is False
        else:
            good = good and bool(value.get("libraries")) and all(item.get("csr_offsets_preserved") for item in value.get("libraries", []))
        result["checks"].append(dict(name=name, required=True, status="pass" if good else "fail", evidence=value))
    for name in ("neural_candidate_features.parquet", "outsider_neural_features.parquet"):
        import pandas as pd
        errors_file = Path(str(root / name) + ".errors.json")
        errors = json.loads(errors_file.read_text()) if errors_file.exists() else None
        if (root / name).is_file():
            frame = pd.read_parquet(root / name)
            active = frame[frame.processed.astype(bool)] if "processed" in frame else frame
            good = errors == [] and bool(active.neural_ok.astype(bool).all())
            empty_path = root / "validation_empty_candidate_audit.json"
            empty_audit = json.loads(empty_path.read_text()) if empty_path.exists() else {}
            known_empty = {item["molecule_id"] for item in empty_audit.get("rows", [])
                           if item.get("query_processed") and item.get("all_materialized_sources_empty")}
            expected_cohort = set(config["active_ids"]) - known_empty
            if name == "neural_candidate_features.parquet":
                good = good and expected_cohort <= set(active.molecule_id.astype(str))
            result["checks"].append(dict(name="validation_full_coverage_" + name, required=True,
                status="pass" if good else "fail", evidence=dict(errors=errors,
                    active_molecules=int(active.molecule_id.nunique()), active_candidates=len(active),
                    all_active_neural_ok=bool(active.neural_ok.astype(bool).all()),
                    expected_nonempty_query_molecules=len(expected_cohort), known_retrieval_miss_queries=sorted(known_empty),
                    cco_fallback_is_not_retrieval_evidence=True)))
        else:
            result["checks"].append(dict(name="validation_full_coverage_" + name, required=True,
                status="unknown", evidence="Materialized neural features absent"))
    for name in ("spectral_parallax_report.json", "merge_report.json", "final_layer_report.json"):
        value = json.loads((root / name).read_text())
        result.setdefault("complete_layer_reports", {})[name] = value
    final_hash = hashlib.sha256((root / "submission.csv").read_bytes()).hexdigest()
    final_report = result["complete_layer_reports"]["final_layer_report.json"]
    physical = result["complete_layer_reports"]["spectral_parallax_report.json"]
    merge = result["complete_layer_reports"]["merge_report.json"]
    result["checks"].append(dict(name="physical_merge_hash_binding", required=True,
        status="pass" if physical.get("submission_sha256") == merge.get("input_sha256", {}).get("physical_v2") else "fail",
        evidence=dict(physical_output=physical.get("submission_sha256"), merge_input=merge.get("input_sha256", {}).get("physical_v2"))))
    result["checks"].append(dict(name="merge_final_hash_binding", required=True,
        status="pass" if merge.get("output_sha256") == final_report.get("input_sha256") else "fail",
        evidence=dict(merge_output=merge.get("output_sha256"), final_input=final_report.get("input_sha256"))))
    result["final_sha256"] = final_hash
    result["explicit_budgets_seconds"] = {key: config[key] for key in ("ice_budget_seconds", "gl_budget_seconds", "n1_budget_seconds")}
    result["evaluation_label"] = config["evaluation_label"]
    result["pretrained_exposure"] = config["pretrained_exposure"]
    if config.get("resume_from"):
        result["recovery"] = {path.stem: json.loads(path.read_text())
                              for path in root.glob("recovery_*.json") if path.name != "recovery_binding.json"}
        ice_meta = json.loads((root/"ice_work/ice_out.json.meta.json").read_text())
        result["recovery"]["ice_meta_performance_scope"] = {
            "seconds": "cumulative prior budget-attempt plus current pending invocation",
            "n_pred_t_pred_t_load_pred_per_s": "current pending invocation only",
            "coverage_and_n_scored": "merged complete prior groups plus current pending output",
            "original_attempt_status": "budget", "cold_run_performance_claimed": False,
            "merged_recovery": ice_meta.get("recovery")}
    result["failed_checks"] = [item["name"] for item in result["checks"] if item["status"] == "fail"]
    result["required_unknown_checks"] = [item["name"] for item in result["checks"] if item["required"] and item["status"] == "unknown"]
    result["allowed_skips"] = [item["name"] for item in result["checks"] if item["status"] == "allowed_skip"]
    result["status"] = "failed" if result["failed_checks"] else "unknown" if result["required_unknown_checks"] else "passed_with_allowed_skips" if result["allowed_skips"] else "passed"
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.work_root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("status", "failed_checks", "required_unknown_checks", "allowed_skips")}))
