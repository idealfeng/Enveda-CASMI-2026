"""Freeze one private offline V18-matching variant; no network or cloud calls."""
from pathlib import Path
import argparse
import ast
import base64
import copy
import hashlib
import json
import zlib

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'submission/optimization_20261109/mass_guarded_extlib'
STAGE = ROOT / 'submission/optimization_20261112/adduct_extlib'
PUBLIC = ROOT / 'reports/public_update_20261111/ozertuu_refresh_20261111T030240Z/0/source.ipynb'
BASE_SHA = '2bb94c91b176f95dfdff52f08781443ffee004c20d06aeb30efb14d0c0112fc7'
PUBLIC_SHA = '54ad16b546964a1044f07aa5229cd7ee81145882d73a83fda061923e9254adcd'
FUNCTION_SHA = '8e1439c05d7721946ab21e08fec18b4d54d890d3188bf7ec111b32712c545624'
GUARD_SHA = 'a31c55a2958139cbeea948ea4d11fa32eb40e3d3d7b0bac157f6d0fdc51025db'
NAME = 'adduct_extlib'
TARGET = 'stormseye/casmi26-adduct-extlib-1112'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def source(cell):
    return ''.join(cell['source']) if isinstance(cell['source'], list) else cell['source']


def public_function():
    if sha(PUBLIC) != PUBLIC_SHA:
        raise ValueError('Archived public V18 source changed')
    cell = source(read(PUBLIC)['cells'][23])
    tree = ast.parse(cell)
    f = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_apex_extlib_overlay')
    raw = ''.join(cell.splitlines(True)[f.lineno-1:f.end_lineno]).encode('utf-8')
    if digest(raw) != FUNCTION_SHA:
        raise ValueError('Public function extraction differs')
    return raw


def prepare():
    if STAGE.exists():
        raise FileExistsError('Preserve frozen stage')
    if sha(BASE / 'notebook.ipynb') != BASE_SHA:
        raise ValueError('Champion source changed')
    parent = read(BASE / 'notebook.ipynb')
    if len(parent['cells']) != 33:
        raise ValueError('Expected exact champion')
    module = ROOT / 'scripts/adduct_external_overlay_20261112.py'
    guard = ROOT / 'scripts/external_library_overlay_20261109.py'
    if sha(guard) != GUARD_SHA:
        raise ValueError('Official guard source changed')
    payloads = {'adduct_external_overlay_20261112.py': module.read_bytes(),
                'external_library_overlay_20261109.py': guard.read_bytes(),
                'ozertuu_v18_adduct_function.py': public_function()}
    pins = {name: digest(raw) for name, raw in payloads.items()}
    for name, raw in payloads.items():
        compile(raw.decode('utf-8'), name, 'exec')
    files = copy.deepcopy(read(BASE / 'recipe.json')['files'])
    for item in files:
        local = ROOT / 'assets/kaggle' / item['ref'] / ('v' + str(item['version'])) / item['file']
        if local.stat().st_size != item['bytes'] or sha(local) != item['sha256']:
            raise ValueError('Library pin differs: ' + item['file'])
    metadata = read(BASE / 'kernel-metadata.json')
    metadata.update(id=TARGET, title='casmi26 adduct extlib 1112', is_private=True, enable_gpu=True, enable_internet=False)
    recipe = dict(branch=NAME, target=TARGET, baseline_ref=58156482, baseline_public_score=.488,
                  champion_notebook_sha256=BASE_SHA, pre_external_parent_ref=58129661,
                  pre_external_parent_public_score=.482, original_first32_cell_objects_exact=True,
                  method='Exact public V18 neutral-mass/adduct external function plus original official identity validity guard',
                  public_source='ozertuu/casmi26-dual-neural-physical-isomer', public_version=18,
                  public_source_sha256=PUBLIC_SHA, public_function_sha256=FUNCTION_SHA,
                  payload_pins=pins, files=files,
                  matching=dict(neutral_mass_ppm=12, neutral_mass_da=.002, structure_mass_max_ppm=15,
                                min_cosine=.8, min_matched_peaks=4, protect_library=.9, fragment_da=.015),
                  proposal_policy='Public native-key promotion/dedup then official metric identity validity guard; invalid query proposal preserves control',
                  massbank_assumption='Unchanged public exact_mass +/- proton; no trusted-adduct precursor correction',
                  source_attribution='V18 public matching code; original Alex V12 A/B data and identity guard retained',
                  title_score_verified=False, validation_mode='fast_static', new_training=False, locked_final_used=False,
                  control='Exact pre-external .482 GUARDED_TAIL_AUDIT; only final external cell replaced')
    raw_recipe = (json.dumps(recipe, indent=2, ensure_ascii=False) + '\n').encode('utf-8')
    recipe_sha = digest(raw_recipe)
    packed = {k: base64.b64encode(zlib.compress(v, 9)).decode('ascii') for k, v in payloads.items()}
    cell = r'''
# Pinned public V18 matching; original .482 upstream including late heads unchanged.
import base64,zlib,hashlib,importlib.util,json,shutil
_adduct_payloads=__PAYLOADS__
_adduct_pins=__PINS__
try:
    shutil.copy2(ROOT/'submission.csv',ROOT/'submission_adduct_preinstall_control.csv')
    for _adduct_name,_adduct_value in _adduct_payloads.items():
        _adduct_raw=zlib.decompress(base64.b64decode(_adduct_value))
        assert hashlib.sha256(_adduct_raw).hexdigest()==_adduct_pins[_adduct_name]
        (CODE/_adduct_name).write_bytes(_adduct_raw)
    _adduct_spec=importlib.util.spec_from_file_location('_adduct_external_runtime',CODE/'adduct_external_overlay_20261112.py')
    _adduct_mod=importlib.util.module_from_spec(_adduct_spec);_adduct_spec.loader.exec_module(_adduct_mod)
    _adduct_args=(ROOT,INPUT,COMP/'test.parquet',IS_RERUN,SAMPLE_IDS,GUARDED_TAIL_AUDIT,CODE/'ozertuu_v18_adduct_function.py',__FILES__)
    ADDUCT_OVERLAY_REPORT=_adduct_mod.run(*_adduct_args)
    ADDUCT_OVERLAY_AUDIT=_adduct_mod.audit(*_adduct_args,__BRANCH__,__RECIPE__)
    _adduct_actual={k:hashlib.sha256((CODE/k).read_bytes()).hexdigest() for k in _adduct_pins}
    ADDUCT_OVERLAY_AUDIT['checks']['installed_payload_pins']=_adduct_actual==_adduct_pins
    assert ADDUCT_OVERLAY_AUDIT['checks']['installed_payload_pins']
    ADDUCT_OVERLAY_AUDIT['installed_payload_pins']=_adduct_actual
    (ROOT/'adduct_overlay_audit.json').write_text(json.dumps(ADDUCT_OVERLAY_AUDIT,indent=2)+'\n')
except BaseException:
    (ROOT/'submission.csv').unlink(missing_ok=True)
    raise
'''
    for token, value in {'__PAYLOADS__': repr(packed), '__PINS__': repr(pins), '__FILES__': repr(files),
                         '__BRANCH__': repr(NAME), '__RECIPE__': repr(recipe_sha)}.items():
        cell = cell.replace(token, value)
    notebook = copy.deepcopy(parent)
    notebook['cells'][-1] = dict(cell_type='code', execution_count=None, metadata={}, outputs=[], source=cell)
    if notebook['cells'][:32] != parent['cells'][:32]:
        raise ValueError('Original upstream cells changed')
    for c in notebook['cells']:
        if c['cell_type'] == 'code':
            compile(source(c), 'adduct_stage', 'exec')
    STAGE.mkdir(parents=True)
    write(STAGE / 'notebook.ipynb', notebook)
    write(STAGE / 'kernel-metadata.json', metadata)
    (STAGE / 'recipe.json').write_bytes(raw_recipe)
    static = dict(status='passed', target=TARGET, version=1, notebook_sha256=sha(STAGE / 'notebook.ipynb'),
                  checks=dict(champion_pin=True, original_first32_exact=True, only_final_cell_replaced=True,
                              original_v18_function_exact=True, explicit_source_pins=True, actual_score_consumption_observer=True,
                              official_guard_preserved=True, all_code_compiles=True, private_offline_gpu=True,
                              no_new_training_or_data=True, error_removes_final=True))
    write(STAGE / 'static_review.json', static)
    checks = ['base_audit_passed', 'control_bound', 'final_bound', 'source_function_pin', 'module_pin',
              'official_guard_pin', 'exact_ids_schema', 'official_identities_valid', 'library_file_pins',
              'runtime_checks', 'fast_no_matching', 'installed_payload_pins']
    audits = copy.deepcopy(read(BASE / 'branch_spec.json')['required_runtime_audits'][:2])
    audits.append(dict(name='adduct_overlay_audit.json', expected_fields=dict(status='passed', branch=NAME,
                  recipe_sha256=recipe_sha, mode='fast_static'), required_true_checks=checks))
    branch = dict(name=NAME, target=TARGET, version=1, stage_dir=STAGE.relative_to(ROOT).as_posix(),
                  notebook_sha256=sha(STAGE / 'notebook.ipynb'), metadata_sha256=sha(STAGE / 'kernel-metadata.json'),
                  description='CASMI26 20261112 public V18 neutral mass adduct external matching audited V1',
                  validation_mode='fast_static', static_review_path=(STAGE / 'static_review.json').relative_to(ROOT).as_posix(),
                  required_runtime_audits=audits)
    write(STAGE / 'branch_spec.json', branch)
    receipt = dict(status='prepared', branch=NAME, target=TARGET, version=1,
                   notebook_sha256=branch['notebook_sha256'], metadata_sha256=branch['metadata_sha256'],
                   recipe_sha256=recipe_sha, notebook_bytes=(STAGE / 'notebook.ipynb').stat().st_size,
                   static_review_path=branch['static_review_path'])
    write(STAGE / 'prepare_receipt.json', receipt)
    return receipt


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prepare', action='store_true')
    args = p.parse_args()
    print(json.dumps(prepare() if args.prepare else dict(status='plan_only_no_writes', branch=NAME, target=TARGET), indent=2))
