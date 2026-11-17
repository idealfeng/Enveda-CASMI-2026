"""No-model contract checks for generated-source isolation hooks."""
from pathlib import Path
import ast,csv,hashlib,importlib.util,json,sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.cache/rdkit-official-linux-2026033'))
sys.path.insert(0,str(ROOT))
from scripts import champion_reference_masks_20261115 as masks
from validation import metric
import pyarrow.parquet as pq
import numpy as np

OUT=ROOT/'reports/champion_error_decomposition_20261115/source_contract_preflight'
OUT.mkdir(parents=True,exist_ok=False)
OLD=ROOT/'runs/generation_production_20261113_r2/kaggle/working'
PANEL=ROOT/'runs/validation_pilot_v2_20261104'
with (PANEL/'truth.csv').open(encoding='utf-8-sig',newline='') as f:truth=list(csv.DictReader(f))
ids=json.loads((PANEL/'class2_exclusion_keys.json').read_text())['blocked_official_identities']
notebook=json.loads((ROOT/'submission/optimization_20261109/mass_guarded_extlib/notebook.ipynb').read_text())
outer20=''.join(notebook['cells'][20]['source'])
checks={};summary=[]
metric.assert_official_rdkit()
for mode in ('class1','class2','class3'):
    work=OUT/mode;work.mkdir()
    c=dict(work_root=str(work),queries_file=str(PANEL/'queries.parquet'),inference_queries_file=str(PANEL/'queries.parquet'),exclusion_rows_file=str(PANEL/('query_duplicate_exclusion_rows.parquet' if mode=='class1' else 'class2_exclusion_rows.parquet')),exclusion_keys_file=str(PANEL/'class2_exclusion_keys.json'),base_train_rows=2539608,cohort_policy='global48 diagnostic source-contract check only',reference_mode=mode,blocked_official_identities=ids)
    cp=work/'config.json';cp.write_text(json.dumps(c))
    e2=work/'eng_runner.py';e2.write_bytes((OLD/'eng/eng_runner.py').read_bytes())
    pc=work/'pc_runner.py';pc.write_bytes((OLD/'pc_runner.py').read_bytes())
    masks.patch_generated_e2(e2,cp);masks.patch_generated_pubchem(pc,cp)
    ast.parse(e2.read_text());ast.parse(pc.read_text())
    patched=masks.patch_outer_static_cell(outer20,cp);ast.parse(patched)
    checks[mode+'_generated_source_parses']=True
    checks[mode+'_c3_static_semantics']=masks.static_keep(truth[0]['smiles'],cp)==(mode!='class3')
    checks[mode+'_unrelated_static_kept']=masks.static_keep('CCO',cp)
    sp=importlib.util.spec_from_file_location('helper_'+mode,ROOT/'scripts/external_library_overlay_20261109.py')
    helper=importlib.util.module_from_spec(sp);sp.loader.exec_module(helper)
    masks.install_ab_observer_filter(cp,helper)
    source=OLD/'p2s_code/alex_v12_external_function.py'
    fn,sites=helper.load_observed(source,masks.sha(source),lambda *args:None,lambda *args:None)
    # Compile actual source; call only the isolated reference decision closure.
    real_fn=next(cell.cell_contents for cell in fn.__closure__ if callable(cell.cell_contents))
    allow=real_fn.__globals__['_champion_allow_ref']
    dummy=(1,12345.,np.array([11.,22.,33.]),np.array([1.,.5,.1]),'',truth[0]['smiles'],100.)
    checks[mode+'_AB_target_identity_mask']=bool(allow('A',dummy))==(mode=='class1')
    frame=pq.read_table(PANEL/'queries.parquet',columns=['precursor_mz','ionization_mode','ms2_mzs','ms2_normalized_intensities']).slice(0,1).to_pydict()
    prec=float(frame['precursor_mz'][0]);mz=np.asarray(frame['ms2_mzs'][0]);it=np.asarray(frame['ms2_normalized_intensities'][0]);ok=(mz>0)&(it>0)&(mz<=prec+.5);mode_q=1 if 'pos' in frame['ionization_mode'][0].lower() else -1
    copy=(mode_q,prec,mz[ok],it[ok],'','CCO',prec)
    checks[mode+'_AB_query_content_mask']=not allow('B',copy)
    summary.append(dict(mode=mode,sites=sites,patched_e2_sha256=masks.sha(e2),patched_pc_sha256=masks.sha(pc),patched_outer20_sha256=hashlib.sha256(patched.encode()).hexdigest()))
result=dict(status='passed_model_free_source_contracts' if all(checks.values()) else 'failed',checks=checks,modes=summary,source_script_sha256=masks.sha(ROOT/'scripts/champion_reference_masks_20261115.py'),model_execution=False,actual_library_initialization=False,full_production_execution=False,boundary='Generated real-source marker/AST checks and reference predicate checks only. No model or full Library/index initialization; runtime completion must be checked by canary.')
(OUT/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
if not all(checks.values()):raise ValueError('Source contract check failed')
