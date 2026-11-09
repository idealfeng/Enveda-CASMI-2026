"""Start one reviewed private offline V2; no competition submission is made."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / 'submission/flex_v56_cloud_draft'
RECEIPT = ROOT / 'reports/kaggle_baseline_run_20261105.json'
TARGET = 'stormseye/casmi26-flex-v56-baseline'


def sha(data): return hashlib.sha256(data).hexdigest()
def save(record): RECEIPT.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')


if RECEIPT.exists():
    raise RuntimeError('Run request already recorded; inspect its version/status instead of pushing again')
created = json.loads((ROOT / 'reports/kaggle_private_draft_20261105.json').read_text())
metadata = json.loads((STAGE / 'kernel-metadata.json').read_text())
raw = (STAGE / 'notebook.ipynb').read_bytes()
if created['status'] != 'created' or created['target'] != TARGET or created['version_number'] != 1:
    raise ValueError('Expected newly created private V1 required')
if sha(raw) != created['notebook_sha256'] or sha((STAGE/'kernel-metadata.json').read_bytes()) != created['metadata_sha256']:
    raise ValueError('Reviewed cloud staging changed')
if metadata['id'] != TARGET or metadata['is_private'] is not True or metadata['enable_internet'] is not False:
    raise ValueError('Account/private/offline guard failed')
from kaggle.api.kaggle_api_extended import KaggleApi
from kagglesdk.kernels.types.kernels_api_service import ApiGetKernelRequest
api = KaggleApi(); api.authenticate()
with api.build_kaggle_client() as client:
    request = ApiGetKernelRequest()
    request.user_name = 'stormseye'; request.kernel_slug = 'casmi26-flex-v56-baseline'
    current = client.kernels.kernels_api_client.get_kernel(request)
meta = current.metadata
if meta.current_version_number != 1 or meta.ref != TARGET or not meta.is_private or meta.enable_internet:
    raise ValueError('Remote draft changed; refusing to overwrite or run an unexpected version')
if sha(current.blob.source.encode('utf-8')) != sha(raw):
    raise ValueError('Remote source differs from reviewed original')
record = dict(status='requesting_save_and_run', started_utc=datetime.now(timezone.utc).isoformat(),
    target=TARGET, expected_version=2, previous_version=1, private=True, internet=False,
    session_timeout_seconds=32400, notebook_sha256=sha(raw),
    metadata_sha256=created['metadata_sha256'], required_dataset_versions=created['required_dataset_versions'],
    competition_submission_performed=False, automatic_retry_allowed=False)
save(record)
try:
    response = api.kernels_push(str(STAGE), timeout='32400', no_run=False)
    invalid = {name: list(getattr(response, name, None) or []) for name in (
        'invalid_tags', 'invalid_dataset_sources', 'invalid_competition_sources',
        'invalid_kernel_sources', 'invalid_model_sources')}
    version = response.version_number
    good = not response.error and not any(invalid.values()) and version == 2
    record.update(status='run_requested' if good else 'server_response_requires_review',
        response_ref=response.ref, response_url=response.url, version_number=version,
        response_error=response.error, invalid_sources=invalid,
        finished_request_utc=datetime.now(timezone.utc).isoformat())
    save(record)
    if good:
        try:
            session = api.kernels_status(TARGET + '/2')
            value = session.status
            record['initial_session_status'] = getattr(value, 'name', str(value))
            record['initial_failure_message'] = session.failure_message
        except Exception as error:
            record['initial_status_read_error'] = type(error).__name__
        save(record)
    print(json.dumps(record, indent=2))
except Exception as error:
    record.update(status='request_outcome_unknown_no_retry', error_type=type(error).__name__,
        http_status=getattr(getattr(error, 'response', None), 'status_code', None))
    save(record)
    print(json.dumps(record, indent=2))
    raise SystemExit(1)
