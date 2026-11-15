"""Freeze two user-authorized exploratory controls without overwriting previous stages."""
from pathlib import Path
import argparse
import ast
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / 'scripts/generation_runtime_patch_20261113.py'
BUILDER = ROOT / 'scripts/build_generation_variant_20261112_r3.py'
ARMS = {
    'generation_noiso_control': dict(target='stormseye/casmi26-gen-noiso-only-1113',
        title='CASMI26 gen noiso only 1113', total=150, isomer=False,
        method='Single factor against exact .488 champion: disable near-zero-delta isomerisation only',
        description='CASMI26 20261113 exploratory iso-off only parents6 products150 V1'),
    'generation_budget_only': dict(target='stormseye/casmi26-gen-budget-only-1113',
        title='CASMI26 gen budget only 1113', total=300, isomer=True,
        method='Single factor against exact .488 champion: total generated candidate cap 150 to 300 only',
        description='CASMI26 20261113 exploratory budget only parents6 products300 iso-on V1'),
}


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError(f'Expected one literal anchor: {old!r}, found {source.count(old)}')
    return source.replace(old, new)


def generalized_module(arm):
    source = TEMPLATE.read_text(encoding='utf-8')
    source = replace_once(source,
        'CONFIG = dict(gen_n_analog=12, gen_max_total=300, gen_max_per_parent=60,\n              max_steps=2, allow_isomerisation=False)',
        f"CONFIG = dict(gen_n_analog=6, gen_max_total={arm['total']}, gen_max_per_parent=60,\n              max_steps=2, allow_isomerisation={arm['isomer']})")
    replacements = {
        "kwargs.get('max_steps') != 2 or kwargs.get('max_per_analog') != 60":
            "kwargs.get('max_steps') != CONFIG['max_steps'] or kwargs.get('max_per_analog') != CONFIG['gen_max_per_parent']",
        "kwargs['allow_isomerisation'] = False": "kwargs['allow_isomerisation'] = CONFIG['allow_isomerisation']",
        "[:12]": "[:CONFIG['gen_n_analog']]",
        "r['parents_used'] <= 12": "r['parents_used'] <= CONFIG['gen_n_analog']",
        "r['n_generated'] <= 300": "r['n_generated'] <= CONFIG['gen_max_total']",
    }
    for old, new in replacements.items():
        source = replace_once(source, old, new)
    compile(source, '<generalized generation observer>', 'exec')
    return source


def prepare(name, arm):
    out = ROOT / 'submission/optimization_20261113' / name
    module = ROOT / 'scripts' / f'generation_runtime_patch_{name}_20261113.py'
    if out.exists() or module.exists():
        raise FileExistsError(f'Frozen arm already exists: {name}')
    module_source = generalized_module(arm)
    source = BUILDER.read_text(encoding='utf-8')
    replacements = {
        "OUT = ROOT/'submission/optimization_20261112/generation_expand/revision3'": f"OUT = ROOT/'submission/optimization_20261113/{name}'",
        "MODULE = ROOT/'scripts/generation_runtime_patch_20261112_r3.py'": f"MODULE = ROOT/'scripts/{module.name}'",
        "BRANCH = 'generation_expand_r3'": f'BRANCH = {name!r}',
        "target='stormseye/casmi26-generation-expand-r3-1112'": f"target={arm['target']!r}",
        "title='CASMI26 generation expand r3 1112'": f"title={arm['title']!r}",
        "method='Expanded spectral parents and bounded product budget without neutral-delta isomer enumeration'": f"method={arm['method']!r}",
        "configuration=dict(gen_n_analog=12,gen_max_total=300,gen_max_per_parent=60,max_steps=2,allow_isomerisation=False)": f"configuration=dict(gen_n_analog=6,gen_max_total={arm['total']},gen_max_per_parent=60,max_steps=2,allow_isomerisation={arm['isomer']})",
        "recovery_scope='Audit path resolution only; generation algorithm and runner unchanged from revision2'": "recovery_scope='Exact e494 post-FROZEN27 engine source pin, reused production runner and generalized config observers'",
        "previous_unsubmitted_failed_target='stormseye/casmi26-generation-expand-1112'": "previous_unsubmitted_failed_target=None",
        "local_module_source='scripts/generation_runtime_patch_20261112_r3.py'": f"local_module_source='scripts/{module.name}'",
        "source_attribution='Existing production Engine + recording hooks, bounded generation budget motivated by completed diagnostics; not a claimed validated gain'": "source_attribution='User explicitly authorized four additional exploratory submissions; positive local score evidence is not a prerequisite; this single-factor arm has no claimed gain'",
        "runtime_guard='Original per-parent derive budget800, products60 and original 2-step semantics; total300 and parents12 explicit'": f"runtime_guard='Original derive budget800 per parent, products60 and 2-step semantics; parents6 total{arm['total']} isomerisation{arm['isomer']} explicit'",
        "final_generated_count='Raw-SMILES intersection conservative diagnostic, not truth recall')": "final_generated_count='Raw-SMILES intersection conservative diagnostic, not truth recall',\n                validation_boundary='Reuses source-pin/runner template with real 2-query production E2E proof at generation_production; THIS arm has not had a new complete production or hidden run. Local static/derive component checks are not full inference.',\n                reused_production_evidence='runs/generation_production_20261113_r2/verification.json',\n                reused_evidence_disclosure='reports/optimization_20261113/generation_disclosure_addendum.json',\n                selection_basis='User-authorized exploration; no efficacy or Class-3 benefit claim')",
        "description='CASMI26 20261112 generation r3 CODE path repair parents12 products300 audited V1'": f"description={arm['description']!r}",
        "status='prepared_pending_actual_canary'": "status='prepared_exploratory_reused_production_template'",
    }
    for old, new in replacements.items():
        source = replace_once(source, old, new)
    compile(source, str(BUILDER), 'exec')
    module.write_text(module_source, encoding='utf-8', newline='\n')
    scope = dict(__name__='_generation_control_builder', __file__=str(BUILDER))
    exec(compile(source, str(BUILDER), 'exec'), scope)
    receipt = scope['prepare']()
    static_path = out / 'static_review.json'
    static = json.loads(static_path.read_text(encoding='utf-8'))
    static.update(validation_scope='Static source, pins and compile checks only; separate derive component check, no new full inference',
        new_arm_complete_production_run=False,
        reused_production_notebook_sha256='a9debc93f59213d3c80a8b3ee0e4808ee930d6ada34c3ee908f1469fa35cfa2c',
        user_authorized_exploration=True)
    static_path.write_text(json.dumps(static, indent=2) + '\n', encoding='utf-8')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    args = parser.parse_args()
    result = [prepare(name, arm) for name, arm in ARMS.items()] if args.prepare else ARMS
    print(json.dumps(result, indent=2))
