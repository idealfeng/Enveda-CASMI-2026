"""Exact frozen outer Notebook replay on two diagnostic queries in a D-backed /kaggle bind mount.

No component injection, cell skipping, cached scores, labels, or produre reexecution.
The one resource adaptation caps os.cpu_count() at four in all subprocesses.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'runs/generation_production_20261113'
STAGE=ROOT/'submission/optimization_20261113/generation_production'


def read(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v): Path(p).write_text(json.dumps(v,indent=2,default=str)+'\n',encoding='utf-8')


def prepare():
    import pandas as pd
    import pyarrow.parquet as pq
    if RUN.exists(): raise FileExistsError('Preserve production replay')
    RUN.mkdir(parents=True)
    view=RUN/'kaggle'; inp=view/'input'; work=view/'working'
    inp.mkdir(parents=True);work.mkdir()
    metadata=read(STAGE/'kernel-metadata.json')
    for item in metadata['dataset_sources']:
        owner,slug,version=item.split('/')
        source=ROOT/'assets/kaggle'/owner/slug/('v'+version)
        if not source.is_dir(): raise FileNotFoundError(source)
        # Path.rglob deliberately does not follow directory symlinks in Python
        # 3.12/3.13. Use real directories and same-volume hardlinked files so
        # exact production model discovery sees the assets without duplication.
        dest=inp/slug;dest.mkdir()
        for folder,dirs,files in os.walk(source,followlinks=False):
            dirs[:]=[d for d in dirs if d!='__pycache__']
            relative=Path(folder).relative_to(source)
            target=dest/relative;target.mkdir(parents=True,exist_ok=True)
            for name in files:
                if name.endswith('.pyc'):continue
                os.link((Path(folder)/name).resolve(),target/name)
    comp=inp/'enveda-CASMI26-molecule-id-mass-spectra';comp.mkdir()
    test_columns=pq.ParquetFile(ROOT/'enveda-CASMI26-molecule-id-mass-spectra/test.parquet').schema_arrow.names
    queries=pd.read_parquet(ROOT/'runs/validation_pilot_v2_20261104/queries.parquet',columns=test_columns)
    mids=['cross_VXVNYCRICCVPTD','np_DUXQKCCELUKXOE']
    test=queries[queries.molecule_id.isin(mids)].copy()
    assert set(test.molecule_id)==set(mids)
    test.to_parquet(comp/'test.parquet',index=False)
    pd.DataFrame(dict(molecule_id=mids,smiles=['C','CC'])).to_csv(comp/'sample_submission.csv',index=False)
    (comp/'train.parquet').symlink_to(ROOT/'enveda-CASMI26-molecule-id-mass-spectra/train.parquet')
    site=RUN/'resource_site';site.mkdir()
    (site/'sitecustomize.py').write_text('import os\nos.cpu_count=lambda:4\n',encoding='utf-8')
    save(RUN/'preparation.json',dict(mode='real_production_hidden_path_local_subset',query_ids=mids,
        spectra=len(test),stage_notebook_sha256=sha(STAGE/'notebook.ipynb'),
        official_test_columns=test_columns,no_truth_loaded=True,no_reused_scores=True,no_cell_skipping=True,
        resource_adaptation='os.cpu_count returns 4 for bounded local multiprocessing',
        bind_mount_source=str(view),data_location='All inputs outputs caches on D workspace'))
    print(json.dumps(dict(status='prepared',view=str(view),queries=mids,spectra=len(test))))


def run():
    notebook=read(STAGE/'notebook.ipynb')
    expected=read(RUN/'preparation.json')['stage_notebook_sha256']
    assert sha(STAGE/'notebook.ipynb')==expected
    mount=Path('/kaggle')
    assert mount.is_mount(), 'Bind the D-backed kaggle view before running'
    assert Path('/kaggle/working').is_dir()
    expected_view=RUN/'kaggle'
    assert os.path.samefile('/kaggle/input',expected_view/'input')
    assert os.path.samefile('/kaggle/working',expected_view/'working')
    os.environ['KAGGLE_IS_COMPETITION_RERUN']='1'
    os.environ['MPLBACKEND']='Agg'
    # No pre-import of CUDA or task model. The original stage runner owns this.
    scope={'__name__':'__main__'}
    marks=[]; started=time.monotonic()
    try:
        for i,cell in enumerate(notebook['cells']):
            if cell['cell_type']!='code': continue
            text=''.join(cell['source']) if isinstance(cell['source'],list) else cell['source']
            print(f'OUTER CELL {i} START',flush=True)
            before=time.monotonic()
            exec(compile(text,f'outer_generation_cell_{i}','exec'),scope)
            marks.append(dict(cell=i,seconds=time.monotonic()-before))
            save(RUN/'progress.json',dict(status='running',last_complete=i,marks=marks,seconds=time.monotonic()-started))
            print(f'OUTER CELL {i} DONE',flush=True)
        work=Path('/kaggle/working')
        required=['batch_variant_audit.json','guarded_tail_audit.json','external_overlay_audit.json','generation_variant_audit.json']
        audits={name:read(work/name) for name in required}
        assert all(a['status']=='passed' and all(a['checks'].values()) for a in audits.values())
        assert all(a['mode']=='hidden_full' for a in audits.values())
        result=dict(status='passed_real_production_subset',seconds=time.monotonic()-started,
                    stage_notebook_sha256=expected,marks=marks,audits=audits,
                    output_sha256=sha(work/'submission.csv'),no_component_only_claim=True,
                    actual_outer_cells=len(marks),resource_adaptation='cpu_count=4',
                    limitation='Two diagnostic queries; consult preparation.json and input_schema_review.json for actual input columns. Proves production path on this subset, not clean validation, hidden efficacy or full test budget.')
        save(RUN/'verification.json',result)
        print(json.dumps(dict(status=result['status'],seconds=result['seconds'],output_sha256=result['output_sha256'])),flush=True)
    except BaseException as error:
        save(RUN/'failure.json',dict(status='failed',type=type(error).__name__,message=str(error)[:1800],
             stage_notebook_sha256=expected,marks=marks,seconds=time.monotonic()-started))
        raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare',action='store_true');p.add_argument('--tag',default='');a=p.parse_args()
    if a.tag:
        assert a.tag.isalnum(), 'Simple tag only'
        RUN=ROOT/('runs/generation_production_20261113_'+a.tag)
    prepare() if a.prepare else run()
