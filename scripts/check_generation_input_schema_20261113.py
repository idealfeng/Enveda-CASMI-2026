"""Correct the historical local smoke provenance; never mutate its live input files."""
from pathlib import Path
import json
import pyarrow.parquet as pq

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'runs/generation_production_20261113_r2'
actual=pq.ParquetFile(RUN/'kaggle/input/enveda-CASMI26-molecule-id-mass-spectra/test.parquet').schema_arrow.names
official=pq.ParquetFile(ROOT/'enveda-CASMI26-molecule-id-mass-spectra/test.parquet').schema_arrow.names
report=dict(status='schema_review',actual_columns=actual,official_test_columns=official,
            extra_columns=sorted(set(actual)-set(official)),missing_columns=sorted(set(official)-set(actual)),
            current_input_file_not_modified=True,purpose='Production execution-path smoke only; no efficacy or clean isolation claim',
            previous_no_truth_loaded_declaration_retracted=True,
            future_prepare_uses_official_schema_projection=True)
(RUN/'input_schema_review.json').write_text(json.dumps(report,indent=2)+'\n')
p=RUN/'preparation.json';old=json.loads(p.read_text());original=RUN/'preparation_original_declaration.json'
if not original.exists(): original.write_text(json.dumps(old,indent=2)+'\n')
old['no_truth_loaded']=False
old['truth_metadata_present']=True
old['truth_metadata_consumption']='Pending read-only code review; no labels deliberately used for selection or metrics'
old['input_schema_review']='input_schema_review.json'
old['purpose']='Production path smoke only; no efficacy claim'
p.write_text(json.dumps(old,indent=2)+'\n')
print(json.dumps(report))
