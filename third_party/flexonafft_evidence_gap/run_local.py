"""Run a path-adapted copy of the exact public notebook, retaining originals.

Linux Python 3.12 is required by the bundled simulator wheels. The default is the
upstream visible-test smoke path. This runner does not claim a leaderboard score.
"""
from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import time
import traceback

from extract_sources import literals

HERE = Path(__file__).resolve().parent


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def get_source(cell):
    value = cell['source']
    return ''.join(value) if isinstance(value, list) else value


def make_input_view(asset_root, work_root, competition_dir, prepare_only):
    """Expose owner/slug/vN stores through the exact layout expected upstream."""
    plan = json.loads((HERE / 'minimum_download_plan.json').read_text(encoding='utf-8'))
    versions = {row['dataset']: row['version'] for row in plan['files']}
    view = work_root / 'input_view'
    links = []
    for slug, version in versions.items():
        target = asset_root / slug / f'v{version}'
        link = view / 'datasets' / slug
        links.append((link, target))
    links.append((view / 'competitions' / 'enveda-CASMI26-molecule-id-mass-spectra', competition_dir))
    missing = [str(target) for _, target in links if not target.is_dir()]
    file_views = []
    if not prepare_only and missing:
        raise FileNotFoundError('Required pinned input directories missing: ' + ', '.join(missing))
    if sys.platform == 'linux':
        for link, target in links:
            if not target.is_dir():
                continue
            link.parent.mkdir(parents=True, exist_ok=True)
            if link.relative_to(view).as_posix() == 'datasets/sanpier/casmi-spectrum-model-v1':
                # pathlib.Path.rglob() does not descend directory symlinks on
                # Python 3.12. The upstream bundle finder must see real parent
                # directories; link only the five already downloaded leaf files.
                if link.is_symlink():
                    if link.resolve() != target.resolve():
                        raise RuntimeError(f'Existing model-bundle link points elsewhere: {link}')
                    assert link.absolute().is_relative_to(view.absolute())
                    link.unlink()  # only the workspace input-view symlink
                elif link.exists() and not link.is_dir():
                    raise RuntimeError(f'Model-bundle view is not a directory: {link}')
                link.mkdir(exist_ok=True)
                for row in plan['files']:
                    if row['dataset'] != 'sanpier/casmi-spectrum-model-v1':
                        continue
                    source = target / row['file']
                    destination = link / row['file']
                    assert destination.absolute().is_relative_to(view.absolute())
                    if not source.is_file():
                        if prepare_only:
                            continue
                        raise FileNotFoundError(source)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    if destination.exists() or destination.is_symlink():
                        if destination.resolve() != source.resolve():
                            raise RuntimeError(f'Existing model file points elsewhere: {destination}')
                    else:
                        destination.symlink_to(source.resolve())
                    file_views.append({'link': str(destination), 'target': str(source)})
                continue
            if link.is_symlink() or link.exists():
                if link.resolve() != target.resolve():
                    raise RuntimeError(f'Existing input link points elsewhere: {link}')
            else:
                link.symlink_to(target.resolve(), target_is_directory=True)
    (work_root / 'input_layout.json').write_text(json.dumps({
        'asset_store': str(asset_root), 'view': str(view),
        'links': [{'link': str(link), 'target': str(target)} for link, target in links],
        'model_bundle_leaf_file_links': file_views,
        'missing_directories': missing,
        'note': 'Symlinks are materialized on Linux only. All targets stay in the configured workspace.',
    }, indent=2) + '\n', encoding='utf-8')
    return view


def build_adapted(version, input_root, work_root, smoke_molecules, shared_spec_cache=None):
    original_path = HERE / version / 'original.ipynb'
    raw = original_path.read_bytes()
    notebook = json.loads(raw)
    values = {}
    source_cell_index = None
    for index, cell in enumerate(notebook['cells']):
        if cell.get('cell_type') == 'code':
            found = literals(get_source(cell))
            values.update(found)
            if 'FROZEN_B64' in found:
                source_cell_index = index
    assert source_cell_index is not None
    frozen_raw = base64.b64decode(values['FROZEN_B64'])
    assert digest(frozen_raw) == values['FROZEN_SHA256']
    for name, code in values['MODULES'].items():
        assert digest(code.encode('utf-8')) == values['MODULE_SHA256'][name]

    replacements = [('/kaggle/working', work_root.as_posix()),
                    ('/kaggle/input', input_root.as_posix())]

    def replace_paths(code):
        for old, new in replacements:
            code = code.replace(old, new)
        return code

    def adapt_code(code):
        # Embedded source strings have their own assertions. Retain those checks
        # against their adapted content, while recording original hashes below.
        hash_rewrites = {}
        for node in ast.walk(ast.parse(code)):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                value = node.value
                changed = replace_paths(value)
                if changed != value:
                    hash_rewrites[digest(value.encode('utf-8'))] = digest(changed.encode('utf-8'))
        # The input view uses symlinks. The upstream observer resolves COMP
        # before comparing it against lexical mount paths; compare resolved
        # allowed paths too, without weakening the allowed-location check.
        result = code.replace(
            "assert comp in {f'/kaggle/input/{slug}', f'/kaggle/input/competitions/{slug}'}",
            "assert comp in {os.path.realpath(f'/kaggle/input/{slug}'), os.path.realpath(f'/kaggle/input/competitions/{slug}')}"
        )
        result = replace_paths(result)
        for old_hash, new_hash in hash_rewrites.items():
            result = result.replace(old_hash, new_hash)
        return result

    frozen = json.loads(frozen_raw)
    io_receipt = None
    if shared_spec_cache is not None:
        helper_path = HERE.parents[1] / 'scripts' / 'reproduction_io.py'
        helper_sha256 = digest(helper_path.read_bytes())
        marker_path = shared_spec_cache / 'cache_complete.json'
        marker_sha256 = digest(marker_path.read_bytes()) if marker_path.is_file() else None
        io_receipt = {
            'shared_spec_cache': shared_spec_cache.as_posix(),
            'shared_cache_receipt_sha256_at_prepare': marker_sha256,
            'helper': helper_path.as_posix(), 'helper_sha256': helper_sha256,
            'changes': ['Reuse four verified clean-CSR files instead of rebuilding them.',
                        "Library CSR and Pool numeric arrays use module-local mmap_mode='c'.",
                        "The main train_fp_sel.npy load uses mmap_mode='c'."],
            'algorithm_changes': False,
        }
        install_io = '\n'.join([
            '# Local IO adapter: source manifests have already been verified upstream.',
            'import importlib.util as _local_io_util',
            f'_local_io_path = Path({helper_path.as_posix()!r})',
            f'assert hashlib.sha256(_local_io_path.read_bytes()).hexdigest() == {helper_sha256!r}',
            "_local_io_spec = _local_io_util.spec_from_file_location('casmi_reproduction_io', _local_io_path)",
            '_local_io_module = _local_io_util.module_from_spec(_local_io_spec)',
            '_local_io_spec.loader.exec_module(_local_io_module)',
            f'_local_io_receipt = _local_io_module.install_shared_cache(V4CODE, {shared_spec_cache.as_posix()!r}, mmap_pool=True)',
            f"Path({(work_root / 'shared_cache_runtime_receipt.json').as_posix()!r}).write_text(json.dumps(_local_io_receipt, indent=2) + '\\n', encoding='utf-8')",
            "print('LOCAL_IO_ADAPTATION', json.dumps(_local_io_receipt), flush=True)",
        ])
        build_call = "from casmi.build import build_spec_cache\nbuild_spec_cache(os.path.join(COMP, 'train.parquet'), 'work')"
        matches = [cell for cell in frozen['cells'] if cell.get('cell_type') == 'code' and build_call in get_source(cell)]
        assert len(matches) == 1, 'Expected one exact full-spectrum cache construction call'
        matches[0]['source'] = get_source(matches[0]).replace(build_call, install_io + '\n' + build_call, 1)
        tfp_call = "tfp = np.load('work/train_fp_sel.npy')"
        tfp_matches = [cell for cell in frozen['cells'] if cell.get('cell_type') == 'code' and tfp_call in get_source(cell)]
        assert len(tfp_matches) == 1, 'Expected one exact train fingerprint load'
        tfp_matches[0]['source'] = get_source(tfp_matches[0]).replace(
            tfp_call, "tfp = np.load('work/train_fp_sel.npy', mmap_mode='c')", 1)
    for cell in frozen['cells']:
        if cell.get('cell_type') == 'code':
            source = adapt_code(get_source(cell))
            if smoke_molecules != 12:
                source = source.replace('SMOKE_N = 12', f'SMOKE_N = {smoke_molecules}')
            cell['source'] = source
            cell['outputs'] = []
            cell['execution_count'] = None
    frozen_adapted = json.dumps(frozen, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    modules = {name: adapt_code(code) for name, code in values['MODULES'].items()}
    module_hashes = {name: digest(code.encode('utf-8')) for name, code in modules.items()}
    source_cell = '\n'.join([
        '# Original embedded sources verified; only workspace paths adapted.',
        'MODULES = ' + repr(modules),
        'MODULE_SHA256 = ' + repr(module_hashes),
        'MODEL_PINS = ' + repr(values['MODEL_PINS']),
        'FROZEN_SHA256 = ' + repr(digest(frozen_adapted)),
        'FROZEN_B64 = ' + repr(base64.b64encode(frozen_adapted).decode('ascii')),
    ])
    for index, cell in enumerate(notebook['cells']):
        if cell.get('cell_type') != 'code':
            continue
        cell['source'] = source_cell if index == source_cell_index else adapt_code(get_source(cell))
        cell['outputs'] = []
        cell['execution_count'] = None
        compile(cell['source'], f'flexonafft-{version}-cell-{index}', 'exec')
    receipt = {
        'upstream': 'flexonafft/casmi26-closing-the-evidence-gap',
        'version': version,
        'original_notebook_sha256': digest(raw),
        'original_frozen_sha256': digest(frozen_raw),
        'adapted_frozen_sha256': digest(frozen_adapted),
        'original_module_sha256': values['MODULE_SHA256'],
        'adapted_module_sha256': module_hashes,
        'model_pins_unchanged': values['MODEL_PINS'],
        'changes': {'path_replacements': replacements, 'smoke_molecules': smoke_molecules,
                    'preflight_allowed_locations_compared_by_realpath': True,
                    'model_bundle_view': 'Regular Saner parent directories with leaf-file links, compatible with upstream Path.rglob().',
                    'io_adaptation': io_receipt,
                    'outputs_cleared': True, 'ranking_or_model_parameters_changed': False},
        'limitation': 'Path adaptation is not yet a parity proof. Visible smoke scores are not generalization or leaderboard scores.',
    }
    return notebook, receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', choices=['v56', 'v61'], default='v56')
    parser.add_argument('--input-root', type=Path, required=True)
    parser.add_argument('--work-root', type=Path, required=True)
    parser.add_argument('--competition-dir', type=Path,
                        default=HERE.parents[1] / 'enveda-CASMI26-molecule-id-mass-spectra')
    parser.add_argument('--smoke-molecules', type=int, default=12)
    parser.add_argument('--shared-spec-cache', type=Path,
                        help='Reuse a completed, source-verified full clean-CSR cache; use copy-on-write mmap for numeric library/pool arrays.')
    parser.add_argument('--full', action='store_true', help='Run all visible molecules; potentially hours. No hidden data is available locally.')
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--materialise-only', action='store_true',
                        help='Run stage-0 source/model-pin/RDKit bootstrap checks, then stop before any model inference.')
    args = parser.parse_args()
    assert args.smoke_molecules > 0
    asset_root, work_root = args.input_root.resolve(), args.work_root.resolve()
    work_root.mkdir(parents=True, exist_ok=True)
    input_root = make_input_view(asset_root, work_root, args.competition_dir.resolve(), args.prepare_only)
    shared_spec_cache = args.shared_spec_cache.resolve() if args.shared_spec_cache else None
    notebook, receipt = build_adapted(args.version, input_root, work_root, args.smoke_molecules, shared_spec_cache)
    run_source = work_root / f'adapted_{args.version}.ipynb'
    run_source.write_text(json.dumps(notebook, ensure_ascii=False, indent=1), encoding='utf-8')
    receipt['adapted_notebook_sha256'] = digest(run_source.read_bytes())
    receipt['execution_mode'] = 'full visible test' if args.full else 'upstream visible smoke'
    if args.materialise_only:
        receipt['execution_mode'] = 'stage-0 materialisation only; no inference'
    receipt['source_mode_effects'] = {
        'upstream_rerun_flag_emulated': args.full,
        'local_data_remains_visible_placeholder': True,
        'active_query_count': 'all visible molecules' if args.full else args.smoke_molecules,
        'original_ice_budget_seconds': 5400 if args.full else 300,
        'original_glacier_budget_seconds': 4000,
        'figures': 'upstream full mode suppresses presentation figures' if args.full else 'upstream smoke presentation remains enabled',
    }
    receipt['python'] = platform.python_version()
    receipt['platform'] = platform.platform()
    receipt['status'] = 'prepared'
    receipt_path = work_root / 'local_reproduction_status.json'

    def save():
        receipt_path.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')

    save()
    print('Prepared source:', run_source, flush=True)
    if args.prepare_only:
        return
    if sys.platform != 'linux' or sys.version_info[:2] != (3, 12):
        raise RuntimeError('Exact bundled simulator dependencies require Linux Python 3.12; use WSL or the pinned Kaggle image.')
    if args.full:
        os.environ['KAGGLE_IS_COMPETITION_RERUN'] = '1'
    else:
        os.environ.pop('KAGGLE_IS_COMPETITION_RERUN', None)
    os.environ.setdefault('PYTHONHASHSEED', '0')
    os.environ.setdefault('PYTHONUNBUFFERED', '1')
    scope = {'__name__': '__main__', '__file__': str(run_source)}
    started = time.time()
    receipt['status'] = 'running'
    save()
    try:
        for index, cell in enumerate(notebook['cells']):
            if cell.get('cell_type') == 'code':
                if args.materialise_only and 'BUNDLE = materialise_sources()' in get_source(cell):
                    scope['BUNDLE'] = scope['materialise_sources']()
                    receipt['bundle_path'] = str(scope['BUNDLE'])
                    receipt['status'] = 'materialised'
                    receipt['last_completed_stage'] = 'Sources, exact model pins and official RDKit bootstrap'
                    break
                print(f'LOCAL NOTEBOOK CELL {index} START', flush=True)
                exec(compile(get_source(cell), f'{run_source}:cell{index}', 'exec'), scope)
                receipt['last_completed_cell'] = index
                receipt['elapsed_seconds'] = round(time.time() - started, 3)
                save()
        if receipt['status'] != 'materialised':
            receipt['status'] = 'complete'
        if (work_root / 'submission.csv').is_file():
            receipt['submission_sha256'] = digest((work_root / 'submission.csv').read_bytes())
    except BaseException as exc:
        receipt['status'] = 'failed'
        receipt['error'] = f'{type(exc).__name__}: {exc}'
        receipt['traceback'] = traceback.format_exc()
        raise
    finally:
        receipt['elapsed_seconds'] = round(time.time() - started, 3)
        save()


if __name__ == '__main__':
    main()
