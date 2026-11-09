"""Build the public engine's cleaned CSR cache with bounded peak-buffer memory.

Calls the original clean_block, instrument mapping and chemistry functions. It
changes the streaming/writing strategy, not cleaning parameters, dtypes or row order.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import platform
import struct
import sys
import time


COLUMNS = [
    "inchikey14", "ingest_lib", "instrument_type", "adduct", "ionization_mode", "precursor_mz",
    "precursor_error_ppm", "collision_energy_ev", "collision_energy_orig_units",
    "base_peak_intensity", "num_peaks", "ms2_mzs", "ms2_normalized_intensities",
]


def sha256(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            result.update(chunk)
    return result.hexdigest()


class AppendableNpy:
    """Write a standard NPY v2 array without retaining earlier batches.

    A 4096-byte standard-format header reservation makes the final shape update
    independent of its digit count. Loaded values/dtype match np.save; header bytes
    differ from NumPy's usual compact header. np.load(..., mmap_mode='r') works.
    """

    def __init__(self, path: Path, dtype):
        import numpy as np
        self.path = path
        self.dtype = np.dtype(dtype)
        self.count = 0
        self.stream = path.open("wb+")
        self._header()

    def _header(self):
        import numpy as np
        descriptor = repr({"descr": np.lib.format.dtype_to_descr(self.dtype),
                           "fortran_order": False, "shape": (self.count,)})
        raw = descriptor.encode("ascii")
        header_bytes = 4096 - 12
        if len(raw) + 1 > header_bytes:
            raise ValueError("NPY header reservation too short")
        self.stream.seek(0)
        self.stream.write(b"\x93NUMPY\x02\x00" + struct.pack("<I", header_bytes))
        self.stream.write(raw + b" " * (header_bytes - len(raw) - 1) + b"\n")

    def append(self, array):
        import numpy as np
        value = np.asarray(array, dtype=self.dtype).reshape(-1)
        self.stream.seek(0, 2)
        self.stream.write(value.tobytes(order="C"))
        self.count += value.size

    def finish(self):
        self._header()
        self.stream.flush()
        os.fsync(self.stream.fileno())
        self.stream.close()


def load_original(code_root: Path, cache_root: Path):
    cache_root.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("NUMBA_CACHE_DIR", str(cache_root))
    sys.path.insert(0, str(code_root.resolve()))
    return importlib.import_module("casmi.build")


def build_cache(train: Path, structs: Path, output: Path, original, batch_size=4096,
                row_groups=None):
    import numpy as np
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq

    started = time.monotonic()
    output.mkdir(parents=True, exist_ok=True)
    marker = output / "cache_complete.json"
    if marker.exists():
        raise FileExistsError(f"Completed cache already exists; choose a new output or reuse it: {marker}")
    metadata_path = output / "spec_meta.parquet"
    paths = [metadata_path] + [output / f"spec_{name}.npy" for name in ("off", "mz", "it")]
    if any(path.exists() for path in paths):
        raise FileExistsError("Partial/final cache files already exist; use a new output directory")

    table = pd.read_parquet(structs, columns=["inchikey14", "sid"])
    key_to_sid = dict(zip(table.inchikey14, table.sid))
    del table
    parquet = pq.ParquetFile(train)
    selected = list(range(parquet.metadata.num_row_groups)) if row_groups is None else list(row_groups)
    expected_rows = sum(parquet.metadata.row_group(i).num_rows for i in selected)
    sinks = {name: AppendableNpy(output / f"spec_{name}.npy", dtype)
             for name, dtype in (("off", np.int64), ("mz", np.float32), ("it", np.float32))}
    sinks["off"].append(np.array([0], dtype=np.int64))
    writer = None
    total_peaks = 0
    total_rows = 0
    counters = {"sid_negative": 0, "neutral_mass_nan": 0}
    try:
        for batch_number, batch in enumerate(parquet.iter_batches(
                batch_size=batch_size, row_groups=selected, columns=COLUMNS, use_threads=False)):
            chunk = pa.Table.from_batches([batch])
            mz_column = chunk.column("ms2_mzs").combine_chunks()
            intensity_column = chunk.column("ms2_normalized_intensities").combine_chunks()
            offsets = mz_column.offsets.to_numpy().astype(np.int64)
            intensity_offsets = intensity_column.offsets.to_numpy().astype(np.int64)
            if not np.array_equal(np.diff(offsets), np.diff(intensity_offsets)):
                raise ValueError("Unaligned m/z and intensity list lengths")
            first, last = int(offsets[0]), int(offsets[-1])
            first_i, last_i = int(intensity_offsets[0]), int(intensity_offsets[-1])
            mz = mz_column.values.slice(first, last - first).to_numpy(zero_copy_only=False).astype(np.float64)
            intensity = intensity_column.values.slice(first_i, last_i - first_i).to_numpy(
                zero_copy_only=False).astype(np.float64)
            offsets -= first
            precursor = chunk.column("precursor_mz").to_numpy(zero_copy_only=False).astype(np.float64)
            cleaned_offsets, cleaned_mz, cleaned_it = original.clean_block(
                offsets, mz, intensity, precursor, 0.001, 512, 2.0)

            # Same field construction and pandas dtypes as the original builder.
            meta = chunk.drop_columns(["ms2_mzs", "ms2_normalized_intensities"]).to_pandas()
            energy = meta.collision_energy_ev
            meta["ce_mean"] = [float(np.mean(x)) if x is not None and len(x) else np.nan for x in energy]
            meta["ce_min"] = [float(np.min(x)) if x is not None and len(x) else np.nan for x in energy]
            meta["ce_max"] = [float(np.max(x)) if x is not None and len(x) else np.nan for x in energy]
            meta["ce_n"] = [len(x) if x is not None else 0 for x in energy]
            meta = meta.drop(columns=["collision_energy_ev"])
            meta["sid"] = meta.inchikey14.map(key_to_sid).fillna(-1).astype(np.int64)
            meta["lib"] = meta.ingest_lib.map(original.LIB_IX).astype(np.int8)
            meta["instr"] = meta.instrument_type.map(original.instr_family).astype(np.int8)
            meta["adduct_ix"] = meta.adduct.map(original.chem.adduct_index).astype(np.int16)
            meta["mode"] = np.where(meta.ionization_mode == "positive", 1, -1).astype(np.int8)
            meta["nm"] = original.chem.neutral_mass(meta.precursor_mz.values, meta.adduct.values)
            meta["n_clean"] = np.diff(cleaned_offsets).astype(np.int32)
            meta = meta.drop(columns=["inchikey14", "ingest_lib", "instrument_type", "ionization_mode"])
            metadata_table = pa.Table.from_pandas(meta, preserve_index=False)
            if writer is None:
                writer = pq.ParquetWriter(metadata_path, metadata_table.schema)
            writer.write_table(metadata_table)
            sinks["off"].append(cleaned_offsets[1:] + total_peaks)
            sinks["mz"].append(cleaned_mz)
            sinks["it"].append(cleaned_it)
            total_peaks += len(cleaned_mz)
            total_rows += len(meta)
            counters["sid_negative"] += int((meta.sid < 0).sum())
            counters["neutral_mass_nan"] += int(meta.nm.isna().sum())
            if batch_number % 32 == 0 or total_rows == expected_rows:
                print(json.dumps({"batch": batch_number, "rows": total_rows, "peaks": total_peaks,
                                  "elapsed_seconds": round(time.monotonic() - started, 2)}), flush=True)
            del chunk, mz_column, intensity_column, mz, intensity, precursor, meta, metadata_table
            del cleaned_offsets, cleaned_mz, cleaned_it
    finally:
        if writer is not None:
            writer.close()
        for sink in sinks.values():
            sink.finish()

    if total_rows != expected_rows:
        raise RuntimeError(f"Row count mismatch: {total_rows} != {expected_rows}")
    off = np.load(output / "spec_off.npy", mmap_mode="r")
    mz = np.load(output / "spec_mz.npy", mmap_mode="r")
    intensity = np.load(output / "spec_it.npy", mmap_mode="r")
    assert off.dtype == np.int64 and mz.dtype == intensity.dtype == np.float32
    assert len(off) == total_rows + 1 and int(off[-1]) == len(mz) == len(intensity) == total_peaks
    report = {
        "status": "complete", "algorithm": "Original clean_block(0.001, 512, 2.0) and original metadata mapping",
        "rows": total_rows, "peaks": total_peaks, "batch_size": batch_size,
        "scope": "full" if selected == list(range(parquet.metadata.num_row_groups)) else "row_group_subset",
        "row_groups": selected, "elapsed_seconds": round(time.monotonic() - started, 3),
        "python": platform.python_version(), "numpy": np.__version__,
        "train": {"path": str(train.resolve()), "bytes": train.stat().st_size,
                  "rows_in_original": parquet.metadata.num_rows},
        "train_structs": {"path": str(structs.resolve()), "sha256": sha256(structs)},
        "original_build_py": {"path": original.__file__, "sha256": sha256(Path(original.__file__))},
        "original_spectra_py_sha256": sha256(Path(original.__file__).with_name("spectra.py")),
        "original_chem_py_sha256": sha256(Path(original.__file__).with_name("chem.py")),
        "metadata_counters": counters,
        "outputs": [{"name": path.name, "bytes": path.stat().st_size, "sha256": sha256(path)} for path in paths],
        "limitations": ["NPY header and Parquet row-group layout differ; array values, dtypes and metadata are preserved.",
                        "Source train digest is not computed here; size, row count and exact cleaning/structure sources are bound."],
    }
    marker.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def validate_row_group(train: Path, structs: Path, output: Path, original, row_group=20):
    import numpy as np
    import pandas as pd
    import pyarrow.parquet as pq
    output.mkdir(parents=True, exist_ok=True)
    fixture = output / "fixture.parquet"
    pq.write_table(pq.ParquetFile(train).read_row_group(row_group), fixture)
    reference = output / "reference"
    reference.mkdir(exist_ok=True)
    original.build_spec_cache(str(fixture), str(reference), str(structs))
    streamed = output / "streamed"
    report = build_cache(fixture, structs, streamed, original, batch_size=127)
    checks = {}
    for name in ("spec_off.npy", "spec_mz.npy", "spec_it.npy"):
        expected = np.load(reference / name)
        actual = np.load(streamed / name, mmap_mode="r")
        assert expected.dtype == actual.dtype
        assert np.array_equal(expected, actual), name
        checks[name] = {"dtype": str(actual.dtype), "shape": list(actual.shape), "bitwise_array_equal": True}
    pd.testing.assert_frame_equal(pd.read_parquet(reference / "spec_meta.parquet"),
                                  pd.read_parquet(streamed / "spec_meta.parquet"), check_exact=True)
    checks["spec_meta.parquet"] = {"pandas_frame_exact_equal": True}
    result = {"status": "passed", "original_row_group": row_group, "rows": report["rows"],
              "peaks": report["peaks"], "checks": checks, "stream_report": report}
    (output / "equivalence_report.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", required=True, type=Path)
    parser.add_argument("--structs", required=True, type=Path)
    parser.add_argument("--code-root", required=True, type=Path, help="Directory containing the unchanged casmi package")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--batch-size", type=int, default=4096)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--validation-row-group", type=int, default=20)
    args = parser.parse_args()
    if args.batch_size <= 0:
        parser.error("batch-size must be positive")
    args.output = args.output.resolve()
    original = load_original(args.code_root, args.output / "numba_cache")
    if args.validate_only:
        result = validate_row_group(args.train, args.structs, args.output, original, args.validation_row_group)
    else:
        result = build_cache(args.train, args.structs, args.output, original, args.batch_size)
    print(json.dumps({k: result[k] for k in ("status", "rows", "peaks")}), flush=True)


if __name__ == "__main__":
    main()
