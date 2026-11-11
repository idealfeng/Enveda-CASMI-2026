"""Read bounded public run logs to identify the checkpoints actually mounted."""
from pathlib import Path
import json
import logging
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from kaggle_first_submission import make_api
from kagglesdk.kernels.types.kernels_api_service import ApiGetKernelSessionLogsStreamRequest


def main():
    dest = ROOT / 'reports/public_update_20261111/ozertuu_refresh_20261111T030240Z'
    api = make_api()
    record = dict(public_read_only=True, requested_version=18)
    try:
        req = ApiGetKernelSessionLogsStreamRequest()
        req.user_name = 'ozertuu'
        req.kernel_slug = 'casmi26-dual-neural-physical-isomer'
        req.version_label = api._kernel_version_label('18')
        req.wait_for_logs_url_seconds = 1
        with api.build_kaggle_client() as client:
            response = client.kernels.kernels_api_client.get_kernel_session_logs_stream(req)
            with response:
                chunks = []
                total = 0
                for chunk in response.iter_content(65536):
                    total += len(chunk)
                    if total > 8 * 1024 * 1024:
                        raise ValueError('Public log cap exceeded')
                    chunks.append(chunk)
                raw = b''.join(chunks)
        (dest / 'public_run_logs.json').write_bytes(raw)
        record.update(status='downloaded', bytes=len(raw))
        try:
            parsed = json.loads(raw)
            entries = parsed if isinstance(parsed, list) else [parsed]
            texts = [str(e.get('data', e.get('text', ''))) for e in entries if isinstance(e, dict)]
            matches = []
            for value in texts:
                for line in value.splitlines():
                    if any(key in line for key in ['EXTRA BUNDLE', 'ENSEMBLE neural', 'Fast commit', 'Traceback']):
                        matches.append(line[:500])
            record['selected_non_sensitive_lines'] = matches
        except (ValueError, TypeError):
            record['log_format'] = 'non_json'
    except Exception as error:
        record.update(status='unavailable', error_type=type(error).__name__,
                      http_status=getattr(getattr(error, 'response', None), 'status_code', None))
    (dest / 'public_run_logs_receipt.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    for key, rel in [('TEMP', '.cache/tmp'), ('TMP', '.cache/tmp'),
                     ('PYTHONPYCACHEPREFIX', '.cache/pycache-win')]:
        os.environ[key] = str(ROOT / rel)
    logging.disable(logging.CRITICAL)
    main()
