"""Durable diagnostics for NEW V43 subprocess calls, outside swallowed errors.

No processes start on import. A caller must explicitly invoke capture_stage.
"""
from __future__ import annotations

from pathlib import Path
import hashlib
import json
import signal
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def _text(value) -> str:
    return value.decode('utf-8', errors='replace') if isinstance(value, bytes) else value or ''


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_helper_hashes(config: dict) -> None:
    for name, expected in config.get('v43_runtime_helpers_sha256', {}).items():
        path = (ROOT / name).resolve()
        if not path.is_relative_to(ROOT) or _sha(path) != expected:
            raise ValueError('V43 runtime helper changed after configuration: ' + name)


def _paths(config_path, stage):
    if stage not in ('engine2', 'pubchem'):
        raise ValueError('Unexpected subprocess stage name')
    config = json.loads(Path(config_path).read_text(encoding='utf-8'))
    work = Path(config['work_root']).resolve()
    if not work.is_relative_to(ROOT):
        raise ValueError('Subprocess diagnostics must remain inside D-drive workspace')
    return config, work, {key: work / f'{stage}_capture{suffix}' for key, suffix in
                         [('stdout', '_stdout.log'), ('stderr', '_stderr.log'), ('receipt', '.json')]}


def capture_stage(command, *, config_path, stage, **kwargs):
    """Return the original CompletedProcess; persist full failures before rethrow.

    Nonzero status intentionally returns normally. require_success is inserted
    AFTER the original Notebook catch so the source cannot swallow the failure.
    """
    config, work, paths = _paths(config_path, stage)
    check_helper_hashes(config)
    if kwargs.get('capture_output') is not True or kwargs.get('text') is not True:
        raise ValueError('Expected the original text/capture_output subprocess contract')
    record = {'status': 'running', 'stage': stage, 'command': [str(item) for item in command],
              'cwd': str(kwargs.get('cwd', work)), 'timeout_seconds': kwargs.get('timeout'),
              'returncode': None, 'started_time_ns': time.time_ns(), 'config_sha256': _sha(Path(config_path)),
              'helper_sha256': _sha(Path(__file__))}
    def save(stdout='', stderr=''):
        paths['stdout'].write_text(_text(stdout), encoding='utf-8')
        paths['stderr'].write_text(_text(stderr), encoding='utf-8')
        record.update(stdout_sha256=_sha(paths['stdout']), stderr_sha256=_sha(paths['stderr']),
                      stdout_bytes=paths['stdout'].stat().st_size, stderr_bytes=paths['stderr'].stat().st_size)
        temporary = paths['receipt'].with_suffix('.json.tmp')
        temporary.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
        temporary.replace(paths['receipt'])
    save(); started = time.monotonic()
    try:
        result = subprocess.run(command, **kwargs)
    except subprocess.TimeoutExpired as error:
        record.update(status='timeout', error=repr(error), elapsed_seconds=round(time.monotonic() - started, 3))
        save(error.stdout, error.stderr)
        raise
    except BaseException as error:
        record.update(status='interrupted_or_failed_to_start', error=repr(error), elapsed_seconds=round(time.monotonic() - started, 3))
        save()
        raise
    record.update(status='returned', returncode=result.returncode, elapsed_seconds=round(time.monotonic() - started, 3))
    if result.returncode < 0:
        record['termination_signal_number'] = -result.returncode
        try:
            record['termination_signal'] = signal.Signals(-result.returncode).name
        except ValueError:
            # The helper is exercised by CPU-only tests on Windows, whose enum
            # omits several POSIX signal names. Real V43 runs are Linux only.
            record['termination_signal'] = {9: 'SIGKILL', 15: 'SIGTERM', 2: 'SIGINT'}.get(-result.returncode, str(-result.returncode))
    save(result.stdout, result.stderr)
    return result


def require_success(*, config_path, stage, output, expected_ids) -> dict:
    """Must execute outside the original Notebook's broad try/except."""
    config, work, paths = _paths(config_path, stage)
    if not paths['receipt'].is_file():
        raise RuntimeError(f'{stage} did not produce process diagnostics; stopping before fallback')
    record = json.loads(paths['receipt'].read_text(encoding='utf-8'))
    if record.get('status') != 'returned' or record.get('returncode') != 0:
        raise RuntimeError(f"{stage} subprocess failed: status={record.get('status')}, returncode={record.get('returncode')}, "
                           f"signal={record.get('termination_signal')}; full diagnostics: {paths['receipt']}")
    if record.get('config_sha256') != _sha(Path(config_path)):
        raise RuntimeError('Subprocess configuration changed during its run')
    for name in ('stdout', 'stderr'):
        if _sha(paths[name]) != record[name + '_sha256']:
            raise RuntimeError('Captured subprocess stream changed: ' + name)
    output = Path(output).resolve()
    if not output.is_relative_to(work) or not output.is_file():
        raise RuntimeError(f'{stage} returned zero but its expected output is missing: {output}')
    payload = json.loads(output.read_text(encoding='utf-8'))
    if not isinstance(payload, dict) or set(map(str, payload)) != set(map(str, expected_ids)):
        raise RuntimeError(f'{stage} output does not cover the exact active validation cohort')
    audit = {'status': 'passed', 'stage': stage, 'returncode': 0, 'output_sha256': _sha(output),
             'molecules': len(payload), 'empty_candidate_lists_allowed': True,
             'capture_receipt_sha256': _sha(paths['receipt'])}
    (work / f'{stage}_capture_success.json').write_text(json.dumps(audit, indent=2) + '\n', encoding='utf-8')
    return audit
