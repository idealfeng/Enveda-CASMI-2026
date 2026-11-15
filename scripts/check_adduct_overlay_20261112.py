"""Real A/B reference and exact staged entry canary; no GPU or MRR claims."""
from pathlib import Path
import argparse
import ast
import base64
import copy
import json
import sys
import time
import zlib

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import adduct_external_overlay_20261112 as module


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tag', required=True)
    p.add_argument('--stage', action='store_true')
    args = p.parse_args()
    out = ROOT / 'runs' / ('adduct_overlay_canary_20261112_' + args.tag)
    out.mkdir(exist_ok=False)
    old = ROOT / 'runs/external_overlay_actual_canary_20261109'
    inp = old / 'input'
    comp = inp / 'enveda-CASMI26-molecule-id-mass-spectra'
    control = pd.read_csv(old / 'hidden_actual/submission_external_control.csv', dtype=str, keep_default_na=False)
    evidence = pd.read_parquet(old / 'hidden_actual/frozen_candidate_evidence.parquet')
    function = ROOT / 'reports/optimization_20261112/adduct_source/ozertuu_v18_adduct_function.py'
    files = module.read(ROOT / 'submission/optimization_20261109/mass_guarded_extlib/recipe.json')['files']
    stage = ROOT / 'submission/optimization_20261112/adduct_extlib'
    book = module.read(stage / 'notebook.ipynb') if args.stage else None
    recipe = module.read(stage / 'recipe.json') if args.stage else None
    cell = book['cells'][-1]['source'] if args.stage else None
    if isinstance(cell, list):
        cell = ''.join(cell)
    checks, cases = {}, {}
    for full in (False, True):
        label = 'hidden' if full else 'fast'
        work = out / label
        work.mkdir()
        code = work / 'code'
        code.mkdir()
        control.to_csv(work / 'submission.csv', index=False)
        evidence.to_parquet(work / 'frozen_candidate_evidence.parquet', index=False)
        base = dict(status='passed', csv_sha256=module.sha(work / 'submission.csv'))
        call_args = (work, inp, comp / 'test.parquet', full, control.molecule_id.tolist(), base, function, files)
        started = time.monotonic()
        if args.stage:
            scope = dict(Path=Path, ROOT=work, INPUT=inp, COMP=comp, CODE=code, IS_RERUN=full,
                         SAMPLE_IDS=control.molecule_id.tolist(), GUARDED_TAIL_AUDIT=base)
            exec(compile(cell, 'exact_adduct_staged_entry', 'exec'), scope)
            runtime, audit = scope['ADDUCT_OVERLAY_REPORT'], scope['ADDUCT_OVERLAY_AUDIT']
            checks[label + '_installed_pins'] = audit['installed_payload_pins'] == recipe['payload_pins']
        else:
            runtime = module.run(*call_args)
            audit = module.audit(*call_args, 'module_canary', 'fixture_only')
        final = pd.read_csv(work / 'submission.csv', dtype=str, keep_default_na=False)
        checks[label + '_actual_passed'] = audit['status'] == 'passed' and all(audit['checks'].values())
        checks[label + '_query_ids'] = final.molecule_id.tolist() == control.molecule_id.tolist()
        checks[label + '_protected'] = final.smiles.iloc[2] == control.smiles.iloc[2]
        checks[label + '_missing_query'] = final.smiles.iloc[4] == control.smiles.iloc[4]
        if full:
            checks['both_actual_reference_sources'] = runtime['reference_counts'] == module.EXPECTED_COUNTS
            checks['actual_scores_consumed'] = audit['checks']['actual_scores_consumed']
            matches = runtime['actual_matches']
            checks['actual_best_scores_observed'] = bool(matches) and any(m['cosine'] is not None and m['cosine'] >= .8 for m in matches)
            checks['actual_hits_after_massgate'] = runtime['original_report']['hits'] > 0
            saved = module.read(work / 'adduct_overlay_runtime.json')
            changed = copy.deepcopy(saved)
            selected = next(x for x in changed['actual_matches'] if x['smiles'] and x['cosine'] is not None and x['cosine'] >= .8
                            and module.exact_mass(x['smiles']) is not None and abs(module.exact_mass(x['smiles'])-x['query_neutral_mass'])/x['query_neutral_mass'] <= 15e-6)
            selected['cosine'] = .799
            write(work / 'adduct_overlay_runtime.json', changed)
            if args.stage:
                target_mod = scope['_adduct_mod']
                target_args = scope['_adduct_args']
                branch, recipe_sha = 'adduct_extlib', module.sha(stage / 'recipe.json')
            else:
                target_mod, target_args, branch, recipe_sha = module, call_args, 'module_canary', 'fixture_only'
            try:
                target_mod.audit(*target_args, branch, recipe_sha)
                checks['tampered_actual_score_rejected'] = False
            except ValueError:
                checks['tampered_actual_score_rejected'] = True
            write(work / 'adduct_overlay_runtime.json', saved)
        else:
            checks['fast_exact_control'] = final.equals(control) and runtime['library_matching_performed'] is False
        cases[label] = dict(seconds=time.monotonic()-started, reference_counts=runtime.get('reference_counts'),
                            public_hits=runtime.get('original_report', {}).get('hits'), changed_top1=runtime.get('changed_top1'))
        print(json.dumps(dict(case=label, **cases[label])), flush=True)
    # Official identity handling, public native promotion, and chemical-mass gate.
    valid_smiles = 'C;CC;CCC'
    fake = dict(smiles='[CH3:1][CH3:2]', cosine=.99, matched_peaks=4, query_neutral_mass=module.exact_mass('CC'))
    checks['native_alias_preserves_original_smiles'] = module.proposal(valid_smiles, fake)[0] == 'CC;C;CCC'
    bad = dict(fake, query_neutral_mass=module.exact_mass('CCC'))
    checks['mass_gate_rejects_wrong_structure'] = module.proposal(valid_smiles, bad)[0] == valid_smiles
    if args.stage:
        champion = module.read(ROOT / 'submission/optimization_20261109/mass_guarded_extlib/notebook.ipynb')
        checks['first32_exact_champion'] = book['cells'][:32] == champion['cells'][:32]
        work = out / 'bad_payload'
        work.mkdir()
        code = work / 'code'
        code.mkdir()
        control.to_csv(work / 'submission.csv', index=False)
        bad_control_pin = module.sha(work / 'submission.csv')
        tree = ast.parse(cell)
        node = next(n for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == '_adduct_payloads' for t in n.targets))
        packed = ast.literal_eval(node.value)
        packed[next(iter(packed))] = base64.b64encode(zlib.compress(b'bad')).decode()
        node.value = ast.parse(repr(packed), mode='eval').body
        ast.fix_missing_locations(tree)
        scope = dict(ROOT=work, CODE=code)
        try:
            exec(compile(tree, 'corrupt_payload', 'exec'), scope)
            checks['bad_payload_fails_closed'] = False
        except AssertionError:
            checks['bad_payload_fails_closed'] = not (work / 'submission.csv').exists() and module.sha(work / 'submission_adduct_preinstall_control.csv') == bad_control_pin
    report = dict(status='passed' if all(checks.values()) else 'failed', checks=checks, cases=cases,
                  module_sha256=module.sha(Path(module.__file__)), function_sha256=module.FUNCTION_SHA,
                  notebook_sha256=module.sha(stage / 'notebook.ipynb') if args.stage else None,
                  gpu_used=False, cloud_writes=False, full_upstream_pipeline=False, efficacy_or_mrr_claim=False)
    write(out / 'verification.json', report)
    if not all(checks.values()):
        raise ValueError('Canary failed: ' + repr(checks))
    dest = ROOT / 'reports/optimization_20261112' / ('adduct_stage_canary.json' if args.stage else 'adduct_module_canary.json')
    dest.parent.mkdir(parents=True, exist_ok=True)
    write(dest, dict(report, evidence=out.relative_to(ROOT).as_posix() + '/verification.json'))
    print(json.dumps(dict(status='passed', checks=sum(checks.values()), total=len(checks))))


if __name__ == '__main__':
    main()
