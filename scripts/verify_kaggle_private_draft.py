"""Read one existing private Kaggle draft version; never save/run/submit."""
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timezone
from pathlib import Path
import ast
import hashlib
import io
import json
import logging

ROOT = Path(__file__).resolve().parents[1]
TARGET = 'stormseye/casmi26-flex-v56-baseline'
PULL = ROOT / 'reports/kaggle_private_draft_pull_20261105'
REPORT = ROOT / 'reports/kaggle_private_draft_server_verification_20261105.json'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def source(cell):
    value = cell.get('source', '')
    return (''.join(value) if isinstance(value, list) else value).replace('\r\n', '\n').replace('\r', '\n')


def main():
    if PULL.exists() and any(PULL.iterdir()):
        raise RuntimeError('Use the saved pull artifacts; do not overwrite a server snapshot')
    PULL.mkdir(exist_ok=True)
    created = json.loads((ROOT/'reports/kaggle_private_draft_20261105.json').read_text())
    if created['status'] != 'created' or created['target'] != TARGET or created['version_number'] != 1:
        raise ValueError('Expected the newly created V1 quick-save receipt')
    original = (ROOT/'third_party/flexonafft_evidence_gap/v56/original.ipynb').read_bytes()
    staged = (ROOT/'submission/flex_v56_cloud_draft/notebook.ipynb').read_bytes()
    requested = json.loads((ROOT/'submission/flex_v56_cloud_draft/kernel-metadata.json').read_text())
    if sha(original) != sha(staged) or sha(staged) != created['notebook_sha256']:
        raise ValueError('Local original/staged notebook binding changed')
    report = dict(status='requesting_read_only_pull', requested_at_utc=datetime.now(timezone.utc).isoformat(),
        target=TARGET, requested_version=1, read_only=True, run_requested=False, push_performed=False,
        submission_performed=False, auth_via_installed_sdk=True,
        credential_values_or_auth_headers_printed_or_persisted=False,
        original_notebook_sha256=sha(original))
    REPORT.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    try:
        logging.disable(logging.CRITICAL)
        # Do not echo SDK authentication/debug output or serialize clients/errors.
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            from kaggle.api.kaggle_api_extended import KaggleApi
            from kagglesdk.kernels.types.kernels_api_service import ApiGetKernelRequest
            api = KaggleApi(); api.authenticate()
            request = ApiGetKernelRequest()
            request.user_name, request.kernel_slug = TARGET.split('/')
            request.version_label = api._kernel_version_label('1')
            with api.build_kaggle_client() as client:
                response = client.kernels.kernels_api_client.get_kernel(request)
        meta, blob = response.metadata, response.blob
        raw = blob.source.encode('utf-8')
        if len(raw) > 8*1024*1024:
            raise ValueError('Unexpectedly large notebook source')
        (PULL/'source.ipynb').write_bytes(raw)
        names = ['id', 'ref', 'title', 'author', 'slug', 'language', 'kernel_type', 'is_private',
                 'enable_gpu', 'enable_tpu', 'enable_internet', 'dataset_data_sources',
                 'kernel_data_sources', 'competition_data_sources', 'model_data_sources',
                 'current_version_number', 'docker_image', 'machine_shape']
        observed = {name: getattr(meta, name, None) for name in names}
        when = getattr(meta, 'last_run_time', None)
        observed['last_run_time'] = when.isoformat() if when is not None else None
        observed['raw_optional_flags'] = {name: getattr(meta, '_'+name, None)
            for name in ('is_private', 'enable_gpu', 'enable_tpu', 'enable_internet', 'docker_image', 'machine_shape')}
        (PULL/'server_metadata.json').write_text(json.dumps(observed, indent=2)+'\n', encoding='utf-8')
        before, after = json.loads(original), json.loads(raw)
        cells = []
        count_equal = len(before['cells']) == len(after['cells'])
        for index, (a, b) in enumerate(zip(before['cells'], after['cells'])):
            kind = a.get('cell_type'); same_type = kind == b.get('cell_type')
            text_equal = source(a) == source(b)
            ast_equal = None
            if kind == 'code' and same_type:
                ast_equal = ast.dump(ast.parse(source(a)), include_attributes=False) == ast.dump(ast.parse(source(b)), include_attributes=False)
            cells.append(dict(index=index, cell_type=kind, same_type=same_type,
                              normalized_source_equal=text_equal, code_ast_equal=ast_equal))
        semantic_equal = count_equal and all(x['same_type'] and
            (x['code_ast_equal'] if x['cell_type']=='code' else x['normalized_source_equal']) for x in cells)
        emitted = observed['dataset_data_sources'] or []
        version_visibility = []
        for ref, version in sorted(created['required_dataset_versions'].items()):
            matches = [value for value in emitted if value == ref or value.startswith(ref+'/')]
            visible_versions = [value.split('/')[2] for value in matches if len(value.split('/')) == 3]
            version_visibility.append(dict(ref=ref, requested_version=version, server_strings=matches,
                requested_version_visible=str(version) in visible_versions,
                version_visibility='explicit_match' if str(version) in visible_versions else 'slug_only' if matches else 'source_not_reported'))
        private = observed['is_private'] is True
        offline = observed['enable_internet'] is False
        checks = dict(target_ref=observed['ref']==TARGET, private=private, internet_disabled=offline,
                      current_version_one=observed['current_version_number']==1,
                      language_python=observed['language']=='python', notebook_type=observed['kernel_type']=='notebook',
                      source_cell_semantics=semantic_equal,
                      six_required_source_refs_reported=all(item['server_strings'] for item in version_visibility))
        report.update(status='verified_metadata_and_source' if all(checks.values()) else 'verification_mismatch',
            checked_at_utc=datetime.now(timezone.utc).isoformat(),
            method='Installed SDK authenticated typed GetKernel, identical read endpoint used by kernels_pull; version_label=v1.',
            checks=checks, server_metadata=observed,
            source_comparison=dict(original_cells=len(before['cells']), server_cells=len(after['cells']),
                original_code_cells=sum(c.get('cell_type')=='code' for c in before['cells']),
                original_markdown_cells=sum(c.get('cell_type')=='markdown' for c in before['cells']),
                all_normalized_sources_equal=count_equal and all(item['normalized_source_equal'] for item in cells),
                all_code_asts_equal=all(item['code_ast_equal'] for item in cells if item['cell_type']=='code'),
                all_code_and_markdown_semantics_equal=semantic_equal, cells=cells,
                outputs_execution_counts_and_notebook_json_layout_not_used_as_semantic_identity=True),
            observed_docker_image_matches_request=bool(observed['docker_image']) and observed['docker_image']==requested['docker_image'],
            observed_machine_shape_matches_request=bool(observed['machine_shape']) and observed['machine_shape']==requested['machine_shape'],
            attachment_versions=version_visibility,
            all_requested_attachment_versions_visible=all(item['requested_version_visible'] for item in version_visibility),
            runtime_execution_verified=False, actual_device_allocation_verified=False,
            docker_container_execution_verified=False, runtime_mounted_attachment_versions_verified=False,
            full_input_or_cold_budget_verified=False,
            artifacts={str(PULL.relative_to(ROOT)/'source.ipynb'):dict(bytes=len(raw),sha256=sha(raw)),
                       str(PULL.relative_to(ROOT)/'server_metadata.json'):dict(sha256=sha((PULL/'server_metadata.json').read_bytes()))},
            limitations=['Quick-save metadata/source readback does not allocate a session or prove a model run.',
                'Echoed Docker/machine strings are stored metadata, not proof of actual device/container availability.',
                'Missing attachment version numbers in metadata remain unverified; versioned request strings alone are not readback proof.',
                'No run, push, dataset write, or competition submission was requested by this verifier.'])
    except BaseException as error:
        report.update(status='read_or_verification_failed', error_type=type(error).__name__,
            http_status=getattr(getattr(error, 'response', None), 'status_code', None),
            checked_at_utc=datetime.now(timezone.utc).isoformat())
    REPORT.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({key: report.get(key) for key in ('status','target','checks',
        'all_requested_attachment_versions_visible','observed_docker_image_matches_request',
        'observed_machine_shape_matches_request','error_type','http_status')}, indent=2))
    return 0 if report['status']=='verified_metadata_and_source' else 1


if __name__ == '__main__':
    raise SystemExit(main())
