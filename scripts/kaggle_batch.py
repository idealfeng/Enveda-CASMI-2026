"""Small manifest-driven private Kaggle runs and code submissions; plan-only by default.

Every --launch and --submit claims one external write durably before calling it.
An unknown outcome is never retried. --status/--poll can only reconcile by reads.
"""
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
import argparse
import csv
import hashlib
import io
import json
import logging
import math
import os
import re
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from kaggle_first_submission import make_api
from poll_public_tri_cloud import same_notebook_contents
from download_public_tri_cloud import destination_for, fetch_bounded, retry_read
from submit_public_tri_cloud import list_submissions

COMPETITION = 'enveda-CASMI26-molecule-id-mass-spectra'
SAMPLE = ROOT/'enveda-CASMI26-molecule-id-mass-spectra/sample_submission.csv'


def now(): return datetime.now(timezone.utc).isoformat()
def read(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def digest(raw): return hashlib.sha256(raw).hexdigest()
def sha(path): return digest(Path(path).read_bytes())
def all_true(checks): return isinstance(checks, dict) and bool(checks) and all(v is True for v in checks.values())
def safe_error(error):
    return dict(error_type=type(error).__name__, http_status=getattr(getattr(error, 'response', None), 'status_code', None))


def inside(path):
    path = Path(path).resolve()
    if path == ROOT or not path.is_relative_to(ROOT): raise ValueError('All workflow paths must stay inside D workspace')
    return path


def save(path, record):
    path = inside(path); path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                prefix=path.name+'.', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name); stream.write(json.dumps(record, indent=2)+'\n')
            stream.flush(); os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        if temporary: temporary.unlink(missing_ok=True)


def claim(path, record):
    path = inside(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(record, indent=2)+'\n'); stream.flush(); os.fsync(stream.fileno())


def slugs(values):
    result = set()
    for value in values or []:
        if not isinstance(value, str) or not re.fullmatch(r'[\w.-]+/[\w.-]+(?:/[\w.-]+)*', value):
            raise ValueError('Unexpected source reference')
        result.add('/'.join(value.split('/')[:2]))
    return result


def load_manifest(path):
    path = inside(path); manifest = read(path)
    branches = manifest.get('branches')
    if (manifest.get('schema_version') != 1 or manifest.get('competition') != COMPETITION
            or not re.fullmatch(r'[a-zA-Z0-9_-]+', str(manifest.get('batch_id', '')))
            or type(manifest.get('max_submissions')) is not int or not 1 <= manifest['max_submissions'] <= 5
            or not isinstance(branches, list) or not 1 <= len(branches) <= 5):
        raise ValueError('Expected a bounded schema-1 CASMI batch manifest')
    inside(ROOT/manifest['state_root'])
    for field in ('name', 'target', 'description'):
        if len({b.get(field) for b in branches}) != len(branches): raise ValueError('Repeated branch identity')
    for branch in branches:
        if (not re.fullmatch(r'[a-z0-9_]+', branch.get('name', ''))
                or not re.fullmatch(r'stormseye/[a-z0-9-]+', branch.get('target', ''))
                or branch.get('version') != 1 or type(branch.get('version')) is not int
                or not isinstance(branch.get('description'), str) or not branch['description'].strip()
                or branch.get('validation_mode') not in ('smoke', 'fast_static')):
            raise ValueError('Expected unique new private V1 branch')
        for field in ('notebook_sha256', 'metadata_sha256'):
            if not re.fullmatch('[0-9a-f]{64}', branch.get(field, '')): raise ValueError('Missing frozen stage SHA')
        inside(ROOT/branch['stage_dir'])
        audits = branch.get('required_runtime_audits')
        if not isinstance(audits, list) or not 1 <= len(audits) <= 8: raise ValueError('Runtime/static observer outputs required')
        if len({a['name'] for a in audits}) != len(audits): raise ValueError('Repeated observer output')
        for audit in audits:
            destination_for(ROOT, audit['name'])
            if not audit['name'].endswith('.json') or not isinstance(audit.get('expected_fields', {}), dict):
                raise ValueError('Expected JSON observer contract')
            if not isinstance(audit.get('required_true_checks'), list) or not audit['required_true_checks']:
                raise ValueError('Observer must assert named checks')
    return manifest


def branch_state(manifest, branch): return inside(ROOT/manifest['state_root']/branch['name'])
def branch_sha(branch): return digest(json.dumps(branch, sort_keys=True, separators=(',', ':')).encode())


def local_preflight(manifest, branch):
    stage = inside(ROOT/branch['stage_dir']); metadata = read(stage/'kernel-metadata.json')
    source = stage/metadata.get('code_file', 'notebook.ipynb')
    if source.resolve().parent != stage or sha(source) != branch['notebook_sha256'] or sha(stage/'kernel-metadata.json') != branch['metadata_sha256']:
        raise ValueError('Frozen notebook or metadata changed')
    if (metadata.get('id') != branch['target'] or metadata.get('is_private') is not True
            or metadata.get('enable_internet') is not False or metadata.get('enable_gpu') is not True or metadata.get('kernel_type') != 'notebook'
            or metadata.get('competition_sources') != [COMPETITION] or metadata.get('model_sources')):
        raise ValueError('Expected private offline competition notebook without model-source dependencies')
    slugs(metadata.get('dataset_sources')); slugs(metadata.get('kernel_sources'))
    notebook = read(source)
    for cell in notebook['cells']:
        text = cell.get('source', ''); text = ''.join(text) if isinstance(text, list) else text
        if cell['cell_type'] == 'code': compile(text, str(source), 'exec')
    if branch['validation_mode'] == 'fast_static' or branch.get('static_review_path'):
        review_path = inside(ROOT/branch['static_review_path']); review = read(review_path)
        if (review.get('status') != 'passed' or review.get('target') != branch['target']
                or review.get('version') != 1 or review.get('notebook_sha256') != branch['notebook_sha256']
                or not all_true(review.get('checks'))): raise ValueError('Passing source-bound static review required')
    return dict(stage=stage, source=source, metadata=metadata)


def bound_receipt(manifest, branch, name):
    record = read(branch_state(manifest, branch)/name)
    if (record.get('branch_sha256') != branch_sha(branch) or record.get('target') != branch['target']
            or record.get('version') != 1): raise ValueError('Receipt belongs to a different branch')
    return record


def cloud_target(manifest, branch):
    record = bound_receipt(manifest, branch, 'cloud.json')
    target = record.get('actual_target', branch['target'])
    if not re.fullmatch(r'stormseye/[a-z0-9-]+', target): raise ValueError('Invalid reconciled cloud target')
    return target


def launch(manifest, branch, api=None):
    state = branch_state(manifest, branch); receipt = state/'cloud.json'
    if receipt.exists(): raise RuntimeError('Cloud write already claimed; inspect status, never push again')
    local = local_preflight(manifest, branch); api = api or make_api()
    complete = False
    for page in range(1, 101):
        owned = api.kernels_list(mine=True, page=page, page_size=100) or []
        refs = [getattr(item, 'ref', None) for item in owned]
        if any(not isinstance(ref, str) for ref in refs): raise ValueError('Incomplete owned inventory')
        if branch['target'].lower() in {ref.lower() for ref in refs}: raise ValueError('Target exists; refusing overwrite')
        if len(owned) < 100: complete = True; break
    if not complete: raise ValueError('Owned inventory page cap')
    local_preflight(manifest, branch)
    record = dict(status='requesting_once', target=branch['target'], version=1, branch_sha256=branch_sha(branch),
        notebook_sha256=branch['notebook_sha256'], metadata_sha256=branch['metadata_sha256'], requested_at_utc=now(),
        automatic_retry_allowed=False, competition_submission_performed=False)
    claim(receipt, record)
    try:
        response = api.kernels_push(str(local['stage']), timeout='32400', no_run=False)
        invalid = any(getattr(response, field, None) for field in ('invalid_tags', 'invalid_dataset_sources',
            'invalid_competition_sources', 'invalid_kernel_sources', 'invalid_model_sources'))
        accepted = (response.version_number == 1 and not response.error and not invalid
            and str(response.ref or '').strip('/') in (branch['target'], 'code/'+branch['target']))
        record.update(status='run_requested' if accepted else 'server_response_requires_review_no_retry',
            responded_at_utc=now(), observed_version=response.version_number, response_error_present=bool(response.error),
            invalid_sources_present=bool(invalid))
        if response.error:
            # This is the API's explanatory response field, never an HTTP request
            # or its headers. Strip URLs before saving/printing diagnostics.
            record['server_error_summary'] = re.sub(r'https?://\S+', '[URL omitted]', str(response.error))[:600]
    except BaseException as error:
        record.update(status='request_outcome_unknown_no_retry', checked_at_utc=now(), **safe_error(error))
        save(receipt, record)
        if not isinstance(error, Exception): raise
    save(receipt, record); return record


def live_binding(manifest, branch, api=None, actual_target=None):
    local = local_preflight(manifest, branch)
    cloud = bound_receipt(manifest, branch, 'cloud.json'); api = api or make_api()
    target = cloud_target(manifest, branch) if actual_target is None else actual_target
    if not re.fullmatch(r'stormseye/[a-z0-9-]+', target): raise ValueError('Reconciliation must stay in the authenticated account')
    if cloud.get('actual_target') and cloud['actual_target'] != target:
        raise ValueError('An established actual target cannot be rebound')
    from kagglesdk.kernels.types.kernels_api_service import ApiGetKernelRequest
    request = ApiGetKernelRequest(); request.user_name, request.kernel_slug = target.split('/')
    request.version_label = api._kernel_version_label('1')
    with api.build_kaggle_client() as client: remote = client.kernels.kernels_api_client.get_kernel(request)
    meta = remote.metadata; raw = remote.blob.source.encode('utf-8')
    checks = dict(target=meta.ref == target, version=meta.current_version_number == 1,
        private=meta.is_private is True, offline=meta.enable_internet is False, gpu=meta.enable_gpu is True,
        source_contents=same_notebook_contents(local['source'].read_bytes(), raw),
        dataset_sources=slugs(meta.dataset_data_sources) == slugs(local['metadata'].get('dataset_sources')),
        kernel_sources=slugs(meta.kernel_data_sources) == slugs(local['metadata'].get('kernel_sources')),
        competition_sources=set(meta.competition_data_sources or []) == {COMPETITION},
        no_model_source_dependencies=not meta.model_data_sources)
    if not all_true(checks): raise ValueError('Live V1 source/private/offline/dependencies differ')
    status = api.kernels_status(target+'/1')
    record = dict(status='passed', checked_at_utc=now(), target=branch['target'], version=1,
        actual_target=target,
        branch_sha256=branch_sha(branch), notebook_sha256=branch['notebook_sha256'],
        server_source_sha256=digest(raw), checks=checks, session_status=status.status.name,
        failure_message_present=bool(status.failure_message), read_only=True,
        source_raw_bytes_equal=local['source'].read_bytes() == raw,
        source_binding_method='Join cell.source lists; every other Notebook JSON field must remain equal.',
        requested_dataset_sources=local['metadata'].get('dataset_sources', []),
        observed_dataset_sources=list(meta.dataset_data_sources or []),
        requested_kernel_sources=local['metadata'].get('kernel_sources', []),
        observed_kernel_sources=list(meta.kernel_data_sources or []), numeric_source_versions_read_back=False)
    save(branch_state(manifest, branch)/'binding.json', record)
    if actual_target is not None:
        cloud.update(status='run_requested', actual_target=target, reconciled_by_read_at=now(),
            reconciliation_server_source_sha256=digest(raw), automatic_retry_allowed=False)
        save(branch_state(manifest, branch)/'cloud.json', cloud)
    elif cloud['status'] == 'request_outcome_unknown_no_retry':
        cloud.update(status='run_requested_reconciled_by_source', reconciled_at_utc=now(), automatic_retry_allowed=False)
        save(branch_state(manifest, branch)/'cloud.json', cloud)
    return record


def reconcile_target(manifest, branch, actual_target, api=None):
    # This path performs only authenticated reads and D: receipt updates, never a push.
    return live_binding(manifest, branch, api=api, actual_target=actual_target)


def observer_valid(audit, contract):
    checks = audit.get('checks')
    return (audit.get('status') == 'passed' and all_true(checks)
        and all(checks.get(name) is True for name in contract['required_true_checks'])
        and all(audit.get(key) == value for key, value in contract.get('expected_fields', {}).items()))


def csv_audit(raw, sample_path=SAMPLE):
    from validation import metric
    metric.assert_official_rdkit()
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))); columns = reader.fieldnames; rows = list(reader)
    with Path(sample_path).open(encoding='utf-8-sig', newline='') as stream: sample = list(csv.DictReader(stream))
    ids = [row.get('molecule_id') for row in rows]
    if columns != ['molecule_id', 'smiles'] or ids != [row['molecule_id'] for row in sample] or len(ids) != 400 or len(set(ids)) != 400:
        raise ValueError('CSV columns/400 IDs/order differ from official sample')
    duplicates = []
    for row in rows:
        guesses = metric.parse_guesses(row['smiles'])
        identities = [metric.identity(guess) for guess in guesses]
        if not 1 <= len(guesses) <= 25 or any(key is None for key in identities): raise ValueError('Invalid candidate count or official identity')
        if len(set(identities)) != len(identities): duplicates.append(row['molecule_id'])
    return dict(rows=len(rows), rdkit='2026.03.3', duplicate_identity_rows=duplicates)


def audit_outputs(manifest, branch, api=None, fetch=None):
    state = branch_state(manifest, branch); output = state/'outputs'
    if output.exists(): raise FileExistsError('Preserve downloaded/audited evidence; do not overwrite')
    api = api or make_api(); binding = live_binding(manifest, branch, api)
    if binding['session_status'] != 'COMPLETE' or binding['failure_message_present']: raise ValueError('V1 must finish successfully')
    import requests
    from kagglesdk.kernels.types.kernels_api_service import ApiListKernelSessionOutputRequest
    wanted = ['submission.csv']+[a['name'] for a in branch['required_runtime_audits']]
    files = {}; token = ''; seen = set()
    with api.build_kaggle_client() as client:
        for _ in range(100):
            request = ApiListKernelSessionOutputRequest(); request.user_name, request.kernel_slug = binding['actual_target'].split('/')
            request.version_label = api._kernel_version_label('1'); request.page_size = 100
            if token: request.page_token = token
            response = retry_read(lambda: client.kernels.kernels_api_client.list_kernel_session_output(request), requests)
            for item in response.files or []:
                if item.file_name in files: raise ValueError('Repeated output filename')
                files[item.file_name] = item
            token = response.next_page_token or ''
            if not token: break
            if token in seen: raise ValueError('Repeated output pagination token')
            seen.add(token)
        else: raise ValueError('Output pagination page cap')
    if not set(wanted) <= set(files): raise ValueError('Required output artifact missing')
    output.mkdir(parents=True, exist_ok=False); records = []; artifacts = {}; total = 0
    try:
        for name in wanted:
            limit = min(4 << 20 if name == 'submission.csv' else 2 << 20, (16 << 20)-total)
            raw = retry_read(lambda: fetch_bounded(files[name].url, limit, requests, fetch), requests)
            destination = destination_for(output, name); destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(raw); total += len(raw); artifacts[name] = raw
            records.append(dict(name=name, bytes=len(raw), sha256=digest(raw)))
        csv_details = csv_audit(artifacts['submission.csv'])
        checks = dict(csv_schema_and_official_identities=True, version_source_private_offline=True)
        for contract in branch['required_runtime_audits']:
            checks['observer:'+contract['name']] = observer_valid(json.loads(artifacts[contract['name']]), contract)
        result = dict(status='passed' if all_true(checks) else 'failed', target=branch['target'], version=1,
            actual_target=binding['actual_target'],
            branch_sha256=branch_sha(branch), notebook_sha256=branch['notebook_sha256'],
            checked_at_utc=now(), checks=checks, files=records, csv=csv_details,
            submission_sha256=digest(artifacts['submission.csv']), total_bytes=total,
            validation_mode=branch['validation_mode'],
            scope='fast_static_no_visible_model_execution' if branch['validation_mode'] == 'fast_static' else 'visible_smoke_only_not_hidden_score',
            signed_urls_persisted=False, read_only=True, competition_submission_performed=False)
    except BaseException as error:
        result = dict(status='audit_failed', target=branch['target'], version=1, branch_sha256=branch_sha(branch),
            files=records, checked_at_utc=now(), **safe_error(error))
        save(state/'output_audit.json', result)
        if not isinstance(error, Exception): raise
    save(state/'output_audit.json', result); return result


def audited_local(manifest, branch):
    local_preflight(manifest, branch); state = branch_state(manifest, branch)
    audit = bound_receipt(manifest, branch, 'output_audit.json')
    if audit.get('status') != 'passed' or not all_true(audit.get('checks')) or audit.get('notebook_sha256') != branch['notebook_sha256']:
        raise ValueError('Passing source-bound output audit required')
    if audit.get('actual_target', branch['target']) != cloud_target(manifest, branch):
        raise ValueError('Output audit belongs to a different actual cloud target')
    for item in audit['files']:
        path = destination_for(state/'outputs', item['name'])
        if sha(path) != item['sha256'] or path.stat().st_size != item['bytes']: raise ValueError('Audited output changed')
    if sha(state/'outputs/submission.csv') != audit['submission_sha256']: raise ValueError('Audited CSV changed')
    return audit


def submit(manifest, branch, api=None):
    state = branch_state(manifest, branch); receipt = state/'submission.json'
    if receipt.exists(): raise RuntimeError('Submission already claimed; poll, never retry')
    audit = audited_local(manifest, branch); api = api or make_api()
    batch_state = inside(ROOT/manifest['state_root']); lock = batch_state/'.submit.lock'
    claim(lock, dict(pid=os.getpid(), branch=branch['name'], started_at_utc=now()))
    try:
        claims = list(batch_state.glob('*/submission.json'))
        if len(claims) >= manifest['max_submissions']: raise ValueError('Batch submission limit reached, including unknown outcomes')
        binding = live_binding(manifest, branch, api)
        if binding['session_status'] != 'COMPLETE' or binding['failure_message_present']: raise ValueError('Cloud V1 not successfully complete')
        existing = list_submissions(api)
        if any(item.description == branch['description'] for item in existing): raise ValueError('Description already submitted')
        if any(getattr(item, 'kernel', None) == binding['actual_target'] and getattr(item, 'kernel_version', None) == 1 for item in existing):
            raise ValueError('Exact code version already submitted')
        limits = api.competition_get_submission_limits(COMPETITION)
        if type(limits.num_allowed_now) is not int or limits.num_allowed_now < 1: raise ValueError('No submission allowance now')
        audited_local(manifest, branch)
        record = dict(status='requesting_once', target=branch['target'], version=1, branch_sha256=branch_sha(branch),
            actual_target=binding['actual_target'],
            description=branch['description'], competition=COMPETITION, output_file='submission.csv',
            requested_at_utc=now(), notebook_sha256=branch['notebook_sha256'],
            visible_output_sha256=audit['submission_sha256'], output_audit_sha256=sha(state/'output_audit.json'),
            observed_existing_refs=sorted(item.ref for item in existing), num_allowed_before=limits.num_allowed_now,
            num_today_before=getattr(limits, 'num_today', None), num_total_before=getattr(limits, 'num_total', None),
            validation_mode=branch['validation_mode'], automatic_retry_allowed=False,
            submits_cloud_code_version=True, local_diagnostic_csv_uploaded=False)
        claim(receipt, record)
        try:
            response = api.competition_submit_code(file_name='submission.csv', message=branch['description'],
                competition=COMPETITION, kernel=binding['actual_target'], kernel_version=1, quiet=True)
            ref = response.ref; accepted = type(ref) is int and ref > 0
            record.update(status='accepted' if accepted else 'server_response_requires_review_no_retry',
                submission_ref=ref if accepted else None, responded_at_utc=now())
        except BaseException as error:
            record.update(status='request_outcome_unknown_no_retry', checked_at_utc=now(), **safe_error(error))
            save(receipt, record)
            if not isinstance(error, Exception): raise
        save(receipt, record); return record
    finally: lock.unlink(missing_ok=True)


def poll_submission(manifest, branch, api=None):
    state = branch_state(manifest, branch); record = bound_receipt(manifest, branch, 'submission.json')
    if record.get('description') != branch['description']: raise ValueError('Submission description changed')
    actual_target = cloud_target(manifest, branch)
    if record.get('actual_target', branch['target']) != actual_target: raise ValueError('Submission actual cloud target changed')
    api = api or make_api(); ref = record.get('submission_ref')
    if type(ref) is not int or ref <= 0:
        matches = [item for item in list_submissions(api) if item.description == branch['description'] and item.file_name == 'submission.csv']
        if len(matches) != 1 or type(matches[0].ref) is not int or matches[0].ref <= 0: raise ValueError('Unknown result remains unresolved; never resubmit')
        ref = matches[0].ref
        record.update(status='accepted_reconciled_by_unique_description', submission_ref=ref, reconciled_at_utc=now())
        save(state/'submission.json', record)
    from kagglesdk.competitions.types.competition_api_service import ApiGetSubmissionRequest
    request = ApiGetSubmissionRequest(); request.ref = ref
    with api.build_kaggle_client() as client: item = client.competitions.competition_api_client.get_submission(request)
    if item.ref != ref or item.description != branch['description'] or item.file_name != 'submission.csv': raise ValueError('Submission readback identity differs')
    status = item.status.name
    try: scored = status == 'COMPLETE' and math.isfinite(float(item.public_score))
    except (TypeError, ValueError): scored = False
    result = dict(target=branch['target'], version=1, branch_sha256=branch_sha(branch), submission_ref=ref,
        actual_target=actual_target,
        status=status, public_score=item.public_score if scored else None, public_score_available=scored,
        error_description_present=bool(item.error_description), checked_at_utc=now(), read_only=True,
        new_submission_performed=False)
    save(state/'score.json', result); return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True); parser.add_argument('--branch')
    actions = parser.add_mutually_exclusive_group()
    for name in ('launch', 'status', 'audit-outputs', 'submit', 'poll'): actions.add_argument('--'+name, action='store_true')
    actions.add_argument('--reconcile-target', metavar='ACTUAL_REF')
    args = parser.parse_args(); action = next((name for name in ('launch', 'status', 'audit_outputs', 'submit', 'poll', 'reconcile_target') if getattr(args, name)), None)
    manifest = load_manifest(args.manifest)
    branches = manifest['branches'] if args.branch in (None, 'all') else [b for b in manifest['branches'] if b['name'] == args.branch]
    if not branches or (action in ('launch', 'audit_outputs', 'submit', 'reconcile_target') and len(branches) != 1): raise ValueError('Choose exactly one branch for writes or output download')
    if not action:
        for branch in branches: local_preflight(manifest, branch)
        return dict(status='plan_only_no_network', batch_id=manifest['batch_id'], max_submissions=manifest['max_submissions'],
            branches=[dict(name=b['name'], target=b['target'], validation_mode=b['validation_mode']) for b in branches])
    function = {'launch':launch, 'status':live_binding, 'audit_outputs':audit_outputs, 'submit':submit, 'poll':poll_submission,
        'reconcile_target':lambda manifest, branch:reconcile_target(manifest, branch, args.reconcile_target)}[action]
    results = []
    for branch in branches:
        try: result = function(manifest, branch)
        except Exception as error: result = dict(status='stopped', **safe_error(error))
        results.append(dict(branch=branch['name'], **result))
    return dict(action=action, results=results)


if __name__ == '__main__':
    for name, relative in [('TEMP','.cache/tmp'),('TMP','.cache/tmp'),('PYTHONPYCACHEPREFIX','.cache/pycache-win')]:
        path = ROOT/relative; path.mkdir(parents=True, exist_ok=True); os.environ[name] = str(path)
    logging.disable(logging.CRITICAL)
    if any(flag in sys.argv[1:] for flag in ('--help', '-h')):
        main()
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()): result = main()
        print(json.dumps(result, indent=2))
        failed = {'stopped','failed','audit_failed','request_outcome_unknown_no_retry','server_response_requires_review_no_retry'}
        raise SystemExit(1 if any(item.get('status') in failed for item in result.get('results', [])) else 0)
    except Exception as error:
        print(json.dumps(dict(status='stopped', **safe_error(error)), indent=2)); raise SystemExit(1)
