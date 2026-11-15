"""Use the fixed batch engine with bounded recovery for transport reads only.

Never retry a cloud push or a claimed formal write. Preserve partial output
artifacts and stop for review if an interrupted download created evidence.
"""
from pathlib import Path
import argparse
import logging
import math
import os
import time

import kaggle_batch as batch
import dispatch_subset_batch_20261112 as dispatcher

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT/'submission/optimization_20261114/manifest.json'


def transport(error):
    return type(error).__name__ in ('ConnectionError', 'Timeout', 'ReadTimeout', 'ConnectTimeout')


def bounded_read(operation, safe, record, phase, sleeper=time.sleep):
    for attempt in range(1, 4):
        try:
            return operation()
        except Exception as error:
            record(phase, attempt, error)
            if not transport(error) or not safe() or attempt == 3:
                raise
            sleeper(2)


def install_read_recovery(manifest):
    state = ROOT/manifest['state_root']
    history = []

    def record(phase, attempt, error):
        history.append(dict(phase=phase, attempt=attempt, checked_at_utc=batch.now(), **batch.safe_error(error)))
        batch.save(state/'transport_read_recovery.json', dict(events=history, unknown_writes_retried=False))

    original_binding = batch.live_binding
    original_audit = batch.audit_outputs
    original_submit = batch.submit

    def live_binding(m, b, *args, **kwargs):
        return bounded_read(lambda: original_binding(m, b, *args, **kwargs), lambda: True, record, 'live_binding')

    def audit_outputs(m, b, *args, **kwargs):
        output = batch.branch_state(m, b)/'outputs'
        return bounded_read(lambda: original_audit(m, b, *args, **kwargs),
                            lambda: not output.exists(), record, 'audit_before_output_artifacts')

    def submit(m, b, *args, **kwargs):
        claim = batch.branch_state(m, b)/'submission.json'
        return bounded_read(lambda: original_submit(m, b, *args, **kwargs),
                            lambda: not claim.exists(), record, 'submit_preclaim_reads')

    batch.live_binding = live_binding
    batch.audit_outputs = audit_outputs
    batch.submit = submit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--watch', action='store_true')
    parser.add_argument('--max-hours', type=float, default=6)
    args = parser.parse_args()
    if not math.isfinite(args.max_hours) or not 0 < args.max_hours <= 6:
        raise ValueError('At most six hours')
    path, manifest = dispatcher.prepare(MANIFEST)
    if len(manifest['branches']) != 5:
        raise ValueError('Exactly five fixed new branches required')
    if not args.watch:
        return dispatcher.plan(path)
    install_read_recovery(manifest)
    return dispatcher.run(path, args.max_hours * 3600)


if __name__ == '__main__':
    import json
    for key, relative in [('TEMP', '.cache/tmp'), ('TMP', '.cache/tmp'), ('PYTHONPYCACHEPREFIX', '.cache/pycache-win')]:
        os.environ[key] = str(ROOT/relative)
    logging.disable(logging.CRITICAL)
    try:
        print(json.dumps(main()))
    except Exception as error:
        print(json.dumps(dict(status='stopped', **batch.safe_error(error))))
        raise SystemExit(1)
