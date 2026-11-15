"""Leader-safe consensus re-ranking for CASMI26 answer lists.

Runs after the frozen 0.465 pipeline and after the neural scorer. It never reruns a
model: it reorders the candidates of each molecule and, only when asked, lets a few
candidates that the pipeline left outside its list compete for the last places.

Order rule
    rank 1   = leader of   1/(k + b) + w_top / (k + n)
    ranks 2+ = the others, ordered by   1/(k + b) + w_mid / (k + n)
with b the baseline rank, n the neural rank among the same candidates and k the
offset. With w_top == w_mid this is exactly the fixed-weight reciprocal-rank fusion
of the public 0.466 notebook (``ranking.rrf_order``), which build_variants re-checks.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ranking import rrf_order, stable_rank

PRESETS = {
    'V0': dict(w_top=0.00, w_mid=0.00, rescue=0, label='Baseline 0.465 - no neural term'),
    'V1': dict(w_top=0.25, w_mid=0.25, rescue=0, label='Neural RRF 0.25 - public 0.466 recipe'),
    'V2': dict(w_top=0.25, w_mid=0.50, rescue=0, label='Leader-safe consensus 0.25 / 0.50'),
    'V3': dict(w_top=0.25, w_mid=0.50, rescue=3, label='Leader-safe consensus + 3-slot tail rescue'),
    'V4': dict(w_top=0.25, w_mid=1.00, rescue=0, label='Bold consensus 0.25 / 1.00'),
}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def leader_safe_order(neural_scores, w_top, w_mid, offset=3.0):
    """Indices of the new order (baseline order = 0..n-1)."""
    s = np.asarray(neural_scores, dtype=float)
    if len(s) == 0:
        return np.zeros(0, dtype=int)
    first = np.asarray(rrf_order(s, w_top, offset), dtype=int)
    if w_mid == w_top:
        return first
    lead = int(first[0])
    rest = [int(i) for i in rrf_order(s, w_mid, offset) if int(i) != lead]
    return np.asarray([lead] + rest, dtype=int)


def rescue_tail(smiles, scores, outsiders, slots, limit=25):
    """Let outside candidates compete for the last `slots` places by neural score.

    smiles, scores: the reordered list and its neural scores.
    outsiders: [(smiles, neural_score)] whose metric identities differ from every
    listed candidate and from each other (guaranteed by outsiders.py).
    Free places of a list shorter than `limit` are offered as well.
    Returns (new_list, number_of_outsiders_admitted).
    """
    smiles = list(smiles)
    scores = [float(v) for v in scores]
    if slots <= 0 or not outsiders or not smiles:
        return smiles, 0
    k = min(int(slots), len(smiles))
    free = max(0, int(limit) - len(smiles))
    head = smiles[:len(smiles) - k]
    pool = [(s, v, 0) for s, v in zip(smiles[len(smiles) - k:], scores[len(scores) - k:])]
    pool += [(str(s), float(v), 1) for s, v in outsiders if np.isfinite(float(v)) and str(s) not in smiles]
    pool.sort(key=lambda t: (-t[1], t[2]))  # stable; on ties a listed candidate keeps its place
    chosen = pool[:k + free]
    out = (head + [s for s, _, _ in chosen])[:limit]
    return out, int(sum(t[2] for t in chosen))


def read_outsiders(path):
    out = {}
    if not path or not Path(path).is_file():
        return out
    frame = pd.read_parquet(path)
    if frame.empty or 'neural_ok' not in frame.columns:
        return out
    score = pd.to_numeric(frame.neural_score, errors='coerce')
    frame = frame[frame.neural_ok.astype(bool) & np.isfinite(score)]
    for mid, g in frame.groupby('molecule_id', sort=False):
        g = g.sort_values('baseline_rank', kind='stable')
        out[str(mid)] = list(zip(g.smiles.astype(str), g.neural_score.astype(float)))
    return out


def build_variants(evidence, baseline, outdir, presets=None, offset=3.0, outsiders=None):
    """Write submission_<name>.csv for every preset; return (report, moves)."""
    presets = dict(PRESETS if presets is None else presets)
    frame = pd.read_parquet(evidence)
    base = pd.read_csv(baseline, dtype=str, keep_default_na=False)
    assert list(base.columns) == ['molecule_id', 'smiles'] and base.molecule_id.is_unique
    groups = {str(m): g.sort_values('baseline_rank', kind='stable') for m, g in frame.groupby('molecule_id', sort=False)}
    assert set(groups) == set(base.molecule_id), 'evidence and baseline cover different molecules'
    outs = read_outsiders(outsiders)
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    report, moves = {}, []
    for name, cfg in presets.items():
        rows = []
        stats = dict(active_rows=0, changed_rows=0, changed_top1=0, rescued=0)
        for mid, text in base.itertuples(index=False):
            original = text.split(';')
            g = groups[mid]
            assert g.smiles.tolist() == original, f'evidence order differs from the baseline: {mid}'
            active = bool(g.processed.iloc[0]) and bool(g.neural_ok.all())
            if active:
                order = leader_safe_order(g.neural_score.values, cfg['w_top'], cfg['w_mid'], offset)
            else:
                order = np.arange(len(g))
            new = g.smiles.iloc[order].tolist()
            new_scores = g.neural_score.astype(float).values[order].tolist()
            rescued = 0
            if active and int(cfg.get('rescue', 0)) > 0 and outs.get(mid):
                new, rescued = rescue_tail(new, new_scores, outs[mid], int(cfg['rescue']))
            assert 1 <= len(new) <= 25 and len(set(new)) == len(new), mid
            if not rescued:
                assert sorted(new) == sorted(original), f'candidate set changed: {mid}'
            stats['active_rows'] += int(active)
            stats['changed_rows'] += int(new != original)
            stats['changed_top1'] += int(new[0] != original[0])
            stats['rescued'] += int(rescued)
            rows.append((mid, ';'.join(new)))
            if active:
                b_rank = {s: i + 1 for i, s in enumerate(original)}
                n_rank = dict(zip(g.smiles, stable_rank(g.neural_score.values)))
                for pos, s in enumerate(new, 1):
                    moves.append((name, mid, s, pos, b_rank.get(s, 0), int(n_rank.get(s, 0))))
        out = pd.DataFrame(rows, columns=['molecule_id', 'smiles'])
        assert out.molecule_id.tolist() == base.molecule_id.tolist()
        path = outdir / f'submission_{name}.csv'
        out.to_csv(path, index=False)
        report[name] = dict(cfg, offset=offset, file=path.name, sha256=sha256(path), **stats)
    moves = pd.DataFrame(moves, columns=['variant', 'molecule_id', 'smiles', 'final_rank', 'baseline_rank', 'neural_rank'])
    (outdir / 'consensus_report.json').write_text(json.dumps(report, indent=2))
    return report, moves


def validate(path, sample_ids, baseline_path=None, allow_new=False, identity_of=None):
    """Raise unless `path` is a well-formed answer file for the expected molecules."""
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    assert list(frame.columns) == ['molecule_id', 'smiles'], 'columns'
    assert frame.molecule_id.tolist() == list(sample_ids), 'molecule order'
    lists = frame.smiles.str.split(';')
    assert lists.map(len).between(1, 25).all(), 'list length'
    assert lists.map(lambda v: all(x.strip() for x in v) and len(set(v)) == len(v)).all(), 'empty or repeated SMILES'
    if baseline_path is not None:
        base = pd.read_csv(baseline_path, dtype=str, keep_default_na=False)
        assert base.molecule_id.tolist() == frame.molecule_id.tolist(), 'baseline order'
        for before, after in zip(base.smiles, frame.smiles):
            b, a = before.split(';'), after.split(';')
            if allow_new:
                assert len(a) >= min(len(b), 25), 'list got shorter'
            else:
                assert sorted(b) == sorted(a), 'candidate set changed'
    if identity_of is not None:
        for answer in frame.smiles:
            keys = [identity_of.get(s) for s in answer.split(';')]
            keys = [k for k in keys if k]
            assert len(keys) == len(set(keys)), 'duplicate metric identity'
    return frame
