"""Production-only generation budget variant; observers consume actual Engine/V1FE/ranker calls."""
from pathlib import Path
import csv
import hashlib
import json
import time

CONFIG = dict(gen_n_analog=6, gen_max_total=300, gen_max_per_parent=60,
              max_steps=2, allow_isomerisation=True)
# Candidate r4: exact runtime source after the frozen cell27 determinism policy.
# Reject the original unpatched engine; do not broaden the allowed source set.
SOURCE_PINS = {
    'engine': 'e4943fb26a8141f47ea95e744910c2d0f4746e36e72ef43e3263e7f327cfc0b5',
    'derive': '7c1e8c3afb4c17a3ae58fbc6c36fd4cfc552da97b9129c9b46cca3cdc6ee4892',
    'hooks_v1': 'd0cb1e37566a54bbb3082ccd29579ac47fc2526c5d64ef073dc0e628ee5657e8',
    'v1engine': '9074546910ba850a98bb95afe531669c62a26c15ab8b6bf9d6b6020c77ea0e8a',
}
STATE = None


def sha(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def install(scope, root):
    global STATE
    import numpy as np
    from casmi import engine, derive
    import hooks_v1, v1engine
    if STATE is not None:
        raise RuntimeError('Generation patch may only install once per pipeline process')
    modules = dict(engine=engine, derive=derive, hooks_v1=hooks_v1, v1engine=v1engine)
    actual = {k: sha(v.__file__) for k, v in modules.items()}
    if actual != SOURCE_PINS:
        raise ValueError('Actual generation source differs from frozen recipe')
    E, V = scope['E'], scope['V']
    if V.E is not E or not E.cfg.generate:
        raise ValueError('Expected actual production E006 Engine and V1FE')
    for name in ('gen_n_analog', 'gen_max_total', 'gen_max_per_parent'):
        setattr(E.cfg, name, CONFIG[name])
    ranker_features = list(scope['RK_FEATS'])
    if len(ranker_features) != 160 or len(set(ranker_features)) != 160:
        raise ValueError('Actual production ranker must select 160 distinct features')
    STATE = dict(root=str(root), installed_source_pins=actual, configuration=CONFIG.copy(),
                 selected_ranker_features=ranker_features,
                 rows=[], derive_errors=0, current=None, installed_at_unix=time.time())
    original_derive = hooks_v1.derive_rec
    original_generate = E.generate
    original_run = V.run
    original_rank = scope['rank_score']

    def derive_rec(smiles, delta, **kwargs):
        if kwargs.get('max_steps') != CONFIG['max_steps'] or kwargs.get('max_per_analog') != CONFIG['gen_max_per_parent']:
            raise ValueError('Original generation call changed')
        kwargs['allow_isomerisation'] = CONFIG['allow_isomerisation']
        active = STATE['current']
        if active is None:
            raise ValueError('Derivation called outside observed query')
        started = time.monotonic()
        try:
            result = original_derive(smiles, delta, **kwargs)
        except Exception:
            STATE['derive_errors'] += 1
            raise
        active['parents_used'] += 1
        active['parent_calls'].append(dict(rank=active['parents_used'], products=len(result),
                                           seconds=round(time.monotonic()-started, 6)))
        return result

    def generate(analogs, target, exclude_keys):
        active = STATE['current']
        if active is None:
            raise ValueError('Generate called outside observed V1FE.run')
        for key in ('gen_n_analog', 'gen_max_total', 'gen_max_per_parent'):
            if getattr(E.cfg, key) != CONFIG[key]:
                raise ValueError('Active engine configuration changed')
        active['eligible_parents'] = len([a for a in analogs if a[1] >= E.cfg.gen_min_sim][:CONFIG['gen_n_analog']])
        t = time.monotonic()
        result = original_generate(analogs, target, exclude_keys)
        active['generation_seconds'] = round(time.monotonic()-t, 6)
        active['generated_smiles'] = [g['smiles'] for g in result]
        active['generated_keys'] = [g['key'] for g in result]
        active['generated_parents'] = [int(g['parent']) for g in result]
        active['n_generated'] = len(result)
        active['hit_total_cap'] = len(result) == CONFIG['gen_max_total']
        if STATE['derive_errors']:
            raise RuntimeError('A swallowed derivation error was observed')
        return result

    def run(*args, **kwargs):
        mid = str(scope.get('mid', ''))
        if not mid:
            raise ValueError('Actual frozen molecule_id scope is unavailable')
        row = dict(molecule_id=mid, parents_used=0, eligible_parents=0, parent_calls=[],
                   generated_smiles=[], generated_keys=[], generated_parents=[], n_generated=0,
                   generation_seconds=0., hit_total_cap=False, rank_called=False)
        STATE['current'] = row
        t = time.monotonic()
        try:
            result = original_run(*args, **kwargs)
            C, X, F, names, info = result[:5]
            row.update(n_candidates=len(C.pid), n_features=int(X.shape[1]+F.shape[1]),
                       observed_generated=int(np.asarray(C.is_gen).sum()),
                       candidate_smiles=list(C.smiles), run_seconds=round(time.monotonic()-t, 6))
            if len(C.pid):
                if row['n_features'] < 160 or row['observed_generated'] != row['n_generated']:
                    raise ValueError('Generated candidates did not pass actual 160-feature extractor')
                all_names = list(engine.FEATURES) + list(names)
                positions = {n:i for i,n in enumerate(all_names)}
                row['selected_feature_positions'] = [positions[n] for n in ranker_features]
                matrix = np.ascontiguousarray(np.concatenate([X, F], 1))
                row['features_sha256'] = hashlib.sha256(matrix.tobytes()).hexdigest()
                selected = np.ascontiguousarray(matrix[:,row['selected_feature_positions']], dtype=np.float32)
                row['selected_features_sha256'] = hashlib.sha256(selected.tobytes()).hexdigest()
            STATE['rows'].append(row)
            return result
        except BaseException:
            row['runtime_error'] = True
            STATE['rows'].append(row)
            raise

    def rank_score(X, names):
        row = STATE['current']
        if row is None:
            raise ValueError('Ranker called without observed candidate construction')
        matrix = np.ascontiguousarray(X)
        if matrix.shape != (row['n_candidates'], row['n_features']) or hashlib.sha256(matrix.tobytes()).hexdigest() != row['features_sha256']:
            raise ValueError('Actual ranker did not consume extracted generation features')
        positions = {n:i for i,n in enumerate(names)}
        selected_positions = [positions[n] for n in ranker_features]
        selected = np.ascontiguousarray(matrix[:,selected_positions], dtype=np.float32)
        if selected.shape[1] != 160 or selected_positions != row['selected_feature_positions'] or hashlib.sha256(selected.tobytes()).hexdigest() != row['selected_features_sha256']:
            raise ValueError('Actual production 160-column ranker projection changed')
        score = original_rank(X, names)
        if len(score) != row['n_candidates'] or not np.isfinite(score).all():
            raise ValueError('Invalid actual ranker outputs')
        row['rank_called'] = True
        row['ranker_feature_count'] = 160
        row['score_sha256'] = hashlib.sha256(np.ascontiguousarray(score).tobytes()).hexdigest()
        order = np.argsort(-score, kind='stable')[:25]
        generated = set(row['generated_smiles'])
        row['engine_top25_generated'] = sum(row['candidate_smiles'][int(i)] in generated for i in order)
        return score

    hooks_v1.derive_rec = derive_rec
    E.generate = generate
    V.run = run
    scope['rank_score'] = rank_score
    STATE['hooks_installed'] = True


def after_cell(scope, index, root):
    if index == 37:
        install(scope, root)


def finish(scope, root):
    root = Path(root)
    if STATE is None:
        raise ValueError('Production pipeline did not install the generation hook')
    import numpy as np
    rows = STATE['rows']
    expected = [str(mid) for mid, sub in scope['te'].groupby('molecule_id', sort=False)
                if np.isfinite(sub.nm.values).any()]
    actual = [r['molecule_id'] for r in rows]
    checks = dict(actual_query_order=actual == expected, unique_actual_queries=len(set(actual)) == len(actual),
                  actual_configuration=STATE['configuration'] == CONFIG,
                  actual_source_pins=STATE['installed_source_pins'] == SOURCE_PINS,
                  no_swallowed_derivation_errors=STATE['derive_errors'] == 0,
                  actual_features_and_rank=all(not r.get('runtime_error') and (r['n_candidates'] == 0 or
                      (r['n_features'] >= 160 and r['rank_called'] and r['ranker_feature_count'] == 160)) for r in rows),
                  actual_parent_bound=all(r['parents_used'] <= CONFIG['gen_n_analog'] and r['parents_used'] <= r['eligible_parents'] for r in rows),
                  actual_product_bound=all(r['n_generated'] <= CONFIG['gen_max_total'] for r in rows))
    if not all(checks.values()):
        raise ValueError('Generation production observer failed: ' + ','.join(k for k,v in checks.items() if not v))
    # Keep the trace bounded by the generation cap; discard full nongenerated candidate lists.
    for row in rows:
        row.pop('candidate_smiles', None)
    STATE['checks'] = checks
    STATE['processed_ids'] = expected
    STATE['baseline_csv_sha256'] = sha(root/'submission.csv')
    STATE['mode'] = 'hidden_full' if scope['IS_RERUN'] else 'real_canary'
    save(root/'generation_runtime.json', STATE)


def audit(root, base_audit, is_rerun, sample_ids, branch, recipe_sha256, module_pin, runner_pin):
    root = Path(root)
    csv_pin = sha(root/'submission.csv')
    module_path = Path(__file__).resolve()
    runner_path = module_path.parent/'generation_runner.py'
    checks = dict(original_ab_audit=base_audit.get('status') == 'passed',
                  original_ab_output_bound=base_audit.get('csv_sha256') == csv_pin,
                  installed_module_pin=sha(module_path) == module_pin)
    report = dict(status='passed', branch=branch, recipe_sha256=recipe_sha256,
                  mode='hidden_full' if is_rerun else 'fast_static', checks=checks,
                  module_sha256=module_pin, runner_sha256=runner_pin, configuration=CONFIG,
                  csv_sha256=csv_pin)
    if is_rerun:
        runtime = json.loads((root/'generation_runtime.json').read_text())
        launch = json.loads((root/'generation_launch.json').read_text())
        with (root/'submission.csv').open() as handle:
            final = list(csv.DictReader(handle))
        by_mid = {row['molecule_id']: row for row in runtime['rows']}
        generated_final = sum(len(set(row['smiles'].split(';')) & set(by_mid.get(row['molecule_id'], {}).get('generated_smiles', []))) for row in final)
        checks.update(runtime_checks=bool(runtime['checks']) and all(runtime['checks'].values()),
                      actual_runtime_config=runtime['configuration'] == CONFIG,
                      actual_runner_launched=launch['runner_sha256'] == runner_pin and launch['module_sha256'] == module_pin,
                      actual_runner_file=sha(runner_path) == runner_pin,
                      actual_runner_path=Path(launch['actual_runner']).resolve() == runner_path.resolve(),
                      complete_hidden_ids=len(runtime['processed_ids'])==len(sample_ids) and set(runtime['processed_ids'])==set(sample_ids),
                      exact_csv_ids=[r['molecule_id'] for r in final] == list(sample_ids))
        report.update(runtime_report_sha256=sha(root/'generation_runtime.json'),
                      queries=len(runtime['rows']), n_generated=sum(r['n_generated'] for r in runtime['rows']),
                      parent7_12_calls=sum(max(0,r['parents_used']-6) for r in runtime['rows']),
                      touched_total_cap=sum(r['hit_total_cap'] for r in runtime['rows']),
                      generated_raw_smiles_in_final25=generated_final,
                      identity_count_note='Exact raw-SMILES intersection is a conservative count, not efficacy or truth recall')
    else:
        checks['fast_no_generation'] = not (root/'generation_runtime.json').exists() and not (root/'generation_launch.json').exists()
    if not all(checks.values()):
        (root/'submission.csv').unlink(missing_ok=True)
        raise ValueError('Generation final audit failed: ' + ','.join(k for k,v in checks.items() if not v))
    save(root/'generation_variant_audit.json', report)
    return report
