"""Independent static and synthetic observer review, no model, labels, or cloud calls."""
from pathlib import Path
import ast, hashlib, importlib.util, json, tempfile
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
STAGE=ROOT/'submission/aggressive_20261107/public_mass_repro'
SOURCE=ROOT/'third_party/public_scan_popwenman__casmi26-0482-gold-apex-v22_20261107/source.ipynb'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def source(cell):return ''.join(cell['source']) if isinstance(cell['source'],list) else cell['source']

def main():
    spec=importlib.util.spec_from_file_location('reviewed_public_mass_builder',ROOT/'scripts/build_public_mass_repro_20261107.py')
    builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
    original,staged=read(SOURCE),read(STAGE/'notebook.ipynb')
    prepared,metadata,recipe=map(read,[STAGE/'prepare_receipt.json',STAGE/'kernel-metadata.json',STAGE/'recipe.json'])
    checks=dict(source_pin=sha(SOURCE)==builder.SOURCE_SHA,
        original_29_cell_sources_unchanged=len(original['cells'])==29 and len(staged['cells'])==30 and all(source(a)==source(b) for a,b in zip(original['cells'],staged['cells'])),
        original_code_asts_unchanged=all(ast.dump(ast.parse(source(a)),include_attributes=False)==ast.dump(ast.parse(source(b)),include_attributes=False) for a,b in zip(original['cells'],staged['cells']) if a['cell_type']=='code'),
        stored_outputs_cleared=all(c.get('execution_count') is None and not c.get('outputs') for c in staged['cells'] if c['cell_type']=='code'),
        private_offline_gpu=metadata['is_private'] is True and metadata['enable_internet'] is False and metadata['enable_gpu'] is True,
        no_kernel_dependencies=not metadata['kernel_sources'],
        version_pinned_eight_datasets=len(metadata['dataset_sources'])==8 and all(len(x.split('/'))==3 and x.split('/')[-1].isdigit() for x in metadata['dataset_sources']),
        prepared_hashes_match=sha(STAGE/'notebook.ipynb')==prepared['notebook_sha256'] and sha(STAGE/'kernel-metadata.json')==prepared['metadata_sha256'] and sha(STAGE/'recipe.json')==prepared['recipe_sha256'])
    binds={}
    for node in ast.parse(source(original['cells'][11])).body:
        if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id=='MODEL_PINS':binds=ast.literal_eval(node.value)
    checks['original_public_model_pins_match']=binds==builder.PUBLIC_PINS
    compile(source(staged['cells'][-1]),'actual-deployed-observer','exec')
    # Use the actual appended observer. Substitute only its expected fixture hashes.
    observer=ast.parse(source(staged['cells'][-1]))
    function=next(node for node in observer.body if isinstance(node,ast.FunctionDef))
    assign=next(node for node in function.body if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='expected' for t in node.targets))
    fixture_results={}
    with tempfile.TemporaryDirectory(prefix='public-mass-review-',dir=ROOT/'.cache/tmp-linux') as temporary:
        fixture=Path(temporary);pub=fixture/'pub';ours=fixture/'ours';pub.mkdir();ours.mkdir()
        pins={}
        for name in builder.PUBLIC_PINS:
            raw=('public-'+name).encode();(pub/name).write_bytes(raw);(ours/name).write_bytes(raw);pins[name]=sha(pub/name)
        (ours/'final_model.pt').write_bytes(b'fixture-second-distinct-model')
        lotus=fixture/'input/casmi26-lotus-candidates/candidates_lotus.parquet';lotus.parent.mkdir(parents=True);lotus.write_bytes(b'fixture-only')
        expected=dict(branch='fixture',recipe_sha256='fixture',public_pins=pins,v2_sha=sha(ours/'final_model.pt'),lotus_sha=sha(lotus))
        assign.value=ast.parse(repr(expected),mode='eval').body
        compiled=compile(ast.fix_missing_locations(observer),'observer-fixture','exec')
        for hidden in [False,True]:
            work=fixture/('hidden' if hidden else 'fast');work.mkdir()
            ids=['fixture_'+str(i) for i in range(400)]
            pd.DataFrame({'molecule_id':ids,'smiles':['CCO;CCC']*400}).to_csv(work/'submission.csv',index=False)
            if hidden:
                (work/'execution_receipt.json').write_text(json.dumps(dict(is_full_run=True,processed_molecules=400)))
                a=pd.DataFrame({'molecule_id':np.repeat(ids,2),'smiles':['CCO','CCC']*400,'neural_score':[.2,.8]*400,'neural_ok':[True]*800})
                b=a.copy();b['neural_score']=[.9,.1]*400
                c=a.copy()
                def z(v):
                    g=v.groupby(a.molecule_id)
                    return (v-g.transform('mean'))/g.transform(lambda x:x.std(ddof=0)).clip(lower=1e-6)
                c['neural_score']=.5*z(a.neural_score)+.5*z(b.neural_score)
                for name,frame in [('neural_public',a),('neural_ours',b),('neural_candidate_features',c)]:frame.to_parquet(work/(name+'.parquet'),index=False)
            scope=dict(ROOT=work,INPUT=fixture/'input',PUB_BUNDLE=pub,OURS_BUNDLE=ours,SAMPLE_IDS=ids,
                V8='MASS',MASS_ON=True,RR8=False,MASS_CENTER=-1.5,MASS_W=.15,POP_W=.10,SPEC_W=.10,NP_W=.12,LIB_HIT_GATE=.78,
                IS_RERUN=hidden,RUN_PIPELINE=hidden,PIPELINE_DONE=hidden,NEURAL_OK=hidden,CONSENSUS_OK=hidden,SUBMITTED='CUSTOM',VARIANT='CUSTOM',
                MASS_REPORT={'status':'on' if hidden else 'off: no pipeline answer in this run'},
                MASS_LEAD_REPORT={'status':'ran' if hidden else 'off: no mass table'},RR8_REPORT={'status':'off in this preset'})
            exec(compiled,scope)
            result=scope['BATCH_VARIANT_AUDIT'];fixture_results['hidden' if hidden else 'fast']=dict(status=result['status'],checks=result['checks'],models_executed=False)
        checks['fast_observer_fixture_passed']=fixture_results['fast']['status']=='passed'
        checks['hidden_observer_fixture_passed']=fixture_results['hidden']['status']=='passed'
    report=dict(status='passed' if all(checks.values()) else 'failed',checks=checks,fixture_results=fixture_results,
        no_model_or_label_or_cloud_calls=True,notebook_sha256=sha(STAGE/'notebook.ipynb'),
        observations=['materialise_sources installs official RDKit and stages both bundles before the fast branch.',
            'Original ours_bundle copies the public config.json; retained config_used differs only in output/work.',
            'Outside candidate scoring writes outsider_neural_features.parquet; mass and merge layers only read primary neural features.',
            'Source RR8 disabled status is off in this preset; active mass statuses on/ran match the observer.',
            'Fixtures exercise observer logic and declared globals, not actual model inference or hidden score.'])
    output=ROOT/'reports/public_mass_static_independent_20261107.json';output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(status=report['status'],checks_passed=sum(checks.values()),checks_total=len(checks),fixture_checks={k:len(v['checks']) for k,v in fixture_results.items()}),indent=2))
    return 0 if report['status']=='passed' else 1

if __name__=='__main__':raise SystemExit(main())
