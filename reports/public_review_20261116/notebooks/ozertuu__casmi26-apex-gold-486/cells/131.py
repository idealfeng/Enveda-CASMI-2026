# CODE CELL 00 · Molecular ranking

from pathlib import Path as _DV_Path
from IPython.display import display as _DV_display
import pandas as _DV_pd

_DV_root = _DV_Path('/kaggle/input')
_DV_checks = [
    ('Competition train', 'train.parquet'),
    ('Competition test', 'test.parquet'),
    ('Sample submission', 'sample_submission.csv'),
    ('Public model checkpoint', 'final_model.pt'),
    ('Scorer configuration', 'config_used.json'),
    ('Popularity prior', 'pool_popularity.csv'),
]
_DV_rows = []
for _DV_label, _DV_basename in _DV_checks:
    _DV_matches = list(_DV_root.rglob(_DV_basename)) if _DV_root.exists() else []
    _DV_rows.append({'Component':_DV_label,
                     'Matches':len(_DV_matches),
                     'Example path':str(_DV_matches[0]) if _DV_matches else 'not found'})
_DV_display(_DV_pd.DataFrame(_DV_rows))
print('Data sources located; model integrity is checked separately.')
