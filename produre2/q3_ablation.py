"""Q3: single-factor PAIRED ablation on the REAL generation path (same 48 queries for
every condition). Factors: parent count, min similarity, mass tol, max steps, template set."""
import json
import sys
import time

sys.path.insert(0, "/mnt/d/Paper/casmi/produre2")
import numpy as np

import q345_lib as H
from casmi import chem, derive as dmod


def derive_filtered(smiles, delta, tol, max_steps, max_per_analog, allow_isomerisation, template_names):
    from rdkit import Chem
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return []
    combos = dmod.matching_transforms(delta, tol, max_steps)
    if template_names is not None:
        combos = [c for c in combos if all(n in template_names for n in c)]
    if abs(delta) < tol and not allow_isomerisation:
        combos = []
    out = {}
    budget = 800
    for combo in combos:
        mols = [mol]
        for depth, name in enumerate(combo):
            nxt = []
            for m in mols[:24]:
                nxt.extend(dmod.apply_transform(m, name, max_products=32 if depth == 0 else 16))
                budget -= 1
                if budget <= 0:
                    break
            mols = nxt
            if not mols or budget <= 0:
                break
        for m in mols:
            s = Chem.MolToSmiles(m)
            if s != smiles and s not in out:
                out[s] = combo
        if len(out) >= max_per_analog or budget <= 0:
            break
    return list(out.keys())[:max_per_analog]


def generate_ablation(eng, analogs, target, exclude_keys, n_analog, min_sim, tol, max_steps, template_names, allow_isomerisation=True):
    cfg = eng.cfg; L = eng.L; P = eng.pool
    out = []; seen = set(exclude_keys)
    parents = [a for a in analogs if a[1] >= min_sim][:n_analog]
    for sid, sim, shift, _ in parents:
        psmi = L.struct_smiles[sid]
        pfp = np.unpackbits(eng.train_fp[sid])[:P.nbits].astype(np.float32)
        delta = target - float(L.struct_mass[sid])
        try:
            prods = derive_filtered(psmi, delta, tol=tol, max_steps=max_steps,
                                    max_per_analog=cfg.gen_max_per_parent,
                                    allow_isomerisation=allow_isomerisation, template_names=template_names)
        except Exception:
            prods = []
        for s in prods:
            std = chem.standardize_smiles(s)
            if std is None:
                continue
            k = chem.score_key(std)
            if k is None or k in seen:
                continue
            p = chem.mol_props(std)
            if p is None or abs(p[1] - target) > tol:
                continue
            fp = chem.raw_fingerprint(std)
            if fp is None:
                continue
            fp = fp[P.bits].astype(np.float32)
            seen.add(k)
            out.append(k)
            if len(out) >= cfg.gen_max_total:
                return out
    return out


def main():
    eng = H.load_engine(bank=False)
    queries, truth = H.load_queries_truth()
    truth_id = dict(zip(truth.molecule_id, truth.official_identity))
    mids = list(truth.molecule_id)

    add_names = [n for n in dmod._TRANSFORMS if dmod._delta_mass(dmod._TRANSFORMS[n][1]) > 0]
    rem_names = [n for n in dmod._TRANSFORMS if dmod._delta_mass(dmod._TRANSFORMS[n][1]) < 0]

    # Transformation-only regime (allow_isomerisation=False) to avoid the delta~0 neutral-combo
    # explosion and to isolate TRUE mass-changing generation. Isomerisation contribution is measured
    # separately by comparing with Q5's iso-ON run (19/48).
    conditions = [
        dict(name="base_transf(n6_sim0.3_tol0.004_step2_all)", n_analog=6, min_sim=0.3, tol=0.004, max_steps=2, template_names=None, allow_isomerisation=False),
        dict(name="n_analog=3", n_analog=3, min_sim=0.3, tol=0.004, max_steps=2, template_names=None, allow_isomerisation=False),
        dict(name="n_analog=12", n_analog=12, min_sim=0.3, tol=0.004, max_steps=2, template_names=None, allow_isomerisation=False),
        dict(name="min_sim=0.1", n_analog=6, min_sim=0.1, tol=0.004, max_steps=2, template_names=None, allow_isomerisation=False),
        dict(name="min_sim=0.5", n_analog=6, min_sim=0.5, tol=0.004, max_steps=2, template_names=None, allow_isomerisation=False),
        dict(name="tol=0.002", n_analog=6, min_sim=0.3, tol=0.002, max_steps=2, template_names=None, allow_isomerisation=False),
        dict(name="tol=0.010", n_analog=6, min_sim=0.3, tol=0.010, max_steps=2, template_names=None, allow_isomerisation=False),
        dict(name="max_steps=1", n_analog=6, min_sim=0.3, tol=0.004, max_steps=1, template_names=None, allow_isomerisation=False),
        dict(name="additions_only", n_analog=6, min_sim=0.3, tol=0.004, max_steps=2, template_names=add_names, allow_isomerisation=False),
        dict(name="removals_only", n_analog=6, min_sim=0.3, tol=0.004, max_steps=2, template_names=rem_names, allow_isomerisation=False),
    ]

    prepared = []
    for i, mid in enumerate(mids, 1):
        spectra, target = H.build_query(queries, mid)
        tid = truth_id[mid]
        analogs, exclude_keys = H.class3_analogs_window(eng, spectra, target, tid)
        prepared.append((mid, tid, analogs, target, exclude_keys))
        print(f"analog [{i}/{len(mids)}] {mid} n_analog={len(analogs)}", flush=True)

    results = {c["name"]: [] for c in conditions}
    per_query = []
    t0 = time.time()
    for mid, tid, analogs, target, exclude_keys in prepared:
        row = dict(molecule_id=mid)
        for c in conditions:
            g = generate_ablation(eng, analogs, target, exclude_keys,
                                  c["n_analog"], c["min_sim"], c["tol"], c["max_steps"],
                                  c["template_names"], c["allow_isomerisation"])
            rec = tid in g
            results[c["name"]].append(rec)
            row[c["name"]] = dict(n_gen=len(g), recovered=rec)
        per_query.append(row)

    summary = dict(
        step="q3_single_factor_ablation",
        scope="paired single-factor ablation on the REAL spectral-analog generate path (truth key excluded), 48 dev queries",
        queries=len(prepared),
        coverage={name: round(sum(v) / len(v), 4) for name, v in results.items()},
        recovered_counts={name: sum(v) for name, v in results.items()},
        elapsed_s=round(time.time() - t0, 1),
        per_query=per_query,
        note="Same analogs/target/exclude reused for all conditions -> true paired comparison.",
    )
    out = "/mnt/d/Paper/casmi/produre2/artifacts/q3_ablation.json"
    with open(out, "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(json.dumps(summary["coverage"], indent=2))
    print("recovered_counts", json.dumps(summary["recovered_counts"], indent=2))


if __name__ == "__main__":
    main()

