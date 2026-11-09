"""Evaluate frozen molecule-level CASMI predictions and paired ablations.

Run: python -m validation.evaluate --truth truth.csv --predictions pred.csv
     --baseline control.csv --require-fixed-candidates --output report.json

Truth schema: molecule_id,identity,normalized_smiles (optional strata columns).
Candidate audit schema: molecule_id,candidate_smiles, with the pre-ranking union
joined by semicolons; an empty value explicitly records an empty candidate pool.
Without this artifact, pre-ranking recall and recall/ranking loss are unknown.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

import numpy as np
import pandas as pd

from . import metric


def _required(frame: pd.DataFrame, columns: list[str], name: str) -> None:
    if not set(columns).issubset(frame.columns):
        raise ValueError(f"{name} requires columns {columns}")
    if frame.empty or frame[columns].isna().any().any():
        raise ValueError(f"{name} is empty or contains null required values")
    if frame.molecule_id.astype(str).str.strip().eq("").any() or frame.molecule_id.duplicated().any():
        raise ValueError(f"{name} molecule_id must be nonempty and unique")


def validate_truth(truth: pd.DataFrame) -> pd.DataFrame:
    metric.assert_official_rdkit()
    result = truth.copy()
    for alias, canonical in (("official_identity", "identity"), ("smiles", "normalized_smiles"), ("query_source", "source")):
        if alias in result.columns:
            if canonical in result.columns and not result[alias].equals(result[canonical]):
                raise ValueError(f"Conflicting truth aliases: {alias} and {canonical}")
            if canonical not in result.columns:
                result[canonical] = result[alias]
    _required(result, ["molecule_id", "identity", "normalized_smiles"], "Truth")
    for row in result.itertuples(index=False):
        if not re.fullmatch(r"[A-Z]{14}", row.identity) or metric.identity(row.normalized_smiles) != row.identity:
            raise ValueError(f"Truth identity does not match normalized_smiles: {row.molecule_id}")
    return result


def _summary(rows: list[dict]) -> dict:
    n = len(rows)
    return {"molecules": n, **{key: float(np.mean([r[key] for r in rows])) if n else None
                               for key in ("mrr_at_25", "top1", "top5", "top25")}}


def evaluate_frames(truth: pd.DataFrame, predictions: pd.DataFrame) -> dict:
    truth = validate_truth(truth)
    _required(predictions, ["molecule_id", "smiles"], "Predictions")
    truth_ids, prediction_ids = set(truth.molecule_id), set(predictions.molecule_id)
    if truth_ids != prediction_ids:
        raise ValueError(f"Prediction IDs differ from truth: missing={sorted(truth_ids-prediction_ids)[:5]}, extra={sorted(prediction_ids-truth_ids)[:5]}")
    by_id = predictions.set_index("molecule_id").smiles.to_dict()
    rows = []
    for item in truth.to_dict("records"):
        mid = item["molecule_id"]
        guesses = metric.parse_guesses(by_id[mid])
        keys = [metric.identity(s) for s in guesses]
        rank = next((i for i, key in enumerate(keys, 1) if key == item["identity"]), None)
        formula = metric.molecular_formula(item["normalized_smiles"])
        formulas = [metric.molecular_formula(s) for s in guesses]
        same_formula = [(s, k) for s, k, f in zip(guesses, keys, formulas) if f == formula]
        formula_rank = next((i for i, (_, key) in enumerate(same_formula, 1) if key == item["identity"]), None)
        row = {"molecule_id": mid, "identity": item["identity"], "rank": rank,
               "mrr_at_25": 1.0/rank if rank else 0.0,
               "top1": int(rank == 1), "top5": int(rank is not None and rank <= 5), "top25": int(rank is not None),
               "guess_count": len(guesses), "valid_identity_count": len(set(keys)-{None}),
               "candidate_identities": keys,
               "invalid_guess_count": keys.count(None),
               "duplicate_identity_guesses": sum(k is not None for k in keys)-len(set(keys)-{None}),
               "truth_formula": formula, "top1_formula": formulas[0],
               "top1_same_formula": formulas[0] == formula if formulas[0] is not None else None,
               "truth_formula_only_rank": formula_rank,
               "truth_formula_only_rr": 1.0/formula_rank if formula_rank else 0.0}
        rows.append(row)
    subsets = {}
    for name in ("split", "source", "library", "panel", "adduct_group"):
        if name in truth.columns:
            lookup = dict(zip(truth.molecule_id, truth[name]))
            subsets[name] = {str(value): _summary([r for r in rows if lookup[r["molecule_id"]] == value])
                             for value in truth[name].drop_duplicates()}
    wrong_valid = [r for r in rows if not r["top1"] and r["top1_same_formula"] is not None]
    return {"metrics": _summary(rows), "subsets": subsets,
            "formula_diagnostics": {
                "scope": "Diagnostic only: conditioning candidates on the known truth formula uses oracle information, not deployable performance.",
                "wrong_top1_valid_molecules": len(wrong_valid),
                "wrong_top1_same_formula_molecules": sum(r["top1_same_formula"] for r in wrong_valid),
                "wrong_top1_same_formula_fraction": float(np.mean([r["top1_same_formula"] for r in wrong_valid])) if wrong_valid else None,
                "truth_formula_only_mrr": float(np.mean([r["truth_formula_only_rr"] for r in rows])),
                "top1_formula_subsets": {label: _summary([r for r in rows if r["top1_same_formula"] is value])
                                         for label, value in (("same", True), ("different", False), ("invalid", None))}},
            "candidate_recall_decomposition": {"status": "unknown", "reason": "No pre-ranking candidate audit supplied; top25 hit rate is not pre-ranking recall."},
            "rows": rows}


def audit_fixed_candidates(truth: pd.DataFrame, predictions: pd.DataFrame, baseline: pd.DataFrame) -> dict:
    # evaluate_frames performs schema/ID/length checks before this helper is used.
    first = predictions.set_index("molecule_id").smiles.to_dict()
    second = baseline.set_index("molecule_id").smiles.to_dict()
    differences = []
    for mid in truth.molecule_id:
        current, control = metric.candidate_identity_set(first[mid]), metric.candidate_identity_set(second[mid])
        if current != control:
            differences.append({"molecule_id": mid, "added_identities": sorted(current-control), "removed_identities": sorted(control-current)})
    return {"equal": not differences, "scope": "Valid metric-identity sets in submitted lists of at most 25 guesses; scoring order and duplicate/invalid slots are not changed.",
            "molecules_checked": len(truth), "different_molecules": len(differences), "differences": differences}


def paired_bootstrap(current_rows: list[dict], baseline_rows: list[dict], resamples: int = 2000,
                     seed: int = 20261104, confidence: float = 0.95) -> dict:
    if resamples < 1 or not 0 < confidence < 1:
        raise ValueError("Bootstrap resamples must be positive and confidence between zero and one")
    current = {r["molecule_id"]: r for r in current_rows}
    baseline = {r["molecule_id"]: r for r in baseline_rows}
    if set(current) != set(baseline) or not current:
        raise ValueError("Paired bootstrap requires the same nonempty molecule IDs")
    ids = sorted(current)
    keys = ("mrr_at_25", "top1", "top5", "top25")
    delta = np.array([[current[mid][key]-baseline[mid][key] for key in keys] for mid in ids], dtype=np.float64)
    rng = np.random.default_rng(seed)
    draws = np.empty((resamples, len(keys)), dtype=np.float64)
    for start in range(0, resamples, 128):
        stop = min(start+128, resamples)
        draws[start:stop] = delta[rng.integers(0, len(ids), size=(stop-start, len(ids)))].mean(axis=1)
    tails = [(1-confidence)/2, (1+confidence)/2]
    intervals = np.quantile(draws, tails, axis=0)
    return {"unit": "molecule", "method": "paired percentile bootstrap", "molecules": len(ids),
            "resamples": resamples, "seed": seed, "confidence": confidence,
            "metrics": {key: {"delta": float(delta[:, i].mean()), "ci_low": float(intervals[0, i]), "ci_high": float(intervals[1, i])}
                        for i, key in enumerate(keys)}}


def add_candidate_audit(report: dict, audit: pd.DataFrame) -> None:
    _required(audit, ["molecule_id", "candidate_smiles"], "Candidate audit")
    lookup = audit.set_index("molecule_id").candidate_smiles.to_dict()
    known = recalled = missed = ranking_losses = 0
    for row in report["rows"]:
        raw = lookup.get(row["molecule_id"])
        if raw is None:
            row["pre_ranking_truth_recalled"] = None
            continue
        if not isinstance(raw, str):
            raise ValueError("candidate_smiles must be a string (empty string means empty pool)")
        values = metric.parse_guesses(raw, max_rank=None) if raw.strip("; \t\r\n") else []
        keys = {key for s in values if (key := metric.identity(s))}
        if set(row["candidate_identities"])-{None}-keys:
            raise ValueError(f"Candidate audit excludes submitted identities: {row['molecule_id']}")
        hit = row["identity"] in keys
        row["pre_ranking_truth_recalled"] = hit
        row["pre_ranking_valid_identity_count"] = len(keys)
        if row["top25"] and not hit:
            raise ValueError(f"Candidate audit excludes a submitted correct identity: {row['molecule_id']}")
        known += 1
        recalled += hit
        missed += not hit
        ranking_losses += hit and not row["top1"]
    report["candidate_recall_decomposition"] = {
        "status": "known" if known == len(report["rows"]) else "partial",
        "audited_molecules": known, "unknown_molecules": len(report["rows"])-known,
        "candidate_recall": recalled/known if known else None, "recalled_molecules": recalled,
        "recall_misses": missed, "recalled_but_not_top1": ranking_losses,
        "scope": "Only supplied pre-ranking candidate unions; missing audit rows remain unknown."}


def _read(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path, dtype=str, keep_default_na=False)


def _file_record(path: Path) -> dict:
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--truth", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--candidate-audit", type=Path)
    parser.add_argument("--require-fixed-candidates", action="store_true")
    parser.add_argument("--bootstrap-resamples", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20261104)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--per-molecule-output", type=Path)
    args = parser.parse_args()
    if args.require_fixed_candidates and not args.baseline:
        parser.error("--require-fixed-candidates requires --baseline")
    truth, predictions = _read(args.truth), _read(args.predictions)
    report = evaluate_frames(truth, predictions)
    report.update(rdkit_version=metric.assert_official_rdkit(), scorer="Local implementation checked against archived official V14; additional strict truth/ID/version guards.",
                  official_metric_url=metric.OFFICIAL_METRIC_URL, official_metric_version=metric.OFFICIAL_METRIC_VERSION,
                  official_source_sha256=metric.OFFICIAL_SOURCE_SHA256,
                  inputs={"truth": _file_record(args.truth), "predictions": _file_record(args.predictions)})
    if args.candidate_audit:
        add_candidate_audit(report, _read(args.candidate_audit))
        report["inputs"]["candidate_audit"] = _file_record(args.candidate_audit)
    if args.baseline:
        baseline = _read(args.baseline)
        control = evaluate_frames(truth, baseline)
        report["baseline_metrics"] = control["metrics"]
        report["fixed_candidate_audit"] = audit_fixed_candidates(truth, predictions, baseline)
        report["paired_bootstrap"] = paired_bootstrap(report["rows"], control["rows"], args.bootstrap_resamples, args.seed)
        if "panel" in truth.columns:
            panel_by_id = dict(zip(truth.molecule_id, truth.panel))
            report["paired_bootstrap_by_panel"] = {
                str(panel): paired_bootstrap([row for row in report["rows"] if panel_by_id[row["molecule_id"]] == panel],
                                            [row for row in control["rows"] if panel_by_id[row["molecule_id"]] == panel],
                                            args.bootstrap_resamples, args.seed)
                for panel in truth.panel.drop_duplicates()}
        report["inputs"]["baseline"] = _file_record(args.baseline)
    report["fixed_candidate_requirement_satisfied"] = (report.get("fixed_candidate_audit", {}).get("equal", False) if args.require_fixed_candidates else None)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    if args.per_molecule_output:
        args.per_molecule_output.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(report["rows"]).to_csv(args.per_molecule_output, index=False)
    print(json.dumps({key: report[key] for key in ("metrics", "candidate_recall_decomposition", "fixed_candidate_requirement_satisfied")}, indent=2))
    if args.require_fixed_candidates and not report["fixed_candidate_audit"]["equal"]:
        print("Fixed-candidate ablation rejected: submitted metric-identity sets differ.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
