"""Bounded read-only watcher tests: no real Kaggle client or wall-clock waiting."""
from pathlib import Path
from unittest import TestCase, mock
import importlib.util
import json
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('tri_watcher_tested', ROOT/'scripts/watch_public_tri_submission.py')
watcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watcher)


class WatcherTests(TestCase):
    def setUp(self):
        temporary = ROOT/'.cache/tmp'
        temporary.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=temporary)
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.receipt = self.base/'receipt.json'
        self.receipt.write_text(json.dumps(dict(target=watcher.TARGET, version=1, status='accepted', submission_ref=123)), encoding='utf-8')
        self.options = dict(receipt_path=self.receipt, state_path=self.base/'state.json', lock_path=self.base/'watch.lock')
        self.elapsed = 0
        self.sleeps = []

    def result(self, status, **extra):
        return dict(target=watcher.TARGET, version=1, submission_ref=123, status=status, public_score=None, **extra)

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.elapsed += seconds

    def test_stops_complete_fixed_ref_without_waiting_again(self):
        poller = mock.Mock(side_effect=[self.result('PENDING'), dict(self.result('COMPLETE'), public_score='0.48')])
        code, record = watcher.run_watch(poller=poller, clock=lambda: self.elapsed, sleeper=self.sleep, **self.options)
        self.assertEqual(code, 0)
        self.assertEqual(self.sleeps, [45])
        self.assertEqual(poller.call_count, 2)
        self.assertTrue(record['public_score_available'])
        self.assertFalse(self.options['lock_path'].exists())

    def test_timeout_and_error_details_are_bounded_and_sanitized(self):
        poller = mock.Mock(side_effect=RuntimeError('secret https://signed.example?credential=bad'))
        code, record = watcher.run_watch(max_seconds=50, poller=poller, clock=lambda: self.elapsed,
                                         sleeper=self.sleep, **self.options)
        self.assertEqual(code, 2)
        self.assertEqual(self.sleeps, [45, 5])
        self.assertEqual(record['last_error'], {'error_type': 'RuntimeError'})
        self.assertNotIn('secret', self.options['state_path'].read_text())

    def test_rejects_duplicate_watcher_and_changed_ref(self):
        self.options['lock_path'].write_text('existing', encoding='utf-8')
        poller = mock.Mock()
        with self.assertRaises(FileExistsError):
            watcher.run_watch(poller=poller, **self.options)
        poller.assert_not_called()
        self.options['lock_path'].unlink()
        poller.return_value = dict(self.result('COMPLETE'), submission_ref=456)
        code, record = watcher.run_watch(poller=poller, **self.options)
        self.assertEqual((code, record['status']), (1, 'identity_mismatch'))

    def test_rejects_unknown_ref_and_overlong_duration_before_poll(self):
        poller = mock.Mock()
        self.receipt.write_text(json.dumps(dict(target=watcher.TARGET, version=1)), encoding='utf-8')
        with self.assertRaises(ValueError):
            watcher.run_watch(poller=poller, **self.options)
        with self.assertRaises(ValueError):
            watcher.run_watch(max_seconds=watcher.MAX_SECONDS+1, poller=poller, **self.options)
        poller.assert_not_called()
