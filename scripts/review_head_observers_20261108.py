"""Independently exercise deployed head observers using source-pinned fixtures, no model."""
from __future__ import annotations
import ast
import base64
import copy
import hashlib
import json
from pathlib import Path
import tempfile

import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
NAMES=('mass_head_seed0','mass_head_seed1','mass_heads_na')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def source(cell):return ''.join(cell['source']) if isinstance(cell['source'],list) else cell['source']
def write(path,value):Path(path).write_text(json.dumps(value,indent=2)+'\n')


def inspect(stage):
    notebook=read(stage/'notebook.ipynb')
    install=next(n for n in ast.parse(source(notebook['cells'][14])).body
                 if isinstance(n,ast.FunctionDef) and n.name=='_install_candidate_head')
    values={}
    for node in install.body:
        if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name):
            try:values[node.targets[0].id]=ast.literal_eval(node.value)
            except (ValueError,TypeError):pass
    observer=source(notebook['cells'][-1])
    function=next(n for n in ast.parse(observer).body if isinstance(n,ast.FunctionDef) and n.name=='_observe_learned_head')
    expected=ast.literal_eval(next(n.value for n in function.body if isinstance(n,ast.Assign)
        and any(isinstance(t,ast.Name) and t.id=='expected' for t in n.targets)))
    return values['payloads'],values['pins'],observer,expected


def fixture(stage,mode,scenario='valid',outsider=True):
    payloads,pins,observer,expected=inspect(stage)
    with tempfile.TemporaryDirectory(prefix='head-observer-review-',dir=ROOT/'.cache/tmp-linux') as temporary:
        root=Path(temporary);code=root/'code';code.mkdir()
        for name,value in payloads.items():
            raw=base64.b64decode(value)
            assert hashlib.sha256(raw).hexdigest()==pins[name]
            (code/name).write_bytes(raw)
        original=ROOT/'runs/validation_flex_c2_20261105d/p2s_code/neural_scores.py'
        (code/'neural_scores_original.py').write_bytes(original.read_bytes())
        pd.DataFrame(dict(molecule_id=['q0','q1'],smiles=['CCO;CCC','CCN;CCCl'])).to_csv(root/'submission.csv',index=False)
        q=pd.DataFrame(dict(molecule_id=['q0','q1'],adduct=['[M+H]+','[M+Na]+']))
        q.to_parquet(root/'effective_query_spectra.parquet',index=False)
        evidence=pd.DataFrame(dict(molecule_id=['q0','q0','q1','q1'],smiles=['CCO','CCC','CCN','CCCl'],
                                   baseline_rank=[1,2,1,2],processed=[True]*4))
        evidence.to_parquet(root/'frozen_candidate_evidence.parquet',index=False)
        evidence.iloc[:2].to_parquet(root/'outsider_evidence.parquet',index=False)
        def scored(label,evidence_path,output_path,audit_path):
            frame=pd.read_parquet(root/evidence_path)
            frame['neural_ok']=True
            frame['neural_score']=[.1]*len(frame)
            frame.to_parquet(root/output_path,index=False)
            item=dict(status='passed',role='learned_v2',head_applied=True,encoder_sha256=expected['encoder_sha256'],
                      heads=expected['head_receipts'],output_sha256=sha(root/output_path),
                      evidence_sha256=sha(root/evidence_path),queries_sha256=sha(root/'effective_query_spectra.parquet'),
                      input_rows=len(frame),output_rows=len(frame),scored_candidate_rows=len(frame),
                      scored_queries=int(frame.molecule_id.nunique()),errors=[])
            write(root/audit_path,item)
        scored('main','frozen_candidate_evidence.parquet','neural_ours.parquet','neural_candidate_features.parquet.head_audit.json')
        scored('outsider','outsider_evidence.parquet','outsider_neural_features.parquet','outsider_neural_features.parquet.head_audit.json')
        name='neural_candidate_features.parquet.head_audit.json'
        audit=read(root/name)
        if scenario=='bad_coverage':audit['scored_candidate_rows']-=1
        elif scenario=='bad_query_coverage':audit['scored_queries']+=1
        elif scenario=='bad_encoder':audit['encoder_sha256']='0'*64
        elif scenario=='bad_head_receipt':audit['heads']=[dict(sha256='0'*64,step=2500,seed=123)]
        elif scenario=='bad_output_hash':audit['output_sha256']='0'*64
        elif scenario=='bad_evidence_hash':audit['evidence_sha256']='0'*64
        elif scenario=='bad_query_hash':audit['queries_sha256']='0'*64
        elif scenario=='bad_row_count':audit['input_rows']+=1
        elif scenario=='bad_error_scope':audit['errors']=[dict(molecule_id='nonexistent')]
        elif scenario=='head_not_applied':audit['head_applied']=False
        elif scenario=='bad_status':audit['status']='failed'
        elif scenario=='corrupt_adapter':(code/'learned_head_score.py').write_bytes(b'corrupted adapter')
        elif scenario=='corrupt_checkpoint':(code/expected['heads'][0]['file']).write_bytes(b'corrupted checkpoint')
        elif scenario=='corrupt_original':(code/'neural_scores_original.py').write_bytes(b'corrupted original')
        elif scenario=='corrupt_runtime':(code/'learned_head_runtime.json').write_bytes(b'{}')
        elif scenario=='bad_outsider_coverage':
            p=root/'outsider_neural_features.parquet.head_audit.json';r=read(p);r['scored_candidate_rows']=0;write(p,r)
        elif scenario!='valid':raise ValueError(scenario)
        write(root/name,audit)
        scope=dict(Path=Path,pd=pd,ROOT=root,CODE=code,BATCH_VARIANT_AUDIT=dict(status='passed'),
            V8='MASS',MASS_ON=True,RR8=False,POP_W=.10,SPEC_W=.10,NP_W=.12,LIB_HIT_GATE=.78,
            IS_RERUN=mode=='hidden',RUN_PIPELINE=mode=='hidden',PIPELINE_DONE=mode=='hidden',
            NEURAL_OK=mode=='hidden',CONSENSUS_OK=mode=='hidden',SUBMITTED='CUSTOM',VARIANT='CUSTOM',
            OUTSIDERS_OK=outsider)
        try:
            exec(compile(observer,'actual-deployed-head-observer','exec'),scope)
            return dict(accepted=True,result=scope['LEARNED_HEAD_AUDIT'],model_inference=False)
        except (AssertionError,ValueError,KeyError) as error:
            return dict(accepted=False,error_type=type(error).__name__,reason=str(error),model_inference=False)


def main():
    out=ROOT/'reports/head_submission_review_20261108';out.mkdir(parents=True,exist_ok=True)
    reports=[]
    failures=('bad_coverage','bad_query_coverage','bad_encoder','bad_head_receipt','bad_output_hash',
              'bad_evidence_hash','bad_query_hash','bad_row_count','bad_error_scope','head_not_applied',
              'bad_status','corrupt_adapter','corrupt_checkpoint','corrupt_original','corrupt_runtime','bad_outsider_coverage')
    for name in NAMES:
        stage=ROOT/'submission/optimization_20261108'/name
        original_sha=sha(stage/'notebook.ipynb')
        receipt=read(stage/'prepare_receipt.json')
        valid_fast=fixture(stage,'fast')
        valid_hidden=fixture(stage,'hidden')
        optional_skipped=fixture(stage,'hidden',outsider=False)
        rejected={kind:fixture(stage,'hidden',kind) for kind in failures}
        checks=dict(frozen_source_sha=original_sha==receipt['notebook_sha256'],
                    actual_fast_observer=valid_fast['accepted'],
                    actual_hidden_main_and_outside_observer=valid_hidden['accepted'],
                    original_optional_outside_skip=optional_skipped['accepted'],
                    no_stage_bytes_changed=sha(stage/'notebook.ipynb')==original_sha)
        checks.update({kind+'_rejected':not result['accepted'] for kind,result in rejected.items()})
        report=dict(status='passed' if all(checks.values()) else 'failed',branch=name,notebook_sha256=original_sha,
                    checks=checks,fast=valid_fast,hidden=valid_hidden,optional_skipped=optional_skipped,
                    rejected=rejected,fixtures_only=True,no_models_loaded=True,no_gpu_or_cloud_calls=True)
        write(out/(name+'.json'),report);reports.append(report)
    summary=dict(status='passed' if all(x['status']=='passed' for x in reports) else 'failed',
                 reports=[dict(branch=x['branch'],notebook_sha256=x['notebook_sha256'],
                               checks_passed=sum(x['checks'].values()),checks_total=len(x['checks'])) for x in reports],
                 no_stage_bytes_changed=True,fixture_scope='Actual final head observers; source/weight payload pins and runtime evidence checks, not model-quality validation')
    write(out/'verification.json',summary);print(json.dumps(summary,indent=2))
    if summary['status']!='passed':raise SystemExit(1)


if __name__=='__main__':main()
