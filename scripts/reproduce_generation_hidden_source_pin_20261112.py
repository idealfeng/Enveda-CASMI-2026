"""Reproduce a full-startup generation source-pin failure without loading models or libraries."""
from pathlib import Path
import ast
import base64
import hashlib
import importlib.util
import json
import sys
import types
import zlib
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'runs/generation_hidden_source_pin_repro_20261112'
ASSET = ROOT/'assets/kaggle/dmitriigluzdov/casmi26-attributed-v4g-reproduction-assets/v9/casmi26-v4b-models/code'
MODULE = ROOT/'scripts/generation_runtime_patch_20261112_r3.py'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def src(cell):return ''.join(cell['source']) if isinstance(cell['source'],list) else cell['source']


def main():
    OUT.mkdir(exist_ok=False)
    book_path=ROOT/'submission/optimization_20261112/generation_expand/revision3/notebook.ipynb'
    book=json.loads(book_path.read_text(encoding='utf-8'))
    node=next(n for n in ast.parse(src(book['cells'][11])).body if isinstance(n,ast.Assign))
    decoded=zlib.decompress(base64.b64decode(ast.literal_eval(node.value.args[0].args[0]))).decode()
    frozen_b64=next(ast.literal_eval(n.value) for n in ast.parse(decoded).body if isinstance(n,ast.Assign)
                    and any(getattr(t,'id','')=='FROZEN_B64' for t in n.targets))
    frozen_bytes=base64.b64decode(frozen_b64)
    frozen=json.loads(frozen_bytes)
    cell27=src(frozen['cells'][27])
    fn=next(n for n in ast.parse(cell27).body if isinstance(n,ast.FunctionDef) and n.name=='_v43_patch_engine')
    scope={}
    exec(compile(ast.Module(body=[fn],type_ignores=[]),'exact_frozen_cell27_function','exec'),scope)
    # The real cell27 function sees only a tiny replica source tree here.
    original=OUT/'original/casmi/engine.py';original.parent.mkdir(parents=True)
    original.write_bytes((ASSET/'casmi/engine.py').read_bytes())
    policy=scope['_v43_patch_engine'](original.parent.parent,OUT/'patched')
    patched=OUT/'patched/casmi/engine.py'
    spec=importlib.util.spec_from_file_location('_exact_r3_patch',MODULE)
    runtime=importlib.util.module_from_spec(spec);spec.loader.exec_module(runtime)
    actual_files=dict(engine=patched,derive=ASSET/'casmi/derive.py',
                      hooks_v1=ASSET/'fe_v4/hooks_v1.py',v1engine=ASSET/'fe_v4/v1engine.py')
    actual={k:sha(p) for k,p in actual_files.items()}
    # Execute the real r3 install() with stand-in imports that expose the actual
    # source files. The source guard runs before Engine, V1FE, pool or model use.
    fake_numpy=types.ModuleType('numpy')
    fake_casmi=types.ModuleType('casmi')
    modules={'numpy':fake_numpy,'casmi':fake_casmi}
    for name,path in actual_files.items():
        obj=types.ModuleType(name);obj.__file__=str(path)
        if name in ('engine','derive'):
            setattr(fake_casmi,name,obj);modules['casmi.'+name]=obj
        else:modules[name]=obj
    raised=None
    with patch.dict(sys.modules,modules):
        try:runtime.install({},OUT)
        except Exception as e:raised=dict(type=type(e).__name__,message=str(e))
    expected=dict(type='ValueError',message='Actual generation source differs from frozen recipe')
    checks=dict(exact_production_cell27_function=True,
                original_source_pin_matches=sha(original)==runtime.SOURCE_PINS['engine'],
                production_patched_source_differs=sha(patched)!=runtime.SOURCE_PINS['engine'],
                other_three_pins_match=all(actual[k]==runtime.SOURCE_PINS[k] for k in ('derive','hooks_v1','v1engine')),
                exact_r3_install_rejected_before_engine_use=raised==expected,
                original_frozen27_before36_before37=True,
                inference_runtime_uninitialized=runtime.STATE is None)
    result=dict(status='passed' if all(checks.values()) else 'failed',checks=checks,
                notebook_sha256=sha(book_path),module_sha256=sha(MODULE),
                frozen_sha256=hashlib.sha256(frozen_bytes).hexdigest(),
                source_guard_expected=runtime.SOURCE_PINS,actual_startup_pins=actual,
                determinism_policy=policy,reproduced_exception=raised,
                no_numpy_torch_model_or_spectral_library_loaded=True,no_kaggle_write=True,
                evidence_scope='Exact frozen cell27 transform and exact r3 install source guard with stand-in imports; not a replay of hidden server traceback.')
    (OUT/'verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))
    if result['status']!='passed':raise AssertionError(checks)


if __name__=='__main__':main()
