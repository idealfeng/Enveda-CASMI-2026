"""Independent V35 patch/observer fixtures; no labels, models or cloud actions."""
from pathlib import Path
import ast
import copy
import hashlib
import importlib.util
import json
import sys
import tempfile

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'submission/aggressive_20261107_pm'
SOURCE=ROOT/'third_party/public_scan_zz3t3rn41__casmi26-peaks-to-structures-v2_20261107_pm/source.ipynb'
NAMES=['v35_baseline','v35_weak_prior','v35_v2_emphasis','v35_robust_mass','v35_no_interleave']

def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def src(cell):return ''.join(cell['source']) if isinstance(cell['source'],list) else cell['source']
def tree(source):return ast.dump(ast.parse(source),include_attributes=False)


def fixture_observer(notebook,recipe,temp):
    parsed=ast.parse(src(notebook['cells'][-1]))
    function=next(node for node in parsed.body if isinstance(node,ast.FunctionDef))
    assignment=next(node for node in function.body if isinstance(node,ast.Assign)
        and any(isinstance(t,ast.Name) and t.id=='expected' for t in node.targets))
    expected=ast.literal_eval(assignment.value)
    pub,ours=temp/'public',temp/'ours';pub.mkdir();ours.mkdir()
    pins={}
    for name in expected['public_pins']:
        data=('fixture-'+name).encode();(pub/name).write_bytes(data);(ours/name).write_bytes(data);pins[name]=sha(pub/name)
    (ours/'final_model.pt').write_bytes(b'fixture-other-checkpoint')
    lotus=temp/'input/casmi26-lotus-candidates/candidates_lotus.parquet';lotus.parent.mkdir(parents=True);lotus.write_bytes(b'fixture')
    expected.update(public_pins=pins,v2_sha=sha(ours/'final_model.pt'),lotus_sha=sha(lotus))
    assignment.value=ast.parse(repr(expected),mode='eval').body
    compiled=compile(ast.fix_missing_locations(parsed),'deployed-round2-observer-fixture','exec')
    results={}
    for hidden in [False,True]:
        work=temp/('hidden' if hidden else 'fast');work.mkdir()
        ids=['synthetic_'+str(i) for i in range(400)]
        pd.DataFrame(dict(molecule_id=ids,smiles=['CCO;CCC']*400)).to_csv(work/'submission.csv',index=False)
        if hidden:
            (work/'execution_receipt.json').write_text(json.dumps(dict(is_full_run=True,processed_molecules=400)))
            a=pd.DataFrame(dict(molecule_id=np.repeat(ids,2),smiles=['CCO','CCC']*400,
                neural_score=[.2,.8]*400,neural_ok=[True]*800))
            b=a.copy();b['neural_score']=[.9,.1]*400
            a.loc[798:,'neural_ok']=False;b.loc[798:,'neural_ok']=False
            a.loc[798:,'neural_score']=np.nan;b.loc[798:,'neural_score']=np.nan
            def z(v):
                v=v.fillna(0.0);g=v.groupby(a.molecule_id)
                return (v-g.transform('mean'))/g.transform(lambda x:x.std(ddof=0)).clip(lower=1e-6)
            c=a.copy();w=recipe['public_weight'];c['neural_score']=w*z(a.neural_score)+(1-w)*z(b.neural_score)
            for prefix in ('neural','outsider'):
                for suffix,frame in [('public',a),('ours',b),('candidate_features' if prefix=='neural' else 'neural_features',c)]:
                    frame.to_parquet(work/(prefix+'_'+suffix+'.parquet'),index=False)
        scope=dict(ROOT=work,INPUT=temp/'input',PUB_BUNDLE=pub,OURS_BUNDLE=ours,SAMPLE_IDS=ids,
            IS_RERUN=hidden,RUN_PIPELINE=hidden,PIPELINE_DONE=hidden,NEURAL_OK=hidden,
            CONSENSUS_OK=hidden,SUBMITTED='CUSTOM',VARIANT='CUSTOM',OUTSIDERS_OK=hidden,
            MERGE_REPORT={'status':'applied'},BATCH_MASS_MAP_AUDIT={'method':'effective_all_spectra_median'})
        scope.update(recipe['config'])
        if recipe['branch']=='v35_robust_mass':
            # Read the actual deployed observer contract; this is a fake audit only.
            method=next((node.comparators[0].value for node in ast.walk(parsed)
                if isinstance(node,ast.Compare) and len(node.comparators)==1
                and isinstance(node.comparators[0],ast.Constant) and isinstance(node.comparators[0].value,str)
                and 'median' in node.comparators[0].value),'effective_all_spectra_median')
            scope['BATCH_MASS_MAP_AUDIT']={'method':method}
        exec(compiled,scope)
        result=scope['BATCH_VARIANT_AUDIT']
        results['hidden' if hidden else 'fast']=dict(status=result['status'],checks=result['checks'],models_executed=False)
        if hidden:
            # A wrong mandatory main score must fail, independently of optional outsider policy.
            wrong=pd.read_parquet(work/'neural_candidate_features.parquet');wrong.loc[0,'neural_score']+=.01
            wrong.to_parquet(work/'neural_candidate_features.parquet',index=False)
            try:exec(compiled,scope)
            except AssertionError:results['wrong_main_score_rejected']=True
            else:results['wrong_main_score_rejected']=False
    return results


def check_robust_map(builder,temp):
    code=builder.ROBUST_MAP
    # The patch executes inside the original merge function. Capture its local result.
    function='def fixture():\n'+code+'    return nm_map\n'
    root=temp/'effective';comp=temp/'raw';root.mkdir();comp.mkdir()
    effective=pd.DataFrame({'molecule_id':['a','a','a','b','bad','d','d'],
        'nm':[100.009,100.,100.0002,np.nan,np.nan,300.,300.002]})
    raw=pd.DataFrame({'molecule_id':['a','a','b','b','c','bad'],
        'precursor_mz':[501.007276,501.007276,201.007276,222.989218,182.996711,np.nan],
        'adduct':['[M+H]+','[M+H]+','[M+H]+','[M+Na]+','[M-H2O+H]+','unknown']})
    effective.to_parquet(root/'effective_query_spectra.parquet',index=False)
    raw.to_parquet(comp/'test.parquet',index=False)
    scope=dict(pd=pd,np=np,ROOT=root,COMP=comp)
    exec(compile(function,'actual-robust-map-fixture','exec'),scope)
    result=scope['fixture']()
    first=dict(result)
    effective.iloc[::-1].to_parquet(root/'effective_query_spectra.parquet',index=False)
    raw.iloc[::-1].to_parquet(comp/'test.parquet',index=False)
    second=scope['fixture']()
    checks=dict(effective_median_priority=abs(result.get('a',0)-100.0002)<1e-10,
        even_sample_median=abs(result.get('d',0)-300.001)<1e-10,
        raw_fills_missing_effective=abs(result.get('b',0)-200.)<1e-10,
        dehydrated_adduct_supported=abs(result.get('c',0)-200.)<1e-10,
        invalid_mass_excluded='bad' not in result,
        row_order_invariant=first==second)
    return dict(checks=checks,result=result,source='Executed actual builder ROBUST_MAP in a local fixture')


def main():
    original=read(SOURCE);manifest=read(BASE/'manifest.json');branches={b['name']:b for b in manifest['branches']}
    spec=importlib.util.spec_from_file_location('independent_round2_builder',ROOT/'scripts/build_round2_variants_20261107.py')
    builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
    refresh='--refresh-v2' in sys.argv
    old_report=read(ROOT/'reports/round2_independent_review_20261107_pm.json') if refresh else None
    results=copy.deepcopy(old_report['branches']) if refresh else {}
    names=['v35_v2_emphasis'] if refresh else NAMES
    with tempfile.TemporaryDirectory(prefix='round2-review-',dir=ROOT/'.cache/tmp-linux') as temporary:
        fixture_root=Path(temporary)
        for name in names:
            stage=BASE/name;nb=read(stage/'notebook.ipynb');recipe=read(stage/'recipe.json');metadata=read(stage/'kernel-metadata.json')
            branch=branches[name]
            changed=[i for i,(a,b) in enumerate(zip(original['cells'],nb['cells'])) if src(a)!=src(b)]
            allowed={'v35_baseline':[],'v35_weak_prior':[4],'v35_v2_emphasis':[14],'v35_robust_mass':[18],'v35_no_interleave':[18]}[name]
            checks=dict(one_observer_added=len(nb['cells'])==len(original['cells'])+1,
                expected_cells_only=changed==allowed,notebook_sha=sha(stage/'notebook.ipynb')==branch['notebook_sha256'],
                metadata_sha=sha(stage/'kernel-metadata.json')==branch['metadata_sha256'],
                static_review_bound=read(stage/'static_review.json')['notebook_sha256']==sha(stage/'notebook.ipynb'),
                no_stored_outputs=all(c.get('execution_count') is None and not c.get('outputs') for c in nb['cells'] if c['cell_type']=='code'),
                private_offline_gpu=metadata['is_private'] is True and metadata['enable_gpu'] is True and metadata['enable_internet'] is False,
                version_pinned_sources=len(metadata['dataset_sources'])==8 and all(len(x.split('/'))==3 for x in metadata['dataset_sources']),
                title_matches_slug=metadata['title'].replace(' ','-')==metadata['id'].split('/')[-1])
            for cell in nb['cells']:
                if cell['cell_type']=='code':compile(src(cell),'independent-compile-'+name,'exec')
            checks['all_code_compile']=True
            if name=='v35_weak_prior':
                before={};after={};exec(src(original['cells'][4]),before);exec(src(nb['cells'][4]),after)
                differences={k for k in before if not k.startswith('__') and before[k]!=after[k]}
                checks['exact_prior_configuration']=differences=={'SPEC_W','NP_W','LIB_HIT_GATE'} and after['SPEC_W']==.05 and after['NP_W']==.02 and after['LIB_HIT_GATE']==.87
            elif name=='v35_v2_emphasis':
                original_lines=src(original['cells'][14]).splitlines();current_lines=src(nb['cells'][14]).splitlines();diffs=[]
                for a,b in zip(original_lines,current_lines):
                    if a!=b:diffs.append((a,b))
                assignments=[(a,b) for a,b in diffs if "['neural_" in a]
                logs=[(a,b) for a,b in diffs if 'print(' in a]
                checks['exact_eight_ensemble_changes']=len(assignments)==8 and all(a.count('0.5 * ')==2 and b.count('0.25 * ')==1 and b.count('0.75 * ')==1 and a.replace('0.5 * ','X * ')==b.replace('0.25 * ','X * ').replace('0.75 * ','X * ') for a,b in assignments)
                checks['only_matching_log_labels_changed']=len(diffs)==10 and len(logs)==2 and all(a.replace('0.5*z(public) + 0.5*z(ours)','0.25*z(public) + 0.75*z(ours)')==b for a,b in logs)
            elif name=='v35_no_interleave':
                current=src(nb['cells'][18]);condition='if False and OUTSIDER_FILL and m_lib < LIB_HIT_GATE and str(mid) in out_by_mid:'
                checks['only_forced_interleave_disabled']=current.count(condition)==1 and current.replace(condition,condition.replace('False and ',''))==src(original['cells'][18])
                checks['vacant_fill_preserved']='if len(res) < 25:' in current and recipe['config']['OUTSIDER_FILL'] is True
            child=fixture_root/name;child.mkdir()
            fixture=fixture_observer(nb,recipe,child)
            checks['actual_fast_observer_passes']=fixture['fast']['status']=='passed'
            checks['actual_hidden_observer_passes']=fixture['hidden']['status']=='passed'
            checks['wrong_main_score_rejected']=fixture['wrong_main_score_rejected']
            results[name]=dict(status='passed' if all(checks.values()) else 'failed',checks=checks,observer_fixtures=fixture,notebook_sha256=sha(stage/'notebook.ipynb'))
        if refresh:
            robust=old_report['robust_mass_fixture']
            for name in NAMES:
                if name!='v35_v2_emphasis' and sha(BASE/name/'notebook.ipynb')!=results[name]['notebook_sha256']:
                    raise ValueError('Previously reviewed source changed')
        else:
            robust_dir=fixture_root/'robust-map';robust_dir.mkdir();robust=check_robust_map(builder,robust_dir)
    report=dict(status='passed' if all(r['status']=='passed' for r in results.values()) and all(robust['checks'].values()) else 'failed',
        branches=results,robust_mass_fixture=robust,source_sha256=sha(SOURCE),
        no_labels_or_models_or_cloud_calls=True,scope='Static source review and synthetic actual-observer fixtures; no accuracy inference')
    destination=ROOT/('reports/round2_independent_review_20261107_pm_final.json' if refresh else 'reports/round2_independent_review_20261107_pm.json')
    if destination.exists():raise FileExistsError('Preserve prior independent review')
    destination.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=report['status'],branch_checks={name:[sum(r['checks'].values()),len(r['checks'])] for name,r in results.items()},robust_mass_checks=robust['checks']),indent=2))
    return 0 if report['status']=='passed' else 1

if __name__=='__main__':raise SystemExit(main())
