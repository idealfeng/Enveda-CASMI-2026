"""Read one accepted private tri-model Save&Run version. No run/push/submit calls."""
from pathlib import Path
from datetime import datetime, timezone
from contextlib import redirect_stdout, redirect_stderr
import hashlib
import ast
import io
import json
import logging
import os

from kaggle_first_submission import make_api

ROOT=Path(__file__).resolve().parents[1]
TARGET='stormseye/casmi26-public-tri-v30'
REPORT=ROOT/'reports/public_tri_v30_cloud_status_20261106.json'
BINDING=ROOT/'reports/public_tri_v30_server_binding_20261106.json'
LOGDIR=ROOT/'reports/public_tri_v30_cloud_logs'


def sha(raw):return hashlib.sha256(raw).hexdigest()
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def save(path,record):
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8');temp.replace(path)
def error(error):return dict(error_type=type(error).__name__,http_status=getattr(getattr(error,'response',None),'status_code',None))


def normalized_notebook(raw):
    notebook=json.loads(raw)
    for cell in notebook['cells']:
        source=cell.get('source','')
        cell['source']=''.join(source) if isinstance(source,list) else source
    return notebook


def same_notebook_contents(first,second):
    # Kaggle converts newly added source lists to strings. Preserve every other field.
    return normalized_notebook(first)==normalized_notebook(second)


def main():
    receipt=read(ROOT/'reports/public_tri_v30_cloud_run_20261106.json')
    if receipt.get('target')!=TARGET or receipt.get('status')!='run_requested' or receipt.get('version_number')!=1:
        raise ValueError('Expected accepted V1 create/run receipt')
    record=dict(checked_at_utc=datetime.now(timezone.utc).isoformat(),target=TARGET,version=1,
        read_only=True,new_run_or_submission_performed=False,version_ref=TARGET+'/1')
    api=make_api()
    if not BINDING.is_file():
        from kagglesdk.kernels.types.kernels_api_service import ApiGetKernelRequest
        request=ApiGetKernelRequest();request.user_name,request.kernel_slug=TARGET.split('/')
        request.version_label=api._kernel_version_label('1')
        with api.build_kaggle_client() as client:
            remote=client.kernels.kernels_api_client.get_kernel(request)
        meta=remote.metadata;raw=remote.blob.source.encode('utf-8')
        expected_sources=set('/'.join(x.split('/')[:2]) for x in receipt['dataset_sources'])
        observed_sources=set('/'.join(x.split('/')[:2]) for x in meta.dataset_data_sources or [])
        staged=(ROOT/'submission/public_tri_cloud_20261106/notebook.ipynb').read_bytes()
        if sha(staged)!=receipt['notebook_sha256']:raise ValueError('Locally staged notebook changed')
        before,after=normalized_notebook(staged),normalized_notebook(raw)
        code_asts_equal=len(before['cells'])==len(after['cells']) and all(
            ast.dump(ast.parse(a['source']),include_attributes=False)==ast.dump(ast.parse(b['source']),include_attributes=False)
            for a,b in zip(before['cells'],after['cells']) if a['cell_type']=='code' and b['cell_type']=='code')
        checks=dict(target=meta.ref==TARGET,version=meta.current_version_number==1,private=meta.is_private is True,
            internet_off=meta.enable_internet is False,source_semantics=same_notebook_contents(staged,raw),
            source_code_asts_equal=code_asts_equal,
            required_dataset_slugs=observed_sources==expected_sources,no_kernel_dependencies=not meta.kernel_data_sources)
        save(BINDING,dict(status='passed' if all(checks.values()) else 'failed',target=TARGET,version=1,
            checked_at_utc=record['checked_at_utc'],checks=checks,server_source_sha256=sha(raw),
            staged_notebook_sha256=sha(staged),source_raw_bytes_equal=raw==staged,
            source_semantics_method='Join source lists into strings; all other Notebook JSON fields and code ASTs must match.',
            dataset_sources=sorted(observed_sources),numeric_dataset_versions_read_back=False,
            metadata_docker_image=meta.docker_image,metadata_machine_shape=meta.machine_shape,
            runtime_device_or_model_execution_proven=False))
    binding=read(BINDING)
    if binding['status']!='passed':raise ValueError('Remote private/offline/source binding mismatch')
    record['server_source_private_offline_binding']='passed'
    try:
        status=api.kernels_status(TARGET+'/1')
        record.update(status_read_success=True,session_status=status.status.name,failure_message=status.failure_message)
    except Exception as exc:record.update(status_read_success=False,status_error=error(exc))
    try:
        log=api.kernels_logs(TARGET+'/1');raw=log.encode('utf-8')
        if len(raw)>4<<20:raise ValueError('Log size cap exceeded')
        LOGDIR.mkdir(exist_ok=True);(LOGDIR/'latest.log').write_bytes(raw)
        try:
            events=json.loads(log)
            decoded=''.join(str(e.get('data','')) for e in events) if isinstance(events,list) else log
        except json.JSONDecodeError:decoded=log
        markers=('MODEL BUNDLE','MODEL WARNING','BUNDLE FALLBACK','NEURAL input failures','LOTUS',
            'TRI-FORCE ENSEMBLE','PUBLIC_NEURAL_INPUT_AUDIT','PUBLIC_NEURAL_EXECUTION_AUDIT',
            'SUBMISSION READY','Traceback (most recent call last)','AssertionError')
        record.update(log_read_success=True,log_bytes=len(raw),log_sha256=sha(raw),
            marker_lines=[line[:700] for line in decoded.splitlines() if any(m in line for m in markers)][-30:])
    except Exception as exc:record.update(log_read_success=False,log_error=error(exc))
    save(REPORT,record)
    with (ROOT/'reports/public_tri_v30_cloud_status_history.jsonl').open('a',encoding='utf-8') as stream:
        stream.write(json.dumps(record)+'\n')
    return record


if __name__=='__main__':
    for name,relative in [('TEMP','.cache/tmp'),('TMP','.cache/tmp'),('PYTHONPYCACHEPREFIX','.cache/pycache-win')]:
        path=ROOT/relative;path.mkdir(parents=True,exist_ok=True);os.environ[name]=str(path)
    logging.disable(logging.CRITICAL)
    try:
        with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):result=main()
        print(json.dumps({k:result.get(k) for k in ('checked_at_utc','target','version','session_status','status_read_success',
            'failure_message','log_bytes','log_read_success','status_error','log_error')},indent=2))
        raise SystemExit(0 if result.get('status_read_success') else 1)
    except Exception as exc:
        print(json.dumps(dict(status='read_failed',**error(exc)),indent=2));raise SystemExit(1)
