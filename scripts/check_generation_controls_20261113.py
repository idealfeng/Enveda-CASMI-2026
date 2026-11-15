"""Static binding plus real RDKit derivation-wrapper component checks; no full Engine/model run."""
from pathlib import Path
import ast
import base64
import hashlib
import importlib.util
import json
import sys
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from build_generation_controls_20261113 import ARMS, generalized_module


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(cell):
    return ''.join(cell['source']) if isinstance(cell['source'], list) else cell['source']


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    import rdkit
    v4 = ROOT / 'assets/kaggle/ahmedberatozer/casmi26-v4b-models/v4/code'
    sys.path.insert(0, str(v4))
    sys.path.insert(0, str(v4 / 'fe_v4'))
    import hooks_v1
    from casmi import derive
    champion = json.loads((ROOT / 'submission/optimization_20261109/mass_guarded_extlib/notebook.ipynb').read_text())
    results = []
    for name, arm in ARMS.items():
        stage = ROOT / 'submission/optimization_20261113' / name
        recipe = json.loads((stage / 'recipe.json').read_text())
        spec = json.loads((stage / 'branch_spec.json').read_text())
        book = json.loads((stage / 'notebook.ipynb').read_text())
        local_module = ROOT / recipe['local_module_source']
        text = local_module.read_text()
        module = load_module(local_module, name)
        tree = ast.parse(text)
        install = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'install')
        wrapper = next(n for n in install.body if isinstance(n, ast.FunctionDef) and n.name == 'derive_rec')
        # Execute the exact nested wrapper body against the actual pinned upstream derivation function.
        # This deliberately does not pretend to initialize E/V or execute the final ranker.
        import time
        state = dict(current=dict(parents_used=0, parent_calls=[]), derive_errors=0)
        scope = dict(CONFIG=module.CONFIG, STATE=state, original_derive=hooks_v1.derive_rec, time=time)
        exec(compile(ast.fix_missing_locations(ast.Module(body=[wrapper], type_ignores=[])), '<actual derive wrapper component>', 'exec'), scope)
        fn = scope['derive_rec']
        kwargs = dict(tol=0.003, max_steps=2, max_per_analog=60)
        smiles = 'COc1ccccc1O'
        zero = fn(smiles, 0.0, **kwargs)
        zero_original = hooks_v1.derive_rec(smiles, 0.0, **kwargs)
        nonzero = fn(smiles, 15.994915, **kwargs)
        nonzero_original = hooks_v1.derive_rec(smiles, 15.994915, **kwargs)
        rejected_bad_steps = False
        try:
            fn(smiles, 15.994915, tol=0.003, max_steps=1, max_per_analog=60)
        except ValueError:
            rejected_bad_steps = True
        setup_tree = ast.parse(source(book['cells'][12])[len(source(champion['cells'][12])):])
        setup_values = {}
        for node in ast.walk(setup_tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'b64decode':
                raw = zlib.decompress(base64.b64decode(ast.literal_eval(node.args[0])))
                setup_values[hashlib.sha256(raw).hexdigest()] = raw
        cfg = dict(gen_n_analog=6, gen_max_total=arm['total'], gen_max_per_parent=60,
                   max_steps=2, allow_isomerisation=arm['isomer'])
        checks = dict(
            rdkit_official=rdkit.__version__ == '2026.03.3',
            notebook_bound=sha(stage / 'notebook.ipynb') == spec['notebook_sha256'],
            metadata_bound=sha(stage / 'kernel-metadata.json') == spec['metadata_sha256'],
            module_bound=sha(local_module) == recipe['module_sha256'],
            embedded_module_exact=setup_values.get(recipe['module_sha256']) == local_module.read_bytes(),
            embedded_runner_exact=recipe['runner_sha256'] in setup_values,
            configuration_exact=module.CONFIG == cfg == recipe['configuration'],
            generalized_source_exact=text == generalized_module(arm),
            only_original_cell12_changed=[i for i, (a, b) in enumerate(zip(champion['cells'], book['cells'])) if a != b] == [12],
            only_one_final_audit_added=len(book['cells']) == len(champion['cells']) + 1,
            hooks_pin=sha(hooks_v1.__file__) == module.SOURCE_PINS['hooks_v1'],
            derivation_pin=sha(derive.__file__) == module.SOURCE_PINS['derive'],
            exact_post_frozen_engine_pin=module.SOURCE_PINS['engine'] == 'e4943fb26a8141f47ea95e744910c2d0f4746e36e72ef43e3263e7f327cfc0b5',
            zero_delta_toggle=(zero == zero_original and len(zero) > 0) if arm['isomer'] else (zero == [] and len(zero_original) > 0),
            nonzero_two_step_preserved=nonzero == nonzero_original and len(nonzero) > 0,
            actual_wrapper_observed_both_calls=state['current']['parents_used'] == 2,
            bad_steps_fail_closed=rejected_bad_steps,
            no_new_complete_run_claim=recipe['validation_boundary'].startswith('Reuses source-pin/runner template') and 'THIS arm has not had' in recipe['validation_boundary'],
        )
        for cell in book['cells']:
            if cell['cell_type'] == 'code':
                compile(source(cell), name, 'exec')
        checks['all_code_compiles'] = True
        result = dict(branch=name, status='passed_static_and_real_derive_component' if all(checks.values()) else 'failed',
            checks=checks, configuration=cfg, notebook_sha256=spec['notebook_sha256'],
            recipe_sha256=sha(stage / 'recipe.json'), module_sha256=recipe['module_sha256'],
            runner_sha256=recipe['runner_sha256'], rdkit=rdkit.__version__,
            actual_derivation=dict(parent_smiles=smiles, zero_delta_products=len(zero),
                original_zero_delta_products=len(zero_original), nonzero_delta_products=len(nonzero),
                nonzero_delta_da=15.994915),
            validation_boundary='Only static binding and exact actual derive wrapper component against real pinned hooks/RDKit. No Engine library, neural models, GPU inference, ranker or complete production initialized for this new arm. Full prior E2E used another CONFIG, disclosed separately.',
            exploration_authorization='User explicitly requested the remaining four exploratory submissions even without demonstrated local improvement.')
        results.append(result)
    report = ROOT / 'reports/optimization_20261113/generation_controls_checks.json'
    report.write_text(json.dumps(dict(status='passed' if all(r['status'].startswith('passed') for r in results) else 'failed', arms=results), indent=2) + '\n')
    print(json.dumps(results, indent=2))
    if not all(all(r['checks'].values()) for r in results):
        raise AssertionError('Generation controls checks failed')


if __name__ == '__main__':
    main()
