"""Freeze one user-authorized exploratory public N1c overlay on the exact .488 parent."""
from pathlib import Path
import base64
import copy
import hashlib
import json

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'submission/optimization_20261109/mass_guarded_extlib'
OUT=ROOT/'submission/optimization_20261113/spectral_network_explore/revision2'
MODULE=ROOT/'scripts/spectral_network_explore_20261113.py'
SOURCE=ROOT/'reports/optimization_20261113/public_short/analyticaobscura__casmi-2026/cells/24.py'
TARGET='stormseye/casmi26-spectral-network-1113'
BRANCH='spectral_network_explore'
CHAMPION='2bb94c91b176f95dfdff52f08781443ffee004c20d06aeb30efb14d0c0112fc7'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def save(p,v):Path(p).write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')

def main():
    if OUT.exists():raise FileExistsError('Preserve frozen exploratory stage')
    assert sha(BASE/'notebook.ipynb')==CHAMPION
    parent=read(BASE/'notebook.ipynb');book=copy.deepcopy(parent)
    module=MODULE.read_bytes();source=SOURCE.read_bytes()
    mp,sp=sha(MODULE),sha(SOURCE)
    assert sp=='8150955a1f0a617639253bd59cca9c186c6e881ebc7f15447682c0e3df7de768'
    recipe=dict(branch=BRANCH,target=TARGET,parent_ref=58156482,parent_public=.488,parent_notebook_sha256=CHAMPION,
        method='Public N1c target-target modified-cosine graph and candidate-fingerprint neighbour agreement after complete original .488 AB output',
        configuration=dict(lam=.25,tau=.6,matched_peaks=6,protect_original_library=.9,protect_accepted_ab=True,scope='post_AB_original_candidates'),
        module_sha256=mp,public_source_sha256=sp,source_url='https://www.kaggle.com/code/analyticaobscura/casmi-2026',
        source_local=SOURCE.relative_to(ROOT).as_posix(),module_local=MODULE.relative_to(ROOT).as_posix(),
        original_cells_unchanged=len(parent['cells']),new_training=False,new_candidates=False,
        experiment_type='user_authorized_speculative_submission',
        previous_fixed_policy_evidence='Old exposed Flex48: -0.00278 MRR25; not exact .488 and not clean CV. No coefficient or policy tuning follows.',
        gain_claim=False,full_pipeline_local_validation=False,
        execution_scope='Existing full .488 parent unchanged, then actual target spectra only; strong reference rows retain exact lists.')
    raw=(json.dumps(recipe,indent=2,ensure_ascii=False)+'\n').encode();rp=hashlib.sha256(raw).hexdigest()
    cell=r'''
# Fixed public target-target network exploration after the original .488 head + AB.
import base64 as _nb64,hashlib as _nh,importlib.util as _ni
try:
    _network_module=_nb64.b64decode(__MODULE_DATA__)
    _network_source=_nb64.b64decode(__SOURCE_DATA__)
    assert _nh.sha256(_network_module).hexdigest()==__MODULE_PIN__
    assert _nh.sha256(_network_source).hexdigest()==__SOURCE_PIN__
    (CODE/'spectral_network_explore.py').write_bytes(_network_module)
    (CODE/'public_n1c_frozen.py').write_bytes(_network_source)
    _network_spec=_ni.spec_from_file_location('_spectral_network_exploration',CODE/'spectral_network_explore.py')
    _network=_ni.module_from_spec(_network_spec);_network_spec.loader.exec_module(_network)
    SPECTRAL_NETWORK_REPORT=_network.run(ROOT,INPUT,COMP/'test.parquet',IS_RERUN,SAMPLE_IDS,EXTERNAL_OVERLAY_AUDIT,CODE/'public_n1c_frozen.py',__SOURCE_PIN__,__BRANCH__,__RECIPE_PIN__)
    SPECTRAL_NETWORK_AUDIT=_network.audit(ROOT,IS_RERUN,SAMPLE_IDS,EXTERNAL_OVERLAY_AUDIT,CODE/'public_n1c_frozen.py',__SOURCE_PIN__,__BRANCH__,__RECIPE_PIN__,__MODULE_PIN__)
except BaseException:
    (ROOT/'submission.csv').unlink(missing_ok=True)
    raise
'''
    for k,v in dict(__MODULE_DATA__=repr(base64.b64encode(module).decode()),__SOURCE_DATA__=repr(base64.b64encode(source).decode()),
        __MODULE_PIN__=repr(mp),__SOURCE_PIN__=repr(sp),__BRANCH__=repr(BRANCH),__RECIPE_PIN__=repr(rp)).items():cell=cell.replace(k,v)
    book['cells'].append(dict(cell_type='code',execution_count=None,metadata={},outputs=[],source=cell))
    assert book['cells'][:-1]==parent['cells']
    for c in book['cells']:
        if c['cell_type']=='code':compile(''.join(c['source']),'frozen_network_stage','exec')
    metadata=read(BASE/'kernel-metadata.json');metadata.update(id=TARGET,title='CASMI26 spectral network explore 1113')
    OUT.mkdir(parents=True);save(OUT/'notebook.ipynb',book);save(OUT/'kernel-metadata.json',metadata);(OUT/'recipe.json').write_bytes(raw)
    review=dict(status='passed',target=TARGET,version=1,notebook_sha256=sha(OUT/'notebook.ipynb'),checks=dict(exact_parent_pin=True,all_original_cells_unchanged=True,
        original_head_AB_retained=True,only_one_appended_cell=True,original_dataset_pins_retained=True,
        private_offline_gpu=True,source_payload_pinned=True,source_compiles=True,errors_fail_closed=True),
        boundary='Static stage review; existing component evidence is not a new complete model/pipeline run.')
    save(OUT/'static_review.json',review)
    audits=copy.deepcopy(read(BASE/'branch_spec.json')['required_runtime_audits'])
    audits.append(dict(name='spectral_network_audit.json',expected_fields=dict(status='passed',branch=BRANCH,mode='fast_static',recipe_sha256=rp),
        required_true_checks=['base_ab_passed','control_bound','final_bound','module_pin','public_source_pin','configuration_exact','recipe_branch_bound',
            'sample_ids_exact','candidate_multisets','official_identities','fast_no_network']))
    spec=dict(name=BRANCH,target=TARGET,version=1,stage_dir=OUT.relative_to(ROOT).as_posix(),notebook_sha256=sha(OUT/'notebook.ipynb'),
        metadata_sha256=sha(OUT/'kernel-metadata.json'),description='CASMI26 20261113 fixed public N1c post-AB protected speculative V1',
        validation_mode='fast_static',static_review_path=(OUT/'static_review.json').relative_to(ROOT).as_posix(),required_runtime_audits=audits)
    save(OUT/'branch_spec.json',spec)
    receipt=dict(status='prepared_pending_component_smoke',notebook_sha256=spec['notebook_sha256'],metadata_sha256=spec['metadata_sha256'],
        recipe_sha256=rp,module_sha256=mp,source_sha256=sp,parent_sha256=CHAMPION,no_cloud_write=True)
    save(OUT/'prepare_receipt.json',receipt);print(json.dumps(receipt,indent=2))

if __name__=='__main__':main()
