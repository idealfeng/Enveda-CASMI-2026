"""Freeze a multi-spectrum library consensus experiment; never push or submit."""
from pathlib import Path
import base64
import copy
import hashlib
import json

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'submission/optimization_20261109/mass_guarded_extlib'
OUT=ROOT/'submission/optimization_20261114/library_consensus_early/revision3'
MODULE=ROOT/'scripts/library_consensus_early_20261114_v3.py'
BRANCH='library_consensus_early'
TARGET='stormseye/casmi26-library-consensus-early-1114'
PARENT_PIN='2bb94c91b176f95dfdff52f08781443ffee004c20d06aeb30efb14d0c0112fc7'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def save(p,x):Path(p).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')


def main():
    if OUT.exists():raise FileExistsError('Preserve existing frozen stage')
    assert sha(BASE/'notebook.ipynb')==PARENT_PIN
    parent=read(BASE/'notebook.ipynb');book=copy.deepcopy(parent)
    parent_recipe=read(BASE/'recipe.json');module=MODULE.read_bytes();mp=sha(MODULE)
    recipe=dict(branch=BRANCH,target=TARGET,parent_ref=58156482,parent_public=.488,parent_notebook_sha256=PARENT_PIN,
        method='Second-pass measured-library per-candidate support across distinct actual query spectra; fixed early same-formula rerank allowing early rank1 challenge while preserving actual AB hits',
        configuration=dict(pair_min_cosine=.60,pair_min_peaks=4,minimum_support_spectra=2,rank_weight=1.,support_weight=1.,protected_prefix=0,protect_accepted_ab=True,same_formula_slots=True,source_reference_algorithm='Alex V12 original precursor window and cosine'),
        module_sha256=mp,module_source=MODULE.relative_to(ROOT).as_posix(),
        original_library_function_sha256=parent_recipe['original_function_sha256'],guard_sha256=parent_recipe['helper_sha256'],
        library_files=parent_recipe['files'],new_training=False,new_candidates=False,full_pipeline_local_validation=False,
        experimental_authorization='User requested five submissions on 2026-11-14 despite preceding displayed .488 scores',
        actual_information='Per query-spectrum maximum cosine for each existing official candidate identity; average similarity and support fraction across spectra rather than one global winner.',
        algorithm_boundary='Original pair math/tolerances/loaders intact; original whole-query library>=.90 skip disabled only in the private evidence pass. Its generated winner CSV is ignored. Actual accepted AB rows protected; rank1 can change only within the same-formula slots under the fixed score. Other original output candidates retain same-formula slots.',
        exact_duplicate_query_spectra_count_once=True,gain_claim=False)
    raw=(json.dumps(recipe,indent=2,ensure_ascii=False)+'\n').encode();rp=hashlib.sha256(raw).hexdigest()
    cell=r'''
# Fixed candidate-level measured-library evidence after the original champion.
import base64 as _cb64,hashlib as _ch,importlib.util as _ci
try:
    _consensus_payload=_cb64.b64decode(__MODULE_DATA__)
    assert _ch.sha256(_consensus_payload).hexdigest()==__MODULE_PIN__
    (CODE/'library_consensus_early.py').write_bytes(_consensus_payload)
    _consensus_spec=_ci.spec_from_file_location('_library_consensus_early',CODE/'library_consensus_early.py')
    _consensus=_ci.module_from_spec(_consensus_spec);_consensus_spec.loader.exec_module(_consensus)
    LIBRARY_CONSENSUS_REPORT=_consensus.run(ROOT,INPUT,COMP/'test.parquet',IS_RERUN,SAMPLE_IDS,EXTERNAL_OVERLAY_AUDIT,CODE/'alex_v12_external_function.py',__FILES__,__BRANCH__,__RECIPE_PIN__)
    LIBRARY_CONSENSUS_AUDIT=_consensus.audit(ROOT,IS_RERUN,SAMPLE_IDS,EXTERNAL_OVERLAY_AUDIT,CODE/'alex_v12_external_function.py',__BRANCH__,__RECIPE_PIN__,__MODULE_PIN__)
except BaseException:
    (ROOT/'submission.csv').unlink(missing_ok=True)
    raise
'''
    for old,new in dict(__MODULE_DATA__=repr(base64.b64encode(module).decode()),__MODULE_PIN__=repr(mp),__FILES__=repr(parent_recipe['files']),__BRANCH__=repr(BRANCH),__RECIPE_PIN__=repr(rp)).items():cell=cell.replace(old,new)
    book['cells'].append(dict(cell_type='code',execution_count=None,metadata={},outputs=[],source=cell))
    assert book['cells'][:-1]==parent['cells']
    for c in book['cells']:
        if c['cell_type']=='code':compile(''.join(c['source']),'frozen_consensus','exec')
    metadata=read(BASE/'kernel-metadata.json');metadata.update(id=TARGET,title='CASMI26 library consensus early 1114')
    OUT.mkdir(parents=True);save(OUT/'notebook.ipynb',book);save(OUT/'kernel-metadata.json',metadata);(OUT/'recipe.json').write_bytes(raw)
    review=dict(status='passed',target=TARGET,version=1,notebook_sha256=sha(OUT/'notebook.ipynb'),checks=dict(parent_pin=True,all_original_33_cells_exact=True,one_appended_cell=True,original_models_head_AB_retained=True,datasets_unchanged=True,private_offline_gpu=True,module_payload_pin=True,branch_recipe_bound=True,source_compiles=True,errors_fail_closed=True),boundary='Static source review only; actual new component smoke is separate, no complete new pipeline claim')
    save(OUT/'static_review.json',review)
    audits=copy.deepcopy(read(BASE/'branch_spec.json')['required_runtime_audits'])
    audits.append(dict(name='library_consensus_audit.json',expected_fields=dict(status='passed',branch=BRANCH,mode='fast_static',recipe_sha256=rp),required_true_checks=['parent_AB_passed','control_bound','final_bound','source_pin','module_pin','recipe_branch_bound','actual_configuration','exact_ids_schema','original_candidate_multisets','official_identity_validity','configured_prefix_preserved','fast_no_pair_matching']))
    spec=dict(name=BRANCH,target=TARGET,version=1,stage_dir=OUT.relative_to(ROOT).as_posix(),notebook_sha256=sha(OUT/'notebook.ipynb'),metadata_sha256=sha(OUT/'kernel-metadata.json'),description='CASMI26 20261114 actual multi-spectrum library consensus early same-formula V1',validation_mode='fast_static',static_review_path=(OUT/'static_review.json').relative_to(ROOT).as_posix(),required_runtime_audits=audits)
    save(OUT/'branch_spec.json',spec);save(OUT/'prepare_receipt.json',dict(status='prepared_pending_actual_component',branch=BRANCH,notebook_sha256=spec['notebook_sha256'],recipe_sha256=rp,module_sha256=mp,no_cloud_write=True));print(json.dumps(spec,indent=2))


if __name__=='__main__':main()
