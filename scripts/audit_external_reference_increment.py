"""Audit the frozen Enveda-180 mirror against official training identities.

No query truth, locked evaluation, model weights, or peak arrays are loaded.
The official metric identity is recomputed for every unique SMILES needed here.
Downloads must be completed separately; all inputs are freshly SHA-256 checked.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from validation.metric import assert_official_rdkit, identity

FILES = {
    'enveda180_hplus_hminus_references.parquet':
        (218514313, '37b8f37c5f5f536ed804d4d0456e20f183fa32388f30ae1c1712928471146069'),
    'enveda180_only_candidate_aliases.parquet':
        (116885, '3ed2d8f086e51931798a34e241027de66cad76b929c0dba1d866f31f2b21e150'),
}


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(8 << 20), b''):
            h.update(b)
    return h.hexdigest()


def write(path, value):
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


def canonical_chunk(smiles):
    return [(s, identity(s)) for s in smiles]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--output', type=Path, default=ROOT / 'reports/external_reference_pilot_20261107')
    parser.add_argument('--full-identity-audit', action='store_true', help='Opt in to the expensive resumable full-table canonicalization')
    parser.add_argument('--max-new-identities', type=int, default=8192, help='Bound a full-audit run; zero means all remaining identities')
    args = parser.parse_args()
    out = args.output.resolve()
    if not out.is_relative_to(ROOT):
        raise ValueError('Output must remain inside the D-drive workspace')
    out.mkdir(parents=True, exist_ok=True)
    assert_official_rdkit()
    import pyarrow as pa
    import pyarrow.parquet as pq

    started = time.monotonic()
    external = ROOT / 'assets/kaggle/egehseyinca/enveda180-casmi26-reference-ccby4/v1'
    receipts = {}
    for name, (size, expected) in FILES.items():
        p = external / name
        if p.stat().st_size != size or sha(p) != expected:
            raise ValueError('External file size or fresh SHA mismatch: ' + name)
        receipts[name] = {'bytes': size, 'sha256': expected}
    train = ROOT / 'enveda-CASMI26-molecule-id-mass-spectra/train.parquet'
    # Re-read ALL rows from two narrow columns, independently checking that the
    # existing unique-pair catalog really covers this exact current train file.
    train_pairs = set()
    rows = 0
    for batch in pq.ParquetFile(train).iter_batches(columns=['inchikey14', 'normalized_smiles'], batch_size=32768):
        d = batch.to_pydict()
        rows += batch.num_rows
        train_pairs.update(zip(d['inchikey14'], d['normalized_smiles']))
    catalog_path = ROOT / 'runs/validation_pilot_v2_20261104/structure_identity_audit.parquet'
    catalog = pq.read_table(catalog_path, columns=['raw_inchikey14', 'smiles']).to_pydict()
    cached_pairs = set(zip(catalog['raw_inchikey14'], catalog['smiles']))
    if train_pairs != cached_pairs:
        raise ValueError('Train pair catalog does not exactly match current train')
    refs = pq.read_table(external / 'enveda180_hplus_hminus_references.parquet',
        columns=['reference_key', 'smiles', 'neutral_mass', 'adduct', 'spectrum_signature'])
    aliases = pq.read_table(external / 'enveda180_only_candidate_aliases.parquet')
    refd, aliases_rows = refs.to_pydict(), aliases.to_pylist()
    train_smiles = {s for _, s in train_pairs}
    ref_smiles = set(refd['smiles'])
    all_smiles = sorted(train_smiles | ref_smiles | {r['smiles'] for r in aliases_rows})
    print(json.dumps({'stage': 'inputs_checked', 'train_rows': rows, 'train_pairs': len(train_pairs),
        'train_unique_smiles': len(train_smiles), 'reference_unique_smiles': len(ref_smiles),
        'combined_unique_smiles': len(all_smiles), 'metadata_only': True}), flush=True)
    del cached_pairs, catalog

    # The small publisher source-only catalog is independently canonicalized in
    # every mode. Membership in official train remains unresolved in this mode.
    alias_identity = {r['smiles']: identity(r['smiles']) for r in aliases_rows}
    alias_ids = {v for v in alias_identity.values() if v}
    alias_related = []
    for i, (key, s, a, mass, sig) in enumerate(zip(*(refd[c] for c in
        ['reference_key','smiles','adduct','neutral_mass','spectrum_signature']))):
        if key in alias_ids:
            alias_related.append({'row_index':i,'publisher_reference_key':key,'smiles':s,
                'adduct':a,'neutral_mass':mass,'spectrum_signature':sig})
    related_official = {r['smiles']:identity(r['smiles']) for r in alias_related}
    for r in alias_related:
        r['official_identity']=related_official[r['smiles']]
    pq.write_table(pa.Table.from_pylist(alias_related),out/'alias_related_reference_rows.parquet',compression='zstd')
    partial = {
        'status':'partial_metadata_and_alias_identity_audit',
        'created_at_utc':datetime.now(timezone.utc).isoformat(),
        'source':{'kaggle_dataset':'egehseyinca/enveda180-casmi26-reference-ccby4/1',
            'zenodo_record':21346580,'license':'CC BY 4.0','fresh_file_checks':receipts},
        'metric_rdkit':'2026.03.3',
        'train':{'rows':rows,'unique_raw_smiles_pairs':len(train_pairs),
            'unique_pair_catalog_exactly_matches_current_train':True,'catalog_sha256':sha(catalog_path)},
        'reference':{'rows':refs.num_rows,'publisher_keys':len(set(refd['reference_key'])),
            'unique_smiles':len(ref_smiles),'rows_by_adduct':dict(Counter(refd['adduct']))},
        'aliases':{'rows':len(aliases_rows),'official_identities':len(alias_ids),
            'publisher_key_mismatch_rows':sum(alias_identity[r['smiles']]!=r['candidate_key'] for r in aliases_rows),
            'related_reference_spectra':len(alias_related),
            'related_reference_identities':len(set(r['official_identity'] for r in alias_related)),
            'related_spectra_by_adduct':dict(Counter(r['adduct'] for r in alias_related)),
            'related_reference_key_mismatch_rows':sum(r['official_identity']!=r['publisher_reference_key'] for r in alias_related)},
        'unresolved':['Independent official-train membership of publisher source-only aliases.',
            'Official identity of reference SMILES outside the alias-related subset.',
            'PubChem/COCONUT candidate membership; exact/near spectrum overlap; matching accuracy.'],
        'all_spectra_and_alias_counts_are_not_hidden_test_coverage':True,
        'no_peak_columns_loaded':True,'no_query_or_locked_truth_loaded':True,
        'elapsed_seconds':round(time.monotonic()-started,2),
    }
    write(out/'partial_audit.json',partial)
    if not args.full_identity_audit:
        print(json.dumps(partial,ensure_ascii=False),flush=True)
        return

    # A local durable cache permits interruption/resume without interpreting raw
    # InChIKey14 as the competition's tautomer-canonical scoring identity.
    db = sqlite3.connect(out / 'official_identity_cache.sqlite')
    db.execute('CREATE TABLE IF NOT EXISTS meta (name TEXT PRIMARY KEY, value TEXT NOT NULL)')
    version = db.execute("SELECT value FROM meta WHERE name='rdkit'").fetchone()
    if version and version[0] != '2026.03.3':
        raise ValueError('Identity cache RDKit mismatch')
    db.execute("INSERT OR REPLACE INTO meta VALUES ('rdkit','2026.03.3')")
    db.execute('CREATE TABLE IF NOT EXISTS identities (smiles TEXT PRIMARY KEY, official_identity TEXT)')
    mapping = dict(db.execute('SELECT smiles, official_identity FROM identities'))
    pending = [s for s in all_smiles if s not in mapping]
    complete_pending_count = len(pending)
    if args.max_new_identities:
        pending = pending[:args.max_new_identities]
    chunks = [pending[i:i+256] for i in range(0, len(pending), 256)]
    print(json.dumps({'stage': 'canonicalizing', 'pending': len(pending), 'workers': args.workers}), flush=True)
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        done = 0
        for result in pool.map(canonical_chunk, chunks):
            db.executemany('INSERT OR REPLACE INTO identities VALUES (?,?)', result)
            mapping.update(result)
            done += len(result)
            if done % 4096 == 0 or done == len(pending):
                db.commit()
                progress = {'stage': 'canonicalizing', 'done': done, 'total': len(pending),
                    'elapsed_seconds': round(time.monotonic()-started, 2)}
                write(out / 'progress.json', progress)
                print(json.dumps(progress), flush=True)
    db.commit()
    db.close()
    if len(pending) < complete_pending_count:
        partial.update(status='partial_identity_cache_budget_reached',
            identity_cache_rows=len(mapping),
            remaining_unique_smiles=sum(s not in mapping for s in all_smiles),
            elapsed_seconds=round(time.monotonic()-started,2))
        write(out/'partial_audit.json',partial)
        print(json.dumps(partial,ensure_ascii=False),flush=True)
        return

    train_ids = {mapping[s] for s in train_smiles if mapping[s]}
    train_invalid = sorted(s for s in train_smiles if not mapping[s])
    if train_invalid:
        # Unparsable training structures create an unresolved membership boundary.
        # Keep evidence, and do not silently certify every source-only identity.
        write(out / 'invalid_train_smiles.json', train_invalid)
    ref_ids = {mapping[s] for s in ref_smiles if mapping[s]}
    novel_ids = ref_ids - train_ids
    ref_key_mismatches = Counter()
    by_adduct = Counter()
    novel_by_adduct = Counter()
    novel_id_adduct = defaultdict(set)
    novel_examples = {}
    sigs = Counter()
    novel_rows = []
    for i, (key, s, adduct, mass, sig) in enumerate(zip(*(refd[c] for c in
        ['reference_key','smiles','adduct','neutral_mass','spectrum_signature']))):
        official = mapping[s]
        by_adduct[adduct] += 1
        if official != key:
            ref_key_mismatches[(str(key), str(official))] += 1
        sigs[(adduct, sig)] += 1
        if official in novel_ids:
            novel_by_adduct[adduct] += 1
            novel_id_adduct[adduct].add(official)
            novel_examples.setdefault(official, {'official_identity': official,'smiles': s,'neutral_mass': mass})
            novel_rows.append({'row_index': i,'official_identity': official,'smiles': s,'adduct': adduct,
                'neutral_mass': mass,'spectrum_signature': sig})
    alias_mismatches = sum(mapping[r['smiles']] != r['candidate_key'] for r in aliases_rows)
    alias_ids = {mapping[r['smiles']] for r in aliases_rows if mapping[r['smiles']]}
    alias_seen = alias_ids & train_ids
    write(out / 'novel_reference_identities.json', sorted(novel_examples.values(),key=lambda r:r['official_identity']))
    pq.write_table(pa.Table.from_pylist(novel_rows), out / 'novel_reference_rows.parquet', compression='zstd')
    result = {
        'status': 'complete' if not train_invalid else 'complete_with_invalid_training_structure_boundary',
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'source': {'kaggle_dataset': 'egehseyinca/enveda180-casmi26-reference-ccby4/1',
            'zenodo_record': 21346580,'license':'CC BY 4.0','fresh_file_checks':receipts},
        'metric': {'rdkit':'2026.03.3','identity':'remove stereo; tautomer canonicalize; InChIKey14'},
        'train': {'rows':rows,'unique_raw_smiles_pairs':len(train_pairs),'unique_smiles':len(train_smiles),
            'official_identities':len(train_ids),'invalid_unique_smiles':len(train_invalid),
            'unique_pair_catalog_exactly_matches_current_train':True,'catalog_sha256':sha(catalog_path)},
        'reference': {'rows':refs.num_rows,'publisher_keys':len(set(refd['reference_key'])),
            'unique_smiles':len(ref_smiles),'official_identities':len(ref_ids),
            'rows_by_adduct':dict(by_adduct),'invalid_unique_smiles':sum(mapping[s] is None for s in ref_smiles),
            'publisher_key_mismatch_rows':sum(ref_key_mismatches.values()),
            'duplicate_same_adduct_signature_rows':sum(c-1 for c in sigs.values() if c>1)},
        'increment': {'official_train_absent_identities':len(novel_ids),'spectra':len(novel_rows),
            'spectra_by_adduct':dict(novel_by_adduct),
            'identities_by_adduct':{a:len(v) for a,v in novel_id_adduct.items()},
            'not_an_estimate_of_hidden_test_overlap':True,
            'existing_train_identity_spectra_not_yet_near_duplicate_audited':refs.num_rows-len(novel_rows)},
        'aliases': {'rows':len(aliases_rows),'official_identities':len(alias_ids),
            'publisher_key_mismatch_rows':alias_mismatches,'actually_seen_in_train':len(alias_seen),
            'source_only_with_Hplus_Hminus_spectra':len(alias_ids & novel_ids),
            'source_only_without_Hplus_Hminus_spectra':len(alias_ids-train_ids-ref_ids)},
        'boundaries': ['No peak column read, no matching model or overlay evaluated.',
            'No query/locked holdout truth read; no training or cloud submission.',
            'Train membership is exact over all parseable unique SMILES, rather than raw InChIKey matching.',
            'Same-adduct signature duplicate counts are publisher signatures, not an independent peak recomputation.',
            'PubChem/COCONUT membership and exact/near spectrum overlap remain separate audits.'],
        'elapsed_seconds':round(time.monotonic()-started,2),
    }
    write(out/'audit.json',result)
    print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__ == '__main__':
    main()
