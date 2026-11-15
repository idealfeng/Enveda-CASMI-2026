"""Fixed-policy actual graph/order component replay; never read labels or run models."""
from pathlib import Path
import hashlib
import importlib.util
import json
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/optimization_20261113/evidence_network_delta'
STAGE=ROOT/'submission/optimization_20261113/spectral_network_explore/revision2'
SOURCE=ROOT/'reports/optimization_20261113/public_short/analyticaobscura__casmi-2026/cells/24.py'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def save(p,v):Path(p).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    import pandas as pd
    if OUT.exists():raise FileExistsError('Preserve first delta replay')
    OUT.mkdir(parents=True);inp=OUT/'inputs';inp.mkdir()
    columns=['molecule_id','spectrum_id','ms2_mzs','ms2_normalized_intensities','base_peak_intensity','adduct','ionization_mode',
        'instrument_type','precursor_mz','collision_energy_orig','collision_energy_ev','collision_energy_orig_units']
    q=pd.read_parquet(ROOT/'runs/validation_pilot_v2_20261104/queries.parquet',columns=columns)
    q.to_parquet(inp/'test.parquet',index=False)
    control=ROOT/'runs/validation_flex_c2_20261105d/submission.csv';old=pd.read_csv(control,dtype=str,keep_default_na=False)
    ids=old.molecule_id.tolist();recipe=read(STAGE/'recipe.json')
    module=ROOT/'scripts/spectral_network_explore_20261113.py';assert sha(module)==recipe['module_sha256']
    spec=importlib.util.spec_from_file_location('network_delta',module);n=importlib.util.module_from_spec(spec);spec.loader.exec_module(n)
    sys.path.insert(0,str(ROOT/'reports/optimization_20261113/evidence_generation_sources'))
    results={}
    def run(name,protect=None):
        work=OUT/name;work.mkdir();shutil.copy2(control,work/'submission.csv')
        # This intentionally constructed interface receipt does not claim an
        # actual .488 AB run. The replay tests network score/output mechanics.
        runtime=dict(output_sha256=sha(control),actual_matches=[] if protect is None else [dict(molecule_id=protect,above_threshold=True)],details=[])
        save(work/'external_overlay_runtime.json',runtime)
        base=dict(status='passed',csv_sha256=sha(control),runtime_report_sha256=sha(work/'external_overlay_runtime.json'))
        r=n.run(work,inp,inp/'test.parquet',True,ids,base,SOURCE,recipe['public_source_sha256'],'spectral_network_explore',sha(STAGE/'recipe.json'))
        a=n.audit(work,True,ids,base,SOURCE,recipe['public_source_sha256'],'spectral_network_explore',sha(STAGE/'recipe.json'),recipe['module_sha256'])
        assert a['status']=='passed' and all(a['checks'].values())
        return r,a
    r,a=run('actual_graph');assert r['graph']['edges']>0 and r['changed_queries']>0 and r['accepted_ids']
    mid=r['accepted_ids'][0];rp,ap=run('protected',mid)
    final=pd.read_csv(OUT/'protected/submission.csv',dtype=str,keep_default_na=False)
    protected_equal=final.loc[final.molecule_id==mid,'smiles'].iloc[0]==old.loc[old.molecule_id==mid,'smiles'].iloc[0]
    assert protected_equal
    result=dict(status='passed_fixed_policy_real_graph_component',notebook_sha256=sha(STAGE/'notebook.ipynb'),module_sha256=sha(module),
        public_source_sha256=sha(SOURCE),recipe_sha256=sha(STAGE/'recipe.json'),queries=len(ids),spectra=len(q),
        graph=r['graph'],changed_queries=r['changed_queries'],changed_top1=r['changed_top1'],
        score_vectors_reconstructed=a['checks']['actual_score_consumption'],candidate_multisets=a['checks']['candidate_multisets'],
        official_identities=a['checks']['official_identities'],protection_fixture_query=mid,protection_exact=protected_equal,
        raw_spectral_columns=columns,truth_metadata_present=False,no_labels_read=True,no_new_metric_evaluated=True,
        no_models_run=True,coefficient_search=False,
        limitations=['Old exposed 48-query Flex predictions, not exact .488 stage output.',
            'Constructed AB interface receipt, not AB efficacy or full-pipeline execution.',
            'The frozen fixed-policy old panel MRR delta was negative; these ordering changes do not claim a gain.'])
    save(OUT/'verification.json',result);print(json.dumps({k:v for k,v in result.items() if k!='graph'},indent=2))

if __name__=='__main__':main()
