"""Fetch exactly two pinned, small public scorers. Never execute a checkpoint."""
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
import hashlib
import json
import os
import shutil
import ssl
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = Path(__file__).resolve().parent
REFERENCES = ('bgunshui/casmi26-scorer-v2-model', 'bgunshui/casmi26-scorer-v4-model')
MAX_WEIGHT_BYTES = 20 << 20
MAX_TOTAL_BYTES = 35 << 20
PUBLIC_KIT = ROOT/'assets/kaggle/sanpier/casmi-spectrum-model-v1/v1/casmi_spectrum_model_v1'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            result.update(block)
    return result.hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')


def main():
    if ROOT.drive.upper() != 'D:':
        raise ValueError('This download is restricted to the D: workspace')
    plans = []
    small_receipts = read(EVIDENCE/'small_file_receipts.json')['records']
    native_names = {'README.md', 'config_used.json', 'training_result.json', 'final_model.pt'}
    for ref in REFERENCES:
        view = read(EVIDENCE/(ref.replace('/', '__')+'_view.json'))
        listing = read(EVIDENCE/(ref.replace('/', '__')+'_files.json'))
        if view['status'] != 'read_success' or view['metadata']['isPrivate'] is not False or view['metadata']['currentVersionNumber'] != 1:
            raise ValueError('Public fixed V1 metadata required')
        files = listing['response']['datasetFiles']
        if listing['response']['nextPageToken'] or {item['name'] for item in files} != native_names:
            raise ValueError('Unexpected or incomplete fixed dataset file inventory')
        dest = ROOT/'assets/kaggle'/ref/'v1'
        if dest.exists() and any(dest.iterdir()):
            raise ValueError('Refusing to overwrite existing target bundle')
        plans.append((ref, files, dest, view))
    expected = sum(item['totalBytes'] for _, files, _, _ in plans for item in files)
    expected += len(plans) * (sum((PUBLIC_KIT/name).stat().st_size for name in ('model.py', 'features.py', 'inference.py')) + 2048)
    if expected > MAX_TOTAL_BYTES:
        raise ValueError('Total planned package exceeds the authorized 35MiB cap')
    report = dict(status='downloading', started_at_utc=now(), authorized_refs=list(REFERENCES),
                  weights_executed=False, new_model_inference_training_or_kaggle_write=False,
                  max_total_bytes=MAX_TOTAL_BYTES, downloaded_weight_bytes=0, bundles=[])
    report_path = EVIDENCE/'minimal_model_download_report.json'
    if report_path.exists():
        raise ValueError('Download action already recorded; inspect rather than automatically retry')
    write_json(report_path, report)
    public_sha = digest(PUBLIC_KIT/'final_model.pt')
    used = 0
    try:
        for ref, files, dest, view in plans:
            dest.mkdir(parents=True, exist_ok=False)
            entries = []
            for item in files:
                name, size = item['name'], item['totalBytes']
                path = dest/name
                if name == 'final_model.pt':
                    if size > MAX_WEIGHT_BYTES:
                        raise ValueError('Weight exceeds per-file bound')
                    partial = path.with_suffix('.pt.part')
                    url = 'https://www.kaggle.com/api/v1/datasets/download/'+ref+'/'+quote(name, safe='')+'?datasetVersionNumber=1'
                    request = urllib.request.Request(url, headers={'User-Agent': 'casmi-pinned-small-model-audit/1.0'})
                    total = 0
                    print(json.dumps(dict(status='downloading_weight', ref=ref, version=1, expected_bytes=size)), flush=True)
                    with urllib.request.urlopen(request, context=ssl.create_default_context(), timeout=45) as response:
                        length = response.headers.get('Content-Length')
                        if response.status != 200 or (length and int(length) != size):
                            raise ValueError('Unexpected weight response size/status')
                        with partial.open('xb') as stream:
                            while True:
                                block = response.read(128 << 10)
                                if not block:
                                    break
                                total += len(block)
                                if total > size or total > MAX_WEIGHT_BYTES or used+total > MAX_TOTAL_BYTES:
                                    raise ValueError('Download stream cap exceeded')
                                stream.write(block)
                    if total != size:
                        raise ValueError('Incomplete weight response')
                    partial.replace(path)
                    used += total
                    report['downloaded_weight_bytes'] += total
                else:
                    match = next(x for x in small_receipts if x['ref'] == ref and x['version'] == 1 and x['file'] == name)
                    source = ROOT/match['path']
                    if match['status'] != 'downloaded' or source.stat().st_size != size or digest(source) != match['sha256']:
                        raise ValueError('Audited small file changed')
                    shutil.copy2(source, path)
                    used += size
                entry = dict(ref=ref, version=1, file=name, destination_file=name, bytes=path.stat().st_size,
                             sha256=digest(path), source_kind='public_dataset_file', acquired_at_utc=now(),
                             signed_url_or_credentials_persisted=False)
                write_json(path.with_name(path.name+'.receipt.json'), entry)
                entries.append(entry)
            for name in ('model.py', 'features.py', 'inference.py'):
                source = PUBLIC_KIT/name
                source_receipt = read(source.with_name(source.name+'.receipt.json'))
                source_sha = digest(source)
                if source_sha != source_receipt['sha256']:
                    raise ValueError('Existing public inference kit file changed')
                path = dest/name
                shutil.copy2(source, path)
                used += path.stat().st_size
                entry = dict(ref='sanpier/casmi-spectrum-model-v1', version=1,
                    file='casmi_spectrum_model_v1/'+name, destination_file=name,
                    bytes=path.stat().st_size, sha256=source_sha, source_kind='existing_public_kit_dependency_copy',
                    source_local_path=str(source.relative_to(ROOT)),
                    source_receipt=str(source.with_name(source.name+'.receipt.json').relative_to(ROOT)),
                    acquired_at_utc=now())
                write_json(path.with_name(path.name+'.receipt.json'), entry)
                entries.append(entry)
            config = dest/'config.json'
            shutil.copy2(dest/'config_used.json', config)
            used += config.stat().st_size
            alias = dict(ref=ref, version=1, file='config_used.json', destination_file='config.json',
                bytes=config.stat().st_size, sha256=digest(config), source_kind='local_filename_alias_of_shipped_config',
                acquired_at_utc=now())
            write_json(config.with_name(config.name+'.receipt.json'), alias)
            entries.append(alias)
            if used > MAX_TOTAL_BYTES:
                raise ValueError('Package total cap exceeded')
            bundle = dict(ref=ref, version=1, path=str(dest.relative_to(ROOT)), files=entries,
                native_dataset_file_count=4, native_dataset_license=view['metadata']['licenseName'],
                inference_code_dependency='sanpier/casmi-spectrum-model-v1 V1; source notices retained in original asset directory',
                weight_matches_public_saner_checkpoint=digest(dest/'final_model.pt') == public_sha,
                config=read(dest/'config.json'), training_result=read(dest/'training_result.json'),
                status='downloaded_not_loaded')
            write_json(dest/'BUNDLE_MANIFEST.json', bundle)
            report['bundles'].append(bundle)
            write_json(report_path, report)
        report.update(status='complete_not_loaded', completed_at_utc=now(), package_payload_bytes=used)
    except Exception as error:
        report.update(status='failed_no_automatic_retry', error_type=type(error).__name__,
                      http_status=getattr(error, 'code', None), checked_at_utc=now())
        write_json(report_path, report)
        raise
    write_json(report_path, report)
    print(json.dumps({key: report[key] for key in ('status', 'downloaded_weight_bytes', 'package_payload_bytes')}, indent=2))


if __name__ == '__main__':
    main()
