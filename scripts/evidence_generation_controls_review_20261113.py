"""Independent source-only review of two exploratory generation controls."""
from pathlib import Path
import ast
import base64
import hashlib
import json
import zlib
ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def src(c):return ''.join(c['source']) if isinstance(c['source'],list) else c['source']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def value(tree,name):return next(n.value for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in n.targets))

parent=read(ROOT/'submission/optimization_20261109/mass_guarded_extlib/notebook.ipynb')
reports={}
for arm,total,isomer in [('generation_noiso_control',150,False),('generation_budget_only',300,True)]:
    p=ROOT/'submission/optimization_20261113'/arm
    b=read(p/'notebook.ipynb');r=read(p/'recipe.json');s=read(p/'branch_spec.json')
    tree=ast.parse(src(b['cells'][12]));node=value(tree,'_gen_raw')
    embedded=zlib.decompress(base64.b64decode(ast.literal_eval(node.args[0].args[0])))
    source=embedded.decode();mt=ast.parse(source)
    cfg_node=value(mt,'CONFIG');cfg={k.arg:ast.literal_eval(k.value) for k in cfg_node.keywords}
    config=dict(gen_n_analog=6,gen_max_total=total,gen_max_per_parent=60,max_steps=2,allow_isomerisation=isomer)
    local=ROOT/r['local_module_source'];pins=ast.literal_eval(value(mt,'SOURCE_PINS'))
    checks=dict(parent_pin=r['champion_notebook_sha256']==sha(ROOT/'submission/optimization_20261109/mass_guarded_extlib/notebook.ipynb'),
        stage_pin=s['notebook_sha256']==sha(p/'notebook.ipynb'),
        only_original_cell12_changed=[i for i,(x,y) in enumerate(zip(parent['cells'],b['cells'])) if x!=y]==[12],
        all_original_head_AB_preserved=b['cells'][13:33]==parent['cells'][13:33],
        setup_only_append=src(b['cells'][12]).startswith(src(parent['cells'][12])),one_new_audit=len(b['cells'])==34,
        source_payload_exact=embedded==local.read_bytes() and hashlib.sha256(embedded).hexdigest()==r['module_sha256'],
        exact_declared_and_actual_configuration=cfg==r['configuration']==config,
        real_post_frozen27_engine_pin=pins['engine']=='e4943fb26a8141f47ea95e744910c2d0f4746e36e72ef43e3263e7f327cfc0b5',
        reused_same_runner=r['runner_sha256']=='153c85fb59025f3c2fa75cf9a64ffe7aa6cdb26b25113fee9fa46643c22f1182',
        dynamic_parent_bound="r['parents_used'] <= CONFIG['gen_n_analog']" in source,
        dynamic_product_bound="r['n_generated'] <= CONFIG['gen_max_total']" in source,
        dynamic_isomer_policy="kwargs['allow_isomerisation'] = CONFIG['allow_isomerisation']" in source,
        final_audit_branch=s['required_runtime_audits'][-1]['expected_fields']['branch']==arm,
        final_audit_recipe=s['required_runtime_audits'][-1]['expected_fields']['recipe_sha256']==sha(p/'recipe.json'),
        new_arm_not_mislabeled_full_run=read(p/'static_review.json')['new_arm_complete_production_run'] is False)
    reports[arm]=dict(status='passed_source_only' if all(checks.values()) else 'failed',checks=checks,
        notebook_sha256=sha(p/'notebook.ipynb'),recipe_sha256=sha(p/'recipe.json'),module_sha256=sha(local),configuration=cfg,
        limitation='No new complete inference, library load or model execution. Source-template review is not new efficacy or full-pipeline proof.')
out=ROOT/'reports/optimization_20261113/evidence_generation_controls_review.json'
out.write_text(json.dumps(reports,indent=2)+'\n',encoding='utf-8')
print(json.dumps(reports,indent=2))
assert all(r['status']=='passed_source_only' for r in reports.values())
