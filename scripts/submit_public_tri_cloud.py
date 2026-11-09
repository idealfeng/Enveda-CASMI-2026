"""Submit the audited private tri-model V1 exactly once, or read its fixed result."""
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
import tempfile

from kaggle_first_submission import make_api
from poll_public_tri_cloud import same_notebook_contents

ROOT = Path(__file__).resolve().parents[1]
TARGET = 'stormseye/casmi26-public-tri-v30'
VERSION = 1
COMPETITION = 'enveda-CASMI26-molecule-id-mass-spectra'
MESSAGE = 'CASMI26 public tri V30 audited reproduction 20261106 V1'
RUN = ROOT/'reports/public_tri_v30_cloud_run_20261106.json'
BINDING = ROOT/'reports/public_tri_v30_server_binding_20261106.json'
VERIFY = ROOT/'reports/public_tri_v30_output_verification_20261106.json'
STAGED = ROOT/'submission/public_tri_cloud_20261106/notebook.ipynb'
RECEIPT = ROOT/'reports/public_tri_v30_submission_20261106.json'
RESULT = ROOT/'reports/public_tri_v30_submission_status_20261106.json'
HISTORY = ROOT/'reports/public_tri_v30_submission_status_history_20261106.jsonl'
REQUIRED_BINDING_CHECKS = {'target','version','private','internet_off','source_semantics',
    'source_code_asts_equal','required_dataset_slugs','no_kernel_dependencies'}
REQUIRED_AUDIT_CHECKS = {'staged_notebook_hash_bound','server_source_observation_bound',
    'server_cell_semantics_bound','private_offline_source_binding_passed','binding_receipt_hash',
    'all_downloaded_hashes_match','both_runtime_audits_passed','runtime_required_checks_present',
    'all_runtime_checks_true','three_distinct_actual_models','combined_score_values_exact',
    'csv_400_rows','csv_matches_official_sample_id_order','runtime_scope_counts',
    'official_rdkit','candidate_count_1_to_25','all_candidates_have_metric_identity',
    'submission_runtime_sha_bound','submission_runtime_rows_and_bytes','csv_bytes_unchanged_by_verifier'}


def now():return datetime.now(timezone.utc).isoformat()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def sha(raw):return hashlib.sha256(raw).hexdigest()
def sha_file(path):return sha(Path(path).read_bytes())
def safe_error(error):
    return dict(error_type=type(error).__name__,
        http_status=getattr(getattr(error,'response',None),'status_code',None))


def inside(path):
    path=Path(path).resolve()
    if not path.is_relative_to(ROOT) or path==ROOT:
        raise ValueError('All workflow paths must stay inside the D: workspace')
    return path


def save(path,record):
    path=inside(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,
                prefix=path.name+'.',suffix='.tmp',delete=False) as stream:
            temporary=Path(stream.name)
            stream.write(json.dumps(record,indent=2)+'\n');stream.flush();os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        if temporary:temporary.unlink(missing_ok=True)


def all_true(record,required):
    return isinstance(record,dict) and required<=set(record) and bool(record) and all(v is True for v in record.values())


def source_slugs(items):
    slugs=set()
    for item in items or []:
        if not isinstance(item,str) or len(item.split('/'))<2:
            raise ValueError('Unexpected dataset source format')
        slug='/'.join(item.split('/')[:2])
        if ':' in slug or '\\' in slug or any(part in ('','..','.') for part in slug.split('/')):
            raise ValueError('Unexpected dataset source slug')
        slugs.add(slug)
    if not slugs:raise ValueError('No reviewed dataset sources')
    return slugs


def local_preflight():
    run,binding,audit=read(RUN),read(BINDING),read(VERIFY)
    if (run.get('status')!='run_requested' or run.get('target')!=TARGET
            or run.get('version_number')!=VERSION):
        raise ValueError('Expected accepted cloud V1 run receipt')
    if (audit.get('status')!='passed' or audit.get('target')!=TARGET or audit.get('version')!=VERSION
            or not all_true(audit.get('checks'),REQUIRED_AUDIT_CHECKS)):
        raise ValueError('A passing complete version-bound output audit is required')
    active=audit.get('active_ids',[])
    if (audit.get('is_full_run') is not False or audit.get('processed_molecules')!=12
            or audit.get('input_molecules')!=400 or audit.get('submission_rows')!=400
            or audit.get('placeholder_rows')!=388 or len(active)!=12 or len(set(active))!=12):
        raise ValueError('This private V1 audit must declare its actual 12-of-400 visible scope')
    if (binding.get('status')!='passed' or binding.get('target')!=TARGET or binding.get('version')!=VERSION
            or not all_true(binding.get('checks'),REQUIRED_BINDING_CHECKS)):
        raise ValueError('A passing private/offline/semantic source binding is required')
    staged=STAGED.read_bytes()
    if not (sha(staged)==run.get('notebook_sha256')==audit.get('notebook_sha256')==binding.get('staged_notebook_sha256')):
        raise ValueError('Staged source does not match the accepted and audited version')
    if source_slugs(run.get('dataset_sources'))!=source_slugs(binding.get('dataset_sources')):
        raise ValueError('Dataset sources changed between reviewed receipts')
    relative=audit.get('downloaded_output_directory')
    if not isinstance(relative,str):raise ValueError('Missing audited output directory')
    output_dir=inside(ROOT/relative)
    csv_path=inside(output_dir/'submission.csv')
    csv_hash=sha_file(csv_path)
    if csv_hash!=audit.get('submission_sha256'):
        raise ValueError('Audited visible CSV has changed')
    download=read(output_dir/'download_receipt.json')
    if (download.get('status')!='downloaded' or download.get('target')!=TARGET
            or download.get('version')!=VERSION or download.get('session_status')!='COMPLETE'
            or download.get('missing_required') or download.get('binding_sha256')!=sha_file(BINDING)
            or download.get('notebook_sha256')!=run['notebook_sha256']
            or download.get('server_source_sha256')!=binding.get('server_source_sha256')):
        raise ValueError('Downloaded outputs no longer match source binding')
    files=download.get('downloaded_files',[])
    names=[item.get('name') for item in files]
    if len(names)!=len(set(names)) or not {'submission.csv','public_neural_input_audit.json','public_neural_execution_audit.json'}<=set(names):
        raise ValueError('Required downloaded artifact receipts are missing or repeated')
    for item in files:
        path=inside(ROOT/item['path'])
        expected=inside(output_dir/item['name'])
        if not expected.is_relative_to(output_dir) or path!=expected or sha_file(path)!=item['sha256'] or path.stat().st_size!=item['bytes']:
            raise ValueError('A downloaded audited artifact changed')
    return dict(audit=audit,run=run,binding=binding,staged=staged,
        output_audit_sha256=sha_file(VERIFY),binding_sha256=sha_file(BINDING),
        visible_output_sha256=csv_hash)


def list_submissions(api):
    from kagglesdk.competitions.types.competition_api_service import ApiListSubmissionsRequest
    items=[];tokens=set();token=''
    with api.build_kaggle_client() as client:
        for page in range(100):
            request=ApiListSubmissionsRequest();request.competition_name=COMPETITION;request.page_size=100
            if token:request.page_token=token
            response=client.competitions.competition_api_client.list_submissions(request)
            items.extend(response.submissions or [])
            token=response.next_page_token or ''
            if not token:return items
            if token in tokens:raise ValueError('Submission pagination token repeated')
            tokens.add(token)
    raise ValueError('Submission inventory pagination cap reached')


def live_preflight(api,local):
    live=api.kernels_status(TARGET+'/1')
    if live.status.name!='COMPLETE' or live.failure_message:
        raise ValueError('Cloud V1 must be COMPLETE without failure')
    from kagglesdk.kernels.types.kernels_api_service import ApiGetKernelRequest
    request=ApiGetKernelRequest();request.user_name,request.kernel_slug=TARGET.split('/')
    request.version_label=api._kernel_version_label('1')
    with api.build_kaggle_client() as client:
        remote=client.kernels.kernels_api_client.get_kernel(request)
    meta=remote.metadata
    if (meta.ref!=TARGET or meta.current_version_number!=VERSION
            or meta.is_private is not True or meta.enable_internet is not False):
        raise ValueError('Unexpected live target/version/privacy/internet settings')
    remote_raw=remote.blob.source.encode('utf-8')
    if not same_notebook_contents(local['staged'],remote_raw):
        raise ValueError('Live V1 source differs from the reviewed Notebook contents')
    expected=source_slugs(local['run']['dataset_sources'])
    if source_slugs(meta.dataset_data_sources)!=expected or meta.kernel_data_sources:
        raise ValueError('Live data or kernel dependencies changed')
    existing=list_submissions(api)
    if any(item.description==MESSAGE for item in existing):
        raise ValueError('This unique submission description already exists')
    if any(getattr(item,'kernel',None)==TARGET and getattr(item,'kernel_version',None)==VERSION for item in existing):
        raise ValueError('This exact code version is already submitted')
    refs=[item.ref for item in existing]
    if len(refs)!=len(set(refs)):
        raise ValueError('Submission inventory contains duplicate references')
    limits=api.competition_get_submission_limits(COMPETITION)
    if not isinstance(limits.num_allowed_now,int) or limits.num_allowed_now<1:
        raise ValueError('No competition submission allowance remains')
    return dict(server_source_sha256=sha(remote_raw),dataset_sources=sorted(expected),
        observed_existing_submission_refs=sorted(refs),
        allowance_before_request=dict(num_today=limits.num_today,num_total=limits.num_total,num_allowed_now=limits.num_allowed_now))


def submit_once(api=None):
    if RECEIPT.exists():raise RuntimeError('A submission claim already exists; never automatically resubmit')
    local=local_preflight()
    api=api if api is not None else make_api()
    live=live_preflight(api,local)
    # Rehash the local review immediately before claiming the one external write.
    current=local_preflight()
    for name in ('output_audit_sha256','binding_sha256','visible_output_sha256'):
        if current[name]!=local[name]:raise ValueError('Local review changed during live preflight')
    record=dict(status='requesting_once',requested_at_utc=now(),target=TARGET,version=VERSION,
        competition=COMPETITION,output_file='submission.csv',description=MESSAGE,
        notebook_sha256=local['run']['notebook_sha256'],output_audit_sha256=local['output_audit_sha256'],
        binding_sha256=local['binding_sha256'],visible_output_sha256=local['visible_output_sha256'],
        automatic_retry_allowed=False,submits_cloud_code_version=True,local_diagnostic_csv_uploaded=False,
        local_scope=dict(processed_molecules=local['audit'].get('processed_molecules'),
            input_molecules=local['audit'].get('input_molecules'),placeholder_rows=local['audit'].get('placeholder_rows'),
            is_full_run=local['audit'].get('is_full_run')),
        **live)
    inside(RECEIPT);RECEIPT.parent.mkdir(parents=True,exist_ok=True)
    with RECEIPT.open('x',encoding='utf-8') as stream:
        stream.write(json.dumps(record,indent=2)+'\n');stream.flush();os.fsync(stream.fileno())
    try:
        response=api.competition_submit_code(file_name='submission.csv',message=MESSAGE,
            competition=COMPETITION,kernel=TARGET,kernel_version=VERSION,quiet=True)
        ref=response.ref
        positive_ref=isinstance(ref,int) and not isinstance(ref,bool) and ref>0
        record.update(status='accepted' if positive_ref else 'server_response_requires_review_no_retry',
            submission_ref=ref if positive_ref else None,response_ref_positive=positive_ref,
            response_message_present=bool(response.message),responded_at_utc=now())
        save(RECEIPT,record)
    except BaseException as error:
        record.update(status='request_outcome_unknown_no_retry',checked_at_utc=now(),**safe_error(error))
        save(RECEIPT,record)
        if not isinstance(error,Exception):raise
    return {key:record.get(key) for key in ('status','submission_ref','target','version','automatic_retry_allowed')}


def poll(api=None):
    record=read(RECEIPT)
    ref=record.get('submission_ref')
    if (record.get('status')!='accepted' or record.get('target')!=TARGET or record.get('version')!=VERSION
            or record.get('competition')!=COMPETITION or record.get('description')!=MESSAGE
            or record.get('output_file')!='submission.csv' or not isinstance(ref,int)
            or isinstance(ref,bool) or ref<=0):
        raise ValueError('Polling requires the accepted fixed positive tri-model submission ref')
    api=api if api is not None else make_api()
    from kagglesdk.competitions.types.competition_api_service import ApiGetSubmissionRequest
    request=ApiGetSubmissionRequest();request.ref=ref
    with api.build_kaggle_client() as client:
        item=client.competitions.competition_api_client.get_submission(request)
    if item.ref!=ref or item.description!=MESSAGE or item.file_name!='submission.csv':
        raise ValueError('Read-back submission identity mismatch')
    status=item.status.name
    try:scored=status=='COMPLETE' and math.isfinite(float(item.public_score))
    except (ValueError,TypeError):scored=False
    error_text=item.error_description or ''
    result=dict(checked_at_utc=now(),read_only=True,target=TARGET,version=VERSION,competition=COMPETITION,
        submission_ref=ref,status=status,public_score=item.public_score if scored else None,
        public_score_available=scored,error_description_present=bool(error_text),
        error_description_sha256=sha(error_text.encode('utf-8')) if error_text else None,
        description=MESSAGE,file_name='submission.csv',
        submitted_at_utc=item.date.isoformat() if item.date else None,
        competition_submission_performed=True,new_submission_performed_by_poll=False)
    save(RESULT,result)
    inside(HISTORY);HISTORY.parent.mkdir(parents=True,exist_ok=True)
    with HISTORY.open('a',encoding='utf-8') as stream:stream.write(json.dumps(result)+'\n')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    actions=parser.add_mutually_exclusive_group(required=True)
    actions.add_argument('--check-local',action='store_true')
    actions.add_argument('--submit',action='store_true')
    actions.add_argument('--poll',action='store_true')
    args=parser.parse_args()
    if ROOT.drive.upper()!='D:':raise ValueError('Workflow must stay on D:')
    for name,relative in [('TEMP','.cache/tmp'),('TMP','.cache/tmp'),('PYTHONPYCACHEPREFIX','.cache/pycache-win')]:
        path=ROOT/relative;path.mkdir(parents=True,exist_ok=True);os.environ[name]=str(path)
    logging.disable(logging.CRITICAL)
    try:
        with redirect_stdout(io.StringIO()),redirect_stderr(io.StringIO()):
            if args.check_local:
                local=local_preflight()
                result=dict(status='local_preflight_passed',target=TARGET,version=VERSION,
                    submission_sha256=local['visible_output_sha256'],external_write_performed=False)
            else:result=submit_once() if args.submit else poll()
        print(json.dumps(result,indent=2))
        return 0 if result.get('status') not in ('server_response_requires_review_no_retry','request_outcome_unknown_no_retry') else 1
    except Exception as error:
        print(json.dumps(dict(status='stopped',**safe_error(error)),indent=2));return 1


if __name__=='__main__':raise SystemExit(main())
