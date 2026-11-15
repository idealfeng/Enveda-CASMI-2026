"""Read-only check of exact component composition; no GPU or cloud calls."""
from pathlib import Path
import ast
import base64
import hashlib
import json
import zlib
from bestval_independent_review import read, sha, src, assignment

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'reports/optimization_20261112'
STAGES=ROOT/'submission/optimization_20261112'
NAME='bestval_v80_adduct'


def main():
    base=read(ROOT/'submission/optimization_20261109/mass_guarded_extlib/notebook.ipynb')
    stage=STAGES/NAME
    nb=read(stage/'notebook.ipynb');recipe=read(stage/'recipe.json');spec=read(stage/'branch_spec.json')
    receipt=read(stage/'prepare_receipt.json');meta=read(stage/'kernel-metadata.json')
    nn=read(STAGES/'bestval_v80_tri/notebook.ipynb');nr=read(STAGES/'bestval_v80_tri/recipe.json')
    ab=read(STAGES/'adduct_extlib/notebook.ipynb');ar=read(STAGES/'adduct_extlib/recipe.json')
    old_recipe=sha(STAGES/'bestval_v80_tri/recipe.json');new_recipe=sha(stage/'recipe.json')
    translate=lambda text:text.replace(repr('bestval_v80_tri'),repr(NAME)).replace(repr(old_recipe),repr(new_recipe))
    c14,c29,c32,c33=(src(nb['cells'][i]) for i in (14,29,32,33))
    expected_final=translate(src(nn['cells'][33])).replace('EXTERNAL_OVERLAY_AUDIT','ADDUCT_OVERLAY_AUDIT')
    module=ROOT/'scripts/v80_ensemble_20261112.py'
    packed=ast.literal_eval(assignment(ast.parse(c14),'_bestval_raw').value.args[0].args[0])
    payload=zlib.decompress(base64.b64decode(packed))
    auditors={x['name']:x for x in spec['required_runtime_audits']}
    nn_meta=read(STAGES/'bestval_v80_tri/kernel-metadata.json')
    clean=lambda m:{k:v for k,v in m.items() if k not in ('id','title')}
    checks=dict(
        frozen_notebook=sha(stage/'notebook.ipynb')==spec['notebook_sha256']==receipt['notebook_sha256']=='1280a429ae410fd282deec6f2f93dd4d035a6a7655443ac95bc21731f99346c1',
        metadata_bound=sha(stage/'kernel-metadata.json')==spec['metadata_sha256']==receipt['metadata_sha256'],
        recipe_bound=new_recipe==receipt['recipe_sha256']=='2c66a0e6017f5df1c46afb6d944ba9fbe16a1d421a7843032f913a0386d0ba3b',
        only_three_original_cells_changed=len(nb['cells'])==34 and all(nb['cells'][i]==c for i,c in enumerate(base['cells']) if i not in (14,29,32)),
        exact_neural_cell_with_new_identity=c14==translate(src(nn['cells'][14])),
        exact_score_observer_with_new_identity=c29==translate(src(nn['cells'][29])),
        exact_external_component_cell=nb['cells'][32]==ab['cells'][32],
        exact_final_composed_audit=c33==expected_final,
        same_neural_configuration=recipe['configuration']==nr['configuration'],
        same_external_recipe=recipe['external_component']['recipe']==ar,
        source_component_pins=recipe['neural_component']['notebook_sha256']==sha(STAGES/'bestval_v80_tri/notebook.ipynb') and recipe['external_component']['notebook_sha256']==sha(STAGES/'adduct_extlib/notebook.ipynb'),
        source_component_recipe_pins=recipe['neural_component']['recipe_sha256']==old_recipe and recipe['external_component']['recipe_sha256']==sha(STAGES/'adduct_extlib/recipe.json'),
        exact_installed_neural_module=payload==module.read_bytes() and hashlib.sha256(payload).hexdigest()==recipe['neural_component']['module_sha256'],
        original_outsider_helper=nb['cells'][12]==base['cells'][12],
        original_latehead=nb['cells'][30:32]==base['cells'][30:32],
        original_generated_candidates=nb['cells'][11]==base['cells'][11],
        same_named_sources=clean(meta)==clean(nn_meta),
        no_obsolete_ab_audit='external_overlay_audit.json' not in auditors,
        exact_four_contracts=set(auditors)=={'batch_variant_audit.json','guarded_tail_audit.json','bestval_ensemble_audit.json','adduct_overlay_audit.json'},
        main_audits_bound_to_combo=all(auditors[k]['expected_fields']['branch']==NAME and auditors[k]['expected_fields']['recipe_sha256']==new_recipe for k in ('batch_variant_audit.json','bestval_ensemble_audit.json')),
        external_component_contract_preserved=auditors['adduct_overlay_audit.json']==next(x for x in read(STAGES/'adduct_extlib/branch_spec.json')['required_runtime_audits'] if x['name']=='adduct_overlay_audit.json'),
        final_consumer_adduct_bound='ADDUCT_OVERLAY_AUDIT' in c33 and 'EXTERNAL_OVERLAY_AUDIT' not in c33,
        standalone_reviews_passed=read(OUT/'bestval_independent_review.json')['status']=='passed' and read(OUT/'adduct_stage_canary.json')['status']=='passed',
        no_enveda_added=recipe['enveda_added'] is False,
        no_training_added=recipe['new_training'] is False)
    for c in nb['cells']:
        if c['cell_type']=='code':compile(src(c),'independent_combo_review','exec')
    checks['all_code_compiles']=True
    result=dict(status='passed' if all(checks.values()) else 'failed',checks=checks,checks_passed=sum(checks.values()),checks_total=len(checks),
                notebook_sha256=sha(stage/'notebook.ipynb'),recipe_sha256=new_recipe,read_only=True,gpu_used=False,cloud_writes=False,efficacy_claim=False)
    (OUT/'combo_independent_review.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=result['status'],passed=result['checks_passed'],total=result['checks_total'],failed=[k for k,v in checks.items() if not v])))
    if result['status']!='passed':raise SystemExit(1)


if __name__=='__main__':main()
