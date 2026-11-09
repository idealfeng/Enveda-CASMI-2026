"""Read fixed positive refs from a bounded batch of 1–5 branches; never launch or submit."""
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
import argparse
import io
import json
import logging
import math
import os
import time

import kaggle_batch as batch

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT/'submission/aggressive_20261107/manifest.json'
INTERVAL = 45
MAX_SECONDS = 12*60*60
BASELINE = 0.479
ACCEPTED = {'accepted', 'accepted_reconciled_by_unique_description'}


def now(): return datetime.now(timezone.utc).isoformat()


def baseline_score(manifest):
    value = manifest.get('baseline_public_score', BASELINE)
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError('Manifest baseline score must be a finite MRR between 0 and 1')
    return float(value)


def snapshot(manifest, *, poller=None, terminal=None, fixed_refs=None):
    """Poll only already accepted positive refs. Missing or unknown refs cause no API call."""
    poller = batch.poll_submission if poller is None else poller
    terminal = {} if terminal is None else terminal
    fixed_refs = {} if fixed_refs is None else fixed_refs
    baseline = baseline_score(manifest)
    rows = []
    for branch in manifest['branches']:
        state = batch.branch_state(manifest, branch)
        row = dict(branch=branch['name'], target=branch['target'], actual_target=branch['target'],
            submission_ref=None, status='not_submitted', public_score=None, public_score_available=False)
        try:
            cloud = state/'cloud.json'
            if cloud.is_file(): row['actual_target'] = batch.cloud_target(manifest, branch)
            receipt = state/'submission.json'
            if receipt.is_file():
                record = batch.bound_receipt(manifest, branch, 'submission.json'); ref = record.get('submission_ref')
                if (record.get('status') not in ACCEPTED or type(ref) is not int or ref <= 0):
                    row.update(status='awaiting_submission_identity', claim_status=record.get('status'))
                else:
                    if (record.get('description') != branch['description'] or record.get('competition') != batch.COMPETITION
                            or record.get('output_file') != 'submission.csv'):
                        raise ValueError('Accepted submission receipt identity changed')
                    if branch['name'] in fixed_refs and fixed_refs[branch['name']] != ref:
                        raise ValueError('Established positive submission ref changed')
                    fixed_refs[branch['name']] = ref; row['submission_ref'] = ref
                    if branch['name'] in terminal:
                        row = terminal[branch['name']].copy()
                    else:
                        result = poller(manifest, branch)
                        if (result.get('submission_ref') != ref or result.get('target') != branch['target']
                                or result.get('version') != 1 or result.get('actual_target', branch['target']) != row['actual_target']):
                            raise ValueError('Readback result identity changed')
                        score = result.get('public_score')
                        try: available = result.get('status') == 'COMPLETE' and math.isfinite(float(score))
                        except (TypeError, ValueError): available = False
                        row.update(status=result.get('status'), public_score=float(score) if available else None,
                            public_score_available=available, checked_at_utc=result.get('checked_at_utc'),
                            error_description_present=bool(result.get('error_description_present')))
                        if row['status'] in ('COMPLETE', 'ERROR'): terminal[branch['name']] = row.copy()
        except Exception as error:
            row.update(status='READ_ERROR', error_type=type(error).__name__)
        rows.append(row)
    scored = [row for row in rows if row['public_score_available']]
    best = max(scored, key=lambda row: row['public_score']) if scored else None
    return dict(checked_at_utc=now(), baseline_public_score=baseline, branches=rows,
        best_this_batch=None if best is None else {k:best[k] for k in ('branch','actual_target','submission_ref','public_score')},
        best_overall_public_score=max([baseline]+[row['public_score'] for row in scored]),
        all_branches_terminal=all(row['status'] in ('COMPLETE', 'ERROR') for row in rows),
        read_only=True, new_run_or_submission_performed=False)


def run_watch(manifest_path=MANIFEST, *, max_seconds=MAX_SECONDS, poller=None, clock=None, sleeper=None):
    if type(max_seconds) not in (int,float) or not math.isfinite(max_seconds) or not 0 < max_seconds <= MAX_SECONDS:
        raise ValueError('Duration must be positive and at most 12 hours')
    manifest_path = batch.inside(manifest_path); manifest = batch.load_manifest(manifest_path)
    if not 1 <= len(manifest['branches']) <= 5: raise ValueError('This watcher requires a fixed batch of 1–5 branches')
    baseline_score(manifest)
    manifest_sha = batch.sha(manifest_path); state = batch.inside(ROOT/manifest['state_root'])
    state.mkdir(parents=True, exist_ok=True); lock = state/'watcher.lock'; output = state/'latest_status.json'
    clock = time.monotonic if clock is None else clock; sleeper = time.sleep if sleeper is None else sleeper
    record = dict(status='monitoring', pid=os.getpid(), started_at_utc=now(), manifest_sha256=manifest_sha,
        max_seconds=max_seconds, poll_interval_seconds=INTERVAL, read_only=True, new_run_or_submission_performed=False)
    batch.claim(lock, record); started = clock(); terminal = {}; fixed_refs = {}
    try:
        while clock()-started < max_seconds:
            if batch.sha(manifest_path) != manifest_sha:
                record.update(status='manifest_changed', checked_at_utc=now(), error_type='ValueError')
                batch.save(output, record); return 1, record
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                result = snapshot(manifest, poller=poller, terminal=terminal, fixed_refs=fixed_refs)
            record.update(result)
            if result['all_branches_terminal']:
                record.update(status='finished', finished_at_utc=now()); batch.save(output, record); return 0, record
            batch.save(output, record)
            remaining = max_seconds-(clock()-started)
            if remaining > 0: sleeper(min(INTERVAL, remaining))
        record.update(status='monitor_timeout', finished_at_utc=now()); batch.save(output, record); return 2, record
    finally:
        lock.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=MANIFEST)
    parser.add_argument('--watch', action='store_true'); parser.add_argument('--max-hours', type=float, default=12)
    args = parser.parse_args()
    if not args.watch:
        manifest = batch.load_manifest(args.manifest)
        print(json.dumps(dict(status='plan_only_no_network', manifest=str(args.manifest),
            branches=[branch['name'] for branch in manifest['branches']], baseline_public_score=baseline_score(manifest),
            poll_interval_seconds=INTERVAL, maximum_hours=12), indent=2)); return 0
    code, result = run_watch(args.manifest, max_seconds=args.max_hours*3600)
    print(json.dumps(result, indent=2)); return code


if __name__ == '__main__':
    for name, relative in [('TEMP','.cache/tmp'),('TMP','.cache/tmp'),('PYTHONPYCACHEPREFIX','.cache/pycache-win')]:
        path = ROOT/relative; path.mkdir(parents=True, exist_ok=True); os.environ[name] = str(path)
    logging.disable(logging.CRITICAL)
    try: raise SystemExit(main())
    except Exception as error:
        print(json.dumps(dict(status='watcher_stopped', error_type=type(error).__name__))); raise SystemExit(1)
