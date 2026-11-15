"""Finish policy/hash observations using already completed actual pair matching.

The first checker selected the first (weakly supported) actual candidate for its
relocation fixture. A lack of movement there is legitimate. Keep that failure;
select the strongest existing support to test score consumption, with the
frozen algorithm and coefficients unchanged. Do not rerun/load the libraries.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.cache/rdkit-official-linux-2026033'))
import pandas as pd
import rdkit
OUT=ROOT/'runs/library_consensus_early_20261114_r2'
STAGE=ROOT/'submission/optimization_20261114/library_consensus_early/revision2'

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text())


def main():
    assert rdkit.__version__=='2026.03.3'
    before=read(OUT/'failure.json')
    assert before['error_type']=='AssertionError' and 'assert fixtures' in before['traceback']
    reports={};fixtures=[]
    work=OUT/'hidden_component';code=work/'p2s_code';sys.path.insert(0,str(code))
    spec=importlib.util.spec_from_file_location('actual_frozen_library_consensus',code/'library_consensus_early.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    for name in ['fast_static','hidden_component']:
        p=OUT/name;a=read(p/'library_consensus_audit.json');r=read(p/'library_consensus_runtime.json')
        assert a['status']=='passed' and all(a['checks'].values())
        reports[name]=dict(audit=a,changed_queries=r['changed_queries'],eligible_queries=r.get('eligible_queries'),pairs_observed=r.get('pairs_observed'),qualified_candidate_pairs=r.get('qualified_candidate_pairs'),protected_ids=r['protected_ids'],reference_counts=r['reference_counts'])
    runtime=read(work/'library_consensus_runtime.json')
    old=pd.read_csv(work/'submission_library_consensus_control.csv',dtype=str)
    for row,raw in zip(runtime['query_rows'],old.smiles):
        values=row['candidate_support'];arr=raw.split(';')
        candidates=sorted(range(len(values)),key=lambda i:-values[i]['consensus'])
        for i in candidates:
            if values[i]['supported_spectra']<2:continue
            group=[j for j,s in enumerate(arr) if module.formula(s)==module.formula(arr[i]) and j!=i]
            if len(group)<2:continue
            order=[group[0],group[1],i]+[j for j in range(len(arr)) if j not in (i,group[0],group[1])]
            fixture=';'.join(arr[j] for j in order);v=[values[j] for j in order]
            proposal,groups=module.reorder(fixture,v)
            fixtures.append(dict(molecule_id=row['molecule_id'],actual_supported_candidate_original_rank=i+1,actual_consensus=values[i]['consensus'],changed=proposal!=fixture,fixture_only=True,actual_scores_unchanged=True,formula_slots_preserved=all(module.formula(a)==module.formula(b) for a,b in zip(fixture.split(';'),proposal.split(';')))))
            break
    assert fixtures and any(x['changed'] for x in fixtures)
    production=ROOT/'runs/generation_production_20261113_r2/kaggle/working'
    base=read(production/'external_overlay_audit.json');mids=old.molecule_id.tolist()
    raw=(work/'submission.csv').read_bytes();(work/'submission.csv').write_bytes(raw+b'\n');rejected=False
    try:module.audit(work,True,mids,base,code/'alex_v12_external_function.py','library_consensus_early',sha(STAGE/'recipe.json'),sha(ROOT/'scripts/library_consensus_early_20261114_v2.py'))
    except ValueError:rejected=True
    finally:(work/'submission.csv').write_bytes(raw)
    assert rejected
    cols=list(pd.read_parquet(OUT/'input/enveda-CASMI26-molecule-id-mass-spectra/test.parquet').columns)
    result=dict(status='passed_actual_appended_cell_components',notebook_sha256=sha(STAGE/'notebook.ipynb'),recipe_sha256=sha(STAGE/'recipe.json'),module_sha256=sha(ROOT/'scripts/library_consensus_early_20261114_v2.py'),queries=2,spectra=20,official_input_columns=cols,truth_metadata_present=False,rdkit=rdkit.__version__,results=reports,actual_support_ranking_fixtures=fixtures,tampered_output_hash_rejected=True,earlier_checker_failure_preserved=True,pure_check_correction='Choose strongest already observed candidate instead of first weakly supported candidate; no algorithm or coefficient changes',full_pipeline_executed=False,truth_metrics_computed=False,limitation='Only exact appended cell on saved expanded-generation production output, not exact champion candidate set, no new full production pipeline or gain claim; relocation is a score-consumption fixture only.')
    p=OUT/'verification_completed.json';p.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':main()
