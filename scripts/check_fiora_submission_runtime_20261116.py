"""Real, label-free runtime-to-CSV checks; this does not rerun the champion."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import sys


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def function_ast(path, name):
    node = next(node for node in ast.parse(path.read_text(encoding="utf-8")).body
                if isinstance(node, ast.FunctionDef) and node.name == name)
    return ast.dump(node, include_attributes=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset-manifest-sha", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    import fiora_submission_runtime_20261116 as runtime
    bundle = root / "submission/optimization_20261116/fiora_payload"
    runtime_path = root / "scripts/fiora_submission_runtime_20261116.py"
    out = root / "runs/fiora_submission_canary_20261116/runtime_checks"
    out.mkdir(parents=True, exist_ok=False)
    contracts = {
        "spectral_score_ast_identical": function_ast(runtime_path, "spectral_score") == function_ast(root / "scripts/score_fiora_candidate_pilot_20261115.py", "spectral_score"),
        "mass_map_ast_identical": function_ast(runtime_path, "compiled_mass_map") == function_ast(root / "scripts/prepare_fiora_tims_pilot_20261115.py", "compiled_mass_map"),
    }
    if not all(contracts.values()):
        raise ValueError("Actual native scorer functions changed")
    checks = {}
    cases = [
        ("label_free_dev2", bundle / "canary_submission.csv", bundle / "canary_queries.parquet"),
        ("existing_production2", root / "runs/generation_production_20261113_r2/kaggle/working/submission.csv",
         root / "runs/generation_production_20261113_r2/kaggle/working/effective_query_spectra.parquet"),
    ]
    for name, submission, queries in cases:
        sys.argv = [str(runtime_path), "--submission", str(submission), "--queries", str(queries),
            "--asset-root", str(bundle), "--asset-manifest-sha", args.asset_manifest_sha,
            "--output-dir", str(out / name), "--device", "cuda", "--mode", "full"]
        runtime.main()
        audit = json.loads((out / name / "runtime_audit.json").read_text())
        if audit["status"] != "passed" or not all(audit["checks"].values()) or not audit["model_loaded"]:
            raise ValueError("Real runtime audit failed: " + name)
        if name == "label_free_dev2" and (not audit["model_invoked"] or audit["scored_queries"] < 1 or audit["scored_candidate_rows"] < 1):
            raise ValueError("Dev canary did not actually consume any model scores")
        checks[name] = {key: audit[key] for key in ("rows", "supported_queries", "scored_queries", "scored_candidate_rows", "actual_forward_calls", "candidate_failure_queries",
            "changed_queries", "changed_top1", "reason_counts", "elapsed_seconds", "host_peak_mib", "gpu_peak_allocated_mib")}
        checks[name]["audit_sha256"] = sha(out / name / "runtime_audit.json")
    # Exact static copy is a distinct path; never count it as actual model inference.
    sys.argv = [str(runtime_path), "--submission", str(bundle / "canary_submission.csv"), "--output-dir", str(out / "static"), "--mode", "static"]
    runtime.main()
    static = json.loads((out / "static/runtime_audit.json").read_text())
    if static["model_invoked"] or static["input_sha256"] != static["output_sha256"]:
        raise ValueError("Static mode is not an exact original copy")
    receipt = dict(status="passed_real_component_runtime_to_csv", script_sha256=sha(runtime_path),
        asset_manifest_sha256=args.asset_manifest_sha, contracts=contracts, cases=checks,
        static_model_not_invoked=True, static_original_bytes_exact=True, labels_read=False,
        full_champion_initialization_rerun=False, kaggle_hidden_success=False, public_score=None,
        boundary="Actual model/runtime/CSV checks on fixed dev2 plus existing production2 outputs; not new full champion initialization or efficacy proof")
    (out / "verification.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt), flush=True)


if __name__ == "__main__":
    main()
