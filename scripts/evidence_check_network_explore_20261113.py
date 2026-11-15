"""Execute the frozen appended cell on cached real production output, without models."""
from pathlib import Path
import csv
import hashlib
import json
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
STAGE=ROOT/'submission/optimization_20261113/spectral_network_explore/revision2'
ACTUAL=ROOT/'runs/generation_production_20261113_r2/kaggle/working'
OUT=ROOT/'reports/optimization_20261113/evidence_network_explore_smoke'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):Path(p).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def main():
    import pandas as pd
    if OUT.exists():raise FileExistsError('Preserve first component test')
    OUT.mkdir(parents=True);inp=OUT/'input';comp=inp/'enveda-CASMI26-molecule-id-mass-spectra';comp.mkdir(parents=True)
    original=ROOT/'runs/generation_production_20261113_r2/kaggle/input/enveda-CASMI26-molecule-id-mass-spectra/test.parquet'
    official=['molecule_id','spectrum_id','ms2_mzs','ms2_normalized_intensities','base_peak_intensity','adduct','ionization_mode',
        'instrument_type','precursor_mz','collision_energy_orig','collision_energy_ev','collision_energy_orig_units']
    query=pd.read_parquet(original,columns=official);query.to_parquet(comp/'test.parquet',index=False)
    assert list(query.columns)==official and not {'normalized_smiles','inchikey14','official_identity'}&set(query.columns)
    book=read(STAGE/'notebook.ipynb');spec=read(STAGE/'branch_spec.json');recipe=read(STAGE/'recipe.json')
    assert sha(STAGE/'notebook.ipynb')==spec['notebook_sha256']
    parent=read(ROOT/'submission/optimization_20261109/mass_guarded_extlib/notebook.ipynb')
    assert book['cells'][:-1]==parent['cells']
    with (ACTUAL/'submission.csv').open() as f:ids=[r['molecule_id'] for r in csv.DictReader(f)]
    reports={}
    for mode,is_rerun in [('fast_static',False),('hidden_full_component',True)]:
        work=OUT/mode;work.mkdir();code=work/'code';code.mkdir()
        for name in ['submission.csv','external_overlay_runtime.json','frozen_candidate_evidence.parquet']:
            shutil.copy2(ACTUAL/name,work/name)
        shutil.copy2(ACTUAL/'p2s_code/external_library_overlay_20261109.py',code/'external_library_overlay_20261109.py')
        sys.path.insert(0,str(code))
        scope=dict(__name__='__main__',ROOT=work,CODE=code,INPUT=inp,COMP=comp,IS_RERUN=is_rerun,SAMPLE_IDS=ids,
            EXTERNAL_OVERLAY_AUDIT=read(ACTUAL/'external_overlay_audit.json'))
        cell=book['cells'][-1]['source'];cell=''.join(cell) if isinstance(cell,list) else cell
        exec(compile(cell,'actual_frozen_network_appended_cell','exec'),scope)
        runtime=read(work/'spectral_network_runtime.json');audit=read(work/'spectral_network_audit.json')
        assert audit['status']=='passed' and all(audit['checks'].values())
        reports[mode]=dict(audit=audit,network_executed=runtime['network_executed'],
            changed_queries=runtime['changed_queries'],changed_top1=runtime['changed_top1'],
            protected_ids=runtime['protected_ids'],graph=runtime.get('graph'),
            input_control_sha256=sha(ACTUAL/'submission.csv'),output_sha256=sha(work/'submission.csv'))
        if is_rerun:
            # Tamper only the final output hash in a separate mutable component
            # evidence record after saving the golden audit above.
            runtime['output_sha256']='0'*64;save(work/'spectral_network_runtime.json',runtime)
            try:
                scope['_network'].audit(work,True,ids,scope['EXTERNAL_OVERLAY_AUDIT'],code/'public_n1c_frozen.py',
                    recipe['public_source_sha256'],spec['name'],sha(STAGE/'recipe.json'),recipe['module_sha256'])
                rejected=False
            except ValueError:rejected=not (work/'submission.csv').exists()
            reports[mode]['tampered_output_hash_rejected_fail_closed']=rejected
            assert rejected
            save(work/'spectral_network_runtime_golden.json',read(work/'spectral_network_runtime.json')|{'output_sha256':reports[mode]['output_sha256']})
            shutil.copy2(work/'spectral_network_runtime.json',work/'spectral_network_runtime_tampered.json')
            shutil.copy2(work/'spectral_network_runtime_golden.json',work/'spectral_network_runtime.json')
            # Both actual diagnostic rows have no network edges, hence the
            # positive output is exactly the cached input; preserve it as well
            # as the explicitly named negative-test evidence.
            assert reports[mode]['changed_queries']==0
            shutil.copy2(ACTUAL/'submission.csv',work/'submission.csv')
            assert sha(work/'spectral_network_runtime.json')==audit['runtime_sha256']
    result=dict(status='passed_actual_appended_cell_component_only',notebook_sha256=sha(STAGE/'notebook.ipynb'),
        recipe_sha256=sha(STAGE/'recipe.json'),module_sha256=recipe['module_sha256'],public_source_sha256=recipe['public_source_sha256'],
        original_all33_cells_exact=True,query_columns_exact_official=official,truth_metadata_present=False,
        raw_source_parquet_sha256=sha(original),projected_query_sha256=sha(comp/'test.parquet'),spectra=len(query),queries=len(ids),
        reports=reports,no_models_run=True,no_new_effectiveness_evaluation=True,
        limitations=['Actual saved two-query output came from the successful generation-production full-chain run, not a fresh .488 run.',
            'Only appended network cell and audit executed. No claim complete new pipeline ran.',
            'Zero graph/changes is valid execution evidence, not gain evidence.',
            'Old Flex48 fixed-policy efficacy was negative; this remains explicitly exploratory at user request.'])
    save(OUT/'verification.json',result);print(json.dumps(result,indent=2))

if __name__=='__main__':main()
