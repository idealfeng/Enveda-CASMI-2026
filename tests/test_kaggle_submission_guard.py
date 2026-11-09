"""Exercise duplicate prevention and version binding without any network request."""
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase, mock
import json
import tempfile

from scripts import kaggle_first_submission as action


class SubmissionGuardTests(TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=action.ROOT / '.cache/tmp')
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.receipt = self.base / 'receipt.json'
        self.verify = self.base / 'verify.json'
        self.verify.write_text('{"status":"passed"}', encoding='utf-8')
        for name, value in [('RECEIPT', self.receipt), ('VERIFY', self.verify)]:
            patch = mock.patch.object(action, name, value)
            patch.start()
            self.addCleanup(patch.stop)

    def test_existing_claim_prevents_all_api_calls(self):
        self.receipt.write_text('{"status":"request_outcome_unknown_no_retry"}')
        with mock.patch.object(action, 'make_api') as make_api:
            with self.assertRaises(RuntimeError):
                action.submit_once()
            make_api.assert_not_called()

    def configured_api(self):
        api = mock.MagicMock()
        api.kernels_status.return_value = SimpleNamespace(status=SimpleNamespace(name='COMPLETE'), failure_message='')
        api.competition_submissions.return_value = []
        api.competition_get_submission_limits.return_value = SimpleNamespace(num_allowed_now=5, num_today=0, num_total=0)
        api.build_kaggle_client.return_value.__enter__.return_value.kernels.kernels_api_client.get_kernel.return_value = SimpleNamespace(
            metadata=SimpleNamespace(ref=action.TARGET, is_private=True, enable_internet=False),
            blob=SimpleNamespace(source='reviewed'))
        api._kernel_version_label.return_value = 'v2'
        return api

    def test_claim_precedes_single_version_bound_submission(self):
        api = self.configured_api()

        def respond(**kwargs):
            claim = json.loads(self.receipt.read_text())
            self.assertEqual(claim['status'], 'requesting_once')
            self.assertEqual(kwargs['kernel_version'], 2)
            self.assertEqual(kwargs['kernel'], action.TARGET)
            self.assertEqual(kwargs['file_name'], 'submission.csv')
            return SimpleNamespace(ref=123, message='accepted')

        api.competition_submit_code.side_effect = respond
        with mock.patch.object(action, 'local_preflight', return_value={}), \
             mock.patch.object(action, 'make_api', return_value=api), \
             mock.patch.object(action, 'ORIGINAL_SHA', action.sha(b'reviewed')):
            self.assertEqual(action.submit_once()['submission_ref'], 123)
        api.competition_submit_code.assert_called_once()
        request = api.build_kaggle_client.return_value.__enter__.return_value.kernels.kernels_api_client.get_kernel.call_args.args[0]
        self.assertEqual(request.version_label, 'v2')

    def test_unknown_outcome_blocks_retry(self):
        api = self.configured_api()
        api.competition_submit_code.side_effect = TimeoutError()
        with mock.patch.object(action, 'local_preflight', return_value={}), \
             mock.patch.object(action, 'make_api', return_value=api), \
             mock.patch.object(action, 'ORIGINAL_SHA', action.sha(b'reviewed')):
            with self.assertRaises(TimeoutError):
                action.submit_once()
            with self.assertRaises(RuntimeError):
                action.submit_once()
        api.competition_submit_code.assert_called_once()
        self.assertEqual(json.loads(self.receipt.read_text())['status'], 'request_outcome_unknown_no_retry')

    def test_changed_remote_source_prevents_submission(self):
        api = self.configured_api()
        with mock.patch.object(action, 'local_preflight', return_value={}), \
             mock.patch.object(action, 'make_api', return_value=api):
            with self.assertRaises(ValueError):
                action.submit_once()
        self.assertFalse(self.receipt.exists())
        api.competition_submit_code.assert_not_called()

    def test_poll_never_treats_nonfinite_score_as_result(self):
        self.receipt.write_text(json.dumps(dict(target=action.TARGET, version=2,
            description=action.MESSAGE, submission_ref=123)), encoding='utf-8')
        (self.base / 'reports').mkdir()
        api = self.configured_api()
        api.build_kaggle_client.return_value.__enter__.return_value.competitions.competition_api_client.get_submission.return_value = SimpleNamespace(
            ref=123, description=action.MESSAGE, status=SimpleNamespace(name='COMPLETE'),
            public_score='NaN', error_description='', file_name='submission.csv', date=None)
        with mock.patch.object(action, 'make_api', return_value=api), \
             mock.patch.object(action, 'RESULT', self.base / 'result.json'), \
             mock.patch.object(action, 'ROOT', self.base):
            self.assertFalse(action.poll()['hidden_score_available'])
        api.competition_submit_code.assert_not_called()

    def test_unresolved_request_poll_does_not_resubmit(self):
        self.receipt.write_text(json.dumps(dict(target=action.TARGET, version=2,
            description=action.MESSAGE, status='request_outcome_unknown_no_retry')), encoding='utf-8')
        api = self.configured_api()
        with mock.patch.object(action, 'make_api', return_value=api):
            with self.assertRaises(RuntimeError):
                action.poll()
        api.competition_submit_code.assert_not_called()
