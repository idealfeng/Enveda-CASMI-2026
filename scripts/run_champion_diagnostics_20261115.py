"""Replay the fixed .488 outer notebook with explicit diagnostic isolation.

All changes are reference/coverage observations and documented resource hooks.
No old scores are injected, no fitting or Kaggle writes occur in this runner.
"""
from pathlib import Path
import argparse
import ast
import hashlib
import json
import os
import shutil
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'submission/optimization_20261109/mass_guarded_extlib'
OUT=ROOT/'runs/champion_error_decomposition_20261115'
PANEL=ROOT/'runs/validation_pilot_v2_20261104'
PIN='2bb94c91b176f95dfdff52f08781443ffee004c20d06aeb30efb14d0c0112fc7'
CANARY='cross_VXVNYCRICCVPTD'
QUERY_FIELDS=['molecule_id','spectrum_id','ms2_mzs','ms2_normalized_intensities',
              'base_peak_intensity','adduct','ionization_mode','instrument_type',
              'precursor_mz','collision_energy_orig','collision_energy_ev','collision_energy_orig_units']

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def save(p,v):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(v,indent=2,ensure_ascii=False,default=str)+'\n',encoding='utf-8')
def src(c):return ''.join(c['source']) if isinstance(c['source'],list) else c['source']

def prepare(arm,full,revision=''):
    import pandas as pd
    import pyarrow.parquet as pq
    if sha(BASE/'notebook.ipynb')!=PIN:raise ValueError('Champion source changed')
    manifest=read(PANEL/'manifest.json')
    for name,pin in manifest['artifact_sha256'].items():
        if sha(PANEL/name)!=pin:raise ValueError('Frozen panel differs: '+name)
    run=OUT/(('full48_' if full else 'canary_')+arm+('_'+revision if revision else ''))
    if run.exists():raise FileExistsError('Preserve previous replay: '+str(run))
    run.mkdir(parents=True)
    view=run/'kaggle';inp=view/'input';work=view/'working';inp.mkdir(parents=True);work.mkdir()
    for item in read(BASE/'kernel-metadata.json')['dataset_sources']:
        owner,slug,version=item.split('/');asset=ROOT/'assets/kaggle'/owner/slug/('v'+version)
        if not asset.is_dir():raise FileNotFoundError(asset)
        for folder,dirs,files in os.walk(asset,followlinks=False):
            dirs[:]=[d for d in dirs if d!='__pycache__']
            target=inp/slug/Path(folder).relative_to(asset);target.mkdir(parents=True,exist_ok=True)
            for name in files:
                if not name.endswith('.pyc'):os.link((Path(folder)/name).resolve(),target/name)
    comp=inp/'enveda-CASMI26-molecule-id-mass-spectra';comp.mkdir()
    queries=pd.read_parquet(PANEL/'queries.parquet')
    selected=queries if full else queries.loc[queries.molecule_id.eq(CANARY)]
    if selected.empty:raise ValueError('Missing fixed canary')
    ids=selected.molecule_id.astype(str).drop_duplicates().tolist()
    selected[QUERY_FIELDS].to_parquet(comp/'test.parquet',index=False)
    pd.DataFrame(dict(molecule_id=ids,smiles=['C']*len(ids))).to_csv(comp/'sample_submission.csv',index=False)
    (comp/'train.parquet').symlink_to(ROOT/'enveda-CASMI26-molecule-id-mass-spectra/train.parquet')
    cfg=dict(schema_version=1,pipeline='champion_0488',reference_mode=arm,
        work_root=str(work),run_root=str(run),queries_file=str(PANEL/'queries.parquet'),
        active_ids=ids,processed_molecules=len(ids),base_train_rows=manifest['train']['rows'],
        shared_spec_cache=str(ROOT/'runs/shared_spec_cache'),
        e2_workers=1,
        exclusion_rows_file=str(PANEL/('query_duplicate_exclusion_rows.parquet' if arm=='class1' else 'class2_exclusion_rows.parquet')),
        exclusion_keys_file=str(PANEL/'class2_exclusion_keys.json'),
        blocked_official_identities=read(PANEL/'class2_exclusion_keys.json')['blocked_official_identities'],
        original_notebook_sha256=PIN,canary_only=not full,query_columns=QUERY_FIELDS,
        query_test_sha256=sha(comp/'test.parquet'),query_spectrum_cap=None,
        cohort_policy='Class1 removes original48 query spectra/exact duplicates; Class2/3 globally exclude all original48 identities from every measured reference. Class3 additionally removes them from every static candidate source, not generated products.',
        labels_in_inference_test=False,legacy_pretrained_exposure=True,
        changed_model_weights=False,produre_experiments_rerun=False,new_public_score=None)
    save(run/'configuration.json',cfg)
    site=run/'resource_site';site.mkdir()
    (site/'sitecustomize.py').write_text('import os,sys\nos.cpu_count=lambda:4\nsys.path.insert(0,'+repr(str(ROOT))+')\nsys.path.insert(0,'+repr(str(ROOT/'scripts'))+')\nsys.path.insert(0,'+repr(str(ROOT/'.cache/rdkit-official-linux-2026033'))+')\n',encoding='utf-8')
    save(run/'preparation.json',dict(status='prepared_not_executed',reference_mode=arm,
        original_notebook_sha256=PIN,configuration_sha256=sha(run/'configuration.json'),
        query_ids=ids,spectra=len(selected),columns=QUERY_FIELDS,unlabelled_test=True,
        only_reference_and_observation_adaptations=True,no_cached_scores=True,
        resource_adaptations=['cpu_count=4','E2 workers=1 to bound memory','verified shared spectrum cache and local mmap'],
        requires_runtime_reference_and_stage_audits=True,view=str(view)))
    return dict(status='prepared_not_executed',run_root=str(run),queries=len(ids),spectra=len(selected))

def replay(run):
    sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
    cfg=read(run/'configuration.json');work=run/'kaggle/working'
    if sha(BASE/'notebook.ipynb')!=PIN:raise ValueError('Champion changed')
    if sha(run/'configuration.json')!=read(run/'preparation.json')['configuration_sha256']:raise ValueError('Prepared reference configuration changed')
    if not Path('/kaggle').is_mount() or not os.path.samefile('/kaggle/working',work):raise ValueError('D-backed intended bind mount required')
    if (work/'submission.csv').exists():raise FileExistsError('Fresh full replay only')
    for module in ['champion_stage_observer_20261115.py','champion_reference_masks_20261115.py','replay_champion_inner_20261115.py']:
        if not (ROOT/'scripts'/module).is_file():raise FileNotFoundError(module)
    os.environ['KAGGLE_IS_COMPETITION_RERUN']='1';os.environ['MPLBACKEND']='Agg'
    os.environ['CASMI_CHAMPION_DIAGNOSTIC_CONFIG']=str(run/'configuration.json')
    sources=run/'executed_sources';sources.mkdir(exist_ok=False)
    pins={}
    for name in ['run_champion_diagnostics_20261115.py','replay_champion_inner_20261115.py','champion_stage_observer_20261115.py','champion_reference_masks_20261115.py']:
        p=ROOT/'scripts'/name;pins[name]=sha(p);shutil.copy2(p,sources/name)
    save(run/'launch_bindings.json',dict(original_champion_sha256=PIN,script_pins=pins,configuration_sha256=sha(run/'configuration.json'),process_id=os.getpid(),started_epoch=time.time(),e2_resource_helper_sha256=sha(ROOT/'validation/e2_resources.py'),new_public_score=None))
    from build_generation_variant_20261112_r3 import original_runner
    book=read(BASE/'notebook.ipynb');runner_pin=hashlib.sha256(original_runner(book).encode()).hexdigest()
    scope={'__name__':'__main__'};marks=[];started=time.monotonic()
    try:
        for i,cell in enumerate(book['cells']):
            if cell['cell_type']!='code':continue
            text=src(cell)
            if i==20:
                from champion_reference_masks_20261115 import patch_outer_static_cell
                text=patch_outer_static_cell(text,run/'configuration.json')
            if i==32:
                needle='_external_spec.loader.exec_module(_external_overlay)'
                if text.count(needle)!=1:raise ValueError('AB installer site changed')
                text=text.replace(needle,needle+'\n    from champion_reference_masks_20261115 import install_ab_observer_filter\n    install_ab_observer_filter(os.environ["CASMI_CHAMPION_DIAGNOSTIC_CONFIG"],_external_overlay)')
            print('CHAMPION OUTER',i,'START',flush=True);tick=time.monotonic()
            exec(compile(text,f'champion_outer_cell_{i}','exec'),scope)
            if i==12:
                original_run_stage=scope['run_stage']
                def run_stage(args,log,name,quiet=None):
                    if len(args)>1 and Path(args[1]).name=='runner.py':
                        if sha(args[1])!=runner_pin:raise ValueError('Original runner changed')
                        args=list(args);args[1]=str(ROOT/'scripts/replay_champion_inner_20261115.py')
                    return original_run_stage(args,log,name,quiet=quiet)
                scope['run_stage']=run_stage
            from champion_stage_observer_20261115 import after_outer_cell
            after_outer_cell(scope,i,work)
            marks.append(dict(cell=i,seconds=time.monotonic()-tick))
            save(run/'progress.json',dict(status='running',last_complete_outer_cell=i,marks=marks,seconds=time.monotonic()-started))
            print('CHAMPION OUTER',i,'DONE',flush=True)
        audits={n:read(work/n) for n in ['batch_variant_audit.json','guarded_tail_audit.json','external_overlay_audit.json']}
        if not all(a['status']=='passed' and a['mode']=='hidden_full' and all(a['checks'].values()) for a in audits.values()):raise ValueError('Original champion audits failed')
        from champion_reference_masks_20261115 import assert_installation_complete
        isolation=assert_installation_complete(run/'configuration.json')
        from champion_stage_observer_20261115 import finish
        observer=finish(scope,work,'outer')
        if any(sha(ROOT/'scripts'/name)!=pin for name,pin in pins.items()):raise ValueError('Executed diagnostic source changed during replay')
        save(run/'verification.json',dict(status='completed_original_champion_with_diagnostic_reference_masks',
             original_notebook_sha256=PIN,configuration_sha256=sha(run/'configuration.json'),
             seconds=time.monotonic()-started,original_audits=audits,isolation_installation=isolation,observer=observer,marks=marks,
             output_sha256=sha(work/'submission.csv'),new_public_score=None,
             pretrained_exposure=True,canary_only=cfg['canary_only'],
             note='Completion is not isolation approval: separate reference audit and candidate coverage audit must pass before class metrics.'))
    except BaseException as e:
        save(run/'failure.json',dict(status='failed',exception=type(e).__name__,message=str(e),traceback=traceback.format_exc(),marks=marks,seconds=time.monotonic()-started));raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare',action='store_true');p.add_argument('--arm',choices=['class1','class2','class3'],required=True);p.add_argument('--full48',action='store_true');p.add_argument('--revision',default='');a=p.parse_args()
    if a.revision and not a.revision.isalnum():raise ValueError('Alphanumeric revision required')
    if a.prepare:print(json.dumps(prepare(a.arm,a.full48,a.revision)))
    else:replay(OUT/(('full48_' if a.full48 else 'canary_')+a.arm+('_'+a.revision if a.revision else '')))
