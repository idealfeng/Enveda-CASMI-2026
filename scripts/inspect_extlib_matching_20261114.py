from pathlib import Path
import json
import pandas as pd
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
for name in ['assets/kaggle/nakhun/casmi26-extlib2/v1/extlib2/ext2_meta.parquet',
             'runs/validation_pilot_v2_20261104/queries.parquet']:
    x=pd.read_parquet(ROOT/name)
    print(name,len(x),x.columns.tolist())
    print({k:(str(v)[:300]) for k,v in x.iloc[0].to_dict().items()})
for name in ['ext2_mz_flat.npy','ext2_in_flat.npy','ext2_offsets.npy']:
    a=np.load(ROOT/'assets/kaggle/nakhun/casmi26-extlib2/v1/extlib2'/name,mmap_mode='r',allow_pickle=False)
    print(name,a.shape,a.dtype,a[:8])
