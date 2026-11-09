"""Compare the V2 mounted-file receipt with pinned local assets, without downloading assets."""
from collections import Counter
from pathlib import Path
import argparse
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
TARGET = 'stormseye/casmi26-flex-v56-baseline'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--outputs', type=Path, default=ROOT/'runs/kaggle_baseline_v2_outputs_20261105b')
    args = parser.parse_args()
    outputs = args.outputs.resolve()
    if not outputs.is_relative_to(ROOT):
        parser.error('Use downloaded receipts inside the D: workspace')
    receipt = read(outputs/'download_receipt.json')
    if receipt.get('status') != 'downloaded' or receipt.get('target') != TARGET or receipt.get('version') != 2:
        raise ValueError('Completed version-bound V2 download required')
    mounted_path = outputs/'v43_mounted_input_hashes.json'
    recorded = next(x for x in receipt['downloaded_files'] if x['name'] == mounted_path.name)
    if hashlib.sha256(mounted_path.read_bytes()).hexdigest() != recorded['sha256']:
        raise ValueError('Downloaded inventory changed')
    mounted = read(mounted_path)
    local = read(ROOT/'submission/flex_v56_review/local_asset_manifest.json')
    by_path = {item['path']: item for item in mounted}
    comparisons = []
    for item in local:
        owner, slug = item['dataset'].split('/')
        relative = item['file'].replace('\\', '/')
        remote = by_path.get(f'/kaggle/input/datasets/{owner}/{slug}/{relative}') or by_path.get(f'/kaggle/input/{slug}/{relative}')
        entry = dict(dataset=item['dataset'], pinned_local_version=item['version'], file=relative)
        if not remote:
            entry['result'] = 'outside_five_dataset_inventory' if owner == 'sanpier' else 'missing_from_mounted_inventory'
        elif remote['bytes'] != item['actual_bytes']:
            entry['result'] = 'size_mismatch'
        elif remote.get('full'):
            entry['result'] = 'full_sha_match' if remote.get('sha256') == item['recorded_sha256'] else 'full_sha_mismatch'
            entry['local_proof'] = 'Previously recorded content SHA; no fresh local full rehash'
        else:
            path = (ROOT/item['local_path']).resolve()
            if not path.is_relative_to(ROOT) or path.stat().st_size != remote['bytes']:
                raise ValueError('Local large asset path/size changed')
            digest = hashlib.sha256()
            with path.open('rb') as stream:
                digest.update(stream.read(4 << 20))
                stream.seek(remote['bytes'] - (4 << 20))
                digest.update(stream.read(4 << 20))
            entry['result'] = 'size_head_tail_match' if digest.hexdigest() == remote.get('sha256_head_tail') else 'head_tail_mismatch'
            entry['local_proof'] = 'Fresh local first/last4MiB SHA and file size; not a full-file digest'
        comparisons.append(entry)
    counts = Counter(item['result'] for item in comparisons)
    bad = [item for item in comparisons if item['result'] not in ('full_sha_match', 'size_head_tail_match', 'outside_five_dataset_inventory')]
    report = dict(status='passed_for_inventory_scope' if not bad else 'mismatch', target=TARGET, version=2,
        read_only=True, mounted_inventory_entries=len(mounted), local_required_files=len(local),
        counts=dict(counts), mismatches=bad, comparisons=comparisons,
        numeric_dataset_versions_independently_read_back=False,
        limitations=['The receipt inventories five baseline datasets and competition files; Saner is checked separately by MODEL_PINS.',
            'Matching content fingerprints support alignment with pinned local assets; they do not expose server numeric dataset versions.',
            'Large files use size and first/last4MiB hashes. Unread middle bytes are not certified by those hashes.',
            'Small files compare runtime full SHA against prior local download receipts, without a fresh local full rehash.'])
    destination = ROOT/'reports/kaggle_baseline_v2_asset_alignment_20261105.json'
    destination.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({key: report[key] for key in ('status','local_required_files','mounted_inventory_entries','counts','mismatches')}, indent=2))
    return 1 if bad else 0


if __name__ == '__main__':
    raise SystemExit(main())
