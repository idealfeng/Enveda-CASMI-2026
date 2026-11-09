"""Taxonomic consistency of the answer lists (v4, romanrozen): a TIMA-style prior taken from the test set itself.

Natural products of one extract share their producing organisms. Molecules whose leader is a library hit (library
match >= `anchor_lib`) are the anchors; the genera that LOTUS reports for their leaders form the test set's genus
profile. Each anchor spreads one unit of mass over its genera; anchors reported from more than `specific_max`
genera carry no taxonomic information and are left out. A candidate then gets the bonus

    w * (1 - exp(-S / scale)),   S = the largest profile mass among the candidate's own LOTUS genera,

with the molecule's own anchor left out of the profile (leave-one-out). The bonus only enters the ranks 2-25 score of
the public final layer, so it never moves rank 1. A gate keeps it off unless at least `min_specific` anchors are
taxonomically specific and their genus co-occurrence (the share of anchors that share a genus with another anchor)
exceeds the 95th percentile of random anchor sets of the same size drawn from the structures with training spectra
(where class-1 anchors come from), and the floor `min_cooccur`: the sample must be more clustered than chance.
Candidates without LOTUS genera get no bonus. Any missing input disables the prior (empty table).

Pure functions (testable without Kaggle): genera_profile, cooccurrence_share, bonus_table.
I/O wrapper used by the notebook: run(root, input_root, ...).
"""
from __future__ import annotations

import glob
import json
import math
import os
from collections import defaultdict
from pathlib import Path

DEFAULTS = dict(w=0.05, anchor_lib=0.87, specific_max=25, min_specific=6, min_cooccur=0.25, scale=0.5)


def genera_profile(anchor_genera, specific_max=25):
    """anchor_genera {mid: set(genus)} -> (mass {genus: m}, contrib {mid: {genus: m}}) over specific anchors only."""
    contrib = {}
    for mid, gs in anchor_genera.items():
        gs = {g for g in gs if g}
        if not gs or len(gs) > int(specific_max):
            continue
        m = 1.0 / len(gs)
        contrib[mid] = {g: m for g in gs}
    mass = defaultdict(float)
    for c in contrib.values():
        for g, m in c.items():
            mass[g] += m
    return dict(mass), contrib


def cooccurrence_share(contrib):
    """Fraction of specific anchors that share at least one genus with another specific anchor."""
    if not contrib:
        return 0.0
    count = defaultdict(int)
    for c in contrib.values():
        for g in c:
            count[g] += 1
    shared = sum(1 for c in contrib.values() if any(count[g] > 1 for g in c))
    return shared / len(contrib)


def null_cooccurrence(population_genera, k, draws=300, seed=0, specific_max=25):
    """Co-occurrence shares of `draws` random sets of k specific structures: (mean, p95). population_genera: [set]."""
    import random
    pool = [gs for gs in population_genera if 1 <= len(gs) <= int(specific_max)]
    if k < 2 or len(pool) < k:
        return None, None
    rng = random.Random(seed)
    vals = []
    for _ in range(int(draws)):
        sample = rng.sample(pool, k)
        _, contrib = genera_profile({i: gs for i, gs in enumerate(sample)}, specific_max)
        vals.append(cooccurrence_share(contrib))
    vals.sort()
    return sum(vals) / len(vals), vals[min(len(vals) - 1, int(0.95 * len(vals)))]


def bonus_table(candidates, genera_of, mass, contrib, w, scale):
    """candidates {mid: [smiles]}, genera_of {smiles: set(genus)} -> {mid: {smiles: bonus}} (positive bonuses only)."""
    out = {}
    if w <= 0 or not mass:
        return out
    for mid, smis in candidates.items():
        own = contrib.get(mid, {})
        row = {}
        for s in smis:
            gs = genera_of.get(s)
            if not gs:
                continue
            support = max((mass.get(g, 0.0) - own.get(g, 0.0)) for g in gs)
            if support > 1e-12:
                row[s] = float(w) * (1.0 - math.exp(-support / float(scale)))
        if row:
            out[mid] = row
    return out


# ── I/O wrapper ──────────────────────────────────────────────────────────────────────────────────────────────────
def _find(input_root, name):
    hits = sorted(glob.glob(os.path.join(str(input_root), '**', name), recursive=True), key=len)
    return Path(hits[0]) if hits else None


def _pick(columns, *names, contains=None):
    low = {c.lower(): c for c in columns}
    for n in names:
        if n in low:
            return low[n]
    if contains:
        for c in columns:
            if contains in c.lower():
                return c
    return None


def load_genera(input_root):
    """{ik14: set(genus)} from the knowledge table's lotus_structure_genus.parquet; plus {scorer_key: set(ik14)}."""
    import pandas as pd
    path = _find(input_root, 'lotus_structure_genus.parquet')
    if path is None:
        raise FileNotFoundError('lotus_structure_genus.parquet not attached (casmi26-natural-product-knowledge-table)')
    import pyarrow.parquet as pq
    cols = pq.read_schema(path).names
    kcol = _pick(cols, 'ik14', 'inchikey14', 'structure_ik14', 'inchikey_14', contains='ik14')
    gcol = _pick(cols, 'genus', 'organism_genus', 'taxon_genus', contains='genus')
    if kcol is None or gcol is None:
        raise KeyError(f'genus table columns not recognised: {cols}')
    t = pd.read_parquet(path, columns=[kcol, gcol]).dropna()
    t[kcol] = t[kcol].astype(str).str[:14]
    t[gcol] = t[gcol].astype(str).str.strip()
    t = t[t[gcol].str.len() > 0]
    genera = {k: set(g) for k, g in t.groupby(kcol, sort=False)[gcol]}
    by_key = defaultdict(set)
    trained = set()
    np_path = _find(input_root, 'natural_products.parquet')
    if np_path is not None:
        ncols = pq.read_schema(np_path).names
        a, b = _pick(ncols, 'ik14', contains='ik14'), _pick(ncols, 'scorer_key', contains='scorer')
        tr = _pick(ncols, 'in_casmi_train', contains='in_casmi_train')
        if a and b:
            nt = pd.read_parquet(np_path, columns=[a, b]).dropna()
            for k, sk in zip(nt[a].astype(str).str[:14], nt[b].astype(str)):
                by_key[sk[:14]].add(k)
        if a and tr:
            nt = pd.read_parquet(np_path, columns=[a, tr])
            trained = set(nt.loc[nt[tr].fillna(False).astype(bool), a].astype(str).str[:14])
    return genera, dict(by_key), dict(path=str(path), key=kcol, genus=gcol, rows=int(len(t)), structures=len(genera),
                                      trained_structures=len(trained), _trained=trained)


def candidate_genera(smiles_keys, genera, by_key):
    """smiles_keys {smiles: metric_key or None} -> {smiles: set(genus)} through the raw InChIKey block and the scorer key."""
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog('rdApp.*')
    out = {}
    for s, mk in smiles_keys.items():
        keys = set()
        try:
            m = Chem.MolFromSmiles(s)
            if m is not None:
                ik = Chem.MolToInchiKey(m)
                if ik:
                    keys.add(ik[:14])
        except Exception:
            pass
        if isinstance(mk, str) and mk:
            keys.add(mk[:14])
            keys |= by_key.get(mk[:14], set())
        gs = set()
        for k in keys:
            gs |= genera.get(k, set())
        if gs:
            out[s] = gs
    return out


def run(root, input_root, w=None, anchor_lib=None, specific_max=None, min_specific=None, min_cooccur=None, scale=None):
    """Returns (bonus {mid: {smiles: b}}, report). Never raises for missing inputs: the report says why it is off."""
    import pandas as pd
    p = dict(DEFAULTS)
    for k, v in dict(w=w, anchor_lib=anchor_lib, specific_max=specific_max, min_specific=min_specific,
                     min_cooccur=min_cooccur, scale=scale).items():
        if v is not None:
            p[k] = v
    rep = dict(status='off', params=p)
    if float(p['w']) <= 0:
        rep['status'] = 'off (weight 0)'
        return {}, rep
    root = Path(root)
    genera, by_key, info = load_genera(input_root)
    trained = info.pop('_trained', set())
    rep['genus_table'] = info
    ev = pd.read_parquet(root / 'neural_candidate_features.parquet',
                         columns=['molecule_id', 'smiles', 'metric_key', 'library_max', 'processed'])
    ev['molecule_id'] = ev.molecule_id.astype(str)
    ev = ev[ev.processed.astype(bool)]
    custom = pd.read_csv(root / 'variants' / 'submission_CUSTOM.csv', dtype=str, keep_default_na=False)
    leaders = {str(m): s.split(';')[0] for m, s in zip(custom.molecule_id, custom.smiles)}
    lib = ev.groupby('molecule_id', sort=False).library_max.max().to_dict()
    candidates = {m: g.smiles.astype(str).tolist() for m, g in ev.groupby('molecule_id', sort=False)}
    keys = dict(zip(ev.smiles.astype(str), ev.metric_key))
    for m in candidates:
        if leaders.get(m) and leaders[m] not in keys:
            keys[leaders[m]] = None
    gen = candidate_genera(keys, genera, by_key)
    anchors = {m: gen.get(leaders.get(m), set()) for m in candidates if float(lib.get(m, 0.0)) >= float(p['anchor_lib'])}
    mass, contrib = genera_profile(anchors, p['specific_max'])
    share = cooccurrence_share(contrib)
    top = sorted(mass.items(), key=lambda kv: -kv[1])[:10]
    rep.update(molecules=len(candidates), anchors=len(anchors),
               anchors_with_genera=sum(1 for g in anchors.values() if g), specific_anchors=len(contrib),
               cooccurrence_share=round(share, 4), genera_in_profile=len(mass),
               top_genera=[(g, round(m, 3)) for g, m in top],
               candidates_with_genera=int(sum(1 for s in ev.smiles.astype(str) if s in gen)),
               candidates_total=int(len(ev)))
    if len(contrib) < int(p['min_specific']):
        rep['status'] = f"off: {len(contrib)} specific anchors (< {p['min_specific']})"
        return {}, rep
    # the null: random sets of the same size from the structures class-1 anchors are drawn from (with training spectra)
    population = [genera[k] for k in trained if k in genera]
    if len(population) < 200:
        population = list(genera.values())
    null_mean, null_p95 = null_cooccurrence(population, len(contrib), specific_max=p['specific_max'])
    rep.update(null_population=len(population), null_mean=None if null_mean is None else round(null_mean, 4),
               null_p95=None if null_p95 is None else round(null_p95, 4))
    need = max(float(p['min_cooccur']), (null_p95 if null_p95 is not None else 0.0) + 1e-9)
    if share < need:
        rep['status'] = (f"off: anchor genus co-occurrence {share:.2f} not above the random-set level "
                         f"(p95 {null_p95}, floor {p['min_cooccur']}): sample looks diffuse")
        return {}, rep
    bonus = bonus_table(candidates, gen, mass, contrib, float(p['w']), float(p['scale']))
    vals = [b for row in bonus.values() for b in row.values()]
    rep.update(status='on', lists_with_bonus=len(bonus), candidates_with_bonus=len(vals),
               mean_bonus=round(sum(vals) / len(vals), 5) if vals else 0.0, max_bonus=round(max(vals), 5) if vals else 0.0)
    return bonus, rep


if __name__ == '__main__':   # python taxonomy_prior.py <root> <input_root>
    import sys
    b, r = run(sys.argv[1], sys.argv[2])
    print(json.dumps(r, indent=2, default=str))
