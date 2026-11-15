"""Actual appended-cell component on saved production output; no truth metrics."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[1]
SITE=ROOT/'.cache/rdkit-official-linux-2026033'
os.environ['PYTHONPATH']=str(SITE)+os.pathsep+os.environ.get('PYTHONPATH','')
sys.path.insert(0,str(SITE))
import numpy as np
import pandas as pd
import rdkit

PRODUCTION=ROOT/'runs/generation_production_20261113_r2/kaggle/working'
STAGE=ROOT/'submission/optimization_20261114/library_consensus_early/revision2'
OUT=ROOT/'runs/library_consensus_early_20261114_r2'

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def save(p,x):Path(p).write_text(json.dumps(x,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def source(c):return ''.join(c['source']) if isinstance(c['source'],list) else c['source']


def main():
    assert rdkit.__version__=='2026.03.3'
    OUT.mkdir(exist_ok=False,parents=True)
    inp=OUT/'input';inp.mkdir();original_input=PRODUCTION.parent/'input'
    cols=['molecule_id','spectrum_id','ms2_mzs','ms2_normalized_intensities','base_peak_intensity','adduct','ionization_mode','instrument_type','precursor_mz','collision_energy_orig','collision_energy_ev','collision_energy_orig_units']
    tests=list(original_input.rglob('test.parquet'));assert len(tests)==1
    comp=inp/'enveda-CASMI26-molecule-id-mass-spectra';comp.mkdir()
    query=pd.read_parquet(tests[0],columns=cols);query.to_parquet(comp/'test.parquet',index=False)
    assert list(pd.read_parquet(comp/'test.parquet').columns)==cols
    recipe=read(STAGE/'recipe.json')
    for f in recipe['library_files']:
        candidates=list(original_input.rglob(f['file']));assert len(candidates)==1
        dest=inp/f['ref'].split('/')[1];dest.mkdir(exist_ok=True)
        os.link(candidates[0],dest/f['file'])
    book=read(STAGE/'notebook.ipynb');parent=read(ROOT/'submission/optimization_20261109/mass_guarded_extlib/notebook.ipynb')
    assert book['cells'][:-1]==parent['cells']
    mids=pd.read_csv(PRODUCTION/'submission.csv',dtype=str).molecule_id.tolist()
    results={}
    for name,hidden in [('fast_static',False),('hidden_component',True)]:
        work=OUT/name;work.mkdir();code=work/'p2s_code';code.mkdir()
        for f in ['alex_v12_external_function.py','external_library_overlay_20261109.py']:
            shutil.copy2(PRODUCTION/'p2s_code'/f,code/f)
        shutil.copy2(PRODUCTION/'submission.csv',work/'submission.csv')
        shutil.copy2(PRODUCTION/'external_overlay_runtime.json',work/'external_overlay_runtime.json')
        shutil.copy2(PRODUCTION/'frozen_candidate_evidence.parquet',work/'frozen_candidate_evidence.parquet')
        base=read(PRODUCTION/'external_overlay_audit.json')
        assert base['csv_sha256']==sha(work/'submission.csv')
        if str(code) not in sys.path:sys.path.insert(0,str(code))
        scope=dict(Path=Path,pd=pd,np=np,ROOT=work,CODE=code,INPUT=inp,COMP=comp,IS_RERUN=hidden,SAMPLE_IDS=mids,EXTERNAL_OVERLAY_AUDIT=base)
        started=time.monotonic();exec(compile(source(book['cells'][-1]),'actual_library_consensus_append','exec'),scope)
        audit=read(work/'library_consensus_audit.json');runtime=read(work/'library_consensus_runtime.json')
        assert audit['status']=='passed' and all(audit['checks'].values())
        before=pd.read_csv(work/'submission_library_consensus_control.csv',dtype=str);after=pd.read_csv(work/'submission.csv',dtype=str)
        assert all(a.split(';')[0]==b.split(';')[0] for a,b in zip(before.smiles,after.smiles))
        assert all(Counter(a.split(';'))==Counter(b.split(';')) for a,b in zip(before.smiles,after.smiles))
        assert all(all(scope['_consensus'].formula(a)==scope['_consensus'].formula(b) for a,b in zip(x.split(';'),y.split(';'))) for x,y in zip(before.smiles,after.smiles))
        results[name]=dict(seconds=time.monotonic()-started,audit=audit,changed_queries=runtime['changed_queries'],eligible_queries=runtime.get('eligible_queries'),pairs_observed=runtime.get('pairs_observed'),qualified_candidate_pairs=runtime.get('qualified_candidate_pairs'),protected_ids=runtime['protected_ids'],reference_counts=runtime['reference_counts'])
        if hidden:
            fixtures=[]
            for row,raw in zip(runtime['query_rows'],before.smiles):
                values=row['candidate_support'];arr=raw.split(';')
                # Pure ranking-consumption fixture: move an actual library-supported
                # candidate down two slots. This is not a prediction or efficacy run.
                for i,v in enumerate(values):
                    if v['supported_spectra']<2:continue
                    group=[j for j,s in enumerate(arr) if scope['_consensus'].formula(s)==scope['_consensus'].formula(arr[i]) and j!=i]
                    if len(group)<2:continue
                    order=[j for j in range(len(arr)) if j not in (i,group[0],group[1])]
                    order=[group[0],group[1],i]+order
                    fixture=';'.join(arr[j] for j in order);fvalues=[values[j] for j in order]
                    proposal,groups=scope['_consensus'].reorder(fixture,fvalues)
                    fixtures.append(dict(molecule_id=row['molecule_id'],actual_supported_candidate_original_rank=i+1,changed=proposal!=fixture,fixture_only=True,source_spectrum_scores_unchanged=True,formula_slots_preserved=all(scope['_consensus'].formula(a)==scope['_consensus'].formula(b) for a,b in zip(fixture.split(';'),proposal.split(';')))))
                    break
            results['actual_score_reordering_fixture']=fixtures
            assert fixtures and any(x['changed'] for x in fixtures)
            # Audit must bind actual output bytes, not just a successful function call.
            original=(work/'submission.csv').read_bytes();(work/'submission.csv').write_bytes(original+b'\n')
            rejected=False
            try:scope['_consensus'].audit(work,hidden,mids,base,code/'alex_v12_external_function.py','library_consensus_early',sha(STAGE/'recipe.json'),sha(ROOT/'scripts/library_consensus_early_20261114_v2.py'))
            except ValueError:rejected=True
            finally:(work/'submission.csv').write_bytes(original)
            assert rejected;results['tampered_output_hash_rejected']=True
    report=dict(status='passed_actual_appended_cell_components',notebook_sha256=sha(STAGE/'notebook.ipynb'),recipe_sha256=sha(STAGE/'recipe.json'),module_sha256=sha(ROOT/'scripts/library_consensus_early_20261114_v2.py'),rdkit=rdkit.__version__,queries=len(mids),spectra=len(query),official_input_columns=cols,truth_metadata_present=False,source_production_output_sha256=sha(PRODUCTION/'submission.csv'),source_test_sha256=sha(tests[0]),query_projection_sha256=sha(comp/'test.parquet'),results=results,full_pipeline_executed=False,truth_metrics_computed=False,limitation='Only exact new appended cell executed on saved actual production intermediate from generation-expanded two-query smoke, not exact champion candidate set and no new complete production run. Library-supported candidate relocation fixture tests score consumption, not prediction improvement.')
    save(OUT/'verification.json',report);print(json.dumps(report))


if __name__=='__main__':
    from collections import Counter
    try:main()
    except BaseException as e:
        if OUT.exists():save(OUT/'failure.json',dict(status='failed',error_type=type(e).__name__,traceback=traceback.format_exc()))
        raise
