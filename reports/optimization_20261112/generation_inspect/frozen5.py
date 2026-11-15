# Locate each mounted dataset by a file it contains (mount paths differ between older and newer notebooks).
import glob, json as _json
from pathlib import Path


def dataset_dir(slug, marker):
    hits = sorted(glob.glob(f'/kaggle/input/**/{slug}/{marker}', recursive=True), key=len)
    return Path(hits[0]).parent if hits else None


V4G = dataset_dir('casmi26-attributed-v4g-reproduction-assets', 'ATTRIBUTION.md')
POP = dataset_dir('casmi26-pubchem-popularity-prior', 'pc_lsid.npy')
PANEL = dataset_dir('casmi26-natural-product-panel-benchmark', 'panel.parquet')
TABLE = dataset_dir('casmi26-natural-product-knowledge-table', 'natural_products.parquet')
FOLD = dataset_dir('casmi26-fold-safe-fpnet', 'MODEL_INPUTS.json')
assert FOLD is not None, 'Attach the updated casmi26-fold-safe-fpnet dataset'