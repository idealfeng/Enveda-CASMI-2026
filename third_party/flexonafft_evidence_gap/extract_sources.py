"""Extract literal embedded sources without executing the fetched notebook."""
import ast
import base64
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def literals(code):
    values = {}
    for node in ast.parse(code).body:
        if not isinstance(node, ast.Assign):
            continue
        try:
            value = ast.literal_eval(node.value)
        except (ValueError, TypeError, SyntaxError):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                values[target.id] = value
            elif (
                isinstance(target, ast.Subscript)
                and isinstance(target.value, ast.Name)
                and isinstance(target.slice, ast.Constant)
            ):
                name = target.value.id
                if isinstance(values.get(name), dict):
                    values[name][target.slice.value] = value
    return values


def extract(version):
    folder = ROOT / version
    nb_path = folder / 'original.ipynb'
    notebook = json.loads(nb_path.read_text(encoding='utf-8'))
    embedded = folder / 'embedded'
    embedded.mkdir(exist_ok=True)
    values = {}
    for cell in notebook['cells']:
        if cell.get('cell_type') == 'code':
            source = cell['source']
            source = ''.join(source) if isinstance(source, list) else source
            values.update(literals(source))
    for name, text in values['MODULES'].items():
        assert Path(name).name == name
        raw = text.encode('utf-8')
        assert hashlib.sha256(raw).hexdigest() == values['MODULE_SHA256'][name]
        (embedded / name).write_bytes(raw)
    frozen = base64.b64decode(values['FROZEN_B64'])
    assert hashlib.sha256(frozen).hexdigest() == values['FROZEN_SHA256']
    (embedded / 'frozen_0465.ipynb').write_bytes(frozen)
    frozen_nb = json.loads(frozen)
    frozen_cells = embedded / 'frozen_cells'
    frozen_cells.mkdir(exist_ok=True)
    for idx, cell in enumerate(frozen_nb['cells']):
        if cell.get('cell_type') != 'code':
            continue
        source = cell['source']
        source = ''.join(source) if isinstance(source, list) else source
        (frozen_cells / f'cell_{idx:02d}.py').write_text(source, encoding='utf-8')
        for name, value in literals(source).items():
            if name == 'ENG_FILES' and isinstance(value, dict):
                engine = embedded / 'engine2_sources'
                engine.mkdir(exist_ok=True)
                for filename, code in value.items():
                    target = (engine / filename).resolve()
                    assert target.is_relative_to(engine.resolve())
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(code, encoding='utf-8')
            elif name in ('PROBE', 'RUNNER', 'CORE', 'V17_PATCH') and isinstance(value, str):
                (embedded / (name.lower() + '_pubchem.py')).write_text(value, encoding='utf-8')
    for name, filename in [('_physical', 'frag_rescore.py'), ('_post', 'parallax_physical.py'), ('_PUBLIC_RERANKER', 'parallax_public_provenance.py')]:
        if name in values:
            (embedded / filename).write_text(values[name], encoding='utf-8')
    receipt = {
        'notebook_sha256': hashlib.sha256(nb_path.read_bytes()).hexdigest(),
        'frozen_sha256': values['FROZEN_SHA256'],
        'verified_module_sha256': values['MODULE_SHA256'],
        'model_pins': values['MODEL_PINS'],
        'note': 'AST literal extraction only; no downloaded code executed.',
    }
    (folder / 'extraction_receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(version, 'verified helper modules:', len(values['MODULES']))


if __name__ == '__main__':
    for version in ('v56', 'v61'):
        extract(version)
