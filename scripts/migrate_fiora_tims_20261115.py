"""Expand frozen FIORA-OS instrument covariates with an explicit timsTOF slot.

No training, spectrum labels, hidden input, old-source edit or environment write.
The two static-tail MLP input matrices are mapped by native encoder feature
names; all other tensors remain byte-identical. Native HCD forward parity is
checked before the independent migrated artifact is released.
"""
from pathlib import Path
import argparse
import copy
import gc
import hashlib
import importlib.metadata
import json
import os
import resource
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[1]
ASSET=ROOT/'assets/research/fiora_os_20261115'
SOURCE=ASSET/'source_checkout'
TARGET=ASSET/'dependencies-linux'
MODEL=SOURCE/'fiora/resources/models/fiora_OS_v1.0.0'
PARENT_SHA='83221e187991f116a8aed1bf272dd656cf31721a177dcbb0239f414c8df31a0e'
COMMIT='e19ef82c9a6cb9dbac92bce23e914008f1aeb44e'
IONS=['[M+H]+','[M-H]-','[M]+','[M]-']
CHANGED_KEYS=('edge_module.dense_layers.0.weight','precursor_module.dense_layers.0.weight')

def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def save(path,value):
    Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def labels(encoder):
    """Read exact column assignments from the frozen native encoder instance."""
    names={}
    for feature,mapping in encoder.one_hot_mapper.items():
        if isinstance(mapping,int): names[mapping]=feature
        else:
            for value,index in mapping.items(): names[index]=feature+'='+value
            if feature in encoder.reduced_categorical_features:
                names[max(mapping.values())+1]=feature+'=OTHER'
    if sorted(names)!=list(range(encoder.encoding_dim)):
        raise ValueError('Native encoder has uncovered/ambiguous columns')
    return [names[i] for i in range(encoder.encoding_dim)]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'runs/fiora_tims_model_20261115')
    args=parser.parse_args();out=args.output.resolve()
    if not out.is_relative_to(ROOT/'runs'):raise ValueError('New D workspace run directory required')
    out.mkdir(parents=True,exist_ok=False)
    started=time.perf_counter()
    report=dict(status='RUNNING',device='cpu',training_performed=False,optimizer_steps=0,
                environment_modified=False,source_commit=COMMIT,dependency_target=str(TARGET),
                original_sources_or_weights_modified=False,hidden_data_used=False,labels_used=False,
                source_script_sha256=sha(__file__),parity_absolute_tolerance=1e-6)
    save(out/'executed_configuration.json',dict(seed=20261115,device='cpu',threads=2,instruments=['HCD','timsTOF'],precursor_modes=IONS,new_instrument_initialization='zero',static_dimensions=[18,19],rt_static_dimensions=[17,18],training_steps=0,parity_atol=1e-6))
    (out/'executed_migration_script.py').write_bytes(Path(__file__).read_bytes())
    try:
        sys.path[:0]=[str(SOURCE),str(TARGET)]
        os.environ['OMP_NUM_THREADS']='2';os.environ['OPENBLAS_NUM_THREADS']='2';os.environ['MKL_NUM_THREADS']='2'
        import numpy as np
        import pandas as pd
        import torch
        import torch_geometric
        from fiora.GNN.FioraModel import FioraModel
        from fiora.GNN.CovariateFeatureEncoder import CovariateFeatureEncoder
        from fiora.cli.predict import build_metabolites
        from fiora.MS.SimulationFramework import SimulationFramework
        torch.set_num_threads(2);torch.manual_seed(20261115)
        report['import_seconds']=time.perf_counter()-started
        print(json.dumps(dict(stage='imported',seconds=report['import_seconds'])),flush=True)
        state_path=Path(str(MODEL)+'_state.pt');params_path=Path(str(MODEL)+'_params.json')
        if sha(state_path)!=PARENT_SHA:raise ValueError('Frozen parent state SHA differs')
        parent=json.loads(params_path.read_text())
        if parent['setup_features_categorical_set']!={'instrument':['HCD'],'precursor_mode':IONS}:
            raise ValueError('Original instrument/ion vocabulary differs')
        if (parent['static_feature_dimension'],parent['static_rt_feature_dimension'])!=(18,17):
            raise ValueError('Unexpected parent static dimensions')
        if parent['prepare_additional_layers']:raise ValueError('Additional RT/CCS heads need separate mapping')
        migrated=copy.deepcopy(parent)
        migrated['setup_features_categorical_set']['instrument']=['HCD','timsTOF']
        migrated['static_feature_dimension']=19;migrated['static_rt_feature_dimension']=18
        # Metadata describes an untrained migration, not a newly fitted model.
        migrated['instrument_migration']=dict(parent_state_sha256=PARENT_SHA,new_instrument='timsTOF',new_instrument_initialization='zero',trained_steps=0)
        old_encoder=CovariateFeatureEncoder(parent['setup_features'],parent['setup_features_categorical_set'])
        new_encoder=CovariateFeatureEncoder(migrated['setup_features'],migrated['setup_features_categorical_set'])
        old_names,new_names=labels(old_encoder),labels(new_encoder)
        if len(old_names)!=18 or len(new_names)!=19:raise ValueError('Native setup encoder dimension mismatch')
        if old_names[6:8]!=['instrument=HCD','instrument=OTHER'] or new_names[6:9]!=['instrument=HCD','instrument=timsTOF','instrument=OTHER']:
            raise ValueError('Unexpected native instrument column order')
        mapping={i:new_names.index(name) for i,name in enumerate(old_names)}
        rt_old=CovariateFeatureEncoder(parent['rt_features'],parent['setup_features_categorical_set'])
        rt_new=CovariateFeatureEncoder(migrated['rt_features'],migrated['setup_features_categorical_set'])
        if (rt_old.encoding_dim,rt_new.encoding_dim)!=(17,18):raise ValueError('RT metadata encoder dimension mismatch')
        state=torch.load(state_path,map_location='cpu',weights_only=True)
        if len(state)!=67:raise ValueError('Expected exactly 67 parent tensor keys')
        updated={};tensor_audit=[]
        stage=time.perf_counter()
        for name,tensor in state.items():
            if name in CHANGED_KEYS:
                expected=(500,13538) if name.startswith('edge_module') else (500,3318)
                if tuple(tensor.shape)!=expected:raise ValueError('Actual parent matrix shape differs: '+name)
                prefix=tensor.shape[1]-len(old_names)
                value=torch.zeros((tensor.shape[0],tensor.shape[1]+1),dtype=tensor.dtype,device='cpu')
                value[:,:prefix]=tensor[:,:prefix]
                for old_index,new_index in mapping.items():value[:,prefix+new_index]=tensor[:,prefix+old_index]
                unchanged_prefix=torch.equal(value[:,:prefix],tensor[:,:prefix])
                preserved_columns=all(torch.equal(value[:,prefix+new_index],tensor[:,prefix+old_index]) for old_index,new_index in mapping.items())
                tims_zero=bool(torch.count_nonzero(value[:,prefix+7]).item()==0)
                if not (unchanged_prefix and preserved_columns and tims_zero):raise ValueError('Matrix mapping changed an original column')
            else:
                value=tensor;unchanged_prefix=True;preserved_columns=True;tims_zero=None
            updated[name]=value
            tensor_audit.append(dict(key=name,parent_shape=list(tensor.shape),migrated_shape=list(value.shape),parent_tensor_bytes_sha256=hashlib.sha256(tensor.detach().cpu().contiguous().numpy().tobytes()).hexdigest(),migrated_tensor_bytes_sha256=hashlib.sha256(value.detach().cpu().contiguous().numpy().tobytes()).hexdigest(),byte_identical_except_declared_matrices=bool(torch.equal(value,tensor)) if name not in CHANGED_KEYS else None,non_static_prefix_preserved=unchanged_prefix,all_old_static_columns_preserved=preserved_columns,tims_column_zero=tims_zero))
        report['migration_seconds']=time.perf_counter()-stage
        old_count=sum(t.numel() for t in state.values());new_count=sum(t.numel() for t in updated.values())
        if old_count!=13447861 or new_count-old_count!=1000:raise ValueError('Parameter count delta differs')
        model=FioraModel(copy.deepcopy(parent));loaded=model.load_state_dict(state,strict=True);model.eval()
        if loaded.missing_keys or loaded.unexpected_keys:raise ValueError('Parent strict load failed')
        records=[]
        for stem,smi in [('caffeic_acid','O=C(O)/C=C/c1ccc(O)c(O)c1'),('24_dihydroxycinnamic_acid','O=C(O)/C=C/c1ccc(O)cc1O')]:
            for ce in (35.,65.):
                records.append(dict(Name=stem+'_ce'+str(int(ce)),SMILES=smi,Precursor_type='[M+H]+',CE=ce,Instrument_type='HCD'))
        pd.DataFrame(records).to_csv(out/'hcd_parity_inputs.csv',index=False)
        stage=time.perf_counter();old_frame,bad=build_metabolites(pd.DataFrame(records),parent)
        if len(bad) or len(old_frame)!=4:raise ValueError('Native old HCD graph construction failed')
        report['parent_graph_seconds']=time.perf_counter()-stage
        framework=SimulationFramework(model,dev='cpu');old_outputs={};forward_times=[]
        with torch.inference_mode():
            for _,row in old_frame.iterrows():
                tick=time.perf_counter();pred=framework.predict_metabolite_property(row['Metabolite'],model,as_batch=True)
                raw=pred['fragment_probs'].detach().cpu().numpy().copy()
                if not np.isfinite(raw).all():raise ValueError('Nonfinite parent output')
                old_outputs[row['Name']]=raw;forward_times.append(time.perf_counter()-tick)
        # Release the parent model before constructing the migrated one.
        del model,framework,old_frame,state;gc.collect()
        model=FioraModel(copy.deepcopy(migrated));loaded=model.load_state_dict(updated,strict=True);model.eval()
        if loaded.missing_keys or loaded.unexpected_keys:raise ValueError('Migrated strict load failed')
        stage=time.perf_counter();new_frame,bad=build_metabolites(pd.DataFrame(records),migrated)
        if len(bad) or len(new_frame)!=4:raise ValueError('Native migrated HCD graph construction failed')
        report['migrated_graph_seconds']=time.perf_counter()-stage
        framework=SimulationFramework(model,dev='cpu');parity=[]
        with torch.inference_mode():
            for _,row in new_frame.iterrows():
                tick=time.perf_counter();pred=framework.predict_metabolite_property(row['Metabolite'],model,as_batch=True)
                raw=pred['fragment_probs'].detach().cpu().numpy().copy();delta=float(np.max(np.abs(raw-old_outputs[row['Name']])))
                if not np.isfinite(raw).all() or delta>1e-6:raise ValueError('HCD forward parity exceeded tolerance')
                parity.append(dict(name=row['Name'],shape=list(raw.shape),max_abs_delta=delta,seconds=time.perf_counter()-tick))
                np.save(out/(row['Name']+'_parent.npy'),old_outputs[row['Name']],allow_pickle=False)
                np.save(out/(row['Name']+'_migrated.npy'),raw,allow_pickle=False)
        mol=new_frame.iloc[0]['Metabolite']
        metadata=dict(mol.metadata)
        encoded={}
        for instrument in ('HCD','timsTOF','unseen_instrument_control'):
            metadata['instrument']=instrument
            encoded[instrument]=new_encoder.encode(1,metadata,G=mol.Graph)
        expected_slots={'HCD':6,'timsTOF':7,'unseen_instrument_control':8}
        for instrument,slot in expected_slots.items():
            actual=encoded[instrument][0,6:9]
            expected=torch.zeros(3);expected[slot-6]=1
            if not torch.equal(actual,expected):raise ValueError('Instrument failed distinct native encoding')
        native_old=old_encoder.encode(1,dict(mol.metadata,instrument='HCD'),G=mol.Graph)
        if any(not torch.equal(native_old[:,i],encoded['HCD'][:,j]) for i,j in mapping.items()):
            raise ValueError('Original HCD encoded columns changed')
        encoding=dict(columns=new_names,vectors={k:v.tolist() for k,v in encoded.items()},distinct_tims_HCD_OTHER=True,new_tims_column=7,old_HCD_column_preserved=6,OTHER_column=8)
        save(out/'instrument_encoding_contract.json',encoding)
        save(out/'tensor_migration_audit.json',dict(state_keys=67,changed_keys=list(CHANGED_KEYS),old_columns=old_names,new_columns=new_names,old_to_new_columns=mapping,tensors=tensor_audit))
        migrated_state=out/'fiora_OS_tims_migrated_state.pt';migrated_params=out/'fiora_OS_tims_migrated_params.json'
        torch.save(updated,migrated_state);save(migrated_params,migrated)
        saved=torch.load(migrated_state,map_location='cpu',weights_only=True)
        if set(saved)!=set(updated) or not all(torch.equal(saved[k],v) for k,v in updated.items()):raise ValueError('Saved state tensor roundtrip mismatch')
        if sha(state_path)!=PARENT_SHA:raise ValueError('Parent file modified unexpectedly')
        sources=['fiora/GNN/CovariateFeatureEncoder.py','fiora/GNN/FioraModel.py','fiora/GNN/EdgePropertyPredictor.py','fiora/GNN/GraphPropertyPredictor.py','fiora/cli/predict.py','fiora/MOL/Metabolite.py','fiora/MS/SimulationFramework.py']
        report.update(status='MIGRATED_STRICT_HCD_PARITY_PASSED',parent_state_sha256=PARENT_SHA,parent_params_sha256=sha(params_path),state_keys=67,parent_parameters=old_count,migrated_parameters=new_count,parameter_delta=new_count-old_count,strict_missing_keys=[],strict_unexpected_keys=[],changed_keys=list(CHANGED_KEYS),all_65_other_tensors_byte_identical=all(row['byte_identical_except_declared_matrices'] for row in tensor_audit if row['key'] not in CHANGED_KEYS),HCD_parity=parity,HCD_max_abs_delta=max(row['max_abs_delta'] for row in parity),parent_forward_seconds=forward_times,instrument_encoding=dict(HCD=6,timsTOF=7,OTHER=8,distinct=True),static_feature_dimension=19,static_rt_feature_dimension=18,migrated_state_sha256=sha(migrated_state),migrated_params_sha256=sha(migrated_params),source_pins={s:sha(SOURCE/s) for s in sources},dependency_versions={k:importlib.metadata.version(k) for k in ['torch','torch-geometric','treelib','dill']},parent_condition_semantics_retained=True,native_instrument_path_used=True,scope='Architecture/weight migration and native HCD parity only; zero timsTOF training and no timsTOF accuracy or ranking claim.')
    except BaseException as error:
        report.update(status='FAILED',error_type=type(error).__name__,error=str(error),traceback=traceback.format_exc())
        save(out/'failure.json',report)
    report.update(total_seconds=time.perf_counter()-started,peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
    save(out/'migration_receipt.json',report)
    report_path=ROOT/'reports/new_paradigm_20261115/fiora_tims_migration.json'
    if not report_path.exists():save(report_path,report)
    print(json.dumps({k:v for k,v in report.items() if k not in ['traceback','source_pins','HCD_parity']},indent=2),flush=True)
    if report['status']!='MIGRATED_STRICT_HCD_PARITY_PASSED':raise SystemExit(1)

if __name__=='__main__':main()
