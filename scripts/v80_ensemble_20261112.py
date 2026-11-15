"""Pinned independent best-validation scorer mixing; no training or truth access."""
from pathlib import Path
import hashlib
import json
import shutil

PUB_PINS = {
    'model.py': '2547418857386d1c2513fd1ab6c70961e6a96e73d9d495bbfe3052197e69dc39',
    'features.py': 'a97ad9b3ab3711517864d56e497e1672cb29bb05683c72b52db9f9b0a17b1455',
    'config.json': '563fb2a2a81ca48ea094f9ab78c157a48a6e9a5503e85e6ce8f0fb3615c1cc03',
    'final_model.pt': '44436b2daec64373e66f9120dd2389c24fc83dd9430ebeeac18e3cb49dcb9642'}
V2_SHA = 'c08d2101154d057890de088be63834eb622468892a3b842512fdc5a65e02ff46'
SPECS = {
    'popwenman_best': dict(marker='casmi26-scorer-train-v80', subdirectory='casmi_spectrum_model_ours_v80',
        filename='best_validation_model.pt', bytes=11873492,
        sha256='f7e2383fe5fc0cc85e7333d308bc7201144574f2eef6b59000570d171e0758a7', weights=[.5,.25,.25]),
    'saner_best': dict(marker='casmi-spectrum-model-v1', subdirectory='casmi_spectrum_model_v1',
        filename='best_validation_model.pt', bytes=11873492,
        sha256='969d13443fcf168eae1e00e56a8e0ae87dcb16f337cb6dbac959e7cd218f089c', weights=[.375,.375,.25])}
RUNTIME = 'bestval_ensemble_runtime.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def config(kind):
    if kind not in SPECS:
        raise ValueError('Unknown independent checkpoint')
    result = dict(kind=kind, checkpoint=SPECS[kind], public_pins=PUB_PINS, v2_sha256=V2_SHA,
                  outsider_scorer='original_v2', late_head='original_frozen_v2_two_heads')
    if len({PUB_PINS['final_model.pt'], V2_SHA, result['checkpoint']['sha256']}) != 3:
        raise ValueError('Duplicate checkpoint does not add model information')
    return result


def select(input_root, filename, marker, subdirectory=None):
    paths = [p for p in Path(input_root).rglob(filename) if marker in p.parts
             and (subdirectory is None or p.parent.name == subdirectory)]
    if len(paths) != 1:
        raise ValueError('Explicit checkpoint source must be unique: ' + marker)
    return paths[0]


def verify_bundles(runtime):
    got = {key:{name:sha(Path(path)/name) for name in PUB_PINS} for key,path in runtime['bundles'].items()}
    pub = dict(PUB_PINS)
    v2 = dict(PUB_PINS, **{'final_model.pt':V2_SHA})
    extra = dict(PUB_PINS, **{'final_model.pt':runtime['configuration']['checkpoint']['sha256']})
    if got != dict(public=pub, v2=v2, extra=extra):
        raise ValueError('Installed scorer bundle differs from explicit pins')
    return got


def prepare(root, input_root, public_bundle, kind, branch, recipe_sha256, module_sha256):
    root = Path(root)
    cfg = config(kind)
    if sha(__file__) != module_sha256:
        raise ValueError('Bestval mixing module changed')
    if {name:sha(Path(public_bundle)/name) for name in PUB_PINS} != PUB_PINS:
        raise ValueError('Original public bundle differs')
    v2 = select(input_root, 'final_model.pt', 'casmi26-scorer-v2-model')
    spec = cfg['checkpoint']
    extra = select(input_root, spec['filename'], spec['marker'], spec['subdirectory'])
    if sha(v2) != V2_SHA or extra.stat().st_size != spec['bytes'] or sha(extra) != spec['sha256']:
        raise ValueError('Explicit input checkpoint pin differs')
    bundles = dict(public=str(Path(public_bundle)), v2=str(root/'ours_bundle'), extra=str(root/'independent_bestval_bundle'))
    for key, source in [('v2',v2), ('extra',extra)]:
        dest = Path(bundles[key]);dest.mkdir(exist_ok=True)
        for name in ('model.py','features.py','config.json'):
            shutil.copy2(Path(public_bundle)/name,dest/name)
        shutil.copy2(source,dest/'final_model.pt')
    runtime = dict(status='prepared', branch=branch, recipe_sha256=recipe_sha256, module_sha256=module_sha256,
                   configuration=cfg, bundles=bundles, input_checkpoints=dict(v2=str(v2),extra=str(extra)),
                   no_new_training=True, outsider_scorer_unchanged=True, late_head_unchanged=True)
    runtime['installed_bundle_pins'] = verify_bundles(runtime)
    write(root/RUNTIME,runtime)
    return bundles


def z(series):
    group = series.groupby(level=0)
    return (series-group.transform('mean'))/group.transform(lambda v:v.std(ddof=0)).clip(lower=1e-6)


def frames(root):
    import pandas as pd
    result = {}
    for key,name in [('public','neural_public.parquet'),('v2','neural_ours.parquet'),('extra','neural_bestval.parquet')]:
        frame = pd.read_parquet(Path(root)/name).set_index(['molecule_id','smiles'])
        if not frame.index.is_unique:
            raise ValueError('Duplicate neural candidate key')
        result[key] = frame
    a = result['public']
    for key in ('v2','extra'):
        if set(a.index) != set(result[key].index):
            raise ValueError('Independent scorer candidate coverage differs')
        result[key] = result[key].reindex(a.index)
        if not a.neural_ok.astype(bool).equals(result[key].neural_ok.astype(bool)):
            raise ValueError('Independent scorer usable coverage differs')
    return result


def expected_mix(root, weights):
    import numpy as np
    fs = frames(root)
    result = fs['public'].copy()
    result['neural_score'] = sum(w*z(fs[k].neural_score.fillna(0.0)) for k,w in zip(('public','v2','extra'),weights))
    for col in ('neural_cos','neural_fp','neural_std'):
        result[col] = sum(w*fs[k][col].fillna(0.0) for k,w in zip(('public','v2','extra'),weights))
    result['neural_ok'] = fs['public'].neural_ok.astype(bool) & fs['v2'].neural_ok.astype(bool) & fs['extra'].neural_ok.astype(bool)
    if not np.isfinite(result.loc[result.neural_ok,'neural_score']).all():
        raise ValueError('Nonfinite usable mixed scores')
    return result


def mix(root, kind):
    root = Path(root)
    runtime = read(root/RUNTIME)
    if runtime['configuration'] != config(kind):
        raise ValueError('Mix configuration differs from fixed source recipe')
    verify_bundles(runtime)
    if runtime['status'] != 'prepared':
        raise ValueError('Mixing cannot run twice or after altered phase')
    result = expected_mix(root,runtime['configuration']['checkpoint']['weights'])
    output = root/'neural_candidate_features.parquet'
    result.reset_index().to_parquet(output,index=False)
    runtime.update(status='mixed',score_rows=len(result),score_queries=result.index.get_level_values(0).nunique(),
        source_hashes={name:sha(root/name) for name in ('neural_public.parquet','neural_ours.parquet','neural_bestval.parquet')},
        output_sha256=sha(output))
    write(root/RUNTIME,runtime)
    return runtime


def audit_scores(root, is_rerun, kind):
    import numpy as np
    import pandas as pd
    root=Path(root);runtime=read(root/RUNTIME)
    if runtime['configuration'] != config(kind):
        raise ValueError('Observed configuration differs from fixed kind')
    checks=dict(configuration_exact=True, installed_models_exact=verify_bundles(runtime)==runtime['installed_bundle_pins'],
        three_distinct_checkpoints=len({v['final_model.pt'] for v in runtime['installed_bundle_pins'].values()})==3,
        outsider_v2_unchanged=runtime['configuration']['outsider_scorer']=='original_v2',
        late_head_unchanged=runtime['configuration']['late_head']=='original_frozen_v2_two_heads')
    if is_rerun:
        expected=expected_mix(root,runtime['configuration']['checkpoint']['weights'])
        actual=pd.read_parquet(root/'neural_candidate_features.parquet').set_index(['molecule_id','smiles'])
        checks['mix_executed']=runtime['status']=='mixed'
        checks['candidate_keys_exact']=actual.index.is_unique and list(actual.index)==list(expected.index)
        checks['actual_input_hashes']=runtime['source_hashes']=={n:sha(root/n) for n in runtime['source_hashes']}
        checks['actual_output_hash']=runtime['output_sha256']==sha(root/'neural_candidate_features.parquet')
        checks['exact_score_consumption']=all(np.array_equal(expected[c].to_numpy(),actual[c].to_numpy(),equal_nan=True)
            for c in ('neural_score','neural_cos','neural_fp','neural_std'))
        checks['coverage_exact']=expected.neural_ok.equals(actual.neural_ok)
    else:
        checks['fast_no_model']=runtime['status']=='prepared' and 'output_sha256' not in runtime
    if not all(v is True for v in checks.values()):
        raise ValueError('Independent bestval score audit failed: '+','.join(k for k,v in checks.items() if not v))
    return checks


def audit(root, is_rerun, sample_ids, external_audit, branch, recipe_sha256, module_sha256, kind):
    import pandas as pd
    root=Path(root);runtime=read(root/RUNTIME)
    checks=audit_scores(root,is_rerun,kind)
    checks.update(module_pin=sha(__file__)==module_sha256==runtime['module_sha256'],
        branch_recipe_bound=runtime['branch']==branch and runtime['recipe_sha256']==recipe_sha256,
        original_ab_passed=external_audit.get('status')=='passed',
        final_ab_output_bound=sha(root/'submission.csv')==external_audit.get('csv_sha256'))
    frame=pd.read_csv(root/'submission.csv',dtype=str,keep_default_na=False)
    checks['exact_ids_schema']=list(frame.columns)==['molecule_id','smiles'] and frame.molecule_id.tolist()==list(sample_ids) and frame.molecule_id.is_unique
    if not all(v is True for v in checks.values()):
        raise ValueError('Bestval final observer failed')
    result=dict(status='passed',branch=branch,recipe_sha256=recipe_sha256,mode='hidden_full' if is_rerun else 'fast_static',
                checks=checks,csv_sha256=sha(root/'submission.csv'),module_sha256=module_sha256,
                runtime_report_sha256=sha(root/RUNTIME),configuration=runtime['configuration'],no_gain_claim=True)
    write(root/'bestval_ensemble_audit.json',result)
    return result
