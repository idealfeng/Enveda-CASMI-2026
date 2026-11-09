"""Read only the already-requested V2 session status/logs; never save/run/submit."""
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import io
import json
import logging
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
TARGET = 'stormseye/casmi26-flex-v56-baseline'
VERSION = 2
REPORT = ROOT / 'reports/kaggle_baseline_v2_status.json'
HISTORY = ROOT / 'reports/kaggle_baseline_v2_status_history.jsonl'
LOGS = ROOT / 'reports/kaggle_baseline_v2_logs'
MAX_LOG_BYTES = 4 * 1024 * 1024
sys.dont_write_bytecode = True
for name, path in {
    'TEMP': ROOT / '.cache/tmp', 'TMP': ROOT / '.cache/tmp',
    'PYTHONPYCACHEPREFIX': ROOT / '.cache/pycache-windows',
}.items():
    path.mkdir(parents=True, exist_ok=True)
    os.environ[name] = str(path)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def error_fields(error):
    return {'error_type': type(error).__name__,
            'http_status': getattr(getattr(error, 'response', None), 'status_code', None)}


def save(record):
    temporary = REPORT.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    temporary.replace(REPORT)
    with HISTORY.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(record, separators=(',', ':')) + '\n')


def main():
    requested = json.loads((ROOT / 'reports/kaggle_baseline_run_20261105.json').read_text())
    if (requested.get('status') != 'run_requested' or requested.get('target') != TARGET
            or requested.get('version_number') != VERSION):
        raise RuntimeError('An accepted V2 Save&Run receipt is required before polling')
    previous = json.loads(REPORT.read_text()) if REPORT.is_file() else {}
    now = datetime.now(timezone.utc)
    record = {'checked_at_utc': now.isoformat(), 'target': TARGET, 'version': VERSION,
              'requested_kernel_ref': TARGET + '/2', 'read_only': True,
              'save_run_submit_or_restart_performed': False,
              'accepted_save_request_utc': requested['finished_request_utc'],
              'execution_kind': 'Private Save&Run against public visible inputs; no competition hidden rerun requested.',
              'last_run_time_used_as_execution_evidence': False,
              'credential_values_headers_and_signed_urls_persisted': False}
    logging.disable(logging.CRITICAL)
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            from kaggle.api.kaggle_api_extended import KaggleApi

            class BoundedReadApi(KaggleApi):
                def build_kaggle_client(self):
                    client = super().build_kaggle_client()
                    http = client._http_client
                    http._init_session()
                    original_send = http._session.send

                    def send_once(*args, **kwargs):
                        kwargs.setdefault('timeout', (5, 15))
                        return original_send(*args, **kwargs)

                    http._session.send = send_once
                    return client

            api = BoundedReadApi()
            api.authenticate()
            try:
                status = api.kernels_status(TARGET + '/2')
                record['session_status'] = getattr(status.status, 'name', str(status.status))
                record['failure_message'] = status.failure_message
                record['status_read_success'] = True
            except Exception as error:
                record['status_read_success'] = False
                record['status_read_error'] = error_fields(error)
            try:
                log = api.kernels_logs(TARGET + '/2')
                raw = log.encode('utf-8')
                record['log_read_success'] = True
                record['log_bytes'] = len(raw)
                record['log_sha256'] = digest(raw)
                record['new_log_content'] = record['log_sha256'] != previous.get('log_sha256')
                LOGS.mkdir(exist_ok=True)
                if len(raw) <= MAX_LOG_BYTES:
                    latest = LOGS / 'latest.log'
                    latest.write_bytes(raw)
                    if raw and record['new_log_content']:
                        snapshot = LOGS / (now.strftime('%Y%m%dT%H%M%S%fZ') + '.log')
                        snapshot.write_bytes(raw)
                        record['new_log_snapshot'] = str(snapshot.relative_to(ROOT))
                    record['full_log_saved'] = True
                    record['latest_log_path'] = str(latest.relative_to(ROOT))
                else:
                    record['full_log_saved'] = False
                    record['log_limit_exceeded_bytes'] = MAX_LOG_BYTES
                patterns = {
                    'device_mentions': ('Tesla T4', 'NVIDIA T4', 'GPU', 'gpu_name'),
                    'manifest_mentions': ('64 files match MANIFEST.json', 'MODEL_PINS', 'model pins', 'model_pins'),
                    'execution_mode_mentions': ('RERUN ', 'SMOKE', 'processed_molecules', 'placeholder_fill_rows'),
                    'stage_mentions': ('Asset inventory', 'Engine 2', 'PubChem channel', 'Engine 1',
                                       'Public 0.465 pipeline', 'Neural scoring', 'Final pass',
                                       'submission.csv', 'PIPELINE CELL'),
                    'error_mentions': ('Traceback (most recent call last)', 'AssertionError',
                                       'RuntimeError', 'ModuleNotFoundError', 'CellExecutionError'),
                }
                lines = log.splitlines()
                record['log_markers'] = {name: [line[:500] for line in lines if any(p in line for p in tokens)][-25:]
                                         for name, tokens in patterns.items()}
            except Exception as error:
                record['log_read_success'] = False
                record['log_read_error'] = error_fields(error)
    except Exception as error:
        record['client_initialization_error'] = error_fields(error)
    record['state_changed'] = record.get('session_status') != previous.get('session_status')
    record['runtime_hardware_offline_and_mount_versions_verified'] = False
    record['verification_note'] = ('Status is queried explicitly for V2. Log mentions are observations, not proof '
        'of hardware/offline/mounted asset versions until the actual runtime report is audited. '
        'Visible-mode twelve predictions plus 388 CCO rows, if observed, are not hidden400 inference.')
    save(record)
    print(json.dumps({key: record.get(key) for key in (
        'checked_at_utc', 'target', 'version', 'session_status', 'state_changed',
        'status_read_success', 'log_read_success', 'log_bytes', 'new_log_content',
        'status_read_error', 'log_read_error', 'client_initialization_error')}, indent=2))
    return 0 if record.get('status_read_success') else 1


if __name__ == '__main__':
    raise SystemExit(main())
