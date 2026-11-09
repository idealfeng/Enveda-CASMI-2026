"""Read-only source/payload and actual observer checks for no-Na two-head stage."""
from pathlib import Path
import ast
import base64
import hashlib
import json
import sys
import zlib

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))


def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def source(c):return ''.join(c['source']) if isinstance(c['source'],list) else c['source']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def installer_payloads(nb):
    function=next(n for n in ast.parse(source(nb['cells'][14])).body
                  if isinstance(n,ast.FunctionDef) and n.name=='_install_candidate_head')
    values={}
    for n in function.body:
        if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name):
            try:values[n.targets[0].id]=ast.literal_eval(n.value)
            except (ValueError,TypeError):pass
    return {k:base64.b64decode(v) for k,v in values['payloads'].items()},values['pins']


def main():
    import review_head_observers_20261108 as fixtures
    from kaggle_batch import load_manifest,local_preflight
    stage=ROOT/'submission/optimization_20261108/mass_heads_only_compact'
    output=ROOT/'reports/heads_only_stage_review_20261108'
    output.mkdir(parents=True,exist_ok=False)
    nb=read(stage/'notebook.ipynb');baseline=read(ROOT/'submission/aggressive_20261107/public_mass_repro/notebook.ipynb')
    paired=read(ROOT/'submission/optimization_20261108/mass_heads_na_compact/notebook.ipynb')
    before=sha(stage/'notebook.ipynb');receipt=read(stage/'prepare_receipt.json');recipe=read(stage/'recipe.json')
    spec=read(stage/'branch_spec.json');metadata=read(stage/'kernel-metadata.json')
    tree=ast.parse(source(nb['cells'][11]));packed=ast.literal_eval(tree.body[1].value.args[0].args[0])
    original=zlib.decompress(base64.b64decode(packed)).decode('utf-8')
    compile(original,'lossless_baseline_sources','exec')
    payloads,pins=installer_payloads(nb);old_payloads,_=installer_payloads(paired)
    runtime=json.loads(payloads['learned_head_runtime.json'])
    meta_keys=['is_private','enable_internet','enable_gpu','competition_sources','dataset_sources','kernel_sources','model_sources']
    base_metadata=read(ROOT/'submission/aggressive_20261107/public_mass_repro/kernel-metadata.json')
    checks=dict(
        receipt_notebook_pin=before==receipt['notebook_sha256'],
        compact_under_1MiB=(stage/'notebook.ipynb').stat().st_size<1048576,
        compact_decodes_exact_baseline_sources=original==source(baseline['cells'][11]),
        no_added_na_module=all(token not in original for token in ('gl_na_hook.py','gl_counted_runner.py','mass_gl_na_counted_hook')),
        all_other_original_cells_unchanged=all(source(a)==source(b) for i,(a,b) in enumerate(zip(baseline['cells'],nb['cells'])) if i not in (11,14,29)),
        public_baseline_and_na_free_recipe=recipe['combined_real_na_gl'] is False and recipe['source_stage'].replace('\\','/')=='submission/aggressive_20261107/public_mass_repro',
        exact_same_trained_two_head_payloads=payloads==old_payloads,
        exact_same_trained_head_installer=source(nb['cells'][14])==source(paired['cells'][14]),
        payload_hashes_match=all(hashlib.sha256(raw).hexdigest()==pins[name] for name,raw in payloads.items()),
        two_fixed_heads=len(runtime['heads'])==2 and runtime['required_step']==2500,
        original_metadata_assets=all(metadata.get(k)==base_metadata.get(k) for k in meta_keys),
        unique_slug_title=metadata['id']=='stormseye/casmi26-mass-heads-only-compact-1108' and metadata['title']==metadata['id'].split('/')[1].replace('-',' '),
        no_na_runtime_audit=not any(x['name']=='na_variant_audit.json' for x in spec['required_runtime_audits']))
    for h in runtime['heads']:
        p=ROOT/'runs/candidate_head_20261108'/h['file']
        checks['original_frozen_weight_'+h['file']]=sha(p)==h['sha256']==hashlib.sha256(payloads[h['file']]).hexdigest()
    for c in nb['cells']:
        if c['cell_type']=='code':compile(source(c),'no_na_stage','exec')
    checks['all_code_compiles']=True
    manifest=dict(schema_version=1,batch_id='heads_only_review_20261108',competition='enveda-CASMI26-molecule-id-mass-spectra',max_submissions=1,state_root='reports/heads_only_stage_review_20261108/batch_state',branches=[spec])
    manifest_path=output/'review_manifest.json';manifest_path.write_text(json.dumps(manifest,indent=2))
    loaded=load_manifest(manifest_path);local_preflight(loaded,spec);checks['batch_local_preflight']=True
    fast=fixtures.fixture(stage,'fast');hidden=fixtures.fixture(stage,'hidden');optional=fixtures.fixture(stage,'hidden',outsider=False)
    failures=('bad_coverage','bad_query_coverage','bad_encoder','bad_head_receipt','bad_output_hash','bad_evidence_hash','bad_query_hash','bad_row_count','bad_error_scope','head_not_applied','bad_status','corrupt_adapter','corrupt_checkpoint','corrupt_original','corrupt_runtime','bad_outsider_coverage')
    rejected={name:fixtures.fixture(stage,'hidden',name) for name in failures}
    checks.update(actual_fast=fast['accepted'],actual_hidden_main_outside=hidden['accepted'],actual_optional_skip=optional['accepted'])
    checks.update({name+'_rejected':not value['accepted'] for name,value in rejected.items()})
    checks['stage_bytes_unchanged']=sha(stage/'notebook.ipynb')==before
    result=dict(status='passed' if all(checks.values()) else 'failed',checks=checks,checks_passed=sum(checks.values()),checks_total=len(checks),notebook_sha256=before,
        source_bytes=(stage/'notebook.ipynb').stat().st_size,fast=fast,hidden=hidden,optional=optional,rejected=rejected,
        actual_trained_pair_inference_reuse='reports/learned_head_stage_actual_inference_20261108/verification.json: identical scorer/model/checkpoint/runtime payloads; no new numerical code',
        no_gpu_training_or_cloud_calls=True)
    (output/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['status','checks_passed','checks_total','notebook_sha256','source_bytes']}))
    if not all(checks.values()):raise SystemExit(1)


if __name__=='__main__':main()
