"""Prepare / privately create one frozen FIORA dataset; never retry an unknown write."""
from pathlib import Path
from datetime import datetime, timezone
from contextlib import redirect_stdout, redirect_stderr
import argparse
import hashlib
import io
import json
import logging
import os
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / 'submission/optimization_20261116/fiora_payload'
UPLOAD = ROOT / 'submission/optimization_20261116/fiora_dataset_upload'
STATE = ROOT / 'reports/optimization_20261116_fiora/dataset'
TARGET = 'stormseye/casmi26-fiora-tims500-1116'


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def save(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(path).with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def validate():
    manifest = read(PAYLOAD / 'asset_manifest.json')
    if manifest['model_step'] != 500 or manifest['parent_checkpoint_sha256'] != '9c899faa1c45d9a0c25588f99186f34112b25eafe3f6d955a3da34c267996252':
        raise ValueError('Expected this actual trained step500')
    if not {'state.pt', 'params.json', 'canary_queries.parquet', 'canary_submission.csv'} <= set(manifest['files']):
        raise ValueError('Complete offline bundle and real canary required')
    for name, pin in manifest['files'].items():
        p = (PAYLOAD / name).resolve()
        if not p.is_relative_to(PAYLOAD.resolve()) or p.is_symlink() or sha(p) != pin:
            raise ValueError('Payload file changed or escaped bundle')
    return manifest


def prepare():
    manifest = validate()
    if UPLOAD.exists():
        raise FileExistsError('Preserve prepared archive and metadata')
    UPLOAD.mkdir(parents=True)
    names = sorted([*manifest['files'], 'asset_manifest.json'])
    with zipfile.ZipFile(UPLOAD / 'fiora_bundle.zip', 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name in names:
            info = zipfile.ZipInfo(name, date_time=(2026, 11, 16, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, (PAYLOAD / name).read_bytes())
    metadata = dict(id=TARGET, title='CASMI26 FIORA tims500 private experiment',
                    licenses=[dict(name='other')],
                    description='Private experimental inference bundle. FIORA OS MSnLib-v7-only parent, '
                                'explicit timsTOF migration and fixed500 updates. Original source/dependency '
                                'licenses and provenance retained. No competition hidden labels. '
                                'The two public-development inference canaries have no target structures '
                                'or outcome labels attached to their queries. Not a claimed leaderboard improvement.')
    save(UPLOAD / 'dataset-metadata.json', metadata)
    result = dict(status='prepared', created_at_utc=now(), target=TARGET, private=True,
                  asset_manifest_sha256=sha(PAYLOAD / 'asset_manifest.json'),
                  archive_sha256=sha(UPLOAD / 'fiora_bundle.zip'), archive_bytes=(UPLOAD / 'fiora_bundle.zip').stat().st_size,
                  metadata_sha256=sha(UPLOAD / 'dataset-metadata.json'), files=len(names),
                  upload_dir=UPLOAD.relative_to(ROOT).as_posix(), network_write_performed=False)
    save(STATE / 'prepare.json', result)
    return result


def ready():
    result = read(STATE / 'prepare.json')
    validate()
    if result['asset_manifest_sha256'] != sha(PAYLOAD / 'asset_manifest.json') or result['archive_sha256'] != sha(UPLOAD / 'fiora_bundle.zip') or result['metadata_sha256'] != sha(UPLOAD / 'dataset-metadata.json'):
        raise ValueError('Frozen archive, manifest or metadata changed')
    return result


def upload():
    prepared = ready()
    receipt = STATE / 'create.json'
    if receipt.exists():
        raise RuntimeError('Write already claimed; status is read-only, never automatically retry')
    sys.path.insert(0, str(ROOT / 'scripts'))
    from kaggle_first_submission import make_api
    api = make_api()
    absence_evidence = {'method': 'authenticated404'}
    try:
        api.dataset_status(TARGET)
    except Exception as error:
        status_code = getattr(getattr(error, 'response', None), 'status_code', None)
        if status_code == 403:
            # Kaggle returns permission-denied for an absent private slug too.
            # Verify the authenticated owner's complete inventory; a403 alone
            # never establishes absence or authorizes a write to another owner.
            owned_refs = []
            for page in range(1, 101):
                owned = api.dataset_list(mine=True, page=page) or []
                refs = [getattr(item, 'ref', None) for item in owned]
                if any(not isinstance(ref, str) for ref in refs):
                    raise ValueError('Incomplete authenticated owned dataset inventory')
                owned_refs.extend(refs)
                if any(ref.lower() == TARGET.lower() for ref in refs):
                    raise RuntimeError('Target exists in owner inventory; refusing overwrite')
                if len(owned) < 20:
                    break
            else:
                raise ValueError('Owned dataset inventory page cap')
            absence_evidence = dict(method='absent_from_complete_authenticated_owner_inventory',
                                    status_endpoint_http=403, inventory_pages=page,
                                    owned_dataset_refs=owned_refs)
        elif status_code != 404:
            raise RuntimeError('Dataset absence not established by authenticated read') from error
    else:
        raise RuntimeError('Dataset already exists, refusing overwrite')
    record = dict(status='requesting_once', target=TARGET, private=True, requested_at_utc=now(),
                  archive_sha256=prepared['archive_sha256'], asset_manifest_sha256=prepared['asset_manifest_sha256'],
                  automatic_retry_allowed=False, absence_evidence=absence_evidence)
    with receipt.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(record, indent=2) + '\n')
        stream.flush()
        os.fsync(stream.fileno())
    try:
        # The parent API wraps creation in with_retry. For this explicit create,
        # disable that wrapper: reconcile ambiguous responses by reads instead.
        api.with_retry = lambda function: function
        response = api.dataset_create_new(str(UPLOAD), public=False, quiet=True,
                                          convert_to_csv=False, dir_mode='skip')
        normalized_ref = response.ref.strip('/')
        if normalized_ref.startswith('datasets/'):
            normalized_ref = normalized_ref[len('datasets/'):]
        accepted = not response.error and normalized_ref == TARGET
        record.update(status='create_accepted' if accepted else 'server_response_requires_review_no_retry',
                      responded_at_utc=now(), observed_ref=response.ref, observed_status=response.status,
                      error_present=bool(response.error), invalid_tags_present=bool(response.invalid_tags))
        if response.error:
            record['server_error_summary'] = str(response.error)[:600]
    except BaseException as error:
        record.update(status='request_outcome_unknown_no_retry', checked_at_utc=now(), error_type=type(error).__name__,
                      http_status=getattr(getattr(error, 'response', None), 'status_code', None))
        save(receipt, record)
        if not isinstance(error, Exception):
            raise
    save(receipt, record)
    return record


def status():
    ready()
    sys.path.insert(0, str(ROOT / 'scripts'))
    from kaggle_first_submission import make_api
    from kagglesdk.datasets.types.dataset_api_service import ApiGetDatasetRequest
    api = make_api()
    observed = json.loads(api.dataset_status(TARGET, format='json(status,current_version_number)'))
    request = ApiGetDatasetRequest()
    request.owner_slug, request.dataset_slug = TARGET.split('/')
    with api.build_kaggle_client() as client:
        dataset = client.datasets.dataset_api_client.get_dataset(request)
    record = dict(target=TARGET, checked_at_utc=now(), read_only=True, **observed,
                  is_private=getattr(dataset, 'is_private', None),
                  observed_ref=getattr(dataset, 'ref', None))
    record['ready_for_notebook'] = (record['status'] == 'ready'
                                    and record['current_version_number'] == 1
                                    and record['is_private'] is True
                                    and record['observed_ref'] == TARGET)
    save(STATE / 'status.json', record)
    claim_path = STATE / 'create.json'
    if record['ready_for_notebook'] and claim_path.is_file():
        claim_record = read(claim_path)
        prepared = read(STATE / 'prepare.json')
        if (claim_record.get('target') != TARGET
                or claim_record.get('asset_manifest_sha256') != prepared['asset_manifest_sha256']
                or claim_record.get('archive_sha256') != prepared['archive_sha256']):
            raise ValueError('Dataset creation claim differs from frozen upload')
        if claim_record.get('status') not in ('create_accepted', 'create_accepted_reconciled_by_readback'):
            preserved = STATE / 'create_server_response.json'
            if not preserved.exists():
                save(preserved, claim_record)
            claim_record.update(status='create_accepted_reconciled_by_readback',
                                reconciled_at_utc=now(), readback_status_sha256=sha(STATE / 'status.json'),
                                reconciliation_method='Authenticated ready/private/V1/owner reference readback; no additional create')
            save(claim_path, claim_record)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'upload', 'status'])
    args = parser.parse_args()
    return {'prepare': prepare, 'upload': upload, 'status': status}[args.action]()


if __name__ == '__main__':
    for key, relative in [('TEMP', '.cache/tmp'), ('TMP', '.cache/tmp'), ('PYTHONPYCACHEPREFIX', '.cache/pycache-win')]:
        p = ROOT / relative
        p.mkdir(parents=True, exist_ok=True)
        os.environ[key] = str(p)
    logging.disable(logging.CRITICAL)
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            result = main()
        print(json.dumps(result, indent=2))
        raise SystemExit(1 if result.get('status') in ('request_outcome_unknown_no_retry', 'server_response_requires_review_no_retry') else 0)
    except Exception as error:
        print(json.dumps(dict(status='stopped', error_type=type(error).__name__,
                              message=str(error)[:300]), indent=2))
        raise SystemExit(1)
