"""Evaluate an already completed, frozen champion replay; never run inference.

Usage: --run-root <completed diagnostic run> --output <new D-workspace directory>
Prediction/source/trace bindings are written BEFORE opening fixed old48 truth.
Observed candidate recall is a lower bound, not full catalog/search recall.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "runs/validation_pilot_v2_20261104"
CHAMPION = ROOT / "submission/optimization_20261109/mass_guarded_extlib/notebook.ipynb"
CHAMPION_PIN = "2bb94c91b176f95dfdff52f08781443ffee004c20d06aeb30efb14d0c0112fc7"
FROZEN_PIN = "d1e757c2b71b46e6e8a5777f14302a4737d0fdbcd56d8365093c039b93c5fd88"
OBSERVER_PIN = "78d21e2a8bdc754ab9466a409aca044cc3e0d6e9c590ad0cb21bf8de4e19d4f5"
TRUTH_PIN = "b47e21297d5b3b528430a9fd2286574589026b4d3f2228c3ac2b6d98f260fb7f"
COMPLETED = "completed_original_champion_with_diagnostic_reference_masks"
METRIC = None


def sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def csv_rows(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def workspace(path):
    path = Path(path).resolve()
    if path == ROOT or not path.is_relative_to(ROOT):
        raise ValueError("Use a specific directory inside the D-backed project workspace")
    return path


def checks_passed(value):
    return isinstance(value, dict) and bool(value) and all(v is True for v in value.values())


def events(path, expected_count=None):
    rows = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows or [r.get("sequence") for r in rows] != list(range(1, len(rows) + 1)):
        raise ValueError("Missing or reordered observer events: " + str(path))
    if expected_count is not None and len(rows) != expected_count:
        raise ValueError("Observer count differs from completed verification: " + str(path))
    if len({r.get("process_id") for r in rows}) != 1:
        raise ValueError("Mixed process trace: " + str(path))
    return rows


def predictions(path, ids):
    rows = csv_rows(path)
    if not rows or set(rows[0]) != {"molecule_id", "smiles"}:
        raise ValueError("Prediction schema differs: " + str(path))
    if [r["molecule_id"] for r in rows] != ids:
        raise ValueError("Prediction ID/order differs: " + str(path))
    out = {}
    for row in rows:
        guesses = [s.strip() for s in row["smiles"].split(";") if s.strip()]
        if not 1 <= len(guesses) <= 25:
            raise ValueError("Invalid final-list length: " + str(path))
        # Invalid identities and repeats retain their original rank positions.
        out[row["molecule_id"]] = guesses
    return out


def verify_completed(run):
    """No truth files or label metrics are accessed in this function."""
    if (run / "failure.json").exists():
        raise ValueError("Refuse a failed replay, even if other partial artifacts exist")
    if not (run / "verification.json").is_file():
        raise ValueError("Replay has no completed verification.json; inference is still incomplete")
    proof = read(run / "verification.json")
    if proof.get("status") != COMPLETED or proof.get("original_notebook_sha256") != CHAMPION_PIN:
        raise ValueError("Replay is incomplete or not the exact champion source")
    cfg, prep, launch = [read(run / p) for p in ("configuration.json", "preparation.json", "launch_bindings.json")]
    cfg_pin = sha(run / "configuration.json")
    if any(v.get("configuration_sha256") != cfg_pin for v in (proof, prep, launch)):
        raise ValueError("Configuration binding differs")
    if cfg.get("pipeline") != "champion_0488" or cfg.get("original_notebook_sha256") != CHAMPION_PIN:
        raise ValueError("Wrong diagnostic pipeline")
    if launch.get("original_champion_sha256") != CHAMPION_PIN or sha(CHAMPION) != CHAMPION_PIN:
        raise ValueError("Champion notebook bytes changed")
    if cfg.get("labels_in_inference_test") is not False or cfg.get("changed_model_weights") is not False:
        raise ValueError("Labels or changed model weights in inference contract")
    ids = cfg["active_ids"]
    if not ids or len(ids) != len(set(ids)) or not all(isinstance(x, str) for x in ids):
        raise ValueError("Invalid active query IDs")
    if prep.get("query_ids") != ids or cfg.get("processed_molecules") != len(ids):
        raise ValueError("Prepared query scope differs")
    work = run / "kaggle/working"
    test = run / "kaggle/input/enveda-CASMI26-molecule-id-mass-spectra/test.parquet"
    if sha(test) != cfg.get("query_test_sha256"):
        raise ValueError("Inference query bytes changed")
    pins = launch.get("script_pins", {})
    required = {"run_champion_diagnostics_20261115.py", "replay_champion_inner_20261115.py",
                "champion_stage_observer_20261115.py", "champion_reference_masks_20261115.py"}
    if set(pins) != required or pins.get("champion_stage_observer_20261115.py") != OBSERVER_PIN:
        raise ValueError("Unsupported or incomplete executed observer/source contract")
    for name, pin in pins.items():
        if sha(run / "executed_sources" / name) != pin:
            raise ValueError("Executed source snapshot changed: " + name)
    marks = [m["cell"] for m in proof.get("marks", [])]
    original = read(CHAMPION)
    if marks != [i for i, c in enumerate(original["cells"]) if c["cell_type"] == "code"]:
        raise ValueError("Outer replay did not complete every original code cell")
    final = work / "submission.csv"
    final_pin = sha(final)
    if proof.get("output_sha256") != final_pin:
        raise ValueError("Final prediction SHA differs from completed replay")
    audits = {}
    for name in ("batch_variant_audit.json", "guarded_tail_audit.json", "external_overlay_audit.json"):
        value = read(work / name)
        if value != proof.get("original_audits", {}).get(name):
            raise ValueError("Actual original audit differs from completed receipt: " + name)
        if value.get("status") != "passed" or value.get("mode") != "hidden_full" or not checks_passed(value.get("checks")):
            raise ValueError("Original audit did not pass full execution: " + name)
        audits[name] = value
    if audits["external_overlay_audit.json"].get("csv_sha256") != final_pin:
        raise ValueError("AB final output binding differs")
    if audits["batch_variant_audit.json"].get("csv_sha256") != sha(work / "submission_guarded_tail_control.csv"):
        raise ValueError("MASS to guarded-head control binding differs")
    if audits["guarded_tail_audit.json"].get("csv_sha256") != sha(work / "submission_external_control.csv"):
        raise ValueError("Guarded-head to AB control binding differs")
    observer = work / "champion_stage_observer"
    outer, inner = [read(observer / role / "verification.json") for role in ("outer", "inner")]
    if outer != proof.get("observer") or outer.get("final_csv_sha256") != final_pin:
        raise ValueError("Outer observer/final receipt binding differs")
    for role, item in (("outer", outer), ("inner", inner)):
        checks = item.get("checks", {})
        if checks.get("no_truth_read") is not True or checks.get("configuration_written_by_observer") is not False:
            raise ValueError("Observer contract failed: " + role)
        if checks.get("original_return_objects_preserved") is not True:
            raise ValueError("Observer return-object contract failed")
    if inner["checks"].get("installed_after_original_cell37") is not True or inner["checks"].get("configuration_unchanged") is not True:
        raise ValueError("Engine observer/configuration check failed")
    if inner.get("final_csv_sha256") != sha(work / "submission_baseline0465.csv"):
        raise ValueError("Inner observer/final25 export binding differs")
    if sha(work / "p2s_code/frozen_0465.ipynb") != FROZEN_PIN:
        raise ValueError("Nested frozen source bytes changed")
    traces = {role: events(observer / role / "events.jsonl", item.get("event_count"))
              for role, item in (("outer", outer), ("inner", inner))}
    traces["engine2"] = events(observer / "engine2/events.jsonl")
    isolation = proof.get("isolation_installation", {})
    if isolation.get("status") != "installation_evidence_present":
        raise ValueError("Reference isolation installation did not finish")
    for name in isolation.get("required", []):
        if Path(name).name != name or not (work / name).is_file():
            raise ValueError("Missing/bad isolation evidence path")
    if not isolation.get("required"):
        raise ValueError("Empty reference isolation evidence")
    return proof, cfg, work, traces, predictions(final, ids)


def collect_observations(work, traces, ids, final):
    observations = []

    def add(name, source, values, *, ranked=False, chain=False, candidate=True, evidence="", scope="observed_return"):
        for mid in ids:
            values_mid = values.get(mid)
            observations.append(dict(molecule_id=mid, stage=name, source=source, guesses=values_mid,
                                     ranked=ranked, chain=chain, candidate=candidate, evidence=evidence,
                                     recall_scope=scope, stage_order=len(observations)))

    by_kind = defaultdict(dict)
    raw, accepted = defaultdict(list), defaultdict(list)
    for event in traces["inner"]:
        mid, kind = str(event.get("molecule_id")), event["kind"]
        if mid not in ids:
            continue
        if kind == "engine.derive_rec":
            raw[mid].extend(event["raw_product_smiles"])
        elif kind == "engine.generate":
            accepted[mid].extend(p["smiles"] for p in event["accepted_products"])
        elif kind in ("v1fe.run.end", "v1fe.run.error", "rank_score"):
            if mid in by_kind[kind]:
                raise ValueError("Duplicate primary observed E1 query: " + mid + "/" + kind)
            by_kind[kind][mid] = event
    e1 = {mid: e["candidates"]["smiles"] for mid, e in by_kind["v1fe.run.end"].items()}
    # A real observed empty/disabled generator is different from a missing query trace.
    raw = {mid: raw.get(mid, []) for mid in e1}
    accepted = {mid: accepted.get(mid, []) for mid in e1}
    add("generation.raw_products", "raw_generation", raw, candidate=False)
    add("generation.accepted", "accepted_generation", accepted)
    add("E1.all_candidates", "E1all", e1, scope="after_actual_mass_window_and_generation_acceptance")
    ranked = {}
    for mid, event in by_kind["rank_score"].items():
        if mid not in e1 or event.get("candidates", {}).get("smiles") != e1[mid]:
            raise ValueError("Ranker/candidate row binding differs: " + mid)
        order = event["rank_order_indices"]
        if sorted(order) != list(range(len(e1[mid]))) or len(event["scores"]) != len(e1[mid]):
            raise ValueError("Ranker indices/scores are not aligned")
        values = [e1[mid][i] for i in order]
        if values != event.get("ranked_smiles"):
            raise ValueError("Recorded actual E1 ranking differs")
        ranked[mid] = values
    add("E1.actual_ranker_order", "E1all", ranked, ranked=True)
    e2, e2_blend = {}, {}
    for event in traces["engine2"]:
        if event["kind"] == "engine2.main.candidates_and_scores":
            mid = str(event["molecule_id"])
            if mid in e2:
                raise ValueError("Duplicate E2 query record")
            e2[mid] = event["candidate_smiles"]
        elif event["kind"] == "engine2.blend_scores":
            e2_blend.update(event["scores"])
    add("E2.all_candidates", "E2all", e2, scope="after_actual_E2_candidate_filters")
    ranked = {}
    for mid, values in e2.items():
        scores = e2_blend.get(mid)
        if scores is not None:
            if len(scores) != len(values) or any(not isinstance(x, (int, float)) for x in scores):
                raise ValueError("E2 score/candidate row binding differs")
            ranked[mid] = [values[i] for i in sorted(range(len(values)), key=lambda i: (-scores[i], i))]
    add("E2.actual_blend_order", "E2all", ranked, ranked=True)
    chain = []
    for role in ("inner", "outer"):
        for event in traces[role]:
            if event["kind"] != "cell.snapshot" or event.get("position") != "after":
                continue
            cell = event["cell"]
            tag = f"cell_{cell:03d}_after"
            base = work / "champion_stage_observer" / role
            snapshot = read(base / (tag + ".json"))
            lists = snapshot.get("lists", {})
            if role == "inner" and cell == 34:
                pc = {str(mid): item.get("pc", []) for mid, item in lists.get("PC", {}).items()}
                add("PC.returned_proposals", "PCreturned", pc, ranked=True,
                    evidence=str(base / (tag + ".json")), scope="returned_proposals_only_raw_PC_recall_unknown")
            if role == "inner" and cell in (39, 45):
                name = "BASE" if cell == 39 else "ENG"
                values = {str(mid): item[0] if name == "BASE" else item.get("smiles", [])
                          for mid, item in lists.get(name, {}).items()}
                add(f"{name}.retained_channel_list", name, values, ranked=True,
                    evidence=str(base / (tag + ".json")))
            for filename, item in event.get("files", {}).items():
                copied = base / tag / filename
                if Path(filename).name != filename or sha(copied) != item["sha256"]:
                    raise ValueError("Observed stage copy differs: " + str(copied))
                if filename == "submission.csv":
                    label = f"{role}.after_cell_{cell:03d}"
                    values = predictions(copied, ids)
                    add(label, "merged_pipeline", values, ranked=True, chain=True, evidence=str(copied))
                    chain.append(label)
    if not chain or chain[-1] != "outer.after_cell_032":
        raise ValueError("Missing exact final AB observer stage")
    final_observed = [o for o in observations if o["stage"] == chain[-1]]
    if {o["molecule_id"]: o["guesses"] for o in final_observed} != final:
        raise ValueError("Observed AB final differs from verified final prediction")
    ab = read(work / "external_overlay_runtime.json")
    proposals = {str(item["molecule_id"]): [item["smiles"]] if item.get("smiles") else []
                 for item in ab.get("actual_matches", [])}
    add("AB.actual_match_proposal", "AB_best_returned", proposals,
        evidence=str(work / "external_overlay_runtime.json"), scope="actual_best_proposal_not_all_reference_recall")
    add("PC.raw_catalog_or_mass_window", "PCraw_unknown", {}, candidate=False,
        scope="unknown_not_inferred_from_returned_proposals")
    return observations, chain, by_kind


def measure(observation, truth):
    guesses = observation["guesses"]
    known = guesses is not None
    positions = [i for i, value in enumerate(guesses or [], 1) if METRIC.identity(value) == truth]
    first = positions[0] if positions else None
    rank = first if observation["ranked"] else None
    return {k: v for k, v in observation.items() if k != "guesses"} | dict(
        observation_known=known, candidate_count=len(guesses) if known else None,
        truth_present=bool(positions) if known else None, truth_first_position=first,
        truth_rank=rank, rr25=(1.0 / rank if rank is not None and rank <= 25 else 0.0)
        if known and observation["ranked"] else None,
        rank_semantics="actual_observed_order" if observation["ranked"] else "unordered_enumeration_only")


def write_csv(path, rows):
    keys = list(rows[0])
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
                         for k, v in row.items()} for row in rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run, out = workspace(args.run_root), workspace(args.output)
    if out.exists() or out.is_relative_to(run) or run.is_relative_to(out):
        raise ValueError("Output must be a fresh, separate experiment directory")
    proof, cfg, work, traces, final = verify_completed(run)
    ids = cfg["active_ids"]
    observations, chain, e1_events = collect_observations(work, traces, ids, final)
    files = [p for p in run.rglob("*") if p.is_file() and (
        p.parent == run and p.suffix == ".json" or "executed_sources" in p.parts or
        "champion_stage_observer" in p.parts and p.suffix in (".json", ".jsonl", ".csv"))]
    files += [work / "submission.csv", CHAMPION, PANEL / "manifest.json", Path(__file__), ROOT / "validation/metric.py"]
    files += [work / name for name in proof["isolation_installation"]["required"]]
    files += [work / name for name in ("batch_variant_audit.json", "guarded_tail_audit.json", "external_overlay_audit.json",
                                      "external_overlay_runtime.json", "submission_guarded_tail_control.csv",
                                      "submission_external_control.csv", "submission_baseline0465.csv")]
    bindings = {str(p.resolve()): sha(p) for p in sorted(set(files))}
    out.mkdir(parents=True, exist_ok=False)
    save(out / "prediction_bindings_before_labels.json", dict(
        status="predictions_sources_and_observations_frozen_before_truth_read",
        frozen_at_utc=datetime.now(timezone.utc).isoformat(), run_root=str(run),
        final_csv_sha256=proof["output_sha256"], files=bindings,
        note="Trace hashes first sealed here; original receipt binds source snapshots, event counts and final CSV, not every trace byte."))
    try:
        # No truth access occurs before the immutable prediction binding above.
        truth_file = PANEL / "truth.csv"
        manifest = read(PANEL / "manifest.json")
        if manifest["artifact_sha256"].get("truth.csv") != TRUTH_PIN or sha(truth_file) != TRUTH_PIN:
            raise ValueError("Frozen old48 truth changed")
        global METRIC
        sys.path.insert(0, str(ROOT / ".cache/rdkit-official-linux-2026033"))
        sys.path.insert(0, str(ROOT))
        from validation import metric as METRIC
        version = METRIC.assert_official_rdkit()
        truth_rows = csv_rows(truth_file)
        truth = {r["molecule_id"]: r["official_identity"] for r in truth_rows}
        if len(truth) != len(truth_rows) or len(truth) != 48 or not set(ids).issubset(truth):
            raise ValueError("Frozen truth/query group scope differs")
        measured = [measure(row, truth[row["molecule_id"]]) for row in observations]
        summaries = []
        for mid in ids:
            rows = [r for r in measured if r["molecule_id"] == mid]
            lookup = {r["stage"]: r for r in rows}
            losses, recoveries, transitions = [], [], []
            previous = None
            for label in chain:
                row = lookup[label]
                if previous is not None:
                    transition = dict(from_stage=previous["stage"], to_stage=label,
                                      before_rank=previous["truth_rank"], after_rank=row["truth_rank"])
                    if previous["truth_present"] and not row["truth_present"]:
                        losses.append(transition)
                    if not previous["truth_present"] and row["truth_present"]:
                        recoveries.append(transition)
                    if previous["truth_rank"] != row["truth_rank"]:
                        transitions.append(transition)
                previous = row
            source_presence = {s: lookup[s]["truth_present"] for s in
                               ("E1.all_candidates", "E2.all_candidates", "PC.returned_proposals")}
            known_hit = any(r["candidate"] and r["truth_present"] is True for r in rows)
            last = lookup[chain[-1]]
            summaries.append(dict(molecule_id=mid, reference_condition=cfg["reference_mode"],
                E1all=source_presence["E1.all_candidates"], E2all=source_presence["E2.all_candidates"],
                PCreturned=source_presence["PC.returned_proposals"], PCraw_recall="unknown",
                raw_generation=lookup["generation.raw_products"]["truth_present"],
                accepted_generation=lookup["generation.accepted"]["truth_present"],
                candidate_recall_known=known_hit,
                candidate_recall_interpretation="observed_viable_candidate_hit" if known_hit else "known_observed_scopes_miss_total_recall_unknown",
                first_observed_loss=losses[0] if losses else None, later_recoveries=recoveries,
                first_chain_absence=not lookup[chain[0]]["truth_present"],
                rank_transitions=transitions, final_rank=last["truth_rank"], final_rr25=last["rr25"],
                E1_actual_runtime_error=mid in e1_events["v1fe.run.error"]))
        stage_metrics = {}
        for stage in dict.fromkeys(row["stage"] for row in measured):
            rows = [r for r in measured if r["stage"] == stage]
            known = [r for r in rows if r["observation_known"]]
            ranked = [r for r in known if r["ranked"]]
            stage_metrics[stage] = dict(queries=len(rows), observed_queries=len(known),
                truth_present=sum(r["truth_present"] is True for r in rows),
                known_scope_recall=sum(r["truth_present"] is True for r in known) / len(known) if known else None,
                unknown_queries=len(rows)-len(known),
                observed_order_mrr25=sum(r["rr25"] for r in ranked) / len(ranked) if ranked else None,
                note="Returned-channel/order diagnostic only; stages have different candidate scopes. Raw PC pool recall remains unknown.")
        if any(sha(Path(path)) != pin for path, pin in bindings.items()):
            raise ValueError("Frozen prediction/source/trace changed during offline evaluation")
        write_csv(out / "stages_per_query.csv", measured)
        write_csv(out / "query_summary.csv", summaries)
        result = dict(status="completed_frozen_champion_observation_funnel", run_root=str(run),
            original_notebook_sha256=CHAMPION_PIN, final_prediction_sha256=proof["output_sha256"],
            prediction_bindings_sha256=sha(out / "prediction_bindings_before_labels.json"),
            evaluator_sha256=sha(__file__), truth_sha256=TRUTH_PIN, official_rdkit=version,
            official_metric_source_sha256=METRIC.OFFICIAL_SOURCE_SHA256, queries=len(ids),
            reference_condition=cfg["reference_mode"], canary_only=bool(cfg["canary_only"]),
            final_mrr25=sum(r["final_rr25"] for r in summaries) / len(ids),
            final_top1=sum(r["final_rank"] == 1 for r in summaries) / len(ids),
            candidate_recall_known=sum(r["candidate_recall_known"] for r in summaries) / len(ids),
            candidate_recall_known_is_observed_lower_bound=True, complete_catalog_recall=None,
            PCraw_recall=None, first_loss_is_not_complete_candidate_failure=True,
            stages=stage_metrics, new_public_score=None, estimated_gain=None, hidden_class_proportions=None,
            separate_isolation_audit_approved=False, classwise_mechanism_or_gain_claim=False,
            boundary="A finished prediction path and installation receipts do not prove reference independence. These are old training-derived diagnostic queries with legacy pretraining exposure. A one-query canary measures path execution only; no gain or hidden class-share estimate. Unknown raw source scopes cannot be converted into failed total recall.")
        save(out / "verification.json", result)
        print(json.dumps({k: result[k] for k in ("status", "queries", "canary_only", "final_mrr25", "candidate_recall_known")}))
    except BaseException as exc:
        save(out / "failure.json", dict(status="offline_evaluation_failed", error_type=type(exc).__name__, message=str(exc)))
        raise


if __name__ == "__main__":
    main()
