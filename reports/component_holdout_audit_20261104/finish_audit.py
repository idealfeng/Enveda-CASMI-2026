"""Check nonrepresentative train SMILES variants and write the human-readable audit."""
from pathlib import Path
import json
import sys
from collections import Counter
import pandas as pd
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from validation.metric import identity,heavy_atom_composition

def main():
    out=Path(__file__).resolve().parent
    path=ROOT/'reports/pretrained_exposure_audit.json'
    audit=json.loads(path.read_text())
    # Restart from the completed raw identity scan so repeated finishing does not
    # erase the pre-selection count or append the same source variants twice.
    audit['records']=json.loads((out/'identity_scan_result.json').read_text())['records']
    saner=ROOT/'assets/kaggle/sanpier/casmi-spectrum-model-v1/v1/casmi_spectrum_model_v1'
    mol=pd.read_parquet(saner/'molecules.parquet')
    with np.load(saner/'validation_candidates.npz',allow_pickle=False) as archive:
        indices={int(value) for name in archive.files for value in archive[name].tolist()}
        query_indices={int(name) for name in archive.files}
        assert len(query_indices)==1000
        assert query_indices==set(np.flatnonzero(mol.split.eq('validation').to_numpy())[:1000])
        assert all(mol.split.iloc[index]=='validation' for index in query_indices)
        assert all(0 <= index < len(mol) for index in indices)
        candidate_keys=set(mol.key.iloc[sorted(indices)])
    import hashlib
    npz_sha=hashlib.sha256((saner/'validation_candidates.npz').read_bytes()).hexdigest()
    assert npz_sha==json.loads((saner/'sha256.json').read_text())['validation_candidates.npz']
    structs=pd.read_parquet(ROOT/'assets/kaggle/ahmedberatozer/casmi26-v2-pool/v1/train_structs.parquet')
    variants=pd.read_parquet(ROOT/'runs/validation_pilot_20261104/structure_identity_audit.parquet')
    representatives=set(zip(structs.inchikey14,structs.smiles))
    sid_by_raw=dict(zip(structs.inchikey14,structs.sid))
    excluded=set(pd.read_parquet(ROOT/'assets/kaggle/dmitriigluzdov/casmi26-fold-safe-fpnet/v5/split.parquet').sid)
    target_by_id={row['identity']:row for row in audit['records']}
    compositions={heavy_atom_composition(row['normalized_smiles']) for row in audit['records']}
    extra_checked=0
    equivalent=[]
    unresolved=[]
    for row in variants.itertuples():
        if (row.raw_inchikey14,row.smiles) in representatives:continue
        if heavy_atom_composition(row.smiles) not in compositions:continue
        extra_checked+=1
        key=identity(row.smiles)
        if key not in target_by_id:continue
        sid=sid_by_raw.get(row.raw_inchikey14)
        if sid is None:
            unresolved.append({'identity':key,'raw_key':row.raw_inchikey14,'smiles':row.smiles})
            target_by_id[key]['component_intersection_eligible']=False
            continue
        record={'source':'fold0_original_smiles_variant','declared_key':row.raw_inchikey14,'sid':int(sid),'smiles':row.smiles,'fold':'excluded' if sid in excluded else 'train'}
        equivalent.append({'identity':key,**record})
        target_by_id[key]['matched_rows'].append(record)
        if sid not in excluded:
            target_by_id[key]['fold0']='declared_seen'
            target_by_id[key]['component_intersection_eligible']=False
    audit['nonrepresentative_fold0_variants']={'catalog_rows':len(variants),'composition_compatible_variants_checked':extra_checked,'equivalent_rows':equivalent,'unresolved_rows':unresolved,'scope':'All original raw-key/SMILES pairs outside train_structs representatives, with fold assignments resolved by raw key/sid.'}
    training_unseen=[row for row in audit['records'] if row['component_intersection_eligible'] and row['selection']!='existing_diagnostic_pilot']
    pd.DataFrame([{k:v for k,v in row.items() if k!='matched_rows'} for row in training_unseen]).to_csv(out/'component_training_unseen_queries.csv',index=False)
    candidate_touched=0
    for row in audit['records']:
        touched=any(item['source']=='saner' and item['declared_key'] in candidate_keys for item in row['matched_rows'])
        row['saner_checkpoint_selection_candidate_used']=touched
        if touched:
            if row['component_intersection_eligible']:candidate_touched+=1
            row['component_intersection_eligible']=False
            if row['saner_best_validation'].startswith('training_identity_unseen'):
                row['saner_best_validation']='training_identity_unseen_checkpoint_selection_candidate_seen'
    safe=[{k:v for k,v in row.items() if k!='matched_rows'} for row in audit['records'] if row['component_intersection_eligible'] and row['selection']!='existing_diagnostic_pilot']
    audit['split_counts']['verified_eligible_selected_queries']=len(safe)
    audit['split_counts']['verified_training_unseen_before_candidate_selection_exclusion']=len(training_unseen)
    audit['split_counts']['verified_training_unseen_touched_as_selection_candidate']=candidate_touched
    audit['checkpoint_selection_candidates']={'artifact':'assets/kaggle/sanpier/casmi-spectrum-model-v1/v1/casmi_spectrum_model_v1/validation_candidates.npz','sha256':npz_sha,'matches_published_sha256':True,'query_indices':len(query_indices),'unique_candidate_indices':len(indices),'query_indices_match_first_1000_validation_rows':True,'scope':'All evaluated candidate identities including decoys, rather than query identities alone.'}
    audit['audit_completed_local_date']='2026-11-05'
    audit['candidate_query_manifest']='reports/component_holdout_audit_20261104/component_intersection_queries.csv'
    path.write_text(json.dumps(audit,indent=2)+'\n')
    pd.DataFrame(safe).to_csv(out/'component_intersection_queries.csv',index=False)
    counts=audit['split_counts']
    bad_saner=[name for name,record in audit['saner_published_hash_checks'].items() if record['match'] is False]
    mismatches={name:[key for key,record in checks.items() if not record['match']] for name,checks in audit['fold0_manifest_checks'].items()}
    pilot_truth=pd.read_csv(ROOT/'runs/validation_pilot_20261104/truth.csv')
    pilot_ids={identity(smiles) for smiles in pilot_truth.smiles}
    pilot=[row for row in audit['records'] if row['identity'] in pilot_ids]
    pilot_summary={field:dict(Counter(row[field] for row in pilot)) for field in ['saner_final','saner_best_validation','fold0']}
    audit['existing_pilot_exposure_summary']=pilot_summary
    path.write_text(json.dumps(audit,indent=2)+'\n')
    text=f'''# Pretrained component exposure audit

Completed 2026-11-05, Asia/Shanghai. Evidence and query manifests remain under D:/Paper/casmi. No model inference, GPU use, training or large spectra/cache download was performed by this audit.

Saner `final_model.pt` is **declared_seen** for the published processed training identities, including former validation identities. `training_result.json` explicitly records a successful full-data refit. The checkpoint's stage metadata is `{audit['checkpoint_metadata']['final_model.pt']}`. It cannot establish unseen validation performance on those identities.

Saner `best_validation_model.pt` has stage metadata `{audit['checkpoint_metadata']['best_validation_model.pt']}`. The published training source restricts positives, hard negatives and auxiliary statistics to the training split. However, checkpoint selection evaluates the first 1,000 validation identities in `molecules.parquet` row order every epoch. We explicitly remove those identities before selecting the component experiment. The remaining selection exclusion is source-declared and content-audited, not reconstructed historical minibatches.

## Available component experiment

- Exact assets: [Saner V1](https://www.kaggle.com/datasets/sanpier/casmi-spectrum-model-v1/versions/1) and [Fold-safe FPNet V5](https://www.kaggle.com/datasets/dmitriigluzdov/casmi26-fold-safe-fpnet/versions/5), using `fpnet_fold0.pt` and `best_validation_model.pt`.
- Saner split: {counts['saner_train']:,} train identities and {counts['saner_validation']:,} validation identities; {counts['saner_spectra']:,} processed spectra. All published spectrum-manifest split labels match the molecule table.
- Fold0 exclusions: {counts['fold0_excluded_rows']:,} structure rows, split reasons {counts['fold0_exclusion_reasons']}. Every published split sid/raw key/key matches the pinned 275,810-row structure table.
- Declared-key intersection: {counts['declared_key_intersection_count']:,}. Of these, {counts['declared_intersection_selection_used']:,} are in Saner's explicit checkpoint-selection set, leaving {counts['declared_intersection_selection_not_used']:,} proposed candidates. This count is only a declared-key count, not proof for all identities.
- A frozen hash sample plus NP intersections was independently checked by official RDKit 2026.03.3 identity. The checked training-unseen intersection initially contains {len(training_unseen)} identities. We also exclude every identity scored as query OR decoy during checkpoint selection, using the actual SHA-bound `validation_candidates.npz` ({len(query_indices):,} query lists; {len(indices):,} unique molecule indices). **{len(safe)} selected identities remain eligible** after all checks. Query manifest: `reports/component_holdout_audit_20261104/component_intersection_queries.csv`. This is a component-level exclusion audit, not proof of an untouched independent final test.
- Fix candidate identities and ordering protocol before scoring. Compare fold0 alone with an added fixed-weight Saner best-validation score; retain an unchanged baseline, paired molecular uncertainty, and source/panel strata. No validation result is yet claimed for this proposed experiment.

## Integrity and limits

Saner hashes matched for all locally present files listed by its published `sha256.json`; mismatches: {bad_saner}. Best-validation SHA-256: `969d13443fcf168eae1e00e56a8e0ae87dcb16f337cb6dbac959e7cd218f089c`. Fold0 checkpoint matches `MODEL_INPUTS.json`; exact hashes are recorded in JSON. Historical fold manifests contain stale entries, mismatches among locally available files: {json.dumps(mismatches)}. A stale manifest is not used to silently certify those individual files.

The Saner V1 `prepare.py` does not accept the `normalized_smiles` column named by its published data audit. Its dataset card acknowledges a later schema-compatibility repair and distinguishes that repair from exact checkpoint reproduction. Therefore the exact producer revision remains unresolved even though checkpoint/split artifacts and declared training scopes are auditable.

This is a **component-level, training-identity-exclusion experiment**. It does not certify the complete Flex/V43 stack, other FPNet checkpoints, ICEBERG, GLACIER or rankers as unseen, and does not certify unrecorded architecture/hyperparameter decisions as untouched by validation. The current 48-query pilot remains diagnostic. Same-formula filtering is never used as an identity gate: protonation/charge variants are checked by heavy composition and official canonical identity.

## Licence sources

Saner V1's author dataset card states Apache-2.0 for original checkpoints/scripts, retaining third-party and competition-data terms. Fold-safe V5's dataset card and `MODEL_INPUTS.json` state non-commercial competition-data terms with attribution for checkpoint/derived data; author training/audit scripts are Apache-2.0. This audit records the source declarations and does not establish competition-prize eligibility for the full stack.
'''
    (ROOT/'reports/pretrained_exposure_audit.md').write_text(text,encoding='utf-8')
    print(json.dumps({'counts':counts,'pilot':pilot_summary,'extra_variants_checked':extra_checked,'eligible_queries':len(safe),'saner_hash_mismatches':bad_saner,'fold_manifest_mismatches':mismatches},indent=2))

if __name__=='__main__':main()
