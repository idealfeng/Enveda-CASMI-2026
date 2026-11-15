# ── Replay scoring: MRR@25 of every answer file the run wrote, on the metric's identity, plus timings ──
import glob, json, shutil, time
from pathlib import Path
import numpy as np
import pandas as pd
_RS = Path('/kaggle/working/replay_results')
_truth = pd.read_csv(_RS / 'queries.csv', dtype=str).set_index('molecule_id').truth_key.to_dict()
try:
    from rdkit import Chem, RDLogger
    from rdkit.Chem.MolStandardize import rdMolStandardize
    RDLogger.DisableLog('rdApp.*')
    _T = rdMolStandardize.TautomerEnumerator(); _kc = {}

    def _key(s):
        if s not in _kc:
            try:
                m = Chem.MolFromSmiles(s)
                if m is None:
                    _kc[s] = None
                else:
                    Chem.RemoveStereochemistry(m); _kc[s] = Chem.MolToInchiKey(_T.Canonicalize(m))[:14]
            except Exception:
                _kc[s] = None
        return _kc[s]

    _rows, _per = [], []
    _files = sorted(set(glob.glob('/kaggle/working/*.csv') + glob.glob('/kaggle/working/variants/*.csv')))
    for _f in _files:
        try:
            _d = pd.read_csv(_f, dtype=str, keep_default_na=False)
        except Exception:
            continue
        if list(_d.columns[:2]) != ['molecule_id', 'smiles'] or not set(_d.molecule_id) <= set(_truth):
            continue
        _rr = []
        for _mid, _s in zip(_d.molecule_id, _d.smiles):
            _seen, _rank, _hit = [], None, 0.0
            for _c in [x for x in _s.split(';') if x][:25]:
                _k = _key(_c)
                if _k in _seen:
                    continue
                _seen.append(_k)
                if _k == _truth[_mid]:
                    _rank = len(_seen); break
            _rr.append(1.0 / _rank if _rank else 0.0)
            _per.append(dict(file=Path(_f).name, molecule_id=_mid, rank=_rank or 0))
        _v = np.array(_rr)
        _rows.append(dict(file=str(Path(_f).relative_to('/kaggle/working')), molecules=len(_v), mrr25=round(float(_v.mean()), 4),
                          top1=round(float((_v == 1).mean()), 3), in_top25=round(float((_v > 0).mean()), 3)))
    _sc = pd.DataFrame(_rows)
    _sc.to_csv(_RS / 'layer_scores.csv', index=False); pd.DataFrame(_per).to_csv(_RS / 'per_molecule_ranks.csv', index=False)
    print(_sc.to_string(index=False))
except Exception as _exc:
    import traceback; traceback.print_exc()
    print('replay scoring failed:', repr(_exc)[:300])
# keep the lists and the per-candidate evidence for offline tests of later changes
(_RS / 'lists').mkdir(exist_ok=True)
for _f in glob.glob('/kaggle/working/*.csv') + glob.glob('/kaggle/working/variants/*.csv'):
    shutil.copy(_f, _RS / 'lists' / (Path(_f).parent.name + '__' + Path(_f).name if 'variants' in _f else Path(_f).name))
for _f in ('frozen_candidate_evidence.parquet', 'neural_candidate_features.parquet', 'outsider_neural_features.parquet',
           'effective_query_spectra.parquet', 'merge_report.json', 'v8_report.json', 'apex_extlib_audit.json',
           'execution_receipt.json', 'frozen_run_info.json', 'submission_pipeline.log'):
    if Path('/kaggle/working', _f).is_file():
        shutil.copy(Path('/kaggle/working', _f), _RS / _f)
_tm = dict(session_seconds=round(time.time() - NB_T0, 1), stages=[list(map(str, x)) for x in globals().get('STAGES', [])], marks={str(k): [list(map(str, m)) for m in v] for k, v in globals().get('STAGE_MARKS', {}).items()})
(_RS / 'timing.json').write_text(json.dumps(_tm, indent=2))
print('REPLAY TIMING', json.dumps(_tm)[:1500])
