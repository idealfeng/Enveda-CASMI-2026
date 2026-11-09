"""Offline boundaries for the manifest-driven batch tool; no real Kaggle calls."""
from pathlib import Path
from types import SimpleNamespace as NS
from unittest import TestCase, mock
import copy
import json
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import kaggle_batch as batch


class BatchTests(TestCase):
    def setUp(self):
        (ROOT/'.cache/tmp').mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=ROOT/'.cache/tmp'); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name); patch = mock.patch.object(batch, 'ROOT', self.root)
        patch.start(); self.addCleanup(patch.stop)
        self.stage = self.root/'stage'; self.stage.mkdir()
        self.notebook = dict(nbformat=4, nbformat_minor=5, metadata={}, cells=[
            dict(cell_type='code', source=['value=1\n'], metadata={}, execution_count=None, outputs=[])])
        self.write(self.stage/'notebook.ipynb', self.notebook)
        self.target = 'stormseye/test-batch-branch'
        self.meta = dict(id=self.target, code_file='notebook.ipynb', kernel_type='notebook',
            is_private=True, enable_internet=False, enable_gpu=True, competition_sources=[batch.COMPETITION],
            dataset_sources=['owner/data/1'], kernel_sources=[], model_sources=[])
        self.write(self.stage/'kernel-metadata.json', self.meta)
        self.branch = dict(name='first', target=self.target, version=1, stage_dir='stage',
            notebook_sha256=batch.sha(self.stage/'notebook.ipynb'), metadata_sha256=batch.sha(self.stage/'kernel-metadata.json'),
            description='unique batch branch 20261107', validation_mode='fast_static', static_review_path='review.json',
            required_runtime_audits=[dict(name='batch_variant_audit.json', required_true_checks=['static_source'],
                expected_fields=dict(mode='fast_static', branch='first'))])
        self.write(self.root/'review.json', dict(status='passed', target=self.target, version=1,
            notebook_sha256=self.branch['notebook_sha256'], checks=dict(compiles=True)))
        self.manifest = dict(schema_version=1, batch_id='20261107', competition=batch.COMPETITION,
            max_submissions=4, state_root='state', branches=[self.branch])
        self.write(self.root/'manifest.json', self.manifest)
        self.state = batch.branch_state(self.manifest, self.branch); self.state.mkdir(parents=True)

    def write(self, path, value): Path(path).write_text(json.dumps(value), encoding='utf-8')

    def cloud(self, status='run_requested'):
        self.write(self.state/'cloud.json', dict(status=status, target=self.target, version=1,
            branch_sha256=batch.branch_sha(self.branch)))

    def api(self):
        api = mock.MagicMock(); api.kernels_list.return_value = []
        api.kernels_status.return_value = NS(status=NS(name='COMPLETE'), failure_message='')
        api._kernel_version_label.return_value = 'v1'
        server = copy.deepcopy(self.notebook); server['cells'][0]['source'] = 'value=1\n'
        self.remote = NS(metadata=NS(ref=self.target, current_version_number=1, is_private=True,
            enable_internet=False, enable_gpu=True, dataset_data_sources=['owner/data'], kernel_data_sources=[],
            competition_data_sources=[batch.COMPETITION], model_data_sources=[]), blob=NS(source=json.dumps(server)))
        client = api.build_kaggle_client.return_value.__enter__.return_value
        client.kernels.kernels_api_client.get_kernel.return_value = self.remote
        client.competitions.competition_api_client.list_submissions.return_value = NS(
            submissions=[NS(ref=58021256, description='old original'), NS(ref=58051406, description='old tri')], next_page_token='')
        api.competition_get_submission_limits.return_value = NS(num_allowed_now=4)
        api.kernels_push.return_value = NS(version_number=1, ref='/code/'+self.target, error='',
            invalid_tags=[], invalid_dataset_sources=[], invalid_competition_sources=[], invalid_kernel_sources=[], invalid_model_sources=[])
        api.competition_submit_code.return_value = NS(ref=99000002)
        self.write(self.state/'output_audit.json', {'fixture': True})
        return api, client

    def test_manifest_bounds_and_identity(self):
        self.assertEqual(batch.load_manifest(self.root/'manifest.json')['max_submissions'], 4)
        changed = copy.deepcopy(self.manifest); changed['max_submissions'] = 6
        self.write(self.root/'manifest.json', changed)
        with self.assertRaises(ValueError): batch.load_manifest(self.root/'manifest.json')
        changed['max_submissions'] = 4; changed['branches'].append(copy.deepcopy(changed['branches'][0]))
        self.write(self.root/'manifest.json', changed)
        with self.assertRaises(ValueError): batch.load_manifest(self.root/'manifest.json')

    def test_local_hash_private_and_static_review_guards(self):
        batch.local_preflight(self.manifest, self.branch)
        (self.stage/'notebook.ipynb').write_text('{}')
        with self.assertRaises(ValueError): batch.local_preflight(self.manifest, self.branch)

    def test_launch_claim_precedes_one_external_write(self):
        api, _ = self.api()
        original = api.kernels_push.return_value
        def observe(*args, **kwargs):
            self.assertEqual(batch.read(self.state/'cloud.json')['status'], 'requesting_once')
            self.assertFalse(kwargs['no_run']); return original
        api.kernels_push.side_effect = observe
        self.assertEqual(batch.launch(self.manifest, self.branch, api)['status'], 'run_requested')
        with self.assertRaises(RuntimeError): batch.launch(self.manifest, self.branch, api)
        self.assertEqual(api.kernels_push.call_count, 1)

    def test_unknown_launch_not_retried(self):
        api, _ = self.api(); api.kernels_push.side_effect = TimeoutError('sensitive URL must not be persisted')
        result = batch.launch(self.manifest, self.branch, api)
        self.assertEqual(result['status'], 'request_outcome_unknown_no_retry')
        self.assertNotIn('sensitive', json.dumps(result))
        with self.assertRaises(RuntimeError): batch.launch(self.manifest, self.branch, api)
        self.assertEqual(api.kernels_push.call_count, 1)

    def test_representation_change_only_is_accepted_and_unknown_reconciles_by_read(self):
        self.cloud('request_outcome_unknown_no_retry'); api, _ = self.api()
        self.assertEqual(batch.live_binding(self.manifest, self.branch, api)['status'], 'passed')
        self.assertEqual(batch.read(self.state/'cloud.json')['status'], 'run_requested_reconciled_by_source')
        api.kernels_push.assert_not_called()
        changed = json.loads(self.remote.blob.source); changed['metadata']['injected'] = True
        self.remote.blob.source = json.dumps(changed)
        with self.assertRaises(ValueError): batch.live_binding(self.manifest, self.branch, api)

    def test_private_internet_and_dependency_mismatches_stop(self):
        self.cloud(); api, _ = self.api()
        for key, value in [('is_private', False), ('enable_internet', True), ('dataset_data_sources', ['owner/other'])]:
            old = getattr(self.remote.metadata, key); setattr(self.remote.metadata, key, value)
            with self.assertRaises(ValueError): batch.live_binding(self.manifest, self.branch, api)
            setattr(self.remote.metadata, key, old)

    def test_fast_static_observer_has_explicit_scope_and_required_checks(self):
        contract = self.branch['required_runtime_audits'][0]
        artifact = dict(status='passed', mode='fast_static', branch='first', checks=dict(static_source=True))
        self.assertTrue(batch.observer_valid(artifact, contract))
        artifact['mode'] = 'runtime'
        self.assertFalse(batch.observer_valid(artifact, contract))
        artifact['mode'] = 'fast_static'; artifact['checks']['unexpected_failure'] = False
        self.assertFalse(batch.observer_valid(artifact, contract))

    def test_submit_once_cloud_code_with_unrelated_historical_refs_allowed(self):
        self.cloud(); api, _ = self.api()
        with mock.patch.object(batch, 'audited_local', return_value=dict(submission_sha256='a'*64)):
            result = batch.submit(self.manifest, self.branch, api)
            self.assertEqual(result['status'], 'accepted')
            with self.assertRaises(RuntimeError): batch.submit(self.manifest, self.branch, api)
        api.competition_submit_code.assert_called_once_with(file_name='submission.csv', message=self.branch['description'],
            competition=batch.COMPETITION, kernel=self.target, kernel_version=1, quiet=True)
        self.assertFalse(result['local_diagnostic_csv_uploaded'])

    def test_unknown_submit_is_preserved_and_counts_towards_batch_limit(self):
        self.cloud(); api, _ = self.api(); api.competition_submit_code.side_effect = TimeoutError('private address')
        with mock.patch.object(batch, 'audited_local', return_value=dict(submission_sha256='a'*64)):
            result = batch.submit(self.manifest, self.branch, api)
            self.assertEqual(result['status'], 'request_outcome_unknown_no_retry')
            with self.assertRaises(RuntimeError): batch.submit(self.manifest, self.branch, api)
            second = copy.deepcopy(self.branch); second['name'] = 'second'; second['target'] += '-second'
            limited = {**self.manifest, 'max_submissions': 1}
            with self.assertRaises(ValueError): batch.submit(limited, second, api)
        self.assertEqual(api.competition_submit_code.call_count, 1)
        self.assertNotIn('private address', json.dumps(result))

    def test_duplicate_description_or_zero_quota_prevents_claim(self):
        self.cloud(); api, client = self.api()
        existing = client.competitions.competition_api_client.list_submissions.return_value
        existing.submissions.append(NS(ref=9911, description=self.branch['description']))
        with mock.patch.object(batch, 'audited_local', return_value=dict(submission_sha256='a'*64)):
            with self.assertRaises(ValueError): batch.submit(self.manifest, self.branch, api)
            existing.submissions.pop(); api.competition_get_submission_limits.return_value.num_allowed_now = 0
            with self.assertRaises(ValueError): batch.submit(self.manifest, self.branch, api)
        self.assertFalse((self.state/'submission.json').exists()); api.competition_submit_code.assert_not_called()

    def test_readonly_fixed_ref_poll(self):
        self.cloud(); api, client = self.api()
        self.write(self.state/'submission.json', dict(status='accepted', target=self.target, version=1,
            branch_sha256=batch.branch_sha(self.branch), description=self.branch['description'], submission_ref=99000002))
        client.competitions.competition_api_client.get_submission.return_value = NS(ref=99000002,
            description=self.branch['description'], file_name='submission.csv', status=NS(name='COMPLETE'),
            public_score='0.481', error_description='')
        result = batch.poll_submission(self.manifest, self.branch, api)
        self.assertEqual(result['public_score'], '0.481'); self.assertTrue(result['read_only'])
        api.competition_submit_code.assert_not_called(); api.kernels_push.assert_not_called()

    def test_bounded_output_audit_preserves_fast_static_scope(self):
        self.cloud(); api, client = self.api()
        artifact = dict(status='passed', mode='fast_static', branch='first', checks=dict(static_source=True))
        payloads = {'https://fixture/submission.csv': b'molecule_id,smiles\n',
            'https://fixture/batch_variant_audit.json': json.dumps(artifact).encode()}
        client.kernels.kernels_api_client.list_kernel_session_output.return_value = NS(
            files=[NS(file_name=name, url='https://fixture/'+name) for name in ('submission.csv', 'batch_variant_audit.json')], next_page_token='')
        with mock.patch.object(batch, 'fetch_bounded', side_effect=lambda url, *a, **kw: payloads[url]), \
                mock.patch.object(batch, 'csv_audit', return_value=dict(rows=400, rdkit='2026.03.3', duplicate_identity_rows=[])):
            result = batch.audit_outputs(self.manifest, self.branch, api)
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['scope'], 'fast_static_no_visible_model_execution')
        self.assertFalse(result['competition_submission_performed'])
        self.assertNotIn('https://', json.dumps(result))
        batch.audited_local(self.manifest, self.branch)
        (self.state/'outputs/submission.csv').write_text('tampered')
        with self.assertRaises(ValueError): batch.audited_local(self.manifest, self.branch)

    def test_declared_kernel_dependencies_are_allowed_but_undeclared_are_rejected(self):
        self.meta['kernel_sources'] = ['trainer/public-weights/2']
        self.write(self.stage/'kernel-metadata.json', self.meta)
        self.branch['metadata_sha256'] = batch.sha(self.stage/'kernel-metadata.json')
        self.cloud(); api, _ = self.api(); self.remote.metadata.kernel_data_sources = ['trainer/public-weights']
        self.assertTrue(batch.live_binding(self.manifest, self.branch, api)['checks']['kernel_sources'])
        self.remote.metadata.kernel_data_sources.append('other/unknown')
        with self.assertRaises(ValueError): batch.live_binding(self.manifest, self.branch, api)

    def test_title_derived_slug_can_be_reconciled_only_by_exact_readback(self):
        self.cloud('server_response_requires_review_no_retry'); api, _ = self.api()
        actual = 'stormseye/title-derived-public-slug'
        self.remote.metadata.ref = actual
        result = batch.reconcile_target(self.manifest, self.branch, actual, api)
        receipt = batch.read(self.state/'cloud.json')
        self.assertEqual(result['actual_target'], actual)
        self.assertEqual(receipt['target'], self.target)
        self.assertEqual(receipt['actual_target'], actual)
        self.assertEqual(receipt['status'], 'run_requested')
        self.assertEqual(receipt['branch_sha256'], batch.branch_sha(self.branch))
        self.assertEqual(batch.live_binding(self.manifest, self.branch, api)['actual_target'], actual)
        api.kernels_status.assert_called_with(actual+'/1')
        with self.assertRaises(RuntimeError): batch.launch(self.manifest, self.branch, api)
        api.kernels_push.assert_not_called()

    def test_wrong_source_reconciliation_never_binds_actual_target(self):
        self.cloud('server_response_requires_review_no_retry'); api, _ = self.api()
        self.remote.metadata.ref = 'stormseye/title-derived-public-slug'
        changed = json.loads(self.remote.blob.source); changed['cells'][0]['source'] = 'wrong=999\n'
        self.remote.blob.source = json.dumps(changed)
        with self.assertRaises(ValueError): batch.reconcile_target(self.manifest, self.branch, self.remote.metadata.ref, api)
        self.assertNotIn('actual_target', batch.read(self.state/'cloud.json'))
        api.kernels_push.assert_not_called()

    def test_submit_uses_reconciled_actual_cloud_slug(self):
        self.cloud('server_response_requires_review_no_retry'); api, _ = self.api()
        actual = 'stormseye/title-derived-public-slug'; self.remote.metadata.ref = actual
        batch.reconcile_target(self.manifest, self.branch, actual, api)
        with mock.patch.object(batch, 'audited_local', return_value=dict(submission_sha256='a'*64)):
            result = batch.submit(self.manifest, self.branch, api)
        self.assertEqual(result['actual_target'], actual)
        self.assertEqual(result['target'], self.target)
        self.assertEqual(api.competition_submit_code.call_args.kwargs['kernel'], actual)
