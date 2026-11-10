"""Q5: which reaction templates / parent-selection actually contribute, with the REAL
reaction path (combo) recorded. Runs the real Engine's spectral analog channel and a
combo-capturing generate() on all 48 dev-panel queries."""
import json
import sys
import time

sys.path.insert(0, "/mnt/d/Paper/casmi/produre2")
import numpy as np

import q345_lib as H
from casmi import chem, derive as dmod


def derive_with_combo(smiles, delta, tol=0.003, max_steps=2, max_per_analog=300, allow_isomerisation=True):
    from rdkit import Chem
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return []
    combos = dmod.matching_transforms(delta, tol, max_steps)
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
    return [(s, c) for s, c in out.items()][:max_per_analog]


def generate_with_paths(eng, analogs, target, exclude_keys, tol=None):
    cfg = eng.cfg; L = eng.L; P = eng.pool
    tol = tol if tol is not None else max(cfg.gen_tol_da, target * cfg.ppm_win * 1e-6)
    out = []; seen = set(exclude_keys)
    parents = [a for a in analogs if a[1] >= cfg.gen_min_sim][:cfg.gen_n_analog]
    paths = []
    for sid, sim, shift, _ in parents:
        psmi = L.struct_smiles[sid]
        pfp = np.unpackbits(eng.train_fp[sid])[:P.nbits].astype(np.float32)
        delta = target - float(L.struct_mass[sid])
        try:
            prods = derive_with_combo(psmi, delta, tol=tol, max_steps=2, max_per_analog=cfg.gen_max_per_parent)
        except Exception:
            prods = []
        for s, combo in prods:
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
            inter = float((fp * pfp).sum()); tan = inter / (fp.sum() + pfp.sum() - inter + 1e-9)
            seen.add(k)
            out.append(dict(smiles=std, key=k, parent_sid=int(sid), sim=float(sim), delta=round(delta, 5),
                            combo=list(combo), steps=len(combo), tan=round(float(tan), 4)))
            paths.append(out[-1])
            if len(out) >= cfg.gen_max_total:
                return out, paths
    return out, paths


def main():
    eng = H.load_engine(bank=False)
    queries, truth = H.load_queries_truth()
    truth_id = dict(zip(truth.molecule_id, truth.official_identity))
    mids = list(truth.molecule_id)

    per_query = []
    template_counts = {}
    combo_counts = {}
    parent_sims = []
    t0 = time.time()
    for i, mid in enumerate(mids, 1):
        spectra, target = H.build_query(queries, mid)
        tid = truth_id[mid]
        analogs, exclude_keys = H.class3_analogs_window(eng, spectra, target, tid)
        parents = [a for a in analogs if a[1] >= eng.cfg.gen_min_sim][:eng.cfg.gen_n_analog]
        out, paths = generate_with_paths(eng, analogs, target, exclude_keys)
        for p in paths:
            parent_sims.append(p["sim"])
            for name in p["combo"]:
                template_counts[name] = template_counts.get(name, 0) + 1
            combo_counts[tuple(p["combo"])] = combo_counts.get(tuple(p["combo"]), 0) + 1
        recovered = any(p["key"] == tid for p in paths)
        per_query.append(dict(molecule_id=mid, n_parents=len(parents),
                              parent_sims=[round(a[1], 4) for a in parents],
                              n_generated=len(out), recovered=recovered,
                              hit_combos=[tuple(p["combo"]) for p in paths if p["key"] == tid]))
        print(f"[{i}/{len(mids)}] {mid} parents={len(parents)} gen={len(out)} recovered={recovered}", flush=True)

    cats = {}
    for name in template_counts:
        d = dmod._delta_mass(dmod._TRANSFORMS[name][1])
        cats[name] = "addition" if d > 0 else ("removal" if d < 0 else "neutral")

    summary = dict(
        step="q5_real_paths",
        scope="real spectral analog channel + combo-capturing derive on 48 dev queries (class-3 truth-key exclusion)",
        queries=len(per_query),
        recovered_queries=sum(1 for r in per_query if r["recovered"]),
        generation_coverage=round(sum(1 for r in per_query if r["recovered"]) / len(per_query), 4),
        parent_sim=dict(n=int(len(parent_sims)), mean=round(float(np.mean(parent_sims)), 4),
                        min=round(float(np.min(parent_sims)), 4), max=round(float(np.max(parent_sims)), 4)),
        template_counts=dict(sorted(template_counts.items(), key=lambda x: -x[1])),
        template_categories=cats,
        combo_counts={";".join(k): n for k, n in sorted(combo_counts.items(), key=lambda x: -x[1])},
        per_query=per_query,
        elapsed_s=round(time.time() - t0, 1),
        note="steps recorded as len(combo) (original engine hardcodes steps=1; this is the true path).",
    )
    out = "/mnt/d/Paper/casmi/produre2/artifacts/q5_real_paths.json"
    with open(out, "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(json.dumps({k: summary[k] for k in ("queries", "recovered_queries", "generation_coverage",
                                               "parent_sim", "elapsed_s")}, indent=2))


if __name__ == "__main__":
    main()
