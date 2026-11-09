"""Prepare source-preserving public-neural review packets; never run models or Kaggle writes."""
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import quote
import argparse
import ast
import base64
import copy
import hashlib
import json
import os
import re
import ssl
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT/'submission/public_neural_review_20261106'
COMMON = {
    'sanpier/casmi-spectrum-model-v1': 1,
    'dmitriigluzdov/casmi26-fold-safe-fpnet': 5,
    'dmitriigluzdov/casmi26-natural-product-knowledge-table': 10,
    'dmitriigluzdov/casmi26-natural-product-panel-benchmark': 10,
    'dmitriigluzdov/casmi26-pubchem-popularity-prior': 13,
    'dmitriigluzdov/casmi26-attributed-v4g-reproduction-assets': 9,
}
RECIPES = {
    'hardened_v1': dict(source='d1m4_enveda0480_20261106', version=1,
        sha='7780631f63b07663792b7e47c06585c7d3799e1e2ad9755698657aa4b2959d7f',
        slug='casmi26-n480-public-v2', title='CASMI26 N480 public v2 review',
        models=['casmi26-scorer-v2-model']),
    'tri_v30': dict(source='zz3t3rn41_peaks_v2_20261106', version=30,
        sha='73c8bdc7799ffdad7ef756015c74c90365ee060122f2567f8a3c061ff42cc0df',
        slug='casmi26-public-tri-v30', title='CASMI26 public tri V30 review',
        models=['casmi26-scorer-v2-model', 'casmi26-scorer-v4-model']),
}


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            result.update(block)
    return result.hexdigest()


def write_once(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError('Refusing to overwrite a modified review artifact: ' + str(path))
        return
    with path.open('xb') as stream:
        stream.write(raw)


def json_bytes(value):
    return (json.dumps(value, indent=2, ensure_ascii=False)+'\n').encode('utf-8')


def constants(notebook):
    result = {'MODULES': {}}
    for cell in notebook['cells']:
        if cell['cell_type'] != 'code':
            continue
        source = cell['source']
        source = ''.join(source) if isinstance(source, list) else source
        for node in ast.parse(source).body:
            if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                continue
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id in ('FROZEN_SHA256', 'FROZEN_B64', 'MODEL_PINS', 'MODULE_SHA256'):
                result[target.id] = ast.literal_eval(node.value)
            if (isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name)
                    and target.value.id == 'MODULES' and isinstance(target.slice, ast.Constant)):
                result['MODULES'][target.slice.value] = ast.literal_eval(node.value)
    if set(result['MODULES']) != set(result['MODULE_SHA256']):
        raise ValueError('Helper module declarations and pins differ')
    for name, text in result['MODULES'].items():
        if hashlib.sha256(text.encode()).hexdigest() != result['MODULE_SHA256'][name]:
            raise ValueError('Embedded helper pin differs: ' + name)
    frozen = base64.b64decode(result['FROZEN_B64'])
    if hashlib.sha256(frozen).hexdigest() != result['FROZEN_SHA256']:
        raise ValueError('Frozen baseline pin differs')
    return result, frozen


def fetch_lotus(out):
    ref = 'qwertykeypadapple/casmi26-lotus-candidates'
    evidence = out/'input_metadata'
    view = read(evidence/'qwertykeypadapple__casmi26-lotus-candidates_view.json')
    files = read(evidence/'qwertykeypadapple__casmi26-lotus-candidates_files.json')
    if view['currentVersionNumber'] != 2 or view['isPrivate'] is not False:
        raise ValueError('Expected the reviewed public LOTUS V2')
    items = files['datasetFiles']
    if files.get('nextPageToken') or {x['name'] for x in items} != {'README.md', 'candidates_lotus.parquet'}:
        raise ValueError('Unexpected LOTUS file listing')
    if sum(x['totalBytes'] for x in items) > 8 << 20:
        raise ValueError('LOTUS exceeds the authorized 8MiB cap')
    destination = ROOT/'assets/kaggle'/ref/'v2'
    if destination.exists() and any(destination.iterdir()):
        raise ValueError('LOTUS destination already has files; inspect receipts rather than overwrite')
    destination.mkdir(parents=True)
    used = 0
    records = []
    for item in items:
        name, expected = item['name'], item['totalBytes']
        path = destination/name
        partial = destination/(name+'.part')
        url = 'https://www.kaggle.com/api/v1/datasets/download/'+ref+'/'+quote(name, safe='')+'?datasetVersionNumber=2'
        request = urllib.request.Request(url, headers={'User-Agent': 'CASMI26-pinned-review/1.0'})
        size = 0
        with urllib.request.urlopen(request, context=ssl.create_default_context(), timeout=45) as response:
            length = response.headers.get('Content-Length')
            if response.status != 200 or (length and int(length) != expected):
                raise ValueError('Unexpected LOTUS response status/length')
            with partial.open('xb') as stream:
                while True:
                    block = response.read(128 << 10)
                    if not block:
                        break
                    size += len(block)
                    if size > expected or used+size > 8 << 20:
                        raise ValueError('LOTUS stream cap exceeded')
                    stream.write(block)
        if size != expected:
            raise ValueError('Incomplete LOTUS file')
        if name.endswith('.parquet'):
            with partial.open('rb') as stream:
                first = stream.read(4)
                stream.seek(-4, 2)
                last = stream.read(4)
            if first != b'PAR1' or last != b'PAR1':
                raise ValueError('LOTUS payload is not a raw Parquet file')
        else:
            partial.read_text(encoding='utf-8')
        partial.replace(path)
        used += size
        record = dict(ref=ref, version=2, file=name, local_path=str(path.relative_to(ROOT)),
            bytes=size, sha256=digest(path), acquired_at_utc=datetime.now(timezone.utc).isoformat(),
            source_kind='public_dataset_file', signed_url_or_credentials_persisted=False)
        write_once(destination/(name+'.receipt.json'), json_bytes(record))
        records.append(record)
    write_once(destination/'DOWNLOAD_MANIFEST.json', json_bytes(dict(status='complete', ref=ref,
        version=2, total_bytes=used, files=records, model_execution=False)))
    return records


def model_records(slug):
    base = ROOT/'assets/kaggle/bgunshui'/slug/'v1'
    manifest = read(base/'BUNDLE_MANIFEST.json')
    for entry in manifest['files']:
        path = base/entry['destination_file']
        if path.stat().st_size != entry['bytes'] or digest(path) != entry['sha256']:
            raise ValueError('New model input differs from its receipt')
    return manifest


def prepare(out, username):
    common_path = ROOT/'submission/flex_v56_review/local_asset_manifest.json'
    common = read(common_path)
    for entry in common:
        path = ROOT/entry['local_path'].replace('\\', '/')
        if not path.is_file() or path.stat().st_size != entry['actual_bytes']:
            raise ValueError('Existing common asset path/size differs')
        if COMMON.get(entry['dataset']) != entry['version']:
            raise ValueError('Common asset version differs')
    write_once(out/'common_local_asset_manifest.json', common_path.read_bytes())
    lotus_base = ROOT/'assets/kaggle/qwertykeypadapple/casmi26-lotus-candidates/v2'
    lotus_files = []
    for name in ('README.md', 'candidates_lotus.parquet'):
        path = lotus_base/name
        receipt = path.with_name(name+'.receipt.json')
        if path.is_file() and receipt.is_file():
            record = read(receipt)
            if digest(path) != record['sha256'] or path.stat().st_size != record['bytes']:
                raise ValueError('LOTUS receipt mismatch')
            lotus_files.append(record)
    aggregate = []
    for key, recipe in RECIPES.items():
        source_root = ROOT/'third_party'/recipe['source']
        source_path = source_root/'source.ipynb'
        if digest(source_path) != recipe['sha']:
            raise ValueError('Expected source snapshot changed')
        raw = source_path.read_bytes()
        notebook, upstream = read(source_path), read(source_root/'metadata.json')
        if upstream['currentVersionNumber'] != recipe['version']:
            raise ValueError('Unexpected upstream source version')
        pins, frozen = constants(notebook)
        folder = out/key
        write_once(folder/'notebook.ipynb', raw)
        write_once(folder/'upstream-metadata.json', (source_root/'metadata.json').read_bytes())
        write_once(folder/'frozen_baseline.ipynb', frozen)
        for name, text in pins['MODULES'].items():
            if Path(name).name != name:
                raise ValueError('Unsafe embedded helper path')
            write_once(folder/'embedded'/name, text.encode())
        models = [model_records(slug) for slug in recipe['models']]
        attachments = [f'{ref}/{version}' for ref, version in COMMON.items()]
        attachments += ['bgunshui/'+slug+'/1' for slug in recipe['models']]
        if key == 'tri_v30':
            attachments.append('qwertykeypadapple/casmi26-lotus-candidates/2')
        metadata = dict(id=username+'/'+recipe['slug'], title=recipe['title'], code_file='notebook.ipynb',
            language='python', kernel_type='notebook', is_private=True, enable_gpu=True, enable_internet=False,
            machine_shape=upstream['machineShape'], docker_image=upstream['dockerImage'],
            competition_sources=upstream['competitionDataSources'], dataset_sources=attachments, kernel_sources=[])
        if metadata['id'] == username+'/casmi26-flex-v56-baseline':
            raise ValueError('Never overwrite the existing .479 anchor')
        write_once(folder/'kernel-metadata.json', json_bytes(metadata))
        smoke = copy.deepcopy(notebook)
        mode = None
        replacements = 0
        for cell in smoke['cells']:
            if cell['cell_type'] != 'code':
                continue
            value = cell['source']
            text = ''.join(value) if isinstance(value, list) else value
            if re.search(r'^COMMIT_MODE\s*=', text, re.M):
                mode = re.search(r'^COMMIT_MODE\s*=\s*[\'"]([^\'"]+)', text, re.M).group(1)
                text, count = re.subn(r"^COMMIT_MODE\s*=\s*['\"][^'\"]+['\"]", "COMMIT_MODE = 'smoke'", text, count=1, flags=re.M)
                replacements += count
                cell['source'] = text.splitlines(keepends=True) if isinstance(value, list) else text
        if replacements != 1:
            raise ValueError('Exactly one commit-mode assignment required')
        smoke_raw = raw if mode == 'smoke' else json_bytes(smoke)
        write_once(folder/'smoke_review/notebook.ipynb', smoke_raw)
        write_once(folder/'smoke_review/kernel-metadata.json', json_bytes(metadata))
        patch = dict(original_sha256=recipe['sha'], smoke_sha256=hashlib.sha256(smoke_raw).hexdigest(),
            source_change={} if mode == 'smoke' else {'COMMIT_MODE': [mode, 'smoke']},
            hidden_scoring_route_modified=False, claimed_real_smoke_execution=False)
        write_once(folder/'smoke_review/patch_receipt.json', json_bytes(patch))
        view = dict(status='prepared_for_review_not_run', source_ref=upstream['ref'], source_version=recipe['version'],
            source_sha256=recipe['sha'], original_source_bytes_preserved=True,
            suggested_new_kernel_id=metadata['id'], original_commit_mode=mode,
            source_pins={k: pins[k] for k in ('FROZEN_SHA256', 'MODEL_PINS', 'MODULE_SHA256')},
            common_assets=dict(snapshot='common_local_asset_manifest.json', sha256=digest(common_path), files=len(common),
                present_and_size_checked=len(common), recorded_sha256_count=sum(bool(x['recorded_sha256']) for x in common),
                large_assets_fresh_rehashed=False), new_model_bundles=models,
            lotus_required=key == 'tri_v30', lotus_files=lotus_files if key == 'tri_v30' else [],
            missing_required=[] if key != 'tri_v30' or len(lotus_files) == 2 else ['LOTUS V2 files'],
            metadata_replacements=dict(removed_kernel_sources=upstream['kernelDataSources'],
                explicit_public_models=['bgunshui/'+slug+'/1' for slug in recipe['models']],
                input_versions_requested_explicitly=True, historical_private_weight_identity_proven=False),
            action_boundaries=dict(network_or_cloud_write=False, model_execution=False, smoke_completed=False, competition_submitted=False),
            limitations=['Public dependency replacement is a reproduction candidate, not proof of identical historical private weights.',
                'Upstream title/personal best is not this packet score; no score is reproduced by preparation.',
                'Source allows model fallback; acceptance must verify unique checkpoint hashes and full model coverage.',
                'V30 original fast commit is dummy-only; use the isolated smoke_review folder for a real12 query run.',
                'Preserved Docker digest/device request is not proof of current cloud allocation.',
                'New bgunshui weight licence remains Unknown; common component notices remain applicable.'])
        write_once(folder/'review.json', json_bytes(view))
        aggregate.append(dict(recipe=key, status=view['status'], source_version=recipe['version'],
            source_sha256=recipe['sha'], suggested_kernel_id=metadata['id'], original_commit_mode=mode,
            smoke_source_sha256=patch['smoke_sha256'], missing_required=view['missing_required']))
    write_once(out/'review_index.json', json_bytes(dict(status='prepared_for_review_not_run',
        private_offline=True, source_assets_originals_unchanged=True, recipes=aggregate)))
    return aggregate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUT)
    parser.add_argument('--username', default='stormseye')
    parser.add_argument('--download-lotus', action='store_true', help='Fetch only the separately authorized public LOTUS V2 two-file8MiB maximum')
    args = parser.parse_args()
    out = args.output.resolve()
    if not out.is_relative_to(ROOT) or out == ROOT or not re.fullmatch(r'[A-Za-z0-9_-]{1,50}', args.username):
        parser.error('Use a separate D: workspace directory and valid username')
    out.mkdir(parents=True, exist_ok=True)
    for name in ('TEMP', 'TMP'):
        os.environ[name] = str(ROOT/'.cache/tmp')
    if args.download_lotus:
        fetch_lotus(out)
    print(json.dumps(prepare(out, args.username), indent=2))


if __name__ == '__main__':
    main()
