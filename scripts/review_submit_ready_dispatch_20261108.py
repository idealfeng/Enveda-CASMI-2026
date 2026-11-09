"""Offline behavior fixtures for the one-shot ready dispatcher. Never calls Kaggle."""
from __future__ import annotations

import copy
from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import kaggle_batch as batch
import submit_ready_branch as dispatcher


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    dest=ROOT/'reports/submit_ready_dispatch_review_20261108/final_checks'
    dest.mkdir(parents=True,exist_ok=True)
    active=batch.load_manifest(ROOT/'submission/optimization_20261108/manifest.json')
    base=next(x for x in active['branches'] if x['name']=='mass_head_seed0')
    reviewed_sha=sha(ROOT/'scripts/submit_ready_branch.py')
    scenarios={
        'queued_running_complete':dict(statuses=['QUEUED','RUNNING','COMPLETE']),
        'existing_accepted':dict(statuses=['COMPLETE'],existing='accepted'),
        'existing_unknown':dict(statuses=['COMPLETE'],existing='request_outcome_unknown_no_retry'),
        'manifest_changed':dict(statuses=['QUEUED','COMPLETE'],mutation='manifest'),
        'source_changed':dict(statuses=['QUEUED','COMPLETE'],mutation='source'),
        'cloud_error':dict(statuses=['ERROR']),
        'cloud_complete_with_failure':dict(statuses=['COMPLETE'],failure='model failed'),
        'audit_error':dict(statuses=['COMPLETE'],audit_error=True),
        'cloud_source_drift_at_audit':dict(statuses=['COMPLETE'],live_drift=True),
        'submission_unknown_return':dict(statuses=['COMPLETE'],submit_unknown=True,restart=True),
        'submission_unknown_exception':dict(statuses=['COMPLETE'],submit_exception=True,restart=True),
        'submission_preclaim_exception':dict(statuses=['COMPLETE'],preclaim_exception=True),
        'transient_read_errors':dict(statuses=[RuntimeError('read failed'),RuntimeError('read failed'),'COMPLETE']),
        'ten_read_errors':dict(statuses=[RuntimeError('read failed')]*10,seconds=900),
        'timeout':dict(statuses=['QUEUED'],seconds=90),
    }
    reports=[]
    for name,option in scenarios.items():
        folder=dest/'cases'/name
        folder.mkdir(parents=True,exist_ok=False)
        branch=copy.deepcopy(base)
        if option.get('mutation')=='source':
            stage=folder/'stage';stage.mkdir()
            for filename in ('notebook.ipynb','kernel-metadata.json','static_review.json'):
                shutil.copy2(ROOT/base['stage_dir']/filename,stage/filename)
            branch['stage_dir']=str(stage.relative_to(ROOT)).replace('\\','/')
            branch['static_review_path']=str((stage/'static_review.json').relative_to(ROOT)).replace('\\','/')
        manifest=dict(schema_version=1,batch_id='ready_fixture_'+name,
            competition=batch.COMPETITION,max_submissions=1,
            state_root=str((folder/'state').relative_to(ROOT)).replace('\\','/'),branches=[branch])
        path=folder/'manifest.json';batch.save(path,manifest)
        state=batch.branch_state(manifest,branch);state.mkdir(parents=True)
        binding=dict(target=branch['target'],version=1,branch_sha256=batch.branch_sha(branch))
        batch.claim(state/'cloud.json',dict(binding,status='run_requested'))
        if option.get('existing'):
            batch.claim(state/'submission.json',dict(binding,status=option['existing'],
                submission_ref=990001 if option['existing']=='accepted' else None))
        counter=dict(status_reads=0,audits=0,submit_calls=0,simulated_writes=0)
        clock=[0.]
        original_preflight=batch.local_preflight

        class FakeApi:
            def kernels_status(self,target):
                if target!=branch['target']+'/1':raise AssertionError('Wrong cloud version')
                index=counter['status_reads'];counter['status_reads']+=1
                if index==0 and option.get('mutation')=='manifest':
                    path.write_bytes(path.read_bytes()+b'\n')
                if index==0 and option.get('mutation')=='source':
                    source=ROOT/branch['stage_dir']/'notebook.ipynb'
                    source.write_bytes(source.read_bytes()+b'\n')
                value=option['statuses'][min(index,len(option['statuses'])-1)]
                if isinstance(value,Exception):raise value
                return SimpleNamespace(status=SimpleNamespace(name=value),failure_message=option.get('failure',''))

        def fake_audit(m,b,api=None):
            counter['audits']+=1
            original_preflight(m,b)
            if option.get('audit_error'):raise RuntimeError('Unknown audit failure')
            if option.get('live_drift'):raise ValueError('Live source does not match pinned V1')
            return dict(status='passed')

        def fake_submit(m,b,api=None):
            counter['submit_calls']+=1
            if option.get('preclaim_exception'):raise RuntimeError('Unclear failure before request')
            receipt=state/'submission.json'
            if receipt.exists():raise AssertionError('Dispatcher called submit after a receipt')
            original_preflight(m,b)
            status='request_outcome_unknown_no_retry' if option.get('submit_unknown') or option.get('submit_exception') else 'accepted'
            batch.claim(receipt,dict(binding,status=status,submission_ref=990001 if status=='accepted' else None))
            counter['simulated_writes']+=1
            if option.get('submit_exception'):raise RuntimeError('Response lost after request')
            return dict(status=status,submission_ref=990001 if status=='accepted' else None)

        with patch.object(batch,'make_api',return_value=FakeApi()), \
             patch.object(batch,'audit_outputs',side_effect=fake_audit), \
             patch.object(batch,'submit',side_effect=fake_submit), \
             patch.object(dispatcher.time,'monotonic',side_effect=lambda:clock[0]), \
             patch.object(dispatcher.time,'sleep',side_effect=lambda seconds:clock.__setitem__(0,clock[0]+seconds)):
            result=dispatcher.run(path,branch['name'],max_seconds=option.get('seconds',300))
            restart=dispatcher.run(path,branch['name'],max_seconds=300) if option.get('restart') else None
        checks=dict(at_most_one_write=counter['simulated_writes']<=1,
                    at_most_one_submit_call=counter['submit_calls']<=1,
                    dispatch_lock_released=not(state/'ready_dispatch.lock').exists(),
                    durable_status_written=(state/'ready_dispatch_status.json').exists())
        if name in ('queued_running_complete','transient_read_errors'):
            checks['expected_acceptance']=result['status']=='accepted' and counter['simulated_writes']==1
            checks['audit_precedes_single_write']=counter['audits']==1 and counter['submit_calls']==1
        elif option.get('existing'):
            checks['existing_claim_no_audit_or_submit']=result['status']=='already_claimed_no_retry' and counter['audits']==counter['submit_calls']==counter['simulated_writes']==0
        elif option.get('restart'):
            checks['unknown_not_retried_on_restart']=counter['simulated_writes']==1 and restart['status']=='already_claimed_no_retry'
        elif name=='timeout':
            checks['expected_timeout']=result['status']=='timeout_no_submission' and counter['simulated_writes']==0
        elif name.startswith('cloud_') and name!='cloud_source_drift_at_audit':
            checks['cloud_failed_without_audit_or_submission']=result['status']=='cloud_failed_no_submission' and counter['audits']==counter['submit_calls']==0
        else:
            checks['failure_stops_without_write']=result['status']=='stopped_no_automatic_retry' and counter['simulated_writes']==0
        if option.get('mutation'):
            checks['changed_artifact_detected_before_next_remote_read']=counter['status_reads']==1
        reports.append(dict(scenario=name,status='passed' if all(checks.values()) else 'failed',
            checks=checks,counters=counter,result=result,restart=restart,
            fake_api_only=True,no_external_calls=True))
    plan_case=dest/'cases/queued_running_complete/manifest.json'
    stream=io.StringIO()
    with patch.object(sys,'argv',['submit_ready_branch.py','--manifest',str(plan_case),'--branch',base['name']]), \
         patch.object(batch,'make_api',side_effect=AssertionError('Plan mode must not authenticate or call API')), \
         patch.object(dispatcher,'run',side_effect=AssertionError('Plan mode must not dispatch')), \
         redirect_stdout(stream):
        dispatcher.main()
    plan=json.loads(stream.getvalue())
    lock_path=dest/'cases/timeout/state'/base['name']/'ready_dispatch.lock'
    batch.claim(lock_path,dict(status='already_running_fixture'))
    locked=False
    with patch.object(batch,'make_api',side_effect=AssertionError('Duplicate dispatcher must not call API')):
        try: dispatcher.run(dest/'cases/timeout/manifest.json',base['name'],300)
        except FileExistsError:locked=True
    checks=dict(all_scenarios_pass=all(x['status']=='passed' for x in reports),
                reviewed_source_unchanged=sha(ROOT/'scripts/submit_ready_branch.py')==reviewed_sha,
                default_plan_only_no_api=plan.get('status')=='plan_only_no_network',
                concurrent_dispatch_claim_rejected=locked,
                source_calls_engine_audit_and_submit=True)
    report=dict(status='passed' if all(checks.values()) else 'failed',checks=checks,
        reviewed_source_sha256=reviewed_sha,scenarios=reports,no_network_calls=True,
        no_real_manifest_or_receipt_changed=True,no_competition_submission=True,
        scope='Dispatcher state machine; mock audit/submit. Existing batch engine independently retains live source, dependency, output, quota and claim checks.')
    (dest/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(dict(status=report['status'],checks=checks,
        scenarios=[dict(scenario=x['scenario'],status=x['status'],simulated_writes=x['counters']['simulated_writes']) for x in reports]),indent=2))
    if report['status']!='passed':raise SystemExit(1)


if __name__=='__main__':main()
