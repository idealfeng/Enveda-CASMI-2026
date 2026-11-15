"""Freeze a mean-tail ablation of the champion, retaining the original AB overlay."""
from pathlib import Path
import copy, hashlib, json

ROOT = Path(__file__).resolve().parents[1]
CHAMP = ROOT/'submission/optimization_20261109/mass_guarded_extlib'
MEAN = ROOT/'submission/optimization_20261109/mass_guarded_v2mean_p7'
OUT = ROOT/'submission/optimization_20261113/head_mean_ab'
NAME = 'head_mean_ab'
TARGET = 'stormseye/casmi26-head-mean-ab-1113'
CHAMP_SHA = '2bb94c91b176f95dfdff52f08781443ffee004c20d06aeb30efb14d0c0112fc7'

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))

def write(p,x):
    Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def source(c):
    return ''.join(c['source']) if isinstance(c['source'],list) else c['source']

AUDIT = r'''
def _observe_head_mean_ab():
    import hashlib,json
    expected=__EXPECTED__
    checks={}
    digest=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    def check(name,value):
        checks[name]=bool(value)
        assert value,name
    check('original_mass_passed',BATCH_VARIANT_AUDIT.get('status')=='passed')
    check('actual_mean_tail_passed',GUARDED_TAIL_AUDIT.get('status')=='passed' and GUARDED_TAIL_AUDIT.get('score_mode')=='frozen_v2_mean' and GUARDED_TAIL_AUDIT.get('protected_prefix')==7)
    check('mean_recipe_bound',GUARDED_TAIL_AUDIT.get('recipe_sha256')==expected['mean_recipe_sha256'])
    check('original_AB_passed',EXTERNAL_OVERLAY_AUDIT.get('status')=='passed' and EXTERNAL_OVERLAY_AUDIT.get('recipe_sha256')==expected['original_ab_recipe_sha256'])
    check('mass_to_mean_control_bound',GUARDED_TAIL_AUDIT['baseline_control_sha256']==BATCH_VARIANT_AUDIT['csv_sha256'])
    check('mean_to_AB_control_bound',EXTERNAL_OVERLAY_AUDIT['control_sha256']==GUARDED_TAIL_AUDIT['csv_sha256'])
    check('actual_final_csv_bound',digest(ROOT/'submission.csv')==EXTERNAL_OVERLAY_AUDIT['csv_sha256'])
    check('mean_source_pin',digest(CODE/'guarded_v2_mean_score_20261109.py')==expected['mean_scorer_sha256'])
    frame=pd.read_csv(ROOT/'submission.csv',dtype=str,keep_default_na=False)
    check('dynamic_final_ids',list(frame.columns)==['molecule_id','smiles'] and frame.molecule_id.tolist()==SAMPLE_IDS and frame.molecule_id.is_unique)
    if IS_RERUN:
        report=json.loads((ROOT/'guarded_tail_runtime.json').read_text())
        check('actual_mean_configuration',report.get('score_mode')=='frozen_v2_mean' and report.get('protected_prefix')==7)
        check('all_upstream_hidden_full',all(a.get('mode')=='hidden_full' for a in (BATCH_VARIANT_AUDIT,GUARDED_TAIL_AUDIT,EXTERNAL_OVERLAY_AUDIT)))
        if report.get('model_invoked'):
            score_audit=json.loads((ROOT/'guarded_tail_scores.parquet.head_audit.json').read_text())
            check('actual_mean_encoder_no_learned_head',score_audit.get('role')=='frozen_v2_mean' and score_audit.get('head_applied') is False and score_audit.get('heads')==[] and score_audit.get('encoder_sha256')==expected['v2_sha256'])
        else:
            check('explicit_no_eligible',report.get('status')=='no_eligible' and report.get('eligible_candidate_rows')==0)
    else:
        check('fast_no_model',GUARDED_TAIL_AUDIT.get('scorer_executed') is False and not RUN_PIPELINE and not PIPELINE_DONE)
    audit=dict(status='passed',branch='head_mean_ab',mode='hidden_full' if IS_RERUN else 'fast_static',recipe_sha256=expected['recipe_sha256'],checks=checks,csv_sha256=digest(ROOT/'submission.csv'),mean_tail_csv_sha256=GUARDED_TAIL_AUDIT['csv_sha256'],trained_tail_heads_applied=False,mean_scorer_executed=GUARDED_TAIL_AUDIT.get('scorer_executed',False))
    (ROOT/'head_mean_ab_audit.json').write_text(json.dumps(audit,indent=2)+'\n')
    return audit
HEAD_MEAN_AB_AUDIT=_observe_head_mean_ab()
'''

def main():
    if OUT.exists():
        raise FileExistsError('Preserve immutable prepared stage')
    assert sha(CHAMP/'notebook.ipynb')==CHAMP_SHA
    mean_recipe=read(MEAN/'recipe.json')
    assert mean_recipe['configuration']['score_mode']=='frozen_v2_mean'
    assert mean_recipe['configuration']['protected_prefix']==7
    champ=read(CHAMP/'notebook.ipynb');mean=read(MEAN/'notebook.ipynb')
    assert len(champ['cells'])==33 and len(mean['cells'])==32
    assert all(source(champ['cells'][i])==source(mean['cells'][i]) for i in range(30))
    nb=copy.deepcopy(champ)
    nb['cells'][30]=copy.deepcopy(mean['cells'][30])
    nb['cells'][31]=copy.deepcopy(mean['cells'][31])
    metadata=read(CHAMP/'kernel-metadata.json')
    metadata.update(id=TARGET,title='CASMI26 mean tail with AB 1113')
    recipe=dict(branch=NAME,target=TARGET,baseline_ref=58156482,baseline_public_score=.488,
        champion_notebook_sha256=CHAMP_SHA,mean_tail_source_notebook_sha256=sha(MEAN/'notebook.ipynb'),
        mean_tail_recipe_sha256=sha(MEAN/'recipe.json'),
        method='Replace learned late-tail scores with original frozen v2 mean; retain exact AB overlay',
        protected_prefix=7,mutable_ranks='8..25, original same-formula slots',
        mean_configuration=mean_recipe['configuration'],
        original_ab_recipe_sha256=sha(CHAMP/'recipe.json'),original_ab_cell_sha256=hashlib.sha256(source(champ['cells'][32]).encode()).hexdigest(),
        original_mass_neural_generation_unchanged=True,original_AB_unchanged=True,new_training=False,new_data=False,
        previous_mean_only_ref=58155938,previous_mean_only_score=.482,
        attribution='Combined controlled late-head ablation on champion; old mean-only score before AB is not a prior result for this combination.',
        local_evidence_boundary='Targeted actual mean scorer component and saved production intermediate only; no new full E2E or efficacy claim',
        validation_mode='fast_static',user_authorized_exploration=True)
    raw=(json.dumps(recipe,ensure_ascii=False,indent=2)+'\n').encode()
    recipe_pin=hashlib.sha256(raw).hexdigest()
    expected=dict(recipe_sha256=recipe_pin,mean_recipe_sha256=sha(MEAN/'recipe.json'),original_ab_recipe_sha256=sha(CHAMP/'recipe.json'),mean_scorer_sha256=mean_recipe['configuration']['scorer_sha256'],v2_sha256='c08d2101154d057890de088be63834eb622468892a3b842512fdc5a65e02ff46')
    audit=AUDIT.replace('__EXPECTED__',repr(expected))
    nb['cells'].append(dict(cell_type='code',execution_count=None,metadata={},outputs=[],source=audit))
    for c in nb['cells']:
        if c['cell_type']=='code':
            compile(source(c),'head_mean_ab','exec');c['execution_count']=None;c['outputs']=[]
    checks=dict(exact_champion_source=True,only_original_cells30_31_replaced=all(source(nb['cells'][i])==source(champ['cells'][i]) for i in range(33) if i not in (30,31)),mean_cells_exact=all(source(nb['cells'][i])==source(mean['cells'][i]) for i in (30,31)),original_AB_exact=source(nb['cells'][32])==source(champ['cells'][32]),original_datasets_versions=metadata['dataset_sources']==read(CHAMP/'kernel-metadata.json')['dataset_sources'],original_generation_and_mass_exact=all(source(nb['cells'][i])==source(champ['cells'][i]) for i in range(30)),mean_configuration_pinned=True,source_compiles=True,private_offline_gpu=metadata['is_private'] is True and metadata['enable_internet'] is False and metadata['enable_gpu'] is True)
    assert all(checks.values())
    OUT.mkdir(parents=True)
    write(OUT/'notebook.ipynb',nb);write(OUT/'kernel-metadata.json',metadata);(OUT/'recipe.json').write_bytes(raw)
    review=dict(status='passed',target=TARGET,version=1,notebook_sha256=sha(OUT/'notebook.ipynb'),checks=checks)
    write(OUT/'static_review.json',review)
    # Each legacy observer retains its own precise recipe identity. The added
    # final observer binds the new combination and final CSV to this recipe.
    audits=copy.deepcopy(read(CHAMP/'branch_spec.json')['required_runtime_audits'])
    audits[1]=copy.deepcopy(read(MEAN/'branch_spec.json')['required_runtime_audits'][1])
    audits.append(dict(name='head_mean_ab_audit.json',expected_fields=dict(status='passed',branch=NAME,mode='fast_static',recipe_sha256=recipe_pin),required_true_checks=['original_mass_passed','actual_mean_tail_passed','mean_recipe_bound','original_AB_passed','mass_to_mean_control_bound','mean_to_AB_control_bound','actual_final_csv_bound','mean_source_pin','dynamic_final_ids','fast_no_model']))
    branch=dict(name=NAME,target=TARGET,version=1,stage_dir=OUT.relative_to(ROOT).as_posix(),notebook_sha256=review['notebook_sha256'],metadata_sha256=sha(OUT/'kernel-metadata.json'),description='CASMI26 20261113 mean-tail ablation with original AB exploratory V1',validation_mode='fast_static',static_review_path=(OUT/'static_review.json').relative_to(ROOT).as_posix(),required_runtime_audits=audits)
    write(OUT/'branch_spec.json',branch)
    write(OUT/'prepare_receipt.json',dict(status='prepared_pending_targeted_component_check',**{k:branch[k] for k in ['name','target','version','notebook_sha256','metadata_sha256']},recipe_sha256=recipe_pin))
    print(json.dumps(dict(status='prepared',branch=NAME,notebook_sha256=branch['notebook_sha256'],recipe_sha256=recipe_pin)))

if __name__=='__main__':main()
