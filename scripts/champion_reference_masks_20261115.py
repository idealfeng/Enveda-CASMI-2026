"""Runtime-only isolation for the frozen .488 champion diagnostic.

Shared assets and frozen notebooks are never edited here. Hooks operate on
generated copies and in-memory indexes. Labels are control metadata for masks,
never ranker features. Model execution belongs to the outer runner.
"""
from __future__ import annotations
import ast
import csv
from collections import Counter
from functools import lru_cache
import hashlib
import importlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]

def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

@lru_cache(maxsize=32)
def config(path):
    c=json.loads(Path(path).read_text(encoding='utf-8'))
    if c['reference_mode'] not in ('class1','class2','class3'):raise ValueError('Unknown reference condition')
    if not c.get('work_root'):raise ValueError('Explicit work_root required')
    return c

def record(c,name,value):
    out=Path(c['work_root'])/name;out.parent.mkdir(parents=True,exist_ok=True)
    tmp=out.with_suffix(out.suffix+'.tmp')
    tmp.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8');tmp.replace(out)

def adapter_config(path):
    """Existing adapter has C1/C2; C3 uses C2 reference mask plus new pool hooks."""
    c=config(path); derived=dict(c)
    if c['reference_mode']=='class3':derived['reference_mode']='class2'
    derived.setdefault('pipeline','champion0488')
    target=Path(c['work_root'])/'champion_adapter_reference_config.json'
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(derived,indent=2)+'\n',encoding='utf-8')
    return target

@lru_cache(maxsize=16)
def blocked(path):
    c=config(path)
    if c['reference_mode']=='class1':return frozenset()
    keys=c.get('blocked_official_identities')
    if keys is None:
        keys=json.loads(Path(c['exclusion_keys_file']).read_text())['blocked_official_identities']
    if not keys:raise ValueError('C2/C3 requires nonempty complete official identity exclusions')
    return frozenset(keys)

def official_identity(smiles):
    from validation.metric import identity
    return identity(str(smiles))

@lru_cache(maxsize=200000)
def _official_cached(smiles):return official_identity(smiles)

@lru_cache(maxsize=16)
def _blocked_compositions(path):
    """Safe optional accelerator from explicit label-side control metadata."""
    from validation.metric import heavy_atom_composition
    c=config(path);ids=blocked(path)
    truth_path=Path(c.get('truth_control_file',Path(c['exclusion_keys_file']).parent/'truth.csv'))
    if not truth_path.is_file():return None
    with truth_path.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    found={r['official_identity'] for r in rows if r['official_identity'] in ids}
    if found!=set(ids):return None
    comps={heavy_atom_composition(r['smiles']) for r in rows if r['official_identity'] in ids}
    return frozenset(comps) if None not in comps else None

def target_identity_match(smiles,path):
    from validation.metric import heavy_atom_composition
    ids=blocked(str(path))
    if not ids:return False
    comps=_blocked_compositions(str(path))
    if comps is not None and heavy_atom_composition(str(smiles)) not in comps:return False
    return _official_cached(str(smiles)) in ids

def static_keep(smiles,path):
    """C1/C2 keep every original candidate; C3 hides every official alias."""
    c=config(path)
    return c['reference_mode']!='class3' or not target_identity_match(smiles,path)

def filter_static_smiles(smiles,path,source='unspecified'):
    c=config(path); values=list(smiles)
    out=[s for s in values if static_keep(s,path)]
    record(c,'champion_static_'+source.lower()+'_last.json',dict(status='filtered' if c['reference_mode']=='class3' else 'unchanged',source=source,input=len(values),kept=len(out),removed=len(values)-len(out),official_identity=True,generated_products_filtered=False))
    return out

def install_e1(code_root,config_path):
    from validation import pipeline_adapter as a
    import numpy as np
    c=config(config_path); derived=adapter_config(config_path)
    result=a.install_e1(code_root,derived)
    if c['reference_mode']=='class3':
        poolmod=importlib.import_module('casmi.pool')
        original=poolmod.Pool.window
        if getattr(poolmod.Pool,'_champion_static_mask',False):raise RuntimeError('E1 pool hook installed twice')
        def window(self,target,ppm):
            ids=original(self,target,ppm)
            keep=np.asarray([static_keep(self.smiles[int(i)],config_path) for i in ids],dtype=bool)
            out=ids[keep]
            record(c,'champion_e1_static_window_last.json',dict(status='filtered',input=len(ids),kept=len(out),removed=int((~keep).sum()),pid_coordinates_preserved=True,generation_recovery_allowed=True))
            return out
        poolmod.Pool.window=window;poolmod.Pool._champion_static_mask=True
    record(c,'champion_e1_mask_install.json',dict(status='installed',reference_mode=c['reference_mode'],reference_adapter_config_sha256=sha(derived),all_alias_reference_mask='precomputed complete official identity-family exclusions',static_pool_filtered=c['reference_mode']=='class3',source_script_sha256=sha(__file__)))
    return result

def install_e2(engine,config_path):
    from validation import pipeline_adapter as a
    import numpy as np
    c=config(config_path);a.install_e2(engine,adapter_config(config_path))
    if c['reference_mode']=='class3':
        original=engine.pool_window
        def window(target,ppm):
            ids=original(target,ppm)
            keep=np.asarray([static_keep(engine.POOL['smiles'][int(i)],config_path) for i in ids],dtype=bool)
            out=ids[keep]
            record(c,'champion_e2_static_window_last.json',dict(status='filtered',input=len(ids),kept=len(out),removed=int((~keep).sum()),pid_coordinates_preserved=True))
            return out
        engine.pool_window=window
    record(c,'champion_e2_mask_install.json',dict(status='installed',reference_mode=c['reference_mode'],static_pool_filtered=c['reference_mode']=='class3',source_script_sha256=sha(__file__)))

def patch_generated_e2(path,config_path):
    """Reuse existing source marker checks, then route its install into this module."""
    from validation import pipeline_adapter as a
    c=config(config_path); path=Path(path); before=sha(path)
    a.patch_generated_e2(path,adapter_config(config_path))
    text=path.read_text(encoding='utf-8')
    old='    from validation.pipeline_adapter import install_e2'
    if text.count(old)!=1:raise ValueError('Unexpected E2 adapter marker count')
    text=text.replace(old,'    from scripts.champion_reference_masks_20261115 import install_e2',1)
    # The original path argument was the derived C2 reference config. Our hook
    # needs the declared C3 mode, and itself derives C2 only for reference masks.
    oldcall=f'    install_e2(E, {str(adapter_config(config_path))!r})'
    if text.count(oldcall)!=1:raise ValueError('Unexpected E2 install call count')
    text=text.replace(oldcall,f'    install_e2(E, {str(config_path)!r})',1)
    ast.parse(text);path.write_text(text,encoding='utf-8')
    record(c,'champion_e2_generated_patch.json',dict(status='patched_generated_copy',before_sha256=before,after_sha256=sha(path),reference_mode=c['reference_mode'],no_model_execution=True))

def install_pubchem(pc,config_path):
    """Filter complete emitted tier windows, including all aligned prior arrays."""
    import numpy as np
    c=config(config_path)
    if c['reference_mode']!='class3':
        record(c,'champion_pubchem_mask_install.json',dict(status='installed_no_static_filter',reference_mode=c['reference_mode']))
        return
    if sys.platform=='win32':raise RuntimeError('C3 PubChem wrapper requires the declared Linux fork runner')
    if getattr(pc,'_champion_static_mask',False):raise RuntimeError('PubChem hook installed twice')
    if not hasattr(pc,'_window_bundle'):raise RuntimeError('Unsupported PubChem source: complete window bundle missing')
    original=pc._window_bundle
    def window(target):
        smis,priors=original(target)
        keep=np.asarray([static_keep(s,config_path) for s in smis],dtype=bool)
        if not all(len(v)==len(smis) for v in priors.values()):raise ValueError('PubChem prior alignment changed')
        filtered=[s for s,k in zip(smis,keep) if k]
        # Multiple fork workers write separate audit files, never shared temp.
        import os
        record(c,'champion_pubchem_window_pid'+str(os.getpid())+'_last.json',dict(status='filtered',input=len(smis),kept=len(filtered),removed=int((~keep).sum()),all_store_priors_row_aligned=True))
        return filtered,{k:np.asarray(v)[keep] for k,v in priors.items()}
    pc._window_bundle=window;pc._champion_static_mask=True
    record(c,'champion_pubchem_mask_install.json',dict(status='installed',reference_mode=c['reference_mode'],all_static_window_stores_filtered=True,fork_required=True))

@lru_cache(maxsize=2)
def _pool_smiles(path):
    import pyarrow.parquet as pq
    return pq.read_table(path,columns=['smiles']).column('smiles').to_pylist()

def pubchem_pool_indices(a,b,pool_meta_path,config_path):
    import numpy as np
    ids=np.arange(a,b,dtype=np.int64)
    if config(config_path)['reference_mode']!='class3':return ids
    smis=_pool_smiles(str(pool_meta_path))
    return ids[np.asarray([static_keep(smis[int(i)],config_path) for i in ids],dtype=bool)]

def patch_generated_pubchem(path,config_path):
    c=config(config_path);path=Path(path);before=sha(path);text=path.read_text(encoding='utf-8')
    marker='    import probe_core2 as pc'
    if text.count(marker)!=1:raise ValueError('Unexpected PubChem import marker count')
    hook=(marker+f'\n    sys.path.insert(0, {str(ROOT)!r})\n'
          '    from scripts.champion_reference_masks_20261115 import install_pubchem, pubchem_pool_indices\n'
          f'    install_pubchem(pc, {str(config_path)!r})')
    text=text.replace(marker,hook,1)
    if c['reference_mode']=='class3':
        marker='        if b > a:\n            F = np.unpackbits(np.asarray(pfp[a:b]), axis=1)[:, :nbits].astype(np.float64)'
        replacement=(f'        _champion_pool_ids = pubchem_pool_indices(a,b,os.path.join(POOL_DIR, "pool_meta.parquet"), {str(config_path)!r})\n'
                     '        if len(_champion_pool_ids):\n            F = np.unpackbits(np.asarray(pfp[_champion_pool_ids]), axis=1)[:, :nbits].astype(np.float64)')
        if text.count(marker)!=1:raise ValueError('Unexpected PubChem best_pool_fz window marker count')
        text=text.replace(marker,replacement,1)
    ast.parse(text);path.write_text(text,encoding='utf-8')
    record(c,'champion_pubchem_generated_patch.json',dict(status='patched_generated_copy',before_sha256=before,after_sha256=sha(path),reference_mode=c['reference_mode'],best_pool_fz_window_filtered=c['reference_mode']=='class3',no_model_execution=True))

def patch_outer_static_cell(text,config_path):
    """Runner calls on outer cell20 only; block separate LOTUS candidate backfill."""
    c=config(config_path)
    if c['reference_mode']!='class3':return text
    old='lotus_by_mid[_mid] = _l_smiles[_lo:_hi].tolist()'
    if text.count(old)!=1:raise RuntimeError('C3 LOTUS source marker not covered; refuse incomplete C3')
    before=hashlib.sha256(text.encode()).hexdigest()
    prefix=f'from scripts.champion_reference_masks_20261115 import filter_static_smiles as _champion_static_smiles\n'
    text=prefix+text.replace(old,f'lotus_by_mid[_mid] = _champion_static_smiles(_l_smiles[_lo:_hi].tolist(), {str(config_path)!r}, source="LOTUS")',1)
    ast.parse(text)
    record(c,'champion_lotus_patch.json',dict(status='patched_execution_text',before_sha256=before,after_sha256=hashlib.sha256(text.encode()).hexdigest(),generated_products_filtered=False))
    return text

def _content_signatures(mz,it,prec,mode):
    """Same explicit float32/quantized C-pilot representations, not acquisition IDs."""
    import numpy as np
    m=np.asarray(mz,dtype=np.float64);v=np.asarray(it,dtype=np.float64)
    ok=np.isfinite(m)&np.isfinite(v)&(m>0)&(v>0);m,v=m[ok],v[ok]
    if not len(m):return ()
    order=np.argsort(m,kind='stable');m,v=m[order],v[order];v=v/v.max()
    h=hashlib.blake2b(digest_size=16);h.update(str(mode).encode());h.update(np.asarray([prec],dtype='<f4').tobytes());h.update(np.column_stack((m.astype('<f4'),v.astype('<f4'))).astype('<f4',copy=False).tobytes());exact=h.digest()
    if len(m)>128:
        use=np.sort(np.argsort(-v,kind='stable')[:128]);m,v=m[use],v[use]
    h=hashlib.blake2b(digest_size=16);h.update(str(mode).encode());h.update(np.asarray([round(prec,3)],dtype='<f4').tobytes());h.update(np.column_stack((np.rint(m*10000),np.rint(v*100000))).astype('<i8').tobytes())
    return exact,h.digest()

def install_ab_observer_filter(config_path,helper_module):
    """Retain original AB math/observer, reject refs BEFORE refs.append/indexing."""
    import numpy as np
    import pyarrow.parquet as pq
    c=config(config_path);ids=blocked(str(config_path));stats=Counter()
    qpath=c.get('inference_queries_file',c['queries_file'])
    q=pq.read_table(qpath,columns=['precursor_mz','ionization_mode','ms2_mzs','ms2_normalized_intensities']).to_pydict()
    signatures=set()
    for i,prec in enumerate(q['precursor_mz']):
        mz=np.asarray(q['ms2_mzs'][i],dtype=float);it=np.asarray(q['ms2_normalized_intensities'][i],dtype=float)
        ok=(mz>0)&(it>0)&(mz<=float(prec)+.5)
        mode=1 if 'pos' in str(q['ionization_mode'][i]).lower() else -1
        signatures.update(_content_signatures(mz[ok],it[ok],float(prec),mode))
    class Filter(ast.NodeTransformer):
        def __init__(self):self.sites=0
        def visit_Expr(self,node):
            node=self.generic_visit(node);call=node.value
            if isinstance(call,ast.Call) and isinstance(call.func,ast.Attribute) and isinstance(call.func.value,ast.Name) and call.func.value.id=='refs' and call.func.attr=='append':
                self.sites+=1;label='A' if any(isinstance(x,ast.Name) and x.id=='key' for x in ast.walk(call.args[0])) else 'B'
                check=ast.If(test=ast.UnaryOp(op=ast.Not(),operand=ast.Call(func=ast.Name(id='_champion_allow_ref',ctx=ast.Load()),args=[ast.Constant(label),call.args[0]],keywords=[])),body=[ast.Continue()],orelse=[])
                return [ast.copy_location(check,node),node]
            return node
    def allow(label,row):
        stats[label+'_considered']+=1
        if any(s in signatures for s in _content_signatures(row[2],row[3],float(row[1]),int(row[0]))):
            stats[label+'_query_content_removed']+=1;return False
        if ids and target_identity_match(row[5],config_path):
            stats[label+'_target_identity_removed']+=1;return False
        stats[label+'_kept']+=1;return True
    def load_observed(source_path,source_sha,reference,match):
        if sha(source_path)!=source_sha:raise ValueError('Original AB source changed')
        tree=ast.parse(Path(source_path).read_text(encoding='utf-8'))
        if len(tree.body)!=1 or not isinstance(tree.body[0],ast.FunctionDef) or tree.body[0].name!='_apex_extlib_overlay':raise ValueError('Unexpected AB function')
        f=Filter();tree=f.visit(tree)
        if f.sites!=2:raise ValueError('Unexpected AB reference filter count')
        obs=helper_module.Observe();tree=obs.visit(tree);ast.fix_missing_locations(tree)
        if (obs.reference_sites,obs.match_sites)!=(2,1):raise ValueError('Original AB observation sites changed')
        scope=dict(_champion_allow_ref=allow,_observe_reference=reference,_observe_match=match)
        exec(compile(tree,'champion_isolated_original_AB','exec'),scope)
        fn=scope['_apex_extlib_overlay']
        def run(*args,**kwargs):
            try:return fn(*args,**kwargs)
            finally:record(c,'champion_AB_reference_mask.json',dict(status='runtime_reference_filter_observed',reference_mode=c['reference_mode'],counters=dict(stats),query_signature_count=len(signatures),no_reference_spectrum_ID_claim=True,content_signature_limitation='Equality at declared float32/quantized representation; unmatched is not proof of independent acquisition. B retains production synthetic precursor.'))
        return run,dict(reference_sites=2,match_sites=1)
    if getattr(helper_module,'_champion_mask_installed',False):raise RuntimeError('AB hook installed twice')
    helper_module.load_observed=load_observed;helper_module._champion_mask_installed=True
    record(c,'champion_AB_mask_install.json',dict(status='installed',reference_mode=c['reference_mode'],all_A_B_references_filtered_before_index=True,query_signature_count=len(signatures),source_script_sha256=sha(__file__)))

def assert_installation_complete(config_path):
    """Runner invokes after outer pipeline; partial C3 is never called complete."""
    c=config(config_path);root=Path(c['work_root'])
    required=['champion_e1_mask_install.json','champion_e2_mask_install.json','champion_pubchem_mask_install.json','champion_AB_mask_install.json','champion_AB_reference_mask.json','validation_e1_reference_audit.json','validation_e2_reference_audit.json']
    if c['reference_mode']=='class3':required+=['champion_lotus_patch.json','champion_e1_static_window_last.json','champion_e2_static_window_last.json']
    missing=[name for name in required if not (root/name).is_file()]
    if missing:raise RuntimeError('Incomplete champion isolation evidence: '+repr(missing))
    return dict(status='installation_evidence_present',reference_mode=c['reference_mode'],required=required,source_script_sha256=sha(__file__),not_a_prediction_or_accuracy_check=True)
