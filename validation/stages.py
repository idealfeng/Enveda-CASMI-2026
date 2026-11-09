"""Read actual candidate-stage artifacts without inventing unobserved recall.

An absent molecule/stage row is unknown, never an inferred empty candidate pool.
Engine 2's local structural mass window and PubChem's emitted top list have
different coverage; neither is global PubChem mass-window recall.
"""
from __future__ import annotations

from pathlib import Path
import json

import numpy as np
import pandas as pd

from . import metric
from .evaluate import validate_truth

STAGE_POLICIES = {
    'e2_mass_window': {'coverage': 'complete_for_recorded_e2_pool_mass_window',
        'scope': 'Engine 2 COCONUT/BIO/PubChemLite/training structural pool mass window only; not the separate PubChem tier.'},
    'e2_ranked_all': {'coverage': 'complete_for_recorded_e2_ranked_candidates',
        'scope': 'Engine 2 candidates with blended ranker scores before emitted top40.'},
    'e1_ranked_all': {'coverage': 'post_engine_candidate_materialization',
        'scope': 'Engine 1 materialized candidates after its retrieval/generation/pruning; not its complete source mass window.'},
    'e1_base_top': {'coverage': 'truncated_output_list',
        'scope': 'Engine 1 BASE list present in final frozen namespace, including in-place re-ranks.'},
    'e2_top40': {'coverage': 'truncated_output_list', 'scope': 'Engine 2 emitted candidate list, normally up to40.'},
    'pubchem_top': {'coverage': 'partial_top_output_only',
        'scope': 'PubChem-only emitted top candidates; complete 104M-tier mass-window candidates and prior filters were not exported.'},
    'prefusion_lists': {'coverage': 'materialized_intermediate_list', 'scope': 'PREFUSION_LISTS from the actual frozen namespace.'},
    'base_tail_candidates': {'coverage': 'materialized_intermediate_list', 'scope': 'BASE_TAIL_CANDIDATES from the actual frozen namespace.'},
    'fusion_overflow': {'coverage': 'materialized_intermediate_list', 'scope': 'FUSION_OVERFLOW from the actual frozen namespace.'},
    'neural_outside_scored': {'coverage': 'partial_selected_outsiders_only',
        'scope': 'Selected outsider candidates scored by Saner, not every candidate omitted by source databases.'},
    'neural_baseline_scored': {'coverage': 'fixed_baseline_candidates_only',
        'scope': 'Saner neural features for the frozen final baseline list; does not expand its candidate recall.'},
    'frozen_final25': {'coverage': 'final_ranked_output', 'scope': 'Source-pipeline final list at namespace export: before optional outer neural/postprocessing layers when those exist.'},
    'final_submission': {'coverage': 'final_ranked_output', 'scope': 'Complete submitted list from this local diagnostic run.'},
}
JSONL_FILES = ('validation_e1_candidates.jsonl', 'validation_e2_candidates.jsonl')
PARQUET_FILE = 'validation_candidate_stages.parquet'
KNOWN_STAGES = tuple(STAGE_POLICIES)
TRANSITIONS = (
    ('e2_mass_window', 'e2_ranked_all'), ('e2_ranked_all', 'e2_top40'),
    ('e1_ranked_all', 'e1_base_top'), ('prefusion_lists', 'frozen_final25'),
    ('frozen_final25', 'final_submission'),
)


def read_predictions(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path) if path.suffix.lower() == '.parquet' else pd.read_csv(path, dtype=str, keep_default_na=False)


def _shape(path: Path) -> dict:
    if path.suffix == '.parquet':
        import pyarrow.parquet as pq
        parquet = pq.ParquetFile(path)
        return {'path': str(path), 'rows': parquet.metadata.num_rows, 'columns': parquet.schema_arrow.names}
    if path.suffix == '.jsonl':
        first = None; count = 0
        with path.open(encoding='utf-8') as stream:
            for line in stream:
                if line.strip():
                    row = json.loads(line); count += 1
                    if first is None:
                        first = sorted(row)
        return {'path': str(path), 'rows': count, 'columns': first or []}
    frame = read_predictions(path)
    return {'path': str(path), 'rows': len(frame), 'columns': frame.columns.tolist()}


def inspect_run_shapes(root: Path) -> dict:
    paths = [root / name for name in (*JSONL_FILES, PARQUET_FILE, 'submission.csv', 'submission_baseline0465.csv',
                                     'frozen_candidate_evidence.parquet', 'neural_candidate_features.parquet', 'outsider_neural_features.parquet')]
    paths += sorted((root / 'variants').glob('submission_*.csv'))
    return {'scope': 'Artifact schema sanity only; no truth or model performance was evaluated.',
            'files': [_shape(path) for path in paths if path.is_file()],
            'missing_stage_files': [name for name in (*JSONL_FILES, PARQUET_FILE) if not (root / name).is_file()]}


def _validate_stage_frame(frame: pd.DataFrame, path: Path, expected_ids: set[str]) -> pd.DataFrame:
    columns = {'molecule_id', 'stage', 'rank', 'smiles'}
    if not columns <= set(frame.columns):
        raise ValueError(f'Candidate stage file lacks {sorted(columns)}: {path}')
    frame = frame.copy()
    if frame[list(columns)].isna().any().any():
        raise ValueError('Null required candidate-stage value: ' + str(path))
    frame['molecule_id'] = frame.molecule_id.astype(str)
    frame['stage'] = frame.stage.astype(str)
    frame['smiles'] = frame.smiles.astype(str)
    if set(frame.molecule_id) - expected_ids:
        raise ValueError('Candidate stages include foreign/locked IDs: ' + str(path))
    ranks = pd.to_numeric(frame['rank'], errors='raise')
    if not np.isfinite(ranks).all() or not (ranks >= 1).all() or not (ranks == np.floor(ranks)).all():
        raise ValueError('Candidate ranks must be finite positive integers: ' + str(path))
    frame['rank'] = ranks.astype(np.int64)
    if frame.duplicated(['molecule_id', 'stage', 'rank']).any():
        raise ValueError('Repeated stage rank (possible append/recovery contamination): ' + str(path))
    frame['artifact'] = str(path)
    return frame


def collect_stages(root: Path, expected_ids: set[str]) -> tuple[pd.DataFrame, list[dict]]:
    frames = []; inputs = []
    for name in JSONL_FILES:
        path = root / name
        if not path.is_file():
            continue
        records = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
        inputs.append({'path': str(path), 'rows': len(records)})
        if records:
            frames.append(_validate_stage_frame(pd.DataFrame(records), path, expected_ids))
    path = root / PARQUET_FILE
    if path.is_file():
        frame = pd.read_parquet(path)
        inputs.append({'path': str(path), 'rows': len(frame)})
        if not frame.empty:
            frames.append(_validate_stage_frame(frame, path, expected_ids))
    for name, stage in (('neural_candidate_features.parquet', 'neural_baseline_scored'),
                        ('outsider_neural_features.parquet', 'neural_outside_scored')):
        path = root / name
        if not path.is_file():
            continue
        frame = pd.read_parquet(path)
        if not {'molecule_id', 'smiles', 'baseline_rank'} <= set(frame):
            raise ValueError('Unexpected neural candidate schema: ' + str(path))
        frame = frame.loc[frame.molecule_id.astype(str).isin(expected_ids)].copy()
        frame['stage'] = stage; frame['rank'] = frame.baseline_rank
        inputs.append({'path': str(path), 'rows': len(frame)})
        if not frame.empty:
            frames.append(_validate_stage_frame(frame, path, expected_ids))
    path = root / 'submission.csv'
    if path.is_file():
        rows = []
        for item in read_predictions(path).itertuples(index=False):
            for rank, smiles in enumerate(metric.parse_guesses(item.smiles), 1):
                rows.append({'molecule_id': str(item.molecule_id), 'stage': 'final_submission', 'rank': rank, 'smiles': smiles})
        frames.append(_validate_stage_frame(pd.DataFrame(rows), path, expected_ids))
        inputs.append({'path': str(path), 'rows': len(rows)})
    if not frames:
        return pd.DataFrame(columns=['molecule_id', 'stage', 'rank', 'smiles', 'artifact', 'identity']), inputs
    combined = pd.concat(frames, ignore_index=True)
    if combined.duplicated(['molecule_id', 'stage', 'rank']).any():
        raise ValueError('Conflicting candidate stage/rank records across source artifacts')
    combined['identity'] = combined.smiles.map(metric.identity)
    return combined.sort_values(['stage', 'molecule_id', 'rank'], kind='stable'), inputs


def read_empty_stage_coverage(root: Path, expected_ids: set[str], candidates: pd.DataFrame) -> tuple[set, dict | None]:
    """Use only the three emptiness flags actually emitted by the adapter."""
    path = root / 'validation_empty_candidate_audit.json'
    if not path.is_file():
        return set(), None
    payload = json.loads(path.read_text(encoding='utf-8'))
    rows = payload['rows']
    if len(rows) != len(expected_ids) or {row['molecule_id'] for row in rows} != expected_ids:
        raise ValueError('Empty-candidate audit cohort differs from the active query cohort')
    observed = set(zip(candidates.stage, candidates.molecule_id))
    result = set()
    for row in rows:
        if row.get('query_processed') is not True or row.get('unprocessed_padding') is not False:
            raise ValueError('Empty candidate audit describes an unprocessed query')
        for flag, stage in (('empty_e1', 'e1_base_top'), ('empty_e2', 'e2_top40'), ('empty_pubchem', 'pubchem_top')):
            if not isinstance(row.get(flag), bool):
                raise ValueError('Candidate-empty flag must be an explicit bool')
            key = (stage, row['molecule_id'])
            if row[flag]:
                if key in observed:
                    raise ValueError('Candidate stage contradicts explicit empty flag')
                result.add(key)
            elif key not in observed:
                raise ValueError('Sidecar reports nonempty candidates but the exported stage is missing')
    return result, {'path': str(path), 'scope': payload.get('scope'), 'rows': rows,
                    'explicit_empty_stage_molecules': len(result), 'no_candidate_queries': payload.get('no_candidate_queries')}


def summarize_stages(truth: pd.DataFrame, candidates: pd.DataFrame, final_rows: list[dict] | None = None,
                     explicit_empty: set | None = None) -> dict:
    truth = validate_truth(truth)
    truth_by_id = truth.set_index('molecule_id').identity.to_dict()
    panel_by_id = truth.set_index('molecule_id').panel.to_dict() if 'panel' in truth else {mid: 'all' for mid in truth_by_id}
    final_by_id = {row['molecule_id']: row for row in (final_rows or [])}
    explicit_empty = explicit_empty or set()
    sets = {}; rows = []; summaries = []
    observed_names = set(candidates.stage) if not candidates.empty else set()
    stage_names = list(KNOWN_STAGES) + sorted(observed_names - set(KNOWN_STAGES))
    for stage in stage_names:
        stage_frame = candidates.loc[candidates.stage == stage] if not candidates.empty else candidates
        groups = {str(mid): group for mid, group in stage_frame.groupby('molecule_id', sort=False)}
        stage_rows = []
        for mid, target in truth_by_id.items():
            group = groups.get(mid)
            known_empty = (stage, mid) in explicit_empty
            if group is None and known_empty:
                present = False; rank = None; count = 0; invalid = 0
                sets[(stage, mid)] = set()
            elif group is None:
                present = None; rank = None; count = None; invalid = None
            else:
                values = set(group.identity.dropna())
                sets[(stage, mid)] = values
                present = target in values
                ranks = group.loc[group.identity == target, 'rank']
                rank = int(ranks.min()) if len(ranks) else None
                count = len(values); invalid = int(group.identity.isna().sum())
            final = final_by_id.get(mid)
            row = {'molecule_id': mid, 'panel': panel_by_id[mid], 'stage': stage,
                   'observed': group is not None or known_empty, 'explicit_empty': known_empty,
                   'truth_present': present, 'truth_first_recorded_rank': rank,
                   'valid_identity_count': count, 'invalid_candidate_rows': invalid,
                   'truth_present_but_not_final_top25': bool(present and not final['top25']) if final is not None and present is not None else None,
                   'truth_present_but_not_final_top1': bool(present and not final['top1']) if final is not None and present is not None else None}
            rows.append(row); stage_rows.append(row)
        for panel in ['all'] + sorted({str(v) for v in panel_by_id.values()}):
            chosen = [row for row in stage_rows if panel == 'all' or str(row['panel']) == panel]
            known = [row for row in chosen if row['observed']]
            hits = sum(row['truth_present'] for row in known)
            summaries.append({'stage': stage, 'panel': panel, **STAGE_POLICIES.get(stage, {'coverage': 'unclassified_materialized_output', 'scope': 'Unclassified recorded stage; no full-pool recall claim.'}),
                'molecules': len(chosen), 'observed_molecules': len(known), 'unknown_molecules': len(chosen) - len(known),
                'explicit_empty_molecules': sum(row['explicit_empty'] for row in chosen),
                'status': 'unknown' if not known else 'observed_complete_cohort' if len(known) == len(chosen) else 'partial_cohort',
                'truth_present_molecules': hits, 'truth_presence_rate_among_observed': hits / len(known) if known else None,
                'cohort_truth_presence_lower_bound': hits / len(chosen) if chosen else None,
                'cohort_truth_presence_upper_bound': (hits + len(chosen) - len(known)) / len(chosen) if chosen else None,
                'truth_present_but_not_final_top25': sum(row['truth_present_but_not_final_top25'] is True for row in known) if final_by_id else None,
                'truth_present_but_not_final_top1': sum(row['truth_present_but_not_final_top1'] is True for row in known) if final_by_id else None})
    transitions = []
    for first, second in TRANSITIONS:
        for panel in ['all'] + sorted({str(v) for v in panel_by_id.values()}):
            ids = [mid for mid in truth_by_id if panel == 'all' or str(panel_by_id[mid]) == panel]
            paired = [mid for mid in ids if (first, mid) in sets and (second, mid) in sets]
            lost = [mid for mid in paired if truth_by_id[mid] in sets[(first, mid)] and truth_by_id[mid] not in sets[(second, mid)]]
            gained = [mid for mid in paired if truth_by_id[mid] not in sets[(first, mid)] and truth_by_id[mid] in sets[(second, mid)]]
            transitions.append({'from_stage': first, 'to_stage': second, 'panel': panel,
                'scope': 'Observed materialized candidate lists only; different branches may add candidates. Not a complete global source-recall decomposition.',
                'paired_observed_molecules': len(paired), 'unknown_molecules': len(ids) - len(paired),
                'truth_lost': len(lost), 'truth_lost_ids': lost, 'truth_gained': len(gained), 'truth_gained_ids': gained,
                'equal_identity_sets_molecules': sum(sets[(first, mid)] == sets[(second, mid)] for mid in paired)})
    return {'scope': 'Truth presence in recorded stage candidates. Explicit adapter empty flags establish three top-list empty states; other absent rows stay unknown.',
            'global_source_candidate_recall': {'status': 'unknown', 'reason': 'Complete global source windows and every filter were not recorded; PubChem is top-output only.'},
            'summaries': summaries, 'transitions': transitions, 'rows': rows}
