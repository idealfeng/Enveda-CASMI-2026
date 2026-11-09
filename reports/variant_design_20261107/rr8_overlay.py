"""Deploy the v8 isomer reranker on a finished submission, with RR3-style rails (romanrozen).

For every molecule whose best library match is below `lib_tau`:
  * G = the candidates of its final list that share the leader's molecular formula (the isomers the model compares);
  * training-set structures in G keep their slots (FREEZE: a model trained on library spectra must not demote the
    structures that do have library spectra); the other members of G are re-ordered among their own slots by
        fused = z(-log position) + alpha * z(model score)            (z over the movable members)
  * everything outside G, and every list with a strong library match, stays as it is.
Candidate sets never change. Returns the new frame and a report; any error leaves the input unchanged (caller's job).
"""
from __future__ import annotations

import math
import time

import numpy as np
import pandas as pd


def _z(v):
    v = np.asarray(v, float)
    sd = v.std()
    return (v - v.mean()) / sd if sd > 1e-12 else np.zeros_like(v)


def load_spectra(test_path):
    t = pd.read_parquet(test_path)
    out = {}
    for r in t.itertuples(index=False):
        ce = getattr(r, 'collision_energy_ev', None)
        try:
            ce = float(np.mean(ce)) if ce is not None and len(ce) else float('nan')
        except Exception:
            ce = float('nan')
        out.setdefault(str(r.molecule_id), []).append(dict(
            mz=np.asarray(r.ms2_mzs, float), it=np.asarray(r.ms2_normalized_intensities, float),
            prec=float(r.precursor_mz), adduct=str(r.adduct),
            mode=1 if str(getattr(r, 'ionization_mode', 'positive')).lower() == 'positive' else -1, ce=ce))
    return out


def model_features(rf, frag, spectra, smiles, cache, fcache):
    X = rf.full_features(spectra, smiles, cache)
    m1 = frag.score_molecule(spectra, smiles, cfg=None, cache=fcache)
    m2 = frag.score_molecule(spectra, smiles, cfg=frag.BASELINE_CFG, cache=fcache)
    M = np.array([[np.nan if a is None else a, np.nan if b is None else b] for a, b in zip(m1, m2)], float)
    with np.errstate(all='ignore'):
        Mc = M - np.nanmean(M, axis=0, keepdims=True)
    return np.hstack([X, M, Mc])


def rerank_list(smiles, scores, frozen, alpha):
    """smiles: the full list; scores/frozen: dicts for members of G (same formula as the leader). Returns new list."""
    pos = {s: i for i, s in enumerate(smiles)}
    movable = [s for s in scores if not frozen.get(s, False)]
    if len(movable) < 2:
        return list(smiles)
    slots = sorted(pos[s] for s in movable)
    base = _z([-math.log(pos[s] + 1) for s in movable])
    rr = _z([scores[s] for s in movable])
    fused = base + float(alpha) * rr
    order = [movable[i] for i in np.argsort(-fused, kind='stable')]
    out = list(smiles)
    for slot, s in zip(slots, order):
        out[slot] = s
    return out


def run(sub, lib_max, spectra, train_keys, booster, rf, frag, alpha=1.0, lib_tau=0.9, max_seconds=1500, log=print):
    """sub: DataFrame molecule_id, smiles (';'-joined). Returns (new DataFrame, report)."""
    from rdkit import Chem, RDLogger
    from rdkit.Chem.rdMolDescriptors import CalcMolFormula
    RDLogger.DisableLog('rdApp.*')
    t0 = time.monotonic()
    info = {}

    def facts(s):
        if s not in info:
            m = Chem.MolFromSmiles(s)
            if m is None:
                info[s] = (None, None)
            else:
                try:
                    k = Chem.MolToInchiKey(m)[:14]
                except Exception:
                    k = None
                info[s] = (CalcMolFormula(m), k)
        return info[s]

    rep = dict(molecules=len(sub), reranked=0, changed=0, top1_changed=0, skipped_library=0, skipped_group=0,
               skipped_frozen=0, no_spectra=0, failed=0, timed_out=0, alpha=float(alpha), lib_tau=float(lib_tau))
    cache, fcache, rows = {}, {}, []
    for mid, joined in zip(sub.molecule_id.astype(str), sub.smiles.astype(str)):
        smis = [s for s in joined.split(';') if s]
        new = smis
        if float(lib_max.get(mid, 0.0)) >= lib_tau:
            rep['skipped_library'] += 1
        elif mid not in spectra:
            rep['no_spectra'] += 1
        elif time.monotonic() - t0 > max_seconds:
            rep['timed_out'] += 1
        elif len(smis) >= 2:
            try:
                f0 = facts(smis[0])[0]
                group = [s for s in smis if f0 is not None and facts(s)[0] == f0]
                frozen = {s: (facts(s)[1] in train_keys) for s in group}
                if len(group) < 2:
                    rep['skipped_group'] += 1
                elif sum(not v for v in frozen.values()) < 2:
                    rep['skipped_frozen'] += 1
                else:
                    F = model_features(rf, frag, spectra[mid], group, cache, fcache)
                    sc = booster.predict(F)
                    scores = {s: float(v) for s, v in zip(group, sc)}
                    new = rerank_list(smis, scores, frozen, alpha)
                    rep['reranked'] += 1
            except Exception as exc:
                rep['failed'] += 1
                if rep['failed'] <= 3:
                    log(f'[rr8] {mid}: {type(exc).__name__}: {exc}')
                new = smis
        if new != smis:
            rep['changed'] += 1
            rep['top1_changed'] += int(new[0] != smis[0])
        rows.append((mid, ';'.join(new) if new else joined))
        if len(cache) > 30000:
            cache.clear()
        if len(fcache) > 30000:
            fcache.clear()
    rep['seconds'] = round(time.monotonic() - t0, 1)
    return pd.DataFrame(rows, columns=['molecule_id', 'smiles']), rep
