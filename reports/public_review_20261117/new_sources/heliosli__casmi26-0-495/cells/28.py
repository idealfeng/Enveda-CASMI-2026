# ===== heliosli: merge the FRIGID + E1 candidates (reports/c3_design_v0.md 11.20) =====
# Waits for the watcher at most until FRIGID_DEADLINE, then applies the pre-registered rule ins2p of B1 (reports 10.8):
# FRIGID's first candidate goes to rank 2 when its similarity to the predicted fingerprint is >= 0.7 and the formula has
# <= 30 heavy atoms; inserted when absent from the list (the last entry drops out), moved up when it sits below rank 2.
# Rank 1 is never changed. Identity = InChIKey first block.
import time as _fr_t
try:
    from rdkit import Chem as _fr_Chem
    if FRIGID_PROC is not None:
        while FRIGID_PROC.poll() is None and _fr_t.time() < FRIGID_DEADLINE + 300:
            _fr_t.sleep(15)
    _fr_k = {}
    def _fr_key(s):
        if s not in _fr_k:
            m = _fr_Chem.MolFromSmiles(s)
            _fr_k[s] = _fr_Chem.MolToInchiKey(m)[:14] if m is not None else None
        return _fr_k[s]
    _fr = {}
    if FRIGID_OUT.exists():
        for _l in FRIGID_OUT.read_text().splitlines():
            _r = json.loads(_l)
            if _r.get('preds'):
                _fr[_r['molecule_id']] = _r
    _sub = pd.read_csv(ROOT / 'submission.csv')
    _stat = dict(frigid_molecules=len(_fr), inserted=0, moved=0, kept=0)
    _new = []
    for _m, _s in zip(_sub.molecule_id, _sub.smiles):
        _lst = str(_s).split(';')
        _r = _fr.get(_m)
        if _r and len(_lst) > 1:
            _f1, _sim = _r['preds'][0][0], float(_r['preds'][0][2])
            _ha = _fr_Chem.MolFromSmiles(_f1).GetNumHeavyAtoms() if _fr_Chem.MolFromSmiles(_f1) is not None else 99
            _k1, _keys = _fr_key(_f1), [_fr_key(x) for x in _lst]
            if _k1 is not None and _sim >= 0.7 and _ha <= 30 and _k1 not in _keys[:2]:
                if _k1 in _keys:
                    _lst.pop(_keys.index(_k1)); _stat['moved'] += 1
                else:
                    _lst = _lst[:-1] if len(_lst) >= 25 else _lst; _stat['inserted'] += 1
                _lst.insert(1, _f1)
            else:
                _stat['kept'] += 1
        _new.append(';'.join(_lst))
    _sub['smiles'] = _new
    _sub.to_csv(ROOT / 'submission.csv', index=False)
    print('[frigid] merge', json.dumps(_stat))
except Exception as exc:
    print('[frigid] merge skipped:', repr(exc)[:300])
