"""Bounded real-query match delta; no labels, GPU, main training library or score claim."""
from pathlib import Path
import gc
import json
import resource
import sys
import time

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import external_library_variants_20261110 as core


def save(p, value):
    p.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def main():
    out = ROOT/'runs/massbank_delta_20261113_v3'
    out.mkdir(exist_ok=False)
    report_dir = ROOT/'reports/optimization_20261113'
    report_dir.mkdir(parents=True, exist_ok=True)
    original = ROOT/'runs/external_overlay_actual_canary_20261109'
    inp = out/'input'
    inp.mkdir()
    source = original/'alex_function.py'
    recipe = json.loads((ROOT/'submission/optimization_20261109/mass_guarded_extlib/recipe.json').read_text())
    for item in recipe['files']:
        target=ROOT/'assets/kaggle'/item['ref']/('v'+str(item['version']))/item['file']
        link=inp/item['ref'].split('/')[1]/item['file']
        link.parent.mkdir(parents=True,exist_ok=True)
        link.symlink_to(target)
    queries = pd.read_parquet(ROOT/'enveda-CASMI26-molecule-id-mass-spectra/test.parquet')
    print('PUBLIC_QUERIES', len(queries), queries.molecule_id.nunique(), flush=True)
    mb_file = ROOT/'assets/kaggle/samartalwar/casmi-2026-spectral-library-massbankharmonized/v1/spectra.parquet'
    metadata = pd.read_parquet(mb_file, columns=['smiles','exact_mass','ion_mode','precursor_mz','adduct','is_casmi_subset','mzs','intensities'])
    corrected = []
    for index, row in metadata[(~metadata.is_casmi_subset.astype(bool)) & metadata.smiles.notna()].iterrows():
        mz,it=np.asarray(row.mzs,dtype=np.float64),np.asarray(row.intensities,dtype=np.float64)
        if np.sum((mz>0)&(it>0))<3:
            continue
        mode = 1 if 'pos' in str(row.ion_mode).lower() else -1
        old = float(row.exact_mass)+mode*1.007276
        measured, yes, reason = core.trusted_precursor(row.exact_mass,mode,row.adduct,row.precursor_mz,old)
        if yes:
            corrected.append(dict(row=int(index),mode=mode,old=old,measured=measured,adduct=str(row.adduct)))
    if len(corrected) != 1281:
        raise ValueError('Trusted correction scope changed')
    modes = np.array([x['mode'] for x in corrected])
    mass = np.array([x['measured'] for x in corrected])
    public_eligible = []
    for row in queries.itertuples(index=False):
        mode = 1 if 'pos' in str(row.ionization_mode).lower() else -1
        tol = float(row.precursor_mz)*1e-5+.002
        ix = np.flatnonzero((modes==mode)&(np.abs(mass-float(row.precursor_mz))<=tol))
        if len(ix):
            public_eligible.append(dict(molecule_id=str(row.molecule_id),precursor_mz=float(row.precursor_mz),
                                        adduct=str(row.adduct),reference_rows=[corrected[int(i)]['row'] for i in ix]))
    save(out/'trusted_metadata.json',dict(count=len(corrected),rows=corrected,public_mass_eligible=public_eligible))
    # Positive interface query from an actual corrected reference, without changing reference content.
    # Self-match is intentionally labeled; it is not evidence of hidden-test benefit.
    reference_rows = metadata.iloc[[x['row'] for x in corrected[:20]]]
    selected = []
    for item, (_, row) in zip(corrected[:20], reference_rows.iterrows()):
        mz = np.asarray(row.mzs, dtype=np.float64)
        it = np.asarray(row.intensities, dtype=np.float64)
        if np.sum((mz>0)&(it>0)&(mz<=item['measured']+.5))>=8:
            selected.append((item,row))
        if len(selected)>=3:
            break
    self_rows = []
    for item,row in selected:
        blank = {name:None for name in queries.columns}
        blank.update(molecule_id='trusted_self_'+str(item['row']),precursor_mz=item['measured'],adduct=item['adduct'],
                     ionization_mode='positive' if item['mode']==1 else 'negative',
                     ms2_mzs=np.asarray(row.mzs,dtype=np.float64),
                     ms2_normalized_intensities=np.asarray(row.intensities,dtype=np.float64))
        self_rows.append(blank)
    test = pd.concat([queries,pd.DataFrame(self_rows)],ignore_index=True)
    del metadata,reference_rows
    gc.collect()
    # Only fields actually read by original matcher; no truth, classification or learned scores.
    needed = ['molecule_id','precursor_mz','adduct','ionization_mode','ms2_mzs','ms2_normalized_intensities']
    test = test[needed]
    test_path=inp/'enveda-CASMI26-molecule-id-mass-spectra/test.parquet'
    test_path.parent.mkdir()
    test.to_parquet(test_path,index=False)
    ids=test.molecule_id.astype(str).drop_duplicates().tolist()
    controls=pd.DataFrame([dict(molecule_id=mid,smiles=';'.join('C'*i+'O' for i in range(1,26))) for mid in ids])
    evidence=pd.DataFrame([dict(molecule_id=mid,library_max=0.) for mid in ids])
    runtime={}
    for name,trusted in [('old_ab',False),('trusted_ab',True)]:
        work=out/name
        work.mkdir()
        controls.to_csv(work/'submission.csv',index=False)
        evidence.to_parquet(work/'frozen_candidate_evidence.parquet',index=False)
        cfg=dict(sources=['A','B'],e_policy='none',trusted_bprec=trusted,
                 old_helper_sha256=core.sha(ROOT/'scripts/external_library_overlay_20261109.py'),
                 e_helper_sha256=None,enveda_file=None)
        args=(work,inp,test_path,True,ids,dict(status='passed',csv_sha256=core.sha(work/'submission.csv')),
              source,core.sha(source),recipe['files'],cfg)
        start=time.monotonic()
        runtime[name]=core.run(*args)
        audit=core.audit(*args,name,'match_delta_only')
        assert audit['status']=='passed'
        print('MATCHED',name,'seconds',time.monotonic()-start,'changes',runtime[name]['changed_top1'],flush=True)
        gc.collect()
    old,new=runtime['old_ab'],runtime['trusted_ab']
    changes=[]
    for mid in ids:
        a,b=old['actual_matches'].get(mid),new['actual_matches'].get(mid)
        av=(a or {}).get('smiles') if (a or {}).get('above_threshold') else None
        bv=(b or {}).get('smiles') if (b or {}).get('above_threshold') else None
        if av != bv:
            changes.append(dict(molecule_id=mid,old=a,new=b,constructed_self=mid.startswith('trusted_self_')))
    old_csv=pd.read_csv(out/'old_ab/submission.csv',dtype=str,keep_default_na=False).set_index('molecule_id')
    new_csv=pd.read_csv(out/'trusted_ab/submission.csv',dtype=str,keep_default_na=False).set_index('molecule_id')
    final_changes=[mid for mid in ids if old_csv.loc[mid,'smiles']!=new_csv.loc[mid,'smiles']]
    result=dict(status='completed_match_delta',source_core_sha256=core.sha(ROOT/'scripts/external_library_variants_20261110.py'),
        visible_public_query_spectra=len(queries),visible_public_molecules=int(queries.molecule_id.nunique()),
        corrected_reference_rows=len(corrected),public_mass_eligible_spectra=len(public_eligible),
        public_mass_eligible_molecules=len({x['molecule_id'] for x in public_eligible}),
        match_identity_changes=changes,public_match_identity_changes=sum(not x['constructed_self'] for x in changes),
        constructed_self_match_identity_changes=sum(x['constructed_self'] for x in changes),
        final_changes_on_constructed_control=final_changes,
        public_final_changes_on_constructed_control=sum(not mid.startswith('trusted_self_') for mid in final_changes),
        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        no_truth_or_main_library_or_gpu=True,no_submission=True,
        limitation='Real visible query spectra and full reference libraries, but candidate lists and library_max=0 controls are constructed. Not exact champion predictions, no efficacy/hidden coverage claim.')
    save(out/'verification.json',result)
    save(report_dir/'massbank_match_delta.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('match_identity_changes','final_changes_on_constructed_control')},indent=2),flush=True)


if __name__=='__main__':
    main()
