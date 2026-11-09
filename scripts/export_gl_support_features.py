"""Export frozen EXP003-A candidate support features; no labels, model or ranking write."""
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
import argparse
import hashlib
import json
import math
import os
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
DEFAULT_BASE=ROOT/'runs/exp003_gl_trace_full_20261106'
DESIGN=ROOT/'reports/EXP003_FEATURE_DESIGN_2026-11-06.md'
RUNNER_SHA='5c4f74313ac54263d05d987c39d012d81ec57c5f35e1095ecd49a5bcb6440fca'
EPS=1e-9


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def inside(path):
    path=Path(path).resolve()
    if path==ROOT or not path.is_relative_to(ROOT):raise ValueError('All paths must stay inside the D: workspace')
    return path
def finite(value):return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)
def unit_key(value):return ('missing','') if value is None else ('raw',str(value))
def metadata_key(e):
    return (e.get('adduct'),e.get('instrument_token'),unit_key(e.get('ce_units')),
        e.get('prediction_mode'),e.get('ce_bucket'))
def winners(values):
    valid={key:value for key,value in values.items() if finite(value)}
    if not valid:return []
    best=max(valid.values())
    return sorted(key for key,value in valid.items() if abs(value-best)<=EPS)


def derive(items,identities,coverage,scores,formula_of):
    """Pure feature computation; formula_of is candidate-only and injectable for tests."""
    import numpy as np
    by_mid={str(item['mid']):item for item in items}
    if len(by_mid)!=len(items):raise ValueError('Repeated input query')
    cov={};observations=defaultdict(list)
    for event in coverage:
        mid=str(event['mid']);index=event['spectrum_index'];key=(mid,index)
        if mid not in by_mid or key in cov or not isinstance(index,int) or index<0:
            raise ValueError('Unknown or repeated spectrum coverage event')
        raw=by_mid[mid].get('spectra',[])
        if index>=len(raw):raise ValueError('Unknown spectrum index')
        payload={name:raw[index].get(name) for name in ('mz','it','prec','adduct','mode')}
        digest=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        if digest!=event['spectrum_content_sha256']:raise ValueError('Spectrum content changed')
        cov[key]=event
        if event.get('covered'):observations[mid].append(event)
    expected_coverage={(mid,index) for mid,item in by_mid.items() for index in range(len(item.get('spectra',[])))}
    if set(cov)!=expected_coverage:raise ValueError('Incomplete spectrum coverage trace')
    matrix={}
    for event in scores:
        mid=str(event['mid']);candidate=event['candidate_smiles'];index=event['spectrum_index'];key=(mid,index,candidate)
        if (mid,index) not in cov or not cov[(mid,index)].get('covered') or key in matrix:
            raise ValueError('Unknown or repeated candidate-spectrum score')
        if candidate not in by_mid[mid]['cands'] or event.get('candidate_official_identity')!=identities.get(candidate):
            raise ValueError('Candidate identity trace mismatch')
        if event.get('spectrum_content_sha256')!=cov[(mid,index)]['spectrum_content_sha256']:
            raise ValueError('Score/coverage spectrum mismatch')
        for name in ('adduct','instrument_token','ce_units','prediction_mode','ce_bucket'):
            if event.get(name)!=cov[(mid,index)].get(name):raise ValueError('Score/coverage metadata mismatch')
        matrix[key]=event
    expected={(mid,e['spectrum_index'],candidate) for mid,item in by_mid.items()
        for e in observations[mid] for candidate in set(item['cands'])}
    if set(matrix)!=expected:raise ValueError('Incomplete candidate-spectrum cross product')
    rows=[];groups=[];reasons=Counter();counts=Counter();conflicts=Counter()
    for mid,item in by_mid.items():
        candidates=item['cands'];formula_groups=defaultdict(list)
        for position,candidate in enumerate(candidates,1):formula_groups[formula_of(candidate)].append((position,candidate))
        clusters=defaultdict(list)
        for event in observations[mid]:clusters[event['spectrum_content_sha256']].append(event)
        counts['queries']+=1;counts['candidate_rows']+=len(candidates)
        counts['covered_spectra']+=len(observations[mid]);counts['unique_exact_spectrum_clusters']+=len(clusters)
        counts['duplicate_spectrum_aliases']+=sum(len(events)-1 for events in clusters.values())
        query_eligible=False
        for formula,members in formula_groups.items():
            counts['formula_groups']+=1
            order=[candidate for _,candidate in members];keys=[identities.get(candidate) for candidate in order]
            k=len(order);reason=None
            if formula is None or formula=='':reason='missing_candidate_formula'
            elif any(not key for key in keys):reason='missing_official_identity'
            elif len(set(keys))<2:reason='fewer_than_two_unique_identities'
            elif len(set(keys))!=k:reason='duplicate_official_identity'
            if len(set(key for key in keys if key))>=2:counts['groups_at_least_two_unique_identities']+=1
            original={}
            for candidate in order:
                values=[matrix[(mid,e['spectrum_index'],candidate)]['score'] for e in observations[mid]
                    if matrix[(mid,e['spectrum_index'],candidate)].get('status')=='scored'
                    and finite(matrix[(mid,e['spectrum_index'],candidate)].get('score'))]
                original[candidate]=float(np.mean(values)) if values else None
            strata=defaultdict(lambda:defaultdict(list));excluded=Counter()
            if reason is None:
                for aliases in clusters.values():
                    aliases=sorted(aliases,key=lambda e:e['spectrum_index']);event=aliases[0]
                    if len({metadata_key(e) for e in aliases})!=1:
                        excluded['duplicate_metadata_conflict']+=1;continue
                    if event.get('adduct')!='[M+H]+':excluded['outside_hplus_scope']+=1;continue
                    if event.get('prediction_mode')!='single_ce' or not finite(event.get('ce_bucket')):
                        excluded['merged_or_unknown_ce']+=1;continue
                    values={};usable=True;alias_conflict=False
                    for candidate in order:
                        evidence=[matrix[(mid,e['spectrum_index'],candidate)] for e in aliases]
                        if any(e.get('status')!='scored' or not finite(e.get('score')) for e in evidence):usable=False;break
                        if any(e['score']!=evidence[0]['score'] for e in evidence):alias_conflict=True;break
                        values[candidate]=evidence[0]['score']
                    if alias_conflict:excluded['duplicate_score_conflict']+=1;continue
                    if not usable:excluded['incomplete_common_observation']+=1;continue
                    layer=(event['adduct'],event['instrument_token'],unit_key(event.get('ce_units')))
                    strata[layer][event['ce_bucket']].append(values)
            eligible_layers=[(layer,bins) for layer,bins in strata.items() if len(bins)>=2]
            selected=None;support={};balanced={};chosen_bins={}
            if reason is None and not eligible_layers:reason='fewer_than_two_common_finite_ce_groups'
            if reason is None:
                selected,chosen_bins=min(eligible_layers,key=lambda p:(-len(p[1]),-sum(len(v) for v in p[1].values()),p[0]))
                ce_values={bucket:{candidate:sum(v[candidate] for v in values)/len(values) for candidate in order}
                    for bucket,values in chosen_bins.items()}
                for candidate in order:
                    votes=[]
                    for values in ce_values.values():
                        for other in order:
                            if other==candidate:continue
                            delta=values[candidate]-values[other]
                            votes.append(1. if delta>EPS else 0. if delta<-EPS else .5)
                    support[candidate]=sum(votes)/len(votes)
                    balanced[candidate]=sum(values[candidate] for values in ce_values.values())/len(ce_values)
                counts['eligible_formula_groups']+=1;query_eligible=True
                if max(support.values())-min(support.values())>EPS:counts['nonconstant_support_groups']+=1
                a,b,c=set(winners(original)),set(winners(balanced)),set(winners(support))
                for label,mean_winners in [('original_mean',a),('ce_balanced_mean',b)]:
                    conflicts[label+'_winner_sets_differ']+=int(mean_winners!=c)
                    conflicts[label+'_winner_sets_disjoint']+=int(not mean_winners&c)
                    conflicts[label+'_unique_winner_excluded']+=int(len(mean_winners)==1 and not mean_winners&c)
            if reason:reasons[reason]+=1
            group=dict(mid=mid,formula=formula,formula_source='candidate_rdkit_formula',candidates=k,
                unique_official_identities=len(set(key for key in keys if key)),eligible=reason is None,
                ineligible_reason=reason,selected_stratum=selected,ce_groups=len(chosen_bins),
                selected_ce_buckets=sorted(chosen_bins),selected_unique_observations=sum(len(v) for v in chosen_bins.values()),
                excluded_spectrum_clusters=dict(excluded),other_eligible_strata=max(0,len(eligible_layers)-1),
                original_mean_winners=winners(original),ce_balanced_mean_winners=winners(balanced),support_winners=winners(support))
            groups.append(group)
            for position,candidate in members:
                rate=support.get(candidate)
                rows.append(dict(mid=mid,candidate_position=position,candidate_smiles=candidate,
                    candidate_official_identity=identities.get(candidate),formula=formula,formula_source='candidate_rdkit_formula',
                    original_gl_mean=original[candidate],ce_balanced_mean=balanced.get(candidate),
                    candidate_support_rate=rate,candidate_support_centered=None if rate is None else 2*rate-1,
                    eligible=reason is None,ineligible_reason=reason,candidates_in_formula=k,
                    ce_groups=len(chosen_bins),selected_stratum=selected))
        if query_eligible:counts['queries_with_eligible_groups']+=1
    return rows,dict(counts=dict(counts),ineligible_group_reasons=dict(reasons),winner_conflicts=dict(conflicts),groups=groups,
        strict_gate_status='strict_gate_not_audited',rankings_modified=False,truth_read=False,
        formula_note='Candidate-only RDKit formula; original stage formula/rank sidecar required before any ranking intervention.')


def export(base,verification,output):
    base,verification,output=map(inside,(base,verification,output))
    if output.exists():raise FileExistsError('Feature outputs must use a fresh directory')
    source,identity_path,trace=base/'input.json',base/'official_identities.json',base/'trace/per_spectrum.jsonl'
    gate=read(verification)
    if (gate.get('status')!='passed' or not isinstance(gate.get('checks'),dict) or not gate['checks']
            or not all(v is True for v in gate['checks'].values())):
        raise ValueError('Independent full trace verification must pass before exporting')
    for name,path in [('input_sha256',source),('trace_sha256',trace),('identity_sidecar_sha256',identity_path)]:
        if gate.get(name)!=sha(path):raise ValueError('Verified input/trace/identity SHA changed')
    items,identities=read(source),read(identity_path)
    starts=[];ends=[];coverage=[];scores=[]
    with trace.open(encoding='utf-8') as stream:
        for line in stream:
            if not line.strip():continue
            event=json.loads(line);kind=event.get('event')
            if kind=='run_start':starts.append(event)
            elif kind=='run_end':ends.append(event)
            elif kind=='spectrum_coverage':coverage.append(event)
            elif kind=='candidate_spectrum_score':scores.append(event)
            else:raise ValueError('Unknown trace event')
    if (len(starts)!=1 or len(ends)!=1 or ends[0].get('status')!='complete'
            or starts[0].get('source_sha256')!=RUNNER_SHA or starts[0].get('input_sha256')!=sha(source)
            or starts[0].get('identity_map_sha256')!=sha(identity_path)):
        raise ValueError('Trace header/end binding mismatch')
    from validation import metric
    from rdkit import Chem
    from rdkit.Chem import rdMolDescriptors
    if metric.assert_official_rdkit()!='2026.03.3':raise ValueError('Official identity RDKit required')
    candidates={candidate for item in items for candidate in item['cands']}
    if any(not identities.get(candidate) or metric.identity(candidate)!=identities.get(candidate) for candidate in candidates):
        raise ValueError('Official candidate identity sidecar is not reproducible')
    formulas={candidate:rdMolDescriptors.CalcMolFormula(Chem.MolFromSmiles(candidate)) for candidate in candidates}
    rows,audit=derive(items,identities,coverage,scores,formulas.get)
    # Require the reconstructed original means to equal the actual runner scalar output.
    standard=read(base/'trace/gl_out.json')
    if any(row['original_gl_mean']!=standard[row['mid']][row['candidate_smiles']] for row in rows):
        raise ValueError('Feature observer did not reconstruct original GL means exactly')
    hashes=dict(input_sha256=sha(source),trace_sha256=sha(trace),identity_sidecar_sha256=sha(identity_path),
        verification_sha256=sha(verification),design_sha256=sha(DESIGN),exporter_sha256=sha(Path(__file__)))
    audit.update(status='exported_no_effect_evaluation',created_at_utc=datetime.now(timezone.utc).isoformat(),
        feature='EXP003_A_pairwise_CE_support_v1',epsilon=EPS,rdkit='2026.03.3',**hashes,
        model_executed=False,original_means_exact=True,performance_evaluated=False,submission_created=False)
    output.mkdir(parents=True,exist_ok=False)
    with (output/'candidate_support_features.jsonl').open('x',encoding='utf-8') as stream:
        for row in rows:stream.write(json.dumps(row,allow_nan=False,separators=(',',':'))+'\n')
    (output/'support_information_audit.json').write_text(json.dumps(audit,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    return {key:audit[key] for key in ('status','feature','counts','ineligible_group_reasons','winner_conflicts','strict_gate_status')}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base',type=Path,default=DEFAULT_BASE)
    parser.add_argument('--verification',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--export',action='store_true')
    args=parser.parse_args()
    base=inside(args.base);verification=inside(args.verification or base/'full_trace_verification.json')
    output=inside(args.output or base/'support_features_v1')
    if not args.export:
        print(json.dumps(dict(status='plan_only',model_executed=False,truth_read=False,
            input_directory=str(base),verification=str(verification),output=str(output),export_requires='--export'),indent=2));return 0
    try:
        result=export(base,verification,output);print(json.dumps(result,indent=2));return 0
    except Exception as error:
        print(json.dumps(dict(status='export_stopped',error_type=type(error).__name__)));return 1


if __name__=='__main__':
    sys.dont_write_bytecode=True
    for name in ('TEMP','TMP','PYTHONPYCACHEPREFIX'):
        path=ROOT/('.cache/pycache-win' if name=='PYTHONPYCACHEPREFIX' else '.cache/tmp')
        path.mkdir(parents=True,exist_ok=True);os.environ[name]=str(path)
    raise SystemExit(main())
