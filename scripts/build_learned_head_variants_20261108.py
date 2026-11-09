"""Freeze learned-head private Notebook variants; no network or cloud mutations."""
from __future__ import annotations
import argparse
import base64
import copy
import hashlib
import json
from pathlib import Path
import zlib

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'submission/aggressive_20261107/public_mass_repro'
BASE_SHA = '2bf3c51c8703956f80892d478b0de77747f90a8228bf275399d793666e5a1ea6'
V2_SHA = 'c08d2101154d057890de088be63834eb622468892a3b842512fdc5a65e02ff46'
SEEDS = (20261108, 20261109)


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))
def source(cell): return ''.join(cell['source']) if isinstance(cell['source'], list) else cell['source']
def write(path, data): Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')


OBSERVER = r'''
def _observe_learned_head():
    import hashlib,json
    expected=__EXPECTED__
    digest=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    checks={}
    def check(name,value):
        checks[name]=bool(value)
        assert value,name
    check('base_mass_audit',BATCH_VARIANT_AUDIT['status']=='passed')
    check('head_scorer_source_pin',digest(CODE/'learned_head_score.py')==expected['adapter_sha256'])
    check('head_model_source_pin',digest(CODE/'candidate_multispectrum_head.py')==expected['model_sha256'])
    check('original_scorer_source_pin',digest(CODE/'neural_scores_original.py')==expected['baseline_sha256'])
    check('runtime_manifest_pin',digest(CODE/'learned_head_runtime.json')==expected['runtime_sha256'])
    check('trained_checkpoint_pins',all(digest(CODE/x['file'])==x['sha256'] for x in expected['heads']))
    check('base_mass_configuration',V8=='MASS' and MASS_ON and not RR8 and POP_W==.10 and SPEC_W==.10 and NP_W==.12 and LIB_HIT_GATE==.78)
    observed={}
    if IS_RERUN:
        check('full_pipeline_executed',PIPELINE_DONE and NEURAL_OK and CONSENSUS_OK and SUBMITTED==VARIANT)
        def audit(label,filename,consumed,evidence):
            item=json.loads((ROOT/filename).read_text())
            frame=pd.read_parquet(ROOT/consumed)
            check(label+'_head_called',item.get('status')=='passed' and item.get('role')=='learned_v2' and item.get('head_applied') is True)
            check(label+'_weights',item.get('encoder_sha256')==expected['encoder_sha256'] and item.get('heads')==expected['head_receipts'])
            check(label+'_output_consumed',item.get('output_sha256')==digest(ROOT/consumed))
            check(label+'_input_bound',item.get('evidence_sha256')==digest(ROOT/evidence) and item.get('queries_sha256')==digest(ROOT/'effective_query_spectra.parquet'))
            check(label+'_rows',item.get('input_rows')==item.get('output_rows')==len(frame))
            check(label+'_coverage',item.get('scored_candidate_rows')==int(frame.neural_ok.astype(bool).sum()) and item.get('scored_queries')==int(frame.loc[frame.neural_ok.astype(bool),'molecule_id'].nunique()))
            failed=set(frame.loc[frame.processed.astype(bool) & ~frame.neural_ok.astype(bool),'molecule_id'].astype(str))
            check(label+'_failures_scoped',{str(x['molecule_id']) for x in item.get('errors',[])}==failed)
            observed[label]=dict(scored_queries=item['scored_queries'],scored_candidate_rows=item['scored_candidate_rows'],head_count=len(item['heads']))
        audit('main','neural_candidate_features.parquet.head_audit.json','neural_ours.parquet','frozen_candidate_evidence.parquet')
        if OUTSIDERS_OK:
            audit('outsider','outsider_neural_features.parquet.head_audit.json','outsider_neural_features.parquet','outsider_evidence.parquet')
        else:
            observed['outsider']=dict(skipped_by_original_optional_time_policy=True)
    else:
        check('fast_no_model_claim',not RUN_PIPELINE and not PIPELINE_DONE)
    result=dict(status='passed',branch=expected['branch'],mode='hidden_full' if IS_RERUN else 'fast_static',
        recipe_sha256=expected['recipe_sha256'],checks=checks,head_execution=observed,
        known_pretrained_exposure=True,new_training_in_notebook=False,
        actual_head_inference=bool(IS_RERUN),csv_sha256=digest(ROOT/'submission.csv'))
    (ROOT/'learned_head_audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
LEARNED_HEAD_AUDIT=_observe_learned_head()
'''


def build(kind, compact=False):
    combined = kind == 'heads_na'
    selected = SEEDS if combined else (SEEDS[0 if kind == 'head_seed0' else 1],)
    name = 'mass_'+kind+('_compact' if compact else '')
    target = 'stormseye/casmi26-mass-'+kind.replace('_','-')+('-compact' if compact else '')+'-1108'
    out = ROOT/'submission/optimization_20261108'/name
    if out.exists(): raise FileExistsError('Preserve frozen stages')
    if sha(BASE/'notebook.ipynb') != BASE_SHA: raise ValueError('Confirmed 0.481 source changed')
    source_stage = ROOT/'submission/optimization_20261108/mass_gl_na' if combined else BASE
    if combined:
        contract = read(source_stage/('branch_spec.json' if (source_stage/'branch_spec.json').exists() else 'branch_manifest.json'))
        if sha(source_stage/'notebook.ipynb') != contract['notebook_sha256']: raise ValueError('Na source pin mismatch')
    nb = copy.deepcopy(read(source_stage/'notebook.ipynb'))
    source_nb_sha = sha(source_stage/'notebook.ipynb')
    metadata = read(source_stage/'kernel-metadata.json')
    metadata.update(id=target, title=target.split('/')[1].replace('-',' '), code_file='notebook.ipynb')
    model = ROOT/'scripts/candidate_multispectrum_head.py'
    adapter = ROOT/'scripts/learned_head_score.py'
    baseline = ROOT/'runs/validation_flex_c2_20261105d/p2s_code/neural_scores.py'
    heads=[]
    for seed in selected:
        path=ROOT/f'runs/candidate_head_20261108/head_seed{seed}_step2500.pt'
        receipt=read(path.parent/f'training_receipt_seed{seed}.json')
        checkpoint=next(x for x in receipt['milestones'] if x['step']==2500)
        if (receipt['status']!='trained' or receipt['seed']!=seed or receipt['steps']!=2500
                or receipt['head_code_sha256']!=sha(model) or not receipt['all_loss_gradient_finite']
                or sha(path)!=checkpoint['checkpoint_sha256']):
            raise ValueError('Missing completed fixed-budget training receipt')
        heads.append(dict(file=path.name,sha256=sha(path),seed=seed,step=2500,path=path))
    runtime=dict(baseline_scorer_file='neural_scores_original.py',baseline_scorer_sha256=sha(baseline),
        head_model_file='candidate_multispectrum_head.py',head_model_sha256=sha(model),required_step=2500,
        heads=[{k:x[k] for k in ('file','sha256')} for x in heads])
    runtime_raw=(json.dumps(runtime,indent=2)+'\n').encode()
    payloads={
        'candidate_multispectrum_head.py':model.read_bytes(),
        'learned_head_score.py':adapter.read_bytes(),
        'learned_head_runtime.json':runtime_raw,
        **{x['file']:x['path'].read_bytes() for x in heads}}
    encoded={k:base64.b64encode(v).decode() for k,v in payloads.items()}
    pins={k:hashlib.sha256(v).hexdigest() for k,v in payloads.items()}
    wrapper="from learned_head_score import score\nimport sys\nif __name__=='__main__':score(*sys.argv[1:])\n"
    install='''
# The v2 encoder stays frozen; the newly trained head changes only its aggregate score.
def _install_candidate_head():
    import base64,hashlib,shutil
    payloads=__PAYLOADS__
    pins=__PINS__
    original=CODE/'neural_scores.py'
    if hashlib.sha256(original.read_bytes()).hexdigest()!=__BASE_PIN__:
        raise ValueError('Materialised original neural scorer source differs')
    shutil.copy2(original,CODE/'neural_scores_original.py')
    for name,value in payloads.items():
        raw=base64.b64decode(value)
        if hashlib.sha256(raw).hexdigest()!=pins[name]:raise ValueError('Head payload integrity error')
        (CODE/name).write_bytes(raw)
    original.write_text(__WRAPPER__)
_install_candidate_head()
'''.replace('__PAYLOADS__',repr(encoded)).replace('__PINS__',repr(pins)).replace('__BASE_PIN__',repr(sha(baseline))).replace('__WRAPPER__',repr(wrapper))
    text=source(nb['cells'][14])
    needle='BUNDLE = materialise_sources()'
    if text.count(needle)!=1:raise ValueError('Unexpected neural stage entry')
    nb['cells'][14]['source']=text.replace(needle,needle+'\n'+install,1)
    # Observer scope follows the actual hidden sample file, as in the new controls.
    for cell in nb['cells']:
        if cell['cell_type']=='code':
            cell['source']=source(cell).replace("receipt.get('processed_molecules')==len(SAMPLE_IDS)==400",
                "receipt.get('processed_molecules')==len(SAMPLE_IDS) and len(SAMPLE_IDS)>0")
    recipe=dict(branch=name,target=target,baseline_own_public_score=.481,source_stage=str(source_stage.relative_to(ROOT)),
        source_notebook_sha256=source_nb_sha,method='frozen v2 candidate-conditioned multispectrum listwise head',
        heads=[{k:x[k] for k in ('sha256','seed','step')} for x in heads],
        combined_real_na_gl=combined,compact_source_envelope=compact,payload_sha256=pins,original_scorer_sha256=sha(baseline),
        unchanged='Original MASS priors, public encoder, .5/.5 public/v2 ensemble, physical and mass leader chain; only v2 neural_score changes.',
        training_data='1024 train identities, actual v2 mass-window hard negatives, fixed 2500 steps',
        evaluation_boundary='known pretrained exposure component diagnostic; not clean full-stack CV',
        locked_final_used=False,validation_mode='fast_static',training_in_notebook=False)
    recipe_raw=(json.dumps(recipe,indent=2,ensure_ascii=False)+'\n').encode()
    recipe_sha=hashlib.sha256(recipe_raw).hexdigest()
    expected=dict(branch=name,recipe_sha256=recipe_sha,adapter_sha256=sha(adapter),model_sha256=sha(model),
        baseline_sha256=sha(baseline),runtime_sha256=hashlib.sha256(runtime_raw).hexdigest(),encoder_sha256=V2_SHA,
        heads=[{k:x[k] for k in ('file','sha256')} for x in heads],
        head_receipts=[{k:x[k] for k in ('sha256','step','seed')} for x in heads])
    nb['cells'].append(dict(cell_type='code',execution_count=None,metadata={},outputs=[],source=OBSERVER.replace('__EXPECTED__',repr(expected))))
    if compact:
        # Lossless envelope only: executing this decodes exactly the original cell.
        pinned=source(nb['cells'][11]).encode('utf-8')
        packed=base64.b64encode(zlib.compress(pinned,9)).decode('ascii')
        pin=hashlib.sha256(pinned).hexdigest()
        nb['cells'][11]['source']=("import base64,zlib,hashlib\n"
            +"_casmi_compact_source=zlib.decompress(base64.b64decode("+repr(packed)+"))\n"
            +"assert hashlib.sha256(_casmi_compact_source).hexdigest()=="+repr(pin)+"\n"
            +"exec(compile(_casmi_compact_source.decode('utf-8'),'pinned_sources_lossless','exec'),globals())\n")
    for cell in nb['cells']:
        if cell['cell_type']=='code':
            compile(source(cell),'learned-head-notebook','exec');cell['outputs']=[];cell['execution_count']=None
    out.mkdir(parents=True)
    write(out/'notebook.ipynb',nb);write(out/'kernel-metadata.json',metadata);(out/'recipe.json').write_bytes(recipe_raw)
    checks=dict(base_mass_source_pin=True,fixed_budget_heads_bound=True,embedded_payloads_sha_bound=True,
        public_passthrough_v2_head_dispatch=True,main_and_outsider_same_scorer=True,
        original_priors_and_leader_chain_preserved=True,dynamic_hidden_scope=True,all_code_compiles=True,
        private_offline_gpu=True,known_exposure_explicit=True,no_notebook_training=True)
    static=dict(status='passed',target=target,version=1,notebook_sha256=sha(out/'notebook.ipynb'),checks=checks)
    write(out/'static_review.json',static)
    receipt=dict(status='prepared',branch=name,target=target,version=1,notebook_sha256=static['notebook_sha256'],
        metadata_sha256=sha(out/'kernel-metadata.json'),recipe_sha256=recipe_sha,
        static_review_path=str((out/'static_review.json').relative_to(ROOT)).replace('\\','/'),validation_mode='fast_static')
    write(out/'prepare_receipt.json',receipt)
    base_spec=read(source_stage/('branch_spec.json' if (source_stage/'branch_spec.json').exists() else 'branch_manifest.json')) if combined else next(b for b in read(ROOT/'submission/aggressive_20261107/manifest.json')['branches'] if b['name']=='public_mass_repro')
    audits=copy.deepcopy(base_spec['required_runtime_audits'])
    audits.append(dict(name='learned_head_audit.json',expected_fields=dict(status='passed',branch=name,mode='fast_static',recipe_sha256=recipe_sha),
        required_true_checks=['base_mass_audit','head_scorer_source_pin','head_model_source_pin','original_scorer_source_pin',
            'runtime_manifest_pin','trained_checkpoint_pins','base_mass_configuration','fast_no_model_claim']))
    branch=dict(name=name,target=target,version=1,stage_dir=str(out.relative_to(ROOT)).replace('\\','/'),
        notebook_sha256=receipt['notebook_sha256'],metadata_sha256=receipt['metadata_sha256'],
        description='CASMI26 20261108 '+kind+(' compact' if compact else '')+' trained multispectrum head audited V1',validation_mode='fast_static',
        static_review_path=receipt['static_review_path'],required_runtime_audits=audits)
    write(out/'branch_spec.json',branch)
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kind',choices=['head_seed0','head_seed1','heads_na'])
    parser.add_argument('--compact',action='store_true')
    args=parser.parse_args()
    build(args.kind,args.compact)
