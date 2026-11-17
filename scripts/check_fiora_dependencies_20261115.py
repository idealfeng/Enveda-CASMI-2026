from pathlib import Path
import importlib.util,json,sys
ROOT=Path(__file__).resolve().parents[1]
names=['torch','torch_geometric','torch_scatter','torch_sparse','rdkit','pandas','numpy','scipy','sklearn','yaml','tqdm','dill','treelib','IPython','matplotlib','networkx','aiohttp','fsspec','jinja2','psutil','requests','pyparsing','xxhash','regex','seaborn']
report=dict(python=sys.version,executable=sys.executable,modules={n:importlib.util.find_spec(n) is not None for n in names},packages_installed=False)
out=ROOT/'reports/new_paradigm_20261115';out.mkdir(exist_ok=True,parents=True)
(out/'fiora_dependency_presence.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
