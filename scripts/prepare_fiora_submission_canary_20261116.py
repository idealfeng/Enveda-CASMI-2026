"""Prepare tiny label-free packaging canary without reading any score/truth file."""
from collections import defaultdict
import hashlib
import json
from pathlib import Path


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def main():
    import pandas as pd
    root = Path(__file__).resolve().parents[1]
    data = root / "runs/fiora_candidate_validation_20261116"
    out = root / "runs/fiora_submission_canary_20261116/inputs"
    out.mkdir(parents=True, exist_ok=False)
    queries_path, candidates_path = data / "queries.json", data / "candidates.json"
    queries = json.loads(queries_path.read_text(encoding="utf-8"))
    candidates = json.loads(candidates_path.read_text(encoding="utf-8"))
    selected_ids = sorted(row["molecule_id"] for row in queries)[:2]
    by_mid = defaultdict(list)
    for row in candidates:
        if row["molecule_id"] in selected_ids and len(by_mid[row["molecule_id"]]) < 25:
            by_mid[row["molecule_id"]].append(row["smiles"])
    clean_queries = []
    for row in queries:
        if row["molecule_id"] in selected_ids:
            clean_queries.append({
                "molecule_id": row["molecule_id"], "spectrum_id": row["spectrum_id"],
                "instrument_type": row["instrument_type"], "adduct": row["adduct"],
                "collision_energy_ev": [float(row["collision_energy_ev"])],
                "precursor_mz": float(row["measured_precursor_mz"]),
                "ms2_mzs": row["ms2_mzs"], "ms2_normalized_intensities": row["ms2_normalized_intensities"],
            })
    clean_queries.sort(key=lambda row: row["molecule_id"])
    pd.DataFrame(clean_queries).to_parquet(out / "canary_queries.parquet", index=False)
    pd.DataFrame([(mid, ";".join(by_mid[mid])) for mid in selected_ids], columns=["molecule_id", "smiles"]).to_csv(out / "canary_submission.csv", index=False)
    receipt = dict(status="prepared_without_labels_or_prediction_reads", selected_ids=selected_ids,
        selection="First two lexicographic molecule_ids of frozen original100; first25 pool candidates each, before scores; no truth injection or score-based selection",
        source_files={str(queries_path.relative_to(root)): sha(queries_path), str(candidates_path.relative_to(root)): sha(candidates_path)},
        outputs={name: sha(out / name) for name in ("canary_queries.parquet", "canary_submission.csv")},
        candidate_counts={mid: len(by_mid[mid]) for mid in selected_ids}, public_score=None,
        boundary="Packaging/actual-forward/score-consumption canary only; not champion initialization or efficacy validation")
    (out / "preparation_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt), flush=True)


if __name__ == "__main__":
    main()
