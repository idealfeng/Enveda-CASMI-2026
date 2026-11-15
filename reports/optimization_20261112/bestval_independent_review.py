"""Independent read-only review of frozen stages, never load a model or call Kaggle."""
from pathlib import Path
import ast
import base64
import hashlib
import json
import zlib

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'reports/optimization_20261112'
BASE = ROOT / 'submission/optimization_20261109/mass_guarded_extlib'
EXPECTED = {
    'bestval_v80_tri': ('popwenman_best', [.5,.25,.25], 'f7e2383fe5fc0cc85e7333d308bc7201144574f2eef6b59000570d171e0758a7'),
    'bestval_saner_tri': ('saner_best', [.375,.375,.25], '969d13443fcf168eae1e00e56a8e0ae87dcb16f337cb6dbac959e7cd218f089c')}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def src(cell):
    return ''.join(cell['source']) if isinstance(cell['source'], list) else cell['source']


def assignment(tree, name):
    return next(n for n in ast.walk(tree) if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == name for t in n.targets))


def literal(node):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id=='dict' and not node.args:
        return {kw.arg:literal(kw.value) for kw in node.keywords}
    if isinstance(node, ast.Dict):
        return {literal(k):literal(v) for k,v in zip(node.keys,node.values)}
    return ast.literal_eval(node)


def main():
    parent = read(BASE / 'notebook.ipynb')
    module = ROOT / 'scripts/v80_ensemble_20261112.py'
    module_text = module.read_text(encoding='utf-8')
    specs = literal(assignment(ast.parse(module_text), 'SPECS').value)
    public_pins = ast.literal_eval(assignment(ast.parse(module_text), 'PUB_PINS').value)
    v2_pin = ast.literal_eval(assignment(ast.parse(module_text), 'V2_SHA').value)
    compat = read(OUT / 'v80_bestval_compatibility.json')
    model_canary = read(OUT / 'v80_bestval_module_canary.json')
    checks = dict(champion_pin=sha(BASE/'notebook.ipynb')=='2bb94c91b176f95dfdff52f08781443ffee004c20d06aeb30efb14d0c0112fc7',
                  actual_compatibility_passed=compat['status']=='passed' and all(x['strict_load_and_actual_scoring'] for x in compat['models']),
                  compatibility_distinct_hashes=len({x['checkpoint_sha256'] for x in compat['models']})==4,
                  current_module_canary=model_canary['status']=='passed' and model_canary['module_sha256']==sha(module),
                  fixed_configuration_guard="runtime['configuration'] != config(kind)" in module_text,
                  fixed_public_v2_weights=public_pins['final_model.pt']=='44436b2daec64373e66f9120dd2389c24fc83dd9430ebeeac18e3cb49dcb9642' and v2_pin=='c08d2101154d057890de088be63834eb622468892a3b842512fdc5a65e02ff46')
    results = {}
    for name, (kind, weights, extra_pin) in EXPECTED.items():
        stage = ROOT / 'submission/optimization_20261112' / name
        receipt = read(stage / 'prepare_receipt.json')
        spec = read(stage / 'branch_spec.json')
        recipe = read(stage / 'recipe.json')
        meta = read(stage / 'kernel-metadata.json')
        nb = read(stage / 'notebook.ipynb')
        c14, c29, c33 = (src(nb['cells'][i]) for i in (14,29,33))
        tree = ast.parse(c14)
        packed = ast.literal_eval(assignment(tree, '_bestval_raw').value.args[0].args[0])
        payload = zlib.decompress(base64.b64decode(packed))
        cfg = recipe['configuration']
        prepare = next(n for n in ast.walk(tree) if isinstance(n, ast.Call)
                       and isinstance(n.func, ast.Attribute) and n.func.attr=='prepare')
        final_audit = next(n for n in ast.walk(ast.parse(c33)) if isinstance(n, ast.Call)
                          and isinstance(n.func, ast.Attribute) and n.func.attr=='audit')
        audit_specs = spec['required_runtime_audits']
        local = dict(source_hashes_bound=sha(stage/'notebook.ipynb')==receipt['notebook_sha256']==spec['notebook_sha256'],
                     metadata_hashes_bound=sha(stage/'kernel-metadata.json')==receipt['metadata_sha256']==spec['metadata_sha256'],
                     recipe_hash_bound=sha(stage/'recipe.json')==receipt['recipe_sha256'],
                     only_expected_cells_changed=len(nb['cells'])==34 and all(nb['cells'][i]==cell for i,cell in enumerate(parent['cells']) if i not in (14,29)),
                     original_outsider_helper=nb['cells'][12]==parent['cells'][12],
                     original_outsider_tail="BUNDLE = OURS_BUNDLE\n        if not NEURAL_OK:" in c14 and "OUTSIDERS_OK = score_outside_candidates(needed=True)" in c14,
                     original_late_head_cells=nb['cells'][30:32]==parent['cells'][30:32],
                     original_ab_cell=nb['cells'][32]==parent['cells'][32],
                     exact_module_payload=hashlib.sha256(payload).hexdigest()==sha(module)==recipe['module_sha256']==receipt['module_sha256'] and payload==module.read_bytes(),
                     fixed_model_kind=cfg['kind']==kind and cfg['checkpoint']==specs[kind],
                     intended_weights=cfg['checkpoint']['weights']==weights,
                     independent_extra=cfg['checkpoint']['sha256']==extra_pin and len({public_pins['final_model.pt'],v2_pin,extra_pin})==3,
                     explicit_prepare_arguments=[ast.literal_eval(x) for x in prepare.args[3:]]==[kind,name,sha(stage/'recipe.json'),sha(module)],
                     explicit_final_arguments=[ast.literal_eval(x) for x in final_audit.args[4:]]==[name,sha(stage/'recipe.json'),sha(module),kind],
                     score_observer_new_recipe=repr(sha(stage/'recipe.json')) in c29 and repr(name) in c29,
                     exact_formula_observer='exact_bestval_scores' in c29 and 'fixed_bestval_formula' in c29,
                     module_rechecks_input_output='actual_input_hashes' in module_text and 'actual_output_hash' in module_text and 'exact_score_consumption' in module_text,
                     final_ab_binding='final_ab_output_bound' in module_text and 'external_audit.get' in module_text,
                     private_offline_gpu=meta['is_private'] is True and meta['enable_internet'] is False and meta['enable_gpu'] is True,
                     versioned_extra_source=meta.get('kernel_sources',[])==(['popwenman/casmi26-scorer-train-v80/1'] if kind=='popwenman_best' else []),
                     common_datasets_unchanged=meta['dataset_sources']==read(BASE/'kernel-metadata.json')['dataset_sources'],
                     final_contract=audit_specs[-1]['name']=='bestval_ensemble_audit.json' and audit_specs[-1]['expected_fields']==dict(status='passed',branch=name,recipe_sha256=sha(stage/'recipe.json'),mode='fast_static'),
                     parent_audit_updated=audit_specs[0]['expected_fields']['branch']==name and audit_specs[0]['expected_fields']['recipe_sha256']==sha(stage/'recipe.json'),
                     final_required_checks=all(x in audit_specs[-1]['required_true_checks'] for x in ('configuration_exact','three_distinct_checkpoints','branch_recipe_bound','module_pin','final_ab_output_bound','fast_no_model')),
                     global_errors_remove_final=all("(ROOT/'submission.csv').unlink(missing_ok=True)" in text for text in (c14,c29,c33)))
        # The call order is checked in the exact installed cell rather than the builder.
        local['mix_validated_before_consensus'] = c14.index('BESTVAL_MIX_REPORT=') < c14.index('_bestval_module.audit_scores(') < c14.index('CONSENSUS_OK, REPORT, MOVES = build_consensus()')
        for c in nb['cells']:
            if c['cell_type']=='code':
                compile(src(c),'independent_static_review','exec')
        local['all_code_compiles'] = True
        checks.update({name+':'+k:v for k,v in local.items()})
        results[name] = dict(checks=local,notebook_sha256=sha(stage/'notebook.ipynb'),recipe_sha256=sha(stage/'recipe.json'),configuration=cfg)
    record = dict(status='passed' if all(checks.values()) else 'failed',checks=checks,checks_passed=sum(checks.values()),
                  checks_total=len(checks),branches=results,module_sha256=sha(module),read_only=True,
                  no_gpu_models_loaded=True,no_cloud_writes=True,efficacy_claim=False)
    (OUT/'bestval_independent_review.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=record['status'],passed=record['checks_passed'],total=record['checks_total'],failed=[k for k,v in checks.items() if not v])))
    if record['status']!='passed':
        raise SystemExit(1)


if __name__=='__main__':
    main()
