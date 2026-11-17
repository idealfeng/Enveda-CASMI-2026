"""Check fixed gate-pilot row/group/peak-content binding before any fit."""
from pathlib import Path
from collections import defaultdict
import importlib.util,json,hashlib
import pyarrow.parquet as pq

ROOT=Path(__file__).resolve().parents[1]

def main():
    p=ROOT/'scripts/build_extlib_gate_pilot_20261115_r2.py'
    spec=importlib.util.spec_from_file_location('pilot_scope_audit',p)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    run=ROOT/'runs/extlib_gate_pilot_20261115_r2'
    selection=json.loads((run/'selection.json').read_text());groups={g['molecule_id']:g for g in selection['groups']}
    d=pq.read_table(run/'queries.parquet').to_pydict();seen=defaultdict(set);by_split=defaultdict(set);dups=[]
    for i,mid in enumerate(d['molecule_id']):
        mode=mod.ionmode(d['ionization_mode'][i])
        sigs=mod.signatures(d['ms2_mzs'][i],d['ms2_normalized_intensities'][i],float(d['precursor_mz'][i]),mode)
        if any(s in seen[mid] for s in sigs if s):dups.append(dict(molecule_id=mid,spectrum_id=d['spectrum_id'][i]))
        seen[mid].update(s for s in sigs if s)
        by_split[groups[mid]['split']].update(s for s in sigs if s)
    fd=pq.read_table(run/'features.parquet').to_pydict()
    ld=pq.read_table(run/'labels.parquet').to_pydict()
    md=pq.read_table(run/'row_metadata.parquet').to_pydict()
    checks=dict(no_within_query_duplicate_content=len(dups)==0,
        no_train_dev_peak_hash_overlap=not(by_split['train']&by_split['development']),
        all_row_keys_align=fd['row_id']==ld['row_id']==md['row_id'],unique_row_keys=len(set(fd['row_id']))==1000,
        no_target_or_arm_feature=set(fd)==set(mod.FEATURE_NAMES)|{'row_id'},
        official_query_groups_disjoint=not({m for m,s in zip(md['official_query_identity'],md['split']) if s=='train'}&{m for m,s in zip(md['official_query_identity'],md['split']) if s=='development'}))
    result=dict(status='passed_learning_data_binding' if all(checks.values()) else 'review_required',checks=checks,
        within_query_duplicate_rows=dups,train_dev_overlap_signatures=len(by_split['train']&by_split['development']),
        source_script_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),training_performed=False,reference_ID_dedup_available=False)
    (ROOT/'reports/extlib2_execution_20261115/gate_pilot_learning_data_review.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))

if __name__=='__main__':main()
