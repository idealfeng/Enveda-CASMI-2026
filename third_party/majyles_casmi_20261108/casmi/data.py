"""Loading the competition data, adduct masses and instrument families."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from .paths import paths

# Lightweight training columns: everything except the peak arrays (most of the 3 GB file).
META_COLUMNS = [
    "ingest_lib", "normalized_smiles", "inchikey14", "molecular_formula",
    "ionization_mode", "instrument_type", "adduct", "precursor_mz", "precursor_error_ppm",
    "num_peaks", "base_peak_intensity", "collision_energy_ev",
]


def load_train_meta(columns: list[str] | None = None) -> pd.DataFrame:
    """Training metadata without the spectra. The index is the row number in the file."""
    return pq.read_table(paths.train, columns=columns or META_COLUMNS).to_pandas()


def load_reference_meta(columns: list[str] | None = None) -> pd.DataFrame:
    """Training metadata annotated for library search.

    Adds, from processed/structures.parquet, the metric `key` and `exact_mass` of each
    spectrum's structure, plus its `instrument_family` and its `source` (library / family),
    the unit hidden by the class-1 validation condition.
    """
    base = ["ingest_lib", "normalized_smiles", "ionization_mode", "instrument_type"]
    meta = load_train_meta(base + [c for c in columns or [] if c not in base])
    structures = pd.read_parquet(paths.processed / "structures.parquet").set_index("normalized_smiles")
    meta["key"] = meta["normalized_smiles"].map(structures["key"])
    meta["exact_mass"] = meta["normalized_smiles"].map(structures["exact_mass"])
    meta["instrument_family"] = instrument_family(meta["instrument_type"])
    meta["source"] = meta["ingest_lib"] + " / " + meta["instrument_family"]
    return meta


def load_train_spectra(rows: np.ndarray) -> pd.DataFrame:
    """Raw peak arrays (m/z, intensities) of a few training rows.

    Only the parquet row groups containing the requested rows are read.
    """
    import pyarrow as pa

    rows = np.asarray(rows)
    pf = pq.ParquetFile(paths.train)
    starts = np.cumsum([0] + [pf.metadata.row_group(i).num_rows for i in range(pf.metadata.num_row_groups)])
    groups = np.searchsorted(starts, rows, side="right") - 1
    parts = []
    for g in np.unique(groups):
        table = pf.read_row_group(int(g), columns=["ms2_mzs", "ms2_normalized_intensities"])
        local = rows[groups == g] - starts[g]
        parts.append(table.take(pa.array(local)))
    df = pa.concat_tables(parts).to_pandas()
    df.index = np.concatenate([rows[groups == g] for g in np.unique(groups)])
    return df.loc[rows]


def load_coconut() -> pd.DataFrame:
    """Useful columns of COCONUT, the open natural-product database (CC0), cached as parquet."""
    path = paths.processed / "coconut.parquet"
    if path.exists():
        return pd.read_parquet(path)
    cols = ["identifier", "canonical_smiles", "standard_inchi_key", "molecular_formula",
            "exact_molecular_weight", "np_likeness"]
    df = pd.read_csv(paths.coconut_zip, usecols=cols)
    df["inchikey14"] = df["standard_inchi_key"].str[:14]
    df.to_parquet(path, index=False)
    return df


# --------------------------------------------------------------------------------------------
# Adducts: precursor m/z -> neutral mass of the molecule
# --------------------------------------------------------------------------------------------
# The ten adducts of the hidden test. m/z = M + offset for a single charge.
TEST_ADDUCTS = {
    "[M+H]+": 1.007276,
    "[M+NH4]+": 18.033823,
    "[M-H2O+H]+": 1.007276 - 18.010565,
    "[M-2H2O+H]+": 1.007276 - 2 * 18.010565,
    "[M+Na]+": 22.989218,
    "[M+K]+": 38.963158,
    "[M-H]-": -1.007276,
    "[M-H2O-H]-": -1.007276 - 18.010565,
    "[M+CH2O2-H]-": 44.998201,
    "[M+Cl]-": 34.969402,
}


def neutral_mass(precursor_mz, adduct) -> np.ndarray:
    """Neutral mass M = m/z - adduct offset (NaN for an adduct outside the table)."""
    offset = pd.Series(adduct).map(TEST_ADDUCTS).to_numpy(dtype=float)
    return np.asarray(precursor_mz, dtype=float) - offset


def molecule_masses(queries: pd.DataFrame) -> pd.Series:
    """Neutral mass of each molecule: median of the masses derived from each of its spectra."""
    m = pd.Series(neutral_mass(queries["precursor_mz"].to_numpy(), queries["adduct"]), index=queries.index)
    return m.groupby(queries["molecule_id"]).median()


# --------------------------------------------------------------------------------------------
# Instrument families
# --------------------------------------------------------------------------------------------
# `instrument_type` is free text (83 spellings outside enveda-180). It is mapped to a family
# according to the fragmentation technique, ordered by closeness to the test's timsTOF:
#   QTOF     : same architecture as the timsTOF, collision-cell fragmentation in eV
#   Orbitrap : HCD fragmentation, similar principle, energies on another scale (NCE)
#   QqQ      : triple quadrupole, similar fragmentation but low mass resolution
#   IonTrap  : ion traps (including IT-FT / IT-TOF hybrids), different fragmentation
INSTRUMENT_PRIORITY = ["timsTOF", "QTOF", "Orbitrap", "QqQ", "IonTrap", "other"]


def _family(raw) -> str:
    s = str(raw).lower()
    if "timstof" in s:
        return "timsTOF"
    if any(t in s for t in ["ittof", "itft", "ion trap", "iontrap", "qit", "lit", "ltq", "-it"]):
        return "IonTrap"
    if s.startswith("maldi") or s.startswith("fab") or "in source" in s or s == "si-be":
        return "other"
    if "tof" in s or "maxis" in s or "impact" in s or "synapt" in s:
        return "QTOF"
    if any(t in s for t in ["orbitrap", "exactive", "qft", "qehf", "ft"]):
        return "Orbitrap"
    if any(t in s for t in ["qqq", "qq", "quattro", "-q"]):
        return "QqQ"
    return "other"


def instrument_family(instrument_type: pd.Series) -> pd.Series:
    """Instrument family of each spectrum (computed once per distinct spelling)."""
    mapping = {v: _family(v) for v in instrument_type.dropna().unique()}
    return instrument_type.map(mapping).fillna("other")
