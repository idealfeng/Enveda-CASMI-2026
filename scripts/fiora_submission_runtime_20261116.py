"""Offline FIORA step500 overlay on the champion's final candidate lists.

No training or target labels: parquet reads use an explicit eight-column whitelist.
Only equal-formula candidates exchange their original slots, including rank one.
Asset/setup failures are fatal; a candidate failure rolls back its whole query.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import copy
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys
import time
import traceback

PARENT_CHECKPOINT_PIN = "9c899faa1c45d9a0c25588f99186f34112b25eafe3f6d955a3da34c267996252"
PARAMS_PIN = "1f189efe9fb64f43406bce409b825870655f8b83765c5ee77d3e208e2cbc2418"
SOURCE_COMMIT = "e19ef82c9a6cb9dbac92bce23e914008f1aeb44e"
QUERY_COLUMNS = ["molecule_id", "spectrum_id", "instrument_type", "adduct",
                 "collision_energy_ev", "precursor_mz", "ms2_mzs", "ms2_normalized_intensities"]
MAX_HEAVY_ATOMS = 64
MAX_DIRECTED_EDGES = 160
NP = None


def sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n", encoding="utf-8")


def verify_assets(root, manifest_pin):
    manifest_path = root / "asset_manifest.json"
    if not manifest_pin or sha(manifest_path) != manifest_pin:
        raise ValueError("Frozen FIORA asset manifest SHA differs")
    manifest = read(manifest_path)
    if manifest.get("parent_checkpoint_sha256") != PARENT_CHECKPOINT_PIN:
        raise ValueError("FIORA deployment state does not bind the fixed step500 parent")
    if manifest.get("source_commit", SOURCE_COMMIT) != SOURCE_COMMIT:
        raise ValueError("FIORA native source commit differs")
    files = manifest.get("files")
    if not isinstance(files, dict) or "state.pt" not in files or "params.json" not in files:
        raise ValueError("Incomplete frozen FIORA manifest")
    paths = {}
    for relative, item in files.items():
        path = (root / relative).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            raise ValueError("Missing or unsafe asset manifest path: " + relative)
        pin = item.get("sha256") if isinstance(item, dict) else item
        if not isinstance(pin, str) or len(pin) != 64 or sha(path) != pin:
            raise ValueError("FIORA payload bytes differ: " + relative)
        paths[relative] = pin
    if paths["params.json"] != PARAMS_PIN:
        raise ValueError("FIORA timsTOF19 parameters differ")
    # Never import an unlisted module or extension accidentally left in the bundle.
    for folder in (root / "source_checkout" / "fiora", root / "dependencies"):
        if not folder.is_dir():
            raise ValueError("Missing isolated FIORA source/dependency directory")
        for path in folder.rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix in (".py", ".so", ".pyd"):
                if path.relative_to(root).as_posix() not in paths:
                    raise ValueError("Unbound importable FIORA payload file: " + str(path))
    return manifest, paths


@lru_cache(maxsize=100000)
def describe(smiles):
    import rdkit
    from rdkit import Chem
    from rdkit.Chem import rdMolDescriptors
    from rdkit.Chem.MolStandardize import rdMolStandardize
    if rdkit.__version__ != "2026.03.3":
        raise RuntimeError("Official RDKit2026.03.3 is required for candidate identity/formula")
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return None
        heavy, edges = int(mol.GetNumHeavyAtoms()), int(2 * mol.GetNumBonds())
        Chem.RemoveStereochemistry(mol)
        mol = rdMolStandardize.TautomerEnumerator().Canonicalize(mol)
        key = Chem.MolToInchiKey(mol)
        if not key:
            return None
        return dict(identity=key[:14], formula=rdMolDescriptors.CalcMolFormula(mol),
                    heavy_atoms=heavy, directed_edges=edges)
    except (ValueError, TypeError, RuntimeError):
        return None


def scalar_ce(value):
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (list, tuple)) or hasattr(value, "ndim") and value.ndim != 0:
        if len(value) != 1:
            return None
        value = value[0]
    if isinstance(value, bool):
        return None
    try:
        value = float(value)
    except (ValueError, TypeError):
        return None
    return value if math.isfinite(value) and 20 <= value <= 60 else None


def select_queries(path):
    import pandas as pd
    # Projecting in the parquet reader prevents target columns entering this process.
    rows = pd.read_parquet(path, columns=QUERY_COLUMNS).to_dict("records")
    groups = defaultdict(list)
    counts = Counter()
    for row_index, row in enumerate(rows):
        mid = str(row["molecule_id"])
        if str(row["instrument_type"]).strip().lower() != "timstof" or row["adduct"] != "[M+H]+":
            counts["unsupported_instrument_or_adduct"] += 1
            continue
        ce = scalar_ce(row["collision_energy_ev"])
        if ce is None:
            counts["unsupported_collision_energy"] += 1
            continue
        try:
            precursor = float(row["precursor_mz"])
            mz = NP.asarray(row["ms2_mzs"], dtype=float)
            intensity = NP.asarray(row["ms2_normalized_intensities"], dtype=float)
            if not math.isfinite(precursor) or precursor <= 0 or mz.ndim != 1 or mz.shape != intensity.shape:
                raise ValueError("Invalid precursor/peak shape")
            keep = NP.isfinite(mz) & NP.isfinite(intensity) & (mz > 0) & (intensity > 0)
            keep &= NP.abs(mz - precursor) > max(.01, abs(precursor) * 100e-6)
            if not bool(keep.any()):
                raise ValueError("No measured nonprecursor fragment peaks")
        except (ValueError, TypeError):
            counts["invalid_or_empty_fragment_spectrum"] += 1
            continue
        groups[mid].append(dict(molecule_id=mid, spectrum_id=str(row["spectrum_id"]),
            source_row_index=row_index, instrument_type="timsTOF", adduct="[M+H]+",
            collision_energy_ev=ce, measured_precursor_mz=precursor,
            ms2_mzs=mz.tolist(), ms2_normalized_intensities=intensity.tolist()))
    selected = {mid: sorted(values, key=lambda r: (r["spectrum_id"], r["source_row_index"]))[0]
                for mid, values in groups.items()}
    return selected, dict(total_spectrum_rows=len(rows), selected_queries=len(selected), rejected_spectrum_reasons=dict(counts))


def compiled_mass_map(mol, modes):
    import numpy as np
    directed = mol.edges_as_tuples
    count = len(directed) * 2 * len(modes) + 2
    masses = np.full(count, np.nan, dtype=np.float64)
    forward = np.zeros(count, dtype=np.bool_)
    edge_map = mol.fragmentation_tree.edge_map
    for i, edge in enumerate(directed):
        edge = tuple(edge)
        frags = edge_map.get(edge)
        reverse = False
        if not frags:
            frags = edge_map.get((edge[1], edge[0]))
            reverse = True
        if not frags:
            continue
        for side_i, side in enumerate(['left', 'right']):
            key = ('right' if side == 'left' else 'left') if reverse else side
            frag = frags.get(key)
            if frag is None:
                continue
            for mode_i, mode in enumerate(modes):
                at = i * 2 * len(modes) + side_i * len(modes) + mode_i
                masses[at] = frag.mz[mode]
                forward[at] = edge[0] < edge[1]
    precursor = edge_map[None].mz['[M+H]+']
    masses[-2:] = precursor
    forward[-1] = True
    return masses, forward, precursor


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


def load_model(root, device_name):
    sys.path[:0] = [str(root / "source_checkout"), str(root / "dependencies")]
    import torch
    from torch_geometric.data import Batch
    from fiora.GNN.FioraModel import FioraModel
    from fiora.GNN.AtomFeatureEncoder import AtomFeatureEncoder
    from fiora.GNN.BondFeatureEncoder import BondFeatureEncoder
    from fiora.GNN.CovariateFeatureEncoder import CovariateFeatureEncoder
    from fiora.MOL.Metabolite import Metabolite
    from fiora.MOL.constants import DEFAULT_MODES
    torch.set_num_threads(4)
    torch.manual_seed(20261115)
    if device_name == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable; no silent CPU replacement")
    device = torch.device(device_name)
    if device.type == "cuda":
        torch.cuda.manual_seed_all(20261115)
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True
    params = read(root / "params.json")
    state = torch.load(root / "state.pt", map_location="cpu", weights_only=True)
    if not isinstance(state, dict) or len(state) != 67 or not all(torch.is_tensor(t) for t in state.values()):
        raise ValueError("Expected pure exact67 tensor deployment state")
    model = FioraModel(copy.deepcopy(params))
    result = model.load_state_dict(state, strict=True)
    del state
    if sum(p.numel() for p in model.parameters()) != 13448861:
        raise ValueError("Expected migrated 13448861-parameter FIORA model")
    model.to(device).eval()
    atoms = AtomFeatureEncoder(feature_list=["symbol", "num_hydrogen", "ring_type"])
    bonds = BondFeatureEncoder(feature_list=["bond_type", "ring_type"])
    categories = params["setup_features_categorical_set"]
    covariates = CovariateFeatureEncoder(feature_list=params["setup_features"], sets_overwrite=categories)
    rt_covariates = CovariateFeatureEncoder(feature_list=params["rt_features"], sets_overwrite=categories)
    if covariates.encoding_dim != 19 or rt_covariates.encoding_dim != 18:
        raise ValueError("Migrated native input dimensions differ")
    load_check = dict(strict=True, state_keys=67, parameters=13448861,
                      missing_keys=list(result.missing_keys), unexpected_keys=list(result.unexpected_keys))

    activity = dict(actual_forward_calls=0)

    def predict(smiles, candidate_index, query):
        mol = Metabolite(smiles)
        mol.create_molecular_structure_graph()
        mol.compute_graph_attributes(atoms, bonds)
        mol.set_id(int(candidate_index))
        mol.add_metadata(dict(name=str(candidate_index), collision_energy=query["collision_energy_ev"],
            instrument="timsTOF", precursor_mode="[M+H]+"), covariates, rt_covariates)
        mol.fragment_MOL(depth=1)
        graph = mol.as_geometric_data(with_labels=False)
        if int(graph.edge_index.shape[1]) > MAX_DIRECTED_EDGES or int(graph.x.shape[0]) > MAX_HEAVY_ATOMS:
            raise ValueError("Native graph exceeds frozen submission budget")
        masses, forward, theoretical = compiled_mass_map(mol, DEFAULT_MODES)
        with torch.inference_mode():
            batch = Batch.from_data_list([graph]).to(device)
            activity["actual_forward_calls"] += 1
            prediction = model(batch)
            raw = prediction["fragment_probs"].detach().cpu().numpy()
            ptr = prediction["segment_ptr"].detach().cpu().tolist()
            if ptr != [0, len(masses)] or raw.ndim != 1 or len(raw) != len(masses) or not NP.isfinite(raw).all():
                raise ValueError("Native graph/output channel binding differs")
            value, channels, peaks = spectral_score(raw, masses, forward, query)
            return dict(score=value, predicted_fragment_channels=channels, measured_fragment_peaks=peaks,
                raw_sha256=hashlib.sha256(raw.tobytes()).hexdigest(), directed_edges=int(graph.edge_index.shape[1]),
                theoretical_candidate_precursor_mz=float(theoretical))
    return predict, load_check, torch, activity


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--submission", required=True, type=Path)
    parser.add_argument("--queries", type=Path)
    parser.add_argument("--asset-root", type=Path)
    parser.add_argument("--asset-manifest-sha")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    parser.add_argument("--mode", choices=("full", "static"), default="full")
    args = parser.parse_args()
    sys.dont_write_bytecode = True
    import pandas as pd
    global NP
    import numpy as NP
    start = time.monotonic()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=False)
    input_path = args.submission.resolve()
    before_sha = sha(input_path)
    control_path = out / "submission_baseline.csv"
    shutil.copy2(input_path, control_path)
    source = pd.read_csv(control_path, dtype=str, keep_default_na=False)
    if source.columns.tolist() != ["molecule_id", "smiles"] or source.molecule_id.duplicated().any() or not len(source):
        raise ValueError("Expected unique ordered final25 molecule_id/smiles rows")
    audit = dict(status="prepared", started_utc=datetime.now(timezone.utc).isoformat(), mode=args.mode,
        script_sha256=sha(__file__), input_sha256=before_sha, baseline_sha256=sha(control_path),
        query_columns_read=QUERY_COLUMNS, labels_read=False, training_performed=False,
        threshold_or_coefficient_search=False, model_invoked=False, rows=len(source),
        policy="step500 same-formula original slots, including rank1; stable original-position ties; no added AB protection",
        spectrum_selection="lexicographically first spectrum_id among supported spectra; source row index breaks duplicate-ID ties",
        supported_conditions=dict(instrument="timsTOF", adduct="[M+H]+", single_finite_ce_ev=[20, 60]),
        graph_budget=dict(heavy_atoms=MAX_HEAVY_ATOMS, directed_edges=MAX_DIRECTED_EDGES,
                          training_max_heavy_atoms=32, training_max_directed_edges=74, submission_extrapolation=True),
        failure_policy="asset/setup failure fatal; unsupported or any competing-candidate failure rolls back whole query",
        public_score=None)
    try:
        if args.mode == "static":
            shutil.copy2(control_path, out / "submission.csv")
            audit.update(status="passed", result="static_original_output_only", output_sha256=sha(out / "submission.csv"),
                supported_queries=0, scored_queries=0, changed_queries=0, checks=dict(original_bytes_exact=True, model_not_invoked=True),
                details=[], elapsed_seconds=time.monotonic() - start)
            save(out / "runtime_audit.json", audit)
            print(json.dumps({k: audit[k] for k in ("status", "mode", "result", "rows", "changed_queries")}), flush=True)
            return
        if args.queries is None or args.asset_root is None:
            raise ValueError("Full inference requires query parquet and frozen asset root")
        asset_root = args.asset_root.resolve()
        manifest, asset_pins = verify_assets(asset_root, args.asset_manifest_sha)
        audit.update(asset_manifest_sha256=args.asset_manifest_sha, parent_checkpoint_sha256=PARENT_CHECKPOINT_PIN,
            model_state_sha256=asset_pins["state.pt"], model_params_sha256=PARAMS_PIN,
            source_commit=SOURCE_COMMIT, queries_sha256=sha(args.queries))
        import rdkit
        from rdkit import RDLogger
        if rdkit.__version__ != "2026.03.3":
            raise RuntimeError("Official RDKit2026.03.3 must be installed before FIORA")
        RDLogger.DisableLog("rdApp.*")
        queries, query_summary = select_queries(args.queries)
        relevant = set(source.molecule_id)
        queries = {mid: row for mid, row in queries.items() if mid in relevant}
        save(out / "selected_queries.json", list(queries.values()))
        audit.update(query_selection=query_summary, supported_queries=len(queries), official_rdkit_version=rdkit.__version__)
        predict, load_check, torch, activity = load_model(asset_root, args.device)
        audit.update(model_loaded=True, model_load_check=load_check)
        if args.device == "cuda":
            torch.cuda.reset_peak_memory_stats()
        destination = []
        details = []
        scores_total = 0
        scored_queries = 0
        with (out / "candidate_scores.jsonl").open("x", encoding="utf-8") as scores_file:
            for row_number, (mid, raw) in enumerate(source.itertuples(index=False, name=None), 1):
                before = raw.split(";")
                if not 1 <= len(before) <= 25 or any(not s for s in before):
                    raise ValueError("Invalid final25 candidate count/content for " + mid)
                after = list(before)
                desc = [describe(s) for s in before]
                reason = None
                if any(item is None for item in desc):
                    reason = "invalid_candidate_identity"
                elif len({item["identity"] for item in desc}) != len(desc):
                    reason = "duplicate_official_identity"
                elif mid not in queries:
                    reason = "no_supported_spectrum"
                slots = defaultdict(list)
                if reason is None:
                    for i, item in enumerate(desc):
                        slots[item["formula"]].append(i)
                competing = [i for indices in slots.values() if len(indices) > 1 for i in indices]
                if reason is None and not competing:
                    reason = "no_same_formula_competition"
                if reason is None and any(desc[i]["heavy_atoms"] > MAX_HEAVY_ATOMS or desc[i]["directed_edges"] > MAX_DIRECTED_EDGES for i in competing):
                    reason = "competing_candidate_exceeds_graph_budget"
                detail = dict(molecule_id=mid, reason=reason, changed=False, candidate_count=len(before),
                    changed_positions=[], candidate_multiset_exact=True, official_identity_multiset_exact=True, formula_slots_exact=True,
                    selected_spectrum_id=queries[mid]["spectrum_id"] if mid in queries else None,
                    score_candidate_count=0, extrapolated_candidates=0)
                values = {}
                if reason is None:
                    try:
                        for i in competing:
                            tick = time.monotonic()
                            scored = predict(before[i], i, queries[mid])
                            if not math.isfinite(scored["score"]):
                                raise ValueError("Nonfinite FIORA candidate score")
                            values[i] = scored["score"]
                            record = dict(molecule_id=mid, spectrum_id=queries[mid]["spectrum_id"], baseline_rank=i + 1,
                                smiles=before[i], formula=desc[i]["formula"], official_identity=desc[i]["identity"],
                                seconds=time.monotonic() - tick, **scored)
                            scores_file.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
                            scores_file.flush()
                            scores_total += 1
                        for indices in slots.values():
                            if len(indices) > 1:
                                ordered = sorted(indices, key=lambda i: (-values[i], i))
                                for destination_index, original_index in zip(indices, ordered):
                                    after[destination_index] = before[original_index]
                        detail.update(reason="scored_same_formula", score_candidate_count=len(values),
                            extrapolated_candidates=sum(desc[i]["heavy_atoms"] > 32 or desc[i]["directed_edges"] > 74 for i in competing))
                        scored_queries += 1
                    except Exception as exc:
                        after = list(before)
                        detail.update(reason="whole_query_fallback_candidate_failure", error_type=type(exc).__name__, error=str(exc),
                                      score_candidate_count=len(values))
                        if args.device == "cuda":
                            torch.cuda.empty_cache()
                if Counter(after) != Counter(before):
                    raise ValueError("FIORA changed candidate multiset")
                if all(item is not None for item in desc):
                    after_desc = [describe(s) for s in after]
                    if Counter(item["identity"] for item in after_desc) != Counter(item["identity"] for item in desc):
                        raise ValueError("FIORA changed official identity multiset")
                    if [item["formula"] for item in after_desc] != [item["formula"] for item in desc]:
                        raise ValueError("FIORA changed per-position formula")
                if detail["reason"] != "scored_same_formula" and after != before:
                    raise ValueError("FIORA fallback changed original candidates")
                detail.update(changed=after != before, changed_positions=[i + 1 for i, (a, b) in enumerate(zip(before, after)) if a != b],
                              scores_consumed=detail["reason"] == "scored_same_formula")
                details.append(detail)
                destination.append((mid, ";".join(after)))
                if row_number <= 2 or row_number % 20 == 0 or row_number == len(source):
                    print(json.dumps(dict(stage="fiora_query_progress", processed=row_number, total=len(source),
                        scored_queries=scored_queries, changed_queries=sum(item["changed"] for item in details),
                        seconds=time.monotonic() - start)), flush=True)
        result = pd.DataFrame(destination, columns=["molecule_id", "smiles"])
        if result.molecule_id.tolist() != source.molecule_id.tolist():
            raise ValueError("FIORA changed molecule order")
        temp = out / "submission.tmp.csv"
        result.to_csv(temp, index=False)
        if not pd.read_csv(temp, dtype=str, keep_default_na=False).equals(result):
            raise ValueError("FIORA output CSV roundtrip differs")
        if sha(input_path) != before_sha or sha(control_path) != before_sha or sha(args.queries) != audit["queries_sha256"]:
            raise ValueError("FIORA frozen input bytes changed during inference")
        verify_assets(asset_root, args.asset_manifest_sha)
        temp.replace(out / "submission.csv")
        import resource
        candidate_failure_queries = sum(item["reason"] == "whole_query_fallback_candidate_failure" for item in details)
        result_status = "applied" if scored_queries else ("all_candidate_attempts_failed" if candidate_failure_queries else "no_eligible")
        audit.update(status="passed", result=result_status, output_sha256=sha(out / "submission.csv"),
            model_invoked=activity["actual_forward_calls"] > 0, actual_forward_calls=activity["actual_forward_calls"],
            candidate_failure_queries=candidate_failure_queries, successful_candidate_inferences=scores_total,
            scored_queries=scored_queries, scored_candidate_rows=scores_total, changed_queries=sum(item["changed"] for item in details),
            changed_top1=sum(1 in item["changed_positions"] for item in details), scores_sha256=sha(out / "candidate_scores.jsonl"),
            selected_queries_sha256=sha(out / "selected_queries.json"), details=details,
            reason_counts=dict(Counter(item["reason"] for item in details)), elapsed_seconds=time.monotonic() - start,
            host_peak_mib=float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) / 1024,
            gpu_peak_allocated_mib=torch.cuda.max_memory_allocated() / 1024 ** 2 if args.device == "cuda" else None,
            checks=dict(baseline_bytes_preserved=True, exact_molecule_order=True, exact_candidate_multiset=True,
                exact_official_identity_multiset=True, exact_formula_slots=True, unsupported_queries_unchanged=True,
                whole_query_failure_fallback=True, csv_roundtrip_exact=True, frozen_inputs_unchanged=True,
                frozen_assets_unchanged=True, labels_not_read=True))
        save(out / "runtime_audit.json", audit)
        print(json.dumps({k: audit[k] for k in ("status", "mode", "result", "rows", "supported_queries", "scored_queries", "changed_queries", "changed_top1", "elapsed_seconds")}), flush=True)
    except BaseException as exc:
        audit.update(status="failed", error_type=type(exc).__name__, error=str(exc), traceback=traceback.format_exc(),
                     elapsed_seconds=time.monotonic() - start)
        save(out / "runtime_audit.json", audit)
        raise


if __name__ == "__main__":
    main()
