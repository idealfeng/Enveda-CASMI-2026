"""Wait for one fixed private V1, audit it, then submit its code exactly once.

Plan-only unless --watch is supplied. Never creates or retries a Notebook and
never retries a competition request with an unknown outcome.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import json
import logging
import os
import time

import kaggle_batch as batch

ROOT=Path(__file__).resolve().parents[1]


def run(manifest_path,name,max_seconds=21600):
    manifest_path=batch.inside(manifest_path)
    manifest=batch.load_manifest(manifest_path)
    branch=next(b for b in manifest['branches'] if b['name']==name)
    batch.local_preflight(manifest,branch)
    state=batch.branch_state(manifest,branch)
    source_sha=batch.sha(manifest_path)
    target=batch.cloud_target(manifest,branch)
    lock=state/'ready_dispatch.lock'
    output=state/'ready_dispatch_status.json'
    record=dict(status='waiting_cloud',pid=os.getpid(),target=target,branch=name,
        manifest_sha256=source_sha,branch_sha256=batch.branch_sha(branch),
        started_at_utc=batch.now(),maximum_seconds=max_seconds,interval_seconds=45,
        submission_retries_allowed=False,notebook_push_performed=False)
    batch.claim(lock,record)
    started=time.monotonic();errors=0
    try:
        api=batch.make_api()
        while time.monotonic()-started<max_seconds:
            if batch.sha(manifest_path)!=source_sha:
                raise ValueError('Frozen active manifest changed')
            batch.local_preflight(manifest,branch)
            receipt=state/'submission.json'
            if receipt.exists():
                claimed=batch.bound_receipt(manifest,branch,'submission.json')
                record.update(status='already_claimed_no_retry',claim_status=claimed.get('status'),
                    submission_ref=claimed.get('submission_ref'),checked_at_utc=batch.now())
                batch.save(output,record)
                return record
            try:
                remote=api.kernels_status(target+'/1')
                status=remote.status.name
                record.update(cloud_status=status,checked_at_utc=batch.now(),
                    cloud_failure_message_present=bool(remote.failure_message))
                errors=0
            except Exception as error:
                errors+=1
                record.update(status='read_error_waiting',consecutive_read_errors=errors,
                    checked_at_utc=batch.now(),**batch.safe_error(error))
                batch.save(output,record)
                if errors>=10:raise RuntimeError('Ten consecutive cloud status read failures')
                time.sleep(45)
                continue
            if status=='COMPLETE' and not remote.failure_message:
                # Both functions repeat live source/dependency and quota checks.
                # submit() durably claims before the only competition write.
                record.update(status='auditing_complete_cloud')
                batch.save(output,record)
                batch.audit_outputs(manifest,branch,api=api)
                record.update(status='requesting_once')
                batch.save(output,record)
                accepted=batch.submit(manifest,branch,api=api)
                record.update(status=accepted['status'],submission_ref=accepted.get('submission_ref'),
                    checked_at_utc=batch.now(),finished_at_utc=batch.now())
                batch.save(output,record)
                return record
            if remote.failure_message or status in ('ERROR','CANCELED','CANCELLED'):
                record.update(status='cloud_failed_no_submission',finished_at_utc=batch.now())
                batch.save(output,record)
                return record
            record['status']='waiting_cloud'
            batch.save(output,record)
            time.sleep(min(45,max(0,max_seconds-(time.monotonic()-started))))
        record.update(status='timeout_no_submission',finished_at_utc=batch.now())
        batch.save(output,record)
        return record
    except Exception as error:
        record.update(status='stopped_no_automatic_retry',finished_at_utc=batch.now(),**batch.safe_error(error))
        batch.save(output,record)
        return record
    finally:
        lock.unlink(missing_ok=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--branch',required=True)
    parser.add_argument('--watch',action='store_true')
    parser.add_argument('--max-hours',type=float,default=6)
    args=parser.parse_args()
    if not 0<args.max_hours<=6:raise ValueError('Bounded waiting requires at most six hours')
    manifest=batch.load_manifest(args.manifest)
    branch=next(b for b in manifest['branches'] if b['name']==args.branch)
    batch.local_preflight(manifest,branch)
    if not args.watch:
        print(json.dumps(dict(status='plan_only_no_network',target=branch['target'],
            branch=args.branch,max_hours=args.max_hours,submissions_at_most=1)))
        return
    print(json.dumps(run(args.manifest,args.branch,args.max_hours*3600),indent=2))


if __name__=='__main__':
    for name,relative in [('TEMP','.cache/tmp'),('TMP','.cache/tmp'),('PYTHONPYCACHEPREFIX','.cache/pycache-win')]:
        path=ROOT/relative;path.mkdir(parents=True,exist_ok=True);os.environ[name]=str(path)
    logging.disable(logging.CRITICAL)
    main()
