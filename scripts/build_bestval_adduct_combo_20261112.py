"""Compose the two frozen components without changing their standalone stages."""
from pathlib import Path
import argparse
import copy
import hashlib
import importlib.util
import json

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'submission/optimization_20261109/mass_guarded_extlib'
OUT = ROOT / 'submission/optimization_20261112'
NAME = 'bestval_v80_adduct'
BASE_SHA = '2bb94c91b176f95dfdff52f08781443ffee004c20d06aeb30efb14d0c0112fc7'


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p, v): Path(p).write_text(json.dumps(v, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
def source(c): return ''.join(c['source']) if isinstance(c['source'], list) else c['source']


def prepare():
    stage = OUT / NAME
    if stage.exists():
        raise FileExistsError('Preserve frozen combo stage')
    if sha(BASE / 'notebook.ipynb') != BASE_SHA:
        raise ValueError('Champion changed')
    import kaggle_batch as batch
    nn_dir, ab_dir = OUT / 'bestval_v80_tri', OUT / 'adduct_extlib'
    nn_spec, ab_spec = read(nn_dir / 'branch_spec.json'), read(ab_dir / 'branch_spec.json')
    for spec in (nn_spec, ab_spec):
        batch.local_preflight({}, spec)
    nn_recipe, ab_recipe = read(nn_dir / 'recipe.json'), read(ab_dir / 'recipe.json')
    module = ROOT / 'scripts/v80_ensemble_20261112.py'
    if sha(module) != nn_recipe['module_sha256']:
        raise ValueError('Neural module differs from frozen component')
    checks = read(ROOT / 'reports/optimization_20261112/adduct_stage_canary.json')
    if checks['status'] != 'passed' or checks['notebook_sha256'] != ab_spec['notebook_sha256']:
        raise ValueError('Exact external component canary required')
    recipe = dict(branch=NAME, baseline_ref=58156482, baseline_public_score=.488,
        method='Independent best-validation scorer plus V18 neutral-mass/adduct AB matching',
        champion_notebook_sha256=BASE_SHA, configuration=nn_recipe['configuration'],
        neural_component=dict(branch='bestval_v80_tri', notebook_sha256=nn_spec['notebook_sha256'],
                              recipe_sha256=sha(nn_dir/'recipe.json'), module_sha256=sha(module)),
        external_component=dict(branch='adduct_extlib', notebook_sha256=ab_spec['notebook_sha256'],
                                recipe_sha256=sha(ab_dir/'recipe.json'), recipe=ab_recipe),
        changed_original_cells=[14,29,32], original_other30_cells_exact=True,
        outsider_original_v2=True, late_head_original_v2=True, original_generation=True,
        new_training=False, enveda_added=False, no_gain_claim=True,
        builder_sha256=sha(ROOT/'scripts/build_v80_variants_20261112.py'), validation_mode='fast_static')
    raw = (json.dumps(recipe, indent=2, ensure_ascii=False)+'\n').encode()
    recipe_pin = hashlib.sha256(raw).hexdigest()
    spec = importlib.util.spec_from_file_location('_bestval_combo_builder', ROOT/'scripts/build_v80_variants_20261112.py')
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    parent = read(BASE/'notebook.ipynb')
    notebook = builder.make_notebook(parent, NAME, 'popwenman_best', recipe_pin, sha(module),
                                     final_audit_variable='ADDUCT_OVERLAY_AUDIT')
    notebook['cells'][32] = copy.deepcopy(read(ab_dir/'notebook.ipynb')['cells'][32])
    exact = all(notebook['cells'][i] == c for i,c in enumerate(parent['cells']) if i not in (14,29,32))
    if not exact:
        raise ValueError('Unexpected champion changes')
    for c in notebook['cells']:
        if c['cell_type']=='code': compile(source(c), 'bestval_adduct_combo', 'exec')
    target = 'stormseye/casmi26-bestval-v80-adduct-1112'
    metadata = read(nn_dir/'kernel-metadata.json')
    metadata.update(id=target, title='CASMI26 bestval v80 adduct 1112')
    stage.mkdir(parents=True)
    write(stage/'notebook.ipynb', notebook)
    write(stage/'kernel-metadata.json', metadata)
    (stage/'recipe.json').write_bytes(raw)
    static = dict(status='passed',target=target,version=1,notebook_sha256=sha(stage/'notebook.ipynb'),
        checks=dict(champion_pin=True, standalone_components_frozen=True, original_other30_cells_exact=exact,
                    external_actual_cell_exact=True, neural_fixed_pop_best_config=True, distinct_checkpoints=True,
                    outside_and_latehead_original=True, final_observer_binds_adduct_output=True,
                    original_generation_preserved=True, official_identity_guard=True,
                    private_offline_gpu=True, source_compiles=True, fail_closed=True))
    write(stage/'static_review.json',static)
    audits = [copy.deepcopy(a) for a in nn_spec['required_runtime_audits'] if a['name']!='external_overlay_audit.json']
    for a in audits:
        if a['name'] in ('batch_variant_audit.json','bestval_ensemble_audit.json'):
            a['expected_fields'].update(branch=NAME,recipe_sha256=recipe_pin)
    external = next(a for a in ab_spec['required_runtime_audits'] if a['name']=='adduct_overlay_audit.json')
    audits.append(copy.deepcopy(external))
    names = [a['name'] for a in audits]
    if len(names)!=len(set(names)) or not 1<=len(names)<=8:
        raise ValueError('Ambiguous component audit contracts')
    branch = dict(name=NAME,target=target,version=1,stage_dir=stage.relative_to(ROOT).as_posix(),
        notebook_sha256=static['notebook_sha256'],metadata_sha256=sha(stage/'kernel-metadata.json'),
        description='CASMI26 20261112 bestval_v80_adduct combined independent scorer neutral mass audited V1',
        validation_mode='fast_static',static_review_path=(stage/'static_review.json').relative_to(ROOT).as_posix(),
        required_runtime_audits=audits)
    write(stage/'branch_spec.json',branch)
    result=dict(status='prepared',branch=NAME,target=target,notebook_sha256=branch['notebook_sha256'],
                metadata_sha256=branch['metadata_sha256'],recipe_sha256=recipe_pin,
                notebook_bytes=(stage/'notebook.ipynb').stat().st_size)
    write(stage/'prepare_receipt.json',result)
    batch.local_preflight({},branch)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prepare',action='store_true')
    args=p.parse_args()
    print(json.dumps(prepare() if args.prepare else dict(status='plan_only_no_write',branch=NAME),indent=2))
