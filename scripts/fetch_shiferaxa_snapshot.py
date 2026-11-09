"""Acquire a bounded commit-pinned code snapshot; never execute its contents."""
from pathlib import Path, PurePosixPath
from urllib.request import Request, urlopen
from datetime import datetime, timezone
import hashlib
import json
import zipfile

workspace = Path(__file__).resolve().parent.parent
sha = '41f0c5dde78e551fb5aedbb3421156a38b3f427d'
url = f'https://codeload.github.com/shiferaxa/casmi26/zip/{sha}'
audit = workspace / 'reports' / 'shiferaxa_source_audit'
audit.mkdir(parents=True, exist_ok=True)
archive = audit / (sha + '.zip')
target = workspace / 'third_party' / 'shiferaxa_casmi26'
cap = 20_000_000
if target.exists():
    raise ValueError('Refusing to overwrite an existing source directory')
total = 0
with urlopen(Request(url, headers={'User-Agent': 'CASMI-local-research'}), timeout=60) as response, archive.open('wb') as output:
    while block := response.read(65536):
        total += len(block)
        if total > cap:
            raise ValueError('20MB network download cap exceeded')
        output.write(block)
files = []
with zipfile.ZipFile(archive) as source:
    entries = [entry for entry in source.infolist() if not entry.is_dir()]
    expanded = sum(entry.file_size for entry in entries)
    if expanded > cap:
        raise ValueError('20MB expanded source cap exceeded')
    for entry in entries:
        relative = PurePosixPath(entry.filename)
        if len(relative.parts) < 2 or relative.parts[0] != 'casmi26-' + sha or '..' in relative.parts or relative.is_absolute():
            raise ValueError('Unexpected archive path')
        name = PurePosixPath(*relative.parts[1:])
        if entry.file_size > 5_000_000 or name.suffix.lower() in {'.pt', '.pth', '.ckpt', '.parquet', '.npy', '.npz', '.bin', '.pkl'}:
            raise ValueError('Large file or model/data payload refused: ' + str(name))
        body = source.read(entry)
        if body.startswith(b'version https://git-lfs.github.com/spec/v1'):
            raise ValueError('Git LFS pointer found: ' + str(name))
        if str(name) in {'.gitattributes', '.gitmodules'}:
            raise ValueError('Repository attributes/submodules require separate review')
        files.append((name, body))
    target.mkdir()
    for name, body in files:
        destination = target.joinpath(*name.parts)
        if not destination.resolve().is_relative_to(target.resolve()):
            raise ValueError('Destination escaped workspace')
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(body)
receipt = {'repository': 'https://github.com/shiferaxa/casmi26', 'commit': sha,
           'commit_resolution': 'git ls-remote refs/heads/main (http.sslBackend=openssl command-local)',
           'acquired_utc': datetime.now(timezone.utc).isoformat(), 'method': 'commit-pinned GitHub source ZIP; no git history',
           'url': url, 'download_bytes': total, 'expanded_bytes': expanded, 'files': len(files),
           'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
           'target': str(target), 'model_data_downloaded': False, 'external_code_executed': False,
           'lfs_pointers': 0, 'per_file': [{'path': str(name), 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()} for name, body in files]}
(audit / 'download_receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({k: v for k, v in receipt.items() if k != 'per_file'}, indent=2))
