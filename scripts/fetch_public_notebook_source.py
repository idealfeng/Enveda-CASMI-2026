"""Archive a small public Kaggle source and metadata without executing its code."""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import urllib.parse
import urllib.request


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--ref', required=True, help='owner/notebook-slug')
parser.add_argument('--destination', type=Path, required=True)
args = parser.parse_args()
owner, slug = args.ref.split('/')
url = 'https://www.kaggle.com/api/v1/kernels/pull?' + urllib.parse.urlencode(
    {'userName': owner, 'kernelSlug': slug})
request = urllib.request.Request(url, headers={'User-Agent': 'CASMI26-source-review/1.0'})
with urllib.request.urlopen(request, timeout=45) as response:
    raw = response.read(10 * 1024 * 1024 + 1)
if len(raw) > 10 * 1024 * 1024:
    raise RuntimeError('API response exceeds the 10 MiB source-only limit')
result = json.loads(raw)
source = result['blob']['source']
notebook = json.loads(source)
if 'cells' not in notebook:
    raise ValueError('Expected a notebook source; no code was executed')
root = args.destination.resolve()
root.mkdir(parents=True, exist_ok=True)
if (root / 'source.ipynb').exists():
    raise FileExistsError('Use a new destination to preserve the existing snapshot')
metadata = result['metadata']
(root / 'api_response.json').write_bytes(raw)
(root / 'metadata.json').write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
(root / 'source.ipynb').write_text(source, encoding='utf-8')
receipt = dict(url=url, downloaded_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    version=metadata.get('currentVersionNumber'), ref=metadata.get('ref'),
    source_sha256=hashlib.sha256((root / 'source.ipynb').read_bytes()).hexdigest(),
    api_sha256=hashlib.sha256(raw).hexdigest(), api_bytes=len(raw), executed=False, assets_downloaded=False)
(root / 'download_receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
outline = []
for index, cell in enumerate(notebook['cells']):
    text = cell.get('source', '')
    text = ''.join(text) if isinstance(text, list) else text
    outline.append(f"\n<!-- {cell.get('cell_type')} cell {index} -->\n" + text)
(root / 'source_review.txt').write_text('\n'.join(outline), encoding='utf-8')
print(json.dumps(receipt))
