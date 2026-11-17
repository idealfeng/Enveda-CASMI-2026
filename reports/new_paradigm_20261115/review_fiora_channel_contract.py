"""Pure-structure channel/mass-map review: never load model/dev predictions."""
from pathlib import Path
import hashlib,importlib.util,json,sys,time
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'assets/research/fiora_os_20261115/source_checkout'
TARGET=ROOT/'assets/research/fiora_os_20261115/dependencies-linux'
sys.path[:0]=[str(SOURCE),str(TARGET),str(ROOT)]
started=time.perf_counter()
import numpy as np
import pandas as pd
import torch
from fiora.cli.predict import build_metabolites
from fiora.MOL.constants import DEFAULT_MODES
from fiora.MS.SimulationFramework import SimulationFramework
torch.set_num_threads(1)
sp=importlib.util.spec_from_file_location('read_preparer',ROOT/'scripts/prepare_fiora_tims_pilot_20261115.py')
preparer=importlib.util.module_from_spec(sp);sp.loader.exec_module(preparer)
params=json.loads((ROOT/'runs/fiora_tims_model_20261115/fiora_OS_tims_migrated_params.json').read_text())
records=[dict(Name=name,SMILES=smi,Precursor_type='[M+H]+',CE=35.,Instrument_type='timsTOF') for name,smi in [('ethanol','CCO'),('caffeic','O=C(O)/C=C/c1ccc(O)c(O)c1'),('phenol','Oc1ccccc1'),('symmetric','CCOCC'),('charged','C[N+](C)(C)CCO'),('disconnected','CCO.CC')]]
frame,invalid=build_metabolites(pd.DataFrame(records),params)
if len(invalid):raise ValueError('Pure fixture graph invalid')
def aggregate(mz,intensity):
    out={}
    for m,v in zip(mz,intensity):
        if float(v)>0:out[float(m)]=out.get(float(m),0.)+float(v)
    return out
framework=SimulationFramework(dev='cpu');results=[]
for _,row in frame.iterrows():
    mol=row['Metabolite'];mz,forward,prec=preparer.compiled_mass_map(mol,DEFAULT_MODES)
    # Unique sentinel intensities identify swapped side/mode contributions.
    values=torch.arange(1,len(mz)+1,dtype=torch.float64)/101.
    mol.review_probs=values
    actual=framework.simulate_spectrum(mol,'review_probs',precursor_mode='[M+H]+',min_intensity=.001)
    native=aggregate(actual['mz'],actual['intensity'])
    use=forward&np.isfinite(mz)&(values.numpy()>.001)
    sidecar=aggregate(mz[use],values.numpy()[use])
    if set(native)!=set(sidecar):raise ValueError('Native versus sidecar mass set differs: '+row['Name'])
    delta=max((abs(native[m]-sidecar[m]) for m in native),default=0.)
    if delta>1e-10:raise ValueError('Native versus sidecar intensity contribution differs')
    if bool(forward[-2]) or not bool(forward[-1]) or mz[-1]!=prec or mz[-2]!=prec:raise ValueError('Duplicate precursor channel contract differs')
    results.append(dict(name=row['Name'],directed_edges=len(mol.edges_as_tuples),compiled_elements=len(mz),forward_mass_channels=int(use.sum()),native_unique_mass_count=len(native),native_vs_sidecar_max_abs_aggregated_intensity_delta=delta,native_ring_skip_and_direction_mass_map_equal=True))
out=ROOT/'reports/new_paradigm_20261115/fiora_channel_contract_review.json'
if out.exists():raise FileExistsError('Preserve prior review')
result=dict(status='passed_pure_structure_native_mass_map_contract',model_loaded=False,development_predictions_read=False,label_cache_results_read=False,fixtures=results,seconds=time.perf_counter()-started,preparer_sha256=hashlib.sha256((ROOT/'scripts/prepare_fiora_tims_pilot_20261115.py').read_bytes()).hexdigest(),native_simulation_sha256=hashlib.sha256((SOURCE/'fiora/MS/SimulationFramework.py').read_bytes()).hexdigest(),native_modes=DEFAULT_MODES,source_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),boundary='Six synthetic graph fixtures with distinct sentinel channel intensities; no trained model, real spectrum labels, dev score, fitting, or training.')
out.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
