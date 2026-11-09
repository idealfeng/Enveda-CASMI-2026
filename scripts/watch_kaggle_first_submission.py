"""Read the existing first submission until scored/error; never create or retry a submission."""
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
import io
import json
import logging
import os
import sys
import time

import kaggle_first_submission as submission

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / 'reports/kaggle_first_submission_watcher.json'
MAX_SECONDS = 12 * 60 * 60


def main():
    if ROOT.drive.upper() != 'D:' or not submission.RECEIPT.is_file():
        raise RuntimeError('An existing D: submission receipt is required')
    record = dict(status='monitoring', pid=os.getpid(), started_at_utc=submission.now(),
                  read_only=True, new_run_or_submission_allowed=False,
                  poll_interval_seconds=45, max_seconds=MAX_SECONDS)
    # Reserve one watcher; an interrupted watcher is inspected by PID before replacement.
    with STATE.open('x', encoding='utf-8') as stream:
        json.dump(record, stream, indent=2)
    logging.disable(logging.CRITICAL)
    started = time.monotonic()
    while time.monotonic() - started < MAX_SECONDS:
        try:
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                result = submission.poll()
            record.update(checked_at_utc=submission.now(), submission_ref=result['submission_ref'],
                          last_submission_status=result['status'], public_score=result['public_score'],
                          hidden_score_available=result['hidden_score_available'], last_error=None)
            if result['status'] in ('COMPLETE', 'ERROR'):
                record.update(status='finished', finished_at_utc=submission.now())
                submission.save(STATE, record)
                print(json.dumps(record), flush=True)
                return 0 if result['hidden_score_available'] else 1
        except Exception as error:
            record.update(checked_at_utc=submission.now(), last_error=submission.safe_error(error))
        submission.save(STATE, record)
        time.sleep(45)
    record.update(status='monitor_timeout', finished_at_utc=submission.now())
    submission.save(STATE, record)
    return 2


if __name__ == '__main__':
    sys.dont_write_bytecode = True
    for name, relative in [('TEMP', '.cache/tmp'), ('TMP', '.cache/tmp'),
                           ('PYTHONPYCACHEPREFIX', '.cache/pycache-win')]:
        directory = ROOT / relative
        directory.mkdir(parents=True, exist_ok=True)
        os.environ[name] = str(directory)
    raise SystemExit(main())
