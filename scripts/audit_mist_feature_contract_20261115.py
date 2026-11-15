"""Compare CASMI tensors to the frozen upstream PeakFormula implementation.

No model forward, no labels, no ranking metrics, and no source modifications.
"""
from pathlib import Path
from functools import lru_cache
from typing import ClassVar
from collections import Counter
from types import SimpleNamespace
import ast
import hashlib
import importlib.util
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/mist_contract_audit_20261115'
SOURCE=ROOT/'assets/research/mist_msg_20261114/source/src/mist/data/featurizers.py'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    import numpy as np
    import pandas as pd
    spec=importlib.util.spec_from_file_location('mist_adapter_audited',ROOT/'scripts/mist_casmi_adapter_20261114.py')
    adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)
    chem,funcs=adapter.upstream_features()
    nodes=ast.parse(SOURCE.read_text(encoding='utf-8')).body
    wanted=[n for n in nodes if isinstance(n,ast.ClassDef) and n.name=='PeakFormula']
    scope=dict(np=np,json=json,Path=Path,ClassVar=ClassVar,chem_utils=chem,assign_subformulae=funcs['assign_subformulae'])
    module=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),*wanted],type_ignores=[])
    ast.fix_missing_locations(module);exec(compile(module,str(SOURCE),'exec'),scope)
    PeakFormula=scope['PeakFormula']
    work=ROOT/'runs/mist_active_evaluation_20261114/inference'
    query=pd.read_parquet(work/'query_official_columns.parquet')
    by_id={(str(r.molecule_id),str(r.spectrum_id)):r for r in query.itertuples(index=False)}
    events=json.loads((work/'feature_events.json').read_text())
    comparisons=[];frames=[];intensity_error=[];reason_counts=Counter()
    for event in events:
        reason_counts[event['reason']]+=1
        if event['reason']!='represented':continue
        row=by_id[(event['molecule_id'],event['spectrum_id'])];formula=event['formula']
        actual,info=adapter.feature_for_spectrum(row,formula,chem,funcs)
        ion=adapter.ALIASES.get(str(row.adduct),str(row.adduct))
        text='>parentmass '+str(float(row.precursor_mz))+'\n'+'\n'.join(str(float(m))+' '+str(float(v)) for m,v in zip(row.ms2_mzs,row.ms2_normalized_intensities))
        peaks=funcs['merge_ms_spectrum'](text)
        tree=funcs['assign_subformulae'](dict(cand_form=formula,cand_ion=ion,output_tbl=dict(mz=peaks[:,0].tolist(),ms2_inten=peaks[:,1].tolist()) if len(peaks) else None),adapter.CONFIG['subformula_ppm'])
        feature=PeakFormula.__new__(PeakFormula)
        feature.max_peaks=adapter.CONFIG['assigned_peak_cap'];feature.subformula_ppm=adapter.CONFIG['subformula_ppm'];feature.merge_collision_energies=False
        class Store:
            def read(self,key):return json.dumps(tree)
        feature.spectrum_store=Store()
        class Spectrum:
            ionization=ion
            def get_spec_name(self):return 'actual_casmi_conditioned'
            def get_spectra_formula(self):return formula
            def get_instrument(self):return str(row.instrument_type)
        expected=feature.featurize(Spectrum(),train_mode=False);n=len(expected['peak_type'])
        checks=dict(formula=np.array_equal(actual['form_vec'][:n],expected['form_vec']),
                    ion=np.array_equal(actual['ion_vec'][:n],expected['ion_vec']),
                    intensity=np.array_equal(actual['intens'][:n],expected['frag_intens']),
                    types=np.array_equal(actual['types'][:n],expected['peak_type']),
                    length=actual['num_peaks']==n,instrument=actual['instruments']==expected['instrument'],
                    exactly_one_cls=int((actual['types']==3).sum())==1,
                    zero_padding=not actual['form_vec'][n:].any() and not actual['intens'][n:].any())
        if not all(checks.values()):raise ValueError('Actual tensor contract mismatch')
        intensity_error.append(float(np.max(np.abs(actual['intens'][:n]-expected['frag_intens'].astype(np.float16).astype(np.float32)))))
        comparisons.append(dict(molecule_id=event['molecule_id'],spectrum_id=event['spectrum_id'],formula=formula,checks=checks))
        frames.append(actual)
    stats={}
    arrays=dict(form_vec=np.stack([f['form_vec'] for f in frames]),ion_vec=np.stack([f['ion_vec'] for f in frames]),
                intens=np.stack([f['intens'] for f in frames]),types=np.stack([f['types'] for f in frames]),
                lengths=np.asarray([f['num_peaks'] for f in frames]),instruments=np.asarray([f['instruments'] for f in frames]))
    valid=np.arange(arrays['types'].shape[1])[None,:]<arrays['lengths'][:,None]
    frag=valid&(arrays['types']==0)
    stats['conditional_rows']=len(frames);stats['token_lengths_quantiles']=np.quantile(arrays['lengths'],[0,.25,.5,.75,1]).tolist()
    stats['fragment_intensity_quantiles']=np.quantile(arrays['intens'][frag],[0,.25,.5,.75,1]).tolist()
    stats['ion_counts']={str(k):int(v) for k,v in Counter(arrays['ion_vec'][valid].tolist()).items()}
    stats['instrument_counts']={str(k):int(v) for k,v in Counter(arrays['instruments'].tolist()).items()}
    OUT.mkdir(parents=True,exist_ok=True)
    np.savez(OUT/'actual_casmi_features.npz',**arrays)
    result=dict(status='passed_actual_upstream_tensor_parity',queries=len(query.molecule_id.unique()),conditional_rows=len(frames),
                upstream_source_sha256=sha(SOURCE),adapter_sha256=sha(ROOT/'scripts/mist_casmi_adapter_20261114.py'),
                all_represented_rows_exact_upstream_pre_cache_tensors=True,comparisons=comparisons,casmi_feature_statistics=stats,
                float16_training_cache_rounding_max_abs_intensity_difference=max(intensity_error),event_reason_counts=dict(reason_counts),
                no_model_forward=True,no_truth_read=True,
                limitation='Parity is against upstream PeakFormula given the SAME reconstructed subformula tree. MSG training uses preassigned source trees; this does not prove CASMI reassignment matches MSG historical preprocessing. Adapter skips unassigned spectra while upstream supports CLS-only trees.')
    (OUT/'feature_tensor_parity.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['status','conditional_rows','float16_training_cache_rounding_max_abs_intensity_difference','event_reason_counts']}))

if __name__=='__main__':main()
