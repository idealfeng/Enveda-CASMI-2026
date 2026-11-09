"""Read schema/row counts from a footer-only public reference parquet snapshot."""
from pathlib import Path
import json
import pyarrow.parquet as pq

root=Path(__file__).resolve().parent
metadata=pq.read_metadata(root/'enveda180_reference_footer.parquet')
schema=metadata.schema.to_arrow_schema()
record=dict(rows=metadata.num_rows,row_groups=metadata.num_row_groups,
    fields=[dict(name=field.name,type=str(field.type),nullable=field.nullable) for field in schema],
    full_file_read=False,peaks_read=False,full_file_hash_verified=False)
(root/'enveda180_reference_schema.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
print(json.dumps(record,indent=2))
