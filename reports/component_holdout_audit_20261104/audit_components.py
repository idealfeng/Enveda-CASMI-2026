"""Read-only CPU identity-exposure audit of two published component checkpoints."""
from __future__ import annotations
from collections import defaultdict, Counter
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import pandas as pd
from validation.metric import assert_official_rdkit, identity, heavy_atom_composition

OUT = Path(__file__).resolve().parent
SANER = ROOT/'assets/kaggle/sanpier/casmi-spectrum-model-v1/v1/casmi_spectrum_model_v1'
FOLD = ROOT/'assets/kaggle/dmitriigluzdov/casmi26-fold-safe-fpnet/v5'
STRUCTS = ROOT/'assets/kaggle/ahmedberatozer/casmi26-v2-pool/v1/train_structs.parquet'

def sha(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()

def file_record(path):
    return {'path':str(path.relative_to(ROOT)), 'bytes':path.stat().st_size, 'sha256':sha(path)}

def main():
    started=time.monotonic()
    assert_official_rdkit()
    mol=pd.read_parquet(SANER/'molecules.parquet')
    spec=pd.read_parquet(SANER/'spectrum_split_manifest.parquet')
    split=pd.read_parquet(FOLD/'split.parquet')
    structs=pd.read_parquet(STRUCTS)
    assert structs.sid.is_unique and not mol.key.duplicated().any()
    join=split.merge(structs[['sid','inchikey14','key']],on='sid',suffixes=('_split','_source'),validate='one_to_one')
    assert (join.inchikey14_split==join.inchikey14_source).all() and (join.key_split==join.key_source).all()
    assert set(spec.key)==set(mol.key)
    assert (spec.split==spec.key.map(mol.set_index('key').split)).all()
    candidate=mol[mol.split.eq('validation') & mol.key.isin(split.key)].copy()
    declared_intersection_count=len(candidate)
    # Data.val is in molecules.parquet row order, and candidate_sets uses val[:1000].
    selection_keys=set(mol.loc[mol.split.eq('validation'),'key'].iloc[:1000])
    selection_intersection_count=int(candidate.key.isin(selection_keys).sum())
    candidate=candidate[~candidate.key.isin(selection_keys)].copy()
    candidate['selection_hash']=candidate.key.map(lambda key:hashlib.sha256(('20261104-component-audit:'+key).encode()).hexdigest())
    selected=candidate.sort_values('selection_hash').head(64)
    # Include every declared NP intersection, irrespective of the sample's rank.
    np_keys=set(split.loc[split.fold.eq('np'),'key'])
    selected=pd.concat([selected,candidate[candidate.key.isin(np_keys)]]).drop_duplicates('key')
    targets={identity(row.smiles):{'identity':identity(row.smiles),'normalized_smiles':row.smiles,'declared_key':row.key,
                                 'selection':'frozen_hash64_plus_all_declared_np_intersection'} for row in selected.itertuples()}
    assert None not in targets
    pilot=pd.read_csv(ROOT/'runs/validation_pilot_20261104/truth.csv')
    for row in pilot.itertuples():
        targets.setdefault(identity(row.smiles), {'identity':identity(row.smiles),'normalized_smiles':row.smiles,'selection':'existing_diagnostic_pilot'})
    target_comps={heavy_atom_composition(item['normalized_smiles']) for item in targets.values()}
    comp_cache={}
    canonical_cache={}
    known=ROOT/'runs/validation_pilot_20261104/structure_identity_audit.parquet'
    if known.exists():
        cached=pd.read_parquet(known)
        for row in cached.itertuples():
            comp_cache[row.smiles]=tuple(tuple(x) for x in json.loads(row.heavy_composition)) if row.heavy_composition else None
            if row.canonical_checked and row.official_identity:canonical_cache[row.smiles]=row.official_identity
    matches=defaultdict(list)
    checked=Counter()
    for source, frame in [('saner',mol),('fold0',structs)]:
        for number,row in enumerate(frame.itertuples()):
            smiles=row.smiles
            if smiles not in comp_cache:comp_cache[smiles]=heavy_atom_composition(smiles)
            if comp_cache[smiles] in target_comps:
                checked[source]+=1
                if smiles not in canonical_cache:canonical_cache[smiles]=identity(smiles)
                key=canonical_cache[smiles]
                if key in targets:
                    detail={'source':source,'declared_key':row.key,'smiles':smiles}
                    if source=='saner':detail['split']=row.split
                    else:detail.update(sid=int(row.sid),fold='excluded' if row.sid in set_excluded else 'train')
                    matches[key].append(detail)
            if number%50000==0:print(f'{source} rows={number} heavy_cache={len(comp_cache)} canonical_checked={checked[source]}',flush=True)
    records=[]
    safe=[]
    for key,item in targets.items():
        entries=matches[key]
        saner_train=[x for x in entries if x['source']=='saner' and x['split']=='train']
        saner_val=[x for x in entries if x['source']=='saner' and x['split']=='validation']
        fold_train=[x for x in entries if x['source']=='fold0' and x['fold']=='train']
        fold_out=[x for x in entries if x['source']=='fold0' and x['fold']=='excluded']
        selection_used=any(x['declared_key'] in selection_keys for x in saner_val)
        eligible=bool(saner_val and fold_out and not saner_train and not fold_train and not selection_used)
        row={**item,'saner_final':'declared_seen' if saner_train or saner_val else 'unknown',
             'saner_best_validation':'declared_seen' if saner_train else ('training_identity_unseen_checkpoint_selection_seen' if selection_used else 'training_identity_unseen_selection_not_used_declared') if saner_val else 'unknown',
             'saner_checkpoint_selection_used':selection_used,
             'fold0':'declared_seen' if fold_train else 'training_identity_unseen_declared' if fold_out else 'unknown',
             'component_intersection_eligible':eligible,'matched_rows':entries}
        records.append(row)
        if eligible and item['selection']!='existing_diagnostic_pilot':safe.append({k:v for k,v in row.items() if k!='matched_rows'})
    (OUT/'identity_scan_result.json').write_text(json.dumps({'records':records,'eligible':safe,'checked':dict(checked)},indent=2)+'\n',encoding='utf-8')
    sums=json.loads((SANER/'sha256.json').read_text())
    saner_hashes={name:{'present':(SANER/name).is_file(), 'match':sha(SANER/name)==value if (SANER/name).is_file() else None}
                  for name,value in sums.items()}
    manifests={}
    for name in ['MANIFEST_20261019.json','MANIFEST_FIVEFOLD.json']:
        data=json.loads((FOLD/name).read_text());files=data.get('files',{})
        if isinstance(files,list):files={entry.get('file',entry.get('path',entry.get('name'))):entry for entry in files}
        manifests[name]={p:{'match':sha(FOLD/p)==(v['sha256'] if isinstance(v,dict) else v)} for p,v in files.items()
                         if (FOLD/p).is_file() and isinstance(v,(dict,str)) and (not isinstance(v,dict) or 'sha256' in v)}
    import torch
    checkpoint_metadata={}
    for name in ['final_model.pt','best_validation_model.pt']:
        checkpoint=torch.load(SANER/name,map_location='cpu',weights_only=True)
        checkpoint_metadata[name]={key:value for key,value in checkpoint.items() if key!='state_dict'}
        del checkpoint
    payload={'rdkit':assert_official_rdkit(),'status':'completed_component_exposure_audit','elapsed_seconds':time.monotonic()-started,
             'inputs':[file_record(path) for path in [SANER/'molecules.parquet',SANER/'spectrum_split_manifest.parquet',SANER/'train.py',SANER/'prepare.py',SANER/'features.py',SANER/'training_result.json',SANER/'best_validation_model.pt',SANER/'final_model.pt',FOLD/'split.parquet',FOLD/'MODEL_INPUTS.json',FOLD/'fpnet_fold0.pt',STRUCTS]],
             'source_assets':{'saner':{'ref':'sanpier/casmi-spectrum-model-v1','version':1,'license_card':'Apache-2.0 for author artifacts; third-party and competition-data terms retained'},'fold0':{'ref':'dmitriigluzdov/casmi26-fold-safe-fpnet','version':5,'license_card':'Checkpoint and competition-derived data: non-commercial with attribution; training/audit scripts Apache-2.0'}},
             'published_training_result':json.loads((SANER/'training_result.json').read_text()),'checkpoint_metadata':checkpoint_metadata,
             'split_counts':{'saner_molecules':len(mol),'saner_train':int(mol.split.eq('train').sum()),'saner_validation':int(mol.split.eq('validation').sum()),'saner_spectra':len(spec),'saner_spectra_split':spec.split.value_counts().to_dict(),'fold0_excluded_rows':len(split),'fold0_exclusion_reasons':split.fold.value_counts().to_dict(),'declared_key_intersection_count':declared_intersection_count,'saner_checkpoint_selection_identities':len(selection_keys),'declared_intersection_selection_used':selection_intersection_count,'declared_intersection_selection_not_used':len(candidate),'selected_intersection_queries':len(selected),'official_identity_audited_targets':len(targets),'verified_eligible_selected_queries':len(safe)},
             'saner_published_hash_checks':saner_hashes,'fold0_manifest_checks':manifests,
             'official_identity_search':{'method':'All Saner molecule and all fold0 structure rows scanned; heavy composition recomputed/cached from actual SMILES, then all composition-compatible rows canonicalized with official stereo-before-tautomer identity. No full-formula gate.','composition_compatible_rows_canonicalized':dict(checked),'scope':'Only audited targets; declared intersection count alone is not equivalence-audited.'},
             'records':records,'limitations':['Published producer declarations and checkpoint metadata support training scope, but do not reconstruct historical minibatches.','Saner best checkpoint was selected using up to the first 1000 validation identities: training-unseen does not mean untouched model-selection holdout.','Published prepare.py lacks normalized_smiles alias despite data_audit naming that input; exact producer revision/provenance remains unresolved.','An eligible pair of neural components does not certify FPNet/ICE/GL/GBDT/whole Flex stack as unseen.','Full candidate set and split must be frozen before component scoring. Current pilot and previous public panels are diagnostic development evidence, not pristine final holdout.']}
    (ROOT/'reports/pretrained_exposure_audit.json').write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')
    pd.DataFrame(safe).to_csv(OUT/'component_intersection_queries.csv',index=False)
    print(json.dumps(payload['split_counts']),flush=True)

if __name__=='__main__':
    # Used by the row scanner; IDs are stable and independently checked against the pool table.
    set_excluded=set(pd.read_parquet(FOLD/'split.parquet').sid.astype(int))
    main()
