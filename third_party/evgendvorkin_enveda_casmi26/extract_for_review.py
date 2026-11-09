"""Statically extract Notebook cells and literal source strings; execute no source."""
from pathlib import Path
import ast
import hashlib
import json


ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parents[1]
notebook = json.loads((ROOT / 'source.ipynb').read_text(encoding='utf-8'))
metadata = json.loads((ROOT / 'metadata.json').read_text(encoding='utf-8'))
cells, payloads, fold_pins = [], [], {}
for index, cell in enumerate(notebook['cells']):
    source = cell.get('source', '')
    source = ''.join(source) if isinstance(source, list) else source
    folder = ROOT / 'cells'
    folder.mkdir(exist_ok=True)
    suffix = '.py' if cell['cell_type'] == 'code' else '.md'
    path = folder / f'cell_{index:02d}{suffix}'
    path.write_text(source, encoding='utf-8')
    record = dict(index=index, kind=cell['cell_type'], bytes=path.stat().st_size,
                  file=str(path.relative_to(ROOT)), sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    if cell['cell_type'] == 'code':
        tree = ast.parse(source)
        record['syntax_valid'] = True
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            names = [item.id for item in node.targets if isinstance(item, ast.Name)]
            if len(names) != 1:
                continue
            name = names[0]
            try:
                value = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                continue
            if name == 'FOLD_CHECKPOINT_SHA256':
                fold_pins = value
            sources = value if name == 'ENG_FILES' and isinstance(value, dict) else (
                {name + '.py': value} if name in {'CORE', 'RUNNER', 'V17_PATCH'} and isinstance(value, str) else {})
            for filename, code in sources.items():
                if Path(filename).name != filename:
                    raise ValueError('Unexpected embedded filename')
                ast.parse(code)
                target = ROOT / 'embedded' / filename
                target.parent.mkdir(exist_ok=True)
                target.write_text(code, encoding='utf-8')
                payloads.append(dict(cell=index, assignment=name, file=str(target.relative_to(ROOT)),
                    sha256=hashlib.sha256(target.read_bytes()).hexdigest(), syntax_valid=True))
    cells.append(record)
fold_assets = []
for name, expected in fold_pins.items():
    path = WORKSPACE / 'assets/kaggle/dmitriigluzdov/casmi26-fold-safe-fpnet/v5' / name
    actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    fold_assets.append(dict(name=name, upstream_required_sha256=expected,
        locally_present=path.is_file(), local_sha256=actual,
        local_hash_matches=actual == expected if actual else None))
report = dict(ref=metadata['ref'], version=metadata['currentVersionNumber'],
    source_sha256=hashlib.sha256((ROOT / 'source.ipynb').read_bytes()).hexdigest(),
    code_cells=sum(c['kind'] == 'code' for c in cells), total_cells=len(cells), cells=cells,
    literal_source_payloads=payloads, fold_asset_check=fold_assets,
    dataset_sources=metadata['datasetDataSources'], kernel_sources=metadata['kernelDataSources'],
    executed=False, model_weights_downloaded=False,
    score_evidence='No current V27 leaderboard score established by source download or comments.')
(ROOT / 'source_audit.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: v for k, v in report.items() if k not in {'cells', 'literal_source_payloads'}}, indent=2))
