"""Independent source/payload/header review of the three trained-head stages."""
from __future__ import annotations
import ast
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from build_mass_na_variant_20261108 import embedded_values,source


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def write(path,value):Path(path).write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')


def main():
    import torch
    out=ROOT/'reports/head_stage_source_review_20261108';out.mkdir(parents=True,exist_ok=False)
    results=[]
    for name in ('mass_head_seed0','mass_head_seed1','mass_heads_na'):
        stage=ROOT/'submission/optimization_20261108'/name
        notebook=stage/'notebook.ipynb';notebook_sha=sha(notebook)
        nb=read(notebook);recipe=read(stage/'recipe.json');branch=read(stage/'branch_spec.json')
        origin=ROOT/recipe['source_stage'].replace('\\','/');original=read(origin/'notebook.ipynb')
        checks={}
        def check(label,value):
            checks[label]=bool(value)
            if not value:raise AssertionError(name+': '+label)
        check('source_stage_pin',sha(origin/'notebook.ipynb')==recipe['source_notebook_sha256'])
        changed=[i for i,(a,b) in enumerate(zip(original['cells'],nb['cells'])) if source(a)!=source(b)]
        check('only_planned_existing_cells_change',changed==([14] if recipe['combined_real_na_gl'] else [14,29]))
        check('one_new_observer_cell',len(nb['cells'])==len(original['cells'])+1)
        check('all_code_compiles',all(compile(source(c),'staged-head','exec') for c in nb['cells'] if c['cell_type']=='code'))
        values=embedded_values(source(nb['cells'][11]));code=out/name;code.mkdir()
        (code/'neural_scores.py').write_text(values['MODULES']['neural_scores.py'],encoding='utf-8')
        function=next(n for n in ast.parse(source(nb['cells'][14])).body
            if isinstance(n,ast.FunctionDef) and n.name=='_install_candidate_head')
        scope=dict(CODE=code)
        exec(compile(ast.fix_missing_locations(ast.Module(body=[function],type_ignores=[])),
                     '<actual-head-installer>','exec'),scope)
        scope['_install_candidate_head']()
        check('actual_installer_payload_shas',all(sha(code/f)==wanted for f,wanted in recipe['payload_sha256'].items()))
        check('original_scorer_copy_pinned',sha(code/'neural_scores_original.py')==recipe['original_scorer_sha256'])
        wrapper=(code/'neural_scores.py').read_text();compile(wrapper,'actual-dispatch-wrapper','exec')
        check('wrapper_dispatches_shared_adapter',wrapper=="from learned_head_score import score\nimport sys\nif __name__=='__main__':score(*sys.argv[1:])\n")
        runtime=read(code/'learned_head_runtime.json')
        check('runtime_source_bindings',sha(code/runtime['baseline_scorer_file'])==runtime['baseline_scorer_sha256']
            and sha(code/runtime['head_model_file'])==runtime['head_model_sha256'] and runtime['required_step']==2500)
        observed=[]
        for item in runtime['heads']:
            path=code/item['file'];weights=torch.load(path,map_location='cpu',weights_only=True)
            observed.append(dict(sha256=sha(path),seed=weights['seed'],step=weights['step']))
            if weights['encoder_sha256']!='c08d2101154d057890de088be63834eb622468892a3b842512fdc5a65e02ff46':
                raise ValueError('Wrong frozen-v2 header')
            if weights['head_config']!=dict(embedding=192,hidden=64,residual_bound=4.0):
                raise ValueError('Unexpected actual head model shape')
            if tuple(weights['state_dict']['network.0.weight'].shape)!=(64,403):
                raise ValueError('Unexpected actual input projection')
        check('actual_checkpoint_headers_match_recipe',observed==recipe['heads'])
        check('trained_files_match_embedded_payload',all(sha(code/x['file'])==sha(ROOT/'runs/candidate_head_20261108'/x['file'])
            for x in runtime['heads']))
        metadata=read(stage/'kernel-metadata.json');oldmeta=read(origin/'kernel-metadata.json')
        check('metadata_changes_only_new_identity',all(metadata.get(k)==v for k,v in oldmeta.items() if k not in ('id','title','code_file')))
        check('title_matches_requested_slug',metadata['id']==branch['target'] and metadata['title']==branch['target'].split('/')[1].replace('-',' '))
        if recipe['combined_real_na_gl']:
            oldbranch=read(origin/'branch_manifest.json')
            check('combined_inherits_final_na_audits',branch['required_runtime_audits'][:-1]==oldbranch['required_runtime_audits'])
            check('combined_preserves_final_na_adapter_and_observer',source(nb['cells'][11])==source(original['cells'][11])
                and source(nb['cells'][30])==source(original['cells'][30]))
        else:
            oldbranch=next(x for x in read(ROOT/'submission/aggressive_20261107/manifest.json')['branches'] if x['name']=='public_mass_repro')
            check('inherits_confirmed_baseline_audit_contract',branch['required_runtime_audits'][:-1]==oldbranch['required_runtime_audits'])
        check('frozen_notebook_sha_matches_branch',sha(notebook)==notebook_sha==branch['notebook_sha256'])
        record=dict(status='passed',name=name,notebook_sha256=notebook_sha,checks=checks,
            actual_ast_installer_executed=True,weights_loaded_cpu_only=True,
            model_inference=False,training=False,cloud_write=False)
        write(code/'source_verification.json',record);write(stage/'independent_source_review.json',record);results.append(record)
    write(out/'verification.json',dict(status='passed',results=results))
    print(json.dumps(dict(status='passed',results=[dict(name=r['name'],notebook_sha256=r['notebook_sha256'],checks=len(r['checks'])) for r in results]),indent=2))


if __name__=='__main__':main()
