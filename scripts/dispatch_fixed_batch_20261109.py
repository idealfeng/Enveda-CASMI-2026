"""Dispatch a fixed five-branch batch with at most two pending Notebook runs.

Plan-only by default. --watch permits claim-before-write launch/audit/submit via
the existing engine. A claimed unknown write is never repeated automatically.
"""
from pathlib import Path
import argparse,json,logging,math,os,time
import kaggle_batch as batch

INTERVAL=45
MAX_SECONDS=21600
ACCEPTED_CLOUD={'run_requested','run_requested_reconciled_by_source'}
ACCEPTED_SUBMISSION={'accepted','accepted_reconciled_by_unique_description'}

def prepare(manifest_path,engine=batch):
    path=engine.inside(manifest_path);manifest=engine.load_manifest(path)
    if len(manifest['branches'])!=5 or manifest['max_submissions']!=5:raise ValueError('A fixed five-branch manifest is required')
    for branch in manifest['branches']:engine.local_preflight(manifest,branch)
    return path,manifest

def plan(manifest_path,engine=batch):
    path,manifest=prepare(manifest_path,engine)
    return dict(status='plan_only_no_network',manifest_sha256=engine.sha(path),max_pending_cloud_runs=2,
        max_hours=6,submissions_at_most=5,branches=[b['name'] for b in manifest['branches']],cloud_or_submission_write_performed=False)

def run(manifest_path,max_seconds=MAX_SECONDS,*,engine=batch,clock=None,sleeper=None):
    if type(max_seconds) not in (int,float) or not math.isfinite(max_seconds) or not 0<max_seconds<=MAX_SECONDS:raise ValueError('At most six hours are allowed')
    path,manifest=prepare(manifest_path,engine);manifest_sha=engine.sha(path)
    state=engine.branch_state(manifest,manifest['branches'][0]).parent
    state.mkdir(parents=True,exist_ok=True)
    lock=state/'.dispatcher.lock';output=state/'batch_dispatcher_status.json'
    clock=time.monotonic if clock is None else clock;sleeper=time.sleep if sleeper is None else sleeper
    rows={b['name']:dict(branch=b['name'],target=b['target'],status='prepared',terminal=False,reserved_cloud_slot=False,consecutive_read_errors=0) for b in manifest['branches']}
    record=dict(status='dispatching',pid=os.getpid(),manifest_sha256=manifest_sha,started_at_utc=engine.now(),maximum_seconds=max_seconds,interval_seconds=INTERVAL,max_pending_cloud_runs=2,submissions_at_most=5,automatic_write_retries_allowed=False,branches=rows)
    engine.claim(lock,dict(pid=os.getpid(),manifest_sha256=manifest_sha,started_at_utc=record['started_at_utc']))
    started=clock();quota_errors=0
    def save():
        record['checked_at_utc']=engine.now();engine.save(output,record)
    def frozen():
        if engine.sha(path)!=manifest_sha:raise ValueError('Fixed active manifest changed')
        for b in manifest['branches']:engine.local_preflight(manifest,b)
    def claimed_count():
        return sum((engine.branch_state(manifest,b)/'submission.json').exists() for b in manifest['branches'])
    def finish(status):
        record.update(status=status,finished_at_utc=engine.now());save();return record
    try:
        api=engine.make_api()
        while clock()-started<max_seconds:
            frozen();ready=[];fresh=[];active_pending=0
            for branch in manifest['branches']:
                row=rows[branch['name']]
                if row['terminal']:continue
                branch_state=engine.branch_state(manifest,branch)
                try:
                    if (branch_state/'submission.json').exists():
                        claim=engine.bound_receipt(manifest,branch,'submission.json');ref=claim.get('submission_ref')
                        accepted=claim.get('status') in ACCEPTED_SUBMISSION and type(ref) is int and ref>0
                        row.update(status='submission_accepted' if accepted else 'submission_claimed_no_retry',terminal=True,reserved_cloud_slot=False,submission_ref=ref,claim_status=claim.get('status'));continue
                    if not (branch_state/'cloud.json').exists():fresh.append(branch);row['status']='waiting_launch_slot';continue
                    cloud=engine.bound_receipt(manifest,branch,'cloud.json')
                    if cloud.get('status') not in ACCEPTED_CLOUD:
                        row.update(status='cloud_claimed_no_retry',claim_status=cloud.get('status'),terminal=True,reserved_cloud_slot=True);continue
                    # This is a read of the complete source/version binding.
                    binding=engine.live_binding(manifest,branch,api=api)
                    status=binding['session_status'];row.update(cloud_status=status,consecutive_read_errors=0)
                    if binding.get('failure_message_present') or status in ('ERROR','CANCELED','CANCELLED'):
                        row.update(status='cloud_failed_no_submission',terminal=True,reserved_cloud_slot=False)
                    elif status=='COMPLETE':
                        row.update(status='ready_to_audit',reserved_cloud_slot=False);ready.append(branch)
                    else:
                        row.update(status='waiting_cloud',reserved_cloud_slot=True);active_pending+=1
                except ValueError as error:
                    row.update(status='binding_or_receipt_failed_no_submission',terminal=True,reserved_cloud_slot=True,**engine.safe_error(error))
                except Exception as error:
                    row['consecutive_read_errors']+=1
                    row.update(status='read_error_waiting',reserved_cloud_slot=True,**engine.safe_error(error))
                    if row['consecutive_read_errors']>=10:row.update(status='ten_read_errors_no_submission',terminal=True)
                    else:active_pending+=1
            record['reserved_pending_cloud_runs']=sum(r['reserved_cloud_slot'] for r in rows.values());save()
            if all(r['terminal'] for r in rows.values()):return finish('finished_all_claimed_or_failed')
            if claimed_count()>=5:return finish('five_submission_claim_limit_no_more_writes')
            try:
                limits=api.competition_get_submission_limits(engine.COMPETITION)
                allowed=limits.num_allowed_now
                if type(allowed) is not int or allowed<0:raise ValueError('Invalid allowance response')
                quota_errors=0;record['num_allowed_now']=allowed
            except Exception as error:
                quota_errors+=1;record.update(status='quota_read_error_waiting',consecutive_quota_read_errors=quota_errors,**engine.safe_error(error));save()
                if quota_errors>=10:return finish('ten_quota_read_errors_no_more_writes')
                sleeper(min(INTERVAL,max(0,max_seconds-(clock()-started))));continue
            if allowed<1:return finish('quota_exhausted_no_more_writes')
            for branch in ready:
                row=rows[branch['name']]
                try:
                    frozen()
                    if claimed_count()>=5:return finish('five_submission_claim_limit_no_more_writes')
                    if (engine.branch_state(manifest,branch)/'submission.json').exists():continue
                    row['status']='auditing_complete_cloud';save()
                    audit=engine.audit_outputs(manifest,branch,api=api)
                    if audit.get('status')!='passed':raise ValueError('Output audit did not pass')
                    frozen();row['status']='submitting_code_once';save()
                    submitted=engine.submit(manifest,branch,api=api)
                    row.update(status='submission_accepted' if submitted.get('status') in ACCEPTED_SUBMISSION else 'submission_claimed_no_retry',terminal=True,reserved_cloud_slot=False,submission_ref=submitted.get('submission_ref'),claim_status=submitted.get('status'));save()
                except Exception as error:
                    receipt=engine.branch_state(manifest,branch)/'submission.json'
                    row.update(status='submission_claimed_no_retry' if receipt.exists() else 'audit_or_submit_stopped_no_retry',terminal=True,reserved_cloud_slot=False,**engine.safe_error(error));save()
            # A prior unknown launch may still occupy a server slot. Reserve it;
            # do not use an inconclusive response as permission for another run.
            pending=sum(r['reserved_cloud_slot'] for r in rows.values())
            if not active_pending and pending>=2 and fresh:return finish('unknown_cloud_capacity_no_more_launches')
            for branch in fresh:
                if pending>=2:break
                row=rows[branch['name']]
                try:
                    frozen()
                    if claimed_count()>=5:return finish('five_submission_claim_limit_no_more_writes')
                    if api.competition_get_submission_limits(engine.COMPETITION).num_allowed_now<1:return finish('quota_exhausted_no_more_writes')
                    # The engine performs a complete owned inventory read and
                    # claims before its one push. Never call launch on a receipt.
                    if (engine.branch_state(manifest,branch)/'cloud.json').exists():continue
                    row['status']='launching_notebook_once';save()
                    launched=engine.launch(manifest,branch,api=api)
                    row.update(status='waiting_cloud' if launched.get('status') in ACCEPTED_CLOUD else 'cloud_claimed_no_retry',terminal=launched.get('status') not in ACCEPTED_CLOUD,reserved_cloud_slot=True,claim_status=launched.get('status'));pending+=1;save()
                except Exception as error:
                    row.update(status='launch_stopped_no_retry',terminal=True,reserved_cloud_slot=True,**engine.safe_error(error));pending+=1;save()
            record['reserved_pending_cloud_runs']=pending
            if all(r['terminal'] for r in rows.values()):return finish('finished_all_claimed_or_failed')
            record['status']='waiting_next_cycle';save()
            sleeper(min(INTERVAL,max(0,max_seconds-(clock()-started))))
        return finish('timeout_no_more_writes')
    except Exception as error:
        record.update(**engine.safe_error(error));return finish('stopped_no_automatic_retry')
    finally:lock.unlink(missing_ok=True)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--watch',action='store_true');p.add_argument('--max-hours',type=float,default=6);a=p.parse_args()
    if not math.isfinite(a.max_hours) or not 0<a.max_hours<=6:raise ValueError('At most six hours')
    result=run(a.manifest,a.max_hours*3600) if a.watch else plan(a.manifest)
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    for key,relative in [('TEMP','.cache/tmp'),('TMP','.cache/tmp'),('PYTHONPYCACHEPREFIX','.cache/pycache-win')]:
        target=batch.ROOT/relative;target.mkdir(parents=True,exist_ok=True);os.environ[key]=str(target)
    logging.disable(logging.CRITICAL)
    try:main()
    except Exception as error:
        print(json.dumps(dict(status='dispatcher_stopped',**batch.safe_error(error))));raise SystemExit(1)
