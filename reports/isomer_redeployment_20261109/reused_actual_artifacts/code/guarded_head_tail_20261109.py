"""Configurable late same-formula ranking, with pinned scorer and exact prefix."""
from __future__ import annotations
from collections import Counter, defaultdict
from functools import lru_cache
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys

import pandas as pd

V2_SHA='c08d2101154d057890de088be63834eb622468892a3b842512fdc5a65e02ff46'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def write(path,value):Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


@lru_cache(maxsize=100000)
def describe(smiles):
    import rdkit
    from rdkit import Chem,RDLogger
    from rdkit.Chem import rdMolDescriptors
    from rdkit.Chem.MolStandardize import rdMolStandardize
    if rdkit.__version__!='2026.03.3':raise RuntimeError('Official RDKit required')
    RDLogger.DisableLog('rdApp.*')
    try:
        mol=Chem.MolFromSmiles(smiles)
        if mol is None:return None,None
        Chem.RemoveStereochemistry(mol)
        mol=rdMolStandardize.TautomerEnumerator().Canonicalize(mol)
        key=Chem.MolToInchiKey(mol)
        return (key[:14],rdMolDescriptors.CalcMolFormula(mol)) if key else (None,None)
    except (ValueError,TypeError,RuntimeError):return None,None


def reorder(control,scores,skipped=None,protected_prefix=7):
    """Scores are precomputed. Original prefix, molecules and formula slots stay fixed."""
    if type(protected_prefix) is not int or not 1 <= protected_prefix <= 24:raise ValueError('Invalid protected prefix')
    skipped={} if skipped is None else skipped
    result=[];details=[]
    if scores.duplicated(['molecule_id','smiles']).any():raise ValueError('Duplicate scored keys')
    bymid={str(mid):g for mid,g in scores.groupby('molecule_id',sort=False)}
    for mid,raw in control[['molecule_id','smiles']].itertuples(index=False,name=None):
        mid=str(mid);before=raw.split(';');after=list(before);reason=skipped.get(mid)
        descriptions=[describe(s) for s in before]
        keys=[x[0] for x in descriptions]
        if reason is None and (None in keys or len(keys)!=len(set(keys))):reason='invalid_or_duplicate_identity'
        group=bymid.get(mid)
        if reason is None:
            if group is None or set(group.smiles)!=set(before):raise ValueError('Scored candidates differ from final control')
            valid=group.neural_ok.astype(bool) & group.neural_score.map(lambda x:math.isfinite(float(x)))
            if not bool(valid.all()):reason='no_usable_head_score'
        changed_groups=0
        if reason is None:
            values=dict(zip(group.smiles,group.neural_score));slots=defaultdict(list)
            for i in range(protected_prefix,len(before)):slots[descriptions[i][1]].append(i)
            for formula,indices in slots.items():
                if len(indices)<2:continue
                ranked=sorted(indices,key=lambda i:(-float(values[before[i]]),i))
                proposed=[before[i] for i in ranked]
                changed_groups+=int(proposed!=[before[i] for i in indices])
                for position,smiles in zip(indices,proposed):after[position]=smiles
            reason='scored_tail'
        if before[:protected_prefix]!=after[:protected_prefix] or Counter(before)!=Counter(after):raise ValueError('Protected prefix or candidate multiset changed')
        if Counter(keys)!=Counter(describe(s)[0] for s in after):raise ValueError('Official identities changed')
        if any(describe(before[i])[1]!=describe(after[i])[1] for i in range(protected_prefix,len(before))):raise ValueError('Formula slots changed')
        if reason!='scored_tail' and after!=before:raise ValueError('Invalid/no-spectrum fallback changed output')
        result.append((mid,';'.join(after)))
        details.append(dict(molecule_id=mid,reason=reason,changed=after!=before,changed_formula_groups=changed_groups,
                            protected_prefix_exact=True,candidate_multiset_exact=True,official_identity_multiset_exact=True,formula_slots_exact=True))
    return pd.DataFrame(result,columns=['molecule_id','smiles']),details


def validate_score_audit(root,configuration):
    root=Path(root);audit=read(root/'guarded_tail_scores.parquet.head_audit.json')
    frame=pd.read_parquet(root/'guarded_tail_scores.parquet');evidence=pd.read_parquet(root/'guarded_tail_evidence.parquet')
    expected_keys=set(zip(evidence.molecule_id.astype(str),evidence.smiles))
    output_keys=set(zip(frame.molecule_id.astype(str),frame.smiles))
    learned=configuration['score_mode']=='learned_heads'
    checks=dict(status=audit.get('status')=='passed' and audit.get('role')==('learned_v2' if learned else 'frozen_v2_mean') and audit.get('head_applied') is learned,
        encoder=audit.get('encoder_sha256')==V2_SHA,heads=audit.get('heads')==configuration['head_receipts'],
        input_hash=audit.get('evidence_sha256')==sha(root/'guarded_tail_evidence.parquet'),
        queries_hash=audit.get('queries_sha256')==sha(root/'effective_query_spectra.parquet'),
        output_hash=audit.get('output_sha256')==sha(root/'guarded_tail_scores.parquet'),
        exact_keys=expected_keys==output_keys and not frame.duplicated(['molecule_id','smiles']).any(),
        exact_rows=audit.get('input_rows')==audit.get('output_rows')==len(evidence)==len(frame),
        actual_score_coverage=audit.get('scored_candidate_rows')==int(frame.neural_ok.astype(bool).sum()) and audit.get('scored_queries')==int(frame.loc[frame.neural_ok.astype(bool),'molecule_id'].nunique()))
    failed=set(frame.loc[~frame.neural_ok.astype(bool),'molecule_id'].astype(str))
    checks['scoped_failures']={str(x['molecule_id']) for x in audit.get('errors',[])}==failed
    if not all(checks.values()):raise ValueError('Head score binding failed: '+repr(checks))
    return frame,audit,checks


def run(root,code,bundle,is_rerun,base_audit,configuration,device='cuda'):
    root,code,bundle=Path(root),Path(code),Path(bundle)
    final=root/'submission.csv';control=root/'submission_guarded_tail_control.csv'
    prefix=configuration['protected_prefix']
    if type(prefix) is not int or not 1 <= prefix <= 24:raise ValueError('Invalid protected prefix')
    if configuration['score_mode'] not in ('learned_heads','frozen_v2_mean'):raise ValueError('Unknown score mode')
    configuration_sha=hashlib.sha256(json.dumps(configuration,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    shutil.copy2(final,control)
    report=dict(status='prepared',mode='hidden_full' if is_rerun else 'fast_static',
        control_sha256=sha(control),baseline_audit_csv_sha256=base_audit['csv_sha256'],
        policy=f'prefix ranks1-{prefix} exact; ranks{prefix+1}-25 same-formula original slots only',model_invoked=False,
        protected_prefix=prefix,score_mode=configuration['score_mode'],configuration_sha256=configuration_sha)
    if report['control_sha256']!=base_audit['csv_sha256']:
        report.update(status='failed_closed',error_type='ValueError',error='Original audited MASS output was changed before tail')
        write(root/'guarded_tail_runtime.json',report)
        final.unlink(missing_ok=True)
        raise ValueError('Original audited MASS output was changed before tail')
    if not is_rerun:
        report.update(status='fast_static_no_model',rows=len(pd.read_csv(control)),output_sha256=sha(final),checks=dict(original_output_untouched=sha(final)==sha(control)),details=[])
        write(root/'guarded_tail_runtime.json',report);return report
    try:
        if sha(code/configuration['scorer_file'])!=configuration['scorer_sha256']:raise ValueError('Scorer source differs')
        if sha(code/'neural_scores_original.py')!=configuration['baseline_scorer_sha256']:raise ValueError('Original scorer source differs')
        if sha(bundle/'final_model.pt')!=V2_SHA:raise ValueError('Frozen v2 encoder differs')
        if not all(sha(code/k)==v for k,v in configuration['payload_pins'].items()):raise ValueError('Payload source/weights differ')
        source=pd.read_csv(control,dtype=str,keep_default_na=False)
        queries=pd.read_parquet(root/'effective_query_spectra.parquet');queries['molecule_id']=queries.molecule_id.astype(str)
        query={str(mid):g for mid,g in queries.groupby('molecule_id',sort=False)}
        spec=importlib.util.spec_from_file_location('_guarded_tail_original_features',bundle/'features.py')
        feat=importlib.util.module_from_spec(spec);spec.loader.exec_module(feat)
        skipped={};rows=[]
        for mid,raw in source.itertuples(index=False,name=None):
            mid=str(mid);candidates=raw.split(';');descriptions=[describe(s) for s in candidates];keys=[x[0] for x in descriptions]
            if None in keys or len(keys)!=len(set(keys)):skipped[mid]='invalid_or_duplicate_identity';continue
            if mid not in query:skipped[mid]='missing_query_spectra';continue
            usable=False
            for r in query[mid].itertuples(index=False):
                try:
                    _,n=feat.peaks(r.ms2_mzs,r.ms2_normalized_intensities,r.precursor_mz,96)
                    feat.metadata(r.precursor_mz,r.adduct,r.ionization_mode,r.collision_energy_ev)
                    if n>=3:usable=True;break
                except (ValueError,TypeError):pass
            if not usable:skipped[mid]='no_usable_spectra';continue
            for i,(s,(key,formula)) in enumerate(zip(candidates,descriptions),1):
                rows.append(dict(molecule_id=mid,smiles=s,baseline_rank=i,processed=True,metric_key=key,formula=formula))
        report['eligible_queries']=len({r['molecule_id'] for r in rows});report['eligible_candidate_rows']=len(rows)
        report['skipped_queries']=skipped
        if rows:
            evidence=pd.DataFrame(rows);evidence.to_parquet(root/'guarded_tail_evidence.parquet',index=False)
            cmd=[sys.executable,str(code/configuration['scorer_file']),str(bundle),'final_model.pt',
                 str(root/'guarded_tail_evidence.parquet'),str(root/'effective_query_spectra.parquet'),str(root/'guarded_tail_scores.parquet'),device]
            report['model_invoked']=True
            child=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=1200)
            (root/'guarded_tail_neural.log').write_text(child.stdout)
            if child.returncode:raise RuntimeError('Guarded tail head process failed; see guarded_tail_neural.log')
            scores,head_audit,bindings=validate_score_audit(root,configuration)
            report.update(score_bindings=bindings,head_receipts=head_audit['heads'],
                evidence_sha256=sha(root/'guarded_tail_evidence.parquet'),queries_sha256=sha(root/'effective_query_spectra.parquet'),
                scores_sha256=sha(root/'guarded_tail_scores.parquet'),head_audit_sha256=sha(root/'guarded_tail_scores.parquet.head_audit.json'))
            destination,details=reorder(source,scores,skipped,protected_prefix=prefix)
        else:
            destination=source.copy();details=[dict(molecule_id=str(mid),reason=skipped.get(str(mid),'no_eligible'),changed=False,
                protected_prefix_exact=True,candidate_multiset_exact=True,official_identity_multiset_exact=True,formula_slots_exact=True) for mid in source.molecule_id]
        if destination.molecule_id.tolist()!=source.molecule_id.tolist():raise ValueError('Molecule order changed')
        temp=root/'submission_guarded_tail.tmp';destination.to_csv(temp,index=False)
        if not pd.read_csv(temp,dtype=str,keep_default_na=False).equals(destination):raise ValueError('Tail CSV roundtrip differs')
        temp.replace(final)
        report.update(status='applied' if rows else 'no_eligible',rows=len(source),changed_queries=sum(x['changed'] for x in details),
            output_sha256=sha(final),details=details,checks=dict(control_matches_audited_base=sha(control)==base_audit['csv_sha256'],
            exact_molecule_order=True,protected_prefix_exact=all(x['protected_prefix_exact'] for x in details),candidate_multiset_exact=all(x['candidate_multiset_exact'] for x in details),
            official_identity_multiset_exact=all(x['official_identity_multiset_exact'] for x in details),formula_slots_exact=all(x['formula_slots_exact'] for x in details),
            no_eligible_explicit=bool(rows) or (not report['model_invoked'] and sha(final)==sha(control))))
        write(root/'guarded_tail_runtime.json',report);return report
    except BaseException as error:
        report.update(status='failed_closed',error_type=type(error).__name__,error=str(error)[:500])
        write(root/'guarded_tail_runtime.json',report)
        final.unlink(missing_ok=True)
        raise
