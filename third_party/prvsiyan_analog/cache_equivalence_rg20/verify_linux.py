"""Compare the Windows-built fixture cache with unchanged Linux source output."""
import json
import os
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import numba
import rdkit

fixture = Path(__file__).resolve().parent
root = fixture.parents[2]
code = root / "assets/kaggle/ahmedberatozer/casmi26-v4b-models/v4/code"
structs = root / "assets/kaggle/ahmedberatozer/casmi26-v2-pool/v1/train_structs.parquet"
reference = fixture / "reference_linux"
reference.mkdir(exist_ok=True)
os.environ["NUMBA_CACHE_DIR"] = str(reference / "numba_cache")
sys.path.insert(0, str(code))
from casmi.build import build_spec_cache

build_spec_cache(str(fixture / "fixture.parquet"), str(reference), str(structs))
checks = {}
for name in ("spec_off.npy", "spec_mz.npy", "spec_it.npy"):
    expected = np.load(reference / name)
    actual = np.load(fixture / "streamed" / name, mmap_mode="c")
    assert expected.dtype == actual.dtype
    assert np.array_equal(expected, actual), name
    checks[name] = {"dtype": str(actual.dtype), "shape": list(actual.shape), "bitwise_array_equal": True}
pd.testing.assert_frame_equal(pd.read_parquet(reference / "spec_meta.parquet"),
                              pd.read_parquet(fixture / "streamed" / "spec_meta.parquet"), check_exact=True)
checks["spec_meta.parquet"] = {"pandas_frame_exact_equal": True}
sys.path.insert(0, str(root / "scripts"))
from reproduction_io import install_shared_cache
from casmi import build as build_module
original_numpy_load = np.load
io_report = install_shared_cache(code, fixture / "streamed", mmap_pool=True)
linked = fixture / "linked_linux"
build_module.build_spec_cache(str(fixture / "fixture.parquet"), str(linked), str(structs))
assert np.load is original_numpy_load
assert all((linked / name).is_symlink() for name in ("spec_meta.parquet", "spec_off.npy", "spec_mz.npy", "spec_it.npy"))
checks["shared_cache_linking"] = {"windows_to_linux_provenance_verified": True,
                                  "four_files_linked": True, "global_numpy_load_unchanged": True}
report = {"status": "passed", "linux_numpy": np.__version__, "linux_numba": numba.__version__,
          "linux_rdkit": rdkit.__version__, "checks": checks,
          "scope": "Linux unchanged original builder versus Windows streamed fixture, row group 20"}
(fixture / "cross_platform_equivalence_report.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report), flush=True)
