"""Acquire only explicitly approved FIORA OS v1 assets from pinned source."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import concurrent.futures
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'assets/research/fiora_os_20261115'
SOURCE = DEST / 'source_checkout'
PIN = 'e19ef82c9a6cb9dbac92bce23e914008f1aeb44e'
STATE = 'fiora/resources/models/fiora_OS_v1.0.0_state.pt'
PARAMS = 'fiora/resources/models/fiora_OS_v1.0.0_params.json'

def git(*args):
    return subprocess.check_output(['git', '-C', str(SOURCE), *args], text=True).strip()

assert git('rev-parse', 'HEAD') == PIN
rows = [x.split('\t', 1) for x in git('ls-tree', '-r', PIN).splitlines()]
selected = []
blob_ids = {}
for info, path in rows:
    keep = ((path.startswith('fiora/') and path.endswith('.py'))
            or path in {STATE, PARAMS, 'README.md', 'LICENSE', 'pyproject.toml',
                        'requirements.txt', 'constraints.txt', 'examples/example_input.csv',
                        'examples/expected_output.mgf'})
    if keep:
        selected.append(path)
        blob_ids[path] = info.split()[-1]
assert [p for p in selected if p.endswith('.pt')] == [STATE]
def acquire(relative):
    path = SOURCE / relative
    if path.exists():
        data = path.read_bytes()
        blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        if blob == blob_ids[relative]:
            return
    url = 'https://raw.githubusercontent.com/BAMeScience/fiora/' + PIN + '/' + relative
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=120) as response:
                data = response.read(64 * 1024 * 1024 + 1)
            assert len(data) <= 64 * 1024 * 1024
            blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
            assert blob == blob_ids[relative], relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            return
        except Exception:
            if attempt == 2:
                raise
            time.sleep(1 + attempt)
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    list(pool.map(acquire, selected))
files = []
for relative in selected:
    path = SOURCE / relative
    data = path.read_bytes()
    blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
    assert blob == blob_ids[relative], relative
    files.append({'path': relative, 'bytes': len(data),
                  'sha256': hashlib.sha256(data).hexdigest(), 'git_blob_sha1': blob})
receipt = {'repository': 'https://github.com/BAMeScience/fiora',
           'source_commit': PIN, 'source_tag': 'v1.1.0', 'model_version': 'FIORA_OS_v1.0.0',
           'model_state': STATE, 'model_params': PARAMS,
           'selection': 'Python source, MIT license, configs, small example, OS v1 state only',
           'excluded_models': ['fiora_OS_v0.1.0.pt', 'fiora_OS_v0.1.0_state.pt', 'fiora_OS_v1.0.0.pt'],
           'files': files}
out = DEST / 'acquisition_receipt.json'
out.write_text(json.dumps(receipt, indent=2), encoding='utf-8')
print(json.dumps({'receipt': str(out), 'files': len(files),
                  'total_bytes': sum(x['bytes'] for x in files),
                  'model': next(x for x in files if x['path'] == STATE)}, indent=2))
