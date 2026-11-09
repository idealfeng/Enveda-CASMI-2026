"""Fetch size-bounded public GitHub metadata only; never execute repository code."""
from pathlib import Path
from urllib.request import Request, urlopen
import json

workspace = Path(__file__).resolve().parent.parent
out = workspace / 'reports' / 'shiferaxa_source_audit'
out.mkdir(parents=True, exist_ok=True)
urls = {
    'repository': 'https://api.github.com/repos/shiferaxa/casmi26',
    'commit': 'https://api.github.com/repos/shiferaxa/casmi26/commits/main',
}
objects = {}
for name, url in urls.items():
    with urlopen(Request(url, headers={'User-Agent': 'CASMI-local-research', 'Accept': 'application/vnd.github+json'}), timeout=30) as response:
        raw = response.read(2_000_001)
    if len(raw) > 2_000_000:
        raise ValueError('Metadata size cap exceeded')
    objects[name] = json.loads(raw)
    (out / (name + '.json')).write_bytes(raw)
sha = objects['commit']['sha']
url = f'https://api.github.com/repos/shiferaxa/casmi26/git/trees/{sha}?recursive=1'
with urlopen(Request(url, headers={'User-Agent': 'CASMI-local-research'}), timeout=30) as response:
    raw = response.read(2_000_001)
if len(raw) > 2_000_000:
    raise ValueError('Tree size cap exceeded')
tree = json.loads(raw)
(out / 'tree.json').write_bytes(raw)
if tree.get('truncated'):
    raise ValueError('Tree incomplete')
blobs = [x for x in tree['tree'] if x['type'] == 'blob']
summary = {'sha': sha, 'repository_size_kb': objects['repository']['size'],
           'license': objects['repository'].get('license'), 'files': len(blobs),
           'payload_bytes': sum(x.get('size', 0) for x in blobs),
           'largest': sorted([{'path': x['path'], 'size': x.get('size', 0)} for x in blobs], key=lambda x: -x['size'])[:8],
           'special_files': [x for x in blobs if x['path'].endswith(('.gitattributes', '.gitmodules'))]}
(out / 'metadata_summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary, indent=2))
