"""Scoring candidates: analog propagation, identity gating, and features for the ranker."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .candidates import candidates_in_window
from .chem import tanimoto
from .data import molecule_masses
from .metric import Scores
from .spectra import Hits, aggregate_hits


def _analog_weights(analog_hits: Hits, power: float) -> dict[str, dict[str, float]]:
    """{molecule: {analog key: sum over query spectra of similarity ** power}}."""
    weights: dict[str, dict[str, float]] = {}
    for mol, best in analog_hits:
        w = weights.setdefault(mol, {})
        for key, s in best.items():
            w[key] = w.get(key, 0.0) + s ** power
    return weights


def analog_propagation(
    analog_hits: Hits, masses: pd.Series, pool: pd.DataFrame,
    fps: np.ndarray, power: float = 4.0, ppm: float = 10.0, excluded: dict[str, str] | None = None,
    candidate_mask: np.ndarray | None = None, analog_mask: np.ndarray | None = None,
) -> Scores:
    """Score the same-mass candidates through spectral analogs.

    For one molecule, each analog a (a similar reference spectrum, found by hybrid search)
    gets a weight w_a = sum over query spectra of sim(q, a) ** power. The power strongly favors
    the most similar analogs. Each candidate c of the mass window then scores
        score(c) = sum_a  w_a * Tanimoto(c, a),
    so a candidate structurally close to the most similar analogs rises to the top.

    `excluded`: {molecule_id: key} removed from the candidates (class-3 condition).
    `candidate_mask`: boolean per pool row, the **proposable** structures. Analogs are looked up
    in the whole pool: they come from the spectral library, not from the candidate pool, and
    restricting one must not deplete the other.
    `analog_mask`: boolean per pool row, the structures allowed **as analogs** (e.g. to drop
    synthetic compounds, which point to wrong candidates).
    """
    key_to_row = pd.Series(np.arange(len(pool)), index=pool["key"])
    if analog_mask is not None:
        key_to_row = key_to_row[analog_mask]
    pool_mass = pool["exact_mass"].to_numpy()
    pool_keys = pool["key"].to_numpy()
    weights = _analog_weights(analog_hits, power)
    scores = {}
    for mol, mass in masses.items():
        cand = candidates_in_window(pool_mass, mass, ppm)
        if candidate_mask is not None:
            cand = cand[candidate_mask[cand]]
        if excluded and mol in excluded:
            cand = cand[pool_keys[cand] != excluded[mol]]
        w = {k: v for k, v in weights.get(mol, {}).items() if k in key_to_row.index}
        if len(cand) == 0:
            scores[mol] = {}
            continue
        if not w:
            scores[mol] = {k: 0.0 for k in pool_keys[cand]}
            continue
        a_rows = key_to_row[list(w)].to_numpy()
        sim = tanimoto(fps[cand], fps[a_rows]) @ np.fromiter(w.values(), dtype=np.float32)
        scores[mol] = dict(zip(pool_keys[cand], sim.astype(float)))
    return scores


def combine_scores(identity_scores: Scores, analog_scores: Scores, threshold: float = 0.8,
                   w_identity: float = 10.0) -> Scores:
    """Identity first (when convincing), analogs next.

    `identity_scores`: best identity similarity per structure ("max" aggregation). An identity
    match only counts if it reaches `threshold`: below it, the matches are usually other
    same-mass isomers whose spectrum looks a little alike, and analogs already rank them.
    Final score = analog score normalized to max 1 + w_identity × identity similarity if above
    the threshold.
    """
    out = {}
    for mol in set(identity_scores) | set(analog_scores):
        an = analog_scores.get(mol, {})
        top = max(an.values(), default=0) or 1.0
        s = {k: v / top for k, v in an.items()}
        for k, v in identity_scores.get(mol, {}).items():
            if v >= threshold:
                s[k] = s.get(k, 0.0) + w_identity * v
        out[mol] = s
    return out


def fill_slots(primary: Scores, secondary: Scores, n: int = 25) -> Scores:
    """Complete each list of `primary` (up to n) with the best candidates of `secondary`.

    Returns decreasing scores reproducing this order (primary first). Slots filled this way
    come after every primary candidate, so they can only raise the score.
    """
    out = {}
    for mol in set(primary) | set(secondary):
        first = [k for k, _ in sorted(primary.get(mol, {}).items(), key=lambda kv: -kv[1])][:n]
        seen = set(first)
        rest = [k for k, _ in sorted(secondary.get(mol, {}).items(), key=lambda kv: -kv[1]) if k not in seen]
        out[mol] = {k: float(n - i) for i, k in enumerate((first + rest)[:n])}
    return out


# --------------------------------------------------------------------------------------------
# Features for the learned ranker
# --------------------------------------------------------------------------------------------
FEATURES = [
    "an16", "an4", "an1", "an16_rel", "an16_rank", "id_max", "id_n_spectra",
    "tani_best_analog", "tani_max_top10", "has_visible_spectra", "in_coconut", "np_likeness",
    "mass_err_ppm", "exact_mass", "n_candidates", "best_analog_sim", "n_query_spectra",
]
DERIVED_FEATURES = ["id_rank", "id_rel", "tani_rank"]


def candidate_features(identity_hits: Hits, hybrid_hits: Hits, queries: pd.DataFrame, pool: pd.DataFrame,
                       fps: np.ndarray, visible_keys: set, np_like: pd.Series,
                       truth: dict | None = None, excluded: dict | None = None,
                       candidate_mask: np.ndarray | None = None, analog_mask: np.ndarray | None = None,
                       identity_threshold: float = 0.9) -> pd.DataFrame:
    """Table (molecule, candidate) -> features, for the ranker.

    Candidates = the mass window (restricted by `candidate_mask`) + structures confirmed by a
    strong identity match, even outside the candidate pool (as in `combine_scores`).

    Beware of leakage: `visible_keys` = structures with at least one reference spectrum
    **allowed** in the simulated condition (not the full training set). In the real test, a
    class-2 molecule never has a public spectrum; with the full training set, the simulated
    correct answer would "have spectra" and the ranker would learn a wrong rule.
    If `truth` ({molecule_id: key}) is given, a `label` column marks the correct answer.
    """
    masses = molecule_masses(queries)
    n_spec = queries.groupby("molecule_id").size()
    an = {p: analog_propagation(hybrid_hits, masses, pool, fps, power=p, excluded=excluded,
                                candidate_mask=candidate_mask, analog_mask=analog_mask) for p in (16, 4, 1)}
    ident = aggregate_hits(identity_hits, "max")
    id_count: dict[str, dict[str, int]] = {}
    for mol, best in identity_hits:
        d = id_count.setdefault(mol, {})
        for k in best:
            d[k] = d.get(k, 0) + 1
    weights = _analog_weights(hybrid_hits, 16)
    best_sim: dict[str, float] = {}
    for mol, best in hybrid_hits:
        if best:
            best_sim[mol] = max(best_sim.get(mol, 0.0), max(best.values()))
    key_to_row = pd.Series(np.arange(len(pool)), index=pool["key"])
    analog_rows = key_to_row if analog_mask is None else key_to_row[analog_mask]
    pool_mass = pool["exact_mass"].to_numpy()

    frames = []
    for mol, s16 in an[16].items():
        extra = [k for k, v in ident.get(mol, {}).items()
                 if v >= identity_threshold and k not in s16 and k in key_to_row.index]
        keys = list(s16) + extra
        if not keys:
            continue
        rows = key_to_row[keys].to_numpy()
        f = pd.DataFrame({"molecule_id": mol, "key": keys})
        f["an16"] = [s16.get(k, 0.0) for k in keys]
        f["an4"] = [an[4][mol].get(k, 0.0) for k in keys]
        f["an1"] = [an[1][mol].get(k, 0.0) for k in keys]
        top = f["an16"].max()
        f["an16_rel"] = f["an16"] / top if top > 0 else 0.0
        f["an16_rank"] = f["an16"].rank(ascending=False, method="min")
        f["id_max"] = [ident.get(mol, {}).get(k, 0.0) for k in keys]
        f["id_n_spectra"] = [id_count.get(mol, {}).get(k, 0) for k in keys]
        analogs = [k for k, _ in sorted(weights.get(mol, {}).items(), key=lambda kv: -kv[1])
                   if k in analog_rows.index][:10]
        if analogs:
            t = tanimoto(fps[rows], fps[analog_rows[analogs].to_numpy()])
            f["tani_best_analog"] = t[:, 0]
            f["tani_max_top10"] = t.max(axis=1)
        else:
            f["tani_best_analog"] = f["tani_max_top10"] = 0.0
        f["has_visible_spectra"] = [k in visible_keys for k in keys]
        f["in_coconut"] = pool["in_coconut"].to_numpy()[rows]
        f["np_likeness"] = np_like.to_numpy()[rows]
        f["exact_mass"] = pool_mass[rows]
        f["mass_err_ppm"] = np.abs(pool_mass[rows] - masses[mol]) / masses[mol] * 1e6
        f["n_candidates"] = len(keys)
        f["best_analog_sim"] = best_sim.get(mol, 0.0)
        f["n_query_spectra"] = n_spec.get(mol, 0)
        if truth is not None:
            f["label"] = (f["key"] == truth.get(mol)).astype(int)
        frames.append(f)
    out = pd.concat(frames, ignore_index=True)
    out["has_visible_spectra"] = out["has_visible_spectra"].astype(int)
    out["in_coconut"] = out["in_coconut"].astype(int)
    return out


def add_derived_features(table: pd.DataFrame, group_cols=("molecule_id",)) -> pd.DataFrame:
    """Features relative to the molecule (computed within each group of candidates).

    - id_rank / id_rel: rank and relative value of the identity similarity within the molecule
      ("is this candidate the best by identity?", whatever the absolute level);
    - tani_rank: rank of the similarity to the closest analog.
    """
    g = table.groupby(list(group_cols))
    table = table.copy()
    table["id_rank"] = g["id_max"].rank(ascending=False, method="min")
    top = g["id_max"].transform("max")
    table["id_rel"] = np.where(top > 0, table["id_max"] / top.replace(0, 1), 0.0)
    table["tani_rank"] = g["tani_max_top10"].rank(ascending=False, method="min")
    return table


def scores_from_table(table: pd.DataFrame, score_col: str) -> Scores:
    """{molecule_id: {key: score}} from a feature table and one of its score columns."""
    return {mol: dict(zip(g["key"], g[score_col])) for mol, g in table.groupby("molecule_id")}
