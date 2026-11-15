"""Maintain a receipt-bound local submission summary and indexes; no cloud writes."""
from pathlib import Path
import argparse
import json
import logging
import math
import os
import subprocess
import sys
import time
import kaggle_batch as batch

ROOT = Path(__file__).resolve().parents[1]


def summarize(manifest):
    rows=[]
    for spec in manifest['branches']:
        state=batch.branch_state(manifest,spec)
        row=dict(branch=spec['name'],target=spec['target'],status='not_submitted',submission_ref=None)
        if (state/'cloud.json').exists():
            cloud=batch.bound_receipt(manifest,spec,'cloud.json')
            row.update(cloud_status=cloud['status'],actual_target=cloud.get('actual_target',spec['target']))
        if (state/'submission.json').exists():
            receipt=batch.bound_receipt(manifest,spec,'submission.json')
            row.update(status=receipt['status'],submission_ref=receipt.get('submission_ref'))
            if row['status'] in ('accepted','accepted_reconciled_by_unique_description'):
                if type(row['submission_ref']) is not int or row['submission_ref']<=0:
                    raise ValueError('Invalid accepted submission identity')
                batch.audited_local(manifest,spec)
                row.update(notebook_sha256=spec['notebook_sha256'],recipe_sha256=batch.sha(ROOT/spec['stage_dir']/'recipe.json'))
        rows.append(row)
    accepted=[r for r in rows if r['status'] in ('accepted','accepted_reconciled_by_unique_description')]
    if len({r['submission_ref'] for r in accepted})!=len(accepted):raise ValueError('Repeated submission reference')
    return dict(status='all_formal_submissions_accepted' if len(accepted)==len(rows) else 'awaiting_remaining_formal_submissions',
                checked_at_utc=batch.now(),accepted_count=len(accepted),planned_count=len(rows),branches=rows,
                cloud_write_performed=False,score_source='latest_status.json',new_gain_claim=False)


def run(path,hours):
    manifest=batch.load_manifest(path);pin=batch.sha(path);state=ROOT/manifest['state_root']
    lock=state/'accounting.lock';batch.claim(lock,dict(pid=os.getpid(),started_at_utc=batch.now(),manifest_sha256=pin))
    started=time.monotonic();previous=None
    try:
        while time.monotonic()-started<hours*3600:
            if batch.sha(path)!=pin:raise ValueError('Active manifest changed')
            result=summarize(manifest);refs=[r['submission_ref'] for r in result['branches']]
            if refs!=previous:
                checks=[]
                for args in [[],['--check']]:
                    proc=subprocess.run([sys.executable,str(ROOT/'scripts/refresh_project_index.py'),*args],cwd=ROOT,
                                        capture_output=True,text=True,encoding='utf-8',timeout=180)
                    checks.append(dict(args=args,returncode=proc.returncode,stdout=proc.stdout[-1000:],stderr=proc.stderr[-1000:]))
                    if proc.returncode:raise ValueError('Index refresh/check failed')
                batch.save(state/'automatic_index_refresh.json',dict(checked_at_utc=batch.now(),refs=refs,checks=checks))
                previous=refs
            result['manifest_sha256']=pin
            batch.save(state/'formal_acceptance_summary.json',result)
            if result['accepted_count']==len(manifest['branches']):return result
            time.sleep(min(45,max(0,hours*3600-(time.monotonic()-started))))
        result.update(accounting_monitor='timeout',finished_at_utc=batch.now());batch.save(state/'formal_acceptance_summary.json',result);return result
    finally:lock.unlink(missing_ok=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--watch',action='store_true');parser.add_argument('--max-hours',type=float,default=6);args=parser.parse_args()
    if not math.isfinite(args.max_hours) or not 0<args.max_hours<=12:raise ValueError('Maximum twelve hours')
    path=batch.inside(args.manifest)
    if not args.watch:return summarize(batch.load_manifest(path))
    return run(path,args.max_hours)


if __name__=='__main__':
    for k,v in [('TEMP','.cache/tmp'),('TMP','.cache/tmp'),('PYTHONPYCACHEPREFIX','.cache/pycache-win')]:os.environ[k]=str(ROOT/v)
    logging.disable(logging.CRITICAL)
    try:print(json.dumps(main()))
    except Exception as error:
        print(json.dumps(dict(status='accounting_stopped',**batch.safe_error(error))));raise SystemExit(1)
