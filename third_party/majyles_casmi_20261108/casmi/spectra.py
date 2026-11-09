"""Spectrum cleaning, the reference library and spectral library search (FlashEntropy).

Libraries of spectra are stored flat: all peaks end to end (`mz`, `intensity`) and
`offsets`, such that the peaks of spectrum i are in [offsets[i], offsets[i + 1]).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from .data import neutral_mass
from .paths import paths

# Cleaning settings (those recommended by the authors of the entropy similarity):
#   - drop everything above precursor - 1.6 Da (the precursor and its isotopes say nothing
#     about the structure: its mass is already known);
#   - drop peaks below 1 % of the base peak (noise);
#   - merge peaks closer than 0.05 Da (centroiding duplicates);
#   - normalize intensities to sum to 1.
CLEAN_PARAMS = dict(noise_threshold=0.01, min_ms2_difference_in_da=0.05)


def clean_peaks(mzs, intensities, precursor_mz: float, **params) -> np.ndarray:
    """Cleaned spectrum, as a float32 array of shape (n_peaks, 2): [m/z, intensity]."""
    from ms_entropy import clean_spectrum

    peaks = np.column_stack([mzs, intensities]).astype(np.float32)
    return clean_spectrum(peaks, min_mz=-1, max_mz=precursor_mz - 1.6, max_peak_num=None,
                          normalize_intensity=True, **{**CLEAN_PARAMS, **params})


def _flat_library(peak_list: list[np.ndarray]) -> dict:
    return {"mz": np.concatenate([p[:, 0] for p in peak_list]).astype(np.float32),
            "intensity": np.concatenate([p[:, 1] for p in peak_list]).astype(np.float32),
            "offsets": np.concatenate([[0], np.cumsum([len(p) for p in peak_list])]).astype(np.int64)}


def _clean_all(precursors, mzs, intensities) -> list[np.ndarray]:
    return [clean_peaks(mz, it, prec) if len(mz) else np.zeros((0, 2), np.float32)
            for prec, mz, it in zip(precursors, mzs, intensities)]


def build_clean_library() -> dict:
    """Clean the 2.5 M training spectra and store them flat (cached on disk).

    The parquet file is read one row group at a time, never loading the 3 GB of peaks at once.
    """
    path = paths.processed / "library_clean.npz"
    if path.exists():
        return dict(np.load(path))
    pf = pq.ParquetFile(paths.train)
    peak_list = []
    for rg in range(pf.metadata.num_row_groups):
        table = pf.read_row_group(rg, columns=["precursor_mz", "ms2_mzs", "ms2_normalized_intensities"])
        peak_list += _clean_all(table.column("precursor_mz").to_numpy(), table.column("ms2_mzs").to_pylist(),
                                table.column("ms2_normalized_intensities").to_pylist())
        print(f"row group {rg + 1}/{pf.metadata.num_row_groups}", flush=True)
    library = _flat_library(peak_list)
    np.savez(path, **library)
    return library


def clean_query_spectra(df: pd.DataFrame) -> dict:
    """Clean the spectra of a DataFrame (e.g. the test set) into the library format.

    The spectrum of row i of the DataFrame becomes entry i: queries must therefore carry a
    `row` column = 0, 1, 2… (position in `df`).
    """
    return _flat_library(_clean_all(df["precursor_mz"], df["ms2_mzs"], df["ms2_normalized_intensities"]))


def library_peaks(library: dict, i: int) -> np.ndarray:
    """Cleaned peaks of spectrum i of a library, as an (n, 2) array."""
    a, b = library["offsets"][i], library["offsets"][i + 1]
    return np.column_stack([library["mz"][a:b], library["intensity"][a:b]])


class SpectralIndex:
    """Entropy-similarity search (FlashEntropy) over the whole library.

    One index per polarity. The index's "precursor" field holds the **neutral mass** of the
    structure, not the measured m/z: an [M+H]+ and an [M+Na]+ spectrum of the same molecule
    thus fall into the same mass window.

    `search` returns, for one query, similarities aligned on the index entries;
    `self.rows[polarity]` gives the training row of each entry.
    """

    def __init__(self, library: dict, meta: pd.DataFrame, cache_name: str | None = "index_full"):
        from ms_entropy import FlashEntropySearch

        self.engines, self.rows = {}, {}
        cache = paths.processed / cache_name if cache_name else None
        if cache is not None and (cache / "negative_rows.npy").exists():
            for polarity in ["positive", "negative"]:
                engine = FlashEntropySearch()
                engine.read(cache / polarity)
                self.engines[polarity] = engine
                self.rows[polarity] = np.load(cache / f"{polarity}_rows.npy")
            return

        # Every training row is indexed: references are filtered at search time (`allowed`)
        rows = np.arange(len(meta))
        for polarity in ["positive", "negative"]:
            sel = rows[(meta["ionization_mode"].to_numpy() == polarity)
                       & np.isfinite(meta["exact_mass"].to_numpy())]
            spectra = [
                {"precursor_mz": float(meta["exact_mass"].iat[r]), "peaks": library_peaks(library, r),
                 "row": int(r)}
                for r in sel
            ]
            spectra = [s for s in spectra if len(s["peaks"])]
            engine = FlashEntropySearch()
            # build_index sorts the spectra by mass: read the order back from the returned list
            spectra = engine.build_index(spectra, clean_spectra=False)
            self.engines[polarity] = engine
            self.rows[polarity] = np.array([s["row"] for s in spectra])
            if cache is not None:
                engine.write(cache / polarity)
                np.save(cache / f"{polarity}_rows.npy", self.rows[polarity])

    def search(self, peaks: np.ndarray, neutral_mass: float, polarity: str,
               method: str = "identity", ppm: float = 10.0, ms2_da: float = 0.02) -> np.ndarray:
        """Similarities (0 to 1) of the query with every spectrum of its polarity's index.

        method: "identity" (same neutral mass, within ±ppm) or "hybrid" (any mass: shared peaks
        OR peaks shifted by the mass difference, to find analogs).
        """
        engine = self.engines[polarity]
        if method == "identity":
            return engine.identity_search(precursor_mz=neutral_mass, peaks=peaks,
                                          ms1_tolerance_in_da=neutral_mass * ppm * 1e-6,
                                          ms2_tolerance_in_da=ms2_da)
        return engine.hybrid_search(precursor_mz=neutral_mass, peaks=peaks, ms2_tolerance_in_da=ms2_da)


Hits = list[tuple[str, dict[str, float]]]


def spectrum_hits(
    index: SpectralIndex, library: dict, row_keys: np.ndarray, queries: pd.DataFrame,
    allowed: np.ndarray, method: str = "identity", top_hits: int = 50,
    query_library: dict | None = None, **search_kwargs,
) -> Hits:
    """Library search, one query spectrum at a time.

    For each spectrum: similarity with every allowed reference (`allowed`, a boolean per
    training row), keep the `top_hits` best, and for each structure (key) hit keep its best
    similarity.

    Query peaks are read from `query_library` (by default the training library, for
    validation; for the test, the output of `clean_query_spectra`).

    Returns a list of (molecule_id, {key: similarity}), one item per query spectrum.
    """
    assert allowed.dtype == bool and len(allowed) == len(row_keys), "allowed: one boolean per training row"
    query_library = library if query_library is None else query_library
    hits = []
    neutral = neutral_mass(queries["precursor_mz"].to_numpy(), queries["adduct"])
    # Mask and keys aligned once and for all on each index's order
    allowed_by_pol = {pol: allowed[rows] for pol, rows in index.rows.items()}
    keys_by_pol = {pol: row_keys[rows] for pol, rows in index.rows.items()}
    for (row, mol, pol), mass in zip(
        queries[["row", "molecule_id", "ionization_mode"]].itertuples(index=False), neutral
    ):
        peaks = library_peaks(query_library, row)
        if len(peaks) == 0 or not np.isfinite(mass):
            hits.append((mol, {}))
            continue
        sim = index.search(peaks, mass, pol, method=method, **search_kwargs)
        # Only non-zero similarities matter (tens to thousands of entries)
        nz = np.flatnonzero(sim)
        nz = nz[allowed_by_pol[pol][nz]]
        if len(nz) > top_hits:
            nz = nz[np.argpartition(sim[nz], -top_hits)[-top_hits:]]
        best: dict[str, float] = {}
        for j in nz:
            key = keys_by_pol[pol][j]
            best[key] = max(best.get(key, 0.0), float(sim[j]))
        hits.append((mol, best))
    return hits


def aggregate_hits(hits: Hits, how: str = "sum") -> dict[str, dict[str, float]]:
    """Combine the spectra of each molecule: {molecule_id: {key: score}}.

    "sum" rewards a structure found by several spectra; "max" keeps the best spectrum only.
    """
    scores: dict[str, dict[str, float]] = {}
    for mol, best in hits:
        mol_scores = scores.setdefault(mol, {})
        for key, s in best.items():
            mol_scores[key] = mol_scores.get(key, 0.0) + s if how == "sum" else max(mol_scores.get(key, 0.0), s)
    return scores
