"""Source-controlled measured-library variants of the frozen Alex overlay.

The original function remains the source of loading, peak processing, cosine,
stable mass sorting, best-match selection and proposal construction. AST changes
only route reference appends, expose actual selections, and add observed adducts.
"""
from __future__ import annotations
import ast
from collections import Counter
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import shutil
import sys

import pandas as pd

REFERENCE_COUNTS={'A':200724,'B':124160}
OFFSETS={'[M+H]+':(1,1.007276466621),'[M-H]-':(1,-1.007276466621),
 '[M+Na]+':(1,22.989218),'[M+K]+':(1,38.963158),'[M+NH4]+':(1,18.033823),
 '[M+HCOO]-':(1,44.998201),'[M+FA-H]-':(1,44.998201),
 '[M+H-H2O]+':(1,-17.003288),'[M-H2O+H]+':(1,-17.003288),
 '[M+Cl]-':(1,34.969402),'[M+2H]2+':(2,2.014552933242),
 '[M-2H]2-':(2,-2.014552933242)}

def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def read(path):return json.loads(Path(path).read_text())
def write(path,value):Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
def canonical_sha(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def load_module(name,path,pin):
    if sha(path)!=pin:raise ValueError('Pinned helper source differs: '+Path(path).name)
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module

def old_helper(configuration):
    return load_module('_external_old_guard_1110',Path(__file__).with_name('external_library_overlay_20261109.py'),configuration['old_helper_sha256'])

def trusted_precursor(neutral,mode,adduct,measured,old):
    """Return exact old value unless every predeclared chemical gate passes."""
    try:measured=float(measured);neutral=float(neutral);old=float(old)
    except (TypeError,ValueError):return old,False,'missing_or_invalid'
    if not math.isfinite(measured) or measured<=0 or not math.isfinite(neutral) or not math.isfinite(old):return old,False,'missing_or_invalid'
    adduct=str(adduct)
    if adduct not in OFFSETS:return old,False,'unknown_adduct'
    if not ((adduct.endswith('+') and mode==1) or (adduct.endswith('-') and mode==-1)):
        return old,False,'mode_incompatible'
    charge,offset=OFFSETS[adduct];theory=(neutral+offset)/charge;tol=measured*1e-5+.002
    if abs(measured-theory)>tol:return old,False,'chemical_inconsistent'
    if abs(measured-old)<=tol:return old,False,'already_within_old_window'
    return measured,True,'trusted_index_corrected'

class Instrument(ast.NodeTransformer):
    """Every matching arithmetic expression and condition is left unchanged."""
    def __init__(self):self.sites=Counter()
    def visit_Call(self,node):
        node=self.generic_visit(node)
        if isinstance(node.func,ast.Attribute) and isinstance(node.func.value,ast.Name):
            if node.func.value.id=='refs' and node.func.attr=='append':
                label='A' if any(isinstance(x,ast.Name) and x.id=='key' for x in ast.walk(node.args[0])) else 'B'
                self.sites['append_'+label]+=1
                return ast.copy_location(ast.Call(func=ast.Name(id='_append_reference',ctx=ast.Load()),args=[ast.Constant(label),ast.Name(id='refs',ctx=ast.Load()),node.args[0],ast.Name(id='row',ctx=ast.Load())],keywords=[]),node)
            if node.func.value.id=='pd' and node.func.attr=='read_parquet':
                for kw in node.keywords:
                    if kw.arg=='columns' and isinstance(kw.value,ast.List):
                        names=[x.value for x in kw.value.elts if isinstance(x,ast.Constant)]
                        if 'is_casmi_subset' in names:
                            for name in ('precursor_mz','adduct'):
                                if name not in names:kw.value.elts.append(ast.Constant(name))
                            self.sites['massbank_metadata']+=1
        if isinstance(node.func,ast.Name) and node.func.id=='dict' and {x.arg for x in node.keywords}=={'mz','it','prec','mode','nm'}:
            node.keywords.append(ast.keyword(arg='adduct',value=ast.Name(id='adduct',ctx=ast.Load())));self.sites['query_adduct']+=1
        return node
    def visit_Assign(self,node):
        node=self.generic_visit(node)
        names=[x.id for x in node.targets if isinstance(x,ast.Name)]
        if names==['refs'] and isinstance(node.value,ast.List):
            self.sites['queries']+=1
            return [ast.copy_location(ast.parse('_observe_queries(queries,lib_max)').body[0],node),node]
        if names==['best_match'] and any(isinstance(x,ast.Name) and x.id=='ref' for x in ast.walk(node.value)):
            self.sites['best_reference']+=1
            return [node,ast.copy_location(ast.parse('_observe_best(mid,q,ref,cos,n_matched)').body[0],node)]
        return node
    def visit_FunctionDef(self,node):
        node=self.generic_visit(node)
        if node.name=='calc_cosine':
            self.sites['cosine']+=1
            return [node,ast.copy_location(ast.parse('_observe_cosine(calc_cosine)').body[0],node)]
        return node
    def visit_If(self,node):
        node=self.generic_visit(node)
        if ast.unparse(node.test)=='match_smi is not None and best_cos >= TAU':
            self.sites['final_match']+=1
            return [ast.copy_location(ast.parse('_observe_match(mid,best_cos,best_k,match_smi)').body[0],node),node]
        return node

def execute_original(root,input_root,source_path,source_sha,configuration):
    if sha(source_path)!=source_sha:raise ValueError('Original Alex function source differs')
    tree=ast.parse(Path(source_path).read_text())
    if len(tree.body)!=1 or not isinstance(tree.body[0],ast.FunctionDef) or tree.body[0].name!='_apex_extlib_overlay':
        raise ValueError('Expected the single original function')
    transformer=Instrument();tree=transformer.visit(tree);ast.fix_missing_locations(tree)
    expected={'append_A':1,'append_B':1,'massbank_metadata':1,'query_adduct':1,'queries':1,'best_reference':1,'cosine':1,'final_match':1}
    if dict(transformer.sites)!=expected:raise ValueError('Original AST observation sites differ: '+repr(dict(transformer.sites)))
    selected=set(configuration['sources'])-{'E'}
    if not selected or not selected<={'A','B'}:raise ValueError('Expected at least one selected A/B source')
    seen=Counter();enabled=Counter();corrections=Counter();row_metadata={};best={};actual={};shared={};corrected_rows=[]
    def append(label,refs,row_tuple,row):
        seen[label]+=1
        if label not in selected:return
        detail=dict(source=label,reference_ordinal=seen[label]-1,adduct=str(row.get('adduct','')) if label=='A' else str(row.adduct))
        if label=='B':
            old=row_tuple[1];new,changed,reason=trusted_precursor(row_tuple[6],row_tuple[0],row.adduct,row.precursor_mz,old)
            detail.update(original_precursor_mz=old,measured_precursor_mz=finite(row.precursor_mz),precursor_corrected=False)
            if configuration.get('trusted_bprec'):
                corrections[reason]+=1
                if changed:
                    row_tuple=(row_tuple[0],new,*row_tuple[2:]);detail['precursor_corrected']=True
                    corrected_rows.append(dict(reference_ordinal=seen[label]-1,old_precursor_mz=old,new_precursor_mz=new,adduct=str(row.adduct)))
        refs.append(row_tuple);enabled[label]+=1;row_metadata[id(row_tuple)]=detail
    def queries(value,lib_max):shared['queries']=value;shared['lib_max']=lib_max
    def cosine(fn):shared['calc_cosine']=fn
    def observe_best(mid,q,ref,cosine,peaks):
        meta=row_metadata[id(ref)]
        best[str(mid)]=dict(**meta,cosine=float(cosine),matched_peaks=int(peaks),smiles=ref[5],
            reference_precursor_mz=finite(ref[1]),query_precursor_mz=finite(q['prec']),query_adduct=q['adduct'],mode=int(q['mode']))
    def observe_match(mid,cosine,peaks,smiles):
        value=float(cosine);record=best.get(str(mid),dict(source=None))
        actual[str(mid)]=dict(record,cosine=value if math.isfinite(value) else None,matched_peaks=int(peaks),smiles=smiles,
            above_threshold=smiles is not None and math.isfinite(value) and value>=.80 and peaks>=4)
    scope=dict(_append_reference=append,_observe_queries=queries,_observe_cosine=cosine,_observe_best=observe_best,_observe_match=observe_match)
    exec(compile(tree,'controlled_original_alex_overlay_1110','exec'),scope)
    scope['_apex_extlib_overlay'](work=str(root),inp=str(input_root))
    if dict(seen)!=REFERENCE_COUNTS:raise ValueError('Pinned source usable-reference counts differ: '+repr(dict(seen)))
    if any(enabled[x]!=REFERENCE_COUNTS[x] for x in selected) or any(enabled[x] for x in {'A','B'}-selected):
        raise ValueError('Selected/disabled source counts differ')
    if configuration.get('trusted_bprec') and len(corrected_rows)!=1281:raise ValueError('Trusted B correction count differs')
    expected_corrected=1281 if configuration.get('trusted_bprec') else 0
    if len(corrected_rows)!=expected_corrected:raise ValueError('Unexpected precursor corrections')
    row_metadata.clear()
    return actual,shared,dict(observation_sites=expected,seen_reference_counts=dict(seen),selected_reference_counts=dict(enabled),
        bprec_reason_counts=dict(corrections),bprec_corrected_rows=corrected_rows,bprec_corrected_count=len(corrected_rows))

def finite(value):
    try:value=float(value);return value if math.isfinite(value) else None
    except (TypeError,ValueError):return None

def propose(raw,match):
    if not match or not match.get('above_threshold'):return raw
    arr=raw.split(';');smiles=match['smiles']
    return ';'.join(([smiles]+[s for s in arr if s!=smiles]) if smiles in arr else ([smiles]+arr)[:25])

def compose(control,ab_matches,e_matches,policy,guard):
    if policy not in ('none','gap_fill','compete'):raise ValueError('Unknown E composition policy')
    for match in ab_matches.values():
        value=finite(match.get('cosine'));expected=(match.get('smiles') is not None and value is not None and value>=.80 and match.get('matched_peaks',0)>=4)
        if match.get('above_threshold') is not expected:raise ValueError('AB observed threshold flag differs')
        if expected and match.get('source') not in ('A','B'):raise ValueError('Invalid observed AB source')
    rows=[];details=[];ab_values=[];proposals=[]
    for mid,raw in control.itertuples(index=False,name=None):
        mid=str(mid);ab=ab_matches.get(mid);proposal=propose(raw,ab);ab_ok=guard.valid(proposal)
        ab_value=proposal if ab_ok else raw
        accepted_ab=bool(ab and ab.get('above_threshold') and ab_ok)
        em=e_matches.get(mid);e_candidate=None;take=False;reason='no_e_hit'
        if em:
            if em.get('source')!='E' or finite(em.get('cosine')) is None or em['cosine']<.80 or em.get('matched_peaks',0)<4:
                raise ValueError('Invalid Enveda match contract')
            if em.get('adduct') not in ('[M+H]+','[M-H]-'):raise ValueError('Unsupported Enveda adduct')
            if not em.get('above_threshold',True):raise ValueError('Unexpected subthreshold E match')
            # E is a second stage over the accepted AB output. A new E winner
            # retains a newly inserted AB candidate below it instead of dropping
            # that candidate by reconstructing from the pre-AB control.
            e_candidate=propose(ab_value,dict(em,above_threshold=True))
            if not guard.valid(e_candidate):reason='invalid_e_preserves_ab'
            elif policy=='gap_fill':take=not accepted_ab;reason='e_gap_fill' if take else 'valid_ab_protected'
            elif policy=='compete':take=not accepted_ab or em['cosine']>ab['cosine'];reason='e_wins' if take else 'ab_score_or_tie_protected'
            else:reason='e_disabled'
        value=e_candidate if take else ab_value
        if not guard.valid(value):raise ValueError('Composed query is invalid')
        ab_identity=guard.identity(ab['smiles']) if ab and ab.get('smiles') is not None else None
        ab_identity_present=ab_identity is not None and ab_identity in {guard.identity(s) for s in raw.split(';')}
        invalid_reason=None if ab_ok else ('duplicate_official_identity' if ab_identity is not None else 'invalid_structure')
        rows.append((mid,value));ab_values.append((mid,ab_value));proposals.append((mid,proposal))
        details.append(dict(molecule_id=mid,ab_hit_accepted=accepted_ab,ab_proposal_valid=ab_ok,ab_changed=ab_value!=raw,
            ab_invalid_reason=invalid_reason,ab_reference_identity_present_in_control=ab_identity_present,
            e_selected=take,e_reason=reason,changed=value!=raw,top1_changed=value.split(';')[0]!=raw.split(';')[0],
            top1_identity_changed=guard.identity(value.split(';')[0])!=guard.identity(raw.split(';')[0])))
    return (pd.DataFrame(rows,columns=['molecule_id','smiles']),details,
        pd.DataFrame(ab_values,columns=['molecule_id','smiles']),pd.DataFrame(proposals,columns=['molecule_id','smiles']))

def validate_configuration(configuration):
    sources=configuration['sources'];policy=configuration['e_policy'];trusted=configuration['trusted_bprec']
    if not isinstance(sources,list) or len(sources)!=len(set(sources)) or not set(sources)<={'A','B','E'}:raise ValueError('Invalid source list')
    if not set(sources)&{'A','B'}:raise ValueError('Missing original source')
    if type(trusted) is not bool or policy not in ('none','gap_fill','compete'):raise ValueError('Invalid variant configuration')
    if ('E' in sources)!=(policy!='none'):raise ValueError('E source/policy mismatch')
    if trusted and (set(sources)!={'A','B'} or policy!='none'):raise ValueError('Trusted precursor variant must be isolated AB')
    if 'E' in sources and (not configuration.get('enveda_file') or not configuration.get('e_helper_sha256')):raise ValueError('Missing Enveda pins')

def resolve_enveda(input_root,configuration):
    item=configuration.get('enveda_file')
    if not item:return None
    hits=[p for p in Path(input_root).rglob(item['file']) if item['ref'].split('/')[1] in str(p)]
    if len(hits)!=1:raise ValueError('Expected one pinned Enveda library')
    p=hits[0]
    if p.stat().st_size!=item['bytes'] or sha(p)!=item['sha256']:raise ValueError('Enveda file pin differs')
    return p

def run(root,input_root,test_path,is_rerun,sample_ids,base_audit,source_path,source_sha,expected_files,configuration):
    root=Path(root);final=root/'submission.csv';control_path=root/'submission_external_control.csv'
    shutil.copy2(final,control_path)
    report=dict(status='prepared',mode='hidden_full' if is_rerun else 'fast_static',configuration=configuration,
        configuration_sha256=canonical_sha(configuration),original_function_sha256=source_sha,
        control_sha256=sha(control_path),base_audit_csv_sha256=base_audit['csv_sha256'],library_matching_performed=False)
    try:
        validate_configuration(configuration);guard=old_helper(configuration)
        if base_audit.get('status')!='passed' or sha(control_path)!=base_audit['csv_sha256']:raise ValueError('Base control/audit mismatch')
        control=pd.read_csv(control_path,dtype=str,keep_default_na=False)
        if list(control.columns)!=['molecule_id','smiles'] or control.molecule_id.tolist()!=list(sample_ids) or not control.molecule_id.is_unique:raise ValueError('Control IDs/schema differ')
        if not all(guard.valid(raw) for raw in control.smiles):raise ValueError('Control has invalid/duplicate official identities')
        if sha(source_path)!=source_sha:raise ValueError('Original function source pin differs')
        report['libraries']=guard.resolve_sources(input_root,expected_files,test_path)
        ep=resolve_enveda(input_root,configuration)
        if ep:report['enveda_file']=dict(path=str(ep),bytes=ep.stat().st_size,sha256=configuration['enveda_file']['sha256'])
        if not is_rerun:
            report.update(status='fast_static_no_matching',rows=len(control),output_sha256=sha(final),
                checks=dict(control_bound=True,original_output_untouched=True,all_library_pins=True,exact_ids_order=True,official_identities_valid=True),details=[])
            write(root/'external_variants_runtime.json',report);return report
        report['library_matching_performed']=True
        matches,shared,ref_audit=execute_original(root,input_root,source_path,source_sha,configuration)
        report.update(ref_audit)
        old_report=read(root/'apex_extlib_audit.json')
        if old_report.get('molecules')!=len(control) or old_report.get('hits')!=sum(x['above_threshold'] for x in matches.values()):raise ValueError('Actual original match counts differ')
        if sha(root/'submission_pre_apex_extlib.csv')!=sha(control_path):raise ValueError('Original function consumed another control')
        original_proposal=pd.read_csv(final,dtype=str,keep_default_na=False)
        expected_proposal=[propose(raw,matches.get(str(mid))) for mid,raw in control.itertuples(index=False,name=None)]
        if original_proposal.molecule_id.tolist()!=control.molecule_id.tolist() or original_proposal.smiles.tolist()!=expected_proposal:raise ValueError('Observed A/B matches not consumed')
        original_proposal.to_csv(root/'submission_external_original_proposed.csv',index=False)
        e_matches={};e_audit=None
        if ep:
            e_module=load_module('_enveda_matching_1110',Path(__file__).with_name('enveda_matching_20261110.py'),configuration['e_helper_sha256'])
            e_matches,e_audit=e_module.score_enveda(shared['queries'],shared['lib_max'],ep,shared['calc_cosine'],
                expected_sha256=configuration['enveda_file']['sha256'],expected_bytes=configuration['enveda_file']['bytes'],min_cosine=.8,min_peaks=4)
        destination,details,ab_frame,proposal_frame=compose(control,matches,e_matches,configuration['e_policy'],guard)
        if not proposal_frame.equals(original_proposal):raise ValueError('Proposal reconstruction differs')
        ab_frame.to_csv(root/'submission_external_ab.csv',index=False)
        tmp=root/'submission_external_variant.tmp';destination.to_csv(tmp,index=False)
        if not pd.read_csv(tmp,dtype=str,keep_default_na=False).equals(destination):raise ValueError('Final CSV roundtrip differs')
        tmp.replace(final)
        report.update(status='applied',rows=len(control),actual_matches=matches,enveda_matches=e_matches,enveda_audit=e_audit,
            details=details,output_sha256=sha(final),queries_sha256=sha(test_path),original_report=old_report,
            ab_output_sha256=sha(root/'submission_external_ab.csv'),original_proposed_sha256=sha(root/'submission_external_original_proposed.csv'),
            changed_queries=sum(x['changed'] for x in details),changed_top1=sum(x['top1_changed'] for x in details),
            e_selected_queries=sum(x['e_selected'] for x in details),
            checks=dict(control_bound=sha(control_path)==base_audit['csv_sha256'],original_function_pin=sha(source_path)==source_sha,
                original_consumed_control=True,all_library_pins=True,selected_source_counts=True,disabled_sources_excluded=True,
                actual_ab_scores_consumed=True,exact_ids_order=destination.molecule_id.tolist()==list(sample_ids),
                official_identities_valid=all(guard.valid(x) for x in destination.smiles),actual_composition_consumed=True))
        write(root/'external_variants_runtime.json',report);return report
    except BaseException as error:
        report.update(status='failed_closed',error_type=type(error).__name__,error=str(error)[:400])
        write(root/'external_variants_runtime.json',report);final.unlink(missing_ok=True);raise

def audit(root,input_root,test_path,is_rerun,sample_ids,base_audit,source_path,source_sha,expected_files,configuration,branch,recipe_sha256):
    root=Path(root);guard=old_helper(configuration);validate_configuration(configuration)
    report=read(root/'external_variants_runtime.json')
    control=pd.read_csv(root/'submission_external_control.csv',dtype=str,keep_default_na=False)
    final=pd.read_csv(root/'submission.csv',dtype=str,keep_default_na=False)
    checks=dict(base_audit_passed=base_audit.get('status')=='passed',configuration_bound=report.get('configuration')==configuration and report.get('configuration_sha256')==canonical_sha(configuration),
        control_bound=sha(root/'submission_external_control.csv')==base_audit['csv_sha256']==report.get('control_sha256'),
        final_bound=sha(root/'submission.csv')==report.get('output_sha256'),source_function_pin=sha(source_path)==source_sha==report.get('original_function_sha256'),
        exact_ids_schema=list(final.columns)==['molecule_id','smiles'] and final.molecule_id.tolist()==list(sample_ids)==control.molecule_id.tolist() and final.molecule_id.is_unique,
        official_identities_valid=all(guard.valid(x) for x in final.smiles),library_file_pins=guard.resolve_sources(input_root,expected_files,test_path)==report.get('libraries'),
        runtime_checks=bool(report.get('checks')) and all(v is True for v in report['checks'].values()))
    ep=resolve_enveda(input_root,configuration)
    if ep:checks['enveda_file_pin']=report.get('enveda_file')==dict(path=str(ep),bytes=ep.stat().st_size,sha256=configuration['enveda_file']['sha256'])
    if is_rerun:
        selected=set(configuration['sources'])-{'E'};counts=report.get('selected_reference_counts',{})
        checks['actual_matching']=report.get('status')=='applied' and report.get('mode')=='hidden_full' and report.get('library_matching_performed') is True
        checks['actual_reference_counts']=report.get('seen_reference_counts')==REFERENCE_COUNTS and all(counts.get(x,0)==REFERENCE_COUNTS[x] for x in selected) and all(counts.get(x,0)==0 for x in {'A','B'}-selected)
        checks['actual_match_sources']=all(m.get('source') in selected or m.get('smiles') is None for m in report['actual_matches'].values())
        checks['trusted_bprec_scope']=report.get('bprec_corrected_count')==(1281 if configuration['trusted_bprec'] else 0) and len(report.get('bprec_corrected_rows',[]))==report.get('bprec_corrected_count')
        checks['queries_bound']=sha(test_path)==report.get('queries_sha256')
        destination,details,ab_frame,proposal_frame=compose(control,report['actual_matches'],report['enveda_matches'],configuration['e_policy'],guard)
        checks['actual_scores_consumed']=destination.equals(final) and details==report['details']
        checks['ab_intermediate_bound']=ab_frame.equals(pd.read_csv(root/'submission_external_ab.csv',dtype=str,keep_default_na=False)) and sha(root/'submission_external_ab.csv')==report['ab_output_sha256']
        checks['original_proposals_bound']=proposal_frame.equals(pd.read_csv(root/'submission_external_original_proposed.csv',dtype=str,keep_default_na=False)) and sha(root/'submission_external_original_proposed.csv')==report['original_proposed_sha256']
        checks['original_input_bound']=sha(root/'submission_pre_apex_extlib.csv')==sha(root/'submission_external_control.csv')
        checks['original_match_counts']=report['original_report']['hits']==sum(x['above_threshold'] for x in report['actual_matches'].values())
        if ep:
            ea=report.get('enveda_audit') or {}
            checks['enveda_actual_scoring']=ea.get('status')=='passed' and ea.get('sha256')==configuration['enveda_file']['sha256']
            checks['enveda_full_source_bound']=ea.get('bytes')==configuration['enveda_file']['bytes'] and ea.get('source_ref')==configuration['enveda_file']['ref'] and ea.get('source_version')==configuration['enveda_file']['version'] and ea.get('source_rows_total')==730252
            qp=ea.get('query_preparation',{});eligible=qp.get('eligible_spectra')
            checks['enveda_explicit_scan_scope']=(type(eligible) is int and eligible>=0 and
                ((eligible==0 and ea.get('scan_performed') is False and ea.get('rows_scanned')==0 and ea.get('no_eligible_queries') is True)
                 or (eligible>0 and ea.get('scan_performed') is True and ea.get('rows_scanned')==730252 and ea.get('no_eligible_queries') is False)))
            expected_hits={x['molecule_id']:x for x in ea.get('query_best',[]) if x.get('above_threshold') is True}
            checks['enveda_actual_hit_receipts']=expected_hits==report['enveda_matches'] and ea.get('returned_hits')==len(expected_hits)
            rules=ea.get('rules',{})
            checks['enveda_same_adduct_recipe']=rules.get('exact_adduct') is True and rules.get('exact_mode') is True and rules.get('min_cosine')==.80 and rules.get('min_matched_peaks')==4
        else:checks['enveda_disabled']=report.get('enveda_audit') is None and report.get('enveda_matches')=={}
    else:checks['fast_no_matching']=report.get('status')=='fast_static_no_matching' and report.get('library_matching_performed') is False and final.equals(control)
    if not all(checks.values()):raise ValueError('External variants observer rejected: '+repr(checks))
    result=dict(status='passed',branch=branch,recipe_sha256=recipe_sha256,mode='hidden_full' if is_rerun else 'fast_static',checks=checks,
        csv_sha256=sha(root/'submission.csv'),control_sha256=sha(root/'submission_external_control.csv'),runtime_report_sha256=sha(root/'external_variants_runtime.json'),
        configuration_sha256=canonical_sha(configuration),sources=configuration['sources'],e_policy=configuration['e_policy'],trusted_bprec=configuration['trusted_bprec'],
        changed_top1=report.get('changed_top1',0),e_selected_queries=report.get('e_selected_queries',0),bprec_corrected_count=report.get('bprec_corrected_count',0))
    write(root/'external_variants_audit.json',result);return result
