"""Create one new private offline quick-save draft; never run or submit it."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / 'submission/flex_v56_review'
STAGE = ROOT / 'submission/flex_v56_cloud_draft'
RECEIPT = ROOT / 'reports/kaggle_private_draft_20261105.json'
TARGET = 'stormseye/casmi26-flex-v56-baseline'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def save(record):
    RECEIPT.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')


if RECEIPT.exists() and json.loads(RECEIPT.read_text()).get('status') == 'created':
    raise RuntimeError('The draft was already created; do not create another version implicitly')
prepared = json.loads((REVIEW / 'preparation_report.json').read_text())
raw = (REVIEW / 'notebook.ipynb').read_bytes()
if sha(raw) != prepared['notebook_sha256'] or not prepared['original_notebook_unchanged']:
    raise ValueError('Notebook differs from the reviewed original V56')
if not all(prepared[key] == 447 for key in ('dataset_files', 'local_files_present', 'files_with_recorded_sha256', 'files_with_expected_size')):
    raise ValueError('Local asset review is incomplete')
metadata = json.loads((REVIEW / 'kernel-metadata.json').read_text())
if metadata['id'] != TARGET or metadata['is_private'] is not True or metadata['enable_internet'] is not False:
    raise ValueError('Expected account/private/offline metadata required')
plan = json.loads((ROOT / 'third_party/flexonafft_evidence_gap/minimum_download_plan.json').read_text())
versions = {}
for entry in plan['files']:
    previous = versions.setdefault(entry['dataset'], entry['version'])
    if previous != entry['version']:
        raise ValueError('Multiple versions of one required source')
# Exactly the six required inputs exercised by the complete local run. The two
# optional upstream attachments were never loaded or downloaded as payloads.
metadata['dataset_sources'] = [f'{ref}/{versions[ref]}' for ref in metadata['dataset_sources'] if ref in versions]
if len(metadata['dataset_sources']) != len(versions):
    raise ValueError('Required attachment list is incomplete')
STAGE.mkdir(exist_ok=True)
(STAGE / 'notebook.ipynb').write_bytes(raw)
(STAGE / 'kernel-metadata.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
record = dict(status='prepared', started_utc=datetime.now(timezone.utc).isoformat(),
    target=TARGET, private=True, internet=False, quick_save=True, execution_requested=False,
    submission_performed=False, notebook_sha256=sha(raw),
    metadata_sha256=sha((STAGE / 'kernel-metadata.json').read_bytes()),
    required_dataset_versions=versions, optional_unused_attachments_omitted=True,
    docker_image_server_acceptance_verified=False, server_attachment_versions_verified=False)
save(record)
try:
    config = Path(os.environ.get('KAGGLE_CONFIG_DIR', str(Path.home() / '.kaggle'))) / 'kaggle.json'
    if json.loads(config.read_text(encoding='utf-8-sig')).get('username') != 'stormseye':
        raise ValueError('Account configuration differs from requested owner')
    from kaggle.api.kaggle_api_extended import KaggleApi
    api = KaggleApi(); api.authenticate()
    own = api.kernels_list(mine=True, page_size=100) or []
    refs = [getattr(item, 'ref', None) for item in own]
    if len(own) >= 100 or not all(isinstance(ref, str) for ref in refs):
        raise ValueError('Complete existing-kernel inventory required before creation')
    if TARGET in refs:
        raise ValueError('Target already exists; refusing to overwrite an existing Notebook')
    record.update(status='requesting_private_quicksave', target_absent_verified=True)
    save(record)
    response = api.kernels_push(str(STAGE), no_run=True)
    response_error = getattr(response, 'error', None)
    record.update(status='server_rejected' if response_error else 'created',
        response_ref=getattr(response, 'ref', None), response_url=getattr(response, 'url', None),
        version_number=getattr(response, 'version_number', None), response_error=response_error,
        finished_utc=datetime.now(timezone.utc).isoformat())
    save(record)
    print(json.dumps(record, indent=2))
except Exception as error:
    record.update(status='request_failed', error_type=type(error).__name__,
        http_status=getattr(getattr(error, 'response', None), 'status_code', None),
        finished_utc=datetime.now(timezone.utc).isoformat())
    save(record)
    print(json.dumps(record, indent=2))
    raise SystemExit(1)
