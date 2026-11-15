"""Complete the existing N1c V1 after read-only connection failures; never push.

Retry only transport errors before any formal claim. Existing/unknown write
claims and partial audit artifacts stop this worker without resubmission.
"""
from pathlib import Path
import json
import logging
import os
import time
import kaggle_batch as batch

ROOT = Path(__file__).resolve().parents[1]


def main():
    path = ROOT/'submission/optimization_20261113/exploration_manifest.json'
    manifest = batch.load_manifest(path)
    branch = next(b for b in manifest['branches'] if b['name'] == 'spectral_network_explore')
    state = batch.branch_state(manifest, branch)
    report = dict(status='starting', started_at_utc=batch.now(), attempts=[],
                  manifest_sha256=batch.sha(path), cloud_push_performed=False,
                  branch=branch['name'], no_unknown_write_retry=True)
    destination = state/'manual_read_recovery.json'
    if (state.parent/'.dispatcher.lock').exists():
        raise ValueError('The dispatcher must finish before manual completion')
    if (state/'submission.json').exists():
        raise ValueError('A formal claim already exists; poll it instead')
    api = batch.make_api()

    def invoke(phase, operation):
        for attempt in range(1, 4):
            if (state/'submission.json').exists():
                raise ValueError('Existing formal write claim; no retry')
            try:
                result = operation()
                report['attempts'].append(dict(phase=phase, attempt=attempt, status=result.get('status')))
                batch.save(destination, report)
                return result
            except Exception as error:
                row = dict(phase=phase, attempt=attempt, checked_at_utc=batch.now(), **batch.safe_error(error))
                report['attempts'].append(row)
                batch.save(destination, report)
                transport = type(error).__name__ in ('ConnectionError', 'Timeout', 'ReadTimeout', 'ConnectTimeout')
                partial = phase == 'audit' and (state/'outputs').exists()
                if not transport or partial or (state/'submission.json').exists() or attempt == 3:
                    raise
                time.sleep(2)

    try:
        if (state/'output_audit.json').exists():
            audit = batch.audited_local(manifest, branch)
        else:
            audit = invoke('audit', lambda: batch.audit_outputs(manifest, branch, api=api))
        if audit['status'] != 'passed':
            raise ValueError('Actual cloud output audit did not pass')
        result = invoke('first_formal_submit', lambda: batch.submit(manifest, branch, api=api))
        report.update(status=result['status'], submission_ref=result.get('submission_ref'),
                      completed_at_utc=batch.now())
    except Exception as error:
        report.update(status='stopped_no_unknown_retry', checked_at_utc=batch.now(), **batch.safe_error(error))
    batch.save(destination, report)
    print(json.dumps(report))


if __name__ == '__main__':
    for key, value in [('TEMP', '.cache/tmp'), ('TMP', '.cache/tmp'), ('PYTHONPYCACHEPREFIX', '.cache/pycache-win')]:
        os.environ[key] = str(ROOT/value)
    logging.disable(logging.CRITICAL)
    main()
