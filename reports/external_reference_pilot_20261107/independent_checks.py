import json,sqlite3
from pathlib import Path
import pyarrow.parquet as pq
p=Path('reports/external_reference_pilot_20261107')
a=json.loads((p/'partial_audit.json').read_text())
t=pq.read_table(p/'alias_related_reference_rows.parquet').to_pylist()
checks={
    'related_rows_1600':len(t)==1600,
    'related_ids_431':len({r['official_identity'] for r in t})==431,
    'official_keys_match':all(r['publisher_reference_key']==r['official_identity'] for r in t),
    'unique_row_indices':len({r['row_index'] for r in t})==len(t),
    'valid_row_indices':all(0<=r['row_index']<730252 for r in t),
    'hplus_1377':sum(r['adduct']=='[M+H]+' for r in t)==1377,
    'hminus_223':sum(r['adduct']=='[M-H]-' for r in t)==223,
    'partial_explicit':a['status']=='partial_metadata_and_alias_identity_audit',
    'no_peak_columns':a['no_peak_columns_loaded'],
    'no_truth':a['no_query_or_locked_truth_loaded'],
    'train_pair_catalog_exact':a['train']['unique_pair_catalog_exactly_matches_current_train'],
}
db=sqlite3.connect(p/'official_identity_cache.sqlite')
print('cache_rows',db.execute('SELECT count(*) FROM identities').fetchone()[0])
db.close()
(p/'independent_checks.json').write_text(json.dumps(checks,indent=2)+'\n')
print(checks)
assert all(checks.values())
