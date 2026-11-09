"""Prepare an offline review draft and provenance manifest; never call Kaggle push/submit."""
from pathlib import Path
import argparse
import ast
import hashlib
import json
import os
import re


ROOT = Path(__file__).resolve().parents[1]


def recorded_hash(path, entry):
    """Read small receipts; an alias must still be the same on-disk file."""
    receipt_path = path.with_name(path.name + '.receipt.json')
    receipt = json.loads(receipt_path.read_text(encoding='utf-8')) if receipt_path.is_file() else {}
    if receipt.get('sha256'):
        return receipt['sha256'], 'recorded target receipt; not rehashed during submission preparation', {
            'receipt': str(receipt_path.relative_to(ROOT)), 'fresh_content_rehash': False}
    links_path = ROOT / 'reports/shared_asset_links.json'
    pins_path = ROOT / 'reports/flexonafft_asset_aliases.json'
    if not links_path.is_file() or not pins_path.is_file():
        return None, 'no hash receipt found', None
    links = json.loads(links_path.read_text(encoding='utf-8'))
    pins = json.loads(pins_path.read_text(encoding='utf-8'))
    matches = [item for item in links if item['destination_ref'] == entry['dataset']
               and item['destination_version'] == entry['version'] and item['destination_file'] == entry['file']]
    if not matches:
        return None, 'no hash receipt found', None
    if len(matches) != 1:
        raise ValueError('Ambiguous asset alias: ' + str(path))
    item = matches[0]
    source = ROOT / 'assets/kaggle' / item['source_ref'] / f"v{item['source_version']}" / item['source_file']
    source_receipt_path = source.with_name(source.name + '.receipt.json')
    source_receipt = json.loads(source_receipt_path.read_text(encoding='utf-8'))
    pin = [value for value in pins if all(value.get(key) == item.get(key) for key in value)]
    sizes = [source.stat().st_size, path.stat().st_size, item['bytes'], source_receipt['bytes']]
    if (item.get('state') != 'verified_hardlink' or len(pin) != 1 or not os.path.samefile(source, path)
            or len(set(sizes)) != 1 or source_receipt.get('sha256') != item.get('sha256')
            or source_receipt.get('ref') != item['source_ref'] or source_receipt.get('version') != item['source_version']):
        raise ValueError('Asset alias receipt/file identity no longer matches: ' + str(path))
    return item['sha256'], 'recorded source receipt plus verified same-file hardlink; no fresh content rehash', {
        'source': str(source.relative_to(ROOT)), 'source_receipt': str(source_receipt_path.relative_to(ROOT)),
        'alias_manifest': str(pins_path.relative_to(ROOT)), 'link_receipt': str(links_path.relative_to(ROOT)),
        'same_file_verified_now': True, 'fresh_content_rehash': False}


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, default=ROOT / 'submission/flex_v56_review')
parser.add_argument('--username', help='Prepare local account metadata; no API call or upload')
args = parser.parse_args()
out = args.output.resolve()
if not out.is_relative_to(ROOT):
    parser.error('Submission artifacts must stay inside the D: workspace')
if args.username and not re.fullmatch(r'[A-Za-z0-9_-]{1,50}', args.username):
    parser.error('Pass a Kaggle username, without a URL or slash')
out.mkdir(parents=True, exist_ok=True)
source_root = ROOT / 'third_party/flexonafft_evidence_gap'
original = source_root / 'v56/original.ipynb'
raw = original.read_bytes()
notebook = json.loads(raw)
for index, cell in enumerate(notebook['cells']):
    if cell.get('cell_type') == 'code':
        text = cell['source']
        ast.parse(''.join(text) if isinstance(text, list) else text, filename=f'original-cell-{index}')
metadata = json.loads((source_root / 'v56/metadata.json').read_text(encoding='utf-8'))
target = out / 'notebook.ipynb'
if target.exists() and target.read_bytes() != raw:
    raise RuntimeError('Refusing to overwrite a modified submission draft')
target.write_bytes(raw)
draft = dict(id='YOUR_KAGGLE_USERNAME/casmi26-flex-v56-baseline',
    title='CASMI26 Flex V56 baseline', code_file='notebook.ipynb',
    language='python', kernel_type='notebook', is_private=True, enable_gpu=True,
    enable_internet=False, machine_shape=metadata['machineShape'],
    docker_image=metadata['dockerImage'],
    competition_sources=metadata['competitionDataSources'],
    dataset_sources=metadata['datasetDataSources'], kernel_sources=metadata['kernelDataSources'])
(out / 'kernel-metadata.template.json').write_text(json.dumps(draft, indent=2) + '\n', encoding='utf-8')
account_path = out / 'kernel-metadata.json'
if args.username:
    account_draft = dict(draft, id=args.username + '/casmi26-flex-v56-baseline')
    if account_path.exists() and json.loads(account_path.read_text(encoding='utf-8')) != account_draft:
        raise RuntimeError('Refusing to overwrite modified account metadata; review it explicitly')
    account_path.write_text(json.dumps(account_draft, indent=2) + '\n', encoding='utf-8')
account_id = json.loads(account_path.read_text(encoding='utf-8')).get('id') if account_path.exists() else None
plan = json.loads((source_root / 'minimum_download_plan.json').read_text(encoding='utf-8'))
assets = []
for entry in plan['files']:
    path = ROOT / 'assets/kaggle' / entry['dataset'] / f"v{entry['version']}" / entry['file']
    asset_sha, evidence, evidence_source = recorded_hash(path, entry)
    assets.append(dict(dataset=entry['dataset'], version=entry['version'], file=entry['file'],
        local_path=str(path.relative_to(ROOT)), present=path.is_file(),
        actual_bytes=path.stat().st_size if path.is_file() else None,
        expected_bytes=entry.get('size', entry.get('bytes')), recorded_sha256=asset_sha,
        hash_evidence=evidence, hash_evidence_source=evidence_source))
(out / 'local_asset_manifest.json').write_text(json.dumps(assets, indent=2) + '\n', encoding='utf-8')
report = dict(status='prepared_for_review', external_write_performed=False, submission_performed=False,
    notebook_sha256=hashlib.sha256(raw).hexdigest(), original_notebook_unchanged=True,
    source_ref=metadata['ref'], source_version=56, dataset_files=len(assets),
    local_files_present=sum(a['present'] for a in assets),
    files_with_recorded_sha256=sum(bool(a['recorded_sha256']) for a in assets),
    same_file_alias_hashes=sum(bool((a['hash_evidence_source'] or {}).get('same_file_verified_now')) for a in assets),
    files_with_expected_size=sum(a['present'] and a['expected_bytes'] is not None and a['actual_bytes'] == a['expected_bytes'] for a in assets),
    fresh_large_asset_rehash_performed=False,
    metadata_file_role='Account metadata prepared locally; no upload or service call.' if account_id else
        'Review template; the installed CLI reads kernel-metadata.json after explicit account preparation.',
    account_kernel_id=account_id,
    account_metadata_file='kernel-metadata.json' if account_id else None,
    docker_image_pinning_verification='Image digest preserved from original metadata; pinning type is unspecified and server acceptance is not verified.',
    local_diagnostic_report='reports/VALIDATION_FLEX_48_2026-11-05.md',
    input_version_limitation='Kaggle attachment slugs do not by themselves freeze the local historical dataset versions.',
    unresolved=([] if account_id else ['Replace the explicit username placeholder when preparing the account draft.']) + [
        'Review completed local diagnostic and known pretrained exposure; it is not clean CV or a hidden score.',
        'Review source-specific licences and the competition-host training-data clarification.',
        'Verify cloud attachment versions/model pins, requested accelerator and Docker availability.',
        'Exercise the unmodified official full-input path and cold-run budget; the original smoke processed 12 and the generated diagnostic processed 48.'])
(out / 'preparation_report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, indent=2))
