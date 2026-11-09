"""Compare completed report rows only; never load spectra or run models."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    import numpy as np
    from validation.evaluate import paired_bootstrap

    paths = {"flex": ROOT / "reports/validation_flex_c2_20261105d/evaluation_report.json",
             "v43": ROOT / "reports/validation_v43_c2_20261105c/evaluation_report.json"}
    reports = {key: json.loads(path.read_text(encoding="utf-8")) for key, path in paths.items()}
    flex, v43 = reports["flex"], reports["v43"]
    binding_keys = ("manifest_sha256", "run_manifest_sha256", "split_sha256", "metric_rdkit",
                    "official_source_sha256", "cohort_policy")
    for key in binding_keys:
        if flex[key] != v43[key]:
            raise ValueError("Report binding differs: " + key)
    for name, report in reports.items():
        if (report["status"] != "complete_diagnostic" or report["runtime_audit"]["status"] != "passed"
                or report["final_locked_evaluated"] or report["final_locked_active_intersection"] != 0):
            raise ValueError("Incomplete, unhealthy or locked-final evaluation: " + name)
    panels = {}
    for name, report in reports.items():
        lookup = {}
        for row in report["candidate_stages"]["rows"]:
            mid, panel = row["molecule_id"], row["panel"]
            if mid in lookup and lookup[mid] != panel:
                raise ValueError("Conflicting report panel labels")
            lookup[mid] = panel
        panels[name] = lookup
    if panels["flex"] != panels["v43"]:
        raise ValueError("Report panel assignments differ")
    panel_by_id = panels["flex"]
    control = {row["molecule_id"]: row for row in v43["predictions"]["final"]["rows"]}
    if len(control) != 48 or set(control) != set(panel_by_id):
        raise ValueError("Unexpected cohort")

    def correlation(first, second):
        a, b = np.asarray(first, float), np.asarray(second, float)
        return None if a.std() == 0 or b.std() == 0 else float(np.corrcoef(a, b)[0, 1])

    comparisons = {}
    for arm in ("final", "V0", "V1"):
        rows = flex["predictions"][arm]["rows"]
        current = {row["molecule_id"]: row for row in rows}
        if len(current) != len(rows) or set(current) != set(control):
            raise ValueError("Comparison cohort differs: " + arm)
        if any(current[mid]["identity"] != control[mid]["identity"]
               or current[mid]["truth_formula"] != control[mid]["truth_formula"] for mid in current):
            raise ValueError("Report truth identity/formula differs: " + arm)
        groups = {"all": sorted(current)}
        groups.update({panel: sorted(mid for mid in current if panel_by_id[mid] == panel)
                       for panel in sorted(set(panel_by_id.values()))})
        strata = {}
        for panel, ids in groups.items():
            a, b = [current[mid] for mid in ids], [control[mid] for mid in ids]
            signs = [x["mrr_at_25"]-y["mrr_at_25"] for x, y in zip(a, b)]
            counts = dict(both_top1_correct=sum(bool(x["top1"] and y["top1"]) for x, y in zip(a, b)),
                          only_flex_top1_correct=sum(bool(x["top1"] and not y["top1"]) for x, y in zip(a, b)),
                          only_v43_top1_correct=sum(bool(not x["top1"] and y["top1"]) for x, y in zip(a, b)),
                          both_top1_wrong=sum(bool(not x["top1"] and not y["top1"]) for x, y in zip(a, b)),
                          rr_flex_better=sum(value > 0 for value in signs),
                          rr_v43_better=sum(value < 0 for value in signs), rr_equal=sum(value == 0 for value in signs))
            strata[panel] = dict(molecules=len(ids),
                flex_metrics={key: float(np.mean([x[key] for x in a])) for key in ("mrr_at_25", "top1", "top5", "top25")},
                v43_metrics={key: float(np.mean([x[key] for x in b])) for key in ("mrr_at_25", "top1", "top5", "top25")},
                paired_bootstrap=paired_bootstrap(a, b, resamples=2000, seed=20261104), counts=counts,
                correlations=dict(top1_error_phi=correlation([not x["top1"] for x in a], [not x["top1"] for x in b]),
                                  top25_miss_phi=correlation([not x["top25"] for x in a], [not x["top25"] for x in b]),
                                  reciprocal_rank_pearson=correlation([x["mrr_at_25"] for x in a], [x["mrr_at_25"] for x in b])),
                common_top25_miss_ids=[mid for mid in ids if not current[mid]["top25"] and not control[mid]["top25"]],
                same_top1_identity_molecules=sum(x["candidate_identities"][0] == y["candidate_identities"][0] for x, y in zip(a, b)),
                oracle=dict(scope="Truth-conditioned diagnostic upper bound, never a deployable prediction or chosen ensemble.",
                            best_of_two_top1_hits=sum(bool(x["top1"] or y["top1"]) for x, y in zip(a, b)),
                            best_of_two_top25_hits=sum(bool(x["top25"] or y["top25"]) for x, y in zip(a, b)),
                            best_of_two_mrr=float(np.mean([max(x["mrr_at_25"], y["mrr_at_25"]) for x, y in zip(a, b)]))))
        differences = []
        jaccards, exact = [], 0
        for mid in sorted(current):
            a, b = current[mid], control[mid]
            aset, bset = set(a["candidate_identities"])-{None}, set(b["candidate_identities"])-{None}
            jaccards.append(len(aset & bset)/len(aset | bset) if aset | bset else 1.0)
            exact += aset == bset
            if a["rank"] != b["rank"]:
                differences.append(dict(molecule_id=mid, panel=panel_by_id[mid], truth_formula=a["truth_formula"],
                    flex_rank=a["rank"], v43_rank=b["rank"], rr_delta=a["mrr_at_25"]-b["mrr_at_25"],
                    flex_top1_same_formula=a["top1_same_formula"], v43_top1_same_formula=b["top1_same_formula"],
                    top1_correctness_differs=a["top1"] != b["top1"], candidate_identity_set_jaccard=jaccards[-1]))
        comparisons["flex_" + arm + "_vs_v43_final"] = dict(strata=strata,
            candidate_overlap=dict(exact_identity_set_molecules=exact, molecules=len(current), mean_jaccard=float(np.mean(jaccards)),
                scope="Observed final list overlap only; architectures/weights/candidate generation differ, so this is not a fixed-candidate causal ablation."),
            differing_truth_ranks=sorted(differences, key=lambda x: -abs(x["rr_delta"])))
    output = ROOT / "reports/validation_comparison_20261105.json"
    result = dict(status="complete_architectural_diagnostic_comparison", input_reports={name: dict(path=str(path.relative_to(ROOT)), sha256=sha(path)) for name, path in paths.items()},
        validated_equal_bindings={key: flex[key] for key in binding_keys}, active_molecules=48,
        panel_sizes={p: sum(value == p for value in panel_by_id.values()) for p in sorted(set(panel_by_id.values()))},
        final_locked_evaluated=False, final_locked_active_intersection=0, comparisons=comparisons,
        implementation_sha256={"scripts/compare_validation_reports.py": sha(__file__), "validation/evaluate.py": sha(ROOT/"validation/evaluate.py")},
        limitations=["Whole-stack public checkpoints have known or insufficiently audited training exposure. Reference isolation does not establish clean CV.",
            "An architectural comparator changes multiple components and candidate lists; it is not the fixed-candidate Saner ablation.",
            "Small-panel paired bootstrap and observed error correlation do not imply hidden-test or medal performance.",
            "Oracle best-of-two results condition on truth and are not an implemented ensemble. No weights or mainline configuration were changed."])
    output.write_text(json.dumps(result, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    print(json.dumps({name: {panel: value["paired_bootstrap"]["metrics"]["mrr_at_25"] for panel, value in item["strata"].items()}
                      for name, item in comparisons.items()}, indent=2))


if __name__ == "__main__":
    main()
