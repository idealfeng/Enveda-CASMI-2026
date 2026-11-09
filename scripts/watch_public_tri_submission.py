"""Read an existing, fixed tri-model V1 competition result for at most 12 hours."""
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

ROOT = Path(__file__).resolve().parents[1]
TARGET = 'stormseye/casmi26-public-tri-v30'
VERSION = 1
STATE = ROOT / 'reports/public_tri_v30_submission_watcher_20261106.json'
LOCK = ROOT / 'reports/public_tri_v30_submission_watcher_20261106.lock'
INTERVAL_SECONDS = 45
MAX_SECONDS = 12 * 60 * 60


def now():
    return datetime.now(timezone.utc).isoformat()


def inside(path):
    path = Path(path).resolve()
    if not path.is_relative_to(ROOT) or path == ROOT:
        raise ValueError('Watcher records must remain inside the D: workspace')
    return path


def save(path, record):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def run_watch(*, max_seconds=MAX_SECONDS, poller=None, receipt_path=None,
              state_path=STATE, lock_path=LOCK, clock=None, sleeper=None):
    """Only the injected/default read-only poll function can reach Kaggle."""
    if isinstance(max_seconds, bool) or not isinstance(max_seconds, (int, float)) or not math.isfinite(max_seconds) or not 0 < max_seconds <= MAX_SECONDS:
        raise ValueError('Monitoring duration must be positive and no more than 12 hours')
    if ROOT.drive.upper() != 'D:':
        raise ValueError('This workflow must stay on D:')
    if poller is None:
        from submit_public_tri_cloud import RECEIPT, poll
        poller = poll
        receipt_path = RECEIPT if receipt_path is None else receipt_path
    if receipt_path is None:
        raise ValueError('An accepted fixed-ref receipt is required')
    receipt_path, state_path, lock_path = map(inside, (receipt_path, state_path, lock_path))
    receipt = json.loads(receipt_path.read_text(encoding='utf-8-sig'))
    ref = receipt.get('submission_ref')
    if (receipt.get('target') != TARGET or receipt.get('version') != VERSION or receipt.get('status') != 'accepted'
            or isinstance(ref, bool) or not isinstance(ref, int) or ref <= 0):
        raise ValueError('An existing positive-ref target V1 receipt is required')
    clock = time.monotonic if clock is None else clock
    sleeper = time.sleep if sleeper is None else sleeper
    state_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    record = dict(status='monitoring', pid=os.getpid(), started_at_utc=now(), read_only=True,
                  target=TARGET, version=VERSION, submission_ref=ref,
                  poll_interval_seconds=INTERVAL_SECONDS, max_seconds=max_seconds,
                  new_run_or_submission_performed=False)
    with lock_path.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(record, indent=2) + '\n')
        stream.flush()
        os.fsync(stream.fileno())
    started = clock()
    try:
        save(state_path, record)
        while clock() - started < max_seconds:
            try:
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    result = poller()
                if (result.get('target') != TARGET or result.get('version') != VERSION
                        or result.get('submission_ref') != ref):
                    record.update(status='identity_mismatch', checked_at_utc=now(),
                                  last_error={'error_type': 'ValueError'})
                    save(state_path, record)
                    return 1, record
                status = result.get('status')
                score = result.get('public_score')
                try:
                    scored = status == 'COMPLETE' and math.isfinite(float(score))
                except (TypeError, ValueError):
                    scored = False
                record.update(checked_at_utc=now(), last_result_status=status,
                              public_score=score, public_score_available=scored, last_error=None)
                if status in ('COMPLETE', 'ERROR'):
                    record.update(status='finished', finished_at_utc=now())
                    save(state_path, record)
                    return (0 if scored else 1), record
            except Exception as error:
                record.update(checked_at_utc=now(), last_error={'error_type': type(error).__name__})
            save(state_path, record)
            remaining = max_seconds - (clock() - started)
            if remaining > 0:
                sleeper(min(INTERVAL_SECONDS, remaining))
        record.update(status='monitor_timeout', finished_at_utc=now())
        save(state_path, record)
        return 2, record
    finally:
        lock_path.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--max-hours', type=float, default=12)
    args = parser.parse_args()
    for name, relative in [('TEMP', '.cache/tmp'), ('TMP', '.cache/tmp'),
                           ('PYTHONPYCACHEPREFIX', '.cache/pycache-win')]:
        directory = ROOT / relative
        directory.mkdir(parents=True, exist_ok=True)
        os.environ[name] = str(directory)
    logging.disable(logging.CRITICAL)
    try:
        code, record = run_watch(max_seconds=args.max_hours * 60 * 60)
        print(json.dumps(record, indent=2))
        return code
    except Exception as error:
        print(json.dumps({'status': 'watcher_stopped', 'error_type': type(error).__name__}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
