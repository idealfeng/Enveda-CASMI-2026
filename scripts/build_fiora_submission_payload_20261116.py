"""Build an ABI-neutral inference payload from fixed FIORA tims500 assets.

No downloads, training, truth labels, notebook edits, or Kaggle mutations.
The verification uses a real candidate/query already scored by the fixed
component inference; it does not evaluate a new ranking or choose a recipe.
"""
from __future__ import annotations

import argparse
import ast
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
ASSET = ROOT / "assets/research/fiora_os_20261115"
MODEL = ROOT / "runs/fiora_tims_model_20261115"
PAYLOAD = ROOT / "submission/optimization_20261116/fiora_payload"
REPORT = ROOT / "reports/optimization_20261116/fiora_payload"
PARENT_SHA = "9c899faa1c45d9a0c25588f99186f34112b25eafe3f6d955a3da34c267996252"
PARAMS_SHA = "1f189efe9fb64f43406bce409b825870655f8b83765c5ee77d3e208e2cbc2418"
SOURCE_COMMIT = "e19ef82c9a6cb9dbac92bce23e914008f1aeb44e"
PURE_DEPENDENCIES = (
    "torch_geometric", "torch_geometric-2.6.1.dist-info",
    "dill", "dill-0.4.0.dist-info", "treelib", "treelib-1.8.0.dist-info",
    "six.py", "six-1.17.0.dist-info",
)


def sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, allow_nan=False, indent=2) + "\n", encoding="utf-8")


def copy_tree(source, target):
    """Preserve package resources and licenses, excluding generated/binary files."""
    if source.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        return
    for path in sorted(source.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or ".git" in path.parts:
            continue
        if path.suffix.lower() in {".pyc", ".pyo", ".so", ".pyd", ".dll", ".exe"}:
            raise ValueError("Refuse nonportable file in pure-Python payload: " + str(path))
        dest = target / path.relative_to(source)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dest)


def build():
    if PAYLOAD.exists():
        raise FileExistsError("Preserve payload; existing output is not overwritten")
    parent = MODEL / "pilot500/last_checkpoint.pt"
    params_path = MODEL / "fiora_OS_tims_migrated_params.json"
    if sha(parent) != PARENT_SHA or sha(params_path) != PARAMS_SHA:
        raise ValueError("Frozen step500 checkpoint or params changed")
    import torch
    checkpoint = torch.load(parent, map_location="cpu", weights_only=True)
    if checkpoint.get("step") != 500 or checkpoint.get("model_params") != read(params_path):
        raise ValueError("Checkpoint step/model-params mismatch")
    state = checkpoint["model_state_dict"]
    if len(state) != 67 or not all(isinstance(v, torch.Tensor) for v in state.values()):
        raise ValueError("Expected all 67 native state tensors")
    PAYLOAD.mkdir(parents=True)
    REPORT.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(params_path, PAYLOAD / "params.json")
    torch.save({k: v.detach().cpu().clone() for k, v in state.items()}, PAYLOAD / "state.pt")
    exported = torch.load(PAYLOAD / "state.pt", map_location="cpu", weights_only=True)
    tensors = []
    for key, original in state.items():
        actual = exported[key]
        if actual.shape != original.shape or actual.dtype != original.dtype or not torch.equal(actual, original.cpu()):
            raise ValueError("Export tensor differs: " + key)
        tensors.append(dict(key=key, shape=list(actual.shape), dtype=str(actual.dtype),
                            sha256=hashlib.sha256(actual.numpy().tobytes()).hexdigest(), equal_to_parent=True))
    native = ASSET / "source_checkout"
    for path in sorted((native / "fiora").rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        target = PAYLOAD / "source_checkout" / path.relative_to(native)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    for name in ("LICENSE", "README.md", "pyproject.toml", "requirements.txt", "constraints.txt"):
        shutil.copyfile(native / name, PAYLOAD / "source_checkout" / name)
    for name in PURE_DEPENDENCIES:
        copy_tree(ASSET / "dependencies-linux" / name, PAYLOAD / "dependencies" / name)
    files = {p.relative_to(PAYLOAD).as_posix(): sha(p) for p in sorted(PAYLOAD.rglob("*")) if p.is_file()}
    manifest = dict(schema_version=1, created_utc=datetime.now(timezone.utc).isoformat(),
                    model_step=500, source_commit=SOURCE_COMMIT, model_family="FIORA-OS explicit timsTOF19",
                    parent_checkpoint_sha256=PARENT_SHA, state_sha256=sha(PAYLOAD / "state.pt"),
                    params_sha256=sha(PAYLOAD / "params.json"), state_tensors=67,
                    trainable_parameters=13448861, files=files,
                    dependency_policy="Only pure Python PyG2.6.1/dill0.4.0/treelib1.8.0/six1.17.0; reuse target native scientific stack; no cp312 binary packages bundled",
                    payload_is_inference_only=True, full_champion_or_kaggle_compatibility_proven=False)
    save(PAYLOAD / "asset_manifest.json", manifest)
    receipt = dict(status="exported_raw_state_all67_tensors_equal_to_parent", parent_checkpoint_sha256=PARENT_SHA,
                   raw_state_sha256=manifest["state_sha256"], params_sha256=PARAMS_SHA,
                   asset_manifest_sha256=sha(PAYLOAD / "asset_manifest.json"), tensor_checks=tensors,
                   payload_files=len(files) + 1, payload_bytes=sum(p.stat().st_size for p in PAYLOAD.rglob("*") if p.is_file()),
                   new_model_training=False, new_public_score=None)
    save(REPORT / "export_receipt.json", receipt)
    print(json.dumps({k: receipt[k] for k in ("status", "raw_state_sha256", "asset_manifest_sha256", "payload_files", "payload_bytes")}), flush=True)


def function_from_file(path, name):
    parsed = ast.parse(path.read_text(encoding="utf-8"))
    node = next(n for n in parsed.body if isinstance(n, ast.FunctionDef) and n.name == name)
    return node


def finalize(canary_root):
    """Add explicitly chosen label-free smoke inputs, then freeze all payload bytes."""
    manifest_path = PAYLOAD / "asset_manifest.json"
    initial = read(manifest_path)
    if initial.get("finalized_for_submission"):
        raise FileExistsError("Finalized manifest is immutable; preserve and create a new payload revision")
    if any(sha(PAYLOAD / relative) != pin for relative, pin in initial["files"].items()):
        raise ValueError("Initial payload changed before finalization")
    if (REPORT / "asset_manifest_initial.json").exists():
        raise FileExistsError("Preserve previous finalization evidence")
    shutil.copyfile(manifest_path, REPORT / "asset_manifest_initial.json")
    canary_files = {}
    for name in ("canary_queries.parquet", "canary_submission.csv"):
        source = canary_root / name
        shutil.copyfile(source, PAYLOAD / name)
        canary_files[name] = dict(source=str(source.relative_to(ROOT)), sha256=sha(source))
    (PAYLOAD / "README.md").write_text(
        "# Private CASMI26 FIORA tims500 inference asset\n\n"
        "This bundle is prepared for the owner's private Kaggle competition notebook. "
        "It contains only the exported step500 inference state, native FIORA source, pure-Python "
        "runtime dependencies, and two label-free official-training development queries for "
        "an offline startup smoke check. It contains no optimizer state, training scripts, "
        "competition test labels, or downloaded NIST model.\n\n"
        "The parent FIORA-OS v1.0.0 release is the MSnLib v7-only model, native source "
        "commit e19ef82c9a6cb9dbac92bce23e914008f1aeb44e. Native FIORA source is MIT "
        "licensed; see source_checkout/LICENSE. Dependency license files are preserved "
        "inside dependencies/*.dist-info/. The MSnLib pretrained model's provenance "
        "must not be confused with the standard FIORA model trained using NIST.\n\n"
        "The explicit timsTOF19 model was adapted by 500 actual optimizer updates on "
        "400 official competition-training structures. A fixed 100-structure development "
        "group was excluded from these updates. Official competition data and derived "
        "query fixtures remain subject to the competition data license and rules; "
        "they are not relicensed as MIT by this bundle. Keep this Kaggle asset private. "
        "MSnLib pretraining exposure to development structures is unknown.\n\n"
        "state.pt contains exactly 67 tensors (13,448,861 parameters), exported "
        "byte-value-equal to the trained parent checkpoint's model_state_dict; "
        "export provenance and all file hashes are in asset_manifest.json and the "
        "local export receipt. No cp312 shared-library dependencies are bundled. "
        "The target must supply compatible torch, RDKit, NumPy, SciPy and the normal "
        "scientific Python stack. Local isolated forward parity does not certify "
        "Kaggle hidden-run success or leaderboard improvement.\n",
        encoding="utf-8")
    initial["finalized_for_submission"] = True
    initial["finalized_utc"] = datetime.now(timezone.utc).isoformat()
    initial["canary_files"] = canary_files
    initial["files"] = {p.relative_to(PAYLOAD).as_posix(): sha(p) for p in sorted(PAYLOAD.rglob("*"))
                        if p.is_file() and p != manifest_path}
    save(manifest_path, initial)
    receipt = dict(status="finalized_payload_with_label_free_canary_and_licenses", created_utc=initial["finalized_utc"],
                   initial_manifest_sha256=sha(REPORT / "asset_manifest_initial.json"),
                   final_manifest_sha256=sha(manifest_path), state_sha256=sha(PAYLOAD / "state.pt"),
                   params_sha256=sha(PAYLOAD / "params.json"), parent_checkpoint_sha256=PARENT_SHA,
                   files=len(initial["files"]) + 1,
                   bytes=sum(p.stat().st_size for p in PAYLOAD.rglob("*") if p.is_file()),
                   canary_files=canary_files, payload_root=str(PAYLOAD.relative_to(ROOT)),
                   no_native_binary_dependencies=not any(p.suffix in {".so", ".pyd", ".dll"} for p in PAYLOAD.rglob("*") if p.is_file()),
                   all_prior_files_unchanged=all(sha(PAYLOAD / rel) == pin for rel, pin in read(REPORT / "asset_manifest_initial.json")["files"].items()))
    save(REPORT / "finalization_receipt.json", receipt)
    print(json.dumps(receipt), flush=True)


def verify():
    tick = time.monotonic()
    if str(ASSET / "dependencies-linux") in sys.path or str(ASSET / "source_checkout") in sys.path:
        raise ValueError("The original dependency target/source must not be on sys.path")
    sys.dont_write_bytecode = True
    sys.path[:0] = [str(PAYLOAD / "source_checkout"), str(PAYLOAD / "dependencies")]
    original = ASSET.resolve()
    if any(original in Path(p).resolve().parents for p in sys.path if p and Path(p).exists()):
        raise ValueError("Original dependency target leaked into inference path")
    manifest = read(PAYLOAD / "asset_manifest.json")
    for relative, pin in manifest["files"].items():
        if sha(PAYLOAD / relative) != pin:
            raise ValueError("Payload file changed: " + relative)
    import numpy as np
    import torch
    import torch_geometric
    from torch_geometric.data import Batch
    from fiora.GNN.FioraModel import FioraModel
    from fiora.GNN.AtomFeatureEncoder import AtomFeatureEncoder
    from fiora.GNN.BondFeatureEncoder import BondFeatureEncoder
    from fiora.GNN.CovariateFeatureEncoder import CovariateFeatureEncoder
    from fiora.MOL.Metabolite import Metabolite
    from fiora.MOL.constants import DEFAULT_MODES
    from rdkit import rdBase, RDLogger
    RDLogger.DisableLog("rdApp.*")
    torch.set_num_threads(4)
    torch.manual_seed(20261115)
    torch.cuda.manual_seed_all(20261115)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    params = read(PAYLOAD / "params.json")
    state = torch.load(PAYLOAD / "state.pt", map_location="cpu", weights_only=True)
    model = FioraModel(copy.deepcopy(params))
    result = model.load_state_dict(state, strict=True)
    if len(state) != 67 or result.missing_keys or result.unexpected_keys or sum(p.numel() for p in model.parameters()) != 13448861:
        raise ValueError("Strict native model shape mismatch")
    model.to("cuda").eval()
    queries = read(ROOT / "runs/fiora_candidate_validation_20261116/queries.json")
    candidates = read(ROOT / "runs/fiora_candidate_validation_20261116/candidates.json")
    row = candidates[0]
    query = next(q for q in queries if q["molecule_id"] == row["molecule_id"])
    old_scores_path = ROOT / "runs/fiora_candidate_validation_20261116/inference/candidate_scores.jsonl"
    with old_scores_path.open(encoding="utf-8") as handle:
        reference = json.loads(next(handle))
    if any(reference[key] != row[key] for key in row):
        raise ValueError("Frozen score/candidate ordering differs")
    atoms = AtomFeatureEncoder(feature_list=["symbol", "num_hydrogen", "ring_type"])
    bonds = BondFeatureEncoder(feature_list=["bond_type", "ring_type"])
    categories = params["setup_features_categorical_set"]
    covariates = CovariateFeatureEncoder(feature_list=params["setup_features"], sets_overwrite=categories)
    rt_covariates = CovariateFeatureEncoder(feature_list=params["rt_features"], sets_overwrite=categories)
    mol = Metabolite(row["smiles"])
    mol.create_molecular_structure_graph()
    mol.compute_graph_attributes(atoms, bonds)
    mol.set_id(int(row["candidate_index"]))
    mol.add_metadata(dict(name=str(row["candidate_index"]), collision_energy=query["collision_energy_ev"],
                          instrument="timsTOF", precursor_mode="[M+H]+"), covariates, rt_covariates)
    mol.fragment_MOL(depth=1)
    graph = mol.as_geometric_data(with_labels=False)
    mass_map_source = ROOT / "scripts/prepare_fiora_tims_pilot_20261115.py"
    scope = {}
    exec(compile(ast.Module(body=[function_from_file(mass_map_source, "compiled_mass_map")], type_ignores=[]), str(mass_map_source), "exec"), scope)
    masses, forward, theoretical = scope["compiled_mass_map"](mol, DEFAULT_MODES)
    with torch.inference_mode():
        prediction = model(Batch.from_data_list([graph]).to("cuda"))
    raw = prediction["fragment_probs"].detach().cpu().numpy()
    score_source = ROOT / "scripts/score_fiora_candidate_validation_20261116.py"
    score_scope = {"NP": np, "math": __import__("math")}
    exec(compile(ast.Module(body=[function_from_file(score_source, "spectral_score")], type_ignores=[]), str(score_source), "exec"), score_scope)
    score, channels, query_peaks = score_scope["spectral_score"](raw, masses, forward, query)
    raw_sha = hashlib.sha256(raw.tobytes()).hexdigest()
    if abs(score - reference["step500_score"]) > 1e-7 or raw_sha != reference["step500_raw_sha256"]:
        mismatch_path = REPORT / "isolated_forward_first_mismatch.json"
        mismatch = dict(status="failed_strict_byte_parity_check", score=score,
             expected_score=reference["step500_score"], raw_sha256=raw_sha, expected_raw_sha256=reference["step500_raw_sha256"],
             rdkit_version=rdBase.rdkitVersion, torch_version=torch.__version__, pyg_version=torch_geometric.__version__,
             graph_edges=int(graph.edge_index.shape[1]), reference_graph_edges=reference["directed_edges"],
             compiled_elements=len(masses), reference_compiled_elements=reference["compiled_elements"],
             candidate_index=row["candidate_index"], molecule_id=row["molecule_id"], asset_manifest_sha256=sha(PAYLOAD / "asset_manifest.json"))
        if not mismatch_path.exists():
            save(mismatch_path, mismatch)
    if abs(score - reference["step500_score"]) > 1e-7:
        raise ValueError("Packaged score differs materially from frozen historical score")
    # Exported tensor identity is exact. CUDA scatter/reduction FP32 execution is
    # checked numerically: a raw-byte hash is retained as provenance, not treated
    # as a cross-process reproducibility guarantee. Do not change computation
    # flags or precision merely to make historical byte hashes match.
    parent_checkpoint = torch.load(MODEL / "pilot500/last_checkpoint.pt", map_location="cpu", weights_only=True)
    parent_state = parent_checkpoint["model_state_dict"]
    parent_tensor_equality = {key: torch.equal(value, parent_state[key]) for key, value in state.items()}
    if not all(parent_tensor_equality.values()):
        raise ValueError("Frozen exported tensors differ from parent checkpoint")
    parent_model = FioraModel(copy.deepcopy(params))
    parent_model.load_state_dict(parent_state, strict=True)
    parent_model.to("cuda").eval()
    cpu_model = FioraModel(copy.deepcopy(params))
    cpu_model.load_state_dict(parent_state, strict=True)
    cpu_model.eval()
    del parent_checkpoint, parent_state
    repeats = []
    with torch.inference_mode():
        for _ in range(3):
            repeated = model(Batch.from_data_list([graph]).to("cuda"))["fragment_probs"].detach().cpu().numpy()
            repeats.append(dict(raw_sha256=hashlib.sha256(repeated.tobytes()).hexdigest(),
                                raw_max_absolute_difference=float(np.max(np.abs(repeated-raw))),
                                score=score_scope["spectral_score"](repeated, masses, forward, query)[0]))
        parent_raw = parent_model(Batch.from_data_list([graph]).to("cuda"))["fragment_probs"].detach().cpu().numpy()
        cpu_raw = cpu_model(Batch.from_data_list([graph]))["fragment_probs"].detach().cpu().numpy()
    comparisons = {}
    for name, other in (("parent_checkpoint_same_cuda", parent_raw), ("parent_checkpoint_cpu", cpu_raw)):
        other_score = score_scope["spectral_score"](other, masses, forward, query)[0]
        comparisons[name] = dict(raw_sha256=hashlib.sha256(other.tobytes()).hexdigest(),
                                raw_max_absolute_difference=float(np.max(np.abs(other-raw))),
                                raw_allclose_atol1e6_rtol1e5=bool(np.allclose(other,raw,atol=1e-6,rtol=1e-5)),
                                score=other_score, score_absolute_difference=abs(other_score-score))
    if not all(item["raw_allclose_atol1e6_rtol1e5"] and item["score_absolute_difference"] <= 1e-7 for item in comparisons.values()):
        raise ValueError("Parent/exported numerical comparison exceeds the explicit FP32 tolerance")
    print(json.dumps(dict(stage="parent_exported_numerical_comparison", historical_score_absdiff=abs(score-reference["step500_score"]), comparisons=comparisons, repeats=repeats)), flush=True)
    imported_paths = {}
    for name in ("fiora", "torch_geometric", "dill", "treelib", "six", "torch", "numpy", "scipy", "rdkit", "aiohttp", "fsspec", "regex", "xxhash"):
        spec = importlib.util.find_spec(name)
        imported_paths[name] = spec.origin if spec else None
    if any(str(original) in str(path) for path in imported_paths.values() if path):
        raise ValueError("Original native source/dependency target supplied a verification import")
    verification = dict(status="completed_isolated_payload_strict_load_real_graph_forward_and_numerical_parity",
                        verified_utc=datetime.now(timezone.utc).isoformat(), parent_checkpoint_sha256=PARENT_SHA,
                        asset_manifest_sha256=sha(PAYLOAD / "asset_manifest.json"), state_sha256=sha(PAYLOAD / "state.pt"),
                        params_sha256=sha(PAYLOAD / "params.json"), state_keys=len(state), strict_missing_keys=list(result.missing_keys),
                        strict_unexpected_keys=list(result.unexpected_keys), parameters=sum(p.numel() for p in model.parameters()),
                        python_version=sys.version, torch_version=torch.__version__, pyg_version=torch_geometric.__version__, rdkit_version=rdBase.rdkitVersion,
                        original_dependency_target_used=False, import_origins=imported_paths,
                        query_molecule_id=row["molecule_id"], query_spectrum_id=row["spectrum_id"], candidate_index=row["candidate_index"],
                        step500_score=score, expected_step500_score=reference["step500_score"], raw_prediction_sha256=raw_sha,
                        expected_raw_prediction_sha256=reference["step500_raw_sha256"], raw_bytes_equal=raw_sha == reference["step500_raw_sha256"],
                        historical_score_absolute_difference=abs(score-reference["step500_score"]), score_absolute_tolerance=1e-7,
                        raw_absolute_tolerance=1e-6, raw_relative_tolerance=1e-5,
                        parent_tensor_equality=parent_tensor_equality, same_gpu_repeated_predictions=repeats, numerical_comparisons=comparisons,
                        computation_flags=dict(torch_threads=torch.get_num_threads(), seed=20261115, cudnn_benchmark=torch.backends.cudnn.benchmark,
                                               cudnn_deterministic=torch.backends.cudnn.deterministic, cuda_matmul_allow_tf32=torch.backends.cuda.matmul.allow_tf32,
                                               cudnn_allow_tf32=torch.backends.cudnn.allow_tf32, float32_matmul_precision=torch.get_float32_matmul_precision(),
                                               deterministic_algorithms_enabled=torch.are_deterministic_algorithms_enabled()),
                        predicted_fragment_channels=channels, measured_fragment_peaks=query_peaks,
                        graph_directed_edges=int(graph.edge_index.shape[1]), prediction_size=len(raw),
                        manifest_files_unchanged=all(sha(PAYLOAD / rel) == pin for rel, pin in manifest["files"].items()),
                        elapsed_seconds=time.monotonic()-tick, labels_read=False, downloaded=False,
                        kaggle_environment_tested=False, full_champion_pipeline_tested=False,
                        boundary="Real isolated local forward and numerical parity against the parent checkpoint and frozen historical score. Exported tensors are exactly equal; CUDA output hashes can differ at FP32 reduction precision. No flags/precision/model/scoring changes were made to reproduce a hash. Not Kaggle ABI certification or a complete champion initialization-to-CSV run.")
    save(REPORT / "isolated_forward_verification.json", verification)
    print(json.dumps({k: verification[k] for k in ("status", "state_keys", "parameters", "step500_score", "raw_bytes_equal", "elapsed_seconds", "import_origins")}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "verify", "finalize", "probe"))
    parser.add_argument("--canary-root", type=Path, default=ROOT / "runs/fiora_submission_canary_20261116/inputs")
    args = parser.parse_args()
    if args.action == "build":
        build()
    elif args.action == "verify":
        verify()
    elif args.action == "finalize":
        finalize(args.canary_root.resolve())
    else:
        print(json.dumps(dict(python=sys.version, modules={n: (s.origin if (s := importlib.util.find_spec(n)) else None) for n in
                         ["torch", "numpy", "scipy", "rdkit", "xxhash", "regex", "aiohttp", "torch_geometric", "fsspec", "dill", "treelib", "six", "psutil", "jinja2"]})))


if __name__ == "__main__":
    main()
