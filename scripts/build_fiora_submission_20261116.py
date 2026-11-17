"""Freeze one explicitly exploratory FIORA overlay after the exact .488 champion.

No external writes. The visible run keeps the parent's fast path but executes a
separate, real FIORA canary in the target image. Competition reruns execute the
complete parent followed by the new scorer. These scopes stay distinct.
"""
from pathlib import Path
import base64
import copy
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'submission/optimization_20261109/mass_guarded_extlib'
PAYLOAD = ROOT / 'submission/optimization_20261116/fiora_payload'
UPLOAD = ROOT / 'submission/optimization_20261116/fiora_dataset_upload'
OUT = ROOT / 'submission/optimization_20261116/fiora_tims500_fullslots'
MODULE = ROOT / 'scripts/fiora_submission_runtime_20261116.py'
PARENT_SHA = '2bb94c91b176f95dfdff52f08781443ffee004c20d06aeb30efb14d0c0112fc7'
DATASET = 'stormseye/casmi26-fiora-tims500-1116'
BRANCH = 'fiora_tims500_fullslots'
TARGET = 'stormseye/casmi26-fiora-tims500-isomers-1116'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


CELL = r'''
# Independent FIORA tims500 model, after the unchanged champion's AB overlay.
# Visible: actual isolated component canary + unchanged parent fast CSV.
# Scoring rerun: complete champion production -> FIORA -> final submission.csv.
import base64 as _fb64, hashlib as _fh, json as _fj, os as _fo
import shutil as _fs, subprocess as _fsp, sys as _fsy, zipfile as _fz
from collections import Counter as _FCounter

def _fiora_submit_stage():
    expected = __EXPECTED__
    digest = lambda p: _fh.sha256(Path(p).read_bytes()).hexdigest()
    checks = {}
    def check(name, value):
        checks[name] = bool(value)
        if not value:
            raise AssertionError(name)
    check('original_mass_passed', BATCH_VARIANT_AUDIT.get('status') == 'passed')
    check('original_head_passed', GUARDED_TAIL_AUDIT.get('status') == 'passed')
    check('original_AB_passed', EXTERNAL_OVERLAY_AUDIT.get('status') == 'passed')
    baseline = ROOT / 'submission_fiora_champion_control.csv'
    _fs.copy2(ROOT / 'submission.csv', baseline)
    check('champion_control_bound', digest(baseline) == EXTERNAL_OVERLAY_AUDIT['csv_sha256'])
    raw = _fb64.b64decode(__PAYLOAD__)
    check('module_pin', _fh.sha256(raw).hexdigest() == expected['module_sha256'])
    executable = CODE / 'fiora_submission_runtime.py'
    executable.write_bytes(raw)
    # Kaggle may expose the single uploaded archive or its expanded contents.
    candidates = [p for p in INPUT.rglob('asset_manifest.json')
                  if expected['dataset_slug'] in str(p)
                  and digest(p) == expected['asset_manifest_sha256']]
    if len(candidates) == 1:
        bundle = candidates[0].parent
    elif not candidates:
        archives = [p for p in INPUT.rglob('fiora_bundle.zip')
                    if expected['dataset_slug'] in str(p)]
        check('unique_payload_archive', len(archives) == 1)
        check('payload_archive_pin', digest(archives[0]) == expected['archive_sha256'])
        bundle = ROOT / 'fiora_asset_snapshot'
        bundle.mkdir(exist_ok=False)
        with _fz.ZipFile(archives[0]) as stream:
            for member in stream.infolist():
                target = (bundle / member.filename).resolve()
                check('archive_paths_inside', target.is_relative_to(bundle.resolve()))
                check('archive_no_symlinks', (member.external_attr >> 16) & 0o170000 != 0o120000)
            stream.extractall(bundle)
    else:
        raise ValueError('Ambiguous fixed FIORA dataset manifest')
    check('asset_manifest_pin', digest(bundle / 'asset_manifest.json') == expected['asset_manifest_sha256'])
    manifest = _fj.loads((bundle / 'asset_manifest.json').read_text())
    check('all_asset_files_pinned', all(digest(bundle / rel) == pin for rel, pin in manifest['files'].items()))
    check('trained_checkpoint_binding', manifest['parent_checkpoint_sha256'] == expected['parent_checkpoint_sha256']
          and manifest['model_step'] == 500 and manifest['state_sha256'] == expected['state_sha256'])
    environment = dict(_fo.environ)
    environment.update(PYTHONUNBUFFERED='1', PYTHONHASHSEED='0', OMP_NUM_THREADS='4', MKL_NUM_THREADS='4',
                       OPENBLAS_NUM_THREADS='4', MPLBACKEND='Agg')
    for key, suffix in {'TMPDIR':'tmp', 'TMP':'tmp', 'TEMP':'tmp', 'XDG_CACHE_HOME':'xdg',
                        'TORCH_HOME':'torch', 'PYTHONPYCACHEPREFIX':'pycache',
                        'MPLCONFIGDIR':'matplotlib', 'CUDA_CACHE_PATH':'cuda'}.items():
        path = ROOT / 'fiora_cache' / suffix
        path.mkdir(parents=True, exist_ok=True)
        environment[key] = str(path)
    def execute(source, queries, destination, mode, log_name):
        command = [_fsy.executable, str(executable), '--submission', str(source), '--queries', str(queries),
                   '--asset-root', str(bundle), '--asset-manifest-sha', expected['asset_manifest_sha256'],
                   '--output-dir', str(destination), '--device', 'cuda', '--mode', mode]
        with (ROOT / log_name).open('w') as log:
            result = _fsp.run(command, env=environment, stdout=log, stderr=_fsp.STDOUT, timeout=3600)
        if result.returncode:
            raise RuntimeError('FIORA child failed; inspect ' + log_name)
        receipt = _fj.loads((destination / 'runtime_audit.json').read_text())
        if receipt.get('status') != 'passed' or not receipt.get('checks') or not all(v is True for v in receipt['checks'].values()):
            raise ValueError('FIORA child audit failed')
        return receipt
    canary = None
    if not IS_RERUN:
        canary = execute(bundle / 'canary_submission.csv', bundle / 'canary_queries.parquet',
                         ROOT / 'fiora_visible_canary', 'full', 'fiora_visible_canary.log')
        check('visible_actual_canary_forward', canary.get('model_invoked') is True
              and canary.get('scored_queries', 0) > 0)
    destination = ROOT / 'fiora_final_overlay'
    receipt = execute(baseline, COMP / 'test.parquet', destination,
                      'full' if IS_RERUN else 'static', 'fiora_final_overlay.log')
    check('runtime_input_is_champion_output', receipt.get('input_sha256') == digest(baseline))
    check('runtime_mode_exact', receipt.get('mode') == ('full' if IS_RERUN else 'static'))
    check('actual_runtime_checks', all(v is True for v in receipt['checks'].values()))
    output = destination / 'submission.csv'
    check('runtime_output_bound', digest(output) == receipt['output_sha256'])
    before = pd.read_csv(baseline, dtype=str, keep_default_na=False)
    after = pd.read_csv(output, dtype=str, keep_default_na=False)
    check('sample_ids_exact', list(after.columns) == ['molecule_id', 'smiles']
          and after.molecule_id.tolist() == before.molecule_id.tolist() == SAMPLE_IDS
          and after.molecule_id.is_unique)
    check('candidate_multisets_exact', all(_FCounter(a.split(';')) == _FCounter(b.split(';'))
          for a, b in zip(before.smiles, after.smiles)))
    if IS_RERUN:
        check('upstream_real_full_path', all(a.get('mode') == 'hidden_full'
              for a in (BATCH_VARIANT_AUDIT, GUARDED_TAIL_AUDIT, EXTERNAL_OVERLAY_AUDIT)))
        check('real_or_explicit_no_eligible', receipt.get('model_invoked') is True
              or (receipt.get('scored_queries') == 0 and after.equals(before)))
    else:
        check('visible_champion_fast_only', not RUN_PIPELINE and not PIPELINE_DONE
              and receipt.get('model_invoked') is False and after.equals(before))
    _fs.copy2(output, ROOT / 'submission.csv')
    check('final_csv_bound', digest(ROOT / 'submission.csv') == receipt['output_sha256'])
    result = dict(status='passed', branch=expected['branch'], recipe_sha256=expected['recipe_sha256'],
                  mode='hidden_full' if IS_RERUN else 'fast_static', checks=checks,
                  parent_ref=58156482, parent_public_score=.488,
                  parent_csv_sha256=digest(baseline), csv_sha256=digest(ROOT / 'submission.csv'),
                  runtime_sha256=digest(destination / 'runtime_audit.json'),
                  asset_manifest_sha256=expected['asset_manifest_sha256'],
                  state_sha256=expected['state_sha256'],
                  visible_component_executed=canary is not None,
                  visible_complete_parent_inference_executed=False if not IS_RERUN else None,
                  runtime=receipt, canary=canary,
                  scope='complete_champion_then_fiora' if IS_RERUN else 'parent_fast_plus_real_isolated_fiora_canary')
    (ROOT / 'fiora_submission_audit.json').write_text(_fj.dumps(result, indent=2) + '\n')
    return result

try:
    FIORA_SUBMISSION_AUDIT = _fiora_submit_stage()
except BaseException:
    (ROOT / 'submission.csv').unlink(missing_ok=True)
    raise
'''


def main():
    if OUT.exists():
        raise FileExistsError('Preserve immutable stage; revise into a new directory')
    assert sha(BASE / 'notebook.ipynb') == PARENT_SHA
    manifest = read(PAYLOAD / 'asset_manifest.json')
    assert manifest['model_step'] == 500
    assert {'canary_queries.parquet', 'canary_submission.csv'} <= set(manifest['files'])
    assert all(sha(PAYLOAD / name) == pin for name, pin in manifest['files'].items())
    archive = UPLOAD / 'fiora_bundle.zip'
    assert archive.is_file()
    payload = MODULE.read_bytes()
    compile(payload.decode('utf-8'), str(MODULE), 'exec')
    parent = read(BASE / 'notebook.ipynb')
    recipe = dict(branch=BRANCH, target=TARGET, parent_ref=58156482, parent_public_score=.488,
                  parent_notebook_sha256=PARENT_SHA, parent_cells_unchanged=33,
                  experiment_type='user_authorized_speculative_submission',
                  method='Independent FIORA tims500 score: reorder identical-formula original slots including rank1, after complete champion AB',
                  candidate_set='Exact champion final25 multiset, no added or removed candidates',
                  spectrum_policy='Lexicographically first spectrum_id among true timsTOF [M+H]+ single finite CE20..60eV; no truth access',
                  formula_policy='Candidate-own official-normalized formula, stable original position ties',
                  support=dict(max_heavy_atoms=64, max_directed_edges=160, training_max_heavy_atoms=32,
                               training_max_directed_edges=74, outside_training_graph_size_explicit=True),
                  fallback='Unsupported query or any candidate failure/oversize: preserve whole original query; global source or asset pin failure aborts',
                  added_AB_protection=False, protected_prefix=0, blend_weights=None,
                  model_step=500, checkpoint_sha256=manifest['parent_checkpoint_sha256'],
                  state_sha256=manifest['state_sha256'], params_sha256=manifest['params_sha256'],
                  asset_manifest_sha256=sha(PAYLOAD / 'asset_manifest.json'), archive_sha256=sha(archive),
                  dataset=DATASET + '/1', module_sha256=sha(MODULE),
                  local_candidate_result='Primary92 standalone MRR .697335->.707332; paired95[-.028883,+.049772], unconfirmed stable gain',
                  validation_mode='fast_static', target_environment_component_canary_required=True,
                  new_full_champion_visible_replay=False, hidden_complete_path_not_yet_verified=True,
                  locked_final_used=False, new_training_this_submission=False, gain_claim=False)
    raw = (json.dumps(recipe, ensure_ascii=False, indent=2) + '\n').encode()
    expected = dict(branch=BRANCH, recipe_sha256=hashlib.sha256(raw).hexdigest(),
                    dataset_slug=DATASET.split('/')[1], module_sha256=sha(MODULE),
                    asset_manifest_sha256=recipe['asset_manifest_sha256'], archive_sha256=recipe['archive_sha256'],
                    parent_checkpoint_sha256=recipe['checkpoint_sha256'], state_sha256=recipe['state_sha256'])
    cell = CELL.replace('__EXPECTED__', repr(expected)).replace('__PAYLOAD__', repr(base64.b64encode(payload).decode()))
    book = copy.deepcopy(parent)
    book['cells'].append(dict(cell_type='code', execution_count=None, metadata={}, outputs=[], source=cell))
    for c in book['cells']:
        if c['cell_type'] == 'code':
            source = c['source']; source = ''.join(source) if isinstance(source, list) else source
            compile(source, 'fiora_frozen_stage', 'exec')
    metadata = read(BASE / 'kernel-metadata.json')
    metadata.update(id=TARGET, title='CASMI26 FIORA tims500 isomers 1116')
    metadata['dataset_sources'].append(DATASET + '/1')
    OUT.mkdir(parents=True)
    save(OUT / 'notebook.ipynb', book)
    save(OUT / 'kernel-metadata.json', metadata)
    (OUT / 'recipe.json').write_bytes(raw)
    checks = dict(parent_source_pin=True, all_original_cells_exact=book['cells'][:-1] == parent['cells'],
                  only_one_appended_cell=len(book['cells']) == 34, actual_trained_500_state=True,
                  all_payload_files_match=True, runtime_source_pin=True, source_compiles=True,
                  original_dataset_pins_retained=metadata['dataset_sources'][:-1] == read(BASE / 'kernel-metadata.json')['dataset_sources'],
                  new_dataset_version_pinned=metadata['dataset_sources'][-1] == DATASET + '/1',
                  private_offline_gpu=metadata['is_private'] is True and metadata['enable_internet'] is False
                                     and metadata['enable_gpu'] is True,
                  visible_canary_not_full_champion_claim=True, failure_removes_final_csv=True)
    assert all(v is True for v in checks.values())
    review = dict(status='passed', target=TARGET, version=1, notebook_sha256=sha(OUT / 'notebook.ipynb'), checks=checks,
                  scope='Source binding only; visible actual FIORA canary must pass before competition request; hidden full execution pending')
    save(OUT / 'static_review.json', review)
    audits = copy.deepcopy(read(BASE / 'branch_spec.json')['required_runtime_audits'])
    audits.append(dict(name='fiora_submission_audit.json',
                       expected_fields=dict(status='passed', branch=BRANCH, mode='fast_static', recipe_sha256=expected['recipe_sha256']),
                       required_true_checks=['original_mass_passed', 'original_head_passed', 'original_AB_passed',
                                             'champion_control_bound', 'module_pin', 'asset_manifest_pin',
                                             'all_asset_files_pinned', 'trained_checkpoint_binding',
                                             'visible_actual_canary_forward', 'runtime_input_is_champion_output',
                                             'runtime_mode_exact', 'actual_runtime_checks', 'runtime_output_bound',
                                             'sample_ids_exact', 'candidate_multisets_exact',
                                             'visible_champion_fast_only', 'final_csv_bound']))
    branch = dict(name=BRANCH, target=TARGET, version=1, stage_dir=OUT.relative_to(ROOT).as_posix(),
                  notebook_sha256=sha(OUT / 'notebook.ipynb'), metadata_sha256=sha(OUT / 'kernel-metadata.json'),
                  description='CASMI26 20261116 FIORA tims500 same-formula fullslots after champion0488 V1',
                  validation_mode='fast_static', static_review_path=(OUT / 'static_review.json').relative_to(ROOT).as_posix(),
                  required_runtime_audits=audits)
    save(OUT / 'branch_spec.json', branch)
    batch = dict(schema_version=1, competition='enveda-CASMI26-molecule-id-mass-spectra',
                 batch_id='optimization_20261116_fiora', max_submissions=1,
                 baseline_public_score=.488, state_root='reports/optimization_20261116_fiora', branches=[branch])
    save(OUT.parent / 'manifest.json', batch)
    print(json.dumps(dict(status='prepared', target=TARGET, notebook_sha256=branch['notebook_sha256'],
                          recipe_sha256=expected['recipe_sha256'], scope=review['scope'])))


if __name__ == '__main__':
    main()
