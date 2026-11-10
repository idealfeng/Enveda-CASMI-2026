"""Step 7 (P1-B): Enveda-180 membership audit, dedup and independent overlay.

1. Membership audit of the 431 alias identities (H+/H- reference identities) against
   train / candidate pool / Takumu / MassBank.
2. Exact-duplicate spectrum audit by spectrum_signature.
3. Independent overlay: add Enveda-180 as a third source, measure Match Coverage and
   Correct Match Coverage increment on the 200-identity cross_development panel.
"""
from __future__ import annotations
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path("/mnt/d/Paper/casmi")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "produre1"))
from validation.metric import assert_official_rdkit, identity  # noqa: E402
import step6_validation_panel as S6  # noqa: E402

ENV180 = ROOT / "assets/kaggle/egehseyinca/enveda180-casmi26-reference-ccby4/v1/enveda180_hplus_hminus_references.parquet"
ALIAS = ROOT / "reports/external_reference_pilot_20261107/alias_related_reference_rows.parquet"
TRAIN_CATALOG = ROOT / "runs/validation_pilot_v2_20261104/structure_identity_audit.parquet"
POOL = ROOT / "assets/kaggle/ahmedberatozer/casmi26-v2-pool/v1/train_structs.parquet"
OUT = ROOT / "produre1" / "artifacts"


def load_alias_identities():
    df = pq.read_table(ALIAS).to_pandas()
    seen = {}
    for r in df.itertuples(index=False):
        oid = str(r.official_identity)
        if oid not in seen:
            seen[oid] = dict(official_identity=oid, smiles=str(r.smiles),
                             publisher_key=str(r.publisher_reference_key))
    return list(seen.values())


def load_key_set(parquet, col):
    return set(pq.read_table(parquet, columns=[col]).column(0).to_pylist())


def load_enveda180_refs(prec_lo=None, prec_hi=None):
    cols = ["reference_key", "smiles", "neutral_mass", "adduct", "ms2_mzs", "ms2_normalized_intensities"]
    pf = pq.ParquetFile(ENV180)
    refs = []
    for batch in pf.iter_batches(batch_size=65536, columns=cols, use_threads=False):
        for i in range(batch.num_rows):
            try:
                adduct = str(batch.column("adduct")[i].as_py())
                if adduct not in ("[M+H]+", "[M-H]-"):
                    continue
                smi = str(batch.column("smiles")[i].as_py())
                if not smi:
                    continue
                nm = float(batch.column("neutral_mass")[i].as_py())
                mode = 1 if adduct == "[M+H]+" else -1
                prec = nm + 1.007276 * mode
                if prec_lo is not None and (prec < prec_lo or prec > prec_hi):
                    continue
                m = np.asarray(batch.column("ms2_mzs")[i].as_py(), dtype=np.float32)
                it = np.asarray(batch.column("ms2_normalized_intensities")[i].as_py(), dtype=np.float32)
                mask = (m > 0) & (it > 0)
                m, it = m[mask], it[mask]
                if len(m) < 3:
                    continue
                o = np.argsort(m)
                refs.append(dict(mode=mode, prec=prec, mz=m[o], it=it[o],
                                 smi=smi, idkey=str(batch.column("reference_key")[i].as_py())[:14],
                                 source="E"))
            except Exception:
                continue
    return refs


def dedup_audit():
    sigs = pq.read_table(ENV180, columns=["spectrum_signature"]).column(0).to_pylist()
    c = Counter(sigs)
    total = len(sigs)
    unique = len(c)
    dup_groups = sum(1 for v in c.values() if v > 1)
    dup_extra_rows = sum(v - 1 for v in c.values() if v > 1)
    return dict(total_rows=total, unique_signatures=unique, duplicate_groups=dup_groups,
                duplicate_extra_rows=dup_extra_rows)


def main():
    assert_official_rdkit()
    OUT.mkdir(parents=True, exist_ok=True)

    # ---- 1. membership audit ----
    aliases = load_alias_identities()
    train_keys = load_key_set(TRAIN_CATALOG, "raw_inchikey14")
    pool_keys = load_key_set(POOL, "inchikey14")
    takumu_keys = load_key_set(S6.AT.A_META, "inchikey14")
    massbank_keys = load_key_set(S6.AT.B_SPECTRA, "inchikey")

    cat = Counter()
    for a in aliases:
        oid = a["official_identity"]
        in_train = oid in train_keys or a["publisher_key"] in train_keys
        in_pool = oid in pool_keys
        in_takumu = oid in takumu_keys
        in_massbank = oid in massbank_keys
        a["in_train"] = in_train
        a["in_pool"] = in_pool
        a["in_takumu"] = in_takumu
        a["in_massbank"] = in_massbank
        if in_train:
            a["category"] = "A_in_train"
        elif in_pool:
            a["category"] = "B_in_pool"
        elif in_takumu or in_massbank:
            a["category"] = "C_other_external_ref"
        else:
            a["category"] = "D_not_covered"
        cat[a["category"]] += 1

    # ---- 2. dedup ----
    dedup = dedup_audit()

    # ---- 3. independent overlay ----
    panel = S6.load_panel()
    queries = S6.load_train_queries(panel)
    all_prec = [q["prec"] for ql in queries.values() for q in ql]
    prec_lo = min(all_prec) - 0.5
    prec_hi = max(all_prec) + 0.5
    refs_A = S6.load_refs_A()
    refs_B = S6.load_refs_B()
    refs_E = load_enveda180_refs(prec_lo, prec_hi)
    refs_AB = refs_A + refs_B
    refs_ABE = refs_AB + refs_E
    sr_ab, pr_ab = S6.build_sorted(refs_AB)
    sr_abe, pr_abe = S6.build_sorted(refs_ABE)

    def coverage(refs_sorted, prec):
        hits = correct = 0
        n = 0
        for item in panel:
            off = item["official_identity"]
            q = queries.get(off, [])
            if not q:
                continue
            n += 1
            m = S6.match_one(q, refs_sorted, prec)
            if m:
                hits += 1
                correct += identity(m["smi"]) == off
        return dict(queries=n, match_coverage=hits / n if n else None,
                    correct_match_coverage=correct / n if n else None, hits=hits, correct=correct)

    cov_ab = coverage(sr_ab, pr_ab)
    cov_abe = coverage(sr_abe, pr_abe)

    summary = dict(
        step="step7_enveda180",
        scope="Enveda-180 membership / dedup / independent overlay on 200 cross_development identities",
        membership=dict(total_alias_identities=len(aliases), categories=dict(cat),
                        scope="official InChIKey14 vs raw publisher keys; raw-key-level membership, tautomer/stereo aliases may differ"),
        dedup=dedup,
        overlay=dict(refs_A=len(refs_A), refs_B=len(refs_B), refs_E=len(refs_E),
                     AB=cov_ab, AB_plus_Enveda180=cov_abe,
                     coverage_increment=round((cov_abe["match_coverage"] or 0) - (cov_ab["match_coverage"] or 0), 4),
                     correct_coverage_increment=round((cov_abe["correct_match_coverage"] or 0) - (cov_ab["correct_match_coverage"] or 0), 4)),
        caveats=["Enveda-180 restricted to [M+H]+ / [M-H]- (its only two adducts).",
                 "Membership is raw-key level, not full official identity.",
                 "Overlay increment is on the 200 dev identities, not hidden test."],
    )
    (OUT / "step7_enveda180_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    pd.DataFrame(aliases).to_csv(OUT / "step7_enveda180_membership.csv", index=False)
    print(json.dumps({k: summary[k] for k in ("membership", "dedup", "overlay")}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()


