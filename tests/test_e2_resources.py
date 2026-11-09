"""Small contract checks only: no original Engine2 data, subprocesses or GPU."""
from pathlib import Path
from types import SimpleNamespace
import json
import tempfile
import unittest
from unittest.mock import patch

from validation import e2_resources


class E2ResourceContracts(unittest.TestCase):
    def test_worker_bound_preserves_input_and_result_objects(self):
        with tempfile.TemporaryDirectory(dir=e2_resources.ROOT / '.cache') as temporary:
            work = Path(temporary)
            config = work / 'config.json'; config.write_text(json.dumps({'work_root': str(work)}))
            calls = []; library = object(); pool = {'keys': ['one', 'two'], 'values': object()}
            def build_pool(value, workers):
                calls.append(('pool', value, workers)); return pool
            engine = SimpleNamespace(build_pool=build_pool)
            def main(*args, **kwargs):
                calls.append(('main', args, kwargs.copy()))
                return engine.build_pool(library, kwargs['workers'])
            engine.main = main
            with patch.object(e2_resources, 'release_unused_allocators', return_value={'fixture': True}):
                e2_resources.install(engine, config, worker_limit=4)
                result = engine.main('test', 'train', 'sample', 'ours', 'pv', 'models', workers=32, w_pv=0.88)
            self.assertIs(result, pool)
            self.assertIs(calls[-1][1], library)
            self.assertEqual(calls[-1][2], 4)
            self.assertEqual(calls[0][2]['w_pv'], 0.88)
            receipt = json.loads((work / 'validation_e2_worker_limit.json').read_text())
            self.assertEqual(receipt['requested_workers'], 32)
            self.assertEqual(receipt['used_workers'], 4)
            self.assertEqual(receipt['status'], 'complete')

    def test_exception_survives_and_is_recorded(self):
        with tempfile.TemporaryDirectory(dir=e2_resources.ROOT / '.cache') as temporary:
            work = Path(temporary); config = work / 'config.json'
            config.write_text(json.dumps({'work_root': str(work)}))
            def fail(*args, **kwargs):
                raise FileNotFoundError('fixture-input-missing')
            engine = SimpleNamespace(build_pool=lambda *args: {}, main=fail)
            e2_resources.install(engine, config, worker_limit=1)
            with self.assertRaisesRegex(FileNotFoundError, 'fixture-input-missing'):
                engine.main(workers=32)
            result = json.loads((work / 'validation_e2_worker_limit.json').read_text())
            self.assertEqual(result['status'], 'failed')
            self.assertEqual(result['used_workers'], 1)

    def test_reject_invalid_worker_limit(self):
        with self.assertRaises(ValueError):
            e2_resources.install(SimpleNamespace(), 'unused', worker_limit=0)


if __name__ == '__main__':
    unittest.main()
