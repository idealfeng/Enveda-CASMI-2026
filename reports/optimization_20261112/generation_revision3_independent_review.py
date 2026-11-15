"""Read-only path-recovery audit; never load models or start a pipeline."""
from pathlib import Path
import json
import hashlib
import ast
import base64
import zlib

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'reports/optimization_20261112'
OLD=ROOT/'submission/optimization_20261112/generation_expand/revision2'
NEW=ROOT/'submission/optimization_20261112/generation_expand/revision3'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
src=lambda c:''.join(c['source']) if isinstance(c['source'],list) else c['source']
base=read(ROOT/'submission/optimization_20261109/mass_guarded_extlib/notebook.ipynb')
nb=read(NEW/'notebook.ipynb');recipe=read(NEW/'recipe.json');spec=read(NEW/'branch_spec.json')
receipt=read(NEW/'prepare_receipt.json');old_recipe=read(OLD/'recipe.json')
old_module=(ROOT/'scripts/generation_runtime_patch_20261112.py').read_text(encoding='utf-8')
new_module=(ROOT/'scripts/generation_runtime_patch_20261112_r3.py').read_text(encoding='utf-8')
canary_root=ROOT/'runs/generation_recovery_r3_20261112'
canary=read(canary_root/'verification.json');hidden=read(canary_root/'hidden_audit_fixture_receipt.json')
setup=src(nb['cells'][12])[len(src(base['cells'][12])):]
tree=ast.parse(setup)


def unpack(name):
    n=next(n for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(getattr(x,'id',None)==name for x in n.targets))
    call=next(c for c in ast.walk(n.value) if isinstance(c,ast.Call) and isinstance(c.func,ast.Attribute) and c.func.attr=='b64decode')
    return zlib.decompress(base64.b64decode(ast.literal_eval(call.args[0])))


module=unpack('_gen_raw');runner=unpack('_gen_runner_text')
checks=dict(
    new_stage_source=sha(NEW/'notebook.ipynb')==spec['notebook_sha256']==receipt['notebook_sha256']==canary['notebook_sha256']=='1f9a7119dd4fdb45e006c71bd89719646dd08723faf0737920e1b0fd658c73a9',
    recipe_binding=sha(NEW/'recipe.json')==receipt['recipe_sha256']==spec['required_runtime_audits'][-1]['expected_fields']['recipe_sha256'],
    metadata_binding=sha(NEW/'kernel-metadata.json')==spec['metadata_sha256']==receipt['metadata_sha256'],
    new_branch_identity=recipe['branch']==spec['name']=='generation_expand_r3' and recipe['target']==spec['target']=='stormseye/casmi26-generation-expand-r3-1112',
    other_original32_cells_unchanged=all(nb['cells'][i]==c for i,c in enumerate(base['cells']) if i!=12),
    frozen_payload_unchanged=nb['cells'][11]==base['cells'][11],
    all_inference_functions_byte_exact=old_module.split('\ndef audit(',1)[0]==new_module.split('\ndef audit(',1)[0],
    generation_configuration_unchanged=recipe['configuration']==old_recipe['configuration'],
    module_payload_exact=module==(ROOT/'scripts/generation_runtime_patch_20261112_r3.py').read_bytes() and hashlib.sha256(module).hexdigest()==recipe['module_sha256']==canary['module_sha256']=='0a9a19291ab2f4867331b6f4c81c535c30246ad2d0df873e11dd8ce04d3c8590',
    runner_unchanged=hashlib.sha256(runner).hexdigest()==recipe['runner_sha256']==old_recipe['runner_sha256']==canary['runner_sha256'],
    actual_production_CODE_p2s=any("CODE = ROOT / 'p2s_code'" in src(c) for c in base['cells'] if c['cell_type']=='code'),
    module_uses_own_installed_path='module_path = Path(__file__).resolve()' in new_module and 'installed_module_pin=sha(module_path) == module_pin' in new_module,
    runner_same_installed_directory="runner_path = module_path.parent/'generation_runner.py'" in new_module and 'actual_runner_file=sha(runner_path) == runner_pin' in new_module,
    launch_path_strictly_bound="Path(launch['actual_runner']).resolve() == runner_path.resolve()" in new_module,
    old_hardcoded_code_removed="root/'code/" not in new_module,
    p2s_directory_exists=(canary_root/'p2s_code').is_dir(),
    old_code_directory_absent=not(canary_root/'code').exists(),
    path_canary12_passed=canary['status']=='passed' and canary['checks_passed']==canary['checks_total']==12 and all(canary['checks'].values()),
    hidden_audit_replay_passed=hidden['status']=='passed' and hidden['checks']['actual_runner_path'] is True and all(hidden['checks'].values()),
    actual_runtime_reused_byte_exact=sha(ROOT/'runs/generation_prod_canary_20261112_actual_revision2/generation_runtime.json')==sha(canary_root/'generation_runtime.json')==hidden['runtime_report_sha256'],
    negative_wrong_path_rejected=canary['checks']['wrong_launch_path_rejected_no_final'] is True,
    fast_entry_no_generation=canary['checks']['fast_final_passed'] is True,
    errors_fail_closed="(ROOT/'submission.csv').unlink(missing_ok=True)" in src(nb['cells'][-1]) and "(ROOT/'submission.csv').unlink(missing_ok=True)" in setup)
assert all(checks.values()),[k for k,x in checks.items() if not x]
result=dict(status='passed',reviewed_revision='revision3',notebook_sha256=sha(NEW/'notebook.ipynb'),
    module_sha256=recipe['module_sha256'],runner_sha256=recipe['runner_sha256'],recipe_sha256=sha(NEW/'recipe.json'),
    checks=checks,checks_passed=sum(checks.values()),checks_total=len(checks),
    scope='Path-only recovery. Exact p2s_code fast entry passed; hidden audit uses unchanged prior actual two-query runtime and ranked CSV with constructed launch/AB fixtures, not a new full pipeline/model run.',
    previous_review_scope_correction='Revision2 review missed real Kaggle CODE=p2s_code and incorrectly accepted a local code fixture. Its 38 checks did not establish actual Kaggle layout compatibility.',
    previous_review='reports/optimization_20261112/generation_revision2_independent_review.json',
    read_only=True,no_gpu_or_model_load=True,no_cloud_writes=True)
for filename in ('generation_independent_review.json','generation_revision3_independent_review.json'):
    (OUT/filename).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(status=result['status'],revision=result['reviewed_revision'],passed=result['checks_passed'],total=result['checks_total'],notebook_sha256=result['notebook_sha256'])))
