"""Evaluate all original100 FIORA development queries AFTER complete inference.

Predeclared primary check:92 queries outside the original8 pilot query IDs.
The original8 are reproduction only; all100 remain the full-panel summary.

This script is not a model runner. The prediction-success gate binds all source,
candidate and checkpoint bytes before it opens any evaluation truth metadata.
No threshold, fusion weight, checkpoint or candidate is selected by evaluation.
"""
from __future__ import annotations
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
import argparse
import csv
import hashlib
import json
import math
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'runs/fiora_candidate_validation_20261116'
OUTPUT=ROOT/'reports/new_paradigm_20261116/candidate_validation100/evaluation'
EXPECTED_INFERENCE_STATUS='completed_dual_checkpoint_candidate_spectrum_scoring'
EXPECTED_FREEZE_STATUS='candidates_and_query_inputs_frozen_before_truth_coverage_or_model_scores'
EXPECTED_SELECTION_SHA='2b4ecd92fbf0f175b8533c1678bf693831e9ef1f75bb48084cf32f0169c2213d'
EXPECTED_FREEZE_SHA='4f4fedc2660096ff8de6e4bd3e1099c421c61189304614d6fb8b1fbfc29016cf'
EXPECTED_SCORER_SHA='312c86fc40f2a71fa9c231438e1f747023efe7923adf0bce2946c28ae3bc4853'
EXPECTED_PREPARE_SHA='f1db3f6bba57c8ff414da332e3d412629811a577820a01a2688e9bde3bac5274'
EXPECTED_STEP0_SHA='38d3208f4c78a4db935b8d4b58cae643def77b050488d5d7191cf845af114048'
EXPECTED_STEP500_SHA='9c899faa1c45d9a0c25588f99186f34112b25eafe3f6d955a3da34c267996252'
EXPECTED_PARAMS_SHA='1f189efe9fb64f43406bce409b825870655f8b83765c5ee77d3e208e2cbc2418'
EXPECTED_SOURCE_COMMIT='e19ef82c9a6cb9dbac92bce23e914008f1aeb44e'
EXPECTED_QUERY_COUNT=100
ORIGINAL_PILOT_QUERIES=ROOT/'runs/fiora_candidate_pilot_20261115/queries.json'
ORIGINAL_PILOT_QUERIES_SHA='d4a7a4de2d7cec6e84d70e963fdced73b76e7a67a0d2f33393e4aeb7e1e84098'
PRIMARY_GROUP='remaining92_not_in_pilot8'
BOOTSTRAP_SEED=20261116
BOOTSTRAP_RESAMPLES=10000
RANK_POLICY=dict(score_direction='descending',tie_break='ascending original candidate_index',
                 identity='RDKit2026.03.3 remove stereo then canonical tautomer then InChIKey14',
                 duplicate_identity_rule='keep first after stable descending score ordering',
                  invalid_identity_rule='exclude before constructing submitted list; report excluded row indices',
                 maximum_submitted_candidates=25,missing_or_outside_top25_reciprocal_rank=0.,
                  missing_prediction_rule='refuse entire evaluation before opening truth; never impute zero or drop a query',
                 candidate_cap_changed=False,threshold_or_fusion_selection=False)

def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def save(path,value):Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def stamp():return datetime.now(timezone.utc).isoformat()
def workspace(path):
    path=Path(path).resolve()
    if path==ROOT or not path.is_relative_to(ROOT):raise ValueError('D workspace path required')
    return path
def source_path(value):
    value=Path(value)
    return workspace(value if value.is_absolute() else ROOT/value)
def finite_score(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(float(value))
def query_key(row):return str(row['molecule_id']),str(row['spectrum_id'])
def candidate_key(row):return (*query_key(row),int(row['candidate_index']))
def require(condition,message):
    if not condition:raise ValueError(message)
def jsonl(path):
    rows=[]
    with Path(path).open(encoding='utf-8') as h:
        for n,line in enumerate(h,1):
            if line.strip():
                try:rows.append(json.loads(line))
                except json.JSONDecodeError as error:raise ValueError(f'Invalid score JSONL line {n}') from error
    return rows

def _declared_plan(queries):
    """Group only by the original pilot query IDs, never by any new score."""
    require(sha(ORIGINAL_PILOT_QUERIES)==ORIGINAL_PILOT_QUERIES_SHA,'Original pilot query input changed')
    old_queries=read(ORIGINAL_PILOT_QUERIES)
    pilot_ids={str(row['molecule_id']) for row in old_queries}
    current_ids={str(row['molecule_id']) for row in queries}
    require(len(old_queries)==len(pilot_ids)==8,'Original pilot must supply exactly eight distinct molecule IDs')
    require(len(queries)==len(current_ids)==EXPECTED_QUERY_COUNT,'Full original100 cohort required for predeclared groups')
    require(pilot_ids<=current_ids,'Original pilot molecule IDs missing from original100 cohort')
    remainder=current_ids-pilot_ids
    require(len(remainder)==92,'Predeclared primary group must contain92 queries')
    groups={'all_original100':sorted(current_ids),'pilot8_reproduction_only':sorted(pilot_ids),
            PRIMARY_GROUP:sorted(remainder)}
    return dict(status='predeclared_groups_bound_before_truth_and_before_new_score_rows_opened',
        primary_group=PRIMARY_GROUP,pilot_group_role='reproduction_only',
        grouping_rule='molecule_id membership in the SHA-pinned original pilot queries.json; no score-based selection',
        groups=groups,group_denominators={name:len(ids) for name,ids in groups.items()},
        original_pilot_queries_path=str(ORIGINAL_PILOT_QUERIES),original_pilot_queries_sha256=ORIGINAL_PILOT_QUERIES_SHA,
        original_development_denominator=EXPECTED_QUERY_COUNT,retain_queries_without_true_fragment_supervision=True,
        bootstrap=dict(seed=BOOTSTRAP_SEED,resamples=BOOTSTRAP_RESAMPLES,confidence_level=.95,
                       method='paired query percentile bootstrap, PCG64, two-sided linear quantiles',
                       unit='original query; resample paired step500-minus-step0 reciprocal-rank deltas',
                       tuning_or_selection_performed=False),
        independent_clean_holdout=False,source_script_sha256=sha(__file__))

def _paired_bootstrap(reports):
    """Descriptive paired-query CI with fixed parameters, never a selector."""
    import numpy as np
    delta=np.asarray([row['delta_rr25'] for row in reports],dtype=np.float64)
    require(delta.ndim==1 and len(delta)>0 and np.isfinite(delta).all(),'Invalid paired delta denominator')
    rng=np.random.Generator(np.random.PCG64(BOOTSTRAP_SEED))
    indices=rng.integers(0,len(delta),size=(BOOTSTRAP_RESAMPLES,len(delta)))
    values=delta[indices].mean(axis=1)
    low,high=np.quantile(values,[.025,.975],method='linear')
    return dict(observed_delta=float(delta.mean()),lower95=float(low),upper95=float(high),
                seed=BOOTSTRAP_SEED,resamples=BOOTSTRAP_RESAMPLES,query_denominator=len(delta),
                confidence_level=.95,method='paired query percentile bootstrap with replacement',
                generator='PCG64',quantile_method='linear',paired=True,
                boundary='Descriptive variability within this fixed existing-development query panel; not an independent-holdout or Kaggle confidence interval.')

def _group_summary(reports,ids,role):
    wanted=set(ids)
    subset=[row for row in reports if row['molecule_id'] in wanted]
    require(len(subset)==len(wanted) and {row['molecule_id'] for row in subset}==wanted,'Group query denominator changed')
    n=len(subset)
    metrics={step:dict(queries=n,MRR_at_25=sum(row[step]['mrr25_contribution'] for row in subset)/n,
        top1_accuracy=sum(row[step]['top1'] for row in subset)/n,
        top1_count=sum(row[step]['top1'] for row in subset),
        top25_recall=sum(row[step]['top25_hit'] for row in subset)/n,
        top25_count=sum(row[step]['top25_hit'] for row in subset)) for step in ('step0','step500')}
    return dict(role=role,query_denominator=n,molecule_ids=sorted(wanted),checkpoint_metrics=metrics,
        delta_MRR_at_25=metrics['step500']['MRR_at_25']-metrics['step0']['MRR_at_25'],
        paired_delta_MRR_at_25_bootstrap95=_paired_bootstrap(subset),
        paired_outcomes=dict(Counter(row['outcome'] for row in subset)),
        full_window_candidate_recall=sum(row['full_window_true_identity_present'] for row in subset)/n,
        capped_candidate_recall=sum(row['capped_true_identity_present'] for row in subset)/n,
        cap_removed_all_truth_queries=sum(row['cap_removed_all_truth'] for row in subset),
        truth_available_for_ranking_queries=sum(row['capped_true_identity_present'] for row in subset),
        empty_candidate_window_queries=sum(row['capped_candidates']==0 for row in subset))

def _bind_inference_success(data,inference,out):
    """No evaluation truth/coverage file is opened anywhere in this gate."""
    proof_path=inference/'verification.json'
    require(proof_path.is_file(),'Inference verification missing; evaluation truth remains unopened')
    proof=read(proof_path)
    require(proof.get('status')==EXPECTED_INFERENCE_STATUS,'Inference not complete; evaluation truth remains unopened')
    require(proof.get('all_candidates_scored') is True and proof.get('all_scores_finite') is True,
            'Incomplete/nonfinite predictions; evaluation truth remains unopened')
    for field in ('labels_read','training_performed','ranking_computed'):
        require(proof.get(field) is False,'Unexpected inference behavior: '+field)
    require(proof.get('same_candidate_set_for_both_models') is True and proof.get('candidate_rows_preserved') is True,
            'Inference did not preserve the complete common candidate set')
    require(proof.get('all_original_dev_queries_preserved') is True and
            proof.get('original_dev_structure_denominator')==EXPECTED_QUERY_COUNT,'Inference filtered original development queries')
    require(proof.get('script_sha256')==EXPECTED_SCORER_SHA and
            proof.get('executed_score_script_sha256')==EXPECTED_SCORER_SHA,'Actual inference scorer digest differs')
    require(proof.get('source_commit')==EXPECTED_SOURCE_COMMIT,'Inference native source commit differs')
    require(proof.get('step0_state_sha256')==EXPECTED_STEP0_SHA and
            proof.get('step500_checkpoint_sha256')==EXPECTED_STEP500_SHA and
            proof.get('final_checkpoint_sha256')==EXPECTED_STEP500_SHA and
            proof.get('model_params_sha256')==EXPECTED_PARAMS_SHA,'Fixed model/params fingerprints differ')
    scorer_path=ROOT/'scripts/score_fiora_candidate_validation_20261116.py'
    require(sha(scorer_path)==EXPECTED_SCORER_SHA,'Frozen executed inference script changed')
    freeze_path=data/'candidate_freeze.json';freeze=read(freeze_path)
    require(sha(freeze_path)==EXPECTED_FREEZE_SHA,'Predeclared candidate freeze changed')
    require(freeze.get('status')==EXPECTED_FREEZE_STATUS,'Unexpected frozen candidate/input contract')
    require(proof.get('candidate_freeze_sha256')==sha(freeze_path),'Prediction candidate manifest differs')
    require(freeze.get('queries')==EXPECTED_QUERY_COUNT,'All original100 development queries required')
    configuration=freeze.get('configuration',{})
    for name in ('formula_filter','truth_candidate_injection','candidate_identity_deduplication','model_scores_used'):
        require(configuration.get(name) is False,'Frozen candidate selection policy changed: '+name)
    require(configuration.get('selected_from_cache_ready_only') is False and
            configuration.get('original_dev_structure_denominator')==EXPECTED_QUERY_COUNT and
            configuration.get('query_selection')=='all original development rows in original index order',
            'Full original development panel was filtered or replaced')
    require(configuration.get('cap')==128,'Predeclared mass-only cap128 changed')
    require(configuration.get('initial_ppm')==10. and configuration.get('empty_window_fallback_ppm')==30.,'Candidate mass windows changed')
    pins={str(freeze_path):sha(freeze_path),str(proof_path):sha(proof_path),
          str(scorer_path):EXPECTED_SCORER_SHA,str(Path(__file__).resolve()):sha(__file__)}
    for filename,field in [('queries.json','queries_sha256'),('candidates.json','candidates_sha256')]:
        path=data/filename
        require(filename in freeze['files'],'Input not in frozen candidate manifest')
        digest=sha(path)
        require(digest==freeze['files'][filename]['sha256']==proof.get(field),'Prediction/frozen input SHA mismatch: '+filename)
        pins[str(path)]=digest
    windows_path=data/'candidate_windows.json'
    require(sha(windows_path)==freeze['files']['candidate_windows.json']['sha256'],'Frozen candidate windows changed')
    pins[str(windows_path)]=sha(windows_path)
    prep_path=ROOT/'scripts/prepare_fiora_candidate_validation_20261116.py'
    require(sha(prep_path)==freeze['source_script_sha256']==EXPECTED_PREPARE_SHA,'Actual candidate preparation source changed')
    pins[str(prep_path)]=sha(prep_path)
    executed_prep_path=data/'executed_prepare_source.py'
    require(sha(executed_prep_path)==freeze['executed_source_sha256']==EXPECTED_PREPARE_SHA,
            'Archived actual candidate preparation source differs')
    pins[str(executed_prep_path)]=EXPECTED_PREPARE_SHA
    pool_path=source_path(freeze['pool_path'])
    require(sha(pool_path)==freeze['pool_sha256'],'Frozen candidate source pool changed')
    pins[str(pool_path)]=sha(pool_path)
    sources=proof.get('source_pins')
    require(isinstance(sources,dict) and sources,'Explicit inference source pins required')
    configuration_path=inference/'configuration.json'
    source_bindings_path=inference/'source_bindings_before_predictions.json'
    require(sha(configuration_path)==proof.get('configuration_sha256'),'Pre-inference scoring configuration changed')
    require(sha(source_bindings_path)==proof.get('source_bindings_sha256'),'Pre-inference source bindings changed')
    require(read(source_bindings_path)==sources,'Inference before/after source bindings differ')
    config=read(configuration_path)
    require(config.get('status')=='frozen_before_candidate_inference' and
            config.get('models_compared')==['step0','step500'] and
            config.get('shared_original_candidate_set') is True,'Frozen dual-checkpoint configuration differs')
    require(config.get('queries')==EXPECTED_QUERY_COUNT and config.get('candidate_rows')==freeze['candidate_rows'] and
            config.get('candidate_freeze_sha256')==EXPECTED_FREEZE_SHA,'Inference configuration cohort differs')
    require(config.get('all_original_dev_queries_preserved') is True and config.get('cache_ready_filter_applied') is False and
            config.get('original_dev_structure_denominator')==EXPECTED_QUERY_COUNT,'Inference configuration filtered original development queries')
    require(config.get('inference_files_sha256')=={name:freeze['files'][name]['sha256']
            for name in ('queries.json','candidates.json')},'Inference configuration input binding differs')
    for field in ('labels_read','training_performed','loss_computed','ranking_computed','fit_or_score_coefficient_selection'):
        require(config.get(field) is False,'Scoring configuration allowed unexpected behavior: '+field)
    require(config.get('model_params_sha256')==EXPECTED_PARAMS_SHA and
            config.get('step0_state_sha256')==EXPECTED_STEP0_SHA and
            config.get('step500_checkpoint_sha256')==EXPECTED_STEP500_SHA,'Configuration checkpoint/params binding differs')
    require(config.get('score_direction')=='larger_is_better' and
            config.get('matching_tolerance_da')==.01 and
            config.get('predicted_intensity_threshold_strict_greater_than')==.001,
            'Predeclared spectral score rule changed')
    for path in (configuration_path,source_bindings_path):pins[str(path)]=sha(path)
    resolved_sources={}
    for path_string,pin in sources.items():
        path=source_path(path_string)
        digest=pin.get('sha256') if isinstance(pin,dict) else pin
        require(isinstance(digest,str) and sha(path)==digest,'Actual inference source changed: '+str(path))
        pins[str(path)]=digest
        resolved_sources[path]=digest
    require(resolved_sources.get(scorer_path)==EXPECTED_SCORER_SHA,'Executed scorer missing from inference source pins')
    params_path=ROOT/'runs/fiora_tims_model_20261115/fiora_OS_tims_migrated_params.json'
    require(resolved_sources.get(params_path)==EXPECTED_PARAMS_SHA,'Pinned model parameters missing from source bindings')
    executed_scorer_path=inference/'executed_score_script.py'
    require(sha(executed_scorer_path)==EXPECTED_SCORER_SHA,'Archived executed scorer bytes differ')
    pins[str(executed_scorer_path)]=EXPECTED_SCORER_SHA
    for path_field,pin_field in [('step0_state_path','step0_state_sha256'),('final_checkpoint_path','final_checkpoint_sha256')]:
        require(path_field in proof,'Actual model path missing: '+path_field)
        path=source_path(proof[path_field]);pin=proof.get(pin_field)
        require(isinstance(pin,str) and sha(path)==pin,'Prediction checkpoint differs: '+path_field)
        require(resolved_sources.get(path)==pin,'Compared checkpoint missing from inference source bindings')
        pins[str(path)]=pin
    score_path=inference/'candidate_scores.jsonl'
    require(score_path.is_file() and sha(score_path)==proof.get('scores_sha256'),'Prediction score file differs')
    pins[str(score_path)]=sha(score_path)
    queries=read(data/'queries.json')
    plan=_declared_plan(queries)
    pins[str(ORIGINAL_PILOT_QUERIES)]=ORIGINAL_PILOT_QUERIES_SHA
    save(out/'evaluation_plan.json',plan)
    pins[str(out/'evaluation_plan.json')]=sha(out/'evaluation_plan.json')
    candidates=read(data/'candidates.json');windows=read(windows_path);scores=jsonl(score_path)
    qkeys=[query_key(row) for row in queries]
    require(len(qkeys)==EXPECTED_QUERY_COUNT and len(set(qkeys))==EXPECTED_QUERY_COUNT and len({x[0] for x in qkeys})==EXPECTED_QUERY_COUNT,'Query cohort is not the original100 distinct molecules')
    require(len(windows)==EXPECTED_QUERY_COUNT and {query_key(row) for row in windows}==set(qkeys),'Candidate windows do not cover all100 queries')
    ck=[candidate_key(row) for row in candidates];sk=[candidate_key(row) for row in scores]
    require(len(ck)==len(set(ck)),'Duplicate frozen candidate row key')
    require(len(sk)==len(set(sk)) and sk==ck,'Prediction row order/set is not exactly frozen candidates')
    require(len(candidates)==freeze['candidate_rows']==proof.get('expected_candidates')==proof.get('processed_candidates'),'Incomplete prediction candidate count')
    require(proof.get('query_count')==EXPECTED_QUERY_COUNT and proof.get('expected_queries')==EXPECTED_QUERY_COUNT,'Inference query count is not100')
    missing=defaultdict(Counter)
    for candidate,score in zip(candidates,scores):
        # All original candidate payload fields must be byte-semantically equal;
        # scores are allowed to add fields, never mutate the candidate evidence.
        require(all(key in score and score[key]==value for key,value in candidate.items()),'Prediction changed an original candidate field')
        for step in ('step0','step500'):
            if score.get(step+'_status')!='scored' or not finite_score(score.get(step+'_score')):
                missing[query_key(candidate)][step]+=1
    by_query=defaultdict(list)
    for row in candidates:
        require(query_key(row) in set(qkeys),'Candidate belongs to an unexpected query')
        by_query[query_key(row)].append(row)
    empty_queries=sum(not by_query[key] for key in qkeys)
    require(empty_queries==freeze.get('empty_queries')==config.get('empty_window_queries')==proof.get('empty_window_queries'),
            'Original empty-window queries were changed or dropped')
    for row in windows:
        key=query_key(row);subset=by_query[key]
        require([int(x['candidate_index']) for x in subset]==list(range(len(subset))),'Candidate index not contiguous original order')
        require([int(x['pool_position']) for x in subset]==row['selected_pool_positions'],'Frozen mass cap/order differs')
        require(row['final_candidates']==len(subset) and len(subset)<=128,'Candidate cap count differs')
        require(set(row['selected_pool_positions'])<=set(row['uncapped_pool_positions']),'Candidate selected outside frozen mass window')
    gate=dict(status='passed_complete_predictions_before_first_truth_open',timestamp_utc=stamp(),queries=EXPECTED_QUERY_COUNT,candidates=len(candidates),missing_scores_by_query=[dict(molecule_id=k[0],spectrum_id=k[1],counts=dict(v)) for k,v in missing.items()],all_candidates_identical_between_steps=True,all_scores_finite=not missing,truth_opened=False,files=pins,source_script_sha256=sha(__file__))
    if missing:
        gate['status']='refused_missing_predictions_before_first_truth_open'
    save(out/'prediction_gate.json',gate)
    require(not missing,'Prediction row has missing/nonfinite score despite receipt; evaluation truth remains unopened')
    return freeze,proof,queries,candidates,windows,scores,pool_path,pins,plan

def _read_pool_structures(pool_path,positions):
    """Read only fixed numeric windows; no fresh retrieval or truth injection."""
    import pyarrow as pa
    import pyarrow.parquet as pq
    pa.set_cpu_count(1);wanted=set(positions);found={};offset=0
    for batch in pq.ParquetFile(pool_path).iter_batches(columns=['pid','smiles'],batch_size=8192,use_threads=False):
        within=sorted(p-offset for p in wanted if offset<=p<offset+batch.num_rows)
        if within:
            values=batch.take(pa.array(within,type=pa.int64())).to_pydict()
            for i,local in enumerate(within):
                position=offset+local
                require(int(values['pid'][i])==position,'Source pool pid/row coordinates differ')
                found[position]=values['smiles'][i]
        offset+=batch.num_rows
    require(set(found)==wanted,'Source pool misses a frozen candidate-window row')
    return found

def _rank(step,rows,truth,metric):
    if not rows:
        return dict(mrr25_contribution=0.,top1=False,top25_hit=False,
            truth_rank_full_unique_candidates=None,truth_rank25=None,
            unique_scored_identity_count=0,duplicate_identities_removed=0,
            invalid_official_identity_candidate_indices=[],top25=[],missing_scores=0,
            official_metric_verified_on_submitted_top25=False,no_submission_reason='empty_frozen_mass_window',
            score_rule=RANK_POLICY)
    ordered=sorted(rows,key=lambda row:(-float(row[step+'_score']),int(row['candidate_index'])))
    seen=set();unique=[];invalid=[]
    for row in ordered:
        identity=metric.identity(row['smiles'])
        if identity is None:
            invalid.append(int(row['candidate_index']));continue
        if identity in seen:continue
        seen.add(identity)
        unique.append(dict(candidate_index=int(row['candidate_index']),pid=int(row['pid']),smiles=row['smiles'],official_identity=identity,score=float(row[step+'_score'])))
    full_rank=next((rank for rank,row in enumerate(unique,1) if row['official_identity']==truth),None)
    top25=unique[:25];rank25=full_rank if full_rank is not None and full_rank<=25 else None
    rr=1./rank25 if rank25 is not None else 0.
    require(top25,'No valid official metric identity available for a nonempty prediction')
    # Identity deduplication constructs the submitted list. The official metric
    # itself retains every submitted position; verify this exact first-25 list.
    submitted=';'.join(row['smiles'] for row in top25)
    official_rank=metric.first_correct_rank(truth,submitted,max_rank=25)
    official_rr=metric.reciprocal_rank(truth,submitted,max_rank=25)
    require(official_rank==rank25 and official_rr==rr,'Constructed first-25 list differs from official MRR@25')
    return dict(mrr25_contribution=official_rr,top1=official_rank==1,top25_hit=official_rank is not None,
                truth_rank_full_unique_candidates=full_rank,truth_rank25=rank25,
                unique_scored_identity_count=len(unique),duplicate_identities_removed=len(rows)-len(invalid)-len(unique),
                invalid_official_identity_candidate_indices=invalid,top25=top25,
                missing_scores=0,official_metric_verified_on_submitted_top25=True,score_rule=RANK_POLICY)

def evaluate(args):
    started=time.perf_counter();data=workspace(args.data_root);inference=workspace(args.inference_root);out=workspace(args.output)
    require(not out.exists(),'Fresh evaluation output directory required; preserve prior result')
    out.mkdir(parents=True,exist_ok=False);truth_opened=False
    try:
        freeze,proof,queries,candidates,windows,scores,pool_path,pins,plan=_bind_inference_success(data,inference,out)
        sys.path[:0]=[str(ROOT/'.cache/rdkit-official-linux-2026033'),str(ROOT)]
        from validation import metric
        metric.assert_official_rdkit()
        metric_path=Path(metric.__file__).resolve();pins[str(metric_path)]=sha(metric_path)
        # ---------------------------------------------------------------
        # FIRST evaluation-truth open: only after complete success gate.
        # Inference receives neither this metadata nor coverage evaluations.
        # ---------------------------------------------------------------
        receipt_path=data/'evaluation_metadata_receipt.json'
        metadata_receipt=read(receipt_path)
        require(metadata_receipt.get('status')=='evaluation_metadata_frozen_after_candidate_freeze','Unknown evaluation metadata receipt')
        require(metadata_receipt.get('inference_allowed_to_read') is False and metadata_receipt.get('frozen_inference_inputs_unchanged') is True,'Evaluation/prediction boundary not declared')
        require(metadata_receipt.get('candidate_freeze_sha256')==sha(data/'candidate_freeze.json'),'Truth metadata refers to another candidate freeze')
        require(metadata_receipt.get('candidate_windows_sha256')==sha(data/'candidate_windows.json'),'Truth metadata windows differ')
        require(metadata_receipt.get('source_selection_sha256')==EXPECTED_SELECTION_SHA,'Truth metadata source selection changed')
        truth_path=data/'evaluation_truth_metadata.json';coverage_path=data/'coverage_evaluation_only.json'
        require(sha(truth_path)==metadata_receipt.get('evaluation_truth_metadata_sha256'),'Evaluation truth bytes changed')
        require(sha(coverage_path)==metadata_receipt.get('coverage_evaluation_sha256'),'Coverage audit bytes changed')
        truth_opened=True;truth_metadata=read(truth_path);coverage=read(coverage_path)
        require(truth_metadata.get('status')=='evaluation_only_truth_after_candidate_freeze','Unknown evaluation truth schema')
        require(truth_metadata.get('candidate_freeze_sha256')==sha(data/'candidate_freeze.json'),'Truth metadata candidate binding differs')
        require(truth_metadata.get('candidate_windows_sha256')==sha(data/'candidate_windows.json'),'Truth metadata window binding differs')
        require(truth_metadata.get('source_selection_sha256')==EXPECTED_SELECTION_SHA,'Truth metadata group source differs')
        require(coverage.get('candidate_freeze_sha256')==sha(data/'candidate_freeze.json'),'Coverage metadata candidate binding differs')
        for path in (receipt_path,truth_path,coverage_path):pins[str(path)]=sha(path)
        qkeys={query_key(row) for row in queries};truth_rows=truth_metadata['rows']
        require(len(truth_rows)==EXPECTED_QUERY_COUNT and {query_key(row) for row in truth_rows}==qkeys,'Truth evaluation does not exactly cover original100 queries')
        coverage_rows={query_key(row):row for row in coverage['rows']}
        require(len(coverage['rows'])==EXPECTED_QUERY_COUNT and set(coverage_rows)==qkeys,'Coverage audit does not exactly cover original100 queries')
        positions={int(position) for row in windows for position in row['uncapped_pool_positions']}
        pool_smiles=_read_pool_structures(pool_path,positions)
        pool_identity={position:metric.identity(smiles) for position,smiles in pool_smiles.items()}
        by_query=defaultdict(list)
        for row in scores:by_query[query_key(row)].append(row)
        window_by_query={query_key(row):row for row in windows}
        reports=[];ranking_rows=[]
        for truth_row in truth_rows:
            key=query_key(truth_row);window=window_by_query[key];rows=by_query[key]
            truth=metric.identity(truth_row['truth_smiles'])
            require(truth is not None and truth==truth_row['truth_official_identity'],'Truth official identity is not reproducible')
            full_hits=[int(position) for position in window['uncapped_pool_positions'] if pool_identity[int(position)]==truth]
            cap_hits=[int(position) for position in window['selected_pool_positions'] if pool_identity[int(position)]==truth]
            require(full_hits==truth_row['uncapped_true_pool_positions'],'Independent official full-window recall differs from evaluation metadata')
            require(cap_hits==truth_row['selected_true_pool_positions'],'Independent official capped recall differs from evaluation metadata')
            require(window['uncapped_candidates']==truth_row['uncapped_candidates'] and window['final_candidates']==truth_row['final_candidates'],'Truth metadata candidate counts differ')
            cr=coverage_rows[key]
            require(bool(full_hits)==cr['uncapped_true_identity_present'] and bool(cap_hits)==cr['final_true_identity_present'],'Independent official recall differs from coverage audit')
            for row in rows:
                require(row['smiles']==pool_smiles[int(row['pool_position'])],'Scored candidate SMILES differs from frozen source pool row')
            first=_rank('step0',rows,truth,metric);last=_rank('step500',rows,truth,metric)
            require(first['unique_scored_identity_count']==last['unique_scored_identity_count'],'Fixed candidate identity multiset changed between steps')
            if not full_hits:origin='truth_absent_from_uncapped_mass_window'
            elif not cap_hits:origin='truth_removed_by_predeclared_mass_cap'
            else:origin='truth_available_for_ranking'
            delta=last['mrr25_contribution']-first['mrr25_contribution']
            row_report=dict(molecule_id=key[0],spectrum_id=key[1],truth_official_identity=truth,
                uncapped_candidates=window['uncapped_candidates'],capped_candidates=len(rows),
                full_window_true_identity_present=bool(full_hits),capped_true_identity_present=bool(cap_hits),
                cap_removed_all_truth=bool(full_hits and not cap_hits),candidate_availability=origin,
                missing_score_count_step0=0,missing_score_count_step500=0,
                same_raw_candidate_set_and_order=True,step0=first,step500=last,
                delta_rr25=delta,outcome='improved' if delta>0 else 'worsened' if delta<0 else 'unchanged')
            reports.append(row_report)
            for step,ranked in [('step0',first),('step500',last)]:
                ranking_rows.append(dict(checkpoint=step,molecule_id=key[0],spectrum_id=key[1],smiles=';'.join(row['smiles'] for row in ranked['top25'])))
        require(len(reports)==EXPECTED_QUERY_COUNT,'All original100 query outcomes must remain in summary')
        roles={'all_original100':'full existing development-panel summary',
               'pilot8_reproduction_only':'reproduction only; already inspected pilot',
               PRIMARY_GROUP:'predeclared primary check; uninspected candidate ranking outcomes outside pilot8'}
        groups={name:_group_summary(reports,ids,roles[name]) for name,ids in plan['groups'].items()}
        summary=groups['all_original100']['checkpoint_metrics']
        result=dict(status='completed_fixed_original100_component_candidate_evaluation',evaluated_at_utc=stamp(),
            first_truth_read_after_complete_prediction_gate=True,official_rdkit_version=metric.assert_official_rdkit(),
            metric_source_sha256=metric.OFFICIAL_SOURCE_SHA256,ranking_policy=RANK_POLICY,
            query_denominator=EXPECTED_QUERY_COUNT,source_development_denominator=EXPECTED_QUERY_COUNT,
            all_original_development_queries_retained=True,queries_selected_from_graph_ready_only=False,
            excluded_for_missing_true_fragment_supervision=0,
            full_window_candidate_recall=sum(row['full_window_true_identity_present'] for row in reports)/float(EXPECTED_QUERY_COUNT),
            capped_candidate_recall=sum(row['capped_true_identity_present'] for row in reports)/float(EXPECTED_QUERY_COUNT),
            cap_removed_all_truth_queries=sum(row['cap_removed_all_truth'] for row in reports),
            unavailable_candidates_not_labeled_ranking_errors=True,missing_scores_total=0,
            checkpoint_metrics=summary,delta_MRR_at_25=summary['step500']['MRR_at_25']-summary['step0']['MRR_at_25'],
            paired_delta_MRR_at_25_bootstrap95=groups['all_original100']['paired_delta_MRR_at_25_bootstrap95'],
            predeclared_primary_group=PRIMARY_GROUP,groups=groups,evaluation_plan=plan,
            primary_group_checkpoint_metrics=groups[PRIMARY_GROUP]['checkpoint_metrics'],
            primary_group_delta_MRR_at_25=groups[PRIMARY_GROUP]['delta_MRR_at_25'],
            primary_group_paired_delta_MRR_at_25_bootstrap95=groups[PRIMARY_GROUP]['paired_delta_MRR_at_25_bootstrap95'],
            paired_outcomes=dict(Counter(row['outcome'] for row in reports)),queries=reports,
            candidate_sets_exactly_identical=True,all_predictions_frozen_and_complete=True,
            source_script_sha256=sha(__file__),input_bindings=pins,total_seconds=time.perf_counter()-started,
            new_public_score=None,champion_full_pipeline_executed=False,independent_clean_cv=False,
            threshold_fusion_checkpoint_or_candidate_tuning=False,
            boundary='All original100 development component queries, including queries without matched true-fragment supervision. Primary predeclared group is remaining92 outside original8 pilot; pilot8 is reproduction only. Existing development panel, not a new independent holdout. Mass-only fixed pool/cap candidates, not champion final candidate set/full pipeline. Unknown MSnLib exposure. No hidden-class proportions, independent generalization or Kaggle gain inferred.')
        for path,pin in pins.items():require(sha(path)==pin,'Bound input changed during evaluation: '+path)
        with (out/'ranked_predictions.csv').open('w',encoding='utf-8',newline='') as h:
            writer=csv.DictWriter(h,fieldnames=['checkpoint','molecule_id','spectrum_id','smiles']);writer.writeheader();writer.writerows(ranking_rows)
        save(out/'evaluation.json',result)
        lines=['# FIORA原100开发查询固定候选组件评价','',
               '预声明主检验：按原8题输入的molecule_id集合排除后的92题；原8题仅作复现。全100保留为整体汇总，包含原两题无真实fragment监督者。',
               'step0/500使用完全相同候选；完成全部预测绑定后才读取评价标签。','',
               '| 分组 | 模型 | MRR@25 | Top1 | Recall@25 |','| --- | --- | ---: | ---: | ---: |']
        for name in (PRIMARY_GROUP,'pilot8_reproduction_only','all_original100'):
            group=groups[name]
            for step in ('step0','step500'):
                values=group['checkpoint_metrics'][step]
                lines.append(f"| {name} (n={group['query_denominator']}) | {step} | {values['MRR_at_25']:.6f} | {values['top1_count']}/{group['query_denominator']} | {values['top25_recall']:.3f} |")
        for name in (PRIMARY_GROUP,'pilot8_reproduction_only','all_original100'):
            group=groups[name]
            ci=group['paired_delta_MRR_at_25_bootstrap95']
            lines.extend(['',f"{name}: 配对MRR增量 {group['delta_MRR_at_25']:+.6f}，paired bootstrap95%区间 [{ci['lower95']:+.6f},{ci['upper95']:+.6f}]；seed={BOOTSTRAP_SEED}，{BOOTSTRAP_RESAMPLES}次。",''])
        lines+=['',f"完整质量窗候选召回 {result['full_window_candidate_recall']:.3f}；cap后 {result['capped_candidate_recall']:.3f}。缺失分数0；cap漏真与候选本来缺失单独报告。",'',
                '这是既用development100组件检查，非新独立holdout。区间只描述固定开发面板的查询重采样变化；不是完整冠军或榜分收益。没有根据本结果调融合、阈值、模型、候选或分组。']
        (out/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
        print(json.dumps({key:result[key] for key in ['status','query_denominator','checkpoint_metrics','paired_outcomes']}))
    except BaseException as error:
        save(out/'failure.json',dict(status='refused_or_failed_candidate_evaluation',truth_metadata_opened=truth_opened,
             error_type=type(error).__name__,error=str(error),traceback=traceback.format_exc(),source_script_sha256=sha(__file__)))
        raise

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root',type=Path,default=DATA)
    parser.add_argument('--inference-root',type=Path,default=DATA/'inference')
    parser.add_argument('--output',type=Path,default=OUTPUT)
    evaluate(parser.parse_args())
