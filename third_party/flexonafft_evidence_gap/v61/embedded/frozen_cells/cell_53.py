# Rank-2 placement of the second engine's leading structure (since v48), after
# antriksharya/casmi26-lb-0-443-v7c-engine-2-rank-2-insert (MODE 'rank2'): the first structure of the second-engine
# list moves to rank 2 unless it already holds rank 1; keys = E006 metric identity; errors keep E006's file unchanged.
def _rank2_overlay(scope):
    import hashlib, json, os
    from pathlib import Path
    import pandas as pd
    path = Path('submission.csv')
    control = path.read_bytes()
    report = dict(control_sha256=hashlib.sha256(control).hexdigest(), rows=0, inserted=0, status='fallback')
    try:
        identity = scope['metric_identity']
        engine = scope['ENG'] if isinstance(scope.get('ENG'), dict) else {}
        frame = pd.read_csv(path, dtype=str, keep_default_na=False)
        rows = []
        for mid, answer in frame.itertuples(index=False):
            report['rows'] += 1
            toks = [t for t in str(answer).split(';') if t]
            listed = [s for s in ((engine.get(str(mid)) or {}).get('smiles') or []) if s and s != 'CCO']
            top = listed[0] if listed else None
            key = identity(top) if top else None
            if toks and toks[0] != 'CCO' and key is not None:
                keys = [identity(t) for t in toks]
                if key != keys[0]:
                    rest = [t for t, k in zip(toks, keys) if k != key]
                    toks = (rest[:1] + [top] + rest[1:])[:25]
                    report['inserted'] += 1
            rows.append((mid, ';'.join(toks) if toks else answer))
        out = pd.DataFrame(rows, columns=['molecule_id', 'smiles'])
        assert out.molecule_id.tolist() == frame.molecule_id.tolist() and out.smiles.notna().all()
        assert out.smiles.map(lambda s: 1 <= len(s.split(';')) <= 25).all()
        for s in out.smiles:
            ids = [identity(x) for x in s.split(';')]
            assert s == 'CCO' or (None not in ids and len(ids) == len(set(ids)))
        Path('submission_e006_control.csv').write_bytes(control)
        out.to_csv('submission_stage.csv', index=False)
        os.replace('submission_stage.csv', path)
        report['status'] = 'ok'
    except Exception as exc:
        path.write_bytes(control)
        report.update(status='fallback', error=f'{type(exc).__name__}: {exc}'[:400], inserted=0)
    report['submission_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    Path('rank2_overlay.json').write_text(json.dumps(report, indent=2))
    print('RANK2_OVERLAY', json.dumps(report), flush=True)
    return report


RANK2_REPORT = _rank2_overlay(globals())
del _rank2_overlay
