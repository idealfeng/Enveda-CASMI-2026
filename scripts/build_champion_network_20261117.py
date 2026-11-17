"""Freeze Rogers' fixed network mechanism between the champion head and AB.

This is the optimized exploration arm, not a claim of reproducing Rogers' .492.
The original head audit remains immutable; a new audit bridges network to AB.
"""
from pathlib import Path
import base64
import copy
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'submission/optimization_20261109/mass_guarded_extlib'
OUT = ROOT / 'submission/public_network_20261117/champion_network'
MODULE = ROOT / 'scripts/public_network_overlay_20261117.py'
PARENT_SHA = '2bb94c91b176f95dfdff52f08781443ffee004c20d06aeb30efb14d0c0112fc7'
ROGERS_SHA = '51c32f200c265fff08bfa4a9841cb6345d1f56515dcd72e254df8da53e07ae99'
NETWORK_SHA = '33153de76fccebe4ed2325bea7649573219e4cfb964483cd5c335ac7dc7e93b8'
BRANCH = 'champion_network'
TARGET = 'stormseye/casmi26-champion-network-before-ab-1117'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def source(cell):
    value = cell.get('source', '')
    return ''.join(value) if isinstance(value, list) else value


NETWORK_CELL = r'''
# Apply the public Rogers network after the unchanged learned head, before AB.
import base64 as _nb64, hashlib as _nh, importlib.util as _ni
try:
    _network_payload = _nb64.b64decode(__PAYLOAD__)
    assert _nh.sha256(_network_payload).hexdigest() == __MODULE_PIN__
    _network_path = CODE / 'public_network_overlay_20261117.py'
    _network_path.write_bytes(_network_payload)
    _network_spec = _ni.spec_from_file_location('_fixed_public_network', _network_path)
    _network_module = _ni.module_from_spec(_network_spec)
    _network_spec.loader.exec_module(_network_module)
    NETWORK_BRIDGE_AUDIT = _network_module.run(ROOT, INPUT, IS_RERUN, SAMPLE_IDS,
                                             GUARDED_TAIL_AUDIT, __BRANCH__, __RECIPE_PIN__)
    assert NETWORK_BRIDGE_AUDIT['status'] == 'passed'
    assert all(v is True for v in NETWORK_BRIDGE_AUDIT['checks'].values())
except BaseException:
    (ROOT / 'submission.csv').unlink(missing_ok=True)
    raise
'''

FINAL_CELL = r'''
# Chain the unchanged head -> public network -> unchanged guarded AB output.
def _observe_champion_network():
    import hashlib, json
    expected = __EXPECTED__
    checks = {}
    digest = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    def check(name, value):
        checks[name] = bool(value)
        if not value:
            raise AssertionError(name)
    check('original_mass_passed', BATCH_VARIANT_AUDIT.get('status') == 'passed')
    check('original_head_passed', GUARDED_TAIL_AUDIT.get('status') == 'passed')
    check('new_network_passed', NETWORK_BRIDGE_AUDIT.get('status') == 'passed'
          and all(v is True for v in NETWORK_BRIDGE_AUDIT['checks'].values()))
    check('original_AB_passed', EXTERNAL_OVERLAY_AUDIT.get('status') == 'passed')
    check('network_module_pin', digest(CODE / 'public_network_overlay_20261117.py') == expected['module_sha256']
          == NETWORK_BRIDGE_AUDIT['module_sha256'])
    check('recipe_branch_bound', NETWORK_BRIDGE_AUDIT.get('branch') == expected['branch']
          and NETWORK_BRIDGE_AUDIT.get('recipe_sha256') == expected['recipe_sha256'])
    check('head_to_network_bound', NETWORK_BRIDGE_AUDIT['control_sha256'] == GUARDED_TAIL_AUDIT['csv_sha256'])
    check('network_to_AB_bound', EXTERNAL_OVERLAY_AUDIT['control_sha256'] == NETWORK_BRIDGE_AUDIT['csv_sha256'])
    check('actual_final_csv_bound', digest(ROOT / 'submission.csv') == EXTERNAL_OVERLAY_AUDIT['csv_sha256'])
    # The older head receipt is evidence of its completed stage, not the new final output.
    old_head = json.loads((ROOT / 'guarded_tail_audit.json').read_text())
    check('original_head_receipt_unchanged', old_head == GUARDED_TAIL_AUDIT)
    check('original_AB_algorithm_pin', digest(CODE / 'alex_v12_external_function.py') == expected['ab_function_sha256']
          and digest(CODE / 'external_library_overlay_20261109.py') == expected['ab_helper_sha256'])
    check('fixed_public_network_parameters', NETWORK_BRIDGE_AUDIT['checks']['network_parameters'] is True)
    final = pd.read_csv(ROOT / 'submission.csv', dtype=str, keep_default_na=False)
    check('sample_ids_exact', list(final.columns) == ['molecule_id', 'smiles']
          and final.molecule_id.tolist() == SAMPLE_IDS and final.molecule_id.is_unique)
    check('official_output_valid', all(_external_overlay.valid(v) for v in final.smiles))
    if IS_RERUN:
        check('full_parent_stage_scope', all(a.get('mode') == 'hidden_full'
              for a in (BATCH_VARIANT_AUDIT, GUARDED_TAIL_AUDIT, NETWORK_BRIDGE_AUDIT, EXTERNAL_OVERLAY_AUDIT)))
    else:
        check('visible_parent_fast_network_real', not RUN_PIPELINE and not PIPELINE_DONE
              and NETWORK_BRIDGE_AUDIT['checks']['actual_network_execution'] is True)
    result = dict(status='passed', branch=expected['branch'], recipe_sha256=expected['recipe_sha256'],
                  mode='hidden_full' if IS_RERUN else 'fast_static', checks=checks,
                  original_parent_ref=58156482, original_parent_public_score=.488,
                  original_head_csv_sha256=GUARDED_TAIL_AUDIT['csv_sha256'],
                  network_csv_sha256=NETWORK_BRIDGE_AUDIT['csv_sha256'],
                  csv_sha256=digest(ROOT / 'submission.csv'),
                  network_audit_sha256=digest(ROOT / 'network_audit.json'),
                  public_score=None, gain_claim=False,
                  scope='complete_parent_then_network_before_AB' if IS_RERUN
                        else 'parent_fast_plus_actual_network_only')
    (ROOT / 'champion_network_audit.json').write_text(json.dumps(result, indent=2) + '\n')
    return result
try:
    CHAMPION_NETWORK_AUDIT = _observe_champion_network()
except BaseException:
    (ROOT / 'submission.csv').unlink(missing_ok=True)
    raise
'''


def main():
    if OUT.exists():
        raise FileExistsError('Preserve immutable prepared stage')
    assert sha(BASE / 'notebook.ipynb') == PARENT_SHA
    assert sha(ROOT / 'reports/public_review_20261116/notebooks/rogersjohnson__casmi26-l4-lam035/source.ipynb') == ROGERS_SHA
    network_file = ROOT / 'reports/public_review_20261116/network_audit/rogers_n1c_function.py'
    assert hashlib.sha256(network_file.read_text(encoding='utf-8').encode('utf-8')).hexdigest() == NETWORK_SHA
    payload = MODULE.read_bytes()
    compile(payload.decode('utf-8'), str(MODULE), 'exec')
    parent = read(BASE / 'notebook.ipynb')
    assert len(parent['cells']) == 33
    recipe = dict(branch=BRANCH, target=TARGET, parent_ref=58156482, parent_public_score=.488,
                  parent_notebook_sha256=PARENT_SHA, public_source_ref='rogersjohnson/casmi26-l4-lam035',
                  public_source_version=1, public_source_sha256=ROGERS_SHA,
                  upstream_reported_score=.492, upstream_reported_reproduction_ref=58380172,
                  upstream_score_not_our_reproduction=True,
                  method='Move fixed public network mechanism onto champion after existing head and before existing guarded AB',
                  network=dict(LAM=.35, TAU=.6, neighbor_top_k=5, minimum_matched_peaks=6,
                               edge_weight_power=4, same_raw_candidate_multiset=True,
                               additional_prefix_or_library_protection=False, original_function_sha256=NETWORK_SHA,
                               function_hash_scope='UTF-8 after universal-newline LF normalization'),
                  module_sha256=sha(MODULE), original_priors=[.10, .10, .12],
                  original_learned_tail_retained=True, original_official_identity_AB_guard_retained=True,
                  original_generation_mass_and_ensemble_retained=True, new_candidates=False,
                  new_weights=False, new_training=False, original_cells0_to31_unchanged=True,
                  original_AB_algorithm_unchanged=True, AB_parent_audit_rebound_to_network=True,
                  old_head_receipt_never_overwritten=True, comparison_type='mechanism_transfer_exploration',
                  prior_network_20261113_difference='Old .25 network was after AB, with strong-library/AB-hit query protection; current .35 is before AB, without those extra skips',
                  validation_mode='fast_static', visible_network_actual_execution=True,
                  full_new_parent_initialization_locally_completed=False, hidden_success=False,
                  locked_final_used=False, gain_claim=False)
    raw = (json.dumps(recipe, ensure_ascii=False, indent=2) + '\n').encode()
    recipe_pin = hashlib.sha256(raw).hexdigest()
    network_cell = NETWORK_CELL
    for k, v in {'__PAYLOAD__':repr(base64.b64encode(payload).decode()), '__MODULE_PIN__':repr(sha(MODULE)),
                 '__BRANCH__':repr(BRANCH), '__RECIPE_PIN__':repr(recipe_pin)}.items():
        network_cell = network_cell.replace(k, v)
    ab_source = source(parent['cells'][32])
    old = 'IS_RERUN,SAMPLE_IDS,GUARDED_TAIL_AUDIT,CODE/'
    new = 'IS_RERUN,SAMPLE_IDS,NETWORK_BRIDGE_AUDIT,CODE/'
    assert ab_source.count(old) == 1
    bridged_ab = ab_source.replace(old, new)
    expected = dict(branch=BRANCH, recipe_sha256=recipe_pin, module_sha256=sha(MODULE),
                    ab_function_sha256='9ceaa95ddda0fb304758c9acd7dd1f256c528fcb4a8304c0152f8b6d8e3e3e76',
                    ab_helper_sha256='a31c55a2958139cbeea948ea4d11fa32eb40e3d3d7b0bac157f6d0fdc51025db')
    book = copy.deepcopy(parent)
    book['cells'] = book['cells'][:32] + [
        dict(cell_type='code', execution_count=None, metadata={}, outputs=[], source=network_cell),
        dict(cell_type='code', execution_count=None, metadata=copy.deepcopy(parent['cells'][32]['metadata']), outputs=[], source=bridged_ab),
        dict(cell_type='code', execution_count=None, metadata={}, outputs=[], source=FINAL_CELL.replace('__EXPECTED__', repr(expected)))]
    for c in book['cells']:
        if c['cell_type'] == 'code':
            compile(source(c), 'champion_public_network', 'exec')
    metadata = read(BASE / 'kernel-metadata.json')
    metadata.update(id=TARGET, title='CASMI26 champion network before AB 1117')
    OUT.mkdir(parents=True)
    save(OUT / 'notebook.ipynb', book)
    save(OUT / 'kernel-metadata.json', metadata)
    (OUT / 'recipe.json').write_bytes(raw)
    checks = dict(exact_parent_source_pin=True, original_first32_cells_exact=book['cells'][:32] == parent['cells'][:32],
                  original_AB_single_audit_argument_change=source(book['cells'][33]).replace(new, old) == ab_source,
                  original_head_receipt_preserved=True, network_comes_before_AB=True,
                  module_source_embedded_and_pinned=True, all_source_compiles=True,
                  original_data_model_versions_retained=metadata['dataset_sources'] == read(BASE / 'kernel-metadata.json')['dataset_sources'],
                  private_offline_gpu=metadata['is_private'] is True and metadata['enable_internet'] is False and metadata['enable_gpu'] is True,
                  no_new_model_or_training=True, visible_scope_explicit=True)
    assert all(checks.values())
    review = dict(status='passed', target=TARGET, version=1, notebook_sha256=sha(OUT / 'notebook.ipynb'),
                  checks=checks, boundary='Static source binding; runtime network and AB consumption must pass separately; no efficacy claim')
    save(OUT / 'static_review.json', review)
    audits = copy.deepcopy(read(BASE / 'branch_spec.json')['required_runtime_audits'])
    audits.insert(2, dict(name='network_audit.json', expected_fields=dict(status='passed', branch=BRANCH, mode='fast_static', recipe_sha256=recipe_pin),
                          required_true_checks=['parent_audit_passed', 'control_bound', 'final_bound', 'exact_ids_order',
                                                'candidate_multisets', 'official_identity_multisets', 'function_pin',
                                                'network_parameters', 'labels_not_read', 'actual_network_execution']))
    audits.append(dict(name='champion_network_audit.json', expected_fields=dict(status='passed', branch=BRANCH, mode='fast_static', recipe_sha256=recipe_pin),
                       required_true_checks=['original_mass_passed', 'original_head_passed', 'new_network_passed',
                                             'original_AB_passed', 'network_module_pin', 'recipe_branch_bound',
                                             'head_to_network_bound', 'network_to_AB_bound', 'actual_final_csv_bound',
                                             'original_head_receipt_unchanged', 'original_AB_algorithm_pin',
                                             'fixed_public_network_parameters', 'sample_ids_exact', 'official_output_valid',
                                             'visible_parent_fast_network_real']))
    branch = dict(name=BRANCH, target=TARGET, version=1, stage_dir=OUT.relative_to(ROOT).as_posix(),
                  notebook_sha256=review['notebook_sha256'], metadata_sha256=sha(OUT / 'kernel-metadata.json'),
                  description='CASMI26 20261117 champion0488 plus Rogers035 network before guarded AB V1',
                  validation_mode='fast_static', static_review_path=(OUT / 'static_review.json').relative_to(ROOT).as_posix(),
                  required_runtime_audits=audits)
    save(OUT / 'branch_spec.json', branch)
    print(json.dumps(dict(status='prepared', branch=BRANCH, notebook_sha256=branch['notebook_sha256'], recipe_sha256=recipe_pin)))


if __name__ == '__main__':
    main()
