"""Reuse the three PubChem arrays only after checking upstream-pinned hashes."""
from pathlib import Path
import hashlib
import json
import os

ROOT = Path(__file__).resolve().parents[1]
asset_root = ROOT/'assets/kaggle'
manifest = json.loads((ROOT/'reports/flexonafft_asset_aliases.json').read_text())
results = []
for item in manifest:
    source = asset_root/item['source_ref']/f'v{item["source_version"]}'/item['source_file']
    destination = asset_root/item['destination_ref']/f'v{item["destination_version"]}'/item['destination_file']
    if not source.is_file() or source.stat().st_size != item['bytes']:
        raise FileNotFoundError(f'Missing complete source: {source}')
    h = hashlib.sha256()
    with source.open('rb') as handle:
        for chunk in iter(lambda:handle.read(8<<20),b''):
            h.update(chunk)
    if h.hexdigest() != item['sha256']:
        raise ValueError(f'Upstream-pinned array hash mismatch: {source}')
    destination.parent.mkdir(parents=True,exist_ok=True)
    if destination.exists():
        if not os.path.samefile(source,destination):
            raise FileExistsError(f'Refusing to replace existing different file: {destination}')
    else:
        os.link(source,destination)
    results.append({**item,'source':str(source),'destination':str(destination),'state':'verified_hardlink'})
(ROOT/'reports/shared_asset_links.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps({'verified_hardlinks':len(results),'bytes_reused':sum(x['bytes'] for x in results)}))
