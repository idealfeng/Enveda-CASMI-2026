"""Real changed-cell evidence smoke and existing unlabelled score replay.

No model process, no full-pipeline initialization, no truth/accuracy evaluation.
"""
from pathlib import Path
from collections import Counter
import importlib.util
import json
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.cache/rdkit-official-linux-2026033'))
sys.path.insert(0,str(ROOT/'scripts'))
import pandas as pd
import rdkit
import evidence_early_overlay_20261114 as overlay
import external_library_overlay_20261109 as original

PRODUCTION=ROOT/'runs/generation_production_20261113_r2/kaggle/working'
OUT=ROOT/'reports/optimization_20261114/evidence_early_components'
ARMS=('gl_evidence_early','dual_evidence_agreement')


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def save(path,value):Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def source(cell):return ''.join(cell['source'])


def main():
    assert rdkit.__version__=='2026.03.3'
    OUT.mkdir(parents=True,exist_ok=False)
    reports={};checks={};base=read(PRODUCTION/'external_overlay_audit.json')
    parent=read(ROOT/'submission/optimization_20261109/mass_guarded_extlib/notebook.ipynb')
    for arm in ARMS:
        stage=ROOT/'submission/optimization_20261114'/arm
        book=read(stage/'notebook.ipynb');spec=read(stage/'branch_spec.json')
        assert book['cells'][:-1]==parent['cells']
        assert overlay.sha(stage/'notebook.ipynb')==spec['notebook_sha256']
        reports[arm]={}
        for hidden in (False,True):
            dest=OUT/(arm+('_hidden' if hidden else '_fast'));code=dest/'p2s_code';code.mkdir(parents=True)
            for name in ['submission.csv','external_overlay_runtime.json','frozen_candidate_evidence.parquet']:
                shutil.copy2(PRODUCTION/name,dest/name)
            for folder,name in [('gl_work','gl_out.json'),('ice_work','ice_out.json')]:
                (dest/folder).mkdir();shutil.copy2(PRODUCTION/folder/name,dest/folder/name)
            ids=pd.read_csv(dest/'submission.csv',dtype=str).molecule_id.tolist()
            scope=dict(ROOT=dest,CODE=code,IS_RERUN=hidden,SAMPLE_IDS=ids,EXTERNAL_OVERLAY_AUDIT=base)
            exec(compile(source(book['cells'][-1]),str(stage/'notebook.ipynb')+':last','exec'),scope)
            audit=read(dest/'evidence_early_audit.json');runtime=read(dest/'evidence_early_runtime.json')
            assert audit['status']=='passed' and all(audit['checks'].values())
            reports[arm]['hidden_full_components' if hidden else 'fast_static']=dict(
                audit=audit,observed_queries=len(runtime['observations']),protected_queries=runtime['protected_queries'],
                eligible_queries=runtime['eligible_queries'],actual_evidence_executed=runtime['evidence_executed'])
            if hidden:
                original_final=(dest/'submission.csv').read_bytes()
                scores=read(dest/'gl_work/gl_out.json');mid=next(iter(scores));key=next(iter(scores[mid]));scores[mid][key]+=1
                save(dest/'gl_work/gl_out.json',scores)
                try:
                    mod=scope['_evidence_module']
                    mod.audit(dest,True,ids,base,arm,read(stage/'recipe.json') and overlay.sha(stage/'recipe.json'),overlay.sha(ROOT/'scripts/evidence_early_overlay_20261114.py'))
                    raise AssertionError('Tampered evidence accepted')
                except ValueError as error:
                    assert 'bindings changed' in str(error)
                checks[arm+'_actual_score_file_tamper_blocked']=True
                shutil.copy2(PRODUCTION/'gl_work/gl_out.json',dest/'gl_work/gl_out.json')
                (dest/'submission.csv').write_bytes(original_final)
        checks[arm+'_actual_cell_and_source_bound']=True
    # Existing actual stage predictions and simulator scores only; no truth
    # labels, no panel reconstruction, no metric calculation or parameter scan.
    cache=ROOT/'runs/validation_flex_c2_20261105d'
    old=pd.read_csv(cache/'submission_e004_control.csv',dtype=str,keep_default_na=False)
    gl=read(cache/'gl_work/gl_out.json');ice=read(cache/'ice_work/ice_out.json')
    larger={}
    for arm in ARMS:
        rows=[]
        for mid,raw in zip(old.molecule_id,old.smiles):
            candidates=raw.split(';')
            proposal,event=overlay.rank_candidates(candidates,gl.get(mid,{}),ice.get(mid,{}),arm,original.identity)
            assert Counter(proposal)==Counter(candidates) and original.valid(';'.join(proposal))
            assert all(overlay.formula(a)==overlay.formula(b) for a,b in zip(candidates,proposal))
            if arm=='gl_evidence_early':assert candidates[0]==proposal[0]
            rows.append(dict(molecule_id=mid,changed=proposal!=candidates,changed_top1=proposal[0]!=candidates[0],
                             eligible=bool(event['decisions']),observation=event))
        larger[arm]=dict(queries=len(rows),changed_queries=sum(r['changed'] for r in rows),
                         changed_top1=sum(r['changed_top1'] for r in rows),eligible_queries=sum(r['eligible'] for r in rows),
                         scope='Existing stage lists, actual aggregate scores, no AB/protection integration and no new metrics.')
        save(OUT/(arm+'_cached_score_replay.json'),dict(summary=larger[arm],rows=rows))
        checks[arm+'_same_candidate_and_formula_slots']=True
    result=dict(status='passed_actual_evidence_changed_components',checks=checks,production_subset_queries=2,
                rdkit_version=rdkit.__version__,reports=reports,larger_component_delta=larger,
                module_sha256=overlay.sha(ROOT/'scripts/evidence_early_overlay_20261114.py'),
                full_pipeline_executed=False,model_or_library_process_launched=False,
                truth_labels_read=False,truth_metrics_computed=False,
                limitation='Actual appended cells on 2-query generated-variant final CSV, then pure ranking on existing old stage lists; not exact champion full inference or clean CV.')
    save(OUT/'verification.json',result)
    print(json.dumps(dict(status=result['status'],checks=checks,larger_component_delta=larger)))


if __name__=='__main__':main()
