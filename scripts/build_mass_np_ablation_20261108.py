"""Prepare one final-NP-bonus ablation of the confirmed 0.481 MASS recipe.

No cloud writes, training, model inference, or evaluation labels are used.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import json
from pathlib import Path

from build_public_mass_repro_20261107 import (
    OBSERVER as BASE_OBSERVER, PUBLIC_PINS, SOURCE, SOURCE_SHA, V2_SHA, src)

ROOT = Path(__file__).resolve().parents[1]
NAME = 'mass_no_np_bonus'
TARGET = 'stormseye/casmi26-mass-no-np-bonus-1108'
OUT = ROOT / 'submission/optimization_20261108' / NAME
LOTUS_SHA = '7684b51f72a2d4c073a8d2435fff14cce0a0e7364ac7904101b8f93990f0ac2f'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Expected exactly one source binding: ' + old[:90])
    return text.replace(old, new, 1)


def instrument_merge(text):
    binding = "    evidence_by_mid = nf_evidence or {}"
    text = replace_once(text, binding, binding + "\n    counts.update(np_scored_candidates=0, np_member_scored_candidates=0, np_bonus_sum=0.0, np_bonus_absmax=0.0)")
    binding = "                    np_val = float(np_map.get(k14, 0.0))"
    text = replace_once(text, binding, binding + "\n                    np_bonus = float(NP_W) * np_val\n                    counts['np_scored_candidates'] += 1\n                    counts['np_member_scored_candidates'] += int(np_val != 0.0)\n                    counts['np_bonus_sum'] += np_bonus\n                    counts['np_bonus_absmax'] = max(counts['np_bonus_absmax'], abs(np_bonus))")
    text = replace_once(text, '+ NP_W * np_val', '+ np_bonus')
    return text


def merge_function(text):
    node = next(x for x in ast.parse(text).body if isinstance(x, ast.FunctionDef) and x.name == 'pxm_merge')
    return ast.Module(body=[node], type_ignores=[])


def build():
    if OUT.exists():
        raise FileExistsError('Preserve the already-frozen preparation stage')
    raw = SOURCE.read_bytes()
    if sha(raw) != SOURCE_SHA:
        raise ValueError('Original public MASS source pin changed')
    original = json.loads(raw)
    nb = copy.deepcopy(original)
    nb['cells'][4]['source'] = replace_once(src(nb['cells'][4]),
        'POP_W, SPEC_W, NP_W = 0.10, 0.10, 0.12',
        'POP_W, SPEC_W, NP_W = 0.10, 0.10, 0.0')
    nb['cells'][20]['source'] = instrument_merge(src(nb['cells'][20]))
    changes = [i for i, (before, after) in enumerate(zip(original['cells'], nb['cells'])) if src(before) != src(after)]
    if changes != [4, 20]:
        raise ValueError('Unexpected scoring-source changes')
    metadata = read(ROOT/'submission/aggressive_20261107/public_mass_repro/kernel-metadata.json')
    metadata.update(id=TARGET, title=TARGET.split('/')[1].replace('-', ' '), code_file='notebook.ipynb')
    if metadata['is_private'] is not True or metadata['enable_internet'] is not False or metadata['enable_gpu'] is not True:
        raise ValueError('Expected private offline GPU notebook')
    # The candidate pool, physical model, dual neural model, library gate, POP/SPEC,
    # final mass leader correction, and outsider/LOTUS fill remain byte-identical.
    recipe = dict(branch=NAME, target=TARGET, upstream='popwenman/casmi26-0482-gold-apex-v22',
        upstream_version=2, upstream_source_sha256=SOURCE_SHA, baseline_own_public_score=0.481,
        recipe='Disable only final membership bonus: NP_W 0.12 -> 0.0', validation_mode='fast_static',
        mechanism_scope='Only pxm_merge ranks 2-25 membership contribution; not all NP information in the trained base.',
        unchanged=['POP_W=.10', 'SPEC_W=.10', 'LIB_HIT_GATE=.78', 'public/v2=.5/.5',
            'physical leader logic', 'final MASS leader correction', 'outsider neural-only vacant-slot fill',
            'LOTUS candidate vacant-slot fill', 'all original candidate generators and models'],
        adaptations=['Retain confirmed 0.481 recipe assets and runtime image.',
            'Instrument final NP contribution without changing candidate scores.',
            'Observer full-scope check uses dynamic sample_submission size.'],
        new_training=False, locked_final_used=False)
    recipe_raw = (json.dumps(recipe, ensure_ascii=False, indent=2) + '\n').encode()
    recipe_sha = sha(recipe_raw)
    expected = dict(branch=NAME, recipe_sha256=recipe_sha, public_pins=PUBLIC_PINS,
                    v2_sha=V2_SHA, lotus_sha=LOTUS_SHA)
    observer = BASE_OBSERVER
    observer = replace_once(observer,
        "check('original_public_priors',POP_W==0.10 and SPEC_W==0.10 and NP_W==0.12 and LIB_HIT_GATE==0.78)",
        "check('np_ablation_configuration',POP_W==0.10 and SPEC_W==0.10 and NP_W==0.0 and LIB_HIT_GATE==0.78)\n    check('other_merge_switches_preserved',PIN_OLD_LEADER is True and OUTSIDER_FILL is True and FRAG_ON_V2 is True)")
    observer = replace_once(observer,
        "receipt.get('processed_molecules')==len(SAMPLE_IDS)==400",
        "receipt.get('processed_molecules')==len(SAMPLE_IDS) and len(SAMPLE_IDS)>0")
    observer = replace_once(observer,
        "check('rr_disabled',RR8_REPORT.get('status')=='off in this preset')",
        "check('rr_disabled',RR8_REPORT.get('status')=='off in this preset')\n        check('merge_layer_executed',MERGE_REPORT.get('status')=='applied' and MERGE_REPORT.get('rows')==len(SAMPLE_IDS))\n        check('np_score_path_executed',MERGE_REPORT.get('np_scored_candidates',0)>0)\n        check('np_bonus_exactly_zero',MERGE_REPORT.get('np_bonus_sum')==0.0 and MERGE_REPORT.get('np_bonus_absmax')==0.0)")
    observer = replace_once(observer,
        "check('fast_no_model',not RUN_PIPELINE and not PIPELINE_DONE)",
        "check('fast_no_model',not RUN_PIPELINE and not PIPELINE_DONE)\n        check('merge_fast_skip_explicit',MERGE_REPORT.get('status')=='skipped_fast_commit')")
    observer = replace_once(observer,
        'mass_report=MASS_REPORT,mass_lead_report=MASS_LEAD_REPORT,',
        "mass_report=MASS_REPORT,mass_lead_report=MASS_LEAD_REPORT,\n        np_contribution_audit={k:MERGE_REPORT.get(k) for k in ('status','np_scored_candidates','np_member_scored_candidates','np_bonus_sum','np_bonus_absmax')},\n        ablation_scope='final pxm_merge membership bonus only; outsider and LOTUS fill unchanged',")
    observer = observer.replace('__EXPECTED__', repr(expected))
    nb['cells'].append(dict(cell_type='code', execution_count=None, metadata={}, outputs=[], source=observer))
    for cell in nb['cells']:
        if cell['cell_type'] == 'code':
            compile(src(cell), 'mass-no-np-bonus', 'exec')
            cell['outputs'], cell['execution_count'] = [], None
    OUT.mkdir(parents=True)
    write(OUT/'notebook.ipynb', nb)
    write(OUT/'kernel-metadata.json', metadata)
    (OUT/'recipe.json').write_bytes(recipe_raw)
    static = dict(status='passed', target=TARGET, version=1,
        notebook_sha256=sha((OUT/'notebook.ipynb').read_bytes()), checks=dict(
            upstream_mass_pin=True, changed_original_cells_exactly_4_20=True,
            all_original_cells_otherwise_identical=True, np_weight_only_configuration_change=True,
            observer_configuration_matches_ablation=True, observer_actual_np_contribution_required=True,
            observer_dynamic_hidden_sample_size=True, all_code_compiles=True,
            private_offline_gpu=True, metadata_inherits_confirmed_baseline_assets=True,
            no_training_or_labels_used=True))
    write(OUT/'static_review.json', static)
    receipt = dict(status='prepared', branch=NAME, target=TARGET, version=1,
        notebook_sha256=static['notebook_sha256'], metadata_sha256=sha((OUT/'kernel-metadata.json').read_bytes()),
        recipe_sha256=recipe_sha, static_review_path=str((OUT/'static_review.json').relative_to(ROOT)).replace('\\','/'),
        validation_mode='fast_static')
    write(OUT/'prepare_receipt.json', receipt)
    branch = dict(name=NAME, target=TARGET, version=1,
        stage_dir=str(OUT.relative_to(ROOT)).replace('\\','/'), notebook_sha256=receipt['notebook_sha256'],
        metadata_sha256=receipt['metadata_sha256'],
        description='CASMI26 20261108 MASS no final NP bonus audited V1', validation_mode='fast_static',
        static_review_path=receipt['static_review_path'], required_runtime_audits=[dict(
            name='batch_variant_audit.json', expected_fields=dict(status='passed', mode='fast_static',
                branch=NAME, recipe_sha256=recipe_sha), required_true_checks=[
                    'mass_recipe','np_ablation_configuration','other_merge_switches_preserved','official_rdkit',
                    'public_model_pins','ours_model_pins','two_distinct_models','lotus_pin',
                    'csv_schema_ids','csv_counts','fast_no_model','merge_fast_skip_explicit'])])
    write(OUT/'branch_spec.json', branch)
    print(json.dumps(receipt, indent=2))
    return receipt


if __name__ == '__main__':
    build()
