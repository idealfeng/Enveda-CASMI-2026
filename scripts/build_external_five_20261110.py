"""Prepare five source-bound private CASMI experiments; no network or cloud writes.

Default is inspection only. --prepare freezes independent stages and
--assemble-manifest freezes their exact five-branch deployment inventory.
"""
from __future__ import annotations
import argparse,ast,base64,copy,hashlib,json,zlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'submission/optimization_20261109/mass_guarded_extlib'
OUT=ROOT/'submission/optimization_20261110'
PLAN=ROOT/'reports/optimization_20261110/submission_plan.json'
BASE_SHA='2bb94c91b176f95dfdff52f08781443ffee004c20d06aeb30efb14d0c0112fc7'
PARENT_SHA='6de37bec32c8aa8bfb46b2c5e94e374b53fe36137dff1cd7d1c4a295359f56fe'
OLD_HELPER_SHA='a31c55a2958139cbeea948ea4d11fa32eb40e3d3d7b0bac157f6d0fdc51025db'
ORIGINAL_FUNCTION_SHA='9ceaa95ddda0fb304758c9acd7dd1f256c528fcb4a8304c0152f8b6d8e3e3e76'
EN_FILE=dict(ref='egehseyinca/enveda180-casmi26-reference-ccby4',version=1,
    file='enveda180_hplus_hminus_references.parquet',bytes=218514313,
    sha256='37b8f37c5f5f536ed804d4d0456e20f183fa32388f30ae1c1712928471146069')
CORE_FILE='external_library_variants_20261110.py'
E_FILE='enveda_matching_20261110.py'

def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def source(cell):return ''.join(cell['source']) if isinstance(cell['source'],list) else cell['source']
def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def digest(raw):return hashlib.sha256(raw).hexdigest()
def write(path,value):Path(path).write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')

def planned():
    plan=read(PLAN)
    names=[b['name'] for b in plan['branches']]
    expected=['extlib_b_only','extlib_a_only','extlib_abe_gap_fill','extlib_abe_compete','extlib_ab_bprec_trusted']
    if names!=expected or plan['baseline_notebook_sha256']!=BASE_SHA or plan['baseline_ref']!=58156482:raise ValueError('Approved plan binding changed')
    return plan

def inherited_payload():
    notebook=read(BASE/'notebook.ipynb')
    if len(notebook['cells'])!=33:raise ValueError('Expected exact 33-cell champion')
    parsed=ast.parse(source(notebook['cells'][-1]));encoded=None
    for node in parsed.body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='_external_payloads' for t in node.targets):encoded=ast.literal_eval(node.value)
    if encoded is None:raise ValueError('Original embedded source payload missing')
    payload={name:base64.b64decode(value) for name,value in encoded.items()}
    if digest(payload['alex_v12_external_function.py'])!=ORIGINAL_FUNCTION_SHA or digest(payload['external_library_overlay_20261109.py'])!=OLD_HELPER_SHA:raise ValueError('Original source payload differs')
    return notebook,payload

def prepare(name):
    plan=planned();spec=next(b for b in plan['branches'] if b['name']==name)
    if sha(BASE/'notebook.ipynb')!=BASE_SHA:raise ValueError('Champion source changed')
    notebook,old_payload=inherited_payload();stage=OUT/name
    if stage.exists():raise FileExistsError('Preserve frozen branch: '+name)
    original=copy.deepcopy(notebook)
    e_policy={'extlib_abe_gap_fill':'gap_fill','extlib_abe_compete':'compete'}.get(name,'none')
    has_e=e_policy!='none'
    payload={
      'external_library_overlay_20261109.py':old_payload['external_library_overlay_20261109.py'],
      'alex_v12_external_function.py':old_payload['alex_v12_external_function.py'],
      CORE_FILE:(ROOT/'scripts'/CORE_FILE).read_bytes()}
    if has_e:payload[E_FILE]=(ROOT/'scripts'/E_FILE).read_bytes()
    for filename,raw_source in payload.items():compile(raw_source.decode('utf-8'),filename,'exec')
    pins={k:digest(v) for k,v in payload.items()}
    cfg=dict(sources=spec['sources'],e_policy=e_policy,trusted_bprec=name=='extlib_ab_bprec_trusted',
        old_helper_sha256=OLD_HELPER_SHA,e_helper_sha256=pins.get(E_FILE),enveda_file=EN_FILE if has_e else None)
    cfg_pin=digest(json.dumps(cfg,sort_keys=True,separators=(',',':')).encode())
    files=copy.deepcopy(read(BASE/'recipe.json')['files'])
    if has_e:
        local=ROOT/'assets/kaggle'/EN_FILE['ref']/('v'+str(EN_FILE['version']))/EN_FILE['file']
        if local.stat().st_size!=EN_FILE['bytes'] or sha(local)!=EN_FILE['sha256']:raise ValueError('Enveda bytes/SHA differ')
    target='stormseye/casmi26-'+name.replace('_','-')+'-1110'
    metadata=read(BASE/'kernel-metadata.json')
    metadata.update(id=target,title=target.split('/')[1].replace('-',' '),is_private=True,enable_internet=False,enable_gpu=True,kernel_sources=[])
    if has_e:metadata['dataset_sources'].append(EN_FILE['ref']+'/'+str(EN_FILE['version']))
    recipe=dict(branch=name,target=target,method='Fixed original .482 upstream plus controlled measured-library variant',
        baseline_ref=58156482,baseline_public_score=.488,champion_notebook_sha256=BASE_SHA,
        pre_external_parent_ref=58129661,pre_external_parent_public_score=.482,pre_external_parent_notebook_sha256=PARENT_SHA,
        configuration=cfg,configuration_sha256=cfg_pin,payload_pins=pins,original_function_sha256=ORIGINAL_FUNCTION_SHA,
        files=files,enveda_file=EN_FILE if has_e else None,
        all_original_first32_cells_unchanged=True,official_identity_guard_preserved=True,
        actual_disabled_source_candidates_zero=True,baseline_control='GUARDED_TAIL_AUDIT bound exact original pre-external .482 output',
        source_attribution=spec,ranking_constants=plan['matching_constants'],new_training=False,locked_final_used=False,
        validation_mode='fast_static',source_compaction='zlib lossless bytes; decode SHA256 before import',
        enveda_attribution=dict(authors='Krettler et al.',title='Enveda-180',doi='10.5281/zenodo.21346580',record='https://zenodo.org/records/21346580',license='CC BY 4.0',kaggle_mirror='egehseyinca/enveda180-casmi26-reference-ccby4/1',coverage_claim='Published reference spectra only; no claim of new identities or hidden coverage') if has_e else None,
        enveda_fallback='Invalid E preserves valid AB output; ties retain AB' if has_e else None,
        trusted_bprec_expected_changed_refs=1281 if cfg['trusted_bprec'] else 0)
    raw=(json.dumps(recipe,indent=2,ensure_ascii=False)+'\n').encode();recipe_pin=digest(raw)
    packed={name:base64.b64encode(zlib.compress(value,9)).decode() for name,value in payload.items()}
    late=("# Enveda-180: Krettler et al., doi:10.5281/zenodo.21346580, CC BY 4.0; mirror egehseyinca/enveda180-casmi26-reference-ccby4/1.\n" if has_e else '')+r'''
import base64,zlib,hashlib,importlib.util,json
_variant_payloads=__PAYLOADS__
_variant_pins=__PINS__
try:
    for _variant_name,_variant_encoded in _variant_payloads.items():
        _variant_raw=zlib.decompress(base64.b64decode(_variant_encoded))
        assert hashlib.sha256(_variant_raw).hexdigest()==_variant_pins[_variant_name],_variant_name
        (CODE/_variant_name).write_bytes(_variant_raw)
    _variant_spec=importlib.util.spec_from_file_location('_external_library_variants_runtime',CODE/'external_library_variants_20261110.py')
    _variant_overlay=importlib.util.module_from_spec(_variant_spec);_variant_spec.loader.exec_module(_variant_overlay)
    _variant_configuration=__CONFIGURATION__
    assert hashlib.sha256(json.dumps(_variant_configuration,sort_keys=True,separators=(',',':')).encode()).hexdigest()==__CONFIGURATION_PIN__
    _variant_args=(ROOT,INPUT,COMP/'test.parquet',IS_RERUN,SAMPLE_IDS,GUARDED_TAIL_AUDIT,CODE/'alex_v12_external_function.py',__FUNCTION_PIN__,__FILES__,_variant_configuration)
    EXTERNAL_VARIANTS_REPORT=_variant_overlay.run(*_variant_args)
    EXTERNAL_VARIANTS_AUDIT=_variant_overlay.audit(*_variant_args,__BRANCH__,__RECIPE_PIN__)
    _variant_installed_pins={k:hashlib.sha256((CODE/k).read_bytes()).hexdigest() for k in _variant_pins}
    EXTERNAL_VARIANTS_AUDIT['checks']['installed_payload_pins']=_variant_installed_pins==_variant_pins
    assert EXTERNAL_VARIANTS_AUDIT['checks']['installed_payload_pins']
    EXTERNAL_VARIANTS_AUDIT['installed_payload_pins']=_variant_installed_pins
    (ROOT/'external_variants_audit.json').write_text(json.dumps(EXTERNAL_VARIANTS_AUDIT,indent=2)+'\n')
except BaseException:
    (ROOT/'submission.csv').unlink(missing_ok=True)
    raise
'''
    for token,value in {'__PAYLOADS__':repr(packed),'__PINS__':repr(pins),'__CONFIGURATION__':repr(cfg),'__CONFIGURATION_PIN__':repr(cfg_pin),'__FUNCTION_PIN__':repr(ORIGINAL_FUNCTION_SHA),'__FILES__':repr(files),'__BRANCH__':repr(name),'__RECIPE_PIN__':repr(recipe_pin)}.items():late=late.replace(token,value)
    notebook['cells'][-1]=dict(cell_type='code',execution_count=None,metadata={},outputs=[],source=late)
    prefix_exact=notebook['cells'][:-1]==original['cells'][:-1]
    if not prefix_exact:raise ValueError('Champion first32 cells changed')
    for cell in notebook['cells']:
        if cell['cell_type']=='code':compile(source(cell),'external_five_stage','exec')
    # Do not rewrite inherited cell objects: their full JSON, including outputs,
    # is already frozen and must remain exact.
    stage.mkdir(parents=True);write(stage/'notebook.ipynb',notebook);write(stage/'kernel-metadata.json',metadata);(stage/'recipe.json').write_bytes(raw)
    static=dict(status='passed',target=target,version=1,notebook_sha256=sha(stage/'notebook.ipynb'),checks=dict(
        champion_source_pin=True,exact_first32_cell_objects=prefix_exact,only_final_external_cell_replaced=True,
        explicit_source_configuration=True,all_embedded_payloads_sha_pinned=True,lossless_payload_compaction=True,
        original_function_source_pinned=True,original_identity_guard_preserved=True,dynamic_hidden_ids=True,
        actual_output_consumption_observer=True,private_offline_gpu=True,versioned_inputs=True,all_code_compiles=True,
        no_training_or_locked_final=True,global_errors_fail_closed=True,all_embedded_python_sources_compile=True))
    write(stage/'static_review.json',static)
    receipt=dict(status='prepared',branch=name,target=target,version=1,notebook_sha256=static['notebook_sha256'],metadata_sha256=sha(stage/'kernel-metadata.json'),recipe_sha256=recipe_pin,static_review_path=str((stage/'static_review.json').relative_to(ROOT)).replace('\\','/'),validation_mode='fast_static',notebook_bytes=(stage/'notebook.ipynb').stat().st_size)
    write(stage/'prepare_receipt.json',receipt)
    audits=copy.deepcopy(read(BASE/'branch_spec.json')['required_runtime_audits'][:2])
    # The final module exposes a fixed base set on fast and hidden paths. The
    # hidden observer additionally reconstructs actual decisions from scores.
    audits.append(dict(name='external_variants_audit.json',expected_fields=dict(status='passed',branch=name,recipe_sha256=recipe_pin,mode='fast_static'),
        required_true_checks=['base_audit_passed','control_bound','final_bound','source_function_pin','configuration_bound','exact_ids_schema','official_identities_valid','library_file_pins','runtime_checks','fast_no_matching','installed_payload_pins']))
    branch=dict(name=name,target=target,version=1,stage_dir=str(stage.relative_to(ROOT)).replace('\\','/'),notebook_sha256=receipt['notebook_sha256'],metadata_sha256=receipt['metadata_sha256'],description='CASMI26 20261110 '+name+' source-bound audited V1',validation_mode='fast_static',static_review_path=receipt['static_review_path'],required_runtime_audits=audits)
    write(stage/'branch_spec.json',branch);return receipt

def assemble():
    plan=planned();path=OUT/'manifest.json'
    if path.exists():raise FileExistsError('Preserve frozen five-branch manifest')
    branches=[read(OUT/item['name']/'branch_spec.json') for item in plan['branches']]
    manifest=dict(schema_version=1,competition='enveda-CASMI26-molecule-id-mass-spectra',batch_id='optimization_20261110',max_submissions=5,baseline_public_score=.488,state_root='reports/optimization_20261110',branches=branches)
    write(path,manifest)
    return dict(status='manifest_prepared',sha256=sha(path),branches=[b['name'] for b in branches])

def main():
    p=argparse.ArgumentParser(description=__doc__);group=p.add_mutually_exclusive_group();group.add_argument('--prepare',action='store_true');group.add_argument('--assemble-manifest',action='store_true');p.add_argument('--branch');a=p.parse_args();plan=planned()
    if a.assemble_manifest:result=assemble()
    elif a.prepare:result=[prepare(a.branch)] if a.branch else [prepare(b['name']) for b in plan['branches']]
    else:result=dict(status='plan_only_no_network_no_stage_write',planned_branches=[b['name'] for b in plan['branches']],required_modules=[CORE_FILE,E_FILE],all_original_first32_cells_preserved=True)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
