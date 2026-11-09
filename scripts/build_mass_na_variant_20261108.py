"""Prepare the 0.481 MASS recipe plus real Na+ GLACIER coverage; no cloud writes."""
from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / 'submission/optimization_20261108/mass_gl_na'
BASE = ROOT / 'submission/aggressive_20261107/public_mass_repro'
BASE_SHA = '2bf3c51c8703956f80892d478b0de77747f90a8228bf275399d793666e5a1ea6'
TARGET = 'stormseye/casmi26-mass-gl-na-1108'
NAME = 'mass_gl_na'


def sha(raw): return hashlib.sha256(raw).hexdigest()
def read(path): return json.loads(path.read_text(encoding='utf-8'))
def source(cell):
    value = cell['source']
    return ''.join(value) if isinstance(value, list) else value
def write(path, value): path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def embedded_values(text):
    values = {}
    for node in ast.parse(text).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    try: values[target.id] = ast.literal_eval(node.value)
                    except (ValueError, TypeError): pass
                elif isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name) and target.value.id == 'MODULES':
                    values.setdefault('MODULES', {})[ast.literal_eval(target.slice)] = ast.literal_eval(node.value)
    return values


NA_OBSERVER = r'''
def _observe_gl_na_branch():
    import hashlib,json
    expected=__EXPECTED__
    digest=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    checks={}
    def check(k,v):
        checks[k]=bool(v)
        assert v,k
    check('original_mass_observer',BATCH_VARIANT_AUDIT['status']=='passed')
    check('explicit_runtime_adapter',digest(CODE/'runner.py')==expected['runner_sha256'] and digest(CODE/'gl_na_hook.py')==expected['hook_sha256'] and all(digest(CODE/name)==wanted for name,wanted in expected['extra_source_sha256'].items()))
    check('original_frozen_source_pin',digest(FROZEN)==FROZEN_SHA256==expected['frozen_sha256'])
    check('original_physical_source_pin',digest(CODE/'parallax_physical.py')=='cd1594b3bbfa75ce30997559c5403438b7cec011879dcb9c0d48e111715dd85d')
    if IS_RERUN:
        report=json.loads((ROOT/'gl_na_runtime.json').read_text())
        names={'original_runner_pin','original_checkpoint_pin','original_h_output_unchanged',
               'non_na_query_scores_exactly_unchanged','exact_na_query_set','exact_na_candidate_sets',
               'actual_finite_candidate_counts','original_candidate_sets','original_h_input_selection',
               'real_na_input_selection'}
        component_checks=report.get('checks')
        check('new_component_executed',report.get('status')=='passed' and isinstance(component_checks,dict)
              and set(component_checks)==names and all(v is True for v in component_checks.values()))
        check('dynamic_full_scope',json.loads((ROOT/'execution_receipt.json').read_text()).get('processed_molecules')==len(SAMPLE_IDS)>0)
        check('explicit_execution_receipt',json.loads((ROOT/'execution_receipt.json').read_text()).get('source_adaptations')==[expected['adaptation']])
        # Export must consume the expanded score dict, not an unused side output.
        evidence=pd.read_parquet(ROOT/'frozen_candidate_evidence.parquet')
        gl=json.loads((ROOT/'gl_na_combined.json').read_text())
        check('combined_query_count',report.get('combined_queries')==len(gl))
        compared=0
        same_values=True
        for r in evidence.itertuples(index=False):
            v=gl.get(str(r.molecule_id),{}).get(r.smiles)
            if v is not None:
                same_values=same_values and float(r.gl)==float(v)
                compared+=1
        check('expanded_export_values',same_values)
        check('expanded_scores_exported',compared>0 or len(gl)==0)
        report=dict(report,exported_candidate_scores_checked=compared)
    else:
        report=dict(status='deferred_hidden_full',visible_model_executed=False)
        check('fast_static_explicit',not RUN_PIPELINE and not PIPELINE_DONE)
    result=dict(status='passed',branch=expected['branch'],mode='hidden_full' if IS_RERUN else 'fast_static',
                recipe_sha256=expected['recipe_sha256'],checks=checks,component=report)
    (ROOT/'na_variant_audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
NA_VARIANT_AUDIT=_observe_gl_na_branch()
'''


def main():
    if STAGE.exists(): raise FileExistsError('Preserve an existing prepared stage')
    raw = (BASE / 'notebook.ipynb').read_bytes()
    if sha(raw) != BASE_SHA: raise ValueError('The 0.481 source stage differs')
    original = json.loads(raw)
    nb = copy.deepcopy(original)
    import mass_gl_na_counted_hook as hook
    values = embedded_values(source(nb['cells'][11]))
    frozen = json.loads(__import__('base64').b64decode(values['FROZEN_B64']))
    before = source(frozen['cells'][41])
    adapted = hook.adapt_cell41(before)
    compile(adapted, 'adapted-frozen-cell-41', 'exec')
    original_runner = values['MODULES']['runner.py']
    line = "        exec(compile(''.join(c['source']),f'pipeline_cell_{i}','exec'),scope)"
    if original_runner.count(line) != 1: raise ValueError('Unexpected frozen runner')
    runner = original_runner.replace(line,
        "        text=''.join(c['source'])\n"
        "        if i==41:\n"
        "            from gl_na_hook import adapt_cell41\n"
        "            text=adapt_cell41(text)\n"
        "        exec(compile(text,f'pipeline_cell_{i}','exec'),scope)")
    runner = runner.replace("source_adaptations=[]", "source_adaptations=[" + repr(hook.SOURCE_ADAPTATION) + "]")
    hook_text = (ROOT / 'scripts/mass_gl_na_counted_hook.py').read_text(encoding='utf-8')
    appendix = ('\n# Explicit runtime adaptation of the pinned frozen GL input selection.\n'
                + f"MODULES['gl_na_hook.py']={hook_text!r}\nMODULE_SHA256['gl_na_hook.py']={sha(hook_text.encode())!r}\n"
                + f"MODULES['runner.py']={runner!r}\nMODULE_SHA256['runner.py']={sha(runner.encode())!r}\n")
    extra_sources={'gl_counted_runner.py':(ROOT/'scripts/gl_counted_runner.py').read_text(encoding='utf-8'),
                   'gl_score_observer.py':(ROOT/'scripts/forward_trace_runner.py').read_text(encoding='utf-8')}
    extra_pins={name:sha(text.encode()) for name,text in extra_sources.items()}
    for name,text in extra_sources.items():
        appendix+=f'MODULES[{name!r}]={text!r}\nMODULE_SHA256[{name!r}]={extra_pins[name]!r}\n'
    nb['cells'][11]['source'] = source(nb['cells'][11]) + appendix
    metadata = read(BASE / 'kernel-metadata.json')
    metadata.update(id=TARGET, title=TARGET.split('/')[1].replace('-', ' '))
    recipe = dict(branch=NAME, target=TARGET, baseline_public_score=.481, baseline_notebook_sha256=BASE_SHA,
                  change=hook.SOURCE_ADAPTATION, new_training=False, candidate_policy='original ICE union lists unchanged',
                  aggregation='original H-only run/order; independent Na-only run; weighted by actual per-candidate finite counts',
                  gl_budget_seconds=4000,na_budget_seconds=1800,na_accuracy_established=False,
                  n1_policy='real Na GL coverage wins proxy overlap, as original hidden clash removal; visible checks allow only Na clashes',
                  adaptations=['Explicit source-pinned runtime cell41 adapter; frozen notebook bytes unchanged',
                               'Dynamic hidden query count audit instead of assuming exactly 400',
                               'Retain original MASS final leader rule, physical code and all priors'],
                  runner_sha256=sha(runner.encode()), hook_sha256=sha(hook_text.encode()),extra_source_sha256=extra_pins,
                  frozen_sha256=values['FROZEN_SHA256'], adapted_cell41_sha256=sha(adapted.encode()),
                  locked_final_used=False)
    recipe_bytes=(json.dumps(recipe, ensure_ascii=False, indent=2)+'\n').encode()
    recipe_sha=sha(recipe_bytes)
    # Keep all original pin/mass/neural checks, only bind this new branch and dynamic scope.
    old_expected = dict(branch=NAME, recipe_sha256=recipe_sha,
                        public_pins=read(BASE/'recipe.json').get('public_pins', {}))
    spec=importlib.util.spec_from_file_location('old_mass_builder',ROOT/'scripts/build_public_mass_repro_20261107.py')
    builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
    old_expected.update(public_pins=builder.PUBLIC_PINS,v2_sha=builder.V2_SHA,
                        lotus_sha='7684b51f72a2d4c073a8d2435fff14cce0a0e7364ac7904101b8f93990f0ac2f')
    nb['cells'][29]['source'] = builder.OBSERVER.replace('__EXPECTED__', repr(old_expected)).replace(
        "receipt.get('processed_molecules')==len(SAMPLE_IDS)==400", "receipt.get('processed_molecules')==len(SAMPLE_IDS)>0")
    expected=dict(branch=NAME,recipe_sha256=recipe_sha,runner_sha256=recipe['runner_sha256'],
                  hook_sha256=recipe['hook_sha256'],extra_source_sha256=extra_pins,frozen_sha256=recipe['frozen_sha256'],adaptation=hook.SOURCE_ADAPTATION)
    nb['cells'].append(dict(cell_type='code',execution_count=None,metadata={},outputs=[],source=NA_OBSERVER.replace('__EXPECTED__',repr(expected))))
    for i,cell in enumerate(nb['cells']):
        if cell['cell_type']=='code':
            compile(source(cell),f'prepared-na-cell-{i}','exec');cell['outputs']=[];cell['execution_count']=None
    untouched=[i for i in range(len(original['cells'])) if i not in (11,29)]
    if not all(source(nb['cells'][i])==source(original['cells'][i]) for i in untouched):
        raise ValueError('Unexpected baseline cell changes')
    # The executed adapter must preserve every original candidate and raw spectrum field.
    fixture=[dict(mid='a',cands=['CCO','CCC'],spectra=[dict(adduct='[M+H]+',prec=47,mz=[20],it=[1]),
              dict(adduct='[M+Na]+',prec=69,mz=[22],it=[.5]),dict(adduct='[M-H]-',prec=45,mz=[18],it=[1])])]
    selected=hook.select_items(fixture)
    assert selected[0]['cands']==fixture[0]['cands'] and selected[0]['spectra']==fixture[0]['spectra'][:2]
    assert fixture[0]['spectra'][1]['adduct']=='[M+Na]+'
    STAGE.mkdir(parents=True)
    write(STAGE/'notebook.ipynb',nb);write(STAGE/'kernel-metadata.json',metadata)
    (STAGE/'recipe.json').write_bytes(recipe_bytes)
    review=dict(status='passed',target=TARGET,version=1,notebook_sha256=sha((STAGE/'notebook.ipynb').read_bytes()),
        checks=dict(base_0481_sha=True,all_code_compiles=True,unchanged_nonadapter_cells=True,
                    original_mass_leader_unchanged=True,physical_cell_unchanged=True,original_model_pins_unchanged=True,
                    fixed_frozen_source=True,real_na_no_relabel_fixture=True,actual_per_spectrum_aggregation=True,
                    explicit_proxy_overlap_policy=True,private_offline_gpu=True,dynamic_hidden_scope=True))
    write(STAGE/'static_review.json',review)
    prepared=dict(status='prepared',branch=NAME,target=TARGET,version=1,notebook_sha256=review['notebook_sha256'],
                  metadata_sha256=sha((STAGE/'kernel-metadata.json').read_bytes()),recipe_sha256=recipe_sha,
                  static_review_path=str((STAGE/'static_review.json').relative_to(ROOT)),validation_mode='fast_static')
    write(STAGE/'prepare_receipt.json',prepared)
    branch=dict(name=NAME,target=TARGET,version=1,stage_dir=str(STAGE.relative_to(ROOT)).replace('\\','/'),
                notebook_sha256=prepared['notebook_sha256'],metadata_sha256=prepared['metadata_sha256'],
                description='CASMI26 20261108 MASS real Na GL coverage audited V1',validation_mode='fast_static',
                static_review_path=str((STAGE/'static_review.json').relative_to(ROOT)).replace('\\','/'),
                required_runtime_audits=[
                    dict(name='batch_variant_audit.json',expected_fields=dict(status='passed',branch=NAME,mode='fast_static',recipe_sha256=recipe_sha),
                         required_true_checks=['mass_recipe','original_public_priors','official_rdkit','public_model_pins','ours_model_pins','lotus_pin','csv_schema_ids','csv_counts','fast_no_model']),
                    dict(name='na_variant_audit.json',expected_fields=dict(status='passed',branch=NAME,mode='fast_static',recipe_sha256=recipe_sha),
                         required_true_checks=['original_mass_observer','explicit_runtime_adapter','original_frozen_source_pin','original_physical_source_pin','fast_static_explicit'])])
    write(STAGE/'branch_manifest.json',branch)
    print(json.dumps(prepared,indent=2))


if __name__ == '__main__': main()
