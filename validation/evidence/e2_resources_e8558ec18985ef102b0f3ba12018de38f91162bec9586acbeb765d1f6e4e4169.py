"""Optional process-count/allocator bound for NEW Engine2 validation runs only.

This does not change candidates, fingerprint functions or their map order. It is
not a raw-CSR replacement and does not claim the whole run will fit in memory.
"""
from __future__ import annotations

from pathlib import Path
import ctypes
import gc
import hashlib
import json
import os
import time

ROOT = Path(__file__).resolve().parents[1]


def memory_snapshot() -> dict:
    result = {}
    status = Path('/proc/self/status')
    if status.is_file():
        for line in status.read_text().splitlines():
            if line.startswith(('VmRSS:', 'VmHWM:', 'VmSwap:', 'Threads:')):
                name, value = line.split(':', 1); result[name] = value.strip()
    return result


def release_unused_allocators() -> dict:
    """Release unreachable buffers only; live spectrum/pool arrays are untouched."""
    result = {'gc_collected': gc.collect()}
    try:
        import pyarrow as pa
        pool = pa.default_memory_pool()
        result['arrow_allocated_before'] = pool.bytes_allocated()
        pool.release_unused()
        result['arrow_allocated_after'] = pool.bytes_allocated()
    except (ImportError, AttributeError, RuntimeError) as error:
        result['arrow_release_unavailable'] = repr(error)
    if os.name == 'posix':
        try:
            libc = ctypes.CDLL(None)
            trim = libc.malloc_trim
            trim.argtypes = [ctypes.c_size_t]; trim.restype = ctypes.c_int
            result['malloc_trim_result'] = int(trim(0))
        except (AttributeError, OSError) as error:
            result['malloc_trim_unavailable'] = repr(error)
    return result


def install(engine, config_path: str | Path, worker_limit: int = 4) -> dict:
    """Wrap original build_pool for a future fresh run; never edit its source."""
    if not isinstance(worker_limit, int) or isinstance(worker_limit, bool) or worker_limit < 1:
        raise ValueError('worker_limit must be a positive integer')
    if getattr(engine, '_e2_resources_installed', False):
        raise RuntimeError('Engine2 resource hooks already installed')
    config = json.loads(Path(config_path).read_text(encoding='utf-8'))
    work = Path(config['work_root']).resolve()
    if not work.is_relative_to(ROOT):
        raise ValueError('Engine2 resource receipts must stay inside D-drive workspace')
    original = engine.build_pool
    original_main = engine.main
    destination = work / 'validation_e2_resource_policy.json'

    def save(record):
        temporary = destination.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
        temporary.replace(destination)

    def build_pool(library, workers):
        chosen = min(max(1, int(workers)), worker_limit)
        record = {'status': 'running', 'requested_workers': int(workers), 'used_workers': chosen,
                  'original_fingerprint_and_pool_algorithm_retained': True,
                  'map_order_retained': True, 'raw_spectrum_representation_changed': False,
                  'source_helper_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  'memory_before_release': memory_snapshot()}
        record['pre_pool_allocator_release'] = release_unused_allocators()
        record['memory_before_pool'] = memory_snapshot()
        save(record); started = time.monotonic()
        try:
            result = original(library, chosen)
        except BaseException as error:
            record.update(status='failed', error=repr(error), memory_after_failure=memory_snapshot(),
                          elapsed_seconds=round(time.monotonic() - started, 3))
            save(record)
            raise
        record.update(status='complete', pool_structures=len(result['keys']),
                      elapsed_seconds=round(time.monotonic() - started, 3), memory_after_pool=memory_snapshot())
        record['post_pool_allocator_release'] = release_unused_allocators()
        record['memory_after_release'] = memory_snapshot()
        save(record)
        return result

    engine.build_pool = build_pool
    def main(*args, **kwargs):
        # Upstream signature: six input arguments, then workers. Preserve every
        # other argument and original call order, including the validation hook.
        positional = list(args)
        if len(positional) > 6:
            if 'workers' in kwargs:
                raise TypeError('workers supplied both positionally and by keyword')
            requested = int(positional[6]); positional[6] = min(max(1, requested), worker_limit)
            chosen = positional[6]
        else:
            requested = int(kwargs.get('workers', 4))
            chosen = min(max(1, requested), worker_limit)
            kwargs['workers'] = chosen
        call_record = {'status': 'running', 'requested_workers': requested, 'used_workers': chosen,
                       'scope': 'All original main workers: pool fingerprints, fragments and canonicalization',
                       'ranking_parameters_changed': False, 'numeric_map_order_retained': True}
        call_path = work / 'validation_e2_worker_limit.json'
        call_path.write_text(json.dumps(call_record, indent=2) + '\n', encoding='utf-8')
        try:
            result = original_main(*positional, **kwargs)
        except BaseException as error:
            call_record.update(status='failed', error=repr(error))
            call_path.write_text(json.dumps(call_record, indent=2) + '\n', encoding='utf-8')
            raise
        call_record['status'] = 'complete'
        call_path.write_text(json.dumps(call_record, indent=2) + '\n', encoding='utf-8')
        return result
    engine.main = main
    engine._e2_resources_installed = True
    return {'worker_limit': worker_limit, 'receipt': str(destination),
            'full_run_memory_fit_verified': False,
            'note': 'Apply only before a new run. SIGKILL cannot be caught here; caller must persist subprocess returncode/stdout/stderr.'}
