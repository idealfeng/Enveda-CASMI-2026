"""Prepared fixed 500-step FIORA tims pilot; run only after cache approval.

Native torch/PyG loop, no Fabric or torchmetrics. Seed20261115, batch4,
Adam lr2e-5, FP32, exactly500 optimizer steps, final checkpoint only.
Development is measured at steps0 and500; it selects no parameters/checkpoint.
"""
from __future__ import annotations

import argparse
from collections import Counter
import copy
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
FIORA = ROOT / "assets/research/fiora_os_20261115"
SOURCE = FIORA / "source_checkout"
DEPENDENCIES = FIORA / "dependencies-linux"
SEED, BATCH_SIZE, LEARNING_RATE, STEPS = 20261115, 4, 2e-5, 500
TARGET = "compiled_probsALL"
SPECTRAL_TOLERANCE_DA = 0.01
MIN_PREDICTED_INTENSITY = 0.001
SELECTION_PIN = "2b4ecd92fbf0f175b8533c1678bf693831e9ef1f75bb48084cf32f0169c2213d"
TORCH = None
NP = None


def sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def under_workspace(path):
    path = Path(path).resolve()
    if path == ROOT or not path.is_relative_to(ROOT):
        raise ValueError("All data, weights and outputs must stay in the D-backed project")
    return path


def cache_path(data_root, relative):
    path = (data_root / relative).resolve()
    if not path.is_relative_to(data_root) or not path.is_file():
        raise ValueError("Cache path escapes prepared data root or is missing")
    return path


def rss_mib():
    try:
        import resource
        # Linux ru_maxrss is KiB. This records peak process RSS, not available RAM.
        return float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) / 1024.0
    except ImportError:
        import psutil
        return psutil.Process().memory_info().rss / (1024.0 ** 2)


def graphwise_kl(y_pred, y_true, segment_ptr, weight=None, reduction="mean"):
    """Exact default GraphwiseKLLoss formula from pinned FIORA Losses.py.

    Normalize target and prediction per graph, eps1e-8, KL(target||prediction).
    A native CPU fixture validates value/gradient equivalence before training.
    """
    eps = 1e-8
    if segment_ptr.ndim != 1 or segment_ptr.numel() < 2:
        raise ValueError("GraphwiseKL requires actual per-graph segment boundaries")
    total = y_pred.new_tensor(0.0)
    total_el = 0
    for g in range(segment_ptr.numel() - 1):
        left, right = int(segment_ptr[g].item()), int(segment_ptr[g + 1].item())
        q = y_pred[left:right].clamp_min(eps)
        q = q / q.sum().clamp_min(eps)
        p = y_true[left:right].clamp_min(0.0)
        if weight is not None:
            p = p * weight[left:right].clamp_min(eps)
        p = p / p.sum().clamp_min(eps)
        total = total + (p * (p.clamp_min(eps).log() - q.log())).sum()
        total_el += right - left
    if reduction == "sum":
        return total
    if reduction == "mean_edge":
        return total / max(total_el, 1)
    return total / max(segment_ptr.numel() - 1, 1)


def native_loss_parity():
    """Extract ONLY upstream torch loss class, avoiding torchmetrics import."""
    import ast
    loss_path = SOURCE / "fiora/GNN/Losses.py"
    parsed = ast.parse(loss_path.read_text(encoding="utf-8"))
    node = next(n for n in parsed.body if isinstance(n, ast.ClassDef) and n.name == "GraphwiseKLLoss")
    namespace = {"torch": TORCH}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(loss_path), "exec"), namespace)
    q0 = TORCH.tensor([.1, .2, .7, .4, .6], dtype=TORCH.float64)
    target = TORCH.tensor([0., 2., 1., 5., 0.], dtype=TORCH.float64)
    ptr = TORCH.tensor([0, 3, 5], dtype=TORCH.long)
    q1, q2 = q0.clone().requires_grad_(), q0.clone().requires_grad_()
    native = namespace["GraphwiseKLLoss"]()(q1, target, ptr)
    local = graphwise_kl(q2, target, ptr)
    native.backward()
    local.backward()
    if not TORCH.equal(native, local) or not TORCH.equal(q1.grad, q2.grad):
        raise ValueError("Thin-loop GraphwiseKL differs from pinned native loss")
    return dict(native_loss_sha256=sha(loss_path), exact_value_equal=True, exact_gradient_equal=True,
                normalization="per_graph", direction="target||prediction", eps=1e-8,
                loss_includes_native_duplicate_precursor_channels=True, loss_weights=False)


def load_selection(data_root):
    index = read(data_root / "index.json")
    if index.get("status") != "completed_native_graph_and_label_cache":
        raise ValueError("Native graph/label preparation is incomplete")
    selection_path = data_root / "selection.json"
    if sha(selection_path) != SELECTION_PIN:
        raise ValueError("Metadata-only fixed500 selection changed")
    if index.get("selection_sha256") != SELECTION_PIN:
        raise ValueError("Graph cache is not bound to the frozen metadata selection")
    selection = read(selection_path)
    if selection.get("requested_400_100_achieved") is not True:
        raise ValueError("Metadata selection did not obtain the fixed400/100 groups")
    if not (data_root / "label_contract.json").is_file():
        raise ValueError("Real-fragment supervision contract must be frozen before training")
    contract_path = data_root / "label_contract.json"
    contract = read(contract_path)
    if index.get("label_contract_sha256") != sha(contract_path) or contract.get("selection_sha256") != SELECTION_PIN:
        raise ValueError("Prepared label/selection contract binding differs")
    if contract.get("minimum_real_fragment_matches") != 1 or contract.get("low_coverage_threshold") is not None:
        raise ValueError("Predeclared nonzero real-fragment supervision contract differs")
    preparation_script = ROOT / "scripts/prepare_fiora_tims_pilot_20261115.py"
    if index.get("source_script_sha256") != sha(preparation_script):
        raise ValueError("Actual preparation source differs from graph-cache receipt")
    rows = index["rows"]
    if not isinstance(rows, list) or not rows:
        raise ValueError("Prepared graph index is empty")
    row_binding = lambda r: (r["official_identity"], r["split"], str(r["spectrum_id"]), int(r["source_row"]))
    if {row_binding(r) for r in rows} != {row_binding(r) for r in selection["groups"]} or len(rows) != len(selection["groups"]):
        raise ValueError("Prepared rows do not exactly preserve the pre-match selection")
    identities = {"train": set(), "development": set()}
    splits = Counter()
    for row in rows:
        split, identity = row["split"], row["official_identity"]
        if split not in identities or not isinstance(identity, str) or len(identity) != 14:
            raise ValueError("Unsupported split/official-identity metadata")
        if identity in identities[split]:
            raise ValueError("Expected fixed one-spectrum-per-identity pilot")
        identities[split].add(identity)
        splits[split] += 1
    if identities["train"] & identities["development"]:
        raise ValueError("Train/development official identity overlap")
    if splits != {"train": 400, "development": 100}:
        raise ValueError("Predeclared selection must remain400/100; do not backfill failed graph matches")
    ready = {split: [] for split in identities}
    files = {str(path): sha(path) for path in data_root.glob("*.json")}
    for row in rows:
        if row.get("status") != "cache_ready":
            continue
        for field, digest in (("graph_path", "graph_sha256"), ("eval_path", "eval_sha256")):
            path = cache_path(data_root, row[field])
            if sha(path) != row[digest]:
                raise ValueError("Frozen graph/evaluation cache changed: " + str(path))
            files[str(path)] = row[digest]
        ready[row["split"]].append(row)
    if len(ready["train"]) < BATCH_SIZE or not ready["development"]:
        raise ValueError("Insufficient real graph/label coverage for fixed pilot")
    return index, rows, ready, files


class CacheDataset:
    def __init__(self, data_root, rows, Data):
        self.root, self.rows, self.Data = data_root, rows, Data

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, i):
        row = self.rows[i]
        graph = TORCH.load(cache_path(self.root, row["graph_path"]), map_location="cpu", weights_only=True)
        if not isinstance(graph, dict):
            raise ValueError("Graph cache must be a torch-safe Data.to_dict dictionary")
        # Sidecar/identity/label provenance never becomes an input feature.
        forbidden = {"official_identity", "query_mz", "query_intensity", "compiled_mz", "split", "source_row"}
        if forbidden & graph.keys():
            raise ValueError("Manifest/evaluation metadata found in model Data")
        for name in ("static_graph_features", "static_edge_features"):
            if graph[name].shape[-1] != 19:
                raise ValueError("Expected19-dimensional HCD/tims instrument migration")
        target = graph[TARGET]
        expected = 10 * int(graph["edge_index"].shape[1]) + 2
        if target.ndim != 1 or target.numel() != expected or not bool(TORCH.isfinite(target).all()):
            raise ValueError("Compiled target/edge row binding differs")
        if bool((target < 0).any()) or float(target.sum()) <= 0 or float(target[:-2].sum()) <= 0:
            raise ValueError("Real GraphwiseKL requires nonzero matched nonprecursor supervision")
        return self.Data(**graph), row


def spectral_without_precursor(probabilities, sidecar):
    """Actual reconstructed m/z spectral cosine; sidecar never enters model."""
    from fiora.MS.spectral_scores import spectral_cosine
    with NP.load(sidecar, allow_pickle=False) as value:
        mz = value["compiled_mz"]
        mask = value["compiled_forward_mask"].astype(bool)
        query_mz, query_intensity = value["query_mz"], value["query_intensity"]
        query_nonprecursor_mask = value["query_nonprecursor_mask"].astype(bool)
        precursor = float(NP.asarray(value["precursor_mz"]).reshape(-1)[0])
    if probabilities.shape != mz.shape or mask.shape != mz.shape:
        raise ValueError("Compiled spectral m/z/probability row binding differs")
    if not math.isfinite(precursor) or len(query_mz) != len(query_intensity):
        raise ValueError("Invalid evaluation peak sidecar")
    if query_nonprecursor_mask.shape != query_mz.shape:
        raise ValueError("Measured nonprecursor mask and peaks differ")
    precursor_removal_da = max(0.01, abs(precursor)*100e-6)
    keep = mask & NP.isfinite(mz) & (probabilities > MIN_PREDICTED_INTENSITY)
    keep[-2:] = False
    keep &= NP.abs(mz - precursor) > precursor_removal_da
    qkeep = NP.isfinite(query_mz) & NP.isfinite(query_intensity) & (query_intensity > 0)
    qkeep &= query_nonprecursor_mask
    qkeep &= NP.abs(query_mz - precursor) > precursor_removal_da
    if not keep.any() or not qkeep.any():
        return 0.0
    # Remove precursor explicitly before native cosine, avoiding its bin0 bug.
    predicted = dict(mz=mz[keep].astype(float).tolist(), intensity=probabilities[keep].astype(float).tolist())
    measured = dict(mz=query_mz[qkeep].astype(float).tolist(), intensity=query_intensity[qkeep].astype(float).tolist())
    score = float(spectral_cosine(measured, predicted, tolerance=SPECTRAL_TOLERANCE_DA, transform=NP.sqrt))
    if not math.isfinite(score):
        raise ValueError("Nonfinite reconstructed spectral cosine")
    return score


def validate_output(prediction, batch):
    p, ptr, target = prediction["fragment_probs"], prediction["segment_ptr"], batch[TARGET]
    if p.ndim != 1 or p.shape != target.shape or not bool(TORCH.isfinite(p).all()):
        raise ValueError("Invalid FIORA probabilities or target alignment")
    values = ptr.detach().cpu().tolist()
    if len(values) != batch.num_graphs + 1 or values[0] != 0 or values[-1] != p.numel():
        raise ValueError("Actual per-graph segment_ptr differs")
    if any(b - a < 2 or (b - a - 2) % 10 for a, b in zip(values[:-1], values[1:])):
        raise ValueError("Malformed per-graph fragment/precursor partition")
    return p, ptr, target


def evaluate(model, loader, data_root, device, step, selected_count):
    model.eval()
    records = []
    with TORCH.no_grad():
        for batch, rows in loader:
            batch = batch.to(device)
            p, ptr, target = validate_output(model(batch), batch)
            indices = ptr.detach().cpu().tolist()
            for row, left, right in zip(rows, indices[:-1], indices[1:]):
                pred, label = p[left:right], target[left:right]
                local_ptr = TORCH.tensor([0, right-left], device=device, dtype=TORCH.long)
                kl = float(graphwise_kl(pred, label, local_ptr).item())
                pf, tf = pred[:-2], label[:-2]
                denom = float((pf.norm() * tf.norm()).item())
                cosine = float(TORCH.dot(pf, tf).item()) / denom if denom > 0 else 0.0
                spectrum = spectral_without_precursor(pred.detach().cpu().numpy(), cache_path(data_root, row["eval_path"]))
                records.append(dict(official_identity=row["official_identity"], graph_path=row["graph_path"],
                                    kl=kl, fragment_channel_cosine_without_precursor=cosine,
                                    physical_sqrt_spectral_cosine_without_precursor=spectrum))
    if not records:
        raise ValueError("Development evaluation has no usable real graph labels")
    return dict(step=step, selected_official_groups=selected_count, evaluated_official_groups=len(records),
                excluded_unmatched_groups=selected_count-len(records),
                kl_valid_group_mean=statistics.mean(r["kl"] for r in records),
                full_selected_denominator_kl=statistics.mean(r["kl"] for r in records) if len(records)==selected_count else None,
                fragment_channel_cosine_valid_mean=statistics.mean(r["fragment_channel_cosine_without_precursor"] for r in records),
                physical_sqrt_spectral_cosine_valid_mean=statistics.mean(r["physical_sqrt_spectral_cosine_without_precursor"] for r in records),
                physical_sqrt_spectral_cosine_selected_denominator_missing_as_zero=sum(r["physical_sqrt_spectral_cosine_without_precursor"] for r in records)/selected_count,
                rows=records, scores_select_checkpoint_or_parameters=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=ROOT / "runs/fiora_tims_pilot_20261115")
    parser.add_argument("--model-root", type=Path, default=ROOT / "runs/fiora_tims_model_20261115")
    parser.add_argument("--output", type=Path, default=ROOT / "runs/fiora_tims_model_20261115/pilot500")
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    args = parser.parse_args()
    data_root, model_root, out = map(under_workspace, (args.data_root, args.model_root, args.output))
    if out.exists() or out.is_relative_to(data_root):
        raise ValueError("Use a fresh output directory outside frozen data cache")
    out.mkdir(parents=True, exist_ok=False)
    step, checkpoint_written = 0, False
    try:
        global TORCH, NP
        sys.dont_write_bytecode = True
        sys.path.insert(0, str(DEPENDENCIES))
        sys.path.insert(0, str(SOURCE))
        import numpy as NP
        import torch as TORCH
        from torch_geometric.data import Batch, Data
        from fiora.GNN.FioraModel import FioraModel
        index, selected, ready, cache_bindings = load_selection(data_root)
        params_path = model_root / "fiora_OS_tims_migrated_params.json"
        state_path = model_root / "fiora_OS_tims_migrated_state.pt"
        receipt_path = model_root / "migration_receipt.json"
        receipt = read(receipt_path)
        if receipt.get("status") != "MIGRATED_STRICT_HCD_PARITY_PASSED":
            raise ValueError("19-dimensional migration has not passed strict HCD parity")
        if receipt.get("migrated_params_sha256") != sha(params_path) or receipt.get("migrated_state_sha256") != sha(state_path):
            raise ValueError("Migrated model/params receipt binding differs")
        if receipt.get("strict_missing_keys") != [] or receipt.get("strict_unexpected_keys") != []:
            raise ValueError("Migration strict load did not pass")
        if not isinstance(receipt.get("HCD_max_abs_delta"), (int, float)) or receipt["HCD_max_abs_delta"] > 1e-6:
            raise ValueError("Migration HCD prediction parity did not pass")
        params = read(params_path)
        if params.get("static_feature_dimension") != 19 or params.get("training_label") != TARGET:
            raise ValueError("Wrong migrated model/input or prediction target")
        if "timsTOF" not in params.get("setup_features_categorical_set", {}).get("instrument", []):
            raise ValueError("Migrated model instrument vocabulary does not include timsTOF")
        random.seed(SEED)
        NP.random.seed(SEED)
        TORCH.manual_seed(SEED)
        TORCH.set_num_threads(4)
        if args.device == "cuda":
            if not TORCH.cuda.is_available():
                raise RuntimeError("CUDA unavailable; no automatic CPU replacement")
            TORCH.cuda.manual_seed_all(SEED)
            TORCH.backends.cudnn.benchmark = False
            TORCH.backends.cudnn.deterministic = True
        device = TORCH.device(args.device)
        model = FioraModel(copy.deepcopy(params))
        state = TORCH.load(state_path, map_location="cpu", weights_only=True)
        model.load_state_dict(state, strict=True)
        model.to(device)
        trainable = [parameter for parameter in model.parameters() if parameter.requires_grad]
        parameter_count = sum(p.numel() for p in model.parameters())
        trainable_count = sum(p.numel() for p in trainable)
        if parameter_count != receipt.get("migrated_parameters") or len(state) != receipt.get("state_keys"):
            raise ValueError("Migrated parameter/tensor count differs from frozen receipt")
        if not trainable:
            raise ValueError("No trainable model parameters")
        native_loss = native_loss_parity()
        optimizer = TORCH.optim.Adam(trainable, lr=LEARNING_RATE)
        initial_rng = TORCH.Generator().manual_seed(SEED)

        def collate(values):
            graphs, rows = zip(*values)
            return Batch.from_data_list(list(graphs)), list(rows)

        train_loader = TORCH.utils.data.DataLoader(CacheDataset(data_root, ready["train"], Data),
            batch_size=BATCH_SIZE, shuffle=True, drop_last=True, num_workers=0,
            collate_fn=collate, generator=initial_rng)
        dev_loader = TORCH.utils.data.DataLoader(CacheDataset(data_root, ready["development"], Data),
            batch_size=BATCH_SIZE, shuffle=False, drop_last=False, num_workers=0, collate_fn=collate)
        source_files = [Path(__file__), SOURCE / "fiora/GNN/FioraModel.py", SOURCE / "fiora/GNN/Losses.py",
                        SOURCE / "fiora/MS/spectral_scores.py", SOURCE / "fiora/MS/SimulationFramework.py",
                        ROOT / "scripts/prepare_fiora_tims_pilot_20261115.py", params_path, state_path, receipt_path]
        source_files += list((SOURCE / "fiora/GNN").rglob("*.py"))
        source_files += list((SOURCE / "fiora/MOL").rglob("*.py"))
        frozen = cache_bindings | {str(path): sha(path) for path in source_files}
        config = dict(status="fixed_pilot_predeclared", seed=SEED, batch_size=BATCH_SIZE,
            optimizer="Adam", learning_rate=LEARNING_RATE, optimizer_steps=STEPS, dtype="float32",
            target=TARGET, loss=native_loss, model_root=str(model_root), data_root=str(data_root),
            checkpoint_policy="last_step500_only_no_dev_selection", development_steps=[0, 500],
            selected_groups=dict(Counter(r["split"] for r in selected)),
            usable_groups={key:len(value) for key,value in ready.items()},
            match_failures_do_not_trigger_replacement=True, development_denominator=100,
            graph_metadata_not_model_features=True, total_parameters=parameter_count,
            trainable_parameters=trainable_count, device=str(device),
            gpu_name=TORCH.cuda.get_device_name() if device.type=="cuda" else None,
            model_parameter_bytes=sum(p.numel()*p.element_size() for p in model.parameters()),
            spectral_evaluation=dict(channel_mz_sidecar=True, precursor_removed_before_cosine=True,
                tolerance_da=SPECTRAL_TOLERANCE_DA, transform="sqrt", native_forward_edges_only=True,
                min_predicted_intensity=MIN_PREDICTED_INTENSITY, empty_fragment_spectrum_score=0.0,
                measured_mask="frozen_sidecar_query_nonprecursor_mask",
                precursor_removal_da="max(.01,100ppm*abs(theoretical_precursor))",
                binning="native spectral_cosine adjacent-bin chaining; not strict one-to-one matching"),
            original_source_modified=False, new_public_score=None)
        save(out / "configuration.json", config)
        save(out / "input_bindings_before_training.json", frozen)
        start = time.monotonic()
        dev0 = evaluate(model, dev_loader, data_root, device, 0, 100)
        save(out / "development_step000.json", dev0)
        if device.type == "cuda":
            TORCH.cuda.reset_peak_memory_stats()
        log_path = out / "steps.jsonl"
        model.train()
        timings, finite_steps, nonzero_grad_steps = [], 0, 0
        while step < STEPS:
            for batch, rows in train_loader:
                if step == STEPS:
                    break
                if device.type == "cuda":
                    TORCH.cuda.synchronize()
                tick = time.monotonic()
                optimizer.zero_grad(set_to_none=True)
                batch = batch.to(device)
                pred, ptr, label = validate_output(model(batch), batch)
                loss = graphwise_kl(pred, label, ptr)
                if not bool(TORCH.isfinite(loss)):
                    raise FloatingPointError("Nonfinite real GraphwiseKL")
                loss.backward()
                grads = [p.grad for p in trainable if p.grad is not None]
                if not grads or not all(bool(TORCH.isfinite(g).all()) for g in grads):
                    raise FloatingPointError("Missing or nonfinite trainable gradient")
                grad_squared = sum(float(TORCH.sum(g.detach().float()**2).item()) for g in grads)
                if not math.isfinite(grad_squared):
                    raise FloatingPointError("Nonfinite aggregate gradient norm")
                finite_steps += 1
                nonzero_grad_steps += grad_squared > 0
                optimizer.step()
                step += 1
                if device.type == "cuda":
                    TORCH.cuda.synchronize()
                elapsed = time.monotonic() - tick
                timings.append(elapsed)
                row = dict(optimizer_step=step, loss=float(loss.item()), seconds=elapsed,
                    batch_graphs=batch.num_graphs, gradient_finite=True, gradient_l2=math.sqrt(grad_squared),
                    gradients_present=len(grads), trainable_tensors=len(trainable), rss_peak_mib=rss_mib(),
                    gpu_peak_allocated_mib=TORCH.cuda.max_memory_allocated()/1024**2 if device.type=="cuda" else None)
                with log_path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(row, allow_nan=False)+"\n")
                if step in (1, 10, 50, 100, 250, 500):
                    print(json.dumps(row), flush=True)
        # A fixed last-step checkpoint is saved before examining final dev scores.
        final_state = {key:value.detach().cpu() for key,value in model.state_dict().items()}
        TORCH.save(dict(model_state_dict=final_state, optimizer_state_dict=optimizer.state_dict(),
                        step=STEPS, model_params=params, training_configuration=config,
                        torch_rng_state=TORCH.get_rng_state()), out / "last_checkpoint.pt")
        checkpoint_written = True
        dev500 = evaluate(model, dev_loader, data_root, device, 500, 100)
        save(out / "development_step500.json", dev500)
        if any(sha(Path(path)) != pin for path,pin in frozen.items()):
            raise ValueError("Frozen model, source or training/cache bytes changed")
        stable = timings[50:]
        parameter_delta = math.sqrt(sum(float(((final_state[key]-value.detach().cpu()).float()**2).sum().item())
                                        for key,value in state.items() if value.is_floating_point()))
        result = dict(status="completed_fixed500_real_fiora_graphwise_kl", optimizer_steps=step,
            checkpoint_sha256=sha(out / "last_checkpoint.pt"), last_only=True, dev_checkpoint_selection=False,
            configuration_sha256=sha(out / "configuration.json"),
            input_bindings_sha256=sha(out / "input_bindings_before_training.json"),
            graphwise_kl_native_value_gradient_parity=native_loss, native_label_target=TARGET,
            total_parameters=parameter_count, trainable_parameters=trainable_count,
            all500_gradient_steps_finite=finite_steps==500, nonzero_gradient_steps=nonzero_grad_steps,
            parameter_update_l2=parameter_delta, total_seconds=time.monotonic()-start,
            stable_steps_51_to_500=dict(count=len(stable), median_seconds=statistics.median(stable),
                mean_seconds=statistics.mean(stable), p90_seconds=float(NP.percentile(stable,90))),
            rss_peak_mib=rss_mib(), gpu_peak_allocated_mib=TORCH.cuda.max_memory_allocated()/1024**2 if device.type=="cuda" else None,
            gpu_peak_reserved_mib=TORCH.cuda.max_memory_reserved()/1024**2 if device.type=="cuda" else None,
            development_step0={k:v for k,v in dev0.items() if k!="rows"},
            development_step500={k:v for k,v in dev500.items() if k!="rows"},
            new_public_score=None, ranking_improvement=None,
            boundary="This is fixed real forward-spectrum fine-tuning and speed/coverage evidence. Development is not a search set. No candidate-ranking gain, hidden class proportions or Kaggle score is inferred.")
        if step != 500 or finite_steps != 500 or parameter_delta <= 0:
            raise ValueError("Fixed optimizer update evidence failed")
        save(out / "verification.json", result)
        print(json.dumps({k:result[k] for k in ("status","optimizer_steps","stable_steps_51_to_500","parameter_update_l2")}),flush=True)
    except BaseException as exc:
        save(out / "failure.json", dict(status="failed_fixed_fiora_pilot", optimizer_steps_completed=step,
            final_checkpoint_written=checkpoint_written, error_type=type(exc).__name__, error=str(exc),
            traceback=traceback.format_exc(), failed_at_utc=datetime.now(timezone.utc).isoformat()))
        raise


if __name__ == "__main__":
    main()
