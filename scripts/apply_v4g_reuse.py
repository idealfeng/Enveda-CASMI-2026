"""Link verified identical package files after the old downloader has stopped."""
from pathlib import Path
import hashlib
import json
import os

ROOT = Path(__file__).resolve().parents[1]
plan = json.loads((ROOT/'third_party/flexonafft_evidence_gap/v4g_reuse_plan.json').read_text())
results = []
for item in plan['links']:
    source = ROOT/item['source']['path']
    target = ROOT/item['dest']['path']
    if target.exists():
        continue
    h = hashlib.sha256()
    with source.open('rb') as handle:
        for chunk in iter(lambda:handle.read(8<<20),b''):
            h.update(chunk)
    if h.hexdigest() != item['dest']['sha256']:
        raise ValueError(f'Pinned package hash mismatch: {source}')
    target.parent.mkdir(parents=True,exist_ok=True)
    os.link(source,target)
    receipt = {**item['dest'], 'sha256':h.hexdigest(), 'state':'verified_hardlink',
               'reused_from':str(source.relative_to(ROOT)), 'proof':item['dest']['hash_evidence']}
    target.with_name(target.name+'.receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    results.append(receipt)
(ROOT/'reports/v4g_reused_assets.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps({'files_linked':len(results),'bytes_reused':sum(x['bytes'] for x in results)}))
