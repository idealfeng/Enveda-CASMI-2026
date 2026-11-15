"""Read-only revision2 source/route/actual-trace review. No model imports."""
from pathlib import Path
import ast
import base64
import hashlib
import json
import zlib
from bestval_independent_review import read, sha, src, assignment, literal

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'reports/optimization_20261112'
STAGE=ROOT/'submission/optimization_20261112/generation_expand/revision2'


def embedded(book):
    node=assignment(ast.parse(src(book['cells'][11])),'_guarded_source')
    text=zlib.decompress(base64.b64decode(ast.literal_eval(node.value.args[0].args[0]))).decode()
    tree=ast.parse(text)
    frozen=ast.literal_eval(assignment(tree,'FROZEN_B64').value)
    runner=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and
                any(isinstance(t,ast.Subscript) and getattr(t.value,'id',None)=='MODULES' and ast.literal_eval(t.slice)=='runner.py' for t in n.targets))
    return base64.b64decode(frozen),runner


def unpack(tree,name):
    value=assignment(tree,name).value
    decode=next(n for n in ast.walk(value) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='b64decode')
    return zlib.decompress(base64.b64decode(ast.literal_eval(decode.args[0])))


def main():
    base=read(ROOT/'submission/optimization_20261109/mass_guarded_extlib/notebook.ipynb')
    book=read(STAGE/'notebook.ipynb');recipe=read(STAGE/'recipe.json');spec=read(STAGE/'branch_spec.json');receipt=read(STAGE/'prepare_receipt.json')
    module=ROOT/'scripts/generation_runtime_patch_20261112.py'
    text=module.read_text(encoding='utf-8');mt=ast.parse(text)
    cfg=literal(assignment(mt,'CONFIG').value);pins=literal(assignment(mt,'SOURCE_PINS').value)
    initial=src(base['cells'][12]);setup=src(book['cells'][12])[len(initial):];tree=ast.parse(setup)
    module_data=unpack(tree,'_gen_raw');runner_data=unpack(tree,'_gen_runner_text')
    frozen,original=embedded(base);variant_frozen,variant_original=embedded(book)
    marker="        exec(compile(''.join(c['source']),f'pipeline_cell_{i}','exec'),scope)"
    expected_runner='from generation_runtime_patch_20261112 import after_cell, finish\n'+original
    expected_runner=expected_runner.replace(marker,marker+'\n        after_cell(scope,i,root)').replace('    export(scope,root)','    export(scope,root)\n    finish(scope,root)')
    frozen_book=json.loads(frozen)
    cell37=src(frozen_book['cells'][37]);cell39=src(frozen_book['cells'][39])
    actual=ROOT/'runs/generation_prod_canary_20261112_actual_revision2'
    route=ROOT/'runs/generation_prod_canary_20261112_route_revision2'
    av=read(actual/'verification.json');rv=read(route/'verification.json');runtime=read(actual/'generation_runtime.json')
    code=ROOT/'assets/kaggle/dmitriigluzdov/casmi26-attributed-v4g-reproduction-assets/v9/casmi26-v4b-models/code'
    actual_sources=dict(engine=code/'casmi/engine.py',derive=code/'casmi/derive.py',hooks_v1=code/'fe_v4/hooks_v1.py',v1engine=code/'fe_v4/v1engine.py')
    hooks=(code/'fe_v4/hooks_v1.py').read_text(encoding='utf-8')
    v1=(code/'fe_v4/v1engine.py').read_text(encoding='utf-8')
    rows=runtime['rows'];features=runtime['selected_ranker_features']
    final=src(book['cells'][-1]);aud=spec['required_runtime_audits'][-1]
    checks=dict(
        revision2_source_bound=sha(STAGE/'notebook.ipynb')==spec['notebook_sha256']==receipt['notebook_sha256']=='7ed40ac01c64448490cf9cfd85ad21210e34163e81affdb2e1a1dcbac7514753',
        recipe_bound=sha(STAGE/'recipe.json')==receipt['recipe_sha256'],
        metadata_bound=sha(STAGE/'kernel-metadata.json')==spec['metadata_sha256']==receipt['metadata_sha256'],
        original_other32_cells_exact=len(book['cells'])==34 and all(book['cells'][i]==c for i,c in enumerate(base['cells']) if i!=12),
        stage_machinery_prefix_exact=src(book['cells'][12]).startswith(initial),
        original_frozen_bytes_exact=variant_frozen==frozen and variant_original==original,
        original_runner_unmodified=hashlib.sha256(original.encode()).hexdigest()==recipe['original_runner_sha256'],
        exact_runner_hook_only=runner_data.decode()==expected_runner,
        runner_pin=hashlib.sha256(runner_data).hexdigest()==recipe['runner_sha256']==receipt['runner_sha256']=='153c85fb59025f3c2fa75cf9a64ffe7aa6cdb26b25113fee9fa46643c22f1182',
        exact_module_payload=module_data==module.read_bytes() and sha(module)==receipt['module_sha256']==recipe['module_sha256']=='32145802187bda9fe178048df49ec9ecfce6a0c7bab46c15550b5a479774eef9',
        exact_configuration=cfg==recipe['configuration']==dict(gen_n_analog=12,gen_max_total=300,gen_max_per_parent=60,max_steps=2,allow_isomerisation=False),
        actual_module_sources_pinned={k:sha(p) for k,p in actual_sources.items()}==pins==runtime['installed_source_pins'],
        actual_stage_router="Path(args[1]).name=='runner.py'" in setup and 'run_stage=_generation_run_stage' in setup and "args[1]=_gen_runner" in setup,
        actual_main_calls_router="run_stage([sys.executable, CODE / 'runner.py', FROZEN, FROZEN_SHA256, ROOT]" in initial,
        after_initialization_hook='if index == 37:' in text and 'install(scope, root)' in text and 'V = v1engine.V1FE(E,' in cell37 and 'def rank_score(X, names):' in cell37,
        original_query_loop_uses_wrapped_instances='V.run(spectra, target)' in cell39 and 'score = rank_score(np.concatenate([X, F], 1), list(FEATURES) + list(names))' in cell39,
        v1_instance_hook_order='hooks_v1.install(E1)' in v1 and 'hooks_v1.derive_rec = derive_rec' in text and 'E.generate = generate' in text and 'V.run = run' in text,
        actual_derive_override='prods = derive_rec(psmi, delta,' in hooks and "kwargs['allow_isomerisation'] = False" in text and "kwargs.get('max_steps') != 2" in text,
        actual_cfg_checked='setattr(E.cfg, name, CONFIG[name])' in text and "getattr(E.cfg, key) != CONFIG[key]" in text,
        projection_matches_frozen_ranker="Xs = np.ascontiguousarray(X[:, [pos[f] for f in RK_FEATS]], dtype=np.float32)" in cell37 and "matrix[:,selected_positions], dtype=np.float32" in text,
        raw_features_not_confused_with_ranker_width=all(r['n_features']==252 and r['ranker_feature_count']==160 for r in rows),
        actual_selected_features_160=len(features)==160 and len(set(features))==160 and all(len(r['selected_feature_positions'])==160 and len(set(r['selected_feature_positions']))==160 for r in rows),
        actual_feature_and_score_hashes=all(r['rank_called'] and len(r['features_sha256'])==len(r['selected_features_sha256'])==len(r['score_sha256'])==64 for r in rows),
        actual_rank_consumption_guard="matrix.shape != (row['n_candidates'], row['n_features'])" in text and "row['features_sha256']" in text and 'score = original_rank(X, names)' in text,
        actual12_parents_and_budget=all(r['parents_used']==12 and r['n_generated']<=300 for r in rows),
        dynamic_scope_order_guard="scope['te'].groupby('molecule_id', sort=False)" in text and "actual == expected" in text,
        hidden_ids_set_not_test_order="len(runtime['processed_ids'])==len(sample_ids) and set(runtime['processed_ids'])==set(sample_ids)" in text,
        output_ids_exact_sample_order="[r['molecule_id'] for r in final] == list(sample_ids)" in text,
        source_fail_closed="(ROOT/'submission.csv').unlink(missing_ok=True)" in setup and "(ROOT/'submission.csv').unlink(missing_ok=True)" in final,
        swallowed_derive_errors_fail="STATE['derive_errors'] += 1" in text and "raise RuntimeError('A swallowed derivation error was observed')" in text,
        before_postlayers_runtime_export='    export(scope,root)\n    finish(scope,root)' in runner_data.decode(),
        final_binds_original_ab="EXTERNAL_OVERLAY_AUDIT" in final and "base_audit.get('csv_sha256') == csv_pin" in text,
        final_binds_actual_runner="sha(root/'code/generation_runner.py') == runner_pin" in text and "launch['runner_sha256'] == runner_pin" in text,
        final_branch_recipe_contract=aud['name']=='generation_variant_audit.json' and aud['expected_fields']['recipe_sha256']==sha(STAGE/'recipe.json') and aud['expected_fields']['branch']=='generation_expand',
        actual_revision2_ready=receipt['status']=='prepared_actual_canary_passed',
        actual_canary_hashes=av['status']==rv['status']=='passed' and all(av['checks'].values()) and all(rv['checks'].values()) and av['module_sha256']==rv['module_sha256']==sha(module) and av['notebook_sha256']==rv['notebook_sha256']==sha(STAGE/'notebook.ipynb'),
        actual_runtime_checks=all(runtime['checks'].values()) and runtime['configuration']==cfg)
    for c in book['cells']:
        if c['cell_type']=='code':compile(src(c),'independent_generation_static','exec')
    checks['all_code_compiles']=True
    result=dict(status='passed' if all(checks.values()) else 'failed',checks=checks,checks_passed=sum(checks.values()),checks_total=len(checks),
                notebook_sha256=sha(STAGE/'notebook.ipynb'),module_sha256=sha(module),runner_sha256=recipe['runner_sha256'],
                reviewed_revision='revision2',read_only=True,no_gpu_or_model_load=True,no_cloud_writes=True,
                actual_canary_scope='Two production-interface queries through Engine/V1FE/ranker; not a full hidden end-to-end rerun or efficacy evaluation')
    # Historical revision2 checks missed Kaggle's p2s_code layout. Never let a
    # rerun overwrite the canonical recovery review with this stale approval.
    if (OUT/'generation_cloud_failure.json').exists():
        result['status']='superseded_cloud_layout_failure'
        result['scope_correction']='These checks used a local code fixture and did not cover the production p2s_code layout; use revision3 review.'
        destination=OUT/'generation_revision2_independent_review.json'
    else:
        destination=OUT/'generation_independent_review.json'
    destination.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=result['status'],passed=result['checks_passed'],total=result['checks_total'],failed=[k for k,v in checks.items() if not v])))
    if result['status']!='passed':raise SystemExit(1)


if __name__=='__main__':main()
