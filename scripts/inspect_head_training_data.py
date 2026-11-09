from pathlib import Path
import pyarrow.parquet as pq
ROOT=Path(__file__).resolve().parents[1]
for rel in ['assets/kaggle/ahmedberatozer/casmi26-v2-pool/v1/pool_meta.parquet','assets/kaggle/ahmedberatozer/casmi26-v2-pool/v1/train_structs.parquet','runs/validation_pilot_v2_20261104/structure_identity_audit.parquet','enveda-CASMI26-molecule-id-mass-spectra/train.parquet']:
 f=pq.ParquetFile(ROOT/rel)
 print(rel,f.metadata.num_rows,f.schema_arrow.names,flush=True)
 print(f.read_row_group(0,columns=f.schema_arrow.names[:8]).slice(0,1).to_pylist(),flush=True)
