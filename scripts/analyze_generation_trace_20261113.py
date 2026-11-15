"""Summarize saved production observations only; never imports or launches models."""
from pathlib import Path
import collections
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / 'runs/generation_production_20261113_r2'
OUT = ROOT / 'reports/optimization_20261113'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    runtime_path = RUN / 'kaggle/working/generation_runtime.json'
    runtime = json.loads(runtime_path.read_text())
    verification_path = RUN / 'verification.json'
    verification = json.loads(verification_path.read_text())
    schema_path = RUN / 'input_schema_review.json'
    schema = json.loads(schema_path.read_text())
    independent_path = OUT / 'evidence_generation_review.json'
    independent = json.loads(independent_path.read_text())
    rows = []
    for row in runtime['rows']:
        first6 = sum(c['products'] for c in row['parent_calls'] if c['rank'] <= 6)
        later = sum(c['products'] for c in row['parent_calls'] if c['rank'] > 6)
        rows.append(dict(
            molecule_id=row['molecule_id'],
            eligible_parents=row['eligible_parents'],
            actual_parent_calls=row['parents_used'],
            first6_raw_products=first6,
            parent7_12_raw_products=later,
            accepted_generated=row['n_generated'],
            accepted_from_parent7_12_lower_bound=max(0, row['n_generated'] - first6),
            accepted_from_parent7_12_exact=(row['n_generated'] if first6 == 0 else None),
            accepted_counts_by_parent_sid=dict(collections.Counter(row['generated_parents'])),
            hit_total_cap=row['hit_total_cap'],
            generation_seconds=row['generation_seconds'],
            actual_feature_columns=row['n_features'],
            ranker_selected_columns=row['ranker_feature_count'],
            engine_top25_generated_raw_smiles=row['engine_top25_generated'],
        ))
    out = dict(
        status='saved_trace_mechanism_description_not_efficacy',
        evidence=dict(runtime=str(runtime_path.relative_to(ROOT)), runtime_sha256=sha(runtime_path),
                      verification_sha256=sha(verification_path),
                      independent_review_sha256=sha(independent_path)),
        configuration=runtime['configuration'],
        rows=rows,
        summary=dict(
            actual_parent_calls=sum(r['actual_parent_calls'] for r in rows),
            actual_parent7_12_calls=sum(max(0, r['actual_parent_calls'] - 6) for r in rows),
            accepted_generated=sum(r['accepted_generated'] for r in rows),
            accepted_from_parent7_12_lower_bound=sum(r['accepted_from_parent7_12_lower_bound'] for r in rows),
            total_cap_queries=sum(r['hit_total_cap'] for r in rows),
            actual_ranker_selected_columns=len(runtime['selected_ranker_features']),
            pipeline_seconds=verification['seconds'],
        ),
        causal_limits=[
            'Champion already generates: 6 parents, total 150, per-parent 60, two steps, isomerisation enabled.',
            'Current candidate changes parents 6->12, total cap 150->300, and isomerisation True->False simultaneously.',
            'No same-run unchanged-champion control exists; generated totals and raw-SMILES final intersections are not incremental recall or score gain.',
            'Parent trace records call rank and output parent sid separately, without explicit rank-to-sid binding. Late-parent accepted counts are conservatively lower bounded, not guessed.',
            'Disabling isomerisation specifically suppresses near-zero mass-delta derivation; nonzero-delta two-step transforms remain enabled.',
            'Two diagnostic queries contain unused truth metadata and cannot select a new algorithm or establish Class-3 efficacy.',
        ],
        additional_arm_recommendation=dict(
            build=False,
            submit=False,
            decision='Wait for the current repaired candidate actual hidden score; no distinct extra arm has sufficient evidence today.',
            reason='12/150/no-isomer is a budget control, while 12/150/default-isomer may reproduce capped original generation. Neither has independent positive ranking evidence; avoid spending a second slot on a blind cap or threshold change.',
            if_later_needed_exact_control=dict(gen_n_analog=6, gen_max_total=150,
                gen_max_per_parent=60, max_steps=2, allow_isomerisation=False),
            control_purpose='Only after a genuine gain, this fixed original-budget no-isomer control isolates isomerisation removal against unchanged champion. It is a proposed attribution control, not a recommended submission now.',
        ),
    )
    (OUT / 'generation_trace_analysis.json').write_text(json.dumps(out, indent=2) + '\n')
    disclosure = dict(
        status='provenance_correction_addendum',
        supersedes='verification.json limitation word unlabelled and preparation original no_truth_loaded=true',
        original_verification_preserved=True,
        actual_input_not_modified=True,
        actual_input_extra_columns=schema['extra_columns'],
        no_truth_loaded=False,
        truth_metadata_present=True,
        clean_validation=False,
        efficacy_claim=False,
        use='Production execution-path smoke only',
        source_review=independent['real_execution']['source_label_audit'],
        future_prepare='Official test schema whitelist; already implemented in run_generation_production_20261113.py',
        sources=dict(verification_sha256=sha(verification_path),
                     input_schema_review_sha256=sha(schema_path),
                     independent_review_sha256=sha(independent_path)),
    )
    (OUT / 'generation_disclosure_addendum.json').write_text(json.dumps(disclosure, indent=2) + '\n')
    print(json.dumps(out['summary'], indent=2))


if __name__ == '__main__':
    main()
