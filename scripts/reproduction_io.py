"""Runtime-only adapters for a verified, shared public-engine spectrum cache.

Does not modify downloaded source files or global numpy. Large numerical arrays
are mapped copy-on-write in the specific library/pool modules that load them.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import sys


def _sha256(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            result.update(chunk)
    return result.hexdigest()


def _portable_source_path(value):
    value = str(value).replace("\\", "/")
    if re.match(r"^[A-Za-z]:/", value):
        return "/mnt/" + value[0].lower() + value[2:]
    return value


class _NumpyCacheProxy:
    def __init__(self, numpy_module, filenames):
        self._numpy = numpy_module
        self._filenames = set(filenames)

    def __getattr__(self, name):
        return getattr(self._numpy, name)

    def load(self, file, *args, **kwargs):
        # Preserve explicit caller policies and non-target loads. No global patch.
        if not args and "mmap_mode" not in kwargs and isinstance(file, (str, os.PathLike)):
            if Path(file).name in self._filenames:
                kwargs["mmap_mode"] = "c"
        return self._numpy.load(file, *args, **kwargs)


def install_shared_cache(code_root, cache_root, mmap_pool=False):
    """Replace cache construction with verified linking; map arrays copy-on-write.

    Call before ``from casmi.build import build_spec_cache`` in the notebook. The
    actual build call still checks its runtime train input and structures against
    the cache receipt. Default mapping affects only the Library CSR arrays.
    """
    import numpy as np
    import pyarrow.parquet as pq

    code_root = Path(code_root).resolve()
    cache_root = Path(cache_root).resolve()
    marker = cache_root / "cache_complete.json"
    cache = json.loads(marker.read_text(encoding="utf-8"))
    if cache.get("status") != "complete" or cache.get("scope") != "full":
        raise ValueError("Shared cache must have a completed full-input receipt")
    sys.path.insert(0, str(code_root))
    build = importlib.import_module("casmi.build")
    library = importlib.import_module("casmi.library")
    if _sha256(build.__file__) != cache["original_build_py"]["sha256"]:
        raise ValueError("Shared cache was built with different source cleaning code")
    for name in ("spectra", "chem"):
        path = Path(build.__file__).with_name(name + ".py")
        if _sha256(path) != cache[f"original_{name}_py_sha256"]:
            raise ValueError(f"Shared cache {name} source differs")
    outputs = {item["name"]: item for item in cache["outputs"]}
    names = ("spec_meta.parquet", "spec_off.npy", "spec_mz.npy", "spec_it.npy")
    for name in names:
        path = cache_root / name
        if not path.is_file() or path.stat().st_size != outputs[name]["bytes"]:
            raise ValueError(f"Missing or size-mismatched shared cache file: {path}")

    def link_cache(train_parquet="data/train.parquet", workdir="work", structs_parquet=None):
        work = Path(workdir).resolve()
        structs = Path(structs_parquet).resolve() if structs_parquet else work / "train_structs.parquet"
        train = Path(train_parquet).resolve()
        if (_portable_source_path(train) != _portable_source_path(cache["train"]["path"])
                or train.stat().st_size != cache["train"]["bytes"]
                or pq.ParquetFile(train).metadata.num_rows != cache["rows"]):
            raise ValueError("Runtime training file differs from the shared cache source")
        if _sha256(structs) != cache["train_structs"]["sha256"]:
            raise ValueError("Runtime training-structure identity/order differs from shared cache")
        work.mkdir(parents=True, exist_ok=True)
        for name in names:
            target = work / name
            source = cache_root / name
            if target.exists() or target.is_symlink():
                if target.resolve() != source:
                    raise FileExistsError(f"Refusing to replace another cache file: {target}")
            else:
                target.symlink_to(source)
        print("SHARED_SPEC_CACHE", json.dumps({"root": str(cache_root), "rows": cache["rows"],
                                               "peaks": cache["peaks"], "work": str(work)}), flush=True)

    # These are module-local references, not assignments to numpy.load globally.
    library.np = _NumpyCacheProxy(np, {"spec_off.npy", "spec_mz.npy", "spec_it.npy"})
    build.build_spec_cache = link_cache
    mapped = {"casmi.library": ["spec_off.npy", "spec_mz.npy", "spec_it.npy"]}
    if mmap_pool:
        pool = importlib.import_module("casmi.pool")
        pool.np = _NumpyCacheProxy(np, {"pool_fp.npy", "pool_frag_off.npy", "pool_frag_mass.npy"})
        mapped["casmi.pool"] = ["pool_fp.npy", "pool_frag_off.npy", "pool_frag_mass.npy"]
    return {"shared_cache": str(cache_root), "cache_rows": cache["rows"], "cache_peaks": cache["peaks"],
            "cache_receipt_sha256": _sha256(marker), "module_local_mmap": mapped,
            "numpy_global_load_unchanged": True, "mmap_mode": "c",
            "algorithm_changes": False,
            "limitations": ["Copy-on-write mmap preserves writeable array semantics without changing cached files.",
                            "Cache file sizes checked on use; full cache hashes retained in builder receipt."]}
