from pathlib import Path
import pyarrow.parquet as pq
paths=[Path(x) for x in ['runs/validation_pilot_v2_20261104/structure_identity_audit.parquet','runs/shared_spec_cache/spec_meta.parquet','enveda-CASMI26-molecule-id-mass-spectra/train.parquet','assets/kaggle/egehseyinca/enveda180-casmi26-reference-ccby4/v1/enveda180_only_candidate_aliases.parquet']]
for p in paths:
    f=pq.ParquetFile(p)
    print(str(p),f.metadata.num_rows,f.schema_arrow,flush=True)
    if 'aliases' in str(p): print(f.read().slice(0,2).to_pylist(),flush=True)
