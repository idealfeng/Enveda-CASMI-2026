"""Check r3 audit path repair in actual p2s_code layout; reuse existing inference only."""
from pathlib import Path
import hashlib
import json
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
STAGE=ROOT/'submission/optimization_20261112/generation_expand/revision3'
OLD_STAGE=ROOT/'submission/optimization_20261112/generation_expand/revision2'
BASE=ROOT/'submission/optimization_20261109/mass_guarded_extlib'


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def src(cell):return ''.join(cell['source']) if isinstance(cell['source'],list) else cell['source']
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):Path(path).write_text(json.dumps(value,indent=2)+'\n')


def main():
    out=ROOT/'runs/generation_recovery_r3_20261112'
    out.mkdir(exist_ok=False)
    root=out;code=root/'p2s_code';code.mkdir()
    old=read(BASE/'notebook.ipynb');book=read(STAGE/'notebook.ipynb');recipe=read(STAGE/'recipe.json')
    old_recipe=read(OLD_STAGE/'recipe.json')
    calls=[]
    def original_run_stage(args,log,name,quiet=None):
        calls.append([str(x) for x in args]);return 19
    scope=dict(ROOT=root,CODE=code,Path=Path,run_stage=original_run_stage)
    setup=src(book['cells'][12])[len(src(old['cells'][12])):]
    exec(compile(setup,'exact_staged_r3_setup','exec'),scope)
    from build_generation_variant_20261112_r3 import original_runner
    (code/'runner.py').write_bytes(original_runner(old).encode())
    scope['run_stage']([sys.executable,code/'runner.py','frozen_original.ipynb','pin',root],root/'pipeline.log','Public 0.465 pipeline')
    launch=read(root/'generation_launch.json')
    (root/'generation_launch.json').unlink()
    (root/'submission.csv').write_text('molecule_id,smiles\ncanary,C\n')
    scope.update(hashlib=hashlib,IS_RERUN=False,SAMPLE_IDS=['canary'],
                 EXTERNAL_OVERLAY_AUDIT=dict(status='passed',csv_sha256=sha(root/'submission.csv')))
    exec(compile(src(book['cells'][-1]),'exact_staged_r3_fast_final','exec'),scope)
    fast=scope['GENERATION_VARIANT_AUDIT']
    checks=dict(p2s_code_actual_layout=code.name=='p2s_code' and not (root/'code').exists(),
                original_runner_preserved=sha(code/'runner.py')==recipe['original_runner_sha256'],
                runner_actual_routing=calls[0][1]==str(code/'generation_runner.py'),
                runner_unchanged=recipe['runner_sha256']==old_recipe['runner_sha256']==sha(code/'generation_runner.py'),
                installed_module_actual_CODE=sha(code/'generation_runtime_patch_20261112.py')==recipe['module_sha256'],
                fast_final_passed=fast['status']=='passed' and all(fast['checks'].values()),
                original_other32_cells=[i for i,(a,b) in enumerate(zip(old['cells'],book['cells'])) if a!=b]==[12])
    old_module=(ROOT/'scripts/generation_runtime_patch_20261112.py').read_text(encoding='utf-8')
    new_module=(ROOT/'scripts/generation_runtime_patch_20261112_r3.py').read_text(encoding='utf-8')
    checks['all_inference_functions_byte_exact']=old_module.split('\ndef audit(',1)[0]==new_module.split('\ndef audit(',1)[0]
    # Fixture reuses actual revision2 runtime and ranked CSV without model execution.
    real=ROOT/'runs/generation_prod_canary_20261112_actual_revision2'
    shutil.copy2(real/'generation_runtime.json',root/'generation_runtime.json')
    shutil.copy2(real/'submission.csv',root/'submission.csv')
    write(root/'generation_launch.json',launch)
    runtime=read(root/'generation_runtime.json')
    scope.update(IS_RERUN=True,SAMPLE_IDS=runtime['processed_ids'],
                 EXTERNAL_OVERLAY_AUDIT=dict(status='passed',csv_sha256=sha(root/'submission.csv')))
    exec(compile(src(book['cells'][-1]),'exact_staged_r3_hidden_audit_fixture','exec'),scope)
    hidden=scope['GENERATION_VARIANT_AUDIT']
    checks['hidden_audit_fixture_passed']=hidden['status']=='passed' and all(hidden['checks'].values())
    checks['launch_and_module_directory_bound']=hidden['checks']['actual_runner_path'] is True
    checks['actual_runtime_reused_unmodified']=sha(root/'generation_runtime.json')==sha(real/'generation_runtime.json')
    write(out/'hidden_audit_fixture_receipt.json',hidden)
    bad=dict(launch,actual_runner=str(root/'wrong_directory/generation_runner.py'))
    write(root/'generation_launch.json',bad)
    rejected=False
    try:exec(compile(src(book['cells'][-1]),'r3_bad_launch_path','exec'),scope)
    except ValueError:rejected=True
    checks['wrong_launch_path_rejected_no_final']=rejected and not (root/'submission.csv').exists()
    result=dict(status='passed' if all(checks.values()) else 'failed',checks=checks,
        checks_passed=sum(checks.values()),checks_total=len(checks),notebook_sha256=sha(STAGE/'notebook.ipynb'),
        module_sha256=recipe['module_sha256'],runner_sha256=recipe['runner_sha256'],
        reused_actual_inference_evidence='runs/generation_prod_canary_20261112_actual_revision2/verification.json',
        no_model_or_large_library_loaded=True,no_produre_rerun=True,no_kaggle_write=True,
        hidden_fixture_scope='Real unchanged revision2 runtime/ranked CSV; constructed AB audit and launch receipt exercise path validation only, not a full pipeline or new model run')
    write(out/'verification.json',result);print(json.dumps(result,indent=2))
    if not all(checks.values()):raise AssertionError(checks)


if __name__=='__main__':main()
