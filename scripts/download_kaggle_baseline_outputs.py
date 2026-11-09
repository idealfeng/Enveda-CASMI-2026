"""Opt-in read-only, bounded V2 output download. Never run/push/submit."""
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
import argparse
import ast
import hashlib
import io
import json
import logging
import re
import time
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
TARGET = 'stormseye/casmi26-flex-v56-baseline'
VERSION = 2
DEFAULT_OUT = ROOT/'runs/kaggle_baseline_v2_outputs_20261105'
REQUIRED = ('submission.csv', 'e004_verification.json', 'v43_execution_receipt.json',
    'execution_receipt.json', 'frozen_run_info.json', 'run_manifest.json',
    'ice_work/ice_out.json.meta.json', 'gl_work/gl_out.json.meta.json',
    'n1_work/n1_out.json.meta.json', 'neural_submission_report.json',
    'neural_candidate_features.parquet.errors.json', 'outsider_neural_features.parquet.errors.json',
    'variants/consensus_report.json', 'spectral_parallax_report.json',
    'merge_report.json', 'final_layer_report.json', 'v43_mounted_input_hashes.json')
OPTIONAL = ('rank2_overlay.json', 'experiment_verification.json', 'experiment_audit.json',
    'submission_pipeline.log', 'submission_neural.log', 'outsiders_neural.log', 'bootstrap.log')
MAX_JSON = 2 << 20
MAX_CSV = 4 << 20
MAX_TOTAL = 16 << 20


def save(path, value):
    path = Path(path)
    temp = path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8'); temp.replace(path)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def semantic_cells(raw):
    cells = json.loads(raw)['cells']
    result = []
    for cell in cells:
        text = cell.get('source', '')
        text = ''.join(text) if isinstance(text, list) else text
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        result.append((cell['cell_type'], ast.dump(ast.parse(text), include_attributes=False)
            if cell['cell_type']=='code' else text))
    return result


def retry_read(call, requests):
    for attempt in range(3):
        try:
            return call()
        except requests.exceptions.RequestException as error:
            status = getattr(getattr(error, 'response', None), 'status_code', None)
            if attempt == 2 or (status is not None and status < 500):
                raise
            time.sleep(attempt+1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download', action='store_true', help='Explicitly enable only read/list/download calls')
    parser.add_argument('--output-dir', type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(); out = args.output_dir.resolve()
    if not out.is_relative_to(ROOT) or out==ROOT:
        parser.error('Output must be a new directory inside D: workspace')
    if not args.download:
        print(json.dumps(dict(mode='plan_only_no_network', target=TARGET, version=VERSION,
            output_dir=str(out), required=list(REQUIRED), optional=list(OPTIONAL),
            max_json_bytes=MAX_JSON, max_csv_bytes=MAX_CSV, max_total_bytes=MAX_TOTAL), indent=2)); return 0
    if out.exists() and any(out.iterdir()):
        parser.error('Fresh output directory required; use the verifier for existing downloads')
    out.mkdir(parents=True, exist_ok=True)
    lock = out/'.download.lock'; lock.open('x').close()
    receipt = dict(status='downloading', target=TARGET, version=VERSION, version_label='v2',
        started_utc=datetime.now(timezone.utc).isoformat(), read_only=True, output_dir=str(out),
        downloaded_files=[], required_files=list(REQUIRED), urls_or_auth_headers_persisted=False,
        push_run_or_competition_submit_performed=False)
    save(out/'download_receipt.json', receipt)
    try:
        logging.disable(logging.CRITICAL)
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            import requests
            from kaggle.api.kaggle_api_extended import KaggleApi
            from kagglesdk.kernels.types.kernels_api_service import ApiGetKernelRequest, ApiListKernelSessionOutputRequest
            api=KaggleApi(); api.authenticate()
            original_send=requests.sessions.Session.send
            def timed_send(session, request, **kwargs):
                kwargs['timeout']=(15,45)
                return original_send(session, request, **kwargs)
            requests.sessions.Session.send=timed_send
            try:
                status=retry_read(lambda:api.kernels_status(TARGET+'/2'), requests)
                status_name=getattr(status.status, 'name', str(status.status)).split('.')[-1]
                if status_name!='COMPLETE' or bool(getattr(status,'failure_message','')):
                    raise ValueError('Pinned V2 is not complete and healthy')
                receipt['session_status']=status_name
                with api.build_kaggle_client() as client:
                    req=ApiGetKernelRequest(); req.user_name,req.kernel_slug=TARGET.split('/'); req.version_label='v2'
                    response=retry_read(lambda:client.kernels.kernels_api_client.get_kernel(req),requests)
                    meta=response.metadata; source=response.blob.source.encode('utf8')
                    if len(source)>8<<20:raise ValueError('Oversized source response')
                    original=(ROOT/'third_party/flexonafft_evidence_gap/v56/original.ipynb').read_bytes()
                    binding=dict(target=meta.ref, version=meta.current_version_number,
                        private=meta.is_private, internet=meta.enable_internet,
                        original_sha256=digest(original), server_source_sha256=digest(source),
                        cell_semantics_equal=semantic_cells(source)==semantic_cells(original),
                        version_label_requested='v2')
                    if not (binding['target']==TARGET and binding['version']==2 and binding['private'] is True
                            and binding['internet'] is False and binding['cell_semantics_equal']
                            and binding['original_sha256']=='0ebc86ad851fe7051e592fb268756e686ee21b9ddbe90012335096a349bd2769'):
                        raise ValueError('Pinned V2/source/private/offline identity mismatch')
                    save(out/'source_binding.json',binding)
                    files={}; token=None; pages=0; log=''
                    while True:
                        request=ApiListKernelSessionOutputRequest();request.user_name,request.kernel_slug=TARGET.split('/')
                        request.version_label='v2';request.page_size=100
                        if token:request.page_token=token
                        listing=retry_read(lambda:client.kernels.kernels_api_client.list_kernel_session_output(request),requests)
                        pages+=1
                        if len(listing.log or '')>len(log):log=listing.log or ''
                        if len(log.encode('utf8'))>2<<20:raise ValueError('Oversized session log')
                        for item in listing.files or []:
                            name=item.file_name.replace('\\','/')
                            if name in files:raise ValueError('Duplicate output listing name')
                            files[name]=item
                        token=listing.next_page_token
                        if not token:break
                        if pages>=100:raise ValueError('Output pagination limit; incomplete inventory')
                save(out/'output_inventory.json',dict(target=TARGET,version=2,pages=pages,files=sorted(files)))
                markers=['Traceback (most recent call last)', 'FAILED ->', 'restored_after_error', 'NEURAL FAILED']
                log_checks=dict(log_bytes=len(log.encode('utf8')),log_sha256=digest(log.encode('utf8')),
                    failure_marker_counts={m:log.count(m) for m in markers},
                    neural_input_failure_counts=[int(x) for x in re.findall(r'NEURAL input failures kept at baseline:\s*(\d+)',log)])
                save(out/'kernel_session_log_checks.json',log_checks)
                total=0
                for name in REQUIRED+OPTIONAL:
                    if name not in files:continue
                    path=PurePosixPath(name)
                    if path.is_absolute() or '..' in path.parts or ':' in name:raise ValueError('Unsafe output path')
                    destination=(out/name).resolve()
                    if not destination.is_relative_to(out):raise ValueError('Output escapes destination')
                    limit=MAX_CSV if name=='submission.csv' else MAX_JSON
                    url=files[name].url
                    if urlparse(url).scheme!='https':raise ValueError('Expected HTTPS output URL')
                    def fetch():
                        chunks=[];size=0
                        with requests.get(url,stream=True,timeout=(15,45)) as response:
                            response.raise_for_status()
                            length=response.headers.get('Content-Length')
                            if length and int(length)>limit:raise ValueError('Output Content-Length exceeds cap')
                            for block in response.iter_content(64<<10):
                                size+=len(block)
                                if size>limit:raise ValueError('Output stream exceeds cap')
                                chunks.append(block)
                        return b''.join(chunks)
                    raw=retry_read(fetch,requests);total+=len(raw)
                    if total>MAX_TOTAL:raise ValueError('Total output download cap exceeded')
                    if name.endswith('.json'):json.loads(raw)
                    else:raw.decode('utf-8-sig')
                    destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(raw)
                    receipt['downloaded_files'].append(dict(name=name,path=str(destination.relative_to(ROOT)),bytes=len(raw),sha256=digest(raw)))
                    save(out/'download_receipt.json',receipt)
                receipt.update(status='downloaded',pages=pages,listed_files=len(files),total_downloaded_bytes=total,
                    missing_required=[name for name in REQUIRED if name not in files],finished_utc=datetime.now(timezone.utc).isoformat())
            finally:
                requests.sessions.Session.send=original_send
    except BaseException as error:
        receipt.update(status='download_failed',error_type=type(error).__name__,
            http_status=getattr(getattr(error,'response',None),'status_code',None),finished_utc=datetime.now(timezone.utc).isoformat())
    save(out/'download_receipt.json',receipt)
    lock.unlink(missing_ok=True)
    print(json.dumps({key:receipt.get(key) for key in ('status','target','version','listed_files','total_downloaded_bytes','missing_required','error_type','http_status')},indent=2))
    return 0 if receipt['status']=='downloaded' else 1


if __name__=='__main__':raise SystemExit(main())
