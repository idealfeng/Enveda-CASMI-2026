# CODE CELL 02 · Deep EDA
CANDIDATES = [
  Path('/kaggle/input/competitions/enveda-CASMI26-molecule-id-mass-spectra'),
  Path('/kaggle/input/enveda-casmi26-molecule-id-mass-spectra'),
]
ROOT = next((d for d in CANDIDATES if (d/'train.parquet').exists()), None)
if ROOT is None:
    matches = sorted(Path('/kaggle/input').rglob('train.parquet')) if Path('/kaggle/input').exists() else []
    matches = [p for p in matches if 'casmi' in str(p).lower() or 'enveda' in str(p).lower()]
    ROOT = matches[0].parent if matches else None
if ROOT is None:
    raise FileNotFoundError('Add the Enveda CASMI 2026 competition dataset under Kaggle Add Input (train.parquet is required).')
TRAIN_PATH = ROOT/'train.parquet'
pf = pq.ParquetFile(TRAIN_PATH)
SCHEMA = pf.schema_arrow.names
REQ = {'ms2_mzs','ms2_normalized_intensities','inchikey14','precursor_mz','adduct'}
missing = REQ - set(SCHEMA)
assert not missing, f'Missing expected columns in train.parquet: {missing}'
print('Data:',TRAIN_PATH)
print('Rows:',pf.metadata.num_rows,'| Parquet row groups:',pf.num_row_groups,'| Columns:',len(SCHEMA))
display(pd.DataFrame({'column':SCHEMA,'type':[str(pf.schema_arrow.field(c).type) for c in SCHEMA]}))