"""Download versioned Kaggle files listed in a static reproduction manifest.

Uses public endpoints without credentials. Keeps incomplete files separate and
records SHA-256 receipts. Does not execute downloaded notebooks or pickles.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request


ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(8 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def fetch(item: dict, asset_root: Path) -> dict:
    ref, version, name = item['ref'], item['version'], item['name']
    relative = PurePosixPath(ref) / f'v{version}' / name
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError(f'Unsafe manifest path: {relative}')
    target = asset_root.joinpath(*relative.parts)
    target.parent.mkdir(parents=True, exist_ok=True)
    expected = item.get('bytes')
    receipt = target.with_name(target.name + '.receipt.json')
    if target.is_file() and expected is not None and target.stat().st_size == expected:
        saved = json.loads(receipt.read_text()) if receipt.is_file() else {}
        result = {**item, 'path': str(target.relative_to(ROOT)), 'sha256': saved.get('sha256') or digest(target), 'state': 'present'}
        receipt.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        return result
    # Kaggle's fileName is one route segment, including encoded folder slashes.
    quoted = urllib.parse.quote(name, safe='')
    url = f'https://www.kaggle.com/api/v1/datasets/download/{ref}/{quoted}?datasetVersionNumber={version}'
    partial = target.with_name(target.name + '.part')
    start = time.monotonic()
    last_error = None
    for attempt in range(5):
        offset = partial.stat().st_size if partial.exists() else 0
        headers = {'User-Agent': 'CASMI26-local-reproduction/1.0'}
        if offset:
            headers['Range'] = f'bytes={offset}-'
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=60) as response:
                append = bool(offset and response.status == 206)
                content_type = response.headers.get('Content-Type', '')
                if 'text/html' in content_type:
                    raise RuntimeError('Received HTML instead of the requested dataset file')
                with partial.open('ab' if append else 'wb') as handle:
                    for chunk in iter(lambda: response.read(2 << 20), b''):
                        handle.write(chunk)
            actual = partial.stat().st_size
            if expected is not None and actual != expected:
                raise RuntimeError(f'File size mismatch: expected {expected}, got {actual}')
            sha = digest(partial)
            if item.get('sha256') and sha != item['sha256']:
                raise RuntimeError('Pinned SHA-256 mismatch')
            partial.replace(target)
            result = {**item, 'path': str(target.relative_to(ROOT)), 'sha256': sha, 'source_url': url, 'state': 'downloaded', 'seconds': round(time.monotonic()-start, 2)}
            receipt.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
            print(json.dumps({'state': 'downloaded', 'ref': ref, 'file': name, 'bytes': actual, 'seconds': result['seconds']}), flush=True)
            return result
        except Exception as exc:
            last_error = f'{type(exc).__name__}: {exc}'
            print(json.dumps({'state': 'retry', 'ref': ref, 'file': name, 'attempt': attempt+1, 'error': last_error}), flush=True)
            if isinstance(exc, urllib.error.HTTPError) and exc.code in (400, 401, 403, 404):
                break
            if attempt < 4:
                time.sleep(min(2**attempt, 15))
    return {**item, 'state': 'failed', 'error': last_error}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path, nargs='+')
    parser.add_argument('--workers', type=int, default=3)
    parser.add_argument('--exclude-ref', action='append', default=[])
    parser.add_argument('--report', type=Path, default=ROOT/'reports/asset_downloads.json')
    args = parser.parse_args()
    asset_root = ROOT/'assets/kaggle'
    tasks = {}
    for path in args.manifest:
        doc = json.loads(path.read_text(encoding='utf-8'))
        for dependency in doc['dependencies']:
            if dependency['ref'] in args.exclude_ref:
                continue
            version = dependency.get('version_number_observed') or dependency.get('version')
            if not isinstance(version, int) or version < 1:
                raise ValueError(f'Missing version for {dependency["ref"]}')
            for file in dependency['files']:
                item = {**file, 'ref': dependency['ref'], 'version': version}
                tasks[(item['ref'], version, item['name'])] = item
    expected = sum(item.get('bytes', 0) for item in tasks.values())
    free = shutil.disk_usage(ROOT).free
    print(json.dumps({'files': len(tasks), 'listed_bytes': expected, 'disk_free_bytes': free}), flush=True)
    if free < expected + (5 << 30):
        raise RuntimeError('Insufficient free disk space including a 5 GiB working reserve')
    results = []
    args.report.parent.mkdir(exist_ok=True, parents=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(fetch, item, asset_root) for item in sorted(tasks.values(), key=lambda x:x.get('bytes',0))]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            results.append(result)
            args.report.write_text(json.dumps({'files': results}, indent=2) + '\n', encoding='utf-8')
    failed = [item for item in results if item['state'] == 'failed']
    print(json.dumps({'complete': len(results)-len(failed), 'failed': len(failed), 'report': str(args.report)}), flush=True)
    if failed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
