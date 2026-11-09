"""Submit the reviewed cloud V2 once, or read its competition result. All records stay on D:."""
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import io
import json
import logging
import math
import os

ROOT = Path(__file__).resolve().parents[1]
TARGET = 'stormseye/casmi26-flex-v56-baseline'
VERSION = 2
COMPETITION = 'enveda-CASMI26-molecule-id-mass-spectra'
MESSAGE = 'CASMI26 first anchor: original Flex V56; stormseye notebook V2; 20261105'
RECEIPT = ROOT / 'reports/kaggle_first_submission_20261105.json'
RESULT = ROOT / 'reports/kaggle_first_submission_status.json'
VERIFY = ROOT / 'reports/kaggle_baseline_v2_output_verification_20261105.json'
ORIGINAL_SHA = '0ebc86ad851fe7051e592fb268756e686ee21b9ddbe90012335096a349bd2769'


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def save(path, record):
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def safe_error(error):
    return dict(error_type=type(error).__name__,
                http_status=getattr(getattr(error, 'response', None), 'status_code', None))


def local_preflight():
    run, verified = read(ROOT / 'reports/kaggle_baseline_run_20261105.json'), read(VERIFY)
    if run.get('target') != TARGET or run.get('version_number') != VERSION or run.get('status') != 'run_requested':
        raise ValueError('Expected accepted cloud V2 run receipt')
    if verified.get('target') != TARGET or verified.get('version') != VERSION or verified.get('status') != 'passed':
        raise ValueError('A passing version-bound cloud output audit is required')
    if sha((ROOT / 'submission/flex_v56_cloud_draft/notebook.ipynb').read_bytes()) != ORIGINAL_SHA:
        raise ValueError('Reviewed original notebook changed')
    return verified


def make_api():
    # requests does not automatically use Windows' system root store. Reuse the
    # D: bundle built from those already-trusted roots, without changing OS trust.
    system_ca = ROOT / '.cache/windows-system-ca-bundle.pem'
    if os.name == 'nt' and not os.environ.get('REQUESTS_CA_BUNDLE') and system_ca.is_file():
        os.environ['REQUESTS_CA_BUNDLE'] = str(system_ca)
    from kaggle.api.kaggle_api_extended import KaggleApi

    class BoundedApi(KaggleApi):
        def build_kaggle_client(self):
            client = super().build_kaggle_client()
            http = client._http_client
            http._init_session()
            original_send = http._session.send

            def send(*args, **kwargs):
                kwargs.setdefault('timeout', (15, 45))
                return original_send(*args, **kwargs)

            http._session.send = send
            return client

    config = Path(os.environ.get('KAGGLE_CONFIG_DIR', str(Path.home() / '.kaggle'))) / 'kaggle.json'
    if read(config).get('username') != 'stormseye':
        raise ValueError('Authenticated account must match stormseye')
    api = BoundedApi()
    api.authenticate()
    return api


def submit_once():
    if RECEIPT.exists():
        raise RuntimeError('A submission claim already exists; use --poll, never automatically resubmit')
    audit = local_preflight()
    api = make_api()
    live = api.kernels_status(TARGET + '/2')
    if live.status.name != 'COMPLETE' or live.failure_message:
        raise ValueError('Cloud V2 must be COMPLETE without failure')
    from kagglesdk.kernels.types.kernels_api_service import ApiGetKernelRequest
    request = ApiGetKernelRequest()
    request.user_name, request.kernel_slug = TARGET.split('/')
    request.version_label = api._kernel_version_label(str(VERSION))
    with api.build_kaggle_client() as client:
        remote = client.kernels.kernels_api_client.get_kernel(request)
    meta = remote.metadata
    if meta.ref != TARGET or not meta.is_private or meta.enable_internet:
        raise ValueError('Unexpected remote target/privacy/internet settings')
    if sha(remote.blob.source.encode('utf-8')) != ORIGINAL_SHA:
        raise ValueError('Remote V2 source does not equal reviewed original')
    existing = api.competition_submissions(COMPETITION, page_size=20) or []
    if existing:
        raise ValueError('First-submission inventory changed; review existing submissions before proceeding')
    limits = api.competition_get_submission_limits(COMPETITION)
    if limits.num_allowed_now < 1:
        raise ValueError('No competition submission allowance remains')
    record = dict(status='requesting_once', requested_at_utc=now(), target=TARGET, version=VERSION,
        competition=COMPETITION, output_file='submission.csv', description=MESSAGE,
        notebook_sha256=ORIGINAL_SHA, output_audit_sha256=sha(VERIFY.read_bytes()),
        visible_output_sha256=audit.get('submission_sha256'),
        automatic_retry_allowed=False, submits_cloud_code_version=True,
        local_diagnostic_csv_uploaded=False,
        allowance_before_request=dict(num_today=limits.num_today, num_total=limits.num_total,
                                      num_allowed_now=limits.num_allowed_now))
    # Exclusive creation claims the action before the single external write.
    with RECEIPT.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(record, indent=2) + '\n')
        stream.flush()
        os.fsync(stream.fileno())
    try:
        response = api.competition_submit_code(file_name='submission.csv', message=MESSAGE,
            competition=COMPETITION, kernel=TARGET, kernel_version=VERSION, quiet=True)
        record.update(status='accepted' if response.ref > 0 else 'server_response_requires_review',
                      submission_ref=response.ref, response_message=response.message, responded_at_utc=now())
        save(RECEIPT, record)
    except Exception as error:
        record.update(status='request_outcome_unknown_no_retry', checked_at_utc=now(), **safe_error(error))
        save(RECEIPT, record)
        raise
    return {key: record.get(key) for key in ('status', 'submission_ref', 'response_message', 'target', 'version')}


def poll():
    record = read(RECEIPT)
    if record.get('target') != TARGET or record.get('version') != VERSION or record.get('description') != MESSAGE:
        raise ValueError('Unexpected submission receipt')
    api = make_api()
    ref = record.get('submission_ref')
    if not ref:
        matches = [item for item in api.competition_submissions(COMPETITION, page_size=100) or []
                   if item.description == MESSAGE and item.file_name == 'submission.csv']
        if len(matches) != 1:
            raise RuntimeError('Submission outcome remains unestablished; no automatic retry is permitted')
        ref = matches[0].ref
        record.update(status='accepted_reconciled_by_unique_description', submission_ref=ref, reconciled_at_utc=now())
        save(RECEIPT, record)
    from kagglesdk.competitions.types.competition_api_service import ApiGetSubmissionRequest
    request = ApiGetSubmissionRequest()
    request.ref = int(ref)
    with api.build_kaggle_client() as client:
        item = client.competitions.competition_api_client.get_submission(request)
    if item.ref != int(ref) or item.description != MESSAGE:
        raise ValueError('Server submission identity mismatch')
    try:
        scored = item.status.name == 'COMPLETE' and math.isfinite(float(item.public_score))
    except (TypeError, ValueError):
        scored = False
    result = dict(checked_at_utc=now(), read_only=True, target=TARGET, version=VERSION,
        competition=COMPETITION, submission_ref=item.ref, status=item.status.name,
        public_score=item.public_score, error_description=item.error_description,
        description=item.description, file_name=item.file_name,
        submitted_at_utc=item.date.isoformat() if item.date else None,
        competition_submission_performed=True, new_submission_performed_by_poll=False,
        hidden_score_available=scored)
    save(RESULT, result)
    with (ROOT / 'reports/kaggle_first_submission_status_history.jsonl').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(result) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument('--check-local', action='store_true')
    actions.add_argument('--submit', action='store_true')
    actions.add_argument('--poll', action='store_true')
    args = parser.parse_args()
    if ROOT.drive.upper() != 'D:':
        raise ValueError('This workflow must stay on D:')
    for name, relative in [('TEMP', '.cache/tmp'), ('TMP', '.cache/tmp'),
                           ('PYTHONPYCACHEPREFIX', '.cache/pycache-win')]:
        directory = ROOT / relative
        directory.mkdir(parents=True, exist_ok=True)
        os.environ[name] = str(directory)
    logging.disable(logging.CRITICAL)
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            if args.check_local:
                audit = local_preflight()
                result = dict(status='local_preflight_passed', target=TARGET, version=VERSION,
                              submission_sha256=audit.get('submission_sha256'), external_write_performed=False)
            else:
                result = submit_once() if args.submit else poll()
        print(json.dumps(result, indent=2))
        return 1 if result.get('status') == 'server_response_requires_review' else 0
    except Exception as error:
        print(json.dumps(dict(status='stopped', **safe_error(error)), indent=2))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
