from pathlib import Path
import json
import pyarrow.parquet as pq
ROOT=Path(__file__).resolve().parents[1]
paths=[ROOT/'assets/kaggle/nakhun/casmi26-extlib2/v1/extlib2/ext2_meta.parquet',
       ROOT/'enveda-CASMI26-molecule-id-mass-spectra/train.parquet',
       ROOT/'runs/validation_pilot_v2_20261104/structure_identity_audit.parquet']
for directory,name in [('takumuhata','ext_meta.parquet'),('samartalwar','spectra.parquet')]:
    paths.extend((ROOT/'assets/kaggle'/directory).rglob(name))
out=[]
for p in paths:
    if not p.exists():continue
    f=pq.ParquetFile(p)
    first=next(f.iter_batches(batch_size=1)).to_pylist()[0]
    sample={k:(str(v)[:180]) for k,v in first.items()}
    out.append(dict(path=str(p.relative_to(ROOT)),rows=f.metadata.num_rows,schema=str(f.schema_arrow),sample=sample))
dest=ROOT/'reports/extlib2_increment_20261114';dest.mkdir(parents=True,exist_ok=True)
(dest/'schemas.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
for r in out:print(json.dumps(r))
