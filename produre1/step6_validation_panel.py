"""Step 6 (P1-A): build a dedicated external-library validation panel.

Uses the frozen cross_development split (200 identities) as the validation panel,
extracts each identity's query spectra from the official train file, then runs the
external measured-library matching (Takumu A + MassBank B) to compute:

  Match Coverage, Correct Match Coverage, Promotion Precision, False Promotion Rate,
  per-source precision, and a B-class (target-identity-exclusion) false-promotion test.

No hidden test, no GPU, no network. Identities are the official RDKit 2026.03.3 keys.
"""
from __future__ import annotations
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path("/mnt/d/Paper/casmi")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "produre1"))
from validation.metric import assert_official_rdkit, identity  # noqa: E402
import attribution as AT  # noqa: E402

DEV = ROOT / "runs/validation_pilot_v2_20261104"
TRAIN = ROOT / "enveda-CASMI26-molecule-id-mass-spectra/train.parquet"
OUT = ROOT / "produre1" / "artifacts"
SPLITS = DEV / "frozen_splits.json"

TAU = AT.TAU
K_PEAKS = AT.K_PEAKS
calc_cosine = AT.calc_cosine
parse_mode = AT.parse_mode


def load_panel() -> list[dict]:
    splits = json.loads(SPLITS.read_text())
    panel = splits["cross_development"]
    assert len(panel) == 200, len(panel)
    return panel


def load_train_queries(panel: list[dict]) -> dict:
    """Extract query spectra per identity from the official train file."""
    raw_to_official = {}
    for item in panel:
        for rk in item["raw_keys"]:
            raw_to_official[rk] = item["official_identity"]
    cols = ["inchikey14", "ionization_mode", "adduct", "precursor_mz",
            "ms2_mzs", "ms2_normalized_intensities"]
    pf = pq.ParquetFile(TRAIN)
    out = {}
    for batch in pf.iter_batches(batch_size=65536, columns=cols, use_threads=False):
        for i in range(batch.num_rows):
            raw = str(batch.column("inchikey14")[i].as_py())
            off = raw_to_official.get(raw)
            if off is None:
                continue
            m = np.asarray(batch.column("ms2_mzs")[i].as_py(), dtype=np.float32)
            it = np.asarray(batch.column("ms2_normalized_intensities")[i].as_py(), dtype=np.float32)
            prec = float(batch.column("precursor_mz")[i].as_py())
            mode = parse_mode(batch.column("ionization_mode")[i].as_py())
            ok = (m > 0) & (it > 0) & (m <= prec + 0.5)
            m, it = m[ok], it[ok]
            o = np.argsort(m)
            out.setdefault(off, []).append(
                dict(mz=m[o], it=it[o], prec=prec, mode=mode, adduct=str(batch.column("adduct")[i].as_py())))
    return out


def load_refs_A():
    meta = pq.read_table(AT.A_META).to_pandas()
    mass = pq.read_table(AT.A_MASS).to_pandas()
    if "exact_mass" in mass.columns:
        meta["exact_mass"] = mass["exact_mass"].values
        meta = meta[meta["exact_mass"].notna() & (meta["exact_mass"] > 0)].copy()
    mz_all = np.load(str(AT.A_MZ), mmap_mode="r")
    in_all = np.load(str(AT.A_IN), mmap_mode="r")
    refs = []
    for idx, row in meta.iterrows():
        try:
            mode = parse_mode(row.get("ionization_mode", "pos"))
            prec = float(row["precursor_mz"])
            m = np.asarray(mz_all[idx], dtype=np.float32)
            it = np.asarray(in_all[idx], dtype=np.float32)
            mask = (m > 0) & (it > 0)
            m, it = m[mask], it[mask]
            if len(m) < 3:
                continue
            o = np.argsort(m)
            refs.append(dict(mode=mode, prec=prec, mz=m[o], it=it[o],
                             smi=str(row["normalized_smiles"]),
                             idkey=str(row.get("inchikey14", ""))[:14], source="A"))
        except Exception:
            continue
    return refs


def load_refs_B():
    mb = pq.read_table(AT.B_SPECTRA, columns=["smiles", "exact_mass", "ion_mode",
                                              "mzs", "intensities", "is_casmi_subset",
                                              "inchikey"]).to_pandas()
    mb = mb[(~mb.is_casmi_subset.astype(bool)) & mb.smiles.notna()]
    refs = []
    for row in mb.itertuples(index=False):
        try:
            mode = parse_mode(row.ion_mode)
            nm = float(row.exact_mass)
            prec = nm + 1.007276 * mode
            m = np.asarray(row.mzs, dtype=np.float32)
            it = np.asarray(row.intensities, dtype=np.float32)
            mask = (m > 0) & (it > 0)
            m, it = m[mask], it[mask]
            if len(m) < 3:
                continue
            o = np.argsort(m)
            refs.append(dict(mode=mode, prec=prec, mz=m[o], it=it[o],
                             smi=str(row.smiles),
                             idkey=str(row.inchikey)[:14], source="B"))
        except Exception:
            continue
    return refs


def build_sorted(refs):
    order = np.argsort([r["prec"] for r in refs], kind="stable")
    sorted_refs = [refs[i] for i in order]
    prec_array = np.array([r["prec"] for r in sorted_refs])
    return sorted_refs, prec_array


def match_one(q_list, sorted_refs, prec_array, strict=False, blocked=None):
    if not q_list:
        return None
    blocked = blocked or set()
    best = (0.0, 0, None, None)
    for q in q_list:
        tol = q["prec"] * 10e-6 + 0.002
        lo = np.searchsorted(prec_array, q["prec"] - tol, "left")
        hi = np.searchsorted(prec_array, q["prec"] + tol, "right")
        for ri in range(lo, hi):
            ref = sorted_refs[ri]
            if ref["idkey"] in blocked:
                continue
            if ref["mode"] != q["mode"]:
                continue
            if strict and ref.get("adduct") != q["adduct"]:
                continue
            cos, n = calc_cosine(q["mz"], q["it"], ref["mz"], ref["it"])
            if n >= K_PEAKS and cos > best[0]:
                best = (cos, n, ref["smi"], ref["source"])
    cos, n, smi, src = best
    if smi is not None and cos >= TAU:
        return dict(cos=cos, n=n, smi=smi, source=src)
    return None


def bootstrap(rows, key, resamples=2000, seed=20261104):
    vals = np.array([r[key] for r in rows], dtype=np.float64)
    rng = np.random.default_rng(seed)
    means = vals[rng.integers(0, len(vals), size=(resamples, len(vals)))].mean(axis=1)
    return dict(mean=float(vals.mean()),
                ci_low=float(np.quantile(means, 0.025)),
                ci_high=float(np.quantile(means, 0.975)))


def main():
    assert_official_rdkit()
    OUT.mkdir(parents=True, exist_ok=True)
    panel = load_panel()
    queries = load_train_queries(panel)
    refs_A = load_refs_A()
    refs_B = load_refs_B()
    refs_all = refs_A + refs_B
    sorted_all, prec_all = build_sorted(refs_all)

    # ---- A-class: positive matching (target present in libraries) ----
    rows = []
    for item in panel:
        off = item["official_identity"]
        q_list = queries.get(off, [])
        m = match_one(q_list, sorted_all, prec_all)
        correct = bool(m and identity(m["smi"]) == off)
        rows.append(dict(official_identity=off, panel=item["panel"],
                         query_source=item["query_source"],
                         n_spectra=len(q_list), hit=bool(m),
                         match_smi=m["smi"] if m else "", source=m["source"] if m else "",
                         cosine=round(m["cos"], 4) if m else None,
                         correct=correct))

    n = len(rows)
    n_query = sum(1 for r in rows if r["n_spectra"] > 0)
    hits = [r for r in rows if r["hit"]]
    correct_hits = [r for r in hits if r["correct"]]
    match_coverage = len(hits) / n_query if n_query else None
    correct_match_coverage = len(correct_hits) / n_query if n_query else None
    promotion_precision = len(correct_hits) / len(hits) if hits else None
    false_promotion_rate = (len(hits) - len(correct_hits)) / len(hits) if hits else None

    per_source = {}
    for src in ("A", "B"):
        s = [r for r in hits if r["source"] == src]
        c = [r for r in s if r["correct"]]
        per_source[src] = dict(hits=len(s), correct=len(c),
                               precision=(len(c) / len(s)) if s else None)

    # ---- B-class: target-identity exclusion (false-promotion pressure test) ----
    excl_rows = []
    for item in panel:
        off = item["official_identity"]
        exclude = {off} | {str(rk)[:14] for rk in item["raw_keys"]}
        q_list = queries.get(off, [])
        m = match_one(q_list, sorted_all, prec_all, blocked=exclude)
        excl_rows.append(dict(official_identity=off, n_spectra=len(q_list),
                              false_hit=bool(m), false_smi=m["smi"] if m else ""))
    n_query2 = sum(1 for r in excl_rows if r["n_spectra"] > 0)
    false_hits = [r for r in excl_rows if r["false_hit"]]
    exclusion_false_promotion_rate = len(false_hits) / n_query2 if n_query2 else None

    # ---- bootstrap on binary metrics ----
    bs_match = bootstrap([dict(v=int(r["hit"])) for r in rows if r["n_spectra"] > 0], "v")
    bs_correct = bootstrap([dict(v=int(r["correct"])) for r in rows if r["n_spectra"] > 0], "v")

    summary = dict(
        step="step6_validation_panel",
        scope="cross_development frozen split (200 identities); positive matching + target-identity exclusion",
        panel_size=len(panel),
        identities_with_query_spectra=n_query,
        refs=dict(A=len(refs_A), B=len(refs_B)),
        a_class=dict(match_coverage=match_coverage,
                     correct_match_coverage=correct_match_coverage,
                     promotion_precision=promotion_precision,
                     false_promotion_rate=false_promotion_rate,
                     hits=len(hits), correct_hits=len(correct_hits),
                     per_source=per_source,
                     bootstrap_match_coverage=bs_match,
                     bootstrap_correct_match_coverage=bs_correct),
        b_class=dict(identities_with_query_spectra=n_query2,
                     false_promotion_rate=exclusion_false_promotion_rate,
                     false_hits=len(false_hits),
                     scope="raw-inchikey14 exclusion of target identity from A+B; any above-threshold match counts as a false promotion"),
        caveats=["Exclusion is at raw inchikey14 level, not full official identity (tautomer/stereo aliases may differ).",
                 "Positive matching compares the external best match to the panel's official identity.",
                 "No pipeline base ranking is used; promotion is the match-level rank-1 rule.",
                 "Public-pretrained exposure; not clean generalization."],
    )
    (OUT / "step6_validation_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    pd.DataFrame(rows).to_csv(OUT / "step6_per_identity.csv", index=False)
    pd.DataFrame(excl_rows).to_csv(OUT / "step6_bclass_exclusion.csv", index=False)
    print(json.dumps({k: summary[k] for k in ("a_class", "b_class", "refs")}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()


