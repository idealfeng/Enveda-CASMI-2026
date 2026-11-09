"""Run Canqiang E006's real FPNet checkpoint on real placeholder-test spectra.

This is a component smoke run, not a reproduction of E006's full ranked output
or its leaderboard score. The upstream notebook and model source stay unchanged.
No network calls, dataset publication, or competition submissions are performed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    here = Path(__file__).resolve().parent
    workspace = here.parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", help="Optionally relaunch with this interpreter.")
    parser.add_argument("--test", type=Path, default=workspace / "enveda-CASMI26-molecule-id-mass-spectra/test.parquet")
    parser.add_argument("--checkpoint", type=Path, default=workspace / "assets/kaggle/ahmedberatozer/casmi26-fpnet-full1/v1/fpnet_full1.pt")
    parser.add_argument("--molecules", type=int, default=3)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument("--output-dir", type=Path, default=here / "runs/fpnet_smoke")
    args = parser.parse_args()
    if args.python and Path(args.python).resolve() != Path(sys.executable).resolve():
        arguments = []
        incoming = iter(sys.argv[1:])
        for argument in incoming:
            if argument == "--python":
                next(incoming)
            elif not argument.startswith("--python="):
                arguments.append(argument)
        raise SystemExit(subprocess.call([args.python, str(Path(__file__).resolve()), *arguments]))
    if args.molecules < 1:
        parser.error("--molecules must be positive")

    source_root = here / "minimal_fpnet_source"
    source_receipt = json.loads((source_root / "download_manifest.json").read_text(encoding="utf-8"))
    for item in source_receipt:
        source_file = here / Path(item["file"].replace("\\", "/"))
        if sha256(source_file) != item["sha256"]:
            raise ValueError(f"Source hash mismatch: {source_file}")

    import numpy as np
    import pandas as pd
    import torch

    sys.path.insert(0, str(source_root))
    from casmi import chem, fpnet

    started = time.monotonic()
    checkpoint_hash = sha256(args.checkpoint)
    receipt_path = args.checkpoint.parent / "download_receipt.json"
    if receipt_path.exists():
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if checkpoint_hash != receipt["sha256"]:
            raise ValueError("Checkpoint hash mismatch")

    device = "cuda" if args.device == "auto" and torch.cuda.is_available() else args.device
    if device == "auto":
        device = "cpu"
    if device == "cuda":
        torch.cuda.reset_peak_memory_stats()

    # The upstream loader uses weights_only=False. This local adapter accepts only
    # the tensor/plain-data checkpoint representation needed for inference.
    def load_model_safely(path, device="cuda"):
        checkpoint = torch.load(path, map_location="cpu", weights_only=True)
        model = fpnet.FPNet(checkpoint["nbits"], d=checkpoint["d"],
                            layers=checkpoint["layers"], heads=checkpoint.get("heads", 8))
        model.load_state_dict(checkpoint["model"], strict=True)
        return model.to(device).eval()

    fpnet.load_model = load_model_safely
    bank = fpnet.ModelBank([str(args.checkpoint)], device=device)
    frame = pd.read_parquet(args.test)
    molecule_ids = sorted(frame["molecule_id"].astype(str).unique())[:args.molecules]
    selected = frame[frame["molecule_id"].astype(str).isin(molecule_ids)].copy()
    selected = selected.sort_values(["molecule_id", "spectrum_id"], kind="stable")
    items = []
    rows = []
    for row in selected.itertuples():
        ce = np.asarray(row.collision_energy_ev, dtype=float).reshape(-1) if row.collision_energy_ev is not None else np.empty(0)
        finite_ce = ce[np.isfinite(ce)]
        mz, intensity = fpnet.prep_peaks(row.ms2_mzs, row.ms2_normalized_intensities, row.precursor_mz)
        items.append(dict(mz=mz, it=intensity, prec=float(row.precursor_mz),
                          adduct_ix=chem.adduct_index(row.adduct),
                          ce=float(finite_ce.mean()) if len(finite_ce) else 0.0,
                          ce_known=float(bool(len(finite_ce))), n_merged=max(1, len(ce)),
                          mode=1.0 if row.ionization_mode == "positive" else -1.0))
        rows.append(dict(molecule_id=str(row.molecule_id), spectrum_id=str(row.spectrum_id),
                         adduct=str(row.adduct), peaks=int(len(mz))))
    logits, elements = bank.logits_el(items, bs=16)
    if not len(items) or not np.isfinite(logits).all() or not np.isfinite(elements).all():
        raise ValueError("Missing spectra or non-finite model output")
    if logits.shape != (len(items), bank.nbits) or float(logits.std()) == 0:
        raise ValueError("Unexpected or constant model output")
    molecule_logits = np.stack([logits[[r["molecule_id"] == mid for r in rows]].mean(axis=0)
                                for mid in molecule_ids])
    args.output_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.output_dir / "logits.npz", logits=logits, elements=elements,
                        molecule_logits=molecule_logits,
                        spectrum_ids=np.asarray([r["spectrum_id"] for r in rows]),
                        molecule_ids=np.asarray(molecule_ids))
    summary = dict(status="component_smoke_passed", scope="FPNet only; no full E006 ranking or score reproduced",
                   visible_test_is_placeholder=True,
                   aggregation="arithmetic mean over single-spectrum logits; E006's merged-view branch is not included",
                   checkpoint=str(args.checkpoint.resolve()), checkpoint_sha256=checkpoint_hash,
                   test=str(args.test.resolve()), source_dataset="ahmedberatozer/casmi26-v3-models/4",
                   python=sys.version.split()[0], torch=torch.__version__, device=device,
                   gpu=torch.cuda.get_device_name(0) if device == "cuda" else None,
                   gpu_peak_allocated_bytes=torch.cuda.max_memory_allocated() if device == "cuda" else None,
                   molecules=len(molecule_ids), spectra=len(rows), fingerprint_bits=int(bank.nbits),
                   logits_shape=list(logits.shape), logits_min=float(logits.min()),
                   logits_max=float(logits.max()), logits_std=float(logits.std()),
                   elapsed_seconds=round(time.monotonic() - started, 3), rows=rows)
    (args.output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "rows"}, indent=2))


if __name__ == "__main__":
    main()
