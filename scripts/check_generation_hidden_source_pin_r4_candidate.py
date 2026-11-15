"""Check only the candidate source-pin correction against the exact startup patch."""
from pathlib import Path
import ast
import hashlib
import importlib.util
import json
import sys
import types
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'runs/generation_hidden_source_pin_r4_candidate_20261112'
OLD=ROOT/'scripts/generation_runtime_patch_20261112_r3.py'
NEW=ROOT/'scripts/generation_runtime_patch_20261112_r4_candidate.py'
ASSET=ROOT/'assets/kaggle/dmitriigluzdov/casmi26-attributed-v4g-reproduction-assets/v9/casmi26-v4b-models/code'
REPRO=ROOT/'runs/generation_hidden_source_pin_repro_20261112'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run_guard(engine_path):
    spec=importlib.util.spec_from_file_location('_r4_source_guard_candidate',NEW)
    candidate=importlib.util.module_from_spec(spec);spec.loader.exec_module(candidate)
    actual=dict(engine=engine_path,derive=ASSET/'casmi/derive.py',
                hooks_v1=ASSET/'fe_v4/hooks_v1.py',v1engine=ASSET/'fe_v4/v1engine.py')
    casmi=types.ModuleType('casmi')
    modules=dict(numpy=types.ModuleType('numpy'),casmi=casmi)
    for name,path in actual.items():
        obj=types.ModuleType(name);obj.__file__=str(path)
        if name in ('engine','derive'):
            setattr(casmi,name,obj);modules['casmi.'+name]=obj
        else:modules[name]=obj
    raised=None
    with patch.dict(sys.modules,modules):
        try:candidate.install({},OUT)
        except Exception as e:raised=dict(type=type(e).__name__,message=str(e))
    return raised


def main():
    OUT.mkdir(exist_ok=False)
    old,new=OLD.read_text(encoding='utf-8'),NEW.read_text(encoding='utf-8')
    old_pin='d914bf9d5eb56cfff434b5d53a4d55881b97697aa834a627d9932a4f8c650d27'
    new_pin='e4943fb26a8141f47ea95e744910c2d0f4746e36e72ef43e3263e7f327cfc0b5'
    # AST comparison ignores only the explanation comment and the exact pin.
    checks=dict(only_runtime_engine_pin_changed=ast.dump(ast.parse(new.replace(new_pin,old_pin)))==ast.dump(ast.parse(old)))
    original=REPRO/'original/casmi/engine.py';patched=REPRO/'patched/casmi/engine.py'
    checks['exact_production_patch_bytes']=sha(original)==old_pin and sha(patched)==new_pin
    passed=run_guard(patched)
    checks['patched_engine_passes_source_gate']=passed==dict(type='KeyError',message="'E'")
    refused=run_guard(original)
    expected=dict(type='ValueError',message='Actual generation source differs from frozen recipe')
    checks['original_engine_rejected']=refused==expected
    tampered=OUT/'tampered_engine.py';tampered.write_bytes(patched.read_bytes()+b'\n# unexpected source\n')
    checks['tampered_engine_rejected']=run_guard(tampered)==expected
    result=dict(status='passed' if all(checks.values()) else 'failed',checks=checks,
                candidate_module_sha256=sha(NEW),old_module_sha256=sha(OLD),
                accepted_runtime_engine_sha256=new_pin,original_engine_sha256=old_pin,
                expected_post_pin_fixture_stop=passed,
                no_models_libraries_or_produre_reexecution=True,no_stage_or_kaggle_write=True,
                scope='Only source gate tested. Missing E in a deliberately empty scope stops before inference; no claim of full pipeline success.')
    (OUT/'verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))
    if result['status']!='passed':raise AssertionError(checks)


if __name__=='__main__':main()
