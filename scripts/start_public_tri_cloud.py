"""Create and run one reviewed private tri-model notebook; never submit competition code."""
from pathlib import Path
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timezone
import hashlib
import io
import json
import logging
import os

from kaggle_first_submission import make_api

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT/'submission/public_tri_cloud_20261106'
RECEIPT = ROOT/'reports/public_tri_v30_cloud_run_20261106.json'
TARGET = 'stormseye/casmi26-public-tri-v30'
EXPECTED_DATASETS = {
    'dmitriigluzdov/casmi26-attributed-v4g-reproduction-assets/9',
    'dmitriigluzdov/casmi26-fold-safe-fpnet/5',
    'dmitriigluzdov/casmi26-natural-product-knowledge-table/10',
    'dmitriigluzdov/casmi26-natural-product-panel-benchmark/10',
    'dmitriigluzdov/casmi26-pubchem-popularity-prior/13',
    'sanpier/casmi-spectrum-model-v1/1',
    'bgunshui/casmi26-scorer-v2-model/1',
    'bgunshui/casmi26-scorer-v4-model/1',
    'qwertykeypadapple/casmi26-lotus-candidates/2',
}


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(record):
    temp = RECEIPT.with_suffix('.json.tmp')
    temp.write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')
    temp.replace(RECEIPT)


def main():
    if RECEIPT.exists():
        raise RuntimeError('Cloud action already claimed: inspect/poll it; never automatically push again')
    prepared = read(STAGE/'prepare_receipt.json')
    metadata = read(STAGE/'kernel-metadata.json')
    if prepared.get('status') != 'prepared' or prepared.get('target') != TARGET:
        raise ValueError('Reviewed stage preparation receipt required')
    if sha(STAGE/'notebook.ipynb') != prepared['notebook_sha256'] or sha(STAGE/'kernel-metadata.json') != prepared['metadata_sha256']:
        raise ValueError('Reviewed notebook or metadata changed')
    if metadata['id'] != TARGET or metadata['is_private'] is not True or metadata['enable_internet'] is not False or metadata['enable_gpu'] is not True:
        raise ValueError('Target/private/offline/GPU guard failed')
    if set(metadata.get('dataset_sources', [])) != EXPECTED_DATASETS or len(metadata['dataset_sources']) != 9:
        raise ValueError('Expected exactly nine version-pinned dataset sources')
    if metadata.get('kernel_sources') or metadata.get('model_sources'):
        raise ValueError('Unexpected kernel/model source dependency')
    if metadata.get('competition_sources') != ['enveda-CASMI26-molecule-id-mass-spectra']:
        raise ValueError('Unexpected competition input')
    api = make_api()
    complete = False
    count = 0
    for page in range(1, 21):
        own = api.kernels_list(mine=True, page=page, page_size=100) or []
        refs = [getattr(item, 'ref', None) for item in own]
        if any(not isinstance(ref, str) for ref in refs):
            raise ValueError('Own-kernel inventory is incomplete')
        if TARGET.lower() in {ref.lower() for ref in refs}:
            raise ValueError('Target already exists; refusing to overwrite a notebook')
        count += len(refs)
        if len(own) < 100:
            complete = True
            break
    if not complete:
        raise ValueError('Could not establish target absence')
    record = dict(status='requesting_create_and_run', started_at_utc=now(), target=TARGET,
        expected_version=1, notebook_sha256=prepared['notebook_sha256'], metadata_sha256=prepared['metadata_sha256'],
        prepare_receipt_sha256=sha(STAGE/'prepare_receipt.json'), dataset_sources=sorted(EXPECTED_DATASETS),
        private=True, internet=False, no_run=False, timeout_seconds=32400,
        own_inventory_complete=True, own_inventory_count=count, target_previously_absent=True,
        competition_submission_performed=False, automatic_retry_allowed=False)
    with RECEIPT.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(record, indent=2)+'\n')
        stream.flush()
        os.fsync(stream.fileno())
    try:
        response = api.kernels_push(str(STAGE), timeout='32400', no_run=False)
        invalid = {name:list(getattr(response,name,None) or []) for name in (
            'invalid_tags','invalid_dataset_sources','invalid_competition_sources','invalid_kernel_sources','invalid_model_sources')}
        response_ref = str(response.ref or '').strip('/')
        accepted = (response.version_number == 1 and not response.error and not any(invalid.values())
                    and response_ref in (TARGET, 'code/'+TARGET))
        record.update(status='run_requested' if accepted else 'server_response_requires_review',
            response_ref=response.ref, response_url=response.url, version_number=response.version_number,
            response_error=response.error, invalid_sources=invalid, responded_at_utc=now())
        save(record)
        return record
    except Exception as error:
        record.update(status='request_outcome_unknown_no_retry', error_type=type(error).__name__,
            http_status=getattr(getattr(error,'response',None),'status_code',None), checked_at_utc=now())
        save(record)
        raise


if __name__ == '__main__':
    for name, relative in [('TEMP','.cache/tmp'),('TMP','.cache/tmp'),('PYTHONPYCACHEPREFIX','.cache/pycache-win')]:
        path=ROOT/relative
        path.mkdir(parents=True, exist_ok=True)
        os.environ[name]=str(path)
    logging.disable(logging.CRITICAL)
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            result=main()
        print(json.dumps(result, indent=2))
        raise SystemExit(0 if result['status']=='run_requested' else 1)
    except Exception as error:
        print(json.dumps(dict(status='stopped',error_type=type(error).__name__,
            http_status=getattr(getattr(error,'response',None),'status_code',None)), indent=2))
        raise SystemExit(1)
