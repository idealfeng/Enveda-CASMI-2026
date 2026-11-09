"""Run the pinned Alex V12 measured-library overlay with explicit observations.

Only AST observation calls are added to the original function. Output validity is
checked with the official identity; an invalid proposed query keeps its control.
Global binding/loader failures remove the final CSV instead of hiding a failure.
"""
from __future__ import annotations
import ast
from collections import Counter
from functools import lru_cache
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import shutil

import pandas as pd


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def write(path,value):
    Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


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
    guesses=raw.split(';');keys=[identity(x) for x in guesses]
    return 1<=len(guesses)<=25 and all(guesses) and None not in keys and len(keys)==len(set(keys))


class Observe(ast.NodeTransformer):
    def __init__(self):self.reference_sites=0;self.match_sites=0
    def visit_Expr(self,node):
        node=self.generic_visit(node)
        call=node.value
        if (isinstance(call,ast.Call) and isinstance(call.func,ast.Attribute)
                and isinstance(call.func.value,ast.Name) and call.func.value.id=='refs'
                and call.func.attr=='append'):
            self.reference_sites+=1
            label='A' if any(isinstance(x,ast.Name) and x.id=='key' for x in ast.walk(call.args[0])) else 'B'
            observation=ast.parse('_observe_reference('+repr(label)+',refs[-1])').body[0]
            return [node,ast.copy_location(observation,node)]
        return node
    def visit_If(self,node):
        node=self.generic_visit(node)
        text=ast.unparse(node.test)
        if text=='match_smi is not None and best_cos >= TAU':
            self.match_sites+=1
            observation=ast.parse('_observe_match(mid,best_cos,best_k,match_smi)').body[0]
            return [ast.copy_location(observation,node),node]
        return node


def load_observed(source_path,source_sha,reference,match):
    source_path=Path(source_path)
    if sha(source_path)!=source_sha:raise ValueError('Original overlay function source changed')
    tree=ast.parse(source_path.read_text())
    if len(tree.body)!=1 or not isinstance(tree.body[0],ast.FunctionDef) or tree.body[0].name!='_apex_extlib_overlay':
        raise ValueError('Expected exactly the original overlay function')
    instrument=Observe();tree=instrument.visit(tree);ast.fix_missing_locations(tree)
    if (instrument.reference_sites,instrument.match_sites)!=(2,1):raise ValueError('Overlay observation sites changed')
    scope=dict(_observe_reference=reference,_observe_match=match)
    exec(compile(tree,'observed_original_external_library_overlay','exec'),scope)
    return scope['_apex_extlib_overlay'],dict(reference_sites=2,match_sites=1)


def resolve_sources(input_root,expected_files,test_path):
    root=Path(input_root);found={}
    for item in expected_files:
        candidates=[p for p in root.rglob(item['file']) if item['ref'].split('/')[1] in str(p)]
        if len(candidates)!=1:raise ValueError('Expected one source for '+item['file'])
        path=candidates[0]
        if path.stat().st_size!=item['bytes'] or sha(path)!=item['sha256']:raise ValueError('Library bytes/SHA mismatch '+item['file'])
        # Ensure the unchanged original glob selector actually reads this source.
        globbed=list(root.rglob(item['file']))
        if item['file']=='spectra.parquet':
            chosen=sorted(globbed,key=lambda p:('massbank' not in str(p).lower(),len(str(p))))[0]
        else:chosen=sorted(globbed,key=lambda p:len(str(p)))[0]
        if chosen.resolve()!=path.resolve():raise ValueError('Original selector points to another library')
        found[item['file']]=dict(path=str(path),bytes=path.stat().st_size,sha256=item['sha256'],ref=item['ref'],version=item['version'])
    tests=sorted(root.rglob('test.parquet'),key=lambda p:('mass-spectra' not in str(p).lower(),len(str(p))))
    if not tests or tests[0].resolve()!=Path(test_path).resolve():raise ValueError('Original overlay selects another test')
    return found


def run(root,input_root,test_path,is_rerun,sample_ids,base_audit,source_path,source_sha,expected_files):
    root=Path(root);final=root/'submission.csv';control=root/'submission_external_control.csv'
    shutil.copy2(final,control)
    report=dict(status='prepared',mode='hidden_full' if is_rerun else 'fast_static',
        control_sha256=sha(control),base_audit_csv_sha256=base_audit['csv_sha256'],
        original_function_sha256=source_sha,library_matching_performed=False,
        algorithm='Alex V12 original TAU=.80, four matched peaks, existing library>=.90 protected; official identity validity guard')
    try:
        if base_audit.get('status')!='passed' or sha(control)!=base_audit['csv_sha256']:raise ValueError('Base audit/output binding failed')
        source=pd.read_csv(control,dtype=str,keep_default_na=False)
        if list(source.columns)!=['molecule_id','smiles'] or source.molecule_id.tolist()!=list(sample_ids) or not source.molecule_id.is_unique:
            raise ValueError('Original control IDs/schema changed')
        if not all(valid(x) for x in source.smiles):raise ValueError('Original control has invalid or duplicate official identities')
        report['libraries']=resolve_sources(input_root,expected_files,test_path)
        if not is_rerun:
            report.update(status='fast_static_no_matching',rows=len(source),output_sha256=sha(final),checks=dict(control_bound=True,original_output_untouched=True,all_library_pins=True,exact_ids_order=True,official_identities_valid=True),details=[])
            write(root/'external_overlay_runtime.json',report);return report
        reference_counts=Counter();reference_peaks=Counter();matches=[]
        def reference(label,row):
            reference_counts[label]+=1;reference_peaks[label]+=len(row[2])
        def match(mid,cosine,peaks,smiles):
            value=float(cosine)
            matches.append(dict(molecule_id=str(mid),cosine=value if math.isfinite(value) else None,matched_peaks=int(peaks),smiles=smiles,
                above_threshold=smiles is not None and math.isfinite(value) and value>=.80 and peaks>=4))
        overlay,sites=load_observed(source_path,source_sha,reference,match)
        report['library_matching_performed']=True
        overlay(work=str(root),inp=str(input_root))
        if reference_counts['A']<1 or reference_counts['B']<1:raise RuntimeError('One external library failed to load usable references')
        original_report_path=root/'apex_extlib_audit.json'
        if not original_report_path.is_file():raise RuntimeError('Original overlay did not finish')
        original_report=json.loads(original_report_path.read_text())
        shutil.copy2(final,root/'submission_external_proposed.csv')
        proposed=pd.read_csv(final,dtype=str,keep_default_na=False)
        if list(proposed.columns)!=list(source.columns) or proposed.molecule_id.tolist()!=source.molecule_id.tolist():raise ValueError('Overlay changed IDs/schema')
        if sha(root/'submission_pre_apex_extlib.csv')!=sha(control):raise ValueError('Original overlay consumed another CSV')
        accepted=[];details=[]
        for mid,old,new in zip(source.molecule_id,source.smiles,proposed.smiles):
            okay=valid(new);value=new if okay else old
            accepted.append(value)
            details.append(dict(molecule_id=mid,proposed_changed=new!=old,accepted_changed=value!=old,
                proposed_top1_changed=new.split(';')[0]!=old.split(';')[0],accepted_top1_changed=value.split(';')[0]!=old.split(';')[0],
                validity_guard_preserved_control=not okay,official_identities_valid=valid(value)))
        if original_report.get('molecules')!=len(source):raise ValueError('Original overlay molecule count differs')
        if original_report.get('hits')!=sum(x['above_threshold'] for x in matches):raise ValueError('Observed hit count differs')
        if original_report.get('promoted')!=sum(x['proposed_top1_changed'] for x in details):raise ValueError('Observed original promotions differ')
        destination=source.copy();destination['smiles']=accepted;temporary=root/'submission_external_guard.tmp'
        destination.to_csv(temporary,index=False)
        if not pd.read_csv(temporary,dtype=str,keep_default_na=False).equals(destination):raise ValueError('CSV roundtrip differs')
        temporary.replace(final)
        report.update(status='applied',rows=len(source),reference_counts=dict(reference_counts),reference_peak_counts=dict(reference_peaks),
            observation_sites=sites,original_report=original_report,actual_matches=matches,
            changed_queries=sum(x['accepted_changed'] for x in details),changed_top1=sum(x['accepted_top1_changed'] for x in details),
            invalid_proposals_preserved=sum(x['validity_guard_preserved_control'] for x in details),
            output_sha256=sha(final),queries_sha256=sha(test_path),details=details,
            checks=dict(control_bound=sha(control)==base_audit['csv_sha256'],original_function_pin=sha(source_path)==source_sha,
                original_consumed_control=sha(root/'submission_pre_apex_extlib.csv')==sha(control),all_library_pins=True,
                both_reference_sources_loaded=reference_counts['A']>0 and reference_counts['B']>0,exact_ids_order=True,
                official_identities_valid=all(x['official_identities_valid'] for x in details),
                actual_hit_count_bound=True,actual_promotion_count_bound=True))
        write(root/'external_overlay_runtime.json',report);return report
    except BaseException as error:
        report.update(status='failed_closed',error_type=type(error).__name__,error=str(error)[:400])
        write(root/'external_overlay_runtime.json',report);final.unlink(missing_ok=True);raise


def audit(root,input_root,test_path,is_rerun,sample_ids,base_audit,source_path,source_sha,expected_files,branch,recipe_sha256):
    root=Path(root);report=json.loads((root/'external_overlay_runtime.json').read_text())
    control=pd.read_csv(root/'submission_external_control.csv',dtype=str,keep_default_na=False)
    final=pd.read_csv(root/'submission.csv',dtype=str,keep_default_na=False)
    checks=dict(base_audit_passed=base_audit.get('status')=='passed',
        control_bound=sha(root/'submission_external_control.csv')==base_audit['csv_sha256']==report.get('control_sha256'),
        final_bound=sha(root/'submission.csv')==report.get('output_sha256'),
        source_function_pin=sha(source_path)==source_sha==report.get('original_function_sha256'),
        exact_ids_schema=list(final.columns)==['molecule_id','smiles'] and final.molecule_id.tolist()==list(sample_ids)==control.molecule_id.tolist() and final.molecule_id.is_unique,
        official_identities_valid=all(valid(s) for s in final.smiles),
        library_file_pins=resolve_sources(input_root,expected_files,test_path)==report.get('libraries'),
        runtime_checks=bool(report.get('checks')) and all(v is True for v in report['checks'].values()))
    if is_rerun:
        checks['actual_external_matching']=report.get('status')=='applied' and report.get('mode')=='hidden_full' and report.get('library_matching_performed') is True
        checks['both_sources_observed']=report.get('reference_counts',{}).get('A',0)>0 and report.get('reference_counts',{}).get('B',0)>0 and report.get('observation_sites')==dict(reference_sites=2,match_sites=1)
        checks['query_hash']=report.get('queries_sha256')==sha(test_path)
        matches=report['actual_matches'];by_mid={x['molecule_id']:x for x in matches}
        checks['unique_observed_queries']=len(matches)==len(by_mid) and set(by_mid)<=set(sample_ids)
        expected_proposals=[];expected_finals=[]
        for mid,raw in control.itertuples(index=False,name=None):
            arr=raw.split(';');match=by_mid.get(mid);proposal=raw
            if match:
                above=match['smiles'] is not None and match['cosine'] is not None and match['cosine']>=.80 and match['matched_peaks']>=4
                if above!=match['above_threshold']:raise ValueError('Observed threshold flag differs')
                if above:
                    s=match['smiles'];proposal=';'.join(([s]+[x for x in arr if x!=s]) if s in arr else ([s]+arr)[:25])
            expected_proposals.append(proposal);expected_finals.append(proposal if valid(proposal) else raw)
        proposed=pd.read_csv(root/'submission_external_proposed.csv',dtype=str,keep_default_na=False)
        checks['actual_matches_consumed']=proposed.molecule_id.tolist()==list(sample_ids) and proposed.smiles.tolist()==expected_proposals and final.smiles.tolist()==expected_finals
        checks['actual_hit_counts']=report['original_report']['hits']==sum(x['above_threshold'] for x in matches)
        checks['actual_promotion_counts']=report['changed_top1']==sum(a.split(';')[0]!=b.split(';')[0] for a,b in zip(control.smiles,final.smiles))
        checks['original_input_bound']=sha(root/'submission_pre_apex_extlib.csv')==sha(root/'submission_external_control.csv')
    else:
        checks['fast_no_matching']=report.get('status')=='fast_static_no_matching' and report.get('library_matching_performed') is False and final.equals(control)
    if not all(checks.values()):raise ValueError('External overlay observer rejected '+repr(checks))
    result=dict(status='passed',branch=branch,recipe_sha256=recipe_sha256,mode='hidden_full' if is_rerun else 'fast_static',checks=checks,
        csv_sha256=sha(root/'submission.csv'),control_sha256=sha(root/'submission_external_control.csv'),runtime_report_sha256=sha(root/'external_overlay_runtime.json'),
        reference_counts=report.get('reference_counts',{}),hits=report.get('original_report',{}).get('hits',0),changed_top1=report.get('changed_top1',0),
        invalid_proposals_preserved=report.get('invalid_proposals_preserved',0),visible_models_executed=False if not is_rerun else None)
    write(root/'external_overlay_audit.json',result);return result
