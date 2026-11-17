# CODE CELL 15 · Molecular ranking

from pathlib import Path as _DV_Path
import pandas as _DV_pd
import json as _DV_json
_DV_sub = _DV_Path('/kaggle/working/submission.csv')
assert _DV_sub.is_file(), 'submission.csv not found; run Part II first'
_DV_df = _DV_pd.read_csv(_DV_sub, dtype=str, keep_default_na=False)
assert list(_DV_df.columns)==['molecule_id','smiles'], list(_DV_df.columns)
assert _DV_df.molecule_id.is_unique
assert _DV_df.molecule_id.tolist()==SAMPLE_IDS, 'Unexpected molecule order in sample_submission'
_DV_lists=_DV_df.smiles.str.split(';')
assert _DV_lists.map(lambda a: 1<=len(a)<=25 and all(a) and len(set(a))==len(a)).all()
print('OK: submission.csv; molecules:', len(_DV_df),
      '; rank list min/median/max:', _DV_lists.map(len).min(),
      int(_DV_lists.map(len).median()), _DV_lists.map(len).max())
for _DV_name in ['merge_report.json','v8_report.json','apex_extlib_audit.json']:
    _DV_p = _DV_sub.parent / _DV_name
    if _DV_p.is_file():
        try:
            _DV_r = _DV_json.loads(_DV_p.read_text())
            print(_DV_name, _DV_json.dumps(_DV_r, ensure_ascii=False)[:600])
        except Exception as _DV_exc:
            print(_DV_name, 'could not read:',repr(_DV_exc))
