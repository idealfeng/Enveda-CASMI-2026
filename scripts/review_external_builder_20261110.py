"""Review staged source/config bindings in a disposable D fixture, without cloud."""
from pathlib import Path
import ast,base64,hashlib,json,sys,tempfile,zlib
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import build_external_five_20261110 as build
import kaggle_batch as batch

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))

def main():
    source_before={str(p.relative_to(ROOT)):sha(p) for p in [build.BASE/'notebook.ipynb',build.BASE/'recipe.json',build.BASE/'kernel-metadata.json',ROOT/'reports/improvement_ledger.json',ROOT/'reports/IMPROVEMENT_LEDGER.md']}
    checks={};details={}
    with tempfile.TemporaryDirectory(prefix='build-five-',dir=ROOT/'.cache/tmp') as temp:
        folder=Path(temp)
        with patch.object(build,'OUT',folder):
            for item in build.planned()['branches']:
                name=item['name'];prepared=build.prepare(name);stage=folder/name
                nb=read(stage/'notebook.ipynb');old=read(build.BASE/'notebook.ipynb');recipe=read(stage/'recipe.json');metadata=read(stage/'kernel-metadata.json');spec=read(stage/'branch_spec.json')
                tree=ast.parse(build.source(nb['cells'][-1]));values={}
                for node in tree.body:
                    if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name):
                        try:values[node.targets[0].id]=ast.literal_eval(node.value)
                        except (ValueError,TypeError):pass
                packed=values['_variant_payloads'];pins=values['_variant_pins']
                actual={k:hashlib.sha256(zlib.decompress(base64.b64decode(v))).hexdigest() for k,v in packed.items()}
                cfg=recipe['configuration'];has_e='E' in item['sources']
                branch_checks=dict(exact_first32_objects=nb['cells'][:-1]==old['cells'][:-1],last_cell_only=len(nb['cells'])==33,
                    source_bound=sha(stage/'notebook.ipynb')==prepared['notebook_sha256']==spec['notebook_sha256'],metadata_bound=sha(stage/'kernel-metadata.json')==spec['metadata_sha256'],
                    source_payload_pins=actual==pins==recipe['payload_pins'],explicit_sources=cfg['sources']==item['sources'],
                    e_policy=cfg['e_policy']==({'extlib_abe_gap_fill':'gap_fill','extlib_abe_compete':'compete'}.get(name,'none')),
                    bprec_flag=cfg['trusted_bprec']==(name=='extlib_ab_bprec_trusted'),
                    only_e_uses_e_module=('enveda_matching_20261110.py' in packed)==has_e,
                    e_dependency=('egehseyinca/enveda180-casmi26-reference-ccby4/1' in metadata['dataset_sources'])==has_e,
                    observer_recipe_pin=spec['required_runtime_audits'][-1]['expected_fields']['recipe_sha256']==sha(stage/'recipe.json'),
                    original_function_pin=actual['alex_v12_external_function.py']==build.ORIGINAL_FUNCTION_SHA,
                    old_guard_pin=actual['external_library_overlay_20261109.py']==build.OLD_HELPER_SHA,
                    private_offline=metadata['is_private'] is True and metadata['enable_internet'] is False and metadata['enable_gpu'] is True,
                    actual_source_consumption_calls='EXTERNAL_VARIANTS_REPORT=_variant_overlay.run(*_variant_args)' in build.source(nb['cells'][-1]) and 'EXTERNAL_VARIANTS_AUDIT=_variant_overlay.audit' in build.source(nb['cells'][-1]),
                    error_deletes_final="(ROOT/'submission.csv').unlink(missing_ok=True)" in build.source(nb['cells'][-1]))
                if has_e:branch_checks['e_credit']='10.5281/zenodo.21346580' in recipe['enveda_attribution']['doi'] and 'CC BY 4.0' in build.source(nb['cells'][-1])
                checks.update({name+':'+k:v for k,v in branch_checks.items()});details[name]=dict(checks=branch_checks,notebook_bytes=prepared['notebook_bytes'])
                try:build.prepare(name)
                except FileExistsError:checks[name+':never_overwrites_stage']=True
                else:checks[name+':never_overwrites_stage']=False
            assembled=build.assemble();manifest=batch.load_manifest(folder/'manifest.json')
            checks['exact_five_manifest']=len(manifest['branches'])==5 and [b['name'] for b in manifest['branches']]==[b['name'] for b in build.planned()['branches']]
            checks['competition_baseline']=manifest['competition']==batch.COMPETITION and manifest['baseline_public_score']==.488
            for br in manifest['branches']:batch.local_preflight(manifest,br)
            checks['actual_engine_preflight']=True
            try:build.assemble()
            except FileExistsError:checks['never_overwrites_manifest']=True
            else:checks['never_overwrites_manifest']=False
    checks['originals_and_real_ledger_unchanged']=all(sha(ROOT/p)==pin for p,pin in source_before.items())
    result=dict(status='passed' if all(checks.values()) else 'failed',checks=checks,branches=details,new_cloud_or_submission_write=False,disposable_d_fixture=True,
        builder_sha256=sha(ROOT/'scripts/build_external_five_20261110.py'))
    out=ROOT/'reports/external_builder_review_20261110';out.mkdir(exist_ok=True)
    (out/'verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=result['status'],checks_passed=sum(checks.values()),checks_total=len(checks),failed=[k for k,v in checks.items() if not v])))
    if result['status']!='passed':raise ValueError('Builder fixtures failed')

if __name__=='__main__':main()
