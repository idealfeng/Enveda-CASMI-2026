"""Exercise new network scoring on existing real spectra/predictions; never run models."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import spectral_network_20261113 as network


def save(p,v):Path(p).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def main():
    import pandas as pd
    parser=argparse.ArgumentParser();parser.add_argument('--tag',default='first');args=parser.parse_args()
    out=ROOT/'runs'/('spectral_network_20261113_'+args.tag);out.mkdir(exist_ok=False)
    inputs=out/'inputs';inputs.mkdir()
    shutil.copy2(ROOT/'runs/validation_pilot_v2_20261104/queries.parquet',inputs/'test.parquet')
    source=ROOT/'reports/optimization_20261113/public_short/analyticaobscura__casmi-2026/cells/24.py'
    source_pin=network.sha(source);module_pin=network.sha(ROOT/'scripts/spectral_network_20261113.py')
    control=ROOT/'runs/validation_flex_c2_20261105d/submission.csv'
    original=pd.read_csv(control,dtype=str,keep_default_na=False);ids=original.molecule_id.tolist()
    results={}
    def run(name,real,protected=None):
        work=out/name;work.mkdir();shutil.copy2(control,work/'submission.csv')
        runtime=dict(output_sha256=network.sha(control),actual_matches=[],details=[])
        if protected:runtime['actual_matches']=[dict(molecule_id=protected,above_threshold=True,cosine=.99,matched_peaks=10)]
        save(work/'external_overlay_runtime.json',runtime)
        audit=dict(status='passed',csv_sha256=network.sha(control),runtime_report_sha256=network.sha(work/'external_overlay_runtime.json'))
        report=network.run(work,inputs,inputs/'test.parquet',real,ids,audit,source,source_pin,'spectral_network','fixture-recipe')
        checked=network.audit(work,real,ids,audit,source,source_pin,'spectral_network','fixture-recipe',module_pin)
        return work,report,checked
    fast,rf,af=run('fast',False)
    hidden,rh,ah=run('real_cached_panel',True)
    checks=dict(fast_exact=rf['changed_queries']==0,real_scores_consumed=ah['checks']['actual_score_consumption'],
                real_spectra_used=rh['graph']['spectra_molecules']>0,edges_observed=rh['graph']['edges']>0,
                output_has_real_changes=rh['changed_queries']>0,candidate_multisets=ah['checks']['candidate_multisets'])
    if rh['accepted_ids']:
        mid=rh['accepted_ids'][0];protected,rp,ap=run('protected',True,mid)
        changed=pd.read_csv(protected/'submission.csv',dtype=str,keep_default_na=False)
        checks['actual_reference_hit_protected']=changed.loc[changed.molecule_id==mid,'smiles'].iloc[0]==original.loc[original.molecule_id==mid,'smiles'].iloc[0]
    else:checks['actual_reference_hit_protected']=False
    # The observer independently reconstructs ordering from captured score vectors.
    p=hidden/'spectral_network_runtime.json';runtime=json.loads(p.read_text());first=next(iter(runtime['observations']))
    runtime['observations'][first]['order']=list(reversed(runtime['observations'][first]['order']));save(p,runtime)
    try:
        network.audit(hidden,True,ids,dict(status='passed',csv_sha256=network.sha(control)),source,source_pin,'spectral_network','fixture-recipe',module_pin)
        checks['tampered_score_order_rejected']=False
    except (ValueError,KeyError):checks['tampered_score_order_rejected']=True
    record=dict(status='passed' if all(checks.values()) else 'no_ready_candidate',checks=checks,source_sha256=source_pin,module_sha256=module_pin,
        actual_panel_queries=len(ids),spectra_molecules=rh['graph']['spectra_molecules'],edges=rh['graph']['edges'],
        changed_queries=rh['changed_queries'],changed_top1=rh['changed_top1'],no_truth_read=True,
        scope='Existing old Flex48 predictions and real query spectra; constructed AB control receipt. Not an exact .488 efficacy comparison or complete pipeline run.')
    save(out/'verification.json',record);save(ROOT/'reports/optimization_20261113/network_canary.json',record)
    print(json.dumps(record,indent=2))


if __name__=='__main__':main()
