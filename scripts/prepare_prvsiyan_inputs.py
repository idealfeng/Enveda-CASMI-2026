"""Build a version-specific Linux input view without copying large datasets."""
from pathlib import Path
import argparse
import json

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, default=ROOT/'runs/inputs/prvsiyan_v43')
args = parser.parse_args()
manifest = json.loads((ROOT/'third_party/prvsiyan_analog/minimum_inputs.json').read_text())
output = args.output.resolve()
output.mkdir(parents=True, exist_ok=True)
missing = []
links = []
for dependency in manifest['dependencies']:
    ref = dependency['ref']
    version = dependency['version_number_observed']
    target = ROOT/'assets/kaggle'/ref/f'v{version}'
    destination = output/'datasets'/ref
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_symlink():
        if destination.resolve() != target.resolve():
            raise ValueError(f'Existing link points to another dataset version: {destination}')
    elif destination.exists():
        raise FileExistsError(destination)
    else:
        destination.symlink_to(target, target_is_directory=True)
    links.append({'ref': ref, 'version': version, 'target': str(target)})
    for file in dependency['files']:
        path = target/file['name']
        if not path.is_file() or path.stat().st_size != file['bytes']:
            missing.append({'ref':ref,'version':version,'file':file['name'],'expected_bytes':file['bytes']})
data = ROOT/'enveda-CASMI26-molecule-id-mass-spectra'
destination = output/'competitions'/data.name
destination.parent.mkdir(parents=True, exist_ok=True)
if not destination.exists():
    destination.symlink_to(data, target_is_directory=True)
report = {'input_root':str(output),'links':links,'missing':missing,'ready':not missing,
          'note':'Source V43 is exact; these are observed current asset versions, not proven original run pins.'}
(output/'input_receipt.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'input_root':str(output),'ready':not missing,'missing_files':len(missing)},indent=2))
if missing:
    raise SystemExit(1)
