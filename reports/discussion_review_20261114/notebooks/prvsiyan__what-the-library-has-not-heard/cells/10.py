# ── Replay: point the pinned 0.465 pipeline at the replay test file (three path lines), and re-pin its hash ──
import base64 as _b64, hashlib as _hl, json as _js
_fz = _js.loads(_b64.b64decode(FROZEN_B64))
_patches = [
    ('Path("/kaggle/input/competitions/enveda-CASMI26-molecule-id-mass-spectra"),',
     'Path(os.environ.get("CASMI_REPLAY_COMP", "/kaggle/input/competitions/enveda-CASMI26-molecule-id-mass-spectra")),'),
    ("COMP = os.path.dirname(find('test.parquet'))",
     "COMP = os.environ.get('CASMI_REPLAY_COMP') or os.path.dirname(find('test.parquet'))"),
    ("assert comp in {f'/kaggle/input/{slug}', f'/kaggle/input/competitions/{slug}'}",
     "assert comp in {f'/kaggle/input/{slug}', f'/kaggle/input/competitions/{slug}', os.path.realpath(os.environ.get('CASMI_REPLAY_COMP', '/kaggle/input/' + slug))}"),
]
for _old, _new in _patches:
    _hits = [c for c in _fz['cells'] if c['cell_type'] == 'code' and _old in ''.join(c['source'])]
    assert len(_hits) == 1 and ''.join(_hits[0]['source']).count(_old) == 1, _old
    _hits[0]['source'] = [''.join(_hits[0]['source']).replace(_old, _new)]
_raw = _js.dumps(_fz).encode()
FROZEN_B64 = _b64.b64encode(_raw).decode()
FROZEN_SHA256 = _hl.sha256(_raw).hexdigest()
print('replay: pinned pipeline re-pointed at', os.environ.get('CASMI_REPLAY_COMP'), '| new hash', FROZEN_SHA256[:16])
