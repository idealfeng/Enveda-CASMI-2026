"""Tiny mocked process contracts; no Engine2 assets, scans, workers or models."""
from pathlib import Path
import json
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from validation import stage_process, v43_runtime_patch


class V43DurableProcessTests(unittest.TestCase):
    def fixture(self, root):
        config = {'pipeline': 'v43', 'work_root': str(root), 'active_ids': ['a'], 'e2_worker_limit': 4}
        path = root / 'validation_config.json'; path.write_text(json.dumps(config))
        text = ("import subprocess,sys,os,json\nfrom pathlib import Path\n"
                f"ENG_DIR = {str(root)!r}\nENG = {{}}\n"
                "try:\n"
                "    rr = subprocess.run([sys.executable, os.path.join(ENG_DIR, 'eng_runner.py')], capture_output=True, text=True, timeout=5, cwd=ENG_DIR)\n"
                "    print(rr.stdout[-3000:]); print(rr.stderr[-3000:])\n"
                "    rr.check_returncode()\n"
                "    ENG = json.loads(Path(ENG_DIR, 'eng_lists.json').read_text())\n"
                "except Exception as error:\n    print('upstream swallowed', repr(error))\n"
                "FOLLOWING_STAGE = True\n")
        adapted, changes = v43_runtime_patch.patch_e2_cell(text, path, config)
        return config, path, adapted, changes

    def test_nonzero_signal_fails_outside_source_catch_even_with_stale_output(self):
        with tempfile.TemporaryDirectory(dir=stage_process.ROOT / '.cache') as directory:
            root = Path(directory); _, _, adapted, changes = self.fixture(root)
            (root / 'eng_lists.json').write_text(json.dumps({'a': {}}))
            result = subprocess.CompletedProcess(['fixture'], -9, stdout='full stdout\n', stderr='full stderr\n')
            namespace = {}
            with patch.object(stage_process.subprocess, 'run', return_value=result):
                with self.assertRaisesRegex(RuntimeError, 'returncode=-9'):
                    exec(compile(adapted, 'fixture', 'exec'), namespace)
            self.assertNotIn('FOLLOWING_STAGE', namespace)
            receipt = json.loads((root / 'engine2_capture.json').read_text())
            self.assertEqual(receipt['termination_signal'], 'SIGKILL')
            self.assertEqual((root / 'engine2_capture_stdout.log').read_text(), 'full stdout\n')
            self.assertEqual((root / 'engine2_capture_stderr.log').read_text(), 'full stderr\n')
            self.assertIn('v43_e2_failfast_outside_original_catch', changes)

    def test_timeout_preserves_partial_stream_and_cannot_be_swallowed(self):
        with tempfile.TemporaryDirectory(dir=stage_process.ROOT / '.cache') as directory:
            root = Path(directory); _, _, adapted, _ = self.fixture(root)
            error = subprocess.TimeoutExpired(['fixture'], 5, output=b'partial out', stderr=b'partial err')
            with patch.object(stage_process.subprocess, 'run', side_effect=error):
                with self.assertRaisesRegex(RuntimeError, 'status=timeout'):
                    exec(compile(adapted, 'fixture', 'exec'), {})
            self.assertEqual((root / 'engine2_capture_stdout.log').read_text(), 'partial out')
            self.assertEqual((root / 'engine2_capture_stderr.log').read_text(), 'partial err')

    def test_zero_exit_requires_output_and_exact_ids_but_allows_empty_retrieval(self):
        with tempfile.TemporaryDirectory(dir=stage_process.ROOT / '.cache') as directory:
            root = Path(directory); _, _, adapted, _ = self.fixture(root)
            result = subprocess.CompletedProcess(['fixture'], 0, stdout='', stderr='')
            with patch.object(stage_process.subprocess, 'run', return_value=result):
                with self.assertRaisesRegex(RuntimeError, 'output is missing'):
                    exec(compile(adapted, 'fixture', 'exec'), {})
            expected = {'a': {'smiles': [], 'keys': []}}
            (root / 'eng_lists.json').write_text(json.dumps(expected))
            namespace = {}
            with patch.object(stage_process.subprocess, 'run', return_value=result):
                exec(compile(adapted, 'fixture', 'exec'), namespace)
            self.assertTrue(namespace['FOLLOWING_STAGE'])
            self.assertEqual(namespace['ENG'], expected)
            self.assertEqual(json.loads((root / 'engine2_capture_success.json').read_text())['status'], 'passed')

    def test_generated_runner_resource_hook_preserves_original_call(self):
        with tempfile.TemporaryDirectory(dir=stage_process.ROOT / '.cache') as directory:
            root = Path(directory); config, path, _, _ = self.fixture(root)
            source = "if __name__ == '__main__':\n    import casmi_engine as E\n    install_e2(E, 'fixture')\n    result = E.main('unchanged', workers=32, w_pv=0.88)\n"
            result, metadata = v43_runtime_patch.patch_runner_resources(source, path, config)
            self.assertIn("result = E.main('unchanged', workers=32, w_pv=0.88)", result)
            self.assertIn('worker_limit=4', result)
            self.assertEqual(metadata['worker_limit'], 4)
            self.assertTrue(metadata['original_map_order_preserved'])


if __name__ == '__main__':
    unittest.main()
