# ── v8 · mass rank-1 rule + learned isomer reranker (romanrozen), guarded and checked ───────────────────────────────
import base64, zlib, hashlib, json, shutil, sys, time, traceback
assert hashlib.sha256(_RR8_FEATURES.encode()).hexdigest() == 'aec9012e72324095308af81c1408aa36f6a44cb00f6d4389e87529a68329d176'
assert hashlib.sha256(_RR8_OVERLAY.encode()).hexdigest() == 'e83b7986c46d0ef02bc6cfde17e891c9e7ee66a0eed8c716f5e3474e5663ccf7'


def _v8_lists(path):
    f = pd.read_csv(path, dtype=str, keep_default_na=False)
    return f, [s.split(';') for s in f.smiles.astype(str)]


def _v8_check(before, after):
    return (after.molecule_id.astype(str).tolist() == before.molecule_id.astype(str).tolist() == SAMPLE_IDS
            and all(set(x) == set(y) and len(x) == len(y) == len(set(y)) and all(y)
                    for x, y in zip(before.smiles.str.split(';'), after.smiles.str.split(';'))))


def _v8_write(frame):
    frame.to_csv(ROOT / 'submission.tmp.csv', index=False)
    os.replace(ROOT / 'submission.tmp.csv', ROOT / 'submission.csv')


try:
    _v8_ev = pd.read_parquet(ROOT / 'frozen_candidate_evidence.parquet', columns=['molecule_id', 'library_max'])
    V8_LIB = {str(m): float(v) for m, v in _v8_ev.groupby('molecule_id').library_max.max().items()}
except Exception:
    V8_LIB = {}

# 1) mass rank-1 rule
MASS_LEAD_REPORT = dict(status='off in this preset')
try:
    if MASS_ON and MASS_PPM:
        shutil.copyfile(ROOT / 'submission.csv', ROOT / 'submission_before_mass_lead.csv')
        _f, _lists = _v8_lists(ROOT / 'submission.csv')
        _rows, _moves = [], 0
        for _mid, _l in zip(_f.molecule_id.astype(str), _lists):
            ppm = MASS_PPM.get(_mid, {})
            if (len(_l) >= 2 and V8_LIB.get(_mid, 0.0) < MASS_LIB_TAU and _l[0] in ppm
                    and abs(ppm[_l[0]] - MASS_CENTER) > MASS_LEAD_OFF):
                for _s in _l[1:3]:
                    if _s in ppm and abs(ppm[_s] - MASS_CENTER) <= MASS_FREE:
                        _l = [_s] + [x for x in _l if x != _s]
                        _moves += 1
                        break
            _rows.append((_mid, ';'.join(_l)))
        _new = pd.DataFrame(_rows, columns=['molecule_id', 'smiles'])
        if _v8_check(_f, _new):
            _v8_write(_new)
            MASS_LEAD_REPORT = dict(status='ran', leader_moves=_moves)
        else:
            MASS_LEAD_REPORT = dict(status='check failed: answer kept')
    elif MASS_ON:
        MASS_LEAD_REPORT = dict(status='off: no mass table')
except Exception as exc:
    traceback.print_exc()
    MASS_LEAD_REPORT = dict(status='off after an error', exception=repr(exc)[:300])
    if (ROOT / 'submission_before_mass_lead.csv').is_file():
        shutil.copyfile(ROOT / 'submission_before_mass_lead.csv', ROOT / 'submission.csv')

# 2) learned isomer reranker
RR8_REPORT = dict(status='off in this preset')
_rr8_before = ROOT / 'submission_before_rr8.csv'
try:
    shutil.copyfile(ROOT / 'submission.csv', _rr8_before)
    _rr8_left = RR8_LIMIT_SECONDS - (time.time() - NB_T0)
    if not RR8:
        pass
    elif not globals().get('PIPELINE_DONE'):
        RR8_REPORT = dict(status='off: no pipeline answer in this run')
    elif _rr8_left < RR8_MIN_SECONDS:
        RR8_REPORT = dict(status='skipped: session time', seconds_left=round(_rr8_left))
    else:
        (CODE / 'rr_features.py').write_text(_RR8_FEATURES)
        (CODE / 'rr_overlay.py').write_text(_RR8_OVERLAY)
        for _p in (str(CODE), str(ROOT)):
            if _p not in sys.path:
                sys.path.insert(0, _p)
        for _m in ('rr_features', 'rr_overlay'):
            sys.modules.pop(_m, None)
        import frag_rescore as _rr8_frag
        import rr_features as _rr8_rf
        import rr_overlay as _rr8_ov
        import lightgbm as _rr8_lgb
        _rr8_txt = zlib.decompress(base64.b64decode(_RR8_MODEL_Z)).decode()
        assert hashlib.sha256(_rr8_txt.encode()).hexdigest() == '3b80e1c9adf90721c99bb4e817a05379dd8b26e0988a001bd112330a66d9122b', 'model text differs'
        _rr8_booster = _rr8_lgb.Booster(model_str=_rr8_txt)
        _rr8_frag.warmup()
        _rr8_sub, _ = _v8_lists(ROOT / 'submission.csv')
        _rr8_spec = _rr8_ov.load_spectra(COMP / 'test.parquet')
        _rr8_train = set(pd.read_parquet(COMP / 'train.parquet', columns=['inchikey14']).inchikey14.astype(str))
        _rr8_new, _rr8_rep = _rr8_ov.run(_rr8_sub, V8_LIB, _rr8_spec, _rr8_train, _rr8_booster, _rr8_rf, _rr8_frag,
                                         alpha=RR8_ALPHA, lib_tau=RR8_LIB_TAU,
                                         max_seconds=float(min(RR8_BUDGET_SECONDS, _rr8_left)))
        if _v8_check(_rr8_sub, _rr8_new):
            _v8_write(_rr8_new)
            RR8_REPORT = dict(status='ran', **_rr8_rep)
        else:
            RR8_REPORT = dict(status='check failed: answer kept', **_rr8_rep)
except Exception as exc:
    traceback.print_exc()
    RR8_REPORT = dict(status='off after an error', exception=repr(exc)[:400])
    try:
        if _rr8_before.is_file():
            shutil.copyfile(_rr8_before, ROOT / 'submission.csv')
    except Exception:
        traceback.print_exc()
try:
    (ROOT / 'v8_report.json').write_text(json.dumps(dict(mass=MASS_REPORT, mass_lead=MASS_LEAD_REPORT, rr=RR8_REPORT),
                                                    indent=2, default=str))
except Exception:
    traceback.print_exc()
final = pd.read_csv(ROOT / 'submission.csv', dtype=str, keep_default_na=False)
assert list(final.columns) == ['molecule_id', 'smiles']
assert final.molecule_id.tolist() == SAMPLE_IDS and final.molecule_id.is_unique
assert final.smiles.str.split(';').map(len).between(1, 25).all()
assert final.smiles.str.split(';').map(lambda a: all(bool(s) for s in a) and len(set(a)) == len(a)).all()
print('SUBMISSION READY:', ROOT / 'submission.csv', 'molecules', len(final), '| V8', V8, '| mass lead',
      json.dumps(MASS_LEAD_REPORT), '| RR', json.dumps(RR8_REPORT, default=str))