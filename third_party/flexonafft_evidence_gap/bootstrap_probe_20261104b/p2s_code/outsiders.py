"""Collect candidates that the frozen pipeline considered but left outside its final list.

Reads the pipeline's own record of its candidate lists (e004_candidate_inputs.json),
walks the fusion overflow, Engine 2, the main-engine tail and the PubChem channel in
round-robin rank order, and keeps structures whose official metric identity (the frozen
notebook's own metric_identity, executed from its source) is new for the molecule.
Output rows follow the evidence schema the neural scorer reads; baseline_rank 26, 27, ...
only fixes their order.

usage: python outsiders.py <frozen.ipynb> <root> <evidence.parquet> <out.parquet> [per_molecule] [max_checks]
"""
import json
import sys
import time
from pathlib import Path

import pandas as pd

COLUMNS = ['molecule_id', 'smiles', 'metric_key', 'source', 'source_rank', 'baseline_rank', 'processed']


def load_identity(frozen):
    cells = json.loads(Path(frozen).read_text())['cells']
    hits = [''.join(c['source']) for c in cells
            if c['cell_type'] == 'code' and 'def metric_identity' in ''.join(c['source'])]
    assert len(hits) == 1, 'metric identity cell not found in the frozen source'
    scope = {'__name__': 'frozen_metric_identity'}
    exec(compile(hits[0], 'frozen_metric_identity', 'exec'), scope)
    return scope['metric_identity']


def source_lists(payload, mid):
    eng = payload.get('engine2', {}).get(mid) or {}
    pc = payload.get('pubchem', {}).get(mid) or {}
    return [('fusion_overflow', list(payload.get('fusion_overflow', {}).get(mid) or [])),
            ('engine2', list(eng.get('smiles') or [])),
            ('main_tail', list(payload.get('base_tail', {}).get(mid) or [])),
            ('pubchem', list(pc.get('pc') or []))]


def collect(payload, evidence, identity, per_molecule=12, max_checks=30):
    rows = []
    active = evidence[evidence.processed.astype(bool)]
    for mid, g in active.groupby('molecule_id', sort=False):
        mid = str(mid)
        if mid not in payload.get('prefusion', {}):
            continue
        listed = g.sort_values('baseline_rank', kind='stable').smiles.astype(str).tolist()
        taken = {k for k in g.metric_key.tolist() if isinstance(k, str) and k}
        seen = set(listed)
        lists = source_lists(payload, mid)
        depth = max((len(v) for _, v in lists), default=0)
        picked = checks = 0
        for r in range(depth):
            if picked >= per_molecule or checks >= max_checks:
                break
            for name, values in lists:
                if r >= len(values) or picked >= per_molecule or checks >= max_checks:
                    continue
                s = str(values[r]).strip()
                if not s or s == 'CCO' or s in seen:
                    continue
                seen.add(s)
                checks += 1
                key = identity(s)
                if key is None or key[0] in taken:
                    continue
                taken.add(key[0])
                picked += 1
                rows.append((mid, s, key[0], name, r + 1, 25 + picked, True))
    return pd.DataFrame(rows, columns=COLUMNS)


if __name__ == '__main__':
    frozen, root, evidence_path, out = sys.argv[1:5]
    per = int(sys.argv[5]) if len(sys.argv) > 5 else 12
    checks = int(sys.argv[6]) if len(sys.argv) > 6 else 30
    t0 = time.time()
    identity = load_identity(frozen)
    payload = json.loads((Path(root) / 'e004_candidate_inputs.json').read_text())
    evidence = pd.read_parquet(evidence_path)
    frame = collect(payload, evidence, identity, per, checks)
    frame.to_parquet(out, index=False)
    by_source = frame.source.value_counts().to_dict() if len(frame) else {}
    print('OUTSIDERS', len(frame), 'candidates for', frame.molecule_id.nunique(), 'molecules',
          json.dumps(by_source), f'{time.time() - t0:.0f}s', flush=True)
