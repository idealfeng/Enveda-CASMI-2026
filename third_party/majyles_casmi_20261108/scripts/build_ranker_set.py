"""Step 4 — training set of the ranker: ~2,000 natural products, disjoint from validation.

Built like validation subset B (notebook 02): public libraries, present in COCONUT, absent
from enveda-180 and drug_plus, 157–1,159 Da, one query source per molecule (QTOF preferred),
validation molecules excluded. The library searches are then cached for one query draw under
three conditions: class 1, cross-instrument class 1 (class1x) and class 2.

Outputs: processed/rank_structures.parquet, rank_queries.parquet, rank_draw.parquet and
processed/cache/hits_{identity,hybrid}_{class1,class1x,class2}_rank.pkl. Several hours.
"""
import time

import numpy as np
import pandas as pd

import casmi

N_MOLECULES = 2000
SEED = 7
NP_LIBS = ["riken", "gnps", "massbank", "mona", "spectraverse", "msdial", "pluskal_ms2", "masaryk"]


def build_split(meta: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    val_structures, _ = casmi.load_validation()
    lib_counts = pd.crosstab(meta["key"], meta["ingest_lib"])
    key_mass = meta.groupby("key")["exact_mass"].first().reindex(lib_counts.index)
    coconut_ik14 = set(casmi.load_coconut()["inchikey14"])
    key_to_ik14 = meta.drop_duplicates("key").set_index("key")["inchikey14"].reindex(lib_counts.index)
    eligible = (
        (lib_counts[NP_LIBS].sum(axis=1) > 0)
        & (lib_counts["enveda-180"] == 0) & (lib_counts["drug_plus"] == 0)
        & (lib_counts["enveda-np-examples"] == 0)
        & key_mass.between(157, 1159)
        & key_to_ik14.isin(coconut_ik14)
        & ~lib_counts.index.isin(set(val_structures["key"]))
    )
    usable = meta["adduct"].isin(casmi.TEST_ADDUCTS) & (meta["precursor_error_ppm"].abs() < 10)
    with_usable = set(meta.loc[usable & meta["ingest_lib"].isin(NP_LIBS), "key"])
    candidates = [k for k in lib_counts.index[eligible] if k in with_usable]
    rng = np.random.default_rng(SEED)
    keys = set(rng.choice(candidates, size=N_MOLECULES, replace=False))

    q = meta[meta["key"].isin(keys) & usable & meta["ingest_lib"].isin(NP_LIBS)].copy()
    # One query source per molecule: at least 2 spectra if possible, closest instrument to the test
    priority = {f: i for i, f in enumerate(casmi.INSTRUMENT_PRIORITY)}
    sources = q.groupby(["key", "source", "instrument_family"]).size().reset_index(name="n_spectra")
    sources["too_small"] = (sources["n_spectra"] < 2).astype(int)
    sources["family_rank"] = sources["instrument_family"].map(priority)
    chosen = (sources.sample(frac=1, random_state=SEED)
              .sort_values(["too_small", "family_rank"], kind="stable")
              .drop_duplicates("key").set_index("key")["source"])
    q = q[q["source"] == q["key"].map(chosen)]
    q.index.name = "row"
    mol_ids = {k: f"t_{i:04d}" for i, k in enumerate(sorted(q["key"].unique()))}
    q["molecule_id"] = q["key"].map(mol_ids)
    q["subset"] = "T_train"
    structures = (q.drop_duplicates("key")[["molecule_id", "key", "normalized_smiles", "exact_mass", "subset"]]
                  .sort_values("molecule_id").reset_index(drop=True))
    cols = ["molecule_id", "subset", "key", "ingest_lib", "instrument_family", "source", "adduct",
            "ionization_mode", "precursor_mz", "collision_energy_ev", "num_peaks", "base_peak_intensity"]
    return structures, q[cols].reset_index()


if __name__ == "__main__":
    t = time.time()
    meta = casmi.load_reference_meta(casmi.META_COLUMNS)

    s_path, q_path = casmi.paths.processed / "rank_structures.parquet", casmi.paths.processed / "rank_queries.parquet"
    d_path = casmi.paths.processed / "rank_draw.parquet"
    if s_path.exists():
        structures, queries = pd.read_parquet(s_path), pd.read_parquet(q_path)
    else:
        structures, queries = build_split(meta)
        structures.to_parquet(s_path, index=False)
        queries.to_parquet(q_path, index=False)
    print(f"ranker training set: {len(structures)} molecules, {len(queries)} query spectra", flush=True)

    if d_path.exists():
        draw = pd.read_parquet(d_path)
    else:
        draw = casmi.sample_queries(queries, casmi.spectra_count_distribution(), seed=0)
        draw.to_parquet(d_path, index=False)

    library = casmi.build_clean_library()
    index = casmi.SpectralIndex(library, meta)
    keys = meta["key"].to_numpy()
    for cond in ["class2", "class1", "class1x"]:
        allowed = casmi.reference_mask(meta, queries, cond)
        for method, top in [("identity", 50), ("hybrid", 100)]:
            t0 = time.time()
            casmi.cached(f"hits_{method}_{cond}_rank",
                         lambda: casmi.spectrum_hits(index, library, keys, draw, allowed, method=method, top_hits=top))
            print(f"{cond} {method}: {time.time() - t0:.0f} s", flush=True)
    print(f"done - {time.time() - t:.0f} s", flush=True)
