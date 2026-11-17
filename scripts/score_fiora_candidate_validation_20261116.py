"""Score frozen candidates for all original100 dev queries; never read truth.

Query/candidate inputs are ONLY candidate_freeze.json, queries.json and candidates.json.
The parent scorer/source receipt is read only to prove unchanged native sources.
No training, loss, model selection, coefficient selection, ranking or label reads.
Graph failures remain explicit missing scores; original candidate rows survive.
"""
from __future__ import annotations

import argparse
import ast
import copy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
ASSET = ROOT / "assets/research/fiora_os_20261115"
SOURCE = ASSET / "source_checkout"
DEPENDENCIES = ASSET / "dependencies-linux"
MODEL = ROOT / "runs/fiora_tims_model_20261115"
DATA = ROOT / "runs/fiora_candidate_validation_20261116"
PARENT_DATA = ROOT / "runs/fiora_candidate_pilot_20261115"
PARENT_SCORER = ROOT / "scripts/score_fiora_candidate_pilot_20261115.py"
PARENT_SCORER_PIN = "a87b089cad27507161a6f4fe592e0e17c1f618ed44f27b1a65678cda6a93eae7"
PARENT_SOURCES = PARENT_DATA / "inference/source_bindings_before_predictions.json"
PARENT_SOURCES_PIN = "ea8064e715a43f78c671b1373752554335116b74aee2a2c2832026700c435f1a"
COMMIT = "e19ef82c9a6cb9dbac92bce23e914008f1aeb44e"
STEP0_PIN = "38d3208f4c78a4db935b8d4b58cae643def77b050488d5d7191cf845af114048"
STEP500_PIN = "9c899faa1c45d9a0c25588f99186f34112b25eafe3f6d955a3da34c267996252"
PARAMS_PIN = "1f189efe9fb64f43406bce409b825870655f8b83765c5ee77d3e208e2cbc2418"
CANDIDATE_FREEZE_PIN = "4f4fedc2660096ff8de6e4bd3e1099c421c61189304614d6fb8b1fbfc29016cf"
EXPECTED_QUERIES = 100
QUERY_KEYS = {"molecule_id", "spectrum_id", "instrument_type", "adduct", "collision_energy_ev",
              "measured_precursor_mz", "observed_neutral_mass", "ms2_mzs",
              "ms2_normalized_intensities", "source_input_sha256"}
CANDIDATE_KEYS = {"molecule_id", "spectrum_id", "candidate_index", "pid", "pool_position", "smiles",
                  "pool_neutral_mass", "observed_neutral_mass", "absolute_mass_error_da", "signed_mass_error_ppm"}
TORCH = NP = None


def sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n", encoding="utf-8")


def workspace(path):
    path = Path(path).resolve()
    if path == ROOT or not path.is_relative_to(ROOT):
        raise ValueError("A specific D-backed project directory is required")
    return path


def freeze_inputs(data):
    """Do not open selection or evaluation-only files, even to compute hashes."""
    manifest_path = data / "candidate_freeze.json"
    if sha(manifest_path) != CANDIDATE_FREEZE_PIN:
        raise ValueError("The fixed original100-query candidate manifest changed")
    manifest = read(manifest_path)
    if manifest.get("queries") != EXPECTED_QUERIES or manifest.get("configuration", {}).get("queries") != EXPECTED_QUERIES:
        raise ValueError("The candidate manifest must preserve all original100 dev queries")
    selection = manifest["configuration"]
    if (selection.get("original_dev_structure_denominator") != EXPECTED_QUERIES
            or selection.get("selected_from_cache_ready_only") is not False
            or selection.get("initial_ppm") != 10.0 or selection.get("empty_window_fallback_ppm") != 30.0
            or selection.get("cap") != 128 or selection.get("formula_filter") is not False
            or selection.get("truth_candidate_injection") is not False
            or selection.get("model_scores_used") is not False):
        raise ValueError("Full original100 / fixed mass-window candidate contract differs")
    files = manifest["files"]
    actual = {}
    for name in ("queries.json", "candidates.json"):
        pin = files[name]
        if isinstance(pin, dict):
            pin = pin["sha256"]
        actual[name] = sha(data / name)
        if actual[name] != pin:
            raise ValueError("Frozen inference input changed: " + name)
    queries, candidates = read(data / "queries.json"), read(data / "candidates.json")
    if not isinstance(queries, list) or len(queries) != EXPECTED_QUERIES or not isinstance(candidates, list) or not candidates:
        raise ValueError("Expected all original100 dev queries and their frozen candidate rows")
    if len(candidates) != manifest.get("candidate_rows"):
        raise ValueError("Frozen candidate row count differs from the pinned manifest")
    by_mid = {}
    for query in queries:
        if not isinstance(query, dict) or set(query) != QUERY_KEYS:
            raise ValueError("Query schema differs from the observed-only inference allowlist")
        mid = query["molecule_id"]
        if mid in by_mid or query["instrument_type"] != "timsTOF" or query["adduct"] != "[M+H]+":
            raise ValueError("Duplicate query or unsupported native condition")
        ce = query["collision_energy_ev"]
        if isinstance(ce, bool) or not isinstance(ce, (int, float)) or not math.isfinite(ce):
            raise ValueError("Only the frozen scalar CE is supported")
        if not math.isfinite(query["measured_precursor_mz"]) or query["measured_precursor_mz"] <= 0:
            raise ValueError("Missing observed query precursor")
        if len(query["ms2_mzs"]) != len(query["ms2_normalized_intensities"]):
            raise ValueError("Query peak row binding differs")
        by_mid[mid] = query
    seen, indices = set(), {mid: [] for mid in by_mid}
    for row in candidates:
        if not isinstance(row, dict) or set(row) != CANDIDATE_KEYS:
            raise ValueError("Candidate schema differs from the label-free pool inference allowlist")
        mid = row["molecule_id"]
        key = (mid, row["candidate_index"])
        if mid not in by_mid or key in seen or row["spectrum_id"] != by_mid[mid]["spectrum_id"]:
            raise ValueError("Candidate key/query binding differs")
        if row["observed_neutral_mass"] != by_mid[mid]["observed_neutral_mass"]:
            raise ValueError("Frozen candidate/query mass field differs")
        seen.add(key)
        indices[mid].append(row["candidate_index"])
    if any(values != list(range(len(values))) or len(values) > 128 for values in indices.values()):
        raise ValueError("Original pool candidate ordering/coverage differs")
    if sum(not values for values in indices.values()) != manifest.get("empty_queries"):
        raise ValueError("Empty-window queries differ from the frozen manifest; never drop or refill them")
    return manifest, queries, candidates, by_mid, actual


def source_bindings():
    if sha(PARENT_SCORER) != PARENT_SCORER_PIN or sha(PARENT_SOURCES) != PARENT_SOURCES_PIN:
        raise ValueError("The unchanged eight-query parent scorer/source provenance changed")
    parent = read(PARENT_SOURCES)
    for recorded_path, pin in parent.items():
        relative = Path(recorded_path).relative_to("/mnt/d/Paper/casmi")
        if sha(ROOT / relative) != pin:
            raise ValueError("Native source/model bytes differ from the completed parent pilot: " + str(relative))
    paths = [Path(__file__), PARENT_SCORER, PARENT_SOURCES, ROOT / "scripts/prepare_fiora_tims_pilot_20261115.py",
             SOURCE / "fiora/MS/SimulationFramework.py", SOURCE / "fiora/MS/spectral_scores.py"]
    paths += list((SOURCE / "fiora/GNN").rglob("*.py"))
    paths += list((SOURCE / "fiora/MOL").rglob("*.py"))
    return {str(path): sha(path) for path in paths}


def mass_map_function():
    """Reuse the peer-checked native mapping without executing prep routines."""
    path = ROOT / "scripts/prepare_fiora_tims_pilot_20261115.py"
    parsed = ast.parse(path.read_text(encoding="utf-8"))
    node = next(node for node in parsed.body if isinstance(node, ast.FunctionDef) and node.name == "compiled_mass_map")
    scope = {}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), scope)
    return scope["compiled_mass_map"]


def spectral_score(raw, masses, forward, query):
    from fiora.MS.spectral_scores import spectral_cosine
    precursor = float(query["measured_precursor_mz"])
    removal = max(.01, abs(precursor) * 100e-6)
    mz, intensity = NP.asarray(query["ms2_mzs"], dtype=float), NP.asarray(query["ms2_normalized_intensities"], dtype=float)
    qkeep = NP.isfinite(mz) & NP.isfinite(intensity) & (mz > 0) & (intensity > 0)
    qkeep &= NP.abs(mz - precursor) > removal
    keep = forward & NP.isfinite(masses) & (raw > .001)
    keep[-2:] = False
    keep &= NP.abs(masses - precursor) > removal
    if not qkeep.any() or not keep.any():
        return 0.0, int(keep.sum()), int(qkeep.sum())
    measured = dict(mz=mz[qkeep].tolist(), intensity=intensity[qkeep].tolist())
    predicted = dict(mz=masses[keep].tolist(), intensity=raw[keep].tolist())
    score = float(spectral_cosine(measured, predicted, tolerance=.01, transform=NP.sqrt))
    if not math.isfinite(score):
        raise ValueError("Nonfinite actual reconstructed sqrt spectral cosine")
    return score, int(keep.sum()), int(qkeep.sum())


def rss_mib():
    import resource
    return float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) / 1024.0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=DATA)
    parser.add_argument("--output", type=Path, default=DATA / "inference")
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    args = parser.parse_args()
    data, out = workspace(args.data_root), workspace(args.output)
    if out == data or out.exists():
        raise ValueError("Preserve previous prediction output; use fresh inference directory")
    manifest, queries, candidates, by_mid, actual = freeze_inputs(data)
    params_path = MODEL / "fiora_OS_tims_migrated_params.json"
    step0_path = MODEL / "fiora_OS_tims_migrated_state.pt"
    step500_path = MODEL / "pilot500/last_checkpoint.pt"
    training = read(MODEL / "pilot500/verification.json")
    migration = read(MODEL / "migration_receipt.json")
    if sha(params_path) != PARAMS_PIN or sha(step0_path) != STEP0_PIN or sha(step500_path) != STEP500_PIN:
        raise ValueError("Fixed compared model/params SHA differs")
    if training.get("status") != "completed_fixed500_real_fiora_graphwise_kl" or training.get("optimizer_steps") != 500 or training.get("checkpoint_sha256") != STEP500_PIN:
        raise ValueError("Fixed500 last checkpoint did not complete")
    if migration.get("status") != "MIGRATED_STRICT_HCD_PARITY_PASSED" or migration.get("source_commit") != COMMIT:
        raise ValueError("Native source/migrated model receipt differs")
    pins = source_bindings()
    pins |= {str(params_path):PARAMS_PIN, str(step0_path):STEP0_PIN, str(step500_path):STEP500_PIN,
             str(MODEL / "pilot500/verification.json"):sha(MODEL / "pilot500/verification.json"),
             str(MODEL / "migration_receipt.json"):sha(MODEL / "migration_receipt.json")}
    config = dict(status="frozen_before_candidate_inference", created_utc=datetime.now(timezone.utc).isoformat(),
        candidate_freeze_sha256=sha(data / "candidate_freeze.json"), source_commit=COMMIT,
        inference_files_sha256=actual, model_params_sha256=PARAMS_PIN, step0_state_sha256=STEP0_PIN,
        step500_checkpoint_sha256=STEP500_PIN, queries=len(queries), candidate_rows=len(candidates),
        original_dev_structure_denominator=EXPECTED_QUERIES, all_original_dev_queries_preserved=True,
        cache_ready_filter_applied=False, empty_window_queries=manifest["empty_queries"],
        parent_scorer_sha256=PARENT_SCORER_PIN, parent_source_bindings_sha256=PARENT_SOURCES_PIN,
        scoring_and_single_graph_inference_unchanged_from_parent=True,
        condition="native [M+H]+ timsTOF frozen scalar CE", device=args.device, graph_depth=1,
        graph_batch_size=1, models_compared=["step0", "step500"], shared_original_candidate_set=True,
        score_direction="larger_is_better", score="native sqrt m/z spectral_cosine",
        matching_tolerance_da=.01, predicted_intensity_threshold_strict_greater_than=.001,
        precursor_removal="Both spectra use common observed query precursor, window=max(.01Da,100ppm*abs(observed precursor)); explicit removal of both native precursor channels",
        forward_mass_map="original native forward directed edges only; ring/no-fragment NaNs excluded",
        binning="native adjacent-bin chaining, not strict one-to-one peak matching",
        graph_or_inference_failure_policy="keep original candidate row and null score; never backfill or drop",
        labels_read=False, training_performed=False, loss_computed=False, ranking_computed=False,
        fit_or_score_coefficient_selection=False, new_public_score=None,
        objective_boundary="FIORA is another forward-spectrum model, as are existing ICE/GL components; trained domain/labels/architecture differ, not an entirely orthogonal objective.")
    out.mkdir(parents=True, exist_ok=False)
    with (out / "worker_claim.json").open("x",encoding="utf-8") as claim:
        claim.write(json.dumps(dict(pid=os.getpid(),script_sha256=sha(__file__)))+"\n")
    save(out / "configuration.json", config)
    save(out / "source_bindings_before_predictions.json", pins)
    (out / "executed_score_script.py").write_bytes(Path(__file__).read_bytes())
    frozen_output_pins = {str(out / name): sha(out / name) for name in
                          ("configuration.json", "source_bindings_before_predictions.json", "executed_score_script.py")}
    score_path = out / "candidate_scores.jsonl"
    start, processed = time.monotonic(), 0
    try:
        global TORCH, NP
        sys.dont_write_bytecode = True
        sys.path[:0] = [str(SOURCE), str(DEPENDENCIES)]
        import numpy as NP
        import torch as TORCH
        from torch_geometric.data import Batch
        from fiora.GNN.FioraModel import FioraModel
        from fiora.GNN.AtomFeatureEncoder import AtomFeatureEncoder
        from fiora.GNN.BondFeatureEncoder import BondFeatureEncoder
        from fiora.GNN.CovariateFeatureEncoder import CovariateFeatureEncoder
        from fiora.MOL.Metabolite import Metabolite
        from fiora.MOL.constants import DEFAULT_MODES
        from rdkit import RDLogger
        RDLogger.DisableLog("rdApp.*")
        TORCH.set_num_threads(4)
        TORCH.manual_seed(20261115)
        if args.device == "cuda" and not TORCH.cuda.is_available():
            raise RuntimeError("CUDA unavailable; no automatic CPU replacement")
        device = TORCH.device(args.device)
        if device.type == "cuda":
            TORCH.cuda.manual_seed_all(20261115)
            TORCH.backends.cudnn.benchmark = False
            TORCH.backends.cudnn.deterministic = True
        params = read(params_path)
        state0 = TORCH.load(step0_path, map_location="cpu", weights_only=True)
        checkpoint = TORCH.load(step500_path, map_location="cpu", weights_only=True)
        state500 = checkpoint["model_state_dict"]
        if checkpoint.get("step") != 500 or checkpoint.get("model_params") != params:
            raise ValueError("Final checkpoint model/step contract differs")
        del checkpoint
        models, load_checks = {}, {}
        for tag, state in (("step0", state0), ("step500", state500)):
            if len(state) != 67:
                raise ValueError("Expected exact67-key native FIORA state")
            model = FioraModel(copy.deepcopy(params))
            result = model.load_state_dict(state, strict=True)
            model.to(device).eval()
            models[tag] = model
            load_checks[tag] = dict(strict=True, state_keys=len(state), missing_keys=list(result.missing_keys),
                                    unexpected_keys=list(result.unexpected_keys), parameters=sum(p.numel() for p in model.parameters()))
        del state0, state500, state
        atoms = AtomFeatureEncoder(feature_list=["symbol", "num_hydrogen", "ring_type"])
        bonds = BondFeatureEncoder(feature_list=["bond_type", "ring_type"])
        categories = params["setup_features_categorical_set"]
        covariates = CovariateFeatureEncoder(feature_list=params["setup_features"], sets_overwrite=categories)
        rt_covariates = CovariateFeatureEncoder(feature_list=params["rt_features"], sets_overwrite=categories)
        if covariates.encoding_dim != 19 or rt_covariates.encoding_dim != 18:
            raise ValueError("Migrated native input dimensions differ")
        mass_map = mass_map_function()
        save(out / "model_load_verification.json", load_checks)
        if device.type == "cuda":
            TORCH.cuda.reset_peak_memory_stats()
        print(json.dumps(dict(stage="both_models_loaded", candidate_rows=len(candidates), seconds=time.monotonic()-start)),flush=True)
        counts = {"step0":0, "step500":0, "graph_error":0}
        graph_times, infer_times = [], {"step0":[],"step500":[]}
        with TORCH.inference_mode(), score_path.open("x", encoding="utf-8") as handle:
            for row in candidates:
                query = by_mid[row["molecule_id"]]
                record = dict(row)
                record |= dict(step0_score=None, step500_score=None, step0_status="not_executed", step500_status="not_executed",
                               collision_energy_ev=query["collision_energy_ev"], instrument_type="timsTOF", adduct="[M+H]+",
                               query_precursor_mz=query["measured_precursor_mz"])
                tick = time.monotonic()
                try:
                    mol = Metabolite(row["smiles"])
                    mol.create_molecular_structure_graph()
                    mol.compute_graph_attributes(atoms,bonds)
                    mol.set_id(int(row["candidate_index"]))
                    mol.add_metadata(dict(name=str(row["candidate_index"]), collision_energy=query["collision_energy_ev"],
                                          instrument="timsTOF", precursor_mode="[M+H]+"), covariates, rt_covariates)
                    mol.fragment_MOL(depth=1)
                    graph = mol.as_geometric_data(with_labels=False)
                    masses, forward, theoretical = mass_map(mol,DEFAULT_MODES)
                    record.update(graph_seconds=time.monotonic()-tick, directed_edges=int(graph.edge_index.shape[1]),
                                  compiled_elements=int(len(masses)), theoretical_candidate_precursor_mz=float(theoretical))
                    graph_times.append(record["graph_seconds"])
                    for tag, model in models.items():
                        if device.type == "cuda":
                            TORCH.cuda.synchronize()
                        predict_start = time.monotonic()
                        try:
                            batch = Batch.from_data_list([graph]).to(device)
                            prediction = model(batch)
                            raw = prediction["fragment_probs"].detach().cpu().numpy()
                            ptr = prediction["segment_ptr"].detach().cpu().tolist()
                            if ptr != [0,len(masses)] or raw.ndim != 1 or len(raw)!=len(masses) or not NP.isfinite(raw).all():
                                raise ValueError("Original graph/output vector row binding differs")
                            value, predicted_channels, query_peaks = spectral_score(raw,masses,forward,query)
                            if device.type == "cuda":
                                TORCH.cuda.synchronize()
                            elapsed = time.monotonic()-predict_start
                            record.update({tag+"_score":value, tag+"_status":"scored", tag+"_seconds":elapsed,
                                           tag+"_raw_sha256":hashlib.sha256(raw.tobytes()).hexdigest(),
                                           tag+"_predicted_fragment_channels":predicted_channels,
                                           "measured_fragment_peaks":query_peaks})
                            counts[tag] += 1
                            infer_times[tag].append(elapsed)
                            del batch,prediction,raw
                        except Exception as exc:
                            record.update({tag+"_status":"inference_error",tag+"_error_type":type(exc).__name__,tag+"_error":str(exc),
                                           tag+"_seconds":time.monotonic()-predict_start})
                            if device.type == "cuda":
                                TORCH.cuda.empty_cache()
                    del mol,graph,masses,forward
                except Exception as exc:
                    counts["graph_error"] += 1
                    record.update(graph_seconds=time.monotonic()-tick, step0_status="graph_error", step500_status="graph_error",
                                  graph_error_type=type(exc).__name__, graph_error=str(exc))
                handle.write(json.dumps(record,ensure_ascii=False,allow_nan=False)+"\n")
                handle.flush()
                processed += 1
                if processed in (1,10,50) or processed%100==0 or processed==len(candidates):
                    print(json.dumps(dict(stage="candidate_progress",processed=processed,total=len(candidates),counts=counts,
                                          seconds=time.monotonic()-start,rss_peak_mib=rss_mib())),flush=True)
        if sha(data / "candidate_freeze.json") != config["candidate_freeze_sha256"] or any(sha(data/name)!=pin for name,pin in actual.items()):
            raise ValueError("Frozen query/candidate bytes changed during inference")
        if any(sha(Path(path)) != pin for path,pin in pins.items()):
            raise ValueError("Frozen source/model bytes changed during inference")
        if any(sha(Path(path)) != pin for path,pin in frozen_output_pins.items()):
            raise ValueError("Frozen configuration/source snapshots changed during inference")
        completed_rows = [json.loads(line) for line in score_path.read_text(encoding="utf-8").splitlines()]
        if len(completed_rows)!=len(candidates) or any(any(saved[k]!=original[k] for k in original) for saved,original in zip(completed_rows,candidates)):
            raise ValueError("Output dropped/reordered/modified a frozen candidate row")
        all_scored = all(r[tag+"_status"]=="scored" for r in completed_rows for tag in models)
        finite = all(r[tag+"_score"] is None or math.isfinite(r[tag+"_score"]) for r in completed_rows for tag in models)
        verification = dict(status="completed_dual_checkpoint_candidate_spectrum_scoring" if all_scored else "completed_candidate_traversal_with_missing_predictions", labels_read=False, training_performed=False,
            candidate_freeze_sha256=config["candidate_freeze_sha256"], queries_sha256=actual["queries.json"],
            candidates_sha256=actual["candidates.json"], step0_state_sha256=STEP0_PIN, step500_checkpoint_sha256=STEP500_PIN,
            final_checkpoint_sha256=STEP500_PIN, step0_state_path=step0_path.relative_to(ROOT).as_posix(),
            final_checkpoint_path=step500_path.relative_to(ROOT).as_posix(),
            model_params_sha256=PARAMS_PIN, source_commit=COMMIT, model_load_checks=load_checks,
            scores_sha256=sha(score_path), configuration_sha256=sha(out/"configuration.json"),
            source_bindings_sha256=sha(out/"source_bindings_before_predictions.json"),
            executed_score_script_sha256=sha(out/"executed_score_script.py"), script_sha256=sha(__file__),
            parent_scorer_sha256=PARENT_SCORER_PIN, parent_source_bindings_sha256=PARENT_SOURCES_PIN,
            source_pins=pins, query_count=len(queries),
            expected_queries=EXPECTED_QUERIES, original_dev_structure_denominator=EXPECTED_QUERIES,
            empty_window_queries=manifest["empty_queries"], all_original_dev_queries_preserved=True,
            expected_candidates=manifest["candidate_rows"], processed_candidates=processed,
            candidate_rows_preserved=True, same_candidate_set_for_both_models=True, all_candidates_scored=all_scored,
            all_scores_finite=finite, score_counts=counts, score_direction="larger_is_better", ranking_computed=False,
            elapsed_seconds=time.monotonic()-start, rss_peak_mib=rss_mib(),
            gpu_peak_allocated_mib=TORCH.cuda.max_memory_allocated()/1024**2 if device.type=="cuda" else None,
            graph_latency=dict(total_seconds=sum(graph_times), median_seconds=float(NP.median(graph_times)) if graph_times else None),
            inference_latency={tag:dict(total_seconds=sum(values),median_seconds=float(NP.median(values)) if values else None) for tag,values in infer_times.items()},
            new_public_score=None, mrr25=None, top1=None,
            boundary="All original100 development queries, including the two without true-fragment supervision; same existing dev panel, not a new holdout, full champion ranking or new public score. Empty mass windows retain their queries; graph/inference failures retain candidate rows with null scores and make predictions incomplete. No labels were opened by inference.")
        save(out / "verification.json", verification)
        print(json.dumps({k:verification[k] for k in ("status","expected_candidates","processed_candidates","all_candidates_scored","score_counts","elapsed_seconds")}),flush=True)
    except BaseException as exc:
        save(out / "failure.json", dict(status="failed_fiora_candidate_inference",processed_candidates=processed,
            error_type=type(exc).__name__,error=str(exc),traceback=traceback.format_exc(),labels_read=False))
        raise


if __name__ == "__main__":
    main()
