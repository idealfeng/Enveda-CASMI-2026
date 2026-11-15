"""Candidate-formula-conditioned MIST smoke on genuine CASMI input columns.

Does not call the canonical MSG-only CLI or mislabel CASMI as MSG. Frozen
upstream model and subformula functions are reused without modifying source.
No training, truth labels, efficacy metrics, or cloud submissions.
"""
from pathlib import Path
from functools import lru_cache
from collections import defaultdict, Counter
import argparse
import ast
import hashlib
import json
import math
import os
import resource
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/'assets/research/mist_msg_20261114/source'
CHECKPOINT = ROOT/'assets/research/mist_msg_20261114/checkpoints/mist_msg_noaug.ckpt'
WORK = ROOT/'runs/generation_production_20261113_r2/kaggle/working'
OFFICIAL_SITE = ROOT/'.cache/rdkit-official-linux-2026033'
if OFFICIAL_SITE.exists(): sys.path.insert(0, str(OFFICIAL_SITE))
sys.path.insert(0, str(SOURCE/'src'))

EXPECTED_CHECKPOINT = '6f8df582df36aa4a984f120efee14ee0a62f3a7723caa770b856a6e704236727'
OFFICIAL_COLUMNS = ['molecule_id','spectrum_id','ms2_mzs','ms2_normalized_intensities',
                    'base_peak_intensity','adduct','ionization_mode','instrument_type',
                    'precursor_mz','collision_energy_orig','collision_energy_ev','collision_energy_orig_units']
ALIASES = {'[M+NH4]+':'[M+H3N+H]+', '[M-2H2O+H]+':'[M-H4O2+H]+'}
CONFIG = dict(max_formula_groups=3, max_formula_states=2_000_000, raw_peak_cap=60,
              assigned_peak_cap=10, subformula_ppm=20., precursor_ppm=20.,
              precursor_absolute_da=.0025, feature_batch_size=4, fingerprint_bits=4096,
              morgan_radius=2, include_chirality=False, spectrum_pooling='mean_probabilities',
              score='soft_tanimoto_probability_vs_binary', instrument_policy='upstream_unknown_default',
              rerank_scope='observed_original_slots_within_same_formula', negative_policy='exact_baseline_fallback')


def sha(path):
    with Path(path).open('rb') as handle: return hashlib.file_digest(handle, 'sha256').hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False, default=str)+'\n', encoding='utf-8')


def verify_source():
    receipt=json.loads((ROOT/'reports/discussion_review_20261114/mist/download_receipt.json').read_text())
    for item in receipt['files']:
        if sha(SOURCE/item['path'])!=item['sha256']: raise ValueError('Frozen MIST source changed: '+item['path'])
    return receipt['commit']


def upstream_features():
    import numpy as np
    from mist.utils import chem_utils
    path=SOURCE/'src/mist/data/featurizers.py'
    tree=ast.parse(path.read_text(encoding='utf-8'))
    wanted={'merge_ms_spectrum','_heavy_formula_space','assign_subformulae'}
    nodes=[n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in wanted]
    if {n.name for n in nodes}!=wanted: raise ValueError('Upstream feature entry points changed')
    scope=dict(np=np,chem_utils=chem_utils,lru_cache=lru_cache)
    # The exact functions require no HDF5; importing the whole upstream module
    # would unnecessarily require h5py for an adapter that reads Parquet.
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),scope)
    return chem_utils, scope


def feature_for_spectrum(row, formula, chem, funcs):
    import numpy as np
    ion=ALIASES.get(str(row.adduct),str(row.adduct))
    if str(row.ionization_mode).lower()!='positive' or ion not in chem.ION_LST:
        return None, dict(reason='unsupported_negative_or_adduct', adduct=str(row.adduct))
    root=chem.formula_to_dense(formula)
    states=math.prod(int(root[i])+1 for i in range(len(root)) if root[i]>0 and i!=chem.element_to_ind['H'])
    if states>CONFIG['max_formula_states']:
        return None,dict(reason='formula_state_cap',states=states)
    expected=chem.formula_mass(formula)+chem.ion_to_mass[ion]
    error=abs(float(row.precursor_mz)-expected)
    if error>max(CONFIG['precursor_absolute_da'],abs(expected)*CONFIG['precursor_ppm']*1e-6):
        return None,dict(reason='candidate_formula_precursor_mismatch',error_da=error)
    mz=np.asarray(row.ms2_mzs,dtype=float);inten=np.asarray(row.ms2_normalized_intensities,dtype=float)
    if mz.ndim!=1 or inten.shape!=mz.shape or not np.isfinite(mz).all() or not np.isfinite(inten).all():
        return None,dict(reason='invalid_raw_peaks')
    text='>parentmass '+str(float(row.precursor_mz))+'\n'+'\n'.join(str(float(m))+' '+str(float(v)) for m,v in zip(mz,inten))
    peaks=funcs['merge_ms_spectrum'](text)
    tree=funcs['assign_subformulae'](dict(cand_form=formula,cand_ion=ion,output_tbl=dict(mz=peaks[:,0].tolist(),ms2_inten=peaks[:,1].tolist()) if len(peaks) else None),CONFIG['subformula_ppm'])
    table=tree['output_tbl']
    if table is None: return None,dict(reason='no_assigned_fragment',raw_peaks=len(mz),retained_peaks=len(peaks))
    order=np.argsort(np.asarray(table['ms2_inten'],dtype=float))[::-1][:CONFIG['assigned_peak_cap']]
    forms=[chem.formula_to_dense(table['formula'][int(i)]) for i in order]+[root]
    intensities=[float(table['ms2_inten'][int(i)]) for i in order]+[1.]
    n=len(forms);width=CONFIG['assigned_peak_cap']+1
    form_vec=np.zeros((width,18),dtype=np.float32);form_vec[:n]=forms
    ion_vec=np.zeros(width,dtype=np.int64);ion_vec[:n]=chem.get_ion_idx(ion)
    intensity=np.zeros(width,dtype=np.float32);intensity[:n]=intensities
    types=np.zeros(width,dtype=np.int64);types[n-1]=3
    feature=dict(form_vec=form_vec,ion_vec=ion_vec,intens=intensity,types=types,
                 num_peaks=n,instruments=chem.get_instr_idx(str(row.instrument_type)))
    info=dict(reason='represented',ion=ion,source_adduct=str(row.adduct),raw_peaks=len(mz),
              retained_peaks=len(peaks),assigned_fragments=len(table['formula']),selected_fragments=n-1,
              formula_states=states,precursor_error_da=error,instrument=str(row.instrument_type),
              instrument_index=feature['instruments'])
    return feature, info


def run(args):
    import numpy as np
    import pandas as pd
    import rdkit
    from rdkit import Chem, DataStructs
    from rdkit.Chem import rdMolDescriptors, rdFingerprintGenerator
    if rdkit.__version__!='2026.03.3': raise ValueError('Official RDKit 2026.03.3 required')
    out=args.output.resolve()
    if not out.is_relative_to(ROOT) or out==ROOT:raise ValueError('Output must stay on D workspace')
    out.mkdir(exist_ok=False,parents=True)
    started=time.monotonic();commit=verify_source();chem,funcs=upstream_features()
    candidates=pd.read_csv(args.candidates,dtype=str,keep_default_na=False)
    if list(candidates.columns)!=['molecule_id','smiles'] or not candidates.molecule_id.is_unique:raise ValueError('Candidate CSV schema')
    query=pd.read_parquet(args.test,columns=OFFICIAL_COLUMNS)
    input_spectra_before_scope=len(query)
    query=query.loc[query.molecule_id.astype(str).isin(set(candidates.molecule_id))].copy()
    if set(query.molecule_id.astype(str))!=set(candidates.molecule_id):raise ValueError('Query/candidate scope mismatch')
    save(out/'input_manifest.json',dict(input_dataset='CASMI26 candidate-CSV-scoped official spectrum columns',
         model_training_dataset='MassSpecGym real spectra',conditioning='candidate_formula_per_group_no_truth',
         candidate_path=str(args.candidates),candidate_sha256=sha(args.candidates),test_path=str(args.test),
         test_sha256=sha(args.test),read_columns=OFFICIAL_COLUMNS,truth_columns_read=[],configuration=CONFIG,
         query_scope='Exact molecule IDs declared in frozen candidate CSV',
         input_spectra_before_scope=input_spectra_before_scope,selected_spectra=len(query),
         source_commit=commit,source_receipt_sha256=sha(ROOT/'reports/discussion_review_20261114/mist/download_receipt.json'),
         source_note='The source parquet may carry historical diagnostic truth columns; this adapter projects only the official whitelist.'))
    query.to_parquet(out/'query_official_columns.parquet',index=False)
    frames=[];events=[];groups=[];candidate_records=[];formula_cache={};unsupported=[]
    features_started=time.monotonic()
    for row in candidates.itertuples(index=False):
        mid=str(row.molecule_id);guesses=row.smiles.split(';');forms=[];formula_order=[]
        for rank,smiles in enumerate(guesses,1):
            mol=Chem.MolFromSmiles(smiles)
            if mol is None:raise ValueError('Invalid actual candidate SMILES')
            formula=rdMolDescriptors.CalcMolFormula(mol);forms.append(formula)
            if formula not in formula_order:formula_order.append(formula)
            candidate_records.append(dict(molecule_id=mid,original_rank=rank,smiles=smiles,formula=formula,score=None,represented=False))
        chosen=formula_order[:CONFIG['max_formula_groups']]
        subset=query.loc[query.molecule_id.astype(str)==mid]
        for formula in chosen:
            group_id=len(groups);indices=[]
            for spectrum in subset.itertuples(index=False):
                tick=time.monotonic()
                try:feature,info=feature_for_spectrum(spectrum,formula,chem,funcs)
                except ValueError as error:
                    feature=None;info=dict(reason='unsupported_candidate_formula',error_type=type(error).__name__)
                info.update(molecule_id=mid,spectrum_id=str(spectrum.spectrum_id),formula=formula,feature_seconds=time.monotonic()-tick)
                if feature is not None:
                    indices.append(len(frames));frames.append(feature);info['feature_row']=len(frames)-1
                events.append(info)
            groups.append(dict(molecule_id=mid,formula=formula,feature_rows=indices,
                original_candidate_ranks=[i+1 for i,f in enumerate(forms) if f==formula],
                selected_from_all_formulas=formula_order,formula_group_cap=CONFIG['max_formula_groups']))
        if not any(g['feature_rows'] for g in groups if g['molecule_id']==mid):unsupported.append(mid)
    feature_seconds=time.monotonic()-features_started
    save(out/'feature_events.json',events);save(out/'formula_groups.json',groups)
    save(out/'preparation.json',dict(status='prepared_actual_candidate_formula_features',queries=len(candidates),spectra=len(query),
          feature_rows=len(frames),groups=len(groups),feature_seconds=feature_seconds,unsupported_query_fallback=unsupported,
          reasons=dict(Counter(e['reason'] for e in events)),truth_metrics_computed=False))
    if args.prepare_only:return dict(status='prepared_only_no_model',feature_rows=len(frames))
    if not frames:
        table=pd.DataFrame(candidate_records);table.to_parquet(out/'candidate_scores.parquet',index=False)
        (out/'submission_mist_component.csv').write_bytes(args.candidates.read_bytes())
        result=dict(status='passed_supported_input_fallback_only',queries=len(candidates),spectra=len(query),
             conditional_feature_rows=0,represented_candidates=0,unsupported_query_fallback=unsupported,
             checks=dict(frozen_source_verified=True,official_query_columns_only=list(query.columns)==OFFICIAL_COLUMNS,
                         all_queries_declared_fallback=set(unsupported)==set(candidates.molecule_id),
                         no_unearned_neural_scores=not any(r['represented'] for r in candidate_records),
                         exact_baseline_csv=sha(out/'submission_mist_component.csv')==sha(args.candidates)),
             feature_seconds=feature_seconds,source_commit=commit,adapter_sha256=sha(__file__),
             output_csv_sha256=sha(out/'submission_mist_component.csv'),actual_model_executed=False,
             new_training=False,truth_labels_read=False,truth_metrics_computed=False,
             limitation='No supported positive formula/spectrum inputs; exact baseline preserved without model inference.')
        if not all(result['checks'].values()):raise ValueError('Unsupported-input fallback checks failed')
        save(out/'verification.json',result);return result
    if sha(CHECKPOINT)!=EXPECTED_CHECKPOINT or CHECKPOINT.stat().st_size!=289222619:raise ValueError('Checkpoint pin mismatch')
    import torch
    from mist.models.scaled_mist import ScaledMIST,count_parameters
    torch.set_num_threads(4);torch.manual_seed(0)
    if args.device=='cuda' and not torch.cuda.is_available():raise RuntimeError('Requested actual CUDA inference unavailable')
    device=torch.device(args.device);load_started=time.monotonic()
    checkpoint=torch.load(CHECKPOINT,map_location='cpu',weights_only=True)
    if checkpoint['config']['data']['dataset_name']!='msg_all':raise ValueError('Checkpoint training provenance differs')
    model=ScaledMIST(**checkpoint['config']['model']);load=model.load_state_dict(checkpoint['ema_model'],strict=True)
    if count_parameters(model)!=72296996:raise ValueError('Actual parameter count differs')
    save(out/'actual_checkpoint_metadata.json',dict(top_level_keys=list(checkpoint),config=checkpoint['config'],parameter_count=count_parameters(model),
         strict_missing_keys=list(load.missing_keys),strict_unexpected_keys=list(load.unexpected_keys),checkpoint_sha256=EXPECTED_CHECKPOINT,
         tensor_count=len(checkpoint['ema_model']),weights_only_deserialization=True))
    del checkpoint
    model.to(device).eval()
    if device.type=='cuda':torch.cuda.reset_peak_memory_stats();torch.cuda.synchronize()
    load_seconds=time.monotonic()-load_started;predictions=[];infer_started=time.monotonic()
    keys=('form_vec','ion_vec','intens','types','num_peaks','instruments')
    with torch.inference_mode():
        for start in range(0,len(frames),CONFIG['feature_batch_size']):
            chunk=frames[start:start+CONFIG['feature_batch_size']]
            batch={k:torch.from_numpy(np.stack([f[k] for f in chunk])).to(device) for k in keys}
            predicted,_=model(batch)
            values=predicted.float().cpu().numpy()
            if values.shape!=(len(chunk),4096) or not np.isfinite(values).all() or np.min(values)<0 or np.max(values)>1:raise ValueError('Actual model probabilities invalid')
            predictions.append(values)
    if device.type=='cuda':torch.cuda.synchronize()
    inference_seconds=time.monotonic()-infer_started;probabilities=np.concatenate(predictions)
    np.save(out/'spectrum_formula_probabilities.npy',probabilities,allow_pickle=False)
    generator=rdFingerprintGenerator.GetMorganGenerator(radius=2,fpSize=4096,includeChirality=False)
    score_started=time.monotonic();group_probs=[]
    for group in groups:
        if not group['feature_rows']:continue
        pooled=probabilities[group['feature_rows']].mean(0);group['pooled_row']=len(group_probs);group_probs.append(pooled)
        for record in candidate_records:
            if record['molecule_id']!=group['molecule_id'] or record['formula']!=group['formula']:continue
            bits=np.zeros(4096,dtype=np.uint8);DataStructs.ConvertToNumpyArray(generator.GetFingerprint(Chem.MolFromSmiles(record['smiles'])),bits)
            intersection=float(pooled@bits);denom=float(pooled.sum()+bits.sum()-intersection)
            value=intersection/denom if denom>0 else 0.
            if not math.isfinite(value) or not 0<=value<=1:raise ValueError('Actual soft Tanimoto invalid')
            record.update(score=value,represented=True,pool_spectra=len(group['feature_rows']))
    np.save(out/'formula_mean_probabilities.npy',np.stack(group_probs),allow_pickle=False)
    score_seconds=time.monotonic()-score_started
    table=pd.DataFrame(candidate_records);table.to_parquet(out/'candidate_scores.parquet',index=False)
    final=candidates.copy();changes=[]
    for index,row in enumerate(candidates.itertuples(index=False)):
        original=row.smiles.split(';');proposal=list(original);by_formula=defaultdict(list)
        records=[r for r in candidate_records if r['molecule_id']==row.molecule_id]
        for record in records:
            if record['represented']:by_formula[record['formula']].append(record)
        for formula,values in by_formula.items():
            slots=[v['original_rank']-1 for v in values];ordered=sorted(values,key=lambda v:(-v['score'],v['original_rank']))
            for slot,value in zip(slots,ordered):proposal[slot]=value['smiles']
        if Counter(original)!=Counter(proposal):raise ValueError('Proposal altered candidate multiset')
        if row.molecule_id in unsupported and proposal!=original:raise ValueError('Unsupported query fallback changed')
        final.loc[index,'smiles']=';'.join(proposal);changes.append(dict(molecule_id=row.molecule_id,changed=original!=proposal,top1_changed=original[0]!=proposal[0]))
    final.to_csv(out/'submission_mist_component.csv',index=False);save(out/'formula_groups.json',groups)
    checks=dict(frozen_source_verified=True,checkpoint_hash_verified=True,strict_model_load=True,actual_parameter_count=True,
                official_query_columns_only=list(query.columns)==OFFICIAL_COLUMNS,all_actual_predictions_finite=bool(np.isfinite(probabilities).all()),
                actual_predictions_4096=probabilities.shape==(len(frames),4096),actual_score_rows=len(table)==sum(len(s.split(';')) for s in candidates.smiles),
                unchanged_ids_order=final.molecule_id.tolist()==candidates.molecule_id.tolist(),
                unchanged_candidate_multisets=all(Counter(a.split(';'))==Counter(b.split(';')) for a,b in zip(candidates.smiles,final.smiles)),
                negative_spectra_excluded=all(e['reason']!='represented' for e in events if e.get('source_adduct',e.get('adduct','')).endswith('-')))
    if not all(checks.values()):raise ValueError('MIST actual smoke checks failed')
    result=dict(status='passed_actual_mist_casmi_component',checks=checks,configuration=CONFIG,seconds=time.monotonic()-started,
         feature_seconds=feature_seconds,model_load_seconds=load_seconds,inference_seconds=inference_seconds,scoring_seconds=score_seconds,
         peak_cpu_rss_mb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024.,
         peak_gpu_allocated_mb=torch.cuda.max_memory_allocated()/2**20 if device.type=='cuda' else 0.,
         peak_gpu_reserved_mb=torch.cuda.max_memory_reserved()/2**20 if device.type=='cuda' else 0.,
         device=str(device),queries=len(candidates),spectra=len(query),conditional_feature_rows=len(frames),represented_candidates=int(table.represented.sum()),
         unsupported_query_fallback=unsupported,changes=changes,checkpoint_sha256=EXPECTED_CHECKPOINT,source_commit=commit,
         adapter_sha256=sha(__file__),candidate_scores_sha256=sha(out/'candidate_scores.parquet'),output_csv_sha256=sha(out/'submission_mist_component.csv'),
         torch_version=torch.__version__,rdkit_version=rdkit.__version__,new_training=False,full_baseline_pipeline_executed=False,
         truth_labels_read=False,truth_metrics_computed=False,actual_model_executed=True,
         limitation='Candidate-formula-conditioned component on the explicitly declared candidate CSV and query inputs; not full champion inference, clean CV, or proof of recall/MRR gain.')
    save(out/'verification.json',result);return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidates',type=Path,default=WORK/'submission.csv')
    parser.add_argument('--test',type=Path)
    parser.add_argument('--output',type=Path,default=ROOT/'runs/mist_casmi_20261114')
    parser.add_argument('--device',choices=['cuda','cpu'],default='cuda')
    parser.add_argument('--prepare-only',action='store_true')
    args=parser.parse_args()
    if args.test is None:
        tests=list((WORK.parent/'input').rglob('test.parquet'))
        if len(tests)!=1:raise ValueError('Exactly one actual production test file required')
        args.test=tests[0]
    try:result=run(args);print(json.dumps(result))
    except BaseException as error:
        if args.output.exists():save(args.output/'failure.json',dict(status='failed',error_type=type(error).__name__,traceback=traceback.format_exc()))
        raise


if __name__=='__main__':main()
