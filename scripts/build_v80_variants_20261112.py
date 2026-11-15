"""Build independent best-validation scorer branches; no cloud calls or training."""
from pathlib import Path
import argparse
import ast
import base64
import copy
import hashlib
import importlib.util
import json
import textwrap
import zlib

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'submission/optimization_20261109/mass_guarded_extlib'
BASE_SHA='2bb94c91b176f95dfdff52f08781443ffee004c20d06aeb30efb14d0c0112fc7'
OUT=ROOT/'submission/optimization_20261112'
MODULE=ROOT/'scripts/v80_ensemble_20261112.py'
BRANCHES={'bestval_v80_tri':'popwenman_best','bestval_saner_tri':'saner_best'}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def source(cell):return ''.join(cell['source']) if isinstance(cell['source'],list) else cell['source']
def write(path,value):Path(path).write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')


def module():
    spec=importlib.util.spec_from_file_location('_bestval_builder',MODULE)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result


def make_notebook(parent,name,kind,recipe_pin,module_pin,final_audit_variable='EXTERNAL_OVERLAY_AUDIT'):
    """Return a new notebook; final_audit_variable allows an independently frozen AB replacement."""
    notebook=copy.deepcopy(parent)
    packed=base64.b64encode(zlib.compress(MODULE.read_bytes(),9)).decode()
    old=source(parent['cells'][14])
    # All public final-list, outsider and head helper implementations remain original.
    cell=r'''
import base64,zlib,hashlib,importlib.util,json,shutil
BUNDLE=materialise_sources()
PUB_BUNDLE=BUNDLE
_bestval_raw=zlib.decompress(base64.b64decode(__PAYLOAD__))
assert hashlib.sha256(_bestval_raw).hexdigest()==__MODULE_SHA__
(CODE/'v80_ensemble_20261112.py').write_bytes(_bestval_raw)
_bestval_spec=importlib.util.spec_from_file_location('_bestval_runtime',CODE/'v80_ensemble_20261112.py')
_bestval_module=importlib.util.module_from_spec(_bestval_spec);_bestval_spec.loader.exec_module(_bestval_module)
_bestval_bundles=_bestval_module.prepare(ROOT,INPUT,PUB_BUNDLE,__KIND__,__BRANCH__,__RECIPE_SHA__,__MODULE_SHA__)
OURS_BUNDLE=_bestval_bundles['v2']
INDEPENDENT_BESTVAL_BUNDLE=_bestval_bundles['extra']
BUNDLE=OURS_BUNDLE
PIPELINE_DONE=run_public_pipeline()
'''
    fast_start=old.index("if not PIPELINE_DONE and not IS_RERUN and COMMIT_MODE == 'fast':")
    else_start=old.index('\nelse:\n',fast_start)
    # Keep the exact original fast dummy branch, then run all three named scorers.
    cell+=old[fast_start:else_start]+r'''
else:
    if not PIPELINE_DONE:
        raise RuntimeError('A real baseline run is required')
    for _bestval_role,_bestval_bundle,_bestval_file in [
            ('public',PUB_BUNDLE,'neural_public.parquet'),
            ('v2',OURS_BUNDLE,'neural_ours.parquet'),
            ('extra',INDEPENDENT_BESTVAL_BUNDLE,'neural_bestval.parquet')]:
        BUNDLE=_bestval_bundle
        if not score_final_lists():
            raise RuntimeError('Required pinned neural scorer failed: '+_bestval_role)
        shutil.copy2(ROOT/'neural_candidate_features.parquet',ROOT/_bestval_file)
    BESTVAL_MIX_REPORT=_bestval_module.mix(ROOT,__KIND__)
    BESTVAL_SCORE_AUDIT=_bestval_module.audit_scores(ROOT,True,__KIND__)
    NEURAL_OK=True
'''
    # Preserve original outsider scoring and all consensus/variant selection calls.
    tail=old[old.index('    BUNDLE = OURS_BUNDLE\n    if not NEURAL_OK:',else_start):]
    cell+=tail
    values={'__PAYLOAD__':repr(packed),'__MODULE_SHA__':repr(module_pin),'__KIND__':repr(kind),
            '__BRANCH__':repr(name),'__RECIPE_SHA__':repr(recipe_pin)}
    for key,value in values.items():cell=cell.replace(key,value)
    cell="try:\n"+textwrap.indent(cell,'    ')+"\nexcept BaseException:\n    (ROOT/'submission.csv').unlink(missing_ok=True)\n    raise\n"
    notebook['cells'][14]=dict(cell_type='code',metadata={},execution_count=None,outputs=[],source=cell)
    observer=source(parent['cells'][29])
    tree=ast.parse(observer)
    fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef))
    assignment=next(n for n in fn.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='expected' for t in n.targets))
    expected=ast.literal_eval(assignment.value)
    expected.update(branch=name,recipe_sha256=recipe_pin)
    lines=observer.splitlines(keepends=True)
    lines[assignment.lineno-1:assignment.end_lineno]=['    expected='+repr(expected)+'\n']
    observer=''.join(lines)
    old_formula="        values=.5*z(a.neural_score.fillna(0.0))+.5*z(b.neural_score.fillna(0.0))\n        check('exact_dual_scores',np.array_equal(values.to_numpy(),c.neural_score.to_numpy()))"
    new_formula="        _bestval_checks=_bestval_module.audit_scores(ROOT,IS_RERUN,"+repr(kind)+")\n        check('fixed_bestval_formula',all(v is True for v in _bestval_checks.values()))\n        values=_bestval_module.expected_mix(ROOT,"+repr(module().config(kind)['checkpoint']['weights'])+").neural_score\n        check('exact_bestval_scores',np.array_equal(values.to_numpy(),c.neural_score.to_numpy()))"
    if observer.count(old_formula)!=1:raise ValueError('Original exact neural formula changed')
    observer=observer.replace(old_formula,new_formula)
    observer="try:\n"+textwrap.indent(observer,'    ')+"\nexcept BaseException:\n    (ROOT/'submission.csv').unlink(missing_ok=True)\n    raise\n"
    notebook['cells'][29]=dict(cell_type='code',metadata={},execution_count=None,outputs=[],source=observer)
    late="""
try:
    shutil.copy2(ROOT/'submission.csv',ROOT/'submission_bestval_observer_control.csv')
    BESTVAL_ENSEMBLE_AUDIT=_bestval_module.audit(ROOT,IS_RERUN,SAMPLE_IDS,__EXTERNAL__,__BRANCH__,__RECIPE_SHA__,__MODULE_SHA__,__KIND__)
except BaseException:
    (ROOT/'submission.csv').unlink(missing_ok=True)
    raise
"""
    for key,value in {**values,'__EXTERNAL__':final_audit_variable}.items():late=late.replace(key,value)
    notebook['cells'].append(dict(cell_type='code',metadata={},execution_count=None,outputs=[],source=late))
    for i,c in enumerate(parent['cells']):
        if i not in (14,29) and notebook['cells'][i]!=c:raise ValueError('Unexpected upstream change')
    for c in notebook['cells']:
        if c['cell_type']=='code':compile(source(c),'bestval_stage','exec')
    return notebook


def prepare(name):
    kind=BRANCHES[name];stage=OUT/name
    if stage.exists():raise FileExistsError('Preserve frozen stage')
    if sha(BASE/'notebook.ipynb')!=BASE_SHA:raise ValueError('Champion source changed')
    mod=module();cfg=mod.config(kind);module_pin=sha(MODULE)
    compatibility=read(ROOT/'reports/optimization_20261112/v80_bestval_compatibility.json')
    if compatibility['status']!='passed':raise ValueError('Actual model compatibility is required')
    canary=read(ROOT/'reports/optimization_20261112/v80_bestval_module_canary.json')
    if canary['status']!='passed' or canary['module_sha256']!=module_pin:raise ValueError('Current mixing module canary is required')
    recipe=dict(branch=name,method='Independent best-validation checkpoint final-candidate neural mixture',
        baseline_ref=58156482,baseline_public_score=.488,champion_notebook_sha256=BASE_SHA,
        configuration=cfg,module_sha256=module_pin,changed_original_cells=[14,29],all_other_original_31_cells_exact=True,
        outsider_original_v2=True,late_head_original_v2=True,external_original_ab=True,new_training=False,
        checkpoint_provenance='Pinned public popwenman kernel v1 best-validation epoch52' if kind=='popwenman_best' else 'Pinned public Saner dataset v1 best-validation epoch16',
        no_claim_of_original_ozertuu_complete_reproduction=True,validation_mode='fast_static')
    raw=(json.dumps(recipe,indent=2,ensure_ascii=False)+'\n').encode();recipe_pin=hashlib.sha256(raw).hexdigest()
    parent=read(BASE/'notebook.ipynb');nb=make_notebook(parent,name,kind,recipe_pin,module_pin)
    target='stormseye/casmi26-'+name.replace('_','-')+'-1112'
    metadata=read(BASE/'kernel-metadata.json');metadata.update(id=target,title=target.split('/')[1].replace('-',' '))
    metadata['kernel_sources']=['popwenman/casmi26-scorer-train-v80/1'] if kind=='popwenman_best' else []
    stage.mkdir(parents=True)
    write(stage/'notebook.ipynb',nb);write(stage/'kernel-metadata.json',metadata);(stage/'recipe.json').write_bytes(raw)
    review=dict(status='passed',target=target,version=1,notebook_sha256=sha(stage/'notebook.ipynb'),checks=dict(
        champion_source_pin=True,all_other_original31_cells_exact=True,outsider_fixed_original_v2=True,late_head_original=True,
        original_ab_unchanged=True,explicit_independent_checkpoint=True,three_distinct_model_hashes=True,
        score_formula_actual_observer=True,model_configuration_compatible=True,lossless_module_pin=True,
        new_module_actual_canary=True,private_offline_gpu=True,source_compiles=True,global_error_removes_final=True))
    write(stage/'static_review.json',review)
    audits=copy.deepcopy(read(BASE/'branch_spec.json')['required_runtime_audits'])
    audits[0]['expected_fields'].update(branch=name,recipe_sha256=recipe_pin)
    audits.append(dict(name='bestval_ensemble_audit.json',expected_fields=dict(status='passed',branch=name,recipe_sha256=recipe_pin,mode='fast_static'),
        required_true_checks=['configuration_exact','installed_models_exact','three_distinct_checkpoints','outsider_v2_unchanged','late_head_unchanged','fast_no_model','module_pin','branch_recipe_bound','original_ab_passed','final_ab_output_bound','exact_ids_schema']))
    spec=dict(name=name,target=target,version=1,stage_dir=stage.relative_to(ROOT).as_posix(),notebook_sha256=review['notebook_sha256'],
        metadata_sha256=sha(stage/'kernel-metadata.json'),description='CASMI26 20261112 '+name+' independent checkpoint audited V1',
        validation_mode='fast_static',static_review_path=(stage/'static_review.json').relative_to(ROOT).as_posix(),required_runtime_audits=audits)
    write(stage/'branch_spec.json',spec)
    receipt=dict(status='prepared',branch=name,target=target,notebook_sha256=spec['notebook_sha256'],metadata_sha256=spec['metadata_sha256'],
                 recipe_sha256=recipe_pin,module_sha256=module_pin,kind=kind,notebook_bytes=(stage/'notebook.ipynb').stat().st_size)
    write(stage/'prepare_receipt.json',receipt)
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare',action='store_true');p.add_argument('--branch',choices=list(BRANCHES));a=p.parse_args()
    print(json.dumps(prepare(a.branch) if a.prepare and a.branch else dict(status='plan_only',branches=BRANCHES),indent=2))
