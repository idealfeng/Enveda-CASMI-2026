"""Assemble the Kaggle dataset `casmi26-assets` in data/kaggle_assets/.

The submission notebook runs without internet, so everything it needs is uploaded as a
dataset: the precomputed tables (candidate pool, fingerprints, NP-likeness arrays, training
structure keys), the ranker model, a wheel of the `casmi` package, and Linux wheels of its
third-party dependencies. The latter are downloaded once, for instance with
    pip download rdkit==2026.3.3 ms_entropy==1.5.2 pebble==5.2.2 --only-binary=:all: --no-deps
        --platform manylinux_2_28_x86_64 --python-version 3.12 -d data/kaggle_assets

Then upload, from inside data/kaggle_assets:  kaggle datasets version -p . -m "<message>"
Replace `<kaggle-username>` in dataset-metadata.json and kernel-metadata.json by your Kaggle
username before any upload.
"""
import shutil
import subprocess
from pathlib import Path

import casmi

ASSETS = casmi.paths.data / "kaggle_assets"
FILES = ["candidate_pool.parquet", "candidate_pool_fp.npy", "structures.parquet", "pool_np_scores.npy",
         "pool_np_likeness.npy", "ranker_final.txt"]
THIRD_PARTY = ["rdkit-2026.3.3-", "ms_entropy-1.5.2-", "pebble-5.2.2-"]

if __name__ == "__main__":
    ASSETS.mkdir(parents=True, exist_ok=True)
    for f in FILES:
        shutil.copy2(casmi.paths.processed / f, ASSETS / f)
    shutil.copy2(Path(__file__).with_name("dataset-metadata.json"), ASSETS / "dataset-metadata.json")
    for old in [*ASSETS.glob("casmi-*.whl"), ASSETS / "casmi.py"]:
        old.unlink(missing_ok=True)
    subprocess.run(["uv", "build", "--wheel", "--out-dir", str(ASSETS)], check=True, cwd=casmi.ROOT)
    missing = [p for p in THIRD_PARTY if not list(ASSETS.glob(f"{p}*.whl"))]
    if missing:
        raise SystemExit(f"missing third-party wheels: {missing} (see the docstring)")
    print("\n".join(sorted(p.name for p in ASSETS.iterdir() if p.is_file())))
