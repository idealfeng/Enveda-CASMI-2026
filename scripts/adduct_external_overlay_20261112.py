"""Pinned V18 external matching with observed scores and official output guard.

Only two reference observations and one best-match observation are inserted in
the public function AST. Matching mathematics and source-B +/-H assumption stay
unchanged. The audit independently rebuilds every proposal from actual scores.
"""
from __future__ import annotations
import ast
from collections import Counter
from functools import lru_cache
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import shutil

import pandas as pd

FUNCTION_SHA = '8e1439c05d7721946ab21e08fec18b4d54d890d3188bf7ec111b32712c545624'
GUARD_SHA = 'a31c55a2958139cbeea948ea4d11fa32eb40e3d3d7b0bac157f6d0fdc51025db'
EXPECTED_COUNTS = {'A': 200724, 'B': 124160}


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def guard_module():
    path = Path(__file__).with_name('external_library_overlay_20261109.py')
    if sha(path) != GUARD_SHA:
        raise ValueError('Official guard source changed')
    spec = importlib.util.spec_from_file_location('_adduct_guard_1112', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Observe(ast.NodeTransformer):
    def __init__(self):
        self.references = 0
        self.matches = 0

    def visit_Expr(self, node):
        node = self.generic_visit(node)
        call = node.value
        if (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                and isinstance(call.func.value, ast.Name) and call.func.value.id == 'refs'
                and call.func.attr == 'append'):
            label = 'A' if any(isinstance(x, ast.Name) and x.id == 'key' for x in ast.walk(call.args[0])) else 'B'
            self.references += 1
            extra = ast.parse('_observe_reference(' + repr(label) + ', refs[-1])').body[0]
            return [node, ast.copy_location(extra, node)]
        return node

    def visit_If(self, node):
        node = self.generic_visit(node)
        if ast.unparse(node.test) == 'match_smi is not None and best_cos >= TAU':
            self.matches += 1
            extra = ast.parse('_observe_match(mid, best_cos, best_k, match_smi, match_q_nm)').body[0]
            return [ast.copy_location(extra, node), node]
        return node


def observed_function(path, on_reference, on_match):
    if sha(path) != FUNCTION_SHA:
        raise ValueError('Pinned public V18 function changed')
    tree = ast.parse(Path(path).read_text(encoding='utf-8'))
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef) or tree.body[0].name != '_apex_extlib_overlay':
        raise ValueError('Expected the single public overlay function')
    observer = Observe()
    tree = observer.visit(tree)
    ast.fix_missing_locations(tree)
    if (observer.references, observer.matches) != (2, 1):
        raise ValueError('Public observation sites changed')
    scope = dict(_observe_reference=on_reference, _observe_match=on_match)
    exec(compile(tree, 'observed_pinned_public_v18_adduct', 'exec'), scope)
    return scope['_apex_extlib_overlay']


@lru_cache(maxsize=100000)
def public_identity(smiles):
    """Exactly the public proposal key, before the official validity guard."""
    from rdkit import Chem
    from rdkit.Chem.MolStandardize import rdMolStandardize
    try:
        mol = Chem.MolFromSmiles(smiles)
        return Chem.MolToInchiKey(rdMolStandardize.TautomerEnumerator().Canonicalize(mol))[:14] if mol else ''
    except Exception:
        return ''


@lru_cache(maxsize=100000)
def exact_mass(smiles):
    from rdkit import Chem
    from rdkit.Chem.rdMolDescriptors import CalcExactMolWt
    try:
        mol = Chem.MolFromSmiles(smiles)
        return float(CalcExactMolWt(mol)) if mol else None
    except Exception:
        return None


def proposal(raw, match):
    """Reconstruct the public output from an actual observed best match."""
    if not match:
        return raw, False, 'no_observed_match'
    above = (match['smiles'] is not None and match['cosine'] is not None
             and match['cosine'] >= .80 and match['matched_peaks'] >= 4)
    if not above:
        return raw, False, 'below_threshold'
    smi, nm = match['smiles'], match['query_neutral_mass']
    mass = exact_mass(smi)
    if mass is not None and abs(mass - nm) / nm > 15e-6:
        return raw, False, 'candidate_mass_rejected'
    arr = raw.split(';')
    keys = [public_identity(s) for s in arr]
    key = public_identity(smi)
    if key and key == keys[0]:
        return raw, True, 'same_leader_identity'
    if key and key in keys[1:]:
        index = keys.index(key)
        return ';'.join([arr[index]] + [s for i, s in enumerate(arr) if i != index]), True, 'native_identity_promotion'
    seen = {key} if key else set()
    out = [smi]
    for s, k in zip(arr, keys):
        if k not in seen:
            seen.add(k)
            out.append(s)
        if len(out) == 25:
            break
    if len(out) < 25:
        for s in arr:
            if s not in out:
                out.append(s)
            if len(out) == 25:
                break
    return ';'.join(out), True, 'outside_promotion'


def run(root, input_root, test_path, is_rerun, sample_ids, base_audit, source_path, expected_files):
    root = Path(root)
    final, control = root / 'submission.csv', root / 'submission_adduct_control.csv'
    shutil.copy2(final, control)
    report = dict(status='prepared', mode='hidden_full' if is_rerun else 'fast_static',
                  control_sha256=sha(control), function_sha256=FUNCTION_SHA, module_sha256=sha(__file__),
                  guard_sha256=GUARD_SHA, library_matching_performed=False)
    try:
        helper = guard_module()
        if base_audit.get('status') != 'passed' or sha(control) != base_audit['csv_sha256']:
            raise ValueError('Pre-external .482 audit/output binding failed')
        if sha(source_path) != FUNCTION_SHA:
            raise ValueError('Public source function pin differs')
        source = pd.read_csv(control, dtype=str, keep_default_na=False)
        if (list(source.columns) != ['molecule_id', 'smiles'] or source.molecule_id.tolist() != list(sample_ids)
                or not source.molecule_id.is_unique or not all(helper.valid(s) for s in source.smiles)):
            raise ValueError('Control identity/schema differs')
        report['libraries'] = helper.resolve_sources(input_root, expected_files, test_path)
        if not is_rerun:
            report.update(status='fast_static_no_matching', output_sha256=sha(final), rows=len(source),
                          checks=dict(control_bound=True, output_unchanged=True, source_pin=True,
                                      library_pins=True, ids_schema=True, official_identity=True))
            write(root / 'adduct_overlay_runtime.json', report)
            return report
        counts, peaks, matches = Counter(), Counter(), []

        def reference(label, value):
            counts[label] += 1
            peaks[label] += len(value[4])

        def match(mid, cosine, n_peaks, smiles, q_nm):
            c = float(cosine)
            matches.append(dict(molecule_id=str(mid), cosine=c if math.isfinite(c) else None,
                                matched_peaks=int(n_peaks), smiles=smiles, query_neutral_mass=float(q_nm)))

        observed = observed_function(source_path, reference, match)
        report['library_matching_performed'] = True
        observed(work=str(root), inp=str(input_root))
        if dict(counts) != EXPECTED_COUNTS:
            raise ValueError('Expected full usable A/B references; public loader may have failed')
        if sha(root / 'submission_pre_apex_extlib.csv') != sha(control):
            raise ValueError('Public function consumed another control')
        original = read(root / 'apex_extlib_audit.json')
        proposed = pd.read_csv(final, dtype=str, keep_default_na=False)
        if list(proposed.columns) != list(source.columns) or proposed.molecule_id.tolist() != list(sample_ids):
            raise ValueError('Public function changed IDs/schema')
        shutil.copy2(final, root / 'submission_adduct_proposed.csv')
        by_mid = {x['molecule_id']: x for x in matches}
        if len(by_mid) != len(matches) or not set(by_mid) <= set(sample_ids):
            raise ValueError('Best-match observations are not unique')
        details, outputs, expected_proposals = [], [], []
        for mid, old, new in zip(source.molecule_id, source.smiles, proposed.smiles):
            expected, hit, reason = proposal(old, by_mid.get(mid))
            if expected != new:
                raise ValueError('Actual public scores were not consumed as expected')
            okay = helper.valid(new)
            value = new if okay else old
            outputs.append(value)
            expected_proposals.append(expected)
            details.append(dict(molecule_id=mid, hit=hit, reason=reason, proposed_changed=new != old,
                                proposed_top1_changed=new.split(';')[0] != old.split(';')[0],
                                accepted_changed=value != old, accepted_top1_changed=value.split(';')[0] != old.split(';')[0],
                                official_guard_preserved_control=not okay))
        if (original.get('molecules') != len(source) or original.get('hits') != sum(x['hit'] for x in details)
                or original.get('promoted') != sum(x['proposed_top1_changed'] for x in details)):
            raise ValueError('Original public counters differ from actual observations')
        destination = source.copy()
        destination['smiles'] = outputs
        temp = root / 'submission_adduct_final.tmp'
        destination.to_csv(temp, index=False)
        temp.replace(final)
        report.update(status='applied', rows=len(source), reference_counts=dict(counts), reference_peaks=dict(peaks),
                      observation_sites=dict(references=2, matches=1), actual_matches=matches,
                      original_report=original, query_sha256=sha(test_path), output_sha256=sha(final), details=details,
                      changed_top1=sum(x['accepted_top1_changed'] for x in details),
                      checks=dict(control_bound=sha(control) == base_audit['csv_sha256'],
                                  original_consumed_control=True, all_reference_sources_loaded=True,
                                  actual_scores_consumed=True, original_counters_bound=True,
                                  ids_schema=True, official_identity=all(helper.valid(s) for s in outputs)))
        write(root / 'adduct_overlay_runtime.json', report)
        return report
    except BaseException as error:
        report.update(status='failed_closed', error_type=type(error).__name__)
        write(root / 'adduct_overlay_runtime.json', report)
        final.unlink(missing_ok=True)
        raise


def audit(root, input_root, test_path, is_rerun, sample_ids, base_audit, source_path, expected_files, branch, recipe_sha256):
    root = Path(root)
    helper = guard_module()
    runtime = read(root / 'adduct_overlay_runtime.json')
    control = pd.read_csv(root / 'submission_adduct_control.csv', dtype=str, keep_default_na=False)
    final = pd.read_csv(root / 'submission.csv', dtype=str, keep_default_na=False)
    checks = dict(base_audit_passed=base_audit.get('status') == 'passed',
                  control_bound=sha(root / 'submission_adduct_control.csv') == base_audit['csv_sha256'] == runtime.get('control_sha256'),
                  final_bound=sha(root / 'submission.csv') == runtime.get('output_sha256'),
                  source_function_pin=sha(source_path) == FUNCTION_SHA == runtime.get('function_sha256'),
                  module_pin=sha(__file__) == runtime.get('module_sha256'),
                  official_guard_pin=sha(Path(__file__).with_name('external_library_overlay_20261109.py')) == GUARD_SHA == runtime.get('guard_sha256'),
                  exact_ids_schema=list(final.columns) == ['molecule_id', 'smiles'] and final.molecule_id.tolist() == list(sample_ids) == control.molecule_id.tolist() and final.molecule_id.is_unique,
                  official_identities_valid=all(helper.valid(s) for s in final.smiles),
                  library_file_pins=helper.resolve_sources(input_root, expected_files, test_path) == runtime.get('libraries'),
                  runtime_checks=bool(runtime.get('checks')) and all(x is True for x in runtime['checks'].values()))
    if is_rerun:
        observations = runtime['actual_matches']
        lookup = {x['molecule_id']: x for x in observations}
        expected = [proposal(raw, lookup.get(mid)) for mid, raw in control.itertuples(index=False, name=None)]
        raw_proposals = [x[0] for x in expected]
        accepted = [new if helper.valid(new) else old for new, old in zip(raw_proposals, control.smiles)]
        proposed = pd.read_csv(root / 'submission_adduct_proposed.csv', dtype=str, keep_default_na=False)
        checks.update(actual_matching=runtime.get('status') == 'applied' and runtime.get('library_matching_performed') is True,
                      full_reference_counts=runtime.get('reference_counts') == EXPECTED_COUNTS,
                      observation_sites=runtime.get('observation_sites') == dict(references=2, matches=1),
                      query_hash=runtime.get('query_sha256') == sha(test_path),
                      unique_observed_queries=len(lookup) == len(observations) and set(lookup) <= set(sample_ids),
                      actual_scores_consumed=proposed.molecule_id.tolist() == list(sample_ids) and proposed.smiles.tolist() == raw_proposals and final.smiles.tolist() == accepted,
                      hit_count=runtime['original_report']['hits'] == sum(x[1] for x in expected),
                      promotion_count=runtime['original_report']['promoted'] == sum(x.split(';')[0] != y.split(';')[0] for x, y in zip(raw_proposals, control.smiles)),
                      original_control_bound=sha(root / 'submission_pre_apex_extlib.csv') == sha(root / 'submission_adduct_control.csv'))
    else:
        checks['fast_no_matching'] = (runtime.get('status') == 'fast_static_no_matching'
                                      and runtime.get('library_matching_performed') is False and final.equals(control))
    if not all(checks.values()):
        raise ValueError('Adduct matching observer rejected ' + repr(checks))
    result = dict(status='passed', branch=branch, recipe_sha256=recipe_sha256,
                  mode='hidden_full' if is_rerun else 'fast_static', checks=checks,
                  csv_sha256=sha(root / 'submission.csv'), control_sha256=sha(root / 'submission_adduct_control.csv'),
                  runtime_report_sha256=sha(root / 'adduct_overlay_runtime.json'),
                  reference_counts=runtime.get('reference_counts', {}), changed_top1=runtime.get('changed_top1', 0))
    write(root / 'adduct_overlay_audit.json', result)
    return result
