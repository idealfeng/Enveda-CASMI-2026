"""Offline fixtures for the read-only bounded batch watcher and legacy defaults."""
from pathlib import Path
from unittest import TestCase, mock
import json
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import kaggle_batch as batch
import watch_kaggle_batch_20261107 as watcher


class WatchTests(TestCase):
    def setUp(self):
        (ROOT/'.cache/tmp').mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=ROOT/'.cache/tmp'); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for module in (batch, watcher):
            patch = mock.patch.object(module, 'ROOT', self.root); patch.start(); self.addCleanup(patch.stop)
        self.branches = [dict(name='b'+str(i), target='stormseye/test-batch-'+str(i), version=1,
            description='unique test branch '+str(i), stage_dir='stage'+str(i), notebook_sha256='a'*64,
            metadata_sha256='b'*64, validation_mode='fast_static', required_runtime_audits=[
                dict(name='audit.json', required_true_checks=['prepared'], expected_fields=dict(mode='fast_static'))]) for i in range(4)]
        self.manifest = dict(schema_version=1, batch_id='fixture', competition=batch.COMPETITION,
            max_submissions=4, state_root='state', branches=self.branches)
        self.path = self.root/'manifest.json'; self.path.write_text(json.dumps(self.manifest))

    def receipt(self, index, status='accepted', ref=None):
        branch = self.branches[index]; state = batch.branch_state(self.manifest, branch); state.mkdir(parents=True, exist_ok=True)
        core = dict(target=branch['target'], version=1, branch_sha256=batch.branch_sha(branch))
        (state/'cloud.json').write_text(json.dumps(dict(core, status='run_requested')))
        record = dict(core, status=status, competition=batch.COMPETITION, output_file='submission.csv',
            description=branch['description'], submission_ref=index+100 if ref is None else ref)
        (state/'submission.json').write_text(json.dumps(record))

    def result(self, branch, status='COMPLETE', score='0.481'):
        return dict(target=branch['target'], actual_target=branch['target'], version=1,
            submission_ref=int(branch['name'][1:])+100, status=status, public_score=score,
            error_description_present=False, checked_at_utc='fixture')

    def test_only_accepted_positive_refs_are_polled_and_best_is_finite(self):
        self.receipt(1, 'request_outcome_unknown_no_retry', ref=0)
        self.receipt(2); self.receipt(3, 'accepted_reconciled_by_unique_description')
        calls = []
        def poll(manifest, branch):
            calls.append(branch['name'])
            return self.result(branch, score='0.481' if branch['name']=='b2' else 'NaN')
        snapshot = watcher.snapshot(self.manifest, poller=poll)
        self.assertEqual(calls, ['b2','b3'])
        self.assertEqual(snapshot['branches'][0]['status'], 'not_submitted')
        self.assertEqual(snapshot['branches'][1]['status'], 'awaiting_submission_identity')
        self.assertIsNone(snapshot['branches'][3]['public_score'])
        self.assertEqual(snapshot['best_this_batch']['branch'], 'b2')
        self.assertEqual(snapshot['best_overall_public_score'], 0.481)
        self.assertFalse(snapshot['new_run_or_submission_performed'])

    def test_terminal_cache_exclusive_lock_and_all_four_stop(self):
        for i in range(4): self.receipt(i)
        calls = {}; virtual = [0.]
        def poll(manifest, branch):
            name = branch['name']; calls[name] = calls.get(name,0)+1
            if name=='b3' and calls[name]==1: return self.result(branch, status='PENDING', score=None)
            return self.result(branch, score='0.475' if name!='b3' else '0.482')
        def sleep(seconds): virtual[0] += seconds
        code, result = watcher.run_watch(self.path, max_seconds=60, poller=poll,
            clock=lambda:virtual[0], sleeper=sleep)
        self.assertEqual(code, 0); self.assertEqual(result['status'], 'finished')
        self.assertEqual(calls, dict(b0=1,b1=1,b2=1,b3=2))
        self.assertEqual(result['best_this_batch']['public_score'], 0.482)
        self.assertFalse((self.root/'state/watcher.lock').exists())
        (self.root/'state/watcher.lock').write_text('already running')
        with self.assertRaises(FileExistsError): watcher.run_watch(self.path, max_seconds=60, poller=poll)

    def test_legacy_four_branches_keep_default_baseline_and_state_root(self):
        for i in range(4): self.receipt(i)
        code, result = watcher.run_watch(self.path, max_seconds=60,
            poller=lambda manifest, branch:self.result(branch, score='0.475'))
        self.assertEqual(code, 0)
        self.assertEqual(result['baseline_public_score'], 0.479)
        self.assertEqual(result['best_overall_public_score'], 0.479)
        self.assertEqual(len(result['branches']), 4)
        self.assertTrue((self.root/'state/latest_status.json').is_file())
        self.assertFalse((self.root/'state/watcher.lock').exists())
        self.assertTrue(result['read_only'])
        self.assertFalse(result['new_run_or_submission_performed'])

    def test_five_branches_use_manifest_baseline_and_separate_state_root(self):
        fifth = dict(self.branches[-1], name='b4', target='stormseye/test-batch-4',
            description='unique test branch 4', stage_dir='stage4')
        self.branches.append(fifth)
        self.manifest.update(max_submissions=5, baseline_public_score=0.481, state_root='new_state')
        self.path.write_text(json.dumps(self.manifest))
        for i in range(5): self.receipt(i)
        code, result = watcher.run_watch(self.path, max_seconds=60,
            poller=lambda manifest, branch:self.result(branch, score='0.480'))
        self.assertEqual(code, 0)
        self.assertEqual(result['baseline_public_score'], 0.481)
        self.assertEqual(result['best_this_batch']['public_score'], 0.480)
        self.assertEqual(result['best_overall_public_score'], 0.481)
        self.assertEqual(len(result['branches']), 5)
        self.assertTrue((self.root/'new_state/latest_status.json').is_file())
        self.assertFalse((self.root/'state').exists())
        self.assertFalse((self.root/'new_state/watcher.lock').exists())
        self.assertTrue(result['read_only'])
        self.assertFalse(result['new_run_or_submission_performed'])
