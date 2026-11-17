"""Execute frozen champion inner source with declared diagnostic-only hooks."""
from pathlib import Path
import hashlib
import json
import os
import sys
import time

PROJECT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT));sys.path.insert(0,str(PROJECT/'scripts'))
from IPython.display import display
import champion_stage_observer_20261115 as observer
import champion_reference_masks_20261115 as masks

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def patch_engine2_observer(path,root,config_path):
    path=Path(path);text=path.read_text();marker='    subs, recs, S = E.main('
    if text.count(marker)!=1:raise ValueError('E2 observer marker changed')
    hook='    from champion_stage_observer_20261115 import install_engine2 as _champion_e2_observer\n    _champion_e2_observer(E, '+repr(str(root))+')\n'
    hook+='    from validation.e2_resources import install as _champion_e2_resources\n    _champion_e2_resources(E, '+repr(str(config_path))+',worker_limit=1)\n'+marker
    text=text.replace(marker,hook,1);compile(text,str(path),'exec');path.write_text(text)

if __name__=='__main__':
    source=Path(sys.argv[1]);expected=sys.argv[2];root=Path(sys.argv[3]).resolve()
    if sha(source)!=expected:raise ValueError('Frozen champion inner bytes changed')
    sys.path.insert(0,str(source.parent.resolve()))
    cfgpath=Path(os.environ['CASMI_CHAMPION_DIAGNOSTIC_CONFIG']);cfg=json.loads(cfgpath.read_text())
    if not os.path.samefile(root,cfg['work_root']):raise ValueError('Diagnostic work-root mismatch')
    if (root/'work/spec_meta.parquet').exists() or (root/'submission.csv').exists():raise FileExistsError('Fresh inner initialization required')
    os.chdir(root);scope={'__name__':'__main__','display':display};adaptations=[];started=time.monotonic()
    for i,c in enumerate(json.loads(source.read_text())['cells']):
        if c['cell_type']!='code':continue
        text=''.join(c['source']) if isinstance(c['source'],list) else c['source']
        original_pin=hashlib.sha256(text.encode()).hexdigest();changes=[]
        if 'ENG_FILES = ' in text:
            marker='ENG = {}'
            if text.count(marker)!=1:raise ValueError('Generated E2 installation moved')
            injected='from champion_reference_masks_20261115 import patch_generated_e2\npatch_generated_e2(os.path.join(ENG_DIR,"eng_runner.py"),'+repr(str(cfgpath))+')\n'
            injected+='from replay_champion_inner_20261115 import patch_engine2_observer\npatch_engine2_observer(os.path.join(ENG_DIR,"eng_runner.py"),'+repr(str(root))+','+repr(str(cfgpath))+')\n'
            injected+='from pathlib import Path as _champion_Path\n_champion_e2_path=_champion_Path(ENG_DIR)/"eng_runner.py"\n_champion_e2_text=_champion_e2_path.read_text()\nassert _champion_e2_text.count("workers=os.cpu_count()")==1\n_champion_e2_text=_champion_e2_text.replace("workers=os.cpu_count()",'+repr('workers='+str(cfg.get('e2_workers',1)))+',1)\n_champion_e2_path.write_text(_champion_e2_text)\n'
            text=text.replace(marker,injected+marker,1)
            changes.append('E2 reference masking and full candidate observations')
            changes.append('Explicit bounded E2 worker count '+str(cfg.get('e2_workers',1)))
        if 'PC = {}' in text and 'pc_runner.py' in text:
            marker='PC = {}'
            if text.count(marker)!=1:raise ValueError('Generated PubChem installation moved')
            text=text.replace(marker,'from champion_reference_masks_20261115 import patch_generated_pubchem\npatch_generated_pubchem("/kaggle/working/pc_runner.py",'+repr(str(cfgpath))+')\n'+marker,1)
            changes.append('PubChem static candidate observations/isolation')
        if 'from casmi.build import build_spec_cache' in text:
            marker='from casmi.build import build_spec_cache'
            if text.count(marker)!=1:raise ValueError('Shared-cache installation moved')
            injected='from reproduction_io import install_shared_cache\ninstall_shared_cache(V4CODE,'+repr(cfg['shared_spec_cache'])+',mmap_pool=True)\nfrom champion_reference_masks_20261115 import install_e1\ninstall_e1(V4CODE,'+repr(str(cfgpath))+')\n'
            text=text.replace(marker,injected+marker,1);changes.append('Verified shared cache and E1 reference masking')
        observer.before_cell(scope,i,root)
        if changes:
            adaptations.append(dict(cell=i,changes=changes,original_source_sha256=original_pin,executed_source_sha256=hashlib.sha256(text.encode()).hexdigest()))
            (root/'champion_inner_adaptations.json').write_text(json.dumps(adaptations,indent=2)+'\n')
        print('PIPELINE CELL',i,'START',flush=True)
        if i in (32,34):scope.pop('rr',None)
        exec(compile(text,f'champion_inner_cell_{i}','exec'),scope)
        if i in (32,34):
            stage='engine2' if i==32 else 'pubchem';process=scope.get('rr')
            for stream in ('stdout','stderr'):
                (root/(stage+'_'+stream+'.log')).write_text(getattr(process,stream,'') or '')
            (root/(stage+'_process.json')).write_text(json.dumps(dict(returncode=getattr(process,'returncode',None)),indent=2)+'\n')
            if process is None or process.returncode!=0:raise RuntimeError(stage+' failed; inspect full stdout/stderr and returncode')
            actual=scope.get('ENG' if i==32 else 'PC',{})
            if set(map(str,actual))!=set(cfg['active_ids']):raise RuntimeError(stage+' silently skipped query IDs')
        observer.after_cell(scope,i,root)
        print('PIPELINE CELL',i,'DONE',flush=True)
    if 'candidate_promotion_evidence' not in scope:raise ValueError('Original source promotion fix missing')
    from export_evidence import export
    export(scope,root);observer.finish(scope,root)
    (root/'execution_receipt.json').write_text(json.dumps(dict(source_sha256=expected,mode='diagnostic',
        source_adaptations=adaptations,candidate_promotion_fix=True,is_full_run=bool(scope['IS_RERUN']),
        processed_molecules=int(scope['te'].molecule_id.nunique()),seconds=time.monotonic()-started,
        source_bytes_unchanged=True,changed_model_weights=False,reference_mode=cfg['reference_mode']),indent=2)+'\n')
