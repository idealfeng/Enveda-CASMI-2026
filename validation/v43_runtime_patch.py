"""Isolated source patches for a fresh V43 run; not imported by active Flex."""
from __future__ import annotations

from pathlib import Path
import ast
import hashlib

from .stage_process import check_helper_hashes

ROOT = Path(__file__).resolve().parents[1]


def _is_e2_subprocess(node):
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name) and node.func.value.id == 'subprocess'
            and node.func.attr == 'run'
            and any(isinstance(value, ast.Constant) and isinstance(value.value, str) and 'eng_runner.py' in value.value
                    for value in ast.walk(node)))


def patch_e2_cell(text: str, config_path: str | Path, config: dict) -> tuple[str, list]:
    if config.get('pipeline') != 'v43':
        raise ValueError('This source patch is exclusive to fresh V43 runs')
    check_helper_hashes(config)
    calls = [node for node in ast.walk(ast.parse(text)) if _is_e2_subprocess(node)]
    if len(calls) != 1:
        raise ValueError('Expected exactly one generated E2 subprocess call')
    original_call = ast.get_source_segment(text, calls[0])
    changed = calls[0]
    changed.func = ast.Attribute(value=ast.Name(id='_v43_stage_process', ctx=ast.Load()), attr='capture_stage', ctx=ast.Load())
    changed.keywords += [ast.keyword(arg='config_path', value=ast.Constant(str(config_path))),
                         ast.keyword(arg='stage', value=ast.Constant('engine2'))]
    adapted = text.replace(original_call, ast.unparse(changed), 1)
    adapted = 'from validation import stage_process as _v43_stage_process\n' + adapted
    tree = ast.parse(adapted)
    tries = [node for node in tree.body if isinstance(node, ast.Try)
             and any(isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                     and isinstance(call.func.value, ast.Name) and call.func.value.id == '_v43_stage_process'
                     and call.func.attr == 'capture_stage' for call in ast.walk(node))]
    if len(tries) != 1:
        raise ValueError('Expected the original top-level E2 try/except wrapper')
    verify = (f"_v43_stage_process.require_success(config_path={str(config_path)!r}, stage='engine2', "
              f"output={str(Path(config['work_root']) / 'eng_lists.json')!r}, expected_ids={config['active_ids']!r})\n")
    lines = adapted.splitlines(keepends=True)
    lines.insert(tries[0].end_lineno, verify)
    result = ''.join(lines)
    compile(result, 'v43_e2_durable_failfast', 'exec')
    return result, ['v43_durable_e2_stdout_stderr_returncode', 'v43_e2_failfast_outside_original_catch']


def patch_runner_resources(text: str, config_path: str | Path, config: dict) -> tuple[str, dict]:
    if config.get('pipeline') != 'v43':
        raise ValueError('Worker-limit hook is exclusive to fresh V43 runs')
    check_helper_hashes(config)
    cap = config.get('e2_worker_limit', 4)
    if not isinstance(cap, int) or isinstance(cap, bool) or cap < 1:
        raise ValueError('e2_worker_limit must be a positive integer')
    calls = [node for node in ast.walk(ast.parse(text)) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Name) and node.func.id == 'install_e2']
    if len(calls) != 1:
        raise ValueError('Install resource hook after exactly one reference-isolation hook')
    lines = text.splitlines(keepends=True)
    indent = ' ' * calls[0].col_offset
    lines.insert(calls[0].end_lineno, indent + 'from validation.e2_resources import install as _install_e2_resources\n'
                 + indent + f'_install_e2_resources(E, {str(config_path)!r}, worker_limit={cap})\n')
    result = ''.join(lines)
    compile(result, 'v43_e2_worker_bound', 'exec')
    return result, {'worker_limit': cap, 'resource_only': True, 'original_map_order_preserved': True,
                    'helper_sha256': hashlib.sha256((ROOT / 'validation/e2_resources.py').read_bytes()).hexdigest()}
