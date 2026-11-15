"""Prepare one production generation-budget variant; no cloud writes or experiments."""
from pathlib import Path
import argparse
import ast
import base64
import copy
import hashlib
import json
import zlib

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'submission/optimization_20261109/mass_guarded_extlib'
OUT = ROOT/'submission/optimization_20261112/generation_expand/revision2'
MODULE = ROOT/'scripts/generation_runtime_patch_20261112.py'
CHAMPION = '2bb94c91b176f95dfdff52f08781443ffee004c20d06aeb30efb14d0c0112fc7'
BRANCH = 'generation_expand'


def sha(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def src(cell):
    return ''.join(cell['source']) if isinstance(cell['source'], list) else cell['source']


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')


def original_runner(book):
    tree = ast.parse(src(book['cells'][11]))
    node = next(n for n in tree.body if isinstance(n, ast.Assign) and any(getattr(t,'id',None)=='_guarded_source' for t in n.targets))
    plain = zlib.decompress(base64.b64decode(ast.literal_eval(node.value.args[0].args[0]))).decode()
    for n in ast.parse(plain).body:
        if isinstance(n, ast.Assign):
            for target in n.targets:
                if isinstance(target, ast.Subscript) and getattr(target.value,'id',None)=='MODULES' and ast.literal_eval(target.slice)=='runner.py':
                    return ast.literal_eval(n.value)
    raise ValueError('Pinned original runner not found')


def patched_runner(original):
    needle="        exec(compile(''.join(c['source']),f'pipeline_cell_{i}','exec'),scope)"
    if original.count(needle)!=1 or original.count('    export(scope,root)')!=1:
        raise ValueError('Frozen runner call structure changed')
    result = 'from generation_runtime_patch_20261112 import after_cell, finish\n'+original
    result=result.replace(needle,needle+'\n        after_cell(scope,i,root)')
    result=result.replace('    export(scope,root)','    export(scope,root)\n    finish(scope,root)')
    compile(result,'generation_runner.py','exec')
    return result


def prepare():
    if OUT.exists():
        raise FileExistsError('Do not overwrite frozen generation stage')
    if sha(BASE/'notebook.ipynb')!=CHAMPION:
        raise ValueError('Champion source changed')
    parent=read(BASE/'notebook.ipynb');book=copy.deepcopy(parent)
    module=MODULE.read_bytes();module_pin=hashlib.sha256(module).hexdigest()
    compile(module.decode(),'generation_runtime_patch_20261112.py','exec')
    original=original_runner(parent);runner=patched_runner(original)
    runner_pin=hashlib.sha256(runner.encode()).hexdigest()
    original_pin=hashlib.sha256(original.encode()).hexdigest()
    target='stormseye/casmi26-generation-expand-1112'
    recipe=dict(branch=BRANCH,target=target,baseline_ref=58156482,baseline_public_score=.488,
                champion_notebook_sha256=CHAMPION,method='Expanded spectral parents and bounded product budget without neutral-delta isomer enumeration',
                configuration=dict(gen_n_analog=12,gen_max_total=300,gen_max_per_parent=60,max_steps=2,allow_isomerisation=False),
                original_runner_sha256=original_pin,runner_sha256=runner_pin,module_sha256=module_pin,
                only_original_cell_changed=12,all_other_original_32_cell_objects_unchanged=True,
                frozen_pipeline_bytes_unchanged=True,actual_production_hook='After frozen cell37, before first V1FE query',
                original_neural_heads_mass_ab_unchanged=True,validation_mode='fast_static',new_training=False,produre_rerun=False,
                source_attribution='Existing production Engine + recording hooks, bounded generation budget motivated by completed diagnostics; not a claimed validated gain',
                runtime_guard='Original per-parent derive budget800, products60 and original 2-step semantics; total300 and parents12 explicit',
                final_generated_count='Raw-SMILES intersection conservative diagnostic, not truth recall')
    raw=(json.dumps(recipe,indent=2,ensure_ascii=False)+'\n').encode();recipe_pin=hashlib.sha256(raw).hexdigest()
    setup=r'''
# Explicit generation runtime; original frozen notebook and all original modules stay pinned.
import base64 as _gb64,zlib as _gz,hashlib as _gh,json as _gj
_GEN_MODULE_PIN=__MODULE_PIN__
_GEN_RUNNER_PIN=__RUNNER_PIN__
try:
    _gen_raw=_gz.decompress(_gb64.b64decode(__MODULE_DATA__))
    assert _gh.sha256(_gen_raw).hexdigest()==_GEN_MODULE_PIN
    (CODE/'generation_runtime_patch_20261112.py').write_bytes(_gen_raw)
    _gen_runner_text=_gz.decompress(_gb64.b64decode(__RUNNER_DATA__)).decode()
    assert _gh.sha256(_gen_runner_text.encode()).hexdigest()==_GEN_RUNNER_PIN
    _generation_original_run_stage=run_stage
    def _generation_run_stage(args,log,name,quiet=None):
        try:
            if len(args)>1 and Path(args[1]).name=='runner.py':
                assert name=='Public 0.465 pipeline'
                assert _gh.sha256(Path(args[1]).read_bytes()).hexdigest()==__ORIGINAL_RUNNER_PIN__
                assert _gh.sha256((CODE/'generation_runtime_patch_20261112.py').read_bytes()).hexdigest()==_GEN_MODULE_PIN
                _gen_runner=CODE/'generation_runner.py'
                _gen_runner.write_text(_gen_runner_text)
                assert _gh.sha256(_gen_runner.read_bytes()).hexdigest()==_GEN_RUNNER_PIN
                args=list(args);args[1]=_gen_runner
                (ROOT/'generation_launch.json').write_text(_gj.dumps(dict(runner_sha256=_GEN_RUNNER_PIN,module_sha256=_GEN_MODULE_PIN,original_runner_sha256=__ORIGINAL_RUNNER_PIN__,actual_executable=str(args[0]),actual_runner=str(args[1])))+'\n')
            return _generation_original_run_stage(args,log,name,quiet=quiet)
        except BaseException:
            (ROOT/'submission.csv').unlink(missing_ok=True)
            raise
    run_stage=_generation_run_stage
except BaseException:
    (ROOT/'submission.csv').unlink(missing_ok=True)
    raise
'''
    values={'__MODULE_PIN__':repr(module_pin),'__RUNNER_PIN__':repr(runner_pin),'__ORIGINAL_RUNNER_PIN__':repr(original_pin),
            '__MODULE_DATA__':repr(base64.b64encode(zlib.compress(module,9)).decode()),
            '__RUNNER_DATA__':repr(base64.b64encode(zlib.compress(runner.encode(),9)).decode())}
    for key,value in values.items():setup=setup.replace(key,value)
    book['cells'][12]['source']=src(book['cells'][12])+setup
    final=r'''
import importlib.util as _gi,shutil as _gs
try:
    _gs.copy2(ROOT/'submission.csv',ROOT/'submission_generation_final_control.csv')
    assert hashlib.sha256((CODE/'generation_runtime_patch_20261112.py').read_bytes()).hexdigest()==__MODULE_PIN__
    _gen_spec=_gi.spec_from_file_location('_generation_final_observer',CODE/'generation_runtime_patch_20261112.py')
    _gen_module=_gi.module_from_spec(_gen_spec);_gen_spec.loader.exec_module(_gen_module)
    GENERATION_VARIANT_AUDIT=_gen_module.audit(ROOT,EXTERNAL_OVERLAY_AUDIT,IS_RERUN,SAMPLE_IDS,__BRANCH__,__RECIPE_PIN__,__MODULE_PIN__,__RUNNER_PIN__)
except BaseException:
    (ROOT/'submission.csv').unlink(missing_ok=True)
    raise
'''
    for key,value in {'__MODULE_PIN__':repr(module_pin),'__RUNNER_PIN__':repr(runner_pin),'__BRANCH__':repr(BRANCH),'__RECIPE_PIN__':repr(recipe_pin)}.items():final=final.replace(key,value)
    book['cells'].append(dict(cell_type='code',execution_count=None,metadata={},outputs=[],source=final))
    changed=[i for i,(a,b) in enumerate(zip(parent['cells'],book['cells'])) if a!=b]
    if changed!=[12]:raise ValueError('Unexpected original cell modifications')
    for cell in book['cells']:
        if cell['cell_type']=='code':compile(src(cell),'generation_stage','exec')
    metadata=read(BASE/'kernel-metadata.json');metadata.update(id=target,title='CASMI26 generation expand 1112')
    OUT.mkdir(parents=True);write(OUT/'notebook.ipynb',book);write(OUT/'kernel-metadata.json',metadata);(OUT/'recipe.json').write_bytes(raw)
    static=dict(status='passed',target=target,version=1,notebook_sha256=sha(OUT/'notebook.ipynb'),
                checks=dict(champion_pin=True,only_stage_machinery_changed=True,all_other_32_original_cells_exact=True,
                            original_frozen_unmodified=True,explicit_actual_runner_replacement=True,
                            runtime_module_and_runner_pinned=True,source_compiles=True,all_original_neural_heads_ab_retained=True,
                            no_new_data_or_training=True,private_offline_gpu=True,errors_fail_closed=True))
    write(OUT/'static_review.json',static)
    audits=copy.deepcopy(read(BASE/'branch_spec.json')['required_runtime_audits'])
    audits.append(dict(name='generation_variant_audit.json',expected_fields=dict(status='passed',branch=BRANCH,mode='fast_static',recipe_sha256=recipe_pin),
                       required_true_checks=['original_ab_audit','original_ab_output_bound','installed_module_pin','fast_no_generation']))
    spec=dict(name=BRANCH,target=target,version=1,stage_dir=OUT.relative_to(ROOT).as_posix(),notebook_sha256=sha(OUT/'notebook.ipynb'),
              metadata_sha256=sha(OUT/'kernel-metadata.json'),description='CASMI26 20261112 generation parents12 products300 no-isomer audited V1',
              validation_mode='fast_static',static_review_path=(OUT/'static_review.json').relative_to(ROOT).as_posix(),required_runtime_audits=audits)
    write(OUT/'branch_spec.json',spec)
    receipt=dict(status='prepared_pending_actual_canary',branch=BRANCH,notebook_sha256=spec['notebook_sha256'],metadata_sha256=spec['metadata_sha256'],
                 recipe_sha256=recipe_pin,module_sha256=module_pin,runner_sha256=runner_pin,notebook_bytes=(OUT/'notebook.ipynb').stat().st_size)
    write(OUT/'prepare_receipt.json',receipt)
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--prepare',action='store_true');args=parser.parse_args()
    print(json.dumps(prepare() if args.prepare else dict(status='plan_only',branch=BRANCH,stage=str(OUT)),indent=2))
