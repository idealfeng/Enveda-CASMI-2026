"""Recover only identity-equivalent existing candidates blocked by old AB guard.

Runs after the complete frozen .488 pipeline. It neither scores references nor
inserts any new candidate. Every promotion moves an existing native SMILES.
"""
from __future__ import annotations
from collections import Counter
from functools import lru_cache
import hashlib,json,math
from pathlib import Path
import shutil

import pandas as pd

def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def read(path):return json.loads(Path(path).read_text())
def write(path,value):Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')

@lru_cache(maxsize=100000)
def identity(smiles):
    import rdkit
    from rdkit import Chem,RDLogger
    from rdkit.Chem.MolStandardize import rdMolStandardize
    if rdkit.__version__!='2026.03.3':raise RuntimeError('Official RDKit required')
    RDLogger.DisableLog('rdApp.*')
    try:
        mol=Chem.MolFromSmiles(smiles)
        if mol is None:return None
        Chem.RemoveStereochemistry(mol)
        key=Chem.MolToInchiKey(rdMolStandardize.TautomerEnumerator().Canonicalize(mol))
        return key[:14] if key else None
    except (ValueError,TypeError,RuntimeError):return None

def valid(raw):
    parts=raw.split(';');keys=[identity(x) for x in parts]
    return 1<=len(parts)<=25 and all(parts) and None not in keys and len(keys)==len(set(keys))

def above(match):
    if not match:return False
    try:score=float(match.get('cosine'));peaks=match.get('matched_peaks')
    except (ValueError,TypeError):score=float('nan');peaks=None
    expected=match.get('smiles') is not None and math.isfinite(score) and score>=.80 and type(peaks) is int and peaks>=4
    if match.get('above_threshold') is not expected:raise ValueError('Old observed threshold flag differs')
    return expected

def old_proposal(raw,match):
    if not above(match):return raw
    parts=raw.split(';');s=match['smiles']
    return ';'.join(([s]+[x for x in parts if x!=s]) if s in parts else ([s]+parts)[:25])

def bindings(root,old_audit,is_rerun,sample_ids,incoming_path):
    root=Path(root);runtime_path=root/'external_overlay_runtime.json';pre_path=root/'submission_external_control.csv'
    if old_audit.get('status')!='passed' or not old_audit.get('checks') or not all(v is True for v in old_audit['checks'].values()):raise ValueError('Original AB audit is not passed')
    if sha(runtime_path)!=old_audit.get('runtime_report_sha256'):raise ValueError('Original AB runtime hash differs')
    if sha(incoming_path)!=old_audit.get('csv_sha256'):raise ValueError('Incoming .488 CSV differs from its audit')
    runtime=read(runtime_path);mode='hidden_full' if is_rerun else 'fast_static'
    if old_audit.get('mode')!=mode or runtime.get('mode')!=mode:raise ValueError('Original AB mode differs')
    if sha(pre_path)!=old_audit.get('control_sha256') or sha(pre_path)!=runtime.get('control_sha256') or sha(pre_path)!=runtime.get('base_audit_csv_sha256'):raise ValueError('Original pre-AB control hash differs')
    if sha(incoming_path)!=runtime.get('output_sha256'):raise ValueError('Original AB output hash differs')
    incoming=pd.read_csv(incoming_path,dtype=str,keep_default_na=False);pre=pd.read_csv(pre_path,dtype=str,keep_default_na=False)
    for frame in (incoming,pre):
        if list(frame.columns)!=['molecule_id','smiles'] or frame.molecule_id.tolist()!=list(sample_ids) or not frame.molecule_id.is_unique:raise ValueError('Original IDs/schema differ')
        if not all(valid(raw) for raw in frame.smiles):raise ValueError('Original control has invalid/duplicate official identity')
    if runtime.get('rows')!=len(incoming):raise ValueError('Original runtime query count differs')
    if is_rerun:
        if runtime.get('status')!='applied' or runtime.get('library_matching_performed') is not True:raise ValueError('Original AB did not actually match')
        if not runtime.get('checks') or not all(v is True for v in runtime['checks'].values()):raise ValueError('Original AB runtime checks not passed')
        details=runtime.get('details',[]);matches=runtime.get('actual_matches',[])
        if [x['molecule_id'] for x in details]!=list(sample_ids):raise ValueError('Original query details differ')
        if len(matches)!=len({x['molecule_id'] for x in matches}) or not {x['molecule_id'] for x in matches}<=set(sample_ids):raise ValueError('Duplicate or unknown original match query')
        by_match={x['molecule_id']:x for x in matches}
        for (mid,raw),new,detail in zip(pre.itertuples(index=False,name=None),incoming.smiles,details):
            proposal=old_proposal(raw,by_match.get(mid));okay=valid(proposal);wanted=proposal if okay else raw
            if new!=wanted or detail.get('validity_guard_preserved_control') is not (not okay):raise ValueError('Original guard decision/output not reconstructed')
            if detail.get('official_identities_valid') is not True or detail.get('accepted_changed') is not (wanted!=raw):raise ValueError('Original acceptance detail differs')
    else:
        if runtime.get('status')!='fast_static_no_matching' or runtime.get('library_matching_performed') is not False or not incoming.equals(pre) or runtime.get('details')!=[]:raise ValueError('Original fast path differs')
    return incoming,pre,runtime

def reorder(incoming,pre,runtime):
    details={x['molecule_id']:x for x in runtime['details']};matches={x['molecule_id']:x for x in runtime['actual_matches']}
    pre_rows=dict(pre.itertuples(index=False,name=None));rows=[];audit_rows=[]
    for mid,raw in incoming.itertuples(index=False,name=None):
        old=raw.split(';');new=list(old);match=matches.get(mid);blocked=details[mid].get('validity_guard_preserved_control') is True
        high=above(match);key=identity(match['smiles']) if high else None
        before=pre_rows[mid].split(';');pre_keys=[identity(x) for x in before];keys=[identity(x) for x in old]
        pre_occ=pre_keys.count(key) if key else 0;current_occ=keys.count(key) if key else 0
        eligible=blocked and high and key is not None and pre_occ==1 and current_occ==1
        from_rank=None;reason='original_guard_not_blocked'
        if blocked:
            if not high:reason='no_threshold_passing_reference'
            elif key is None:reason='invalid_reference_identity'
            elif pre_occ!=1 or current_occ!=1:reason='reference_identity_not_unique_in_both_controls'
            else:
                index=keys.index(key);from_rank=index+1
                if index==0:reason='identity_already_first'
                else:new=[old[index]]+old[:index]+old[index+1:];reason='blocked_alias_native_candidate_promoted'
        if Counter(old)!=Counter(new) or len(old)!=len(new):raise ValueError('Alias promotion changed native candidate multiset')
        value=';'.join(new)
        if not valid(value):raise ValueError('Alias output identity invalid')
        if value!=raw and (not eligible or from_rank is None or from_rank<2):raise ValueError('Promotion outside approved blocked-alias scope')
        rows.append((mid,value));audit_rows.append(dict(molecule_id=mid,old_guard_blocked=blocked,above_threshold=high,
            reference_identity=key,precontrol_occurrences=pre_occ,incoming_occurrences=current_occ,eligible=eligible,
            reason=reason,from_rank=from_rank,to_rank=1 if from_rank else None,changed=value!=raw,
            candidate_multiset_exact=True,candidate_count_exact=True))
    return pd.DataFrame(rows,columns=['molecule_id','smiles']),audit_rows

def run(root,old_audit,is_rerun,sample_ids,branch,recipe_sha256):
    root=Path(root);final=root/'submission.csv';incoming_path=root/'submission_alias_promotion_control.csv'
    shutil.copy2(final,incoming_path)
    report=dict(status='prepared',mode='hidden_full' if is_rerun else 'fast_static',branch=branch,recipe_sha256=recipe_sha256,
        module_sha256=sha(__file__),incoming_ab_sha256=sha(incoming_path),old_runtime_sha256=None,
        old_audit=old_audit,matching_performed=False,new_candidates_inserted=0)
    try:
        incoming,pre,runtime=bindings(root,old_audit,is_rerun,sample_ids,incoming_path)
        report.update(old_runtime_sha256=sha(root/'external_overlay_runtime.json'),pre_ab_control_sha256=sha(root/'submission_external_control.csv'),rows=len(incoming))
        if is_rerun:destination,details=reorder(incoming,pre,runtime)
        else:destination=incoming.copy();details=[]
        temporary=root/'submission_alias_promotion.tmp';destination.to_csv(temporary,index=False)
        if not pd.read_csv(temporary,dtype=str,keep_default_na=False).equals(destination):raise ValueError('Alias CSV roundtrip differs')
        temporary.replace(final)
        report.update(status='applied' if is_rerun else 'fast_static_no_promotion',details=details,
            changed_queries=sum(x['changed'] for x in details),eligible_queries=sum(x['eligible'] for x in details),
            output_sha256=sha(final),checks=dict(original_ab_audit_bound=True,original_runtime_bound=True,pre_ab_control_bound=True,
                original_ab_output_bound=True,exact_ids_order=destination.molecule_id.tolist()==list(sample_ids),
                all_native_candidate_multisets=True,all_native_candidate_counts=True,
                official_identities_valid=all(valid(x) for x in destination.smiles),no_new_matching=True,no_new_candidates=True,
                approved_blocked_alias_scope=True))
        write(root/'alias_promotion_runtime.json',report);return report
    except BaseException as error:
        report.update(status='failed_closed',error_type=type(error).__name__,error=str(error)[:400])
        write(root/'alias_promotion_runtime.json',report);final.unlink(missing_ok=True);raise

def audit(root,old_audit,is_rerun,sample_ids,branch,recipe_sha256):
    root=Path(root);report=read(root/'alias_promotion_runtime.json');incoming_path=root/'submission_alias_promotion_control.csv'
    incoming,pre,runtime=bindings(root,old_audit,is_rerun,sample_ids,incoming_path)
    final=pd.read_csv(root/'submission.csv',dtype=str,keep_default_na=False)
    checks=dict(original_ab_audit_passed=old_audit.get('status')=='passed',old_audit_snapshot_bound=report.get('old_audit')==old_audit,
        original_runtime_bound=sha(root/'external_overlay_runtime.json')==old_audit['runtime_report_sha256']==report.get('old_runtime_sha256'),
        original_ab_output_bound=sha(incoming_path)==old_audit['csv_sha256']==report.get('incoming_ab_sha256'),
        pre_ab_control_bound=sha(root/'submission_external_control.csv')==old_audit['control_sha256']==report.get('pre_ab_control_sha256'),
        module_pin=sha(__file__)==report.get('module_sha256'),branch_recipe_bound=report.get('branch')==branch and report.get('recipe_sha256')==recipe_sha256,
        final_bound=sha(root/'submission.csv')==report.get('output_sha256'),exact_ids_schema=list(final.columns)==['molecule_id','smiles'] and final.molecule_id.tolist()==list(sample_ids)==incoming.molecule_id.tolist() and final.molecule_id.is_unique,
        native_candidate_multisets=all(Counter(a.split(';'))==Counter(b.split(';')) for a,b in zip(incoming.smiles,final.smiles)),
        official_identities_valid=all(valid(x) for x in final.smiles),runtime_checks=bool(report.get('checks')) and all(x is True for x in report['checks'].values()),
        no_new_scoring_or_candidates=report.get('matching_performed') is False and report.get('new_candidates_inserted')==0)
    if is_rerun:
        wanted,details=reorder(incoming,pre,runtime)
        checks['actual_old_matches_consumed']=wanted.equals(final) and report.get('details')==details
        checks['actual_causal_scope_counts']=report.get('eligible_queries')==sum(x['eligible'] for x in details) and report.get('changed_queries')==sum(x['changed'] for x in details)
        checks['hidden_execution']=report.get('status')=='applied' and report.get('mode')=='hidden_full' and report.get('rows')==len(sample_ids)>0
    else:checks['fast_no_promotion']=report.get('status')=='fast_static_no_promotion' and report.get('mode')=='fast_static' and final.equals(incoming) and report.get('details')==[] and report.get('changed_queries')==0
    if not all(checks.values()):raise ValueError('Alias promotion audit rejected: '+repr(checks))
    result=dict(status='passed',mode='hidden_full' if is_rerun else 'fast_static',branch=branch,recipe_sha256=recipe_sha256,checks=checks,
        csv_sha256=sha(root/'submission.csv'),control_sha256=sha(incoming_path),runtime_report_sha256=sha(root/'alias_promotion_runtime.json'),
        eligible_queries=report.get('eligible_queries',0),changed_queries=report.get('changed_queries',0),module_sha256=sha(__file__))
    write(root/'alias_promotion_audit.json',result);return result
