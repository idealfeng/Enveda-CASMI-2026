"""Summarize completed extlib2 audits without rerunning matching or identity work."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/extlib2_execution_20261115'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    with Path(p).open('rb') as h:return hashlib.file_digest(h,'sha256').hexdigest()
def main():
    sources={name:ROOT/path for name,path in {
        'metadata':'reports/extlib2_increment_20261114/metadata_audit.json',
        'spectra':'reports/extlib2_increment_20261114/spectrum_overlap_complete.json',
        'bounded_official':'reports/extlib2_increment_20261114/bounded_official_identity_audit.json',
        'matching':'reports/extlib2_matching_20261114/verification.json',
        'evidence':'reports/extlib2_matching_20261114/evidence_summary.json'}.items()}
    data={k:read(p) for k,p in sources.items()};m,s,b,v,e=[data[k] for k in ['metadata','spectra','bounded_official','matching','evidence']]
    checks=dict(full_train_spectrum_count=s['official_train_spectra_scanned']==m['sources']['official_train_rows']==2539608,
                C_count=s['C_rows']==m['sources']['C_rows']==490840,
                bounded_official_completed=b['status']=='complete_official_identity_audit_of_raw_key_novel_subset',
                real_matching_complete=v['status']=='passed_real_controlled_matching' and all(v['checks'].values()),
                old_candidate_features_complete=e['candidate_feature_rows']==1250,
                old_feature_fingerprint=sha(ROOT/'runs/extlib2_matching_20261114_v2/candidate_library_features.parquet')==e['candidate_feature_sha256'],
                matched_tables_bound=all(sha(ROOT/'runs/extlib2_matching_20261114_v2'/f'{k}_actual_match_table.json')==pin for k,pin in v['score_artifact_sha256'].items()))
    if not all(checks.values()):raise ValueError('Existing evidence failed final binding')
    result=dict(status='completed_corpus_and_fixed_matching_review',checked_at_utc=datetime.now(timezone.utc).isoformat(),checks=checks,
                raw_membership=m['publisher_key_overlap'],bounded_official_new_identities=b['official_ids_absent_from_train_and_AB'],
                bounded_official_new_spectra=b['official_rows_absent_from_both'],bounded_official_scope=b['scope_boundary'],
                spectrum_hash_results=s,controlled_matching=v['evaluations'],old_features=dict(rows=e['candidate_feature_rows'],sha256=e['candidate_feature_sha256'],truth_labels_in_features=False),
                source_pins={k:dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p)) for k,p in sources.items()},
                new_public_score=None,new_model_training=False,old_experiments_rerun=False,
                recommendation='Do not force C high-cosine winners to rank1. Preserve measured evidence for independently grouped gate learning; require truth-present and truth-absent behavior.',
                limitations=['115 is the exactly resolved raw-key-novel subset, not a full-corpus official novelty count.',
                             'Unmatched spectral hashes are not proof of independently acquired spectra.',
                             'Old48 fixed matching has known pretrained exposure and is not exact .488 CV; prior pipeline confidence is not rebuilt in reference-absence arm.',
                             'The two-query component has zero efficacy claim; real C matches were blocked by original pipeline confidence.',
                             'Public download and upstream source log are recorded, but this report does not grant a new license or prove a hidden-test gain.'])
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'completed_audit_summary.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=result['status'],bounded_official_new_identities=result['bounded_official_new_identities'],all_checks=True)))
if __name__=='__main__':main()
