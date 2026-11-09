"""Independent artifact checks for split boundaries, mined negatives and checkpoints."""
from pathlib import Path
from collections import Counter
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
OUT=ROOT/'runs/candidate_head_20261108'
import numpy as np
import pyarrow.parquet as pq
from validation.metric import identity,assert_official_rdkit
assert_official_rdkit()
queries=json.loads((OUT/'queries.json').read_text())
prep=json.loads((OUT/'prepare_receipt.json').read_text())
groups={name:{q['key'] for q in queries if q['split']==name} for name in ['train','monitor','eval']}
denied=set(prep['deny_identities'])
catalog=pq.read_table(OUT/'candidate_catalog.parquet').to_pylist()
by_index={r['fp_index']:r for r in catalog}
checks={'train_1024':len(groups['train'])==1024,
 'monitor_128':len(groups['monitor'])==128,'eval_128':len(groups['eval'])==128,
 'split_disjoint':all(not groups[a]&groups[b] for a,b in [('train','monitor'),('train','eval'),('monitor','eval')]),
 'no_frozen_targets':not set.union(*groups.values())&denied,
 'canonical_positive_identity':all(identity(q['smiles'])==q['key'] for q in queries),
 'raw_original_preprocessing':prep['preprocessing']=='unmodified original Saner features.peaks and metadata on raw train arrays'}
for split in ['train','monitor','eval']:
 records=[q for q in queries if q['split']==split]
 checks[split+'_retrieved_unique_official_identity']=all(len({by_index[i]['key'] for i in q['retrieved_candidates']})==len(q['retrieved_candidates']) for q in records)
 checks[split+'_no_frozen_negative_targets']=all(not {by_index[i]['key'] for i in q['retrieved_candidates']}&denied for q in records)
checks['monitor_eval_not_in_training_candidates']=all(not {by_index[i]['key'] for i in q['retrieved_candidates']}&(groups['monitor']|groups['eval']) for q in queries if q['split']=='train')
inputs=np.load(OUT/'spectra_inputs.npz')
checks['preprocessed_arrays_finite']=bool(np.isfinite(inputs['x']).all() and np.isfinite(inputs['meta']).all())
checks['valid_peak_and_adduct_ranges']=bool((inputs['lengths']>=3).all() and (inputs['lengths']<=96).all() and (inputs['adduct']>=0).all() and (inputs['adduct']<=10).all())
provenance=pq.read_table(OUT/'spectrum_provenance.parquet').to_pylist()
signature_splits={}
for row in provenance:signature_splits.setdefault(row['signature'],set()).add(row['split'])
checks['no_exact_preprocessed_spectrum_cross_split']=all(len(v)==1 for v in signature_splits.values())
negative_file=OUT/'actual_v2_hard_negatives.parquet'
if negative_file.exists():
 negatives=pq.read_table(negative_file).to_pylist()
 checks['actual_negatives_only_training_queries']=all(r['query_key'] in groups['train'] for r in negatives)
 checks['no_equivalent_positive_false_negatives']=all(r['query_key']!=r['negative_key'] for r in negatives)
 checks['no_monitor_eval_or_frozen_negative_targets']=not {r['negative_key'] for r in negatives}&(groups['monitor']|groups['eval']|denied)
 checks['negative_rank_max32']=all(1<=r['wrong_rank']<=32 for r in negatives)
else:negatives=[]
assert all(checks.values()),checks
result=dict(status='passed',checks=checks,known_pretrained_exposure=True,full_stack_clean_cv=False,
 raw_spectra=len(inputs['x']),query_counts={k:len(v) for k,v in groups.items()},
 negative_rows=len(negatives),same_formula_negative_rows=sum(r['same_formula'] for r in negatives),
 source_spectra=dict(Counter(r['source'] for r in provenance)))
(OUT/'independent_data_checks.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result))
