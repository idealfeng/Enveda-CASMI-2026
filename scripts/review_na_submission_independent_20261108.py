"""Independent staged Na observer and counted merge mechanics, no model or cloud."""
from __future__ import annotations
import ast
import base64
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from build_mass_na_variant_20261108 import embedded_values,source


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):Path(path).write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module);return module


def main():
    import pandas as pd
    stage=ROOT/'submission/optimization_20261108/mass_gl_na'
    notebook=stage/'notebook.ipynb';notebook_sha=sha(notebook)
    nb=json.loads(notebook.read_text(encoding='utf-8'));base=json.loads((ROOT/'submission/aggressive_20261107/public_mass_repro/notebook.ipynb').read_text(encoding='utf-8'))
    folder=ROOT/'reports/na_submission_independent_review_20261108';folder.mkdir(parents=True,exist_ok=False)
    checks={}
    def check(name,value):
        checks[name]=bool(value)
        if not value:raise AssertionError(name)
    check('only_adapter_and_observer_original_cells_changed',
        [i for i,(a,b) in enumerate(zip(base['cells'],nb['cells'])) if source(a)!=source(b)]==[11,29])
    check('all_code_compiles',all(compile(source(c),'staged-na','exec') for c in nb['cells'] if c['cell_type']=='code'))
    values=embedded_values(source(nb['cells'][11]));code=folder/'code';code.mkdir()
    for name,text in values['MODULES'].items():(code/name).write_text(text,encoding='utf-8')
    post=embedded_values(source(nb['cells'][13]))['_post'];(code/'parallax_physical.py').write_text(post,encoding='utf-8')
    frozen=folder/'frozen.ipynb';frozen.write_bytes(base64.b64decode(values['FROZEN_B64']))
    check('frozen_source_bytes_preserved',sha(frozen)==values['FROZEN_SHA256'])
    observer=source(nb['cells'][-1]);fn=next(n for n in ast.parse(observer).body if isinstance(n,ast.FunctionDef))
    expected=ast.literal_eval(next(n.value for n in fn.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='expected' for t in n.targets)))
    check('runtime_payloads_match_observer_pins',sha(code/'runner.py')==expected['runner_sha256']
        and sha(code/'gl_na_hook.py')==expected['hook_sha256']
        and all(sha(code/name)==wanted for name,wanted in expected['extra_source_sha256'].items()))
    # Extracted adapter is tested; no source mutation or GPU model load.
    hook=load('_review_actual_na_hook',code/'gl_na_hook.py')
    h={'a':{'C':.2,'CC':.5},'h':{'N':.8}}
    na={'a':{'C':.8,'CC':.4},'n':{'O':.6}}
    hc={'a':{'C':1,'CC':2},'h':{'N':1}}
    nc={'a':{'C':3,'CC':1},'n':{'O':2}}
    merged=hook.merge_scores(h,na,hc,nc)
    check('actual_merge_candidate_weighted',abs(merged['a']['C']-.65)<1e-15 and abs(merged['a']['CC']-(1.4/3))<1e-15)
    check('actual_merge_preserves_no_na_values',merged['h']==h['h'])
    check('actual_merge_adds_na_only_query',merged['n']==na['n'])
    for name,counts in [('negative_count',{'a':{'C':-1,'CC':1},'n':{'O':2}}),
                        ('finite_with_zero_count',{'a':{'C':0,'CC':1},'n':{'O':2}}),
                        ('float_count',{'a':{'C':3.,'CC':1},'n':{'O':2}})]:
        rejected=False
        try:hook.merge_scores(h,na,hc,counts)
        except ValueError:rejected=True
        check('actual_merge_rejects_'+name,rejected)
    runtime_checks={name:True for name in ['original_runner_pin','original_checkpoint_pin','original_h_output_unchanged',
        'non_na_query_scores_exactly_unchanged','exact_na_query_set','exact_na_candidate_sets',
        'actual_finite_candidate_counts','original_candidate_sets','original_h_input_selection','real_na_input_selection']}
    report=dict(status='passed',checks=runtime_checks,combined_queries=3)
    write(folder/'gl_na_runtime.json',report);write(folder/'gl_na_combined.json',merged)
    write(folder/'execution_receipt.json',dict(processed_molecules=3,source_adaptations=[expected['adaptation']]))
    evidence=pd.DataFrame([dict(molecule_id=m,smiles=s,gl=v) for m,d in merged.items() for s,v in d.items()])
    evidence.to_parquet(folder/'frozen_candidate_evidence.parquet',index=False)
    namespace=dict(ROOT=folder,CODE=code,FROZEN=frozen,FROZEN_SHA256=values['FROZEN_SHA256'],
        pd=pd,Path=Path,SAMPLE_IDS=['a','h','n'],BATCH_VARIANT_AUDIT={'status':'passed'})
    def observe(hidden=True):
        scope=dict(namespace,IS_RERUN=hidden,RUN_PIPELINE=hidden,PIPELINE_DONE=hidden)
        exec(compile(observer,'<actual-staged-na-observer>','exec'),scope)
        return scope['NA_VARIANT_AUDIT']
    fast=observe(False);check('actual_fast_observer_passes',fast['mode']=='fast_static')
    hidden=observe();check('actual_hidden_observer_passes',hidden['mode']=='hidden_full' and hidden['checks']['expanded_scores_exported'])
    def rejects(name,change):
        write(folder/'gl_na_runtime.json',report)
        evidence.to_parquet(folder/'frozen_candidate_evidence.parquet',index=False)
        change();rejected=False
        try:observe()
        except (AssertionError,KeyError,ValueError):rejected=True
        check(name,rejected)
    rejects('observer_rejects_empty_runtime_checks',lambda:write(folder/'gl_na_runtime.json',dict(report,checks={})))
    rejects('observer_rejects_failed_runtime',lambda:write(folder/'gl_na_runtime.json',dict(report,status='failed')))
    bad=copy.deepcopy(runtime_checks);bad['original_candidate_sets']=False
    rejects('observer_rejects_failed_named_check',lambda:write(folder/'gl_na_runtime.json',dict(report,checks=bad)))
    rejects('observer_rejects_wrong_query_count',lambda:write(folder/'gl_na_runtime.json',dict(report,combined_queries=4)))
    def corrupt_export():
        changed=evidence.copy();changed.loc[0,'gl']+=.001;changed.to_parquet(folder/'frozen_candidate_evidence.parquet',index=False)
    rejects('observer_rejects_changed_consumed_gl_score',corrupt_export)
    def no_export():
        changed=evidence.copy();changed['smiles']='DOES_NOT_MATCH';changed.to_parquet(folder/'frozen_candidate_evidence.parquet',index=False)
    rejects('observer_rejects_no_consumed_scores',no_export)
    check('reviewed_notebook_unchanged',sha(notebook)==notebook_sha)
    result=dict(status='passed',notebook_sha256=notebook_sha,checks=checks,model_inference=False,
        training=False,cloud_write=False,fixtures_only=True,
        source_scope='actual staged observer and embedded counted-merge helper',
        fast_checks=fast['checks'],hidden_checks=hidden['checks'])
    write(folder/'verification.json',result);write(stage/'independent_review.json',result)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
