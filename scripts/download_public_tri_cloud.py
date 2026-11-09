"""Bounded read-only download of the reviewed private tri-model V1 small outputs."""
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse
import argparse
import hashlib
import io
import json
import logging
import os
import time

ROOT = Path(__file__).resolve().parents[1]
TARGET = 'stormseye/casmi26-public-tri-v30'
VERSION = 1
DEFAULT_OUT = ROOT/'runs/public_tri_cloud_v1_outputs_20261106'
RUN_RECEIPT = ROOT/'reports/public_tri_v30_cloud_run_20261106.json'
BINDING = ROOT/'reports/public_tri_v30_server_binding_20261106.json'
REQUIRED = ('submission.csv', 'public_neural_input_audit.json', 'public_neural_execution_audit.json')
OPTIONAL = ('e004_verification.json', 'execution_receipt.json', 'frozen_run_info.json',
    'merge_report.json', 'final_layer_report.json', 'run_manifest.json',
    'variants/consensus_report.json', 'submission_pipeline.log', 'submission_neural.log',
    'outsiders_neural.log', 'bootstrap.log')
MAX_JSON = 2 << 20
MAX_CSV = 4 << 20
MAX_TOTAL = 16 << 20


def now(): return datetime.now(timezone.utc).isoformat()
def digest(raw): return hashlib.sha256(raw).hexdigest()
def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path, record):
    path = Path(path)
    temporary = path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')
    temporary.replace(path)


def safe_error(error):
    return dict(error_type=type(error).__name__,
        http_status=getattr(getattr(error, 'response', None), 'status_code', None))


def destination_for(out, name):
    relative = PurePosixPath(name)
    if '\\' in name or relative.is_absolute() or '..' in relative.parts or ':' in name:
        raise ValueError('Unsafe output name')
    destination = (out/name).resolve()
    if not destination.is_relative_to(out):
        raise ValueError('Output path escapes destination')
    return destination


def prerequisites():
    receipt, binding = read(RUN_RECEIPT), read(BINDING)
    if receipt.get('target') != TARGET or receipt.get('version_number') != VERSION or receipt.get('status') != 'run_requested':
        raise ValueError('Accepted create/run receipt for this V1 is required')
    if (binding.get('target') != TARGET or binding.get('version') != VERSION
            or binding.get('status') != 'passed' or not binding.get('checks')
            or not all(value is True for value in binding['checks'].values())
            or binding['checks'].get('source_semantics') is not True
            or binding.get('staged_notebook_sha256') != receipt.get('notebook_sha256')):
        raise ValueError('Passing version-bound source/private/offline binding is required')
    return receipt, binding


def retry_read(call, requests):
    for attempt in range(3):
        try:
            return call()
        except requests.exceptions.RequestException as error:
            status = getattr(getattr(error, 'response', None), 'status_code', None)
            if attempt == 2 or (status is not None and status < 500 and status != 429):
                raise
            time.sleep(attempt+1)


def fetch_bounded(url, limit, requests, get=None):
    if urlparse(url).scheme != 'https' or limit <= 0:
        raise ValueError('Expected HTTPS URL and positive remaining byte budget')
    get = requests.get if get is None else get
    with get(url, stream=True, timeout=(15,45)) as response:
        response.raise_for_status()
        if urlparse(getattr(response, 'url', url)).scheme != 'https':
            raise ValueError('Output redirect did not remain HTTPS')
        length = response.headers.get('Content-Length')
        if length and not 0 <= int(length) <= limit:
            raise ValueError('Output Content-Length exceeds limit')
        chunks, size = [], 0
        for block in response.iter_content(64 << 10):
            size += len(block)
            if size > limit:
                raise ValueError('Output body exceeds limit')
            chunks.append(block)
    return b''.join(chunks)


def download(out, api=None, get=None):
    out = Path(out).resolve()
    if not out.is_relative_to(ROOT) or out == ROOT:
        raise ValueError('Output must remain inside the D: workspace')
    run, binding = prerequisites()
    if out.exists() and any(out.iterdir()):
        raise ValueError('A fresh output directory is required; preserve old evidence')
    out.mkdir(parents=True, exist_ok=True)
    lock = out/'.download.lock'
    lock.open('x').close()
    record = dict(status='downloading', target=TARGET, version=VERSION,
        version_ref=TARGET+'/1', started_at_utc=now(), read_only=True,
        notebook_sha256=run['notebook_sha256'], binding_sha256=digest(BINDING.read_bytes()),
        server_source_sha256=binding['server_source_sha256'],
        output_dir=str(out.relative_to(ROOT)), downloaded_files=[],
        required_files=list(REQUIRED), signed_urls_or_auth_headers_persisted=False,
        run_push_or_competition_submit_performed=False)
    save(out/'download_receipt.json', record)
    try:
        import requests
        from kagglesdk.kernels.types.kernels_api_service import ApiListKernelSessionOutputRequest
        if api is None:
            from kaggle_first_submission import make_api
            api = make_api()
        status = retry_read(lambda: api.kernels_status(TARGET+'/1'), requests)
        if getattr(status.status, 'name', str(status.status)).split('.')[-1] != 'COMPLETE' or status.failure_message:
            raise ValueError('V1 is not COMPLETE without failure')
        record['session_status'] = 'COMPLETE'
        files, token, pages, session_log = {}, None, 0, ''
        with api.build_kaggle_client() as client:
            while True:
                request = ApiListKernelSessionOutputRequest()
                request.user_name, request.kernel_slug = TARGET.split('/')
                request.version_label = api._kernel_version_label('1')
                request.page_size = 100
                if token: request.page_token = token
                listing = retry_read(lambda: client.kernels.kernels_api_client.list_kernel_session_output(request), requests)
                pages += 1
                if len(listing.log or '') > len(session_log): session_log = listing.log or ''
                if len(session_log.encode('utf-8')) > MAX_JSON:
                    raise ValueError('Session log exceeds limit')
                for item in listing.files or []:
                    name = item.file_name
                    if name in files: raise ValueError('Duplicate output inventory name')
                    files[name] = item
                token = listing.next_page_token
                if not token: break
                if pages >= 100: raise ValueError('Output inventory pagination limit reached')
        save(out/'output_inventory.json', dict(target=TARGET, version=VERSION, pages=pages, files=sorted(files)))
        total = 0
        for name in REQUIRED+OPTIONAL:
            if name not in files: continue
            record['current_file'] = name
            save(out/'download_receipt.json', record)
            limit = min(MAX_CSV if name == 'submission.csv' else MAX_JSON, MAX_TOTAL-total)
            raw = retry_read(lambda: fetch_bounded(files[name].url, limit, requests, get), requests)
            if name.endswith('.json'): json.loads(raw)
            else: raw.decode('utf-8-sig')
            destination = destination_for(out, name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(raw)
            total += len(raw)
            record['downloaded_files'].append(dict(name=name, path=str(destination.relative_to(ROOT)),
                bytes=len(raw), sha256=digest(raw)))
            save(out/'download_receipt.json', record)
        record.pop('current_file', None)
        record.update(status='downloaded', listed_files=len(files), pages=pages,
            total_downloaded_bytes=total, missing_required=[name for name in REQUIRED if name not in files],
            finished_at_utc=now())
        if record['missing_required']: record['status']='missing_required_outputs'
    except Exception as error:
        record.update(status='download_failed', finished_at_utc=now(), **safe_error(error))
    finally:
        save(out/'download_receipt.json', record)
        lock.unlink(missing_ok=True)
    return record


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download', action='store_true')
    parser.add_argument('--output-dir', type=Path, default=DEFAULT_OUT)
    args=parser.parse_args()
    for name, relative in [('TEMP','.cache/tmp'),('TMP','.cache/tmp'),('PYTHONPYCACHEPREFIX','.cache/pycache-win')]:
        directory=ROOT/relative;directory.mkdir(parents=True,exist_ok=True);os.environ[name]=str(directory)
    if not args.download:
        print(json.dumps(dict(mode='plan_only_no_network', target=TARGET, version=VERSION,
            output_dir=str(args.output_dir), required=list(REQUIRED), optional=list(OPTIONAL),
            max_json_bytes=MAX_JSON,max_csv_bytes=MAX_CSV,max_total_bytes=MAX_TOTAL),indent=2))
        return 0
    logging.disable(logging.CRITICAL)
    try:
        with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):record=download(args.output_dir)
        print(json.dumps({k:record.get(k) for k in ('status','target','version','listed_files',
            'total_downloaded_bytes','missing_required','current_file','error_type','http_status')},indent=2))
        return 0 if record['status']=='downloaded' else 1
    except Exception as error:
        print(json.dumps(dict(status='stopped',**safe_error(error)),indent=2));return 1


if __name__=='__main__':raise SystemExit(main())
