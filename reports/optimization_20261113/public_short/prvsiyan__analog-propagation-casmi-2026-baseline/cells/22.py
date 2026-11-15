# ── FRNet fragment isomer re-ranker on ranks 2-25 (Amil Gentili's casmi26-fr-reranker-blend), rank 1 frozen ──
# Recipe of the dataset's harmonized_fr_blend.py: key = -rank + FR_W * z(FRNet score) over ranks 2-25, z taken over the
# whole list; rank 1 never moves; a candidate below rank FR_MAX_PROMOTE_RANK may not take rank 2. Only the order changes:
# every list keeps the same molecules. Fail-safe: any error, a missing input or a changed file keeps the list as it was.
import glob, hashlib, json, os, shutil, sys, time, traceback
FR_ON = False                               # V49: off. V48 ran it at FR_W = 1.0 and scored 0.486 public (V47: 0.487)
FR_W = 1.0
FR_MAX_PROMOTE_RANK = 3
FR_MIN_PEAKS = 3
FR_BUDGET_SECONDS = 1500
FR_LIMIT_SECONDS = 9 * 3600 - 1500          # never start past 8 h 35 min of session time
FR_SHA256 = {'fr_model.pt': '21f70d461564a1db09ce7e181a138538b8efcef2f05c67050f042c607560ff7e',
             'fragfeat.py': '7b54023d89617fafebbd052e500dba30a7825d8e6893e8bf6567fe11ab7f8ecf',
             'model.py': 'b6276a285903181455df40bfe1215788f31f3ed6466066152efa68d2f21f596d'}
FR_REPORT = dict(status='off')


def _fr_sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def _fr_load():
    """Find the dataset folder, check the three pinned files, import its code from a copy in the working folder."""
    for m in sorted(glob.glob(str(INPUT / '**' / 'fr_model.pt'), recursive=True), key=len):
        d = os.path.dirname(m)
        if all(os.path.isfile(os.path.join(d, f)) and _fr_sha(os.path.join(d, f)) == h for f, h in FR_SHA256.items()):
            break
    else:
        return None, 'off: pinned FRNet files not found'
    dst = CODE / 'fr_agentili'; dst.mkdir(exist_ok=True)
    for f in ('fragfeat.py', 'model.py'):
        shutil.copyfile(os.path.join(d, f), dst / f)
    if str(dst) not in sys.path:
        sys.path.insert(0, str(dst))
    for name in ('fragfeat', 'model'):
        sys.modules.pop(name, None)
    import torch
    import fragfeat as ff
    from model import FRNet
    if not ff.HAVE_NUMBA:
        return None, 'off: numba missing (the fragment kernel would be too slow)'
    ck = torch.load(os.path.join(d, 'fr_model.pt'), map_location='cpu', weights_only=True)
    a = ck['args']
    net = FRNet(d=int(a['d']), layers=int(a['layers']), no_frag=bool(a['no_frag']))
    net.load_state_dict(ck['state']); net.eval()
    return (ff, net, torch), 'loaded'


def _fr_batch(fs, torch):
    import numpy as np
    nn_ = np.array([f['node_cat'].shape[0] for f in fs]); ne = np.array([f['edge'].shape[0] for f in fs])
    npk = np.array([f['peak_x'].shape[0] for f in fs])
    shift = np.concatenate([[0], np.cumsum(nn_)[:-1]])
    edge = np.concatenate([f['edge'] for f in fs]).astype(np.int64) + np.repeat(shift, ne)[:, None]
    P = int(npk.max()); px = np.zeros((len(fs), P, 7), np.float32); pm = np.zeros((len(fs), P), bool)
    for i, f in enumerate(fs):
        px[i, :npk[i]] = f['peak_x']; pm[i, :npk[i]] = True
    T = lambda x, dt=torch.float32: torch.as_tensor(np.ascontiguousarray(x)).to(dt)
    return dict(node_cat=T(np.concatenate([f['node_cat'] for f in fs]), torch.long),
                node_x=T(np.concatenate([f['node_x'] for f in fs])), edge=T(edge, torch.long),
                edge_cat=T(np.concatenate([f['edge_cat'] for f in fs]), torch.long),
                edge_x=T(np.concatenate([f['edge_x'] for f in fs])), peak_x=T(px), peak_mask=T(pm, torch.bool),
                glob_x=T(np.stack([f['glob_x'] for f in fs])), graph=T(np.repeat(np.arange(len(fs)), nn_), torch.long),
                n_graphs=len(fs))


def _fr_scores(model, spectra, smiles):
    """FRNet logit per candidate against the molecule's merged spectra (NaN where a candidate does not featurize)."""
    import numpy as np
    ff, net, torch = model
    out = np.full(len(smiles), np.nan)
    spec = ff.merge_spectra(spectra)
    if spec is None or len(spec['mz']) < FR_MIN_PEAKS:
        return out
    q = ff.query_table(spec)
    fs = [ff.featurize(spec, q, s) for s in smiles]
    ok = [i for i, f in enumerate(fs) if f is not None]
    if ok:
        with torch.no_grad():
            out[ok] = net(_fr_batch([fs[i] for i in ok], torch)).float().numpy()
    return out


def _fr_blend(lst, scores):
    """The dataset's blend_apex_with_frnet ordering rule, without its re-deduplication (lists are already unique)."""
    import numpy as np
    s = np.asarray(scores, float); m = np.isfinite(s)
    if len(lst) < 3 or not m.any():
        return list(lst)
    z = np.zeros_like(s); sd = s[m].std()
    z[m] = (s[m] - s[m].mean()) / sd if sd > 1e-8 else 0.0
    tail = lst[1:]
    keys = sorted(((-(j + 2) + FR_W * z[j + 1], 2 if j + 2 > FR_MAX_PROMOTE_RANK else 25, c) for j, c in enumerate(tail)),
                  key=lambda x: x[0], reverse=True)
    n = len(tail); slots = [None] * n
    for _, ma, c in keys:
        pos = ma - 1 if ma - 1 < n else 0
        while pos < n and slots[pos] is not None:
            pos += 1
        if pos < n:
            slots[pos] = c
        else:
            slots[slots.index(None)] = c
    return [lst[0]] + slots


def _fr_spectra(path):
    te = pd.read_parquet(path, columns=['molecule_id', 'ms2_mzs', 'ms2_normalized_intensities', 'precursor_mz',
                                        'adduct', 'ionization_mode'])
    spec = {}
    for r in te.itertuples(index=False):
        spec.setdefault(str(r.molecule_id), []).append(dict(
            mz=np.asarray(r.ms2_mzs, np.float64), it=np.asarray(r.ms2_normalized_intensities, np.float64),
            adduct=str(r.adduct), mode=1 if str(r.ionization_mode).lower().startswith('pos') else -1,
            prec=float(r.precursor_mz)))
    return spec


_fr_before = ROOT / 'submission_before_frnet.csv'
try:
    _fr_t0 = time.time()
    _fr_left = FR_LIMIT_SECONDS - (_fr_t0 - NB_T0)
    if not FR_ON:
        FR_REPORT = dict(status='off in this version (V48 ran it at W=1.0: 0.486 public, V47 without it: 0.487)')
    elif _fr_left < 300:
        FR_REPORT = dict(status='skipped: session time', seconds_left=round(_fr_left))
    else:
        _fr_model, _fr_status = _fr_load()
        if _fr_model is None:
            FR_REPORT = dict(status=_fr_status)
        else:
            shutil.copyfile(ROOT / 'submission.csv', _fr_before)
            _fr_spec = _fr_spectra(COMP / 'test.parquet')
            if not (PIPELINE_DONE or IS_RERUN):
                # Fast commit: the lists are placeholders, so only check that the model runs on this image.
                _probe = ['CCOC(=O)c1ccccc1O', 'COc1cc(C=CC(=O)O)ccc1O', 'CN1CCC23c4c5ccc(O)c4OC2C(O)C=CC3C1C5', 'OCC1OC(O)C(O)C(O)C1O']
                _fin = [int(np.isfinite(_fr_scores(_fr_model, _fr_spec[k], _probe)).sum()) for k in list(_fr_spec)[:5]]
                FR_REPORT = dict(status='self-test only (fast commit, answer unchanged)', finite_scores=_fin,
                                 seconds=round(time.time() - _fr_t0, 1))
            else:
                _fr_sub = pd.read_csv(ROOT / 'submission.csv', dtype=str, keep_default_na=False)
                _fr_rows, _fr_scored, _fr_moved, _fr_err, _fr_budget = [], 0, 0, 0, False
                for _mid, _s in zip(_fr_sub.molecule_id.astype(str), _fr_sub.smiles.astype(str)):
                    _l = _s.split(';')
                    if _fr_budget or len(_l) < 3 or _mid not in _fr_spec:
                        _fr_rows.append((_mid, _s)); continue
                    if time.time() - _fr_t0 > min(FR_BUDGET_SECONDS, _fr_left):
                        _fr_budget = True; _fr_rows.append((_mid, _s)); continue
                    try:
                        _new = _fr_blend(_l, _fr_scores(_fr_model, _fr_spec[_mid], _l))
                        _fr_scored += 1; _fr_moved += int(_new != _l)
                        _fr_rows.append((_mid, ';'.join(_new)))
                    except Exception:
                        _fr_err += 1; _fr_rows.append((_mid, _s))
                _fr_new = pd.DataFrame(_fr_rows, columns=['molecule_id', 'smiles'])
                _fr_ok = (_fr_new.molecule_id.tolist() == _fr_sub.molecule_id.astype(str).tolist() == SAMPLE_IDS and all(
                    set(a.split(';')) == set(b.split(';')) and len(a.split(';')) == len(b.split(';'))
                    and a.split(';')[0] == b.split(';')[0] for a, b in zip(_fr_sub.smiles, _fr_new.smiles)))
                FR_REPORT = dict(status='ran' if _fr_ok else 'check failed: answer kept', w=FR_W,
                                 molecules_scored=_fr_scored, lists_reordered=_fr_moved, errors=_fr_err,
                                 budget_hit=_fr_budget, seconds=round(time.time() - _fr_t0, 1))
                if _fr_ok:
                    _fr_new.to_csv(ROOT / 'submission.tmp.csv', index=False)
                    os.replace(ROOT / 'submission.tmp.csv', ROOT / 'submission.csv')
except Exception as exc:
    traceback.print_exc()
    FR_REPORT = dict(status='off after an error', exception=repr(exc)[:400])
    try:
        if _fr_before.is_file():
            shutil.copyfile(_fr_before, ROOT / 'submission.csv')
    except Exception:
        traceback.print_exc()
try:
    (ROOT / 'frnet_report.json').write_text(json.dumps(FR_REPORT, indent=2, default=str))
except Exception:
    traceback.print_exc()
final = pd.read_csv(ROOT / 'submission.csv', dtype=str, keep_default_na=False)
assert list(final.columns) == ['molecule_id', 'smiles']
assert final.molecule_id.tolist() == SAMPLE_IDS and final.molecule_id.is_unique
assert final.smiles.str.split(';').map(len).between(1, 25).all()
assert final.smiles.str.split(';').map(lambda a: all(bool(s) for s in a) and len(set(a)) == len(a)).all()
print('SUBMISSION READY:', ROOT / 'submission.csv', 'molecules', len(final), '| FRNet', json.dumps(FR_REPORT, default=str))
