"""Freeze the public Rogers LAM=.35 recipe with source-bound completion observers.

This prepares a private local stage only. It does not run, push, or submit it.
Original algorithms/configuration are retained; instrumentation detects the
upstream catch-and-continue paths instead of mistaking them for reproduction.
"""
from pathlib import Path
import ast
import base64
import copy
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / 'reports/public_review_20261116/notebooks/rogersjohnson__casmi26-l4-lam035'
SOURCE = SOURCE_DIR / 'source.ipynb'
SOURCE_PIN = '51c32f200c265fff08bfa4a9841cb6345d1f56515dcd72e254df8da53e07ae99'
OUT = ROOT / 'submission/public_network_20261117/rogers_repro'
TARGET = 'stormseye/casmi26-rogers0492-repro-1117'
BRANCH = 'rogers_repro'
V2 = 'c08d2101154d057890de088be63834eb622468892a3b842512fdc5a65e02ff46'
PUBLIC_PINS = dict(features='a97ad9b3ab3711517864d56e497e1672cb29bb05683c72b52db9f9b0a17b1455',
                   model='2547418857386d1c2513fd1ab6c70961e6a96e73d9d495bbfe3052197e69dc39',
                   config='563fb2a2a81ca48ea094f9ab78c157a48a6e9a5503e85e6ce8f0fb3615c1cc03',
                   final_model='44436b2daec64373e66f9120dd2389c24fc83dd9430ebeeac18e3cb49dcb9642')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def source(cell):
    s = cell['source']
    return ''.join(s) if isinstance(s, list) else s


def function_text(text, name):
    node = next(n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef) and n.name == name)
    return '\n'.join(text.splitlines()[node.lineno - 1:node.end_lineno]) + '\n'


def codecell(text):
    return dict(cell_type='code', execution_count=None, metadata={}, outputs=[], source=text)


OBSERVER = r'''
# Completion and source observers only: no scoring or candidate changes here.
import contextlib as _rc, io as _ri, re as _rr
_ROGERS_EXPECTED = __EXPECTED__
_ROGERS_STEPS = {}
_roger_sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
for _name, _encoded in __FUNCTIONS__.items():
    _raw = base64.b64decode(_encoded)
    assert hashlib.sha256(_raw).hexdigest() == _ROGERS_EXPECTED['function_pins'][_name]
    (CODE / (_name + '_original.py')).write_bytes(_raw)

def _observe_rogers_call(name, function, **kwargs):
    final = ROOT / 'submission.csv'
    before = _roger_sha(final)
    capture = _ri.StringIO()
    record = dict(status='started', input_csv_sha256=before,
                  function_source_sha256=_ROGERS_EXPECTED['function_pins'][name],
                  parameters=kwargs, real_function_called=False)
    try:
        with _rc.redirect_stdout(capture):
            record['real_function_called'] = True
            function(**kwargs)
        output = capture.getvalue()
        if name == 'network':
            if '[n1c] LAM=0.35 TAU=0.6 ' not in output:
                raise RuntimeError('Original network did not reach its completion marker')
            counts = _rr.search(r'with neighbors (\d+), edges (\d+), changed lists (\d+), top1 changed (\d+)', output)
            if not counts:
                raise RuntimeError('Original network summary missing')
            record.update(neighbor_queries=int(counts[1]), edges=int(counts[2]),
                          changed_queries=int(counts[3]), changed_top1=int(counts[4]))
            original_control = ROOT / 'submission_pre_n1c.csv'
        else:
            if '[apex-extlib] SUCCESS:' not in output:
                raise RuntimeError('Original AB overlay did not complete')
            a = _rr.search(r'Loaded (\d+) reference spectra from Source A', output)
            b = _rr.search(r'Total references after Source B: (\d+) spectra', output)
            if not a or not b or int(a[1]) <= 0 or int(b[1]) <= int(a[1]):
                raise RuntimeError('Both original AB reference libraries must actually load')
            record.update(source_a_references=int(a[1]), source_b_references=int(b[1])-int(a[1]))
            original_control = ROOT / 'submission_pre_apex_extlib.csv'
            report = json.loads((ROOT / 'apex_extlib_audit.json').read_text())
            if report.get('molecules') != len(SAMPLE_IDS):
                raise ValueError('Original AB report denominator differs')
            record['original_report'] = report
        if _roger_sha(original_control) != before:
            raise ValueError('Original step read a different CSV control')
        record.update(status='passed', output_csv_sha256=_roger_sha(final),
                      original_control_sha256=_roger_sha(original_control))
        shutil.copy2(final, ROOT / ('submission_after_rogers_' + name + '.csv'))
    except BaseException as error:
        record.update(status='failed', error_type=type(error).__name__)
        raise
    finally:
        (ROOT / ('rogers_' + name + '.log')).write_text(capture.getvalue())
        _ROGERS_STEPS[name] = record
        (ROOT / ('rogers_' + name + '_observation.json')).write_text(json.dumps(record, indent=2) + '\n')
        print(capture.getvalue(), end='')
'''

AUDIT = r'''
# Final immutable recipe observer. Upstream exceptions cannot masquerade as success.
def _audit_rogers_reproduction():
    from collections import Counter
    import rdkit
    from rdkit import Chem
    from rdkit.Chem.MolStandardize import rdMolStandardize
    expected = _ROGERS_EXPECTED
    checks = {}
    def check(name, value):
        checks[name] = bool(value)
        if not value:
            raise AssertionError(name)
    check('configuration_exact', VARIANT == 'CUSTOM' and CUSTOM == dict(w_top=.25, w_mid=.75, rescue=0)
          and V8 == 'MASS' and MASS_ON and not RR8 and (POP_W, SPEC_W, NP_W) == (.12,.12,.12)
          and (MASS_CENTER, MASS_FREE, MASS_FULL, MASS_W) == (-1.5,3.,8.,.15)
          and PHYSICAL and not PROVENANCE and FRAG_ON_V2)
    check('official_rdkit', rdkit.__version__ == '2026.03.3')
    check('frozen_source_pin', _roger_sha(FROZEN) == expected['frozen_sha256'])
    files = {'features.py':'features', 'model.py':'model', 'config.json':'config', 'final_model.pt':'final_model'}
    pub = {name:_roger_sha(Path(PUB_BUNDLE) / name) for name in files}
    ours = {name:_roger_sha(Path(OURS_BUNDLE) / name) for name in files}
    wanted = {name:expected['public_pins'][key] for name,key in files.items()}
    check('public_model_pins', pub == wanted)
    wanted_v2 = dict(wanted); wanted_v2['final_model.pt'] = expected['v2_sha256']
    check('actual_v80_final_is_fixed_v2', ours == wanted_v2)
    check('two_distinct_models', pub['final_model.pt'] != ours['final_model.pt'])
    selected_libraries = {}
    for item in expected['external_library_files']:
        hits = list(INPUT.rglob(item['file']))
        if item['file'] == 'spectra.parquet':
            hits = sorted(hits, key=lambda p: ('massbank' not in str(p).lower(), len(str(p))))
        else:
            hits = sorted(hits, key=lambda p: len(str(p)))
        check('library_selector:' + item['file'], bool(hits) and item['ref'].split('/')[1] in str(hits[0]))
        path = hits[0]
        check('library_pin:' + item['file'], path.stat().st_size == item['bytes'] and _roger_sha(path) == item['sha256'])
        selected_libraries[item['file']] = dict(path=str(path), sha256=item['sha256'], bytes=item['bytes'])
    check('all_external_library_pins', len(selected_libraries) == 5)
    check('original_function_files_pinned', all(_roger_sha(CODE / (name + '_original.py')) == pin
          for name,pin in expected['function_pins'].items()))
    net = _ROGERS_STEPS.get('network', {})
    ab = _ROGERS_STEPS.get('ab', {})
    check('actual_network_completed', net.get('status') == 'passed' and net.get('real_function_called') is True)
    check('actual_network_parameters', net.get('parameters') == dict(LAM=.35, TAU=.6))
    check('actual_AB_completed', ab.get('status') == 'passed' and ab.get('real_function_called') is True)
    check('network_to_AB_control_bound', net['output_csv_sha256'] == ab['input_csv_sha256']
          == _roger_sha(ROOT / 'submission_pre_apex_extlib.csv'))
    check('final_AB_csv_bound', ab['output_csv_sha256'] == _roger_sha(ROOT / 'submission.csv'))
    check('both_AB_libraries_loaded', ab.get('source_a_references', 0) > 0 and ab.get('source_b_references', 0) > 0)
    before = pd.read_csv(ROOT / 'submission_pre_n1c.csv', dtype=str, keep_default_na=False)
    network = pd.read_csv(ROOT / 'submission_after_rogers_network.csv', dtype=str, keep_default_na=False)
    final = pd.read_csv(ROOT / 'submission.csv', dtype=str, keep_default_na=False)
    check('sample_ids_and_schema_exact', all(list(frame.columns) == ['molecule_id','smiles']
          and frame.molecule_id.tolist() == SAMPLE_IDS and frame.molecule_id.is_unique
          for frame in (before, network, final)))
    check('network_candidate_multisets_exact', all(Counter(a.split(';')) == Counter(b.split(';'))
          for a,b in zip(before.smiles, network.smiles)))
    check('CSV_candidate_counts_valid', all(1 <= len(s.split(';')) <= 25 and all(s.split(';')) for s in final.smiles))
    normalizer = rdMolStandardize.TautomerEnumerator()
    def identity(smiles):
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return None
        Chem.RemoveStereochemistry(mol)
        return Chem.MolToInchiKey(normalizer.Canonicalize(mol))[:14]
    before_keys = [[identity(s) for s in raw.split(';')] for raw in before.smiles]
    network_keys = [[identity(s) for s in raw.split(';')] for raw in network.smiles]
    final_keys = [[identity(s) for s in raw.split(';')] for raw in final.smiles]
    check('network_identity_multisets_exact', all(Counter(a) == Counter(b) for a,b in zip(before_keys, network_keys)))
    check('final_candidates_parse_as_official_identities', all(key for group in final_keys for key in group))
    duplicates = [mid for mid, keys in zip(final.molecule_id, final_keys) if len(keys) != len(set(keys))]
    # Raw upstream AB is reproduced, including its duplicate-identity behavior;
    # we record duplicates rather than silently add our champion's identity guard.
    if IS_RERUN:
        check('full_pipeline_completed', PIPELINE_DONE and NEURAL_OK and CONSENSUS_OK and SUBMITTED == VARIANT)
        receipt = json.loads((ROOT / 'execution_receipt.json').read_text())
        check('actual_full_query_denominator', receipt.get('is_full_run') is True
              and receipt.get('processed_molecules') == len(SAMPLE_IDS) > 0)
        check('actual_mass_layer_executed', MASS_REPORT.get('status') == 'on' and MASS_LEAD_REPORT.get('status') == 'ran')
        check('original_RR_disabled', RR8_REPORT.get('status') == 'off in this preset')
        a = pd.read_parquet(ROOT / 'neural_public.parquet').set_index(['molecule_id','smiles'])
        b = pd.read_parquet(ROOT / 'neural_ours.parquet').set_index(['molecule_id','smiles'])
        c = pd.read_parquet(ROOT / 'neural_candidate_features.parquet').set_index(['molecule_id','smiles'])
        check('dual_candidate_keys', a.index.is_unique and b.index.is_unique and c.index.is_unique
              and set(a.index) == set(b.index) == set(c.index))
        b,c = b.reindex(a.index), c.reindex(a.index)
        def z(series):
            group = series.groupby(level=0)
            return (series-group.transform('mean'))/group.transform(lambda x:x.std(ddof=0)).clip(lower=1e-6)
        dual = .5*z(a.neural_score.fillna(0.0)) + .5*z(b.neural_score.fillna(0.0))
        check('actual_dual_scores_exact', np.array_equal(dual.to_numpy(), c.neural_score.to_numpy()))
    else:
        check('visible_parent_fast_explicit', not RUN_PIPELINE and not PIPELINE_DONE)
    result = dict(status='passed', branch='rogers_repro', version=1, recipe_sha256=expected['recipe_sha256'],
                  mode='hidden_full' if IS_RERUN else 'fast_static', checks=checks,
                  csv_sha256=_roger_sha(ROOT / 'submission.csv'), network=net, external_AB=ab,
                  upstream_source_sha256=expected['upstream_source_sha256'],
                  visible_parent_model_inference_executed=bool(RUN_PIPELINE),
                  network_executed=True, external_matching_executed=True,
                  duplicate_identity_rows=duplicates,
                  selected_libraries=selected_libraries,
                  official_score_claim=False, locally_reproduced_score=None)
    (ROOT / 'rogers_repro_audit.json').write_text(json.dumps(result, indent=2) + '\n')
    return result
try:
    ROGERS_REPRO_AUDIT = _audit_rogers_reproduction()
except BaseException:
    (ROOT / 'submission.csv').unlink(missing_ok=True)
    raise
'''


def main():
    if OUT.exists():
        raise FileExistsError('Preserve frozen stage; create an explicit revision')
    assert sha(SOURCE) == SOURCE_PIN
    parent = read(SOURCE)
    assert len(parent['cells']) > 25
    book = copy.deepcopy(parent)
    network = function_text(source(parent['cells'][24]), '_n1c')
    ab = function_text(source(parent['cells'][25]), '_apex_extlib_overlay')
    assert hashlib.sha256(network.encode()).hexdigest() == '33153de76fccebe4ed2325bea7649573219e4cfb964483cd5c335ac7dc7e93b8'
    assert hashlib.sha256(ab.encode()).hexdigest() == '9ceaa95ddda0fb304758c9acd7dd1f256c528fcb4a8304c0152f8b6d8e3e3e76'
    # Freeze the one intended final checkpoint, rather than the first rglob hit.
    selector = source(book['cells'][15])
    anchor = '    if not _hits:\n'
    assert selector.count(anchor) == 1
    pinned_selector = ("    _hits = sorted([_p for _p in _hits if 'casmi_spectrum_model_ours_v80' in _p.as_posix() "
                       "and hashlib.sha256(_p.read_bytes()).hexdigest() == " + repr(V2) + "], key=lambda _p: _p.as_posix())\n"
                       "    if len(_hits) != 1:\n"
                       "        raise RuntimeError('Expected one fixed V80 final checkpoint, no silent public fallback')\n")
    book['cells'][15]['source'] = selector.replace(anchor, pinned_selector + anchor)
    # Only wrap invocation; original definitions stay byte-for-byte.
    net_cell = source(book['cells'][24])
    assert net_cell.count('    _n1c(LAM=0.35, TAU=0.6)') == 1
    book['cells'][24]['source'] = net_cell.replace('    _n1c(LAM=0.35, TAU=0.6)',
                                                  "    _observe_rogers_call('network', _n1c, LAM=0.35, TAU=0.6)")
    ab_cell = source(book['cells'][25])
    assert ab_cell.count('    _apex_extlib_overlay()') == 1
    book['cells'][25]['source'] = ab_cell.replace('    _apex_extlib_overlay()',
                                                "    _observe_rogers_call('ab', _apex_extlib_overlay)")
    assert function_text(source(book['cells'][24]), '_n1c') == network
    assert function_text(source(book['cells'][25]), '_apex_extlib_overlay') == ab
    versions = read(ROOT / 'reports/public_review_20261116/notebooks/roger_dataset_versions.json')
    versions = {row['ref']: row['current_version_number'] for row in versions['datasets']}
    upstream_meta = read(SOURCE_DIR / 'api_metadata_full.json')
    datasets = [ref + '/' + str(versions[ref]) for ref in upstream_meta['datasetDataSources']]
    assert len(datasets) == 10
    metadata = dict(id=TARGET, title='CASMI26 Rogers0492 reproduction 1117', code_file='notebook.ipynb',
                    language='python', kernel_type='notebook', is_private=True, enable_gpu=True, enable_internet=False,
                    machine_shape=upstream_meta['machineShape'], docker_image=upstream_meta['dockerImage'],
                    competition_sources=['enveda-CASMI26-molecule-id-mass-spectra'],
                    dataset_sources=datasets, kernel_sources=['popwenman/casmi26-scorer-train-v80/1'])
    recipe = dict(branch=BRANCH, target=TARGET, upstream='rogersjohnson/casmi26-l4-lam035', upstream_version=1,
                  upstream_source_sha256=SOURCE_PIN, method='Original public Rogers recipe, network LAM=.35 before original raw AB',
                  author_reported_public_score=.492, independently_reported_reproduction_ref=58380172,
                  own_public_score=None, baseline_for_comparison_ref=58156482, baseline_for_comparison_public_score=.488,
                  configuration=dict(POP_W=.12,SPEC_W=.12,NP_W=.12,V8='MASS',LAM=.35,TAU=.6,learned_late_head=False),
                  original_functions_unchanged=True, original_merge_warning_policy_retained=True,
                  original_raw_AB_no_added_identity_guard=True,
                  runtime_adaptations=['Select exactly one V80 final with intended SHA instead of arbitrary first recursive hit',
                                       'Wrap original network/AB calls with observers; require normal completion and both AB libraries loaded',
                                       'Append source/config/model/CSV/real-hidden-pipeline observers; no score mathematics changed',
                                       'Freeze numeric dataset/current kernel versions; preserve upstream docker and accelerator'],
                  parent_visible_mode='fast', visible_network_and_AB_real=True, new_full_pipeline_local_validation=False,
                  validation_mode='fast_static', no_new_model_training=True,
                  public_model_pins=PUBLIC_PINS, v2_sha256=V2,
                  function_pins=dict(network=hashlib.sha256(network.encode()).hexdigest(), ab=hashlib.sha256(ab.encode()).hexdigest()),
                  numeric_dataset_versions_are_current_readback_not_proven_upstream_session=True,
                  full_hidden_inference_success=False, gain_claim=False, user_authorized_submission=True)
    raw = (json.dumps(recipe, ensure_ascii=False, indent=2) + '\n').encode()
    expected = dict(recipe_sha256=hashlib.sha256(raw).hexdigest(), upstream_source_sha256=SOURCE_PIN,
                    public_pins=PUBLIC_PINS, v2_sha256=V2, function_pins=recipe['function_pins'],
                    external_library_files=read(ROOT / 'submission/optimization_20261109/mass_guarded_extlib/recipe.json')['files'],
                    frozen_sha256='d1e757c2b71b46e6e8a5777f14302a4737d0fdbcd56d8365093c039b93c5fd88')
    functions = {name:base64.b64encode(value.encode()).decode() for name,value in [('network',network),('ab',ab)]}
    observer = OBSERVER.replace('__EXPECTED__', repr(expected)).replace('__FUNCTIONS__', repr(functions))
    book['cells'].insert(24, codecell(observer))
    book['cells'].append(codecell(AUDIT))
    changed = {15,24,25}
    retained = all(source(book['cells'][i + (1 if i >= 24 else 0)]) == source(parent['cells'][i])
                   for i in range(len(parent['cells'])) if i not in changed)
    assert retained
    for c in book['cells']:
        if c['cell_type'] == 'code':
            compile(source(c), 'frozen_rogers_reproduction', 'exec')
            c['outputs'] = []; c['execution_count'] = None
    OUT.mkdir(parents=True)
    save(OUT / 'notebook.ipynb', book)
    save(OUT / 'kernel-metadata.json', metadata)
    (OUT / 'recipe.json').write_bytes(raw)
    checks = dict(upstream_source_pin=True, original_configuration_exact=True,
                  original_merge_warning_policy_exact=source(parent['cells'][21]) == source(book['cells'][21]),
                  original_algorithm_cells_retained=retained, original_network_function_bytes=True,
                  original_AB_function_bytes=True, intended_scorer_final_pinned=True,
                  no_champion_head_or_identity_guard_added=True, source_compiles=True,
                  private_offline_gpu=True, dataset_and_kernel_numeric_versions_pinned=True,
                  visible_fast_not_claimed_full=True)
    review = dict(status='passed', target=TARGET, version=1, notebook_sha256=sha(OUT / 'notebook.ipynb'), checks=checks,
                  scope='Static source/config/asset binding only; visible network/AB and hidden complete inference await actual runs')
    save(OUT / 'static_review.json', review)
    branch = dict(name=BRANCH, target=TARGET, version=1, stage_dir=OUT.relative_to(ROOT).as_posix(),
                  notebook_sha256=review['notebook_sha256'], metadata_sha256=sha(OUT / 'kernel-metadata.json'),
                  description='CASMI26 20261117 Rogers public0492 recipe reproduction LAM035 rawAB V1',
                  validation_mode='fast_static', static_review_path=(OUT / 'static_review.json').relative_to(ROOT).as_posix(),
                  required_runtime_audits=[dict(name='rogers_repro_audit.json',
                      expected_fields=dict(status='passed',branch=BRANCH,version=1,mode='fast_static',recipe_sha256=expected['recipe_sha256']),
                      required_true_checks=['configuration_exact','official_rdkit','frozen_source_pin','public_model_pins',
                          'actual_v80_final_is_fixed_v2','two_distinct_models','all_external_library_pins','original_function_files_pinned',
                          'actual_network_completed','actual_network_parameters','actual_AB_completed',
                          'network_to_AB_control_bound','final_AB_csv_bound','both_AB_libraries_loaded',
                          'sample_ids_and_schema_exact','network_candidate_multisets_exact','CSV_candidate_counts_valid',
                          'network_identity_multisets_exact','final_candidates_parse_as_official_identities','visible_parent_fast_explicit'])])
    save(OUT / 'branch_spec.json', branch)
    save(OUT / 'prepare_receipt.json', dict(status='prepared_no_network_writes', target=TARGET,
         notebook_sha256=branch['notebook_sha256'], recipe_sha256=expected['recipe_sha256'], upstream_source_sha256=SOURCE_PIN,
         full_pipeline_local_validation=False))
    print(json.dumps(dict(status='prepared',target=TARGET,notebook_sha256=branch['notebook_sha256'],
                         recipe_sha256=expected['recipe_sha256'])))


if __name__ == '__main__':
    main()
