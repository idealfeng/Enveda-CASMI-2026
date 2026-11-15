# ---- E006 + engine-2 cell, MODE = 'rank2' ----
# probe : x1 where it differs from E006 r1, else CCO          | r1probe: E006 r1 where x1 differs, else CCO
# swap  : on disagreement [x1] + E006 list (metric-key dedup)  | rank2  : on disagreement r1, x1, rest of E006 list
MODE = 'rank2'
import shutil as _shp
from rdkit import Chem as _Chp
_shp.copyfile('submission.csv', 'submission_e006.csv')
_sub = pd.read_csv('submission_e006.csv')
def _keyp(s):
    if not isinstance(s, str) or not s or s == 'CCO':
        return None
    try:
        return (chem.score_key(s) or None) if _Chp.MolFromSmiles(s) is not None else None
    except Exception:
        return None
_st = dict(rows=0, x1_missing=0, x1_invalid=0, same_as_r1=0, guess=0)
_rows = []
for m, s in zip(_sub.molecule_id, _sub.smiles):
    _st['rows'] += 1
    toks = [t for t in str(s).split(';') if t]
    r1 = toks[0] if toks else 'CCO'
    e = ENG.get(str(m)) if isinstance(ENG, dict) else None
    l = [x for x in (e.get('smiles') or []) if x and x != 'CCO'] if e else []
    out = 'CCO'
    if not l:
        _st['x1_missing'] += 1
    else:
        kx = _keyp(l[0])
        if kx is None:
            _st['x1_invalid'] += 1
        elif kx == _keyp(r1):
            _st['same_as_r1'] += 1
        else:
            _st['guess'] += 1
            if MODE == 'probe':
                out = l[0]
            elif MODE == 'r1probe':
                out = r1
            else:
                x1 = l[0]
                new = [x1] + toks if MODE == 'swap' else toks[:1] + [x1] + toks[1:]
                seen, out_l = set(), []
                for t in new:
                    k = _keyp(t) or t
                    if k not in seen:
                        seen.add(k); out_l.append(t)
                out = ';'.join(out_l[:25])
    if MODE in ('swap', 'rank2') and out == 'CCO':
        out = str(s)
    _rows.append((m, out))
_fs = pd.DataFrame(_rows, columns=['molecule_id', 'smiles'])
_samp = pd.read_csv(os.path.join(COMP, 'sample_submission.csv'))
assert len(_fs) == len(_sub) == len(_samp) and _fs.molecule_id.is_unique and _fs.smiles.notna().all()
assert set(_fs.molecule_id.astype(str)) == set(_samp.molecule_id.astype(str))
_fs.to_csv('submission.csv', index=False)
open('probe_applied.txt', 'w').write(json.dumps(_st))
print(f'E006 ENGINE-2 CELL APPLIED mode={MODE}:', json.dumps(_st), flush=True)
