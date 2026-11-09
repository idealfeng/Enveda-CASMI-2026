"""Check account/competition/kernel status read-only; never upload or submit."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import json
import os

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--username', required=True)
args = parser.parse_args()
out = ROOT / 'reports/kaggle_readiness_20261105.json'
report = dict(checked_at_utc=datetime.now(timezone.utc).isoformat(),
              expected_username=args.username, read_only=True,
              external_write_performed=False, submission_performed=False)


def error_record(error):
    # Do not serialize request objects, headers, credential values or raw errors.
    return dict(error_type=type(error).__name__,
                missing_module=getattr(error, 'name', None),
                http_status=getattr(getattr(error, 'response', None), 'status_code', None))


config_path = Path(os.environ.get('KAGGLE_CONFIG_DIR', str(Path.home() / '.kaggle'))) / 'kaggle.json'
try:
    username = json.loads(config_path.read_text(encoding='utf-8-sig')).get('username')
    report['local_username_matches'] = username == args.username
    if username != args.username:
        raise ValueError('Account identity differs from requested username')
    from kaggle.api.kaggle_api_extended import KaggleApi
    api = KaggleApi()
    api.authenticate()
    report['local_authentication_loaded'] = True
    try:
        submissions = api.competition_submissions('enveda-CASMI26-molecule-id-mass-spectra', page_size=20)
        report['competition_submissions'] = dict(status='read_success', returned_count=len(submissions or []),
            note='Only the first page count is recorded; submission contents are not persisted.')
    except Exception as error:
        report['competition_submissions'] = dict(status='read_failed', **error_record(error))
    try:
        kernels = api.kernels_list(mine=True, page_size=100) or []
        refs = [getattr(item, 'ref', None) for item in kernels]
        complete = len(kernels) < 100 and all(isinstance(ref, str) for ref in refs)
        target = args.username + '/casmi26-flex-v56-baseline'
        report['own_kernel_inventory'] = dict(status='read_success', returned_count=len(kernels),
            complete=complete, target_exists=target in refs if complete else 'not_established')
    except Exception as error:
        report['own_kernel_inventory'] = dict(status='read_failed', **error_record(error))
    try:
        status = api.kernels_status(args.username + '/casmi26-flex-v56-baseline')
        report['target_kernel'] = dict(status='read_success', exists=True,
            session_status=str(getattr(status, 'status', 'unknown')))
    except Exception as error:
        report['target_kernel'] = dict(status='read_failed', exists='not_established', **error_record(error))
except Exception as error:
    report['initialization'] = dict(status='failed', **error_record(error))
out.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, indent=2))
