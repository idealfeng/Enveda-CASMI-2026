"""Read-only thin-batch audit of actual MassBank precursor metadata."""
from pathlib import Path
from collections import Counter,defaultdict
import hashlib,json,math,time
import numpy as np
import pyarrow.parquet as pq
ROOT=Path(__file__).resolve().parents[2]
P=ROOT/'assets/kaggle/samartalwar/casmi-2026-spectral-library-massbankharmonized/v1/spectra.parquet'
started=time.monotonic();pf=pq.ParquetFile(P)
required=['smiles','exact_mass','ion_mode','mzs','intensities','is_casmi_subset','adduct','precursor_mz']
missing=set(required)-set(pf.schema_arrow.names)
if missing:raise ValueError('Missing measured precursor fields '+repr(missing))
count=Counter();byadduct=defaultdict(Counter);examples=[];allerrs=[];expectederrs=[];invalid_examples=[]
offsets={'[M+H]+':(1,1.007276466621),'[M-H]-':(1,-1.007276466621),'[M+Na]+':(1,22.989218),'[M+K]+':(1,38.963158),'[M+NH4]+':(1,18.033823),'[M+HCOO]-':(1,44.998201),'[M+FA-H]-':(1,44.998201),'[M+H-H2O]+':(1,-17.003288),'[M-H2O+H]+':(1,-17.003288),'[M+Cl]-':(1,34.969402),'[M+2H]2+':(2,2.014552933242),'[M-2H]2-':(2,-2.014552933242)}
for b in pf.iter_batches(batch_size=8192,columns=required,use_threads=False):
 for r in b.to_pylist():
  count['raw_rows']+=1
  if bool(r['is_casmi_subset']) or r['smiles'] is None:continue
  count['non_casmi_smiles_rows']+=1
  try:
   mz=np.asarray(r['mzs'],float);it=np.asarray(r['intensities'],float)
   valid=(mz>0)&(it>0)
   if int(valid.sum())<3:continue
   mode=1 if 'pos' in str(r['ion_mode']).lower() else -1
   nm=float(r['exact_mass']);old=nm+1.007276*mode
   # Match the original usable-reference loader, including permissive masses.
   ad=str(r['adduct']);count['usable_refs']+=1;byadduct[ad]['usable_refs']+=1
  except (TypeError,ValueError):count['loader_failures']+=1;continue
  try:prec=float(r['precursor_mz'])
  except (TypeError,ValueError):prec=float('nan')
  if not math.isfinite(prec) or prec<=0:
   count['missing_or_invalid_measured_precursor']+=1;byadduct[ad]['missing_or_invalid']+=1
   if len(invalid_examples)<6:invalid_examples.append(dict(adduct=ad,precursor=r['precursor_mz']))
   continue
  count['finite_positive_measured_precursor']+=1;byadduct[ad]['measured']+=1
  tol=prec*1e-5+.002;err=abs(prec-old)
  if not math.isfinite(err):count['old_synthetic_nonfinite']+=1;continue
  allerrs.append(err)
  if err>tol:
   count['measured_outside_old_10ppm_plus_002']+=1;byadduct[ad]['outside_old_window']+=1
   if len(examples)<12:examples.append(dict(adduct=ad,measured_precursor=prec,old_neutral_plus_carrier=old,absolute_da=err,neutral_mass=nm))
  else:count['measured_within_old_window']+=1
  if ad in offsets:
   z,delta=offsets[ad];expected=(nm+delta)/z;err2=abs(prec-expected);expectederrs.append(err2)
   count['known_adduct_measured_rows']+=1;byadduct[ad]['known_adduct_measured_rows']+=1
   if err2>tol:count['measured_inconsistent_with_named_adduct_and_mass']+=1;byadduct[ad]['inconsistent_known_adduct_mass']+=1
   else:
    count['measured_consistent_with_named_adduct_and_mass']+=1
    compatible=(ad.endswith('+') and mode==1) or (ad.endswith('-') and mode==-1)
    if not compatible:count['named_adduct_mode_inconsistent']+=1
    if err>tol:
     count['changed_measured_and_chemically_consistent']+=1;byadduct[ad]['changed_chemically_consistent']+=1
     if compatible:count['changed_chemically_consistent_and_mode_compatible']+=1
with P.open('rb') as f:pin=hashlib.file_digest(f,'sha256').hexdigest()
report=dict(status='completed_read_only',source=str(P.relative_to(ROOT)),source_sha256=pin,elapsed_seconds=time.monotonic()-started,
 counts=dict(count),by_adduct={k:dict(v) for k,v in sorted(byadduct.items(),key=lambda x:-x[1]['usable_refs'])},
 absolute_da_quantiles=dict(zip(['p0','p50','p90','p99','p100'],np.quantile(allerrs,[0,.5,.9,.99,1]).tolist())),
 named_adduct_absolute_da_quantiles=dict(zip(['p0','p50','p90','p99','p100'],np.quantile(expectederrs,[0,.5,.9,.99,1]).tolist())),
 discrepant_examples=examples,invalid_measured_examples=invalid_examples,
 interpretation='Finite-positive publisher measured precursor is materially different for some records; no assay/pipeline score inferred. Missing measured values can retain exact original fallback. A valid measured number alone does not prove metadata correct.',
 no_user_artifact_or_frozen_source_changes=True,no_training_or_network_or_gpu=True)
out=Path(__file__).parent/'massbank_precursor_metadata.json';out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='by_adduct'},ensure_ascii=False,indent=2))
