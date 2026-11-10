"""External-library source attribution on the 48-query dev panel.

Faithful re-implementation of the Alex V12 measured-library overlay (cell 14 of
third_party/public_scan_alexchilton__casmi26-lb-0-484-peaks-to-structures-extlib_20261109),
parameterized by external source so Takumu (A) and MassBank (B) contributions can be
separated. Runs only on the frozen 48-query development panel (known truth); no hidden
test coverage, no GPU, no network. All identities use the official RDKit 2026.03.3 key.

Variants:
  BASE       - frozen base ranking, no overlay
  A          - Takumu extlib v2 only
  B          - MassBank harmonized v1 only
  AB         - both sources (the submitted 0.488 overlay)
  AB_STRICT  - both sources, require identical adduct string (not just ion mode)
"""
from __future__ import annotations
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path("/mnt/d/Paper/casmi")
sys.path.insert(0, str(ROOT))
from validation.metric import assert_official_rdkit, identity  # noqa: E402

DEV = ROOT / "runs/validation_pilot_v2_20261104"
RUN = ROOT / "runs/validation_flex_c2_20261105d"
OUT = ROOT / "produre1" / "artifacts"

A_META = ROOT / "assets/kaggle/takumuhata/casmi26-extlib/v2/ext_meta.parquet"
A_MASS = ROOT / "assets/kaggle/takumuhata/casmi26-extlib/v2/ext_mass.parquet"
A_MZ = ROOT / "assets/kaggle/takumuhata/casmi26-extlib/v2/ext_mz.npy"
A_IN = ROOT / "assets/kaggle/takumuhata/casmi26-extlib/v2/ext_in.npy"
B_SPECTRA = ROOT / "assets/kaggle/samartalwar/casmi-2026-spectral-library-massbankharmonized/v1/spectra.parquet"

TAU = 0.80
K_PEAKS = 4
LIB_TAU = 0.90
FRAG_TOL = 0.015
PRECURSOR_PPM = 10e-6
PRECURSOR_DA = 0.002


def sha(p: Path) -> str:
    return hashlib.file_digest(p.open("rb"), "sha256").hexdigest()


def parse_mode(raw) -> int:
    return 1 if "pos" in str(raw).lower() else -1


def calc_cosine(qm, qi, rm, ri, tol=FRAG_TOL):
    if len(qm) == 0 or len(rm) == 0:
        return 0.0, 0
    qa, ra = np.sqrt(qi), np.sqrt(ri)
    qa = qa / (np.linalg.norm(qa) + 1e-12)
    ra = ra / (np.linalg.norm(ra) + 1e-12)
    j0 = np.searchsorted(rm, qm - tol, "left")
    j1 = np.searchsorted(rm, qm + tol, "right")
    pairs = [(qa[i] * ra[j], i, j) for i in range(len(qm)) for j in range(j0[i], j1[i])]
    if not pairs:
        return 0.0, 0
    pairs.sort(reverse=True)
    ui, uj, s, n = set(), set(), 0.0, 0
    for p, i, j in pairs:
        if i in ui or j in uj:
            continue
        ui.add(i)
        uj.add(j)
        s += p
        n += 1
    return float(s), n


def load_truth() -> dict:
    df = pd.read_csv(DEV / "truth.csv", dtype=str, keep_default_na=False)
    return dict(zip(df.molecule_id, df.official_identity))


def load_queries() -> dict:
    df = pq.read_table(DEV / "queries.parquet").to_pandas()
    out = {}
    for r in df.itertuples(index=False):
        m = np.asarray(r.ms2_mzs, dtype=np.float64)
        it = np.asarray(r.ms2_normalized_intensities, dtype=np.float64)
        prec = float(r.precursor_mz)
        mode = parse_mode(r.ionization_mode)
        ok = (m > 0) & (it > 0) & (m <= prec + 0.5)
        m, it = m[ok], it[ok]
        o = np.argsort(m)
        out.setdefault(str(r.molecule_id), []).append(
            dict(mz=m[o], it=it[o], prec=prec, mode=mode, adduct=str(r.adduct)))
    return out


def load_base() -> dict:
    df = pd.read_csv(RUN / "baseline_submission.csv", dtype=str, keep_default_na=False)
    return {str(m): s.split(";") for m, s in zip(df.molecule_id, df.smiles)}


def load_libmax() -> dict:
    ev = pq.read_table(RUN / "frozen_candidate_evidence.parquet",
                       columns=["molecule_id", "library_max"]).to_pandas()
    return {str(m): float(v) for m, v in
            ev.groupby("molecule_id", sort=False).library_max.first().items()}


def load_refs(sources: set[str]) -> list[dict]:
    """Return dict refs tagged with source; faithful to the Alex loader."""
    refs = []
    if "A" in sources:
        meta = pq.read_table(A_META).to_pandas()
        mass = pq.read_table(A_MASS).to_pandas()
        if "exact_mass" in mass.columns:
            meta["exact_mass"] = mass["exact_mass"].values
            meta = meta[meta["exact_mass"].notna() & (meta["exact_mass"] > 0)].copy()
        mz_all = np.load(str(A_MZ), mmap_mode="r")
        in_all = np.load(str(A_IN), mmap_mode="r")
        for idx, row in meta.iterrows():
            try:
                mode = parse_mode(row.get("ionization_mode", "pos"))
                prec = float(row["precursor_mz"])
                nm = float(row.get("exact_mass", prec - 1.007276 * mode))
                m = np.asarray(mz_all[idx], dtype=np.float64)
                it = np.asarray(in_all[idx], dtype=np.float64)
                mask = (m > 0) & (it > 0)
                m, it = m[mask], it[mask]
                if len(m) < 3:
                    continue
                o = np.argsort(m)
                refs.append(dict(mode=mode, prec=prec, mz=m[o], it=it[o],
                                 key=str(row.get("inchikey14", "")), smi=str(row["normalized_smiles"]),
                                 nm=nm, adduct=str(row.get("adduct", "")), source="A"))
            except Exception:
                continue
    if "B" in sources:
        mb = pq.read_table(B_SPECTRA, columns=["smiles", "exact_mass", "ion_mode",
                                               "mzs", "intensities", "is_casmi_subset",
                                               "adduct"]).to_pandas()
        mb = mb[(~mb.is_casmi_subset.astype(bool)) & mb.smiles.notna()]
        for row in mb.itertuples(index=False):
            try:
                mode = parse_mode(row.ion_mode)
                nm = float(row.exact_mass)
                prec = nm + 1.007276 * mode
                m = np.asarray(row.mzs, dtype=np.float64)
                it = np.asarray(row.intensities, dtype=np.float64)
                mask = (m > 0) & (it > 0)
                m, it = m[mask], it[mask]
                if len(m) < 3:
                    continue
                o = np.argsort(m)
                refs.append(dict(mode=mode, prec=prec, mz=m[o], it=it[o],
                                 key="", smi=str(row.smiles), nm=nm,
                                 adduct=str(row.adduct), source="B"))
            except Exception:
                continue
    return refs


def match_molecule(q_list, sorted_refs, prec_array, libmax_val, strict_adduct):
    """Return best (cosine, n, smi, source) above threshold, else None."""
    if libmax_val is not None and libmax_val >= LIB_TAU:
        return None
    if not q_list:
        return None
    best = (0.0, 0, None, None)
    for q in q_list:
        tol = q["prec"] * PRECURSOR_PPM + PRECURSOR_DA
        lo = np.searchsorted(prec_array, q["prec"] - tol, "left")
        hi = np.searchsorted(prec_array, q["prec"] + tol, "right")
        for ri in range(lo, hi):
            ref = sorted_refs[ri]
            if ref["mode"] != q["mode"]:
                continue
            if strict_adduct and ref["adduct"] != q["adduct"]:
                continue
            cos, n = calc_cosine(q["mz"], q["it"], ref["mz"], ref["it"])
            if n >= K_PEAKS and cos > best[0]:
                best = (cos, n, ref["smi"], ref["source"])
    cos, n, smi, src = best
    if smi is not None and cos >= TAU:
        return dict(cos=cos, n=n, smi=smi, source=src)
    return None


def promote(base_list, match):
    if not match:
        return list(base_list), False
    smi = match["smi"]
    if smi in base_list:
        new = [smi] + [s for s in base_list if s != smi]
        changed = base_list[0] != smi
    else:
        new = ([smi] + base_list)[:25]
        changed = True
    return new, changed


def run_variant(queries, base, libmax, refs, strict_adduct=False):
    order = np.argsort([r["prec"] for r in refs], kind="stable")
    sorted_refs = [refs[i] for i in order]
    prec_array = np.array([r["prec"] for r in sorted_refs])
    rows = []
    for mid, base_list in base.items():
        m = match_molecule(queries.get(mid, []), sorted_refs, prec_array,
                           libmax.get(mid), strict_adduct)
        new_list, changed = promote(base_list, m)
        rows.append(dict(molecule_id=mid, new_list=new_list, changed=changed, match=m))
    return rows


def eval_ranked(ranked_list, truth_identity):
    keys = [identity(s) for s in ranked_list]
    rank = next((i for i, k in enumerate(keys, 1) if k == truth_identity), None)
    return dict(rank=rank, mrr=1.0 / rank if rank else 0.0,
                top1=int(rank == 1), top5=int(rank is not None and rank <= 5),
                top25=int(rank is not None))


def summarize(rows, truth):
    evals = [eval_ranked(r["new_list"], truth[r["molecule_id"]]) for r in rows]
    metrics = {k: float(np.mean([e[k] for e in evals])) for k in ("mrr", "top1", "top5", "top25")}
    promoted = [r for r in rows if r["changed"]]
    correct = [r for r in promoted if r["match"] and r["match"]["smi"] and
               identity(r["match"]["smi"]) == truth[r["molecule_id"]]]
    return dict(metrics=metrics, molecules=len(rows), promoted=len(promoted),
                promoted_correct=len(correct), promoted_incorrect=len(promoted) - len(correct),
                promotion_precision=(len(correct) / len(promoted)) if promoted else None,
                false_promotion_rate=((len(promoted) - len(correct)) / len(promoted)) if promoted else None)


def main():
    assert_official_rdkit()
    OUT.mkdir(parents=True, exist_ok=True)
    truth = load_truth()
    queries = load_queries()
    base = load_base()
    libmax = load_libmax()

    refs_A = load_refs({"A"})
    refs_B = load_refs({"B"})
    refs_all = refs_A + refs_B
    comp = {"refs_total": len(refs_all),
            "A": len(refs_A),
            "B": len(refs_B),
            "A_keys": len({r["key"] for r in refs_A if r["key"]}),
            "A_adduct_top": Counter(r["adduct"] for r in refs_A).most_common(12),
            "B_adduct_top": Counter(r["adduct"] for r in refs_B).most_common(12)}

    results = {}
    per_query = {mid: {"molecule_id": mid, "truth": truth[mid],
                       "base_rank": eval_ranked(base[mid], truth[mid])["rank"]}
                 for mid in base}

    base_rows = [dict(molecule_id=mid, new_list=base[mid], changed=False, match=None) for mid in base]
    results["BASE"] = summarize(base_rows, truth)

    for name, refs, strict in [("A", refs_A, False), ("B", refs_B, False),
                               ("AB", refs_all, False), ("AB_STRICT", refs_all, True)]:
        rows = run_variant(queries, base, libmax, refs, strict_adduct=strict)
        results[name] = summarize(rows, truth)
        for r in rows:
            rank = eval_ranked(r["new_list"], truth[r["molecule_id"]])["rank"]
            d = per_query[r["molecule_id"]]
            d[name + "_hit"] = bool(r["match"])
            d[name + "_smi"] = r["match"]["smi"] if r["match"] else ""
            d[name + "_cos"] = round(r["match"]["cos"], 4) if r["match"] else None
            d[name + "_changed"] = r["changed"]
            d[name + "_correct"] = bool(r["match"] and identity(r["match"]["smi"]) == truth[r["molecule_id"]])
            d[name + "_rank"] = rank

    base_mrr = results["BASE"]["metrics"]["mrr"]
    deltas = {name: round(results[name]["metrics"]["mrr"] - base_mrr, 6)
              for name in ("A", "B", "AB", "AB_STRICT")}
    deltas["interaction_AB"] = round(results["AB"]["metrics"]["mrr"] - results["A"]["metrics"]["mrr"]
                                     - results["B"]["metrics"]["mrr"] + base_mrr, 6)

    both_hit = [m for m in per_query.values() if m.get("A_hit") and m.get("B_hit")]
    conflict = [m for m in both_hit if m.get("A_smi") and m.get("B_smi") and m["A_smi"] != m["B_smi"]]

    summary = dict(
        created_by="produre1/attribution.py",
        scope="48-query dev panel (reference-isolated diagnostic, known pretrained exposure)",
        base_source=str((RUN / "baseline_submission.csv").relative_to(ROOT)),
        truth_source=str((DEV / "truth.csv").relative_to(ROOT)),
        library_sha=dict(ext_meta=sha(A_META), ext_mass=sha(A_MASS), ext_mz=sha(A_MZ),
                         ext_in=sha(A_IN), spectra=sha(B_SPECTRA)),
        ranking_constants=dict(TAU=TAU, K_PEAKS=K_PEAKS, LIB_TAU=LIB_TAU,
                               fragment_da=FRAG_TOL, precursor_ppm=PRECURSOR_PPM, precursor_da=PRECURSOR_DA),
        composition=comp,
        results=results,
        deltas=deltas,
        ab_conflict=dict(both_hit=len(both_hit), conflict_queries=len(conflict),
                         conflict_ids=[m["molecule_id"] for m in conflict][:50]),
        caveats=["Base is the Flex48 V0 diagnostic ranking, NOT the 0.482 MASS hidden output.",
                 "Public-pretrained exposure; not clean generalization.",
                 "Promotion precision is against the 48 dev truths only.",
                 "AB_STRICT uses exact adduct string equality, a strict proxy."],
    )
    (OUT / "attribution_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    pd.DataFrame(list(per_query.values())).to_csv(OUT / "per_query_attribution.csv", index=False)
    print(json.dumps({k: summary[k] for k in ("deltas", "results", "ab_conflict", "composition")},
                     indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()



