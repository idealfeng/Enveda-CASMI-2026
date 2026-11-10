"""Independent bounded, read-only checks. Never imports/runs user experiment mains."""
from pathlib import Path
from collections import Counter
import ast,csv,hashlib,json,sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from validation.metric import identity,assert_official_rdkit

def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def csvread(p):
 with Path(p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def rr(x):return 1/float(x) if x else 0.
def truth(x):return str(x).lower()=='true'

assert_official_rdkit()
out=Path(__file__).parent
rows=csvread(ROOT/'produre1/artifacts/per_query_attribution.csv');summary=read(ROOT/'produre1/artifacts/attribution_summary.json')
recomputed={}
for var,col in [('BASE','base_rank')]+[(x,x+'_rank') for x in ['A','B','AB','AB_STRICT']]:
 v=sum(rr(r[col]) for r in rows)/len(rows)
 assert abs(v-summary['results'][var]['metrics']['mrr'])<1e-12
 recomputed[var]=v
excluded=csvread(ROOT/'produre1/artifacts/step6_bclass_exclusion.csv')
residual_truth=[];wrong=[]
for r in excluded:
 if truth(r['false_hit']):
  dest=residual_truth if identity(r['false_smi'])==r['official_identity'] else wrong
  dest.append(r['official_identity'])
source_stats={}
base_rows=csvread(ROOT/'runs/validation_flex_c2_20261105d/baseline_submission.csv')
base_lists={x['molecule_id']:x['smiles'].split(';') for x in base_rows}
invalid_base_ids=[]
for mid,guesses in base_lists.items():
 keys=[identity(s) for s in guesses]
 if None in keys or len(keys)!=len(set(keys)):invalid_base_ids.append(mid)
for n in ['A','B','AB','AB_STRICT']:
 changed=[r for r in rows if truth(r[n+'_changed'])]
 invalid=[];guarded_rr=0.
 for row in rows:
  old=base_lists[row['molecule_id']];s=row[n+'_smi']
  proposal=([s]+[x for x in old if x!=s]) if truth(row[n+'_hit']) and s in old else ([s]+old)[:25] if truth(row[n+'_hit']) else list(old)
  keys=[identity(x) for x in proposal]
  okay=None not in keys and len(keys)==len(set(keys))
  if not okay:invalid.append(row['molecule_id']);keys=[identity(x) for x in old]
  guarded_rr+=1/(keys.index(row['truth'])+1) if row['truth'] in keys else 0.
 source_stats[n]=dict(changed=len(changed),correct=sum(truth(r[n+'_correct']) for r in changed),
  changed_whole_lists_not_top1_guarded=True,
  invalid_or_duplicate_metric_proposal_check_implemented=False,
  invalid_or_duplicate_metric_proposals=len(invalid),invalid_proposal_ids=invalid,
  newly_invalid_proposal_ids=sorted(set(invalid)-set(invalid_base_ids)),
  diagnostic_querywise_guard_only_mrr_not_production_run=guarded_rr/len(rows))
up=read(ROOT/'third_party/public_scan_alexchilton__casmi26-lb-0-484-peaks-to-structures-extlib_20261109/source.ipynb')
src=up['cells'][24]['source'];src=''.join(src) if isinstance(src,list) else src
original=next(x for x in ast.parse(src).body if isinstance(x,ast.FunctionDef) and x.name=='_apex_extlib_overlay')
copyfn=next(x for x in ast.parse((ROOT/'produre1/reference_cell14.py').read_text(encoding='utf-8')).body if isinstance(x,ast.FunctionDef))
assert ast.dump(original,include_attributes=False)==ast.dump(copyfn,include_attributes=False)
report=dict(status='passed_bounded_read_only',user_artifacts_unchanged=True,
 scope='CSV metric arithmetic + original source AST + 200 exclusion identity recheck + bounded metadata/peak sample',
 current_production_baseline='58156482 / .488; not rerun by this audit',
 matching_reference_function_exact_ast=True,document_actual_cell_index=24,
 independently_recomputed_48_mrr=recomputed,source_changed_stats=source_stats,
 invalid_original_base_queries=invalid_base_ids,
 production_control_precondition_satisfied=not bool(invalid_base_ids),
 guard_replay_boundary='Only a per-query diagnostic reconstruction: real helper rejects a globally invalid base before matching. This is NOT a production run or .482/.488 local reproduction.',
 exclusion=dict(reported_false_hits=sum(truth(r['false_hit']) for r in excluded),
  actually_same_official_identity_hits=len(residual_truth),actually_wrong_official_identity_hits=len(wrong),
  residual_same_identity_ids=residual_truth),
 source_hashes={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in [ROOT/'produre1/attribution.py',ROOT/'produre1/step6_validation_panel.py',ROOT/'produre1/step7_enveda180.py',ROOT/'produre1/artifacts/attribution_summary.json',ROOT/'produre1/artifacts/step6_validation_summary.json',ROOT/'produre1/artifacts/step7_enveda180_summary.json']})
if sys.platform!='win32':
 import pyarrow.parquet as pq,numpy as np
 bpath=ROOT/'assets/kaggle/samartalwar/casmi-2026-spectral-library-massbankharmonized/v1/spectra.parquet'
 keys=pq.read_table(bpath,columns=['inchikey']).column(0).to_pylist()
 lengths=Counter(len(str(x)) for x in keys if x is not None)
 aliases=csvread(ROOT/'produre1/artifacts/step7_enveda180_membership.csv')
 whole=set(keys);trunc={str(x)[:14] for x in keys if x is not None}
 report['massbank_membership_format']=dict(key_lengths=dict(lengths),
  direct_14_to_full_matches=sum(x['official_identity'] in whole for x in aliases),
  normalized_14_prefix_matches=sum(x['official_identity'] in trunc for x in aliases),
  meaning='14-character official IDs compared to full publisher InChIKeys is a format error; even prefix matching is not official-tautomer membership')
 pool=ROOT/'assets/kaggle/ahmedberatozer/casmi26-v2-pool/v1'
 report['candidate_pool_file_rows']={n:pq.ParquetFile(pool/n).metadata.num_rows for n in ['train_structs.parquet','pool_meta.parquet']}
 ep=ROOT/'assets/kaggle/egehseyinca/enveda180-casmi26-reference-ccby4/v1/enveda180_hplus_hminus_references.parquet'
 batch=next(pq.ParquetFile(ep).iter_batches(batch_size=4096,columns=['spectrum_signature','adduct','neutral_mass','ms2_mzs','ms2_normalized_intensities']))
 counts=Counter();examples={};given=Counter()
 for row in batch.to_pylist():
  m=np.asarray(row['ms2_mzs'],dtype='<f4');it=np.asarray(row['ms2_normalized_intensities'],dtype='<f4')
  good=np.isfinite(m)&np.isfinite(it)&(m>0)&(it>0);m,it=m[good],it[good]
  ix=np.argsort(m,kind='stable');m,it=m[ix],it[ix]
  if len(it):it=it/it.max()
  h=hashlib.sha256();h.update(m.tobytes());h.update(it.tobytes());h.update(str((row['adduct'],row['neutral_mass'])).encode())
  k=h.hexdigest();counts[k]+=1;given[str(row['spectrum_signature'])]+=1;examples.setdefault(k,[]).append(str(row['spectrum_signature']))
 report['enveda_bounded_signature_check']=dict(rows=batch.num_rows,publisher_unique=len(given),
  independent_content_unique=len(counts),duplicate_content_groups=sum(n>1 for n in counts.values()),
  duplicate_extra_rows=sum(n-1 for n in counts.values() if n>1),
  first_signature_examples=[x for x in list(given)[:3]],
  exact_check='sorted finite positive peaks; float32 basepeak intensity normalization; exact neutral mass/adduct',
  scope='first4096 only, not full spectrum or train-reference overlap audit')
(out/'produre1_independent_checks.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='source_hashes'},indent=2,ensure_ascii=False))
