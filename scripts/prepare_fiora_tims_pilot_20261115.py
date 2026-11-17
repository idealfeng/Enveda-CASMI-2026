"""Frozen metadata selection, then real native FIORA labels/graphs; no training.

Read official train only in Arrow batches. Never open held-out truth/queries.
All graph/label quality is measured after selection and never selects replacements.
"""
from pathlib import Path
from collections import Counter, defaultdict
import argparse
import csv
import gc
import hashlib
import json
import math
import os
import resource
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
ASSET = ROOT / 'assets/research/fiora_os_20261115'
OUT = ROOT / 'runs/fiora_tims_pilot_20261115'
TRAIN = ROOT / 'enveda-CASMI26-molecule-id-mass-spectra/train.parquet'
sys.path[:0] = [str(ROOT / '.cache/rdkit-official-linux-2026033'), str(ROOT)]
CONFIG = dict(seed=20261115, max_structures=500, target_train=400,
              target_development=100, spectra_per_structure=1,
              instrument='timsTOF', adduct='[M+H]+', finite_ce_count=1,
              workers=1, rss_limit_bytes=1024**3, arrow_batch_rows=8192,
              fragmentation_depth=1, relative_match_tolerance=0.0001,
              native_minimum_absolute_tolerance_da=0.01,
              minimum_real_fragment_matches_for_training=1, replace_after_matching=False,
              pretraining_exposure='MSnLib v7 exposure unknown',
              model_features='native graph, CE, molweight, four-mode onehot, HCD/timsTOF/OTHER, elements')
RUNTIME_RSS_LIMIT = CONFIG['rss_limit_bytes']

def sha(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()

def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    tmp.replace(path)

def rank(value):
    return hashlib.sha256((str(CONFIG['seed']) + '|' + str(value)).encode()).hexdigest()

def memory():
    current = 0
    for line in Path('/proc/self/status').read_text().splitlines():
        if line.startswith('VmRSS:'):
            current = int(line.split()[1]) * 1024
            break
    peak = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1024
    if current > RUNTIME_RSS_LIMIT:
        raise MemoryError(f'RSS budget exceeded: {current} > {RUNTIME_RSS_LIMIT}')
    return dict(current_rss_bytes=current, process_peak_rss_bytes=peak)

def read_exclusion_ids():
    raw, official, receipts = set(), set(), []
    json_paths = sorted(set((ROOT / 'runs').glob('validation_pilot*/frozen_splits.json')) |
                        set((ROOT / 'runs').glob('validation_pilot*/class2_exclusion_keys.json')))
    if not json_paths:
        raise FileNotFoundError('Required frozen validation identity manifests missing')
    def visit(value):
        if isinstance(value, dict):
            key = value.get('official_identity')
            if isinstance(key, str):
                official.add(key)
            raw.update(x for x in value.get('raw_keys', []) if isinstance(x, str))
            raw.update(x for x in value.get('blocked_raw_keys', []) if isinstance(x, str))
            official.update(x for x in value.get('blocked_official_identities', []) if isinstance(x, str))
            for item in value.values():
                if isinstance(item, (dict, list)):
                    visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)
    for path in json_paths:
        # These are frozen identity declarations, never truth.csv/query.parquet.
        visit(json.loads(path.read_text(encoding='utf-8')))
        receipts.append(dict(path=path.relative_to(ROOT).as_posix(), sha256=sha(path)))
    for path in [ROOT / 'reports/component_holdout_audit_20261104/component_intersection_queries.csv',
                 ROOT / 'reports/component_holdout_audit_20261104/component_training_unseen_queries.csv']:
        if path.exists():
            with path.open(newline='', encoding='utf-8') as handle:
                for row in csv.DictReader(handle):
                    if row.get('identity'):
                        official.add(row['identity'])
                    if row.get('declared_key'):
                        raw.add(row['declared_key'])
            receipts.append(dict(path=path.relative_to(ROOT).as_posix(), sha256=sha(path), read_fields=['identity', 'declared_key']))
    return raw, official, dict(files=receipts, raw_keys=len(raw), official_ids=len(official),
                               final_truth_or_final_queries_read=False)

def scalar_ce(value):
    values = value if isinstance(value, (list, tuple)) else [value]
    if len(values) != 1:
        return None
    try:
        result = float(values[0])
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None

def metadata():
    import pyarrow as pa
    import pyarrow.parquet as pq
    from validation import metric
    metric.assert_official_rdkit()
    pa.set_cpu_count(1)
    if (OUT / 'selection.json').exists():
        raise FileExistsError('Frozen selection exists; never silently select again')
    OUT.mkdir(parents=True, exist_ok=True)
    save(OUT / 'configuration.json', {**CONFIG, 'script_sha256_at_metadata': sha(__file__)})
    frozen_raw, frozen_ids, exclusions = read_exclusion_ids()
    parquet = pq.ParquetFile(TRAIN)
    columns = ['inchikey14', 'normalized_smiles', 'ingest_lib', 'instrument_type',
               'adduct', 'collision_energy_ev']
    unknown = set(columns) - set(parquet.schema_arrow.names)
    if unknown:
        raise ValueError('Missing metadata columns: ' + str(unknown))
    pool, counters, ce_sizes, sources = {}, Counter(), Counter(), Counter()
    offset, start = 0, time.perf_counter()
    for batch in parquet.iter_batches(batch_size=CONFIG['arrow_batch_rows'], columns=columns, use_threads=False):
        data = batch.to_pydict()
        counters['all_official_train_rows'] += batch.num_rows
        for i, instrument in enumerate(data['instrument_type']):
            if str(instrument).strip().lower() != 'timstof':
                continue
            counters['explicit_timstof_rows'] += 1
            if data['adduct'][i] != CONFIG['adduct']:
                continue
            counters['timstof_positive_protonated_rows'] += 1
            energy_raw = data['collision_energy_ev'][i]
            ce_sizes[str(len(energy_raw)) if isinstance(energy_raw, (list, tuple)) else 'scalar_or_null'] += 1
            ce = scalar_ce(energy_raw)
            if ce is None:
                continue
            counters['single_finite_ce_rows'] += 1
            raw = data['inchikey14'][i]
            smiles = data['normalized_smiles'][i]
            if not isinstance(raw, str) or not raw or not isinstance(smiles, str) or not smiles:
                counters['missing_identity_or_smiles'] += 1
                continue
            if raw in frozen_raw or raw in frozen_ids:
                counters['frozen_raw_excluded_rows'] += 1
                continue
            row_id = offset + i
            source = str(data['ingest_lib'][i])
            sources[source] += 1
            candidate = dict(raw_key=raw, normalized_smiles=smiles, source_row=row_id,
                             spectrum_id='official_' + str(row_id).zfill(9),
                             ingest_lib=source, instrument_type=instrument,
                             adduct=CONFIG['adduct'], collision_energy_ev=ce)
            old = pool.get(raw)
            if old is None or rank(candidate['spectrum_id']) < rank(old['spectrum_id']):
                pool[raw] = candidate
        offset += batch.num_rows
        memory()
        if offset % (CONFIG['arrow_batch_rows'] * 16) == 0:
            print(json.dumps({'stage': 'metadata_scan', 'rows': offset, 'eligible_raw_structures': len(pool), **memory()}), flush=True)
    metadata_audit = dict(status='metadata_scanned_no_fragment_matching', counters=dict(counters),
                          positive_tims_ce_list_length_histogram=dict(ce_sizes),
                          eligible_rows_by_source=dict(sources), eligible_raw_structures=len(pool),
                          elapsed_seconds=time.perf_counter()-start, source_metadata_rows=parquet.metadata.num_rows,
                          exclusions=exclusions, **memory())
    save(OUT / 'metadata_audit.json', metadata_audit)
    # Deterministic before any graph/match statistics are computed.
    chosen, seen, rejected = [], set(), Counter()
    for item in sorted(pool.values(), key=lambda x: (rank(x['raw_key']), x['raw_key'])):
        identity = metric.identity(item['normalized_smiles'])
        if not identity:
            rejected['invalid_official_identity'] += 1
            continue
        if identity in frozen_ids or identity in frozen_raw:
            rejected['frozen_official_identity'] += 1
            continue
        if identity in seen:
            rejected['same_official_identity_alias'] += 1
            continue
        seen.add(identity)
        chosen.append({**item, 'official_identity': identity, 'molecule_id': 'fiora_' + identity})
        if len(chosen) == CONFIG['max_structures']:
            break
    chosen.sort(key=lambda x: (rank('split|' + x['official_identity']), x['official_identity']))
    ntrain = CONFIG['target_train'] if len(chosen) == 500 else int(0.8 * len(chosen))
    for i, item in enumerate(chosen):
        item['split'] = 'train' if i < ntrain else 'development'
        item['group_id'] = i
    result = dict(status='selection_frozen_before_fragment_matching', configuration=CONFIG,
                  source_train_path=str(TRAIN), source_train_bytes=TRAIN.stat().st_size,
                  source_train_sha256=sha(TRAIN), official_rdkit_version=metric.assert_official_rdkit(),
                  structures=len(chosen), spectra=len(chosen), train_structures=ntrain,
                  development_structures=len(chosen)-ntrain, requested_400_100_achieved=len(chosen)==500,
                  rejected_during_canonical_selection=dict(rejected), exclusions=exclusions,
                  metadata_audit_sha256=sha(OUT/'metadata_audit.json'), groups=chosen,
                  ms_nlib_pretraining_exposure='unknown; no unseen-pretraining claim',
                  no_label_quality_selection=True, no_replacement_after_matching=True,
                  final_truth_or_final_queries_read=False, training_performed=False,
                  script_sha256_at_freeze=sha(__file__), **memory())
    save(OUT / 'selection.json', result)
    print(json.dumps({k:v for k,v in result.items() if k not in ['groups','exclusions']}, indent=2), flush=True)

def compiled_mass_map(mol, modes):
    import numpy as np
    directed = mol.edges_as_tuples
    count = len(directed) * 2 * len(modes) + 2
    masses = np.full(count, np.nan, dtype=np.float64)
    forward = np.zeros(count, dtype=np.bool_)
    edge_map = mol.fragmentation_tree.edge_map
    for i, edge in enumerate(directed):
        edge = tuple(edge)
        frags = edge_map.get(edge)
        reverse = False
        if not frags:
            frags = edge_map.get((edge[1], edge[0]))
            reverse = True
        if not frags:
            continue
        for side_i, side in enumerate(['left', 'right']):
            key = ('right' if side == 'left' else 'left') if reverse else side
            frag = frags.get(key)
            if frag is None:
                continue
            for mode_i, mode in enumerate(modes):
                at = i * 2 * len(modes) + side_i * len(modes) + mode_i
                masses[at] = frag.mz[mode]
                forward[at] = edge[0] < edge[1]
    precursor = edge_map[None].mz['[M+H]+']
    masses[-2:] = precursor
    forward[-1] = True
    return masses, forward, precursor

def spectra():
    """Extract fixed rows in an Arrow-only process; Torch never overlaps it."""
    import numpy as np
    import pyarrow as pa
    import pyarrow.parquet as pq
    pa.set_cpu_count(1)
    selection = json.loads((OUT/'selection.json').read_text())
    if (OUT/'input_spectra_index.json').exists():
        raise FileExistsError('Frozen source spectrum extraction already exists')
    folder=OUT/'input_spectra';folder.mkdir(exist_ok=True)
    expected={x['source_row']:x for x in selection['groups']}
    rows=[];running=0;start=time.perf_counter()
    source=pq.ParquetFile(TRAIN)
    columns=['inchikey14','instrument_type','adduct','collision_energy_ev',
             'ms2_mzs','ms2_normalized_intensities','precursor_mz']
    for group_i in range(source.metadata.num_row_groups):
        group_n=source.metadata.row_group(group_i).num_rows
        wanted={r:item for r,item in expected.items() if running<=r<running+group_n}
        if not wanted:
            running+=group_n
            continue
        local=0
        for batch in source.iter_batches(row_groups=[group_i],columns=columns,batch_size=64,use_threads=False):
            positions=sorted(r-running-local for r in wanted if running+local<=r<running+local+batch.num_rows)
            if positions:
                records=batch.take(pa.array(positions,type=pa.int64())).to_pylist()
                for position,record in zip(positions,records):
                    item=expected[running+local+position]
                    assert record['inchikey14']==item['raw_key']
                    assert scalar_ce(record['collision_energy_ev'])==item['collision_energy_ev']
                    assert str(record['instrument_type']).strip().lower()=='timstof' and record['adduct']=='[M+H]+'
                    path=folder/(item['spectrum_id']+'.npz')
                    np.savez_compressed(path,ms2_mzs=np.asarray(record['ms2_mzs'],dtype=np.float64),
                                        ms2_normalized_intensities=np.asarray(record['ms2_normalized_intensities'],dtype=np.float64),
                                        precursor_mz=np.array([record['precursor_mz']],dtype=np.float64))
                    rows.append(dict(source_row=item['source_row'],spectrum_id=item['spectrum_id'],
                                     path=path.relative_to(OUT).as_posix(),sha256=sha(path)))
            local+=batch.num_rows
            memory()
        running+=group_n
    assert len(rows)==len(expected)
    save(OUT/'input_spectra_index.json',dict(status='frozen_spectrum_extraction_completed',
         selection_sha256=sha(OUT/'selection.json'),rows=rows,elapsed_seconds=time.perf_counter()-start,
         source_script_sha256=sha(__file__),no_label_matching=True,**memory()))
    print(json.dumps({'stage':'spectra_extracted','rows':len(rows),'seconds':time.perf_counter()-start,**memory()}),flush=True)

def graphs():
    import numpy as np
    # Imported only for the graph stage; no model initialization, no CUDA context.
    sys.path[:0] = [str(ASSET/'source_checkout'), str(ASSET/'dependencies-linux')]
    import torch
    from rdkit import Chem, RDLogger
    from fiora.GNN.AtomFeatureEncoder import AtomFeatureEncoder
    from fiora.GNN.BondFeatureEncoder import BondFeatureEncoder
    from fiora.GNN.CovariateFeatureEncoder import CovariateFeatureEncoder
    from fiora.MOL.Metabolite import Metabolite
    from fiora.MOL.constants import DEFAULT_MODES
    RDLogger.DisableLog('rdApp.*')
    torch.set_num_threads(1)
    selection = json.loads((OUT/'selection.json').read_text())
    if (OUT/'index.json').exists():
        raise FileExistsError('Graph index exists; preserve completed cache')
    # Fixed before graph quality is measured; replaces unused planned min2-count
    # in the metadata selection config. Selection and its SHA remain unchanged.
    label_contract = dict(policy='at_least_one_nonprecursor_real_fragment_match',
                          minimum_real_fragment_matches=1, low_coverage_threshold=None,
                          replacing_unused_metadata_config='minimum_matches_for_training=2',
                          replacement_reason='Explicit parent instruction before first graph/label run; precursor count duplicates are not fragment supervision',
                          selection_sha256=sha(OUT/'selection.json'), script_sha256=sha(__file__),
                          no_matching_outcomes_seen_at_freeze=True, zero_fragment_rows_preserved_in_original_denominators=True)
    if not (OUT/'label_contract.json').exists():
        save(OUT/'label_contract.json', label_contract)
    if not selection['groups']:
        save(OUT/'index.json', dict(status='no_eligible_metadata_queries', rows=[], selection_sha256=sha(OUT/'selection.json')))
        return
    for folder in ['graphs','evaluation','records']:
        (OUT/folder).mkdir(exist_ok=True)
    categories = dict(instrument=['HCD','timsTOF'], precursor_mode=['[M+H]+','[M-H]-','[M]+','[M]-'])
    atoms = AtomFeatureEncoder(feature_list=['symbol','num_hydrogen','ring_type'])
    bonds = BondFeatureEncoder(feature_list=['bond_type','ring_type'])
    covariates = CovariateFeatureEncoder(feature_list=['collision_energy','molecular_weight','precursor_mode','instrument','element_composition'], sets_overwrite=categories)
    rt_covariates = CovariateFeatureEncoder(feature_list=['molecular_weight','precursor_mode','instrument','element_composition'], sets_overwrite=categories)
    assert covariates.encoding_dim == 19 and rt_covariates.encoding_dim == 18
    expected = {x['source_row']: x for x in selection['groups']}
    extracted=json.loads((OUT/'input_spectra_index.json').read_text())
    assert extracted['selection_sha256']==sha(OUT/'selection.json')
    inputs={r['source_row']:r for r in extracted['rows']}
    assert set(inputs)==set(expected)
    index, csv_rows, start = [], [], time.perf_counter()
    print(json.dumps({'stage':'graph_import_completed',**memory()}),flush=True)
    def process(item, record):
        record_file = OUT/'records'/(item['spectrum_id']+'.json')
        if record_file.exists():
            saved = json.loads(record_file.read_text())
            index.append(saved)
            return
        result = {k:item[k] for k in ['molecule_id','official_identity','raw_key','source_row','spectrum_id','split','group_id','ingest_lib']}
        result.update(status='preparing', graph_path=None, graph_sha256=None, eval_path=None, eval_sha256=None,
                      ms_nlib_pretraining_exposure='unknown', no_replacement=True,
                      native_adduct='[M+H]+', precursor_mode='[M+H]+',
                      instrument_type='timsTOF', collision_energy_ev=item['collision_energy_ev'])
        begin = time.perf_counter()
        try:
            if record['inchikey14'] != item['raw_key'] or scalar_ce(record['collision_energy_ev']) != item['collision_energy_ev']:
                raise ValueError('Metadata source row changed after freeze')
            mz = np.asarray(record['ms2_mzs'], dtype=np.float64)
            intensity = np.asarray(record['ms2_normalized_intensities'], dtype=np.float64)
            if mz.shape != intensity.shape or mz.ndim != 1:
                raise ValueError('Query peak shape mismatch')
            valid = np.isfinite(mz) & np.isfinite(intensity) & (mz > 0) & (intensity >= 0)
            result['original_peak_count'] = int(len(mz))
            result['invalid_peaks_removed'] = int((~valid).sum())
            mz, intensity = mz[valid], intensity[valid]
            if not len(mz) or intensity.sum() <= 0:
                raise ValueError('No positive finite peak intensity')
            mol = Metabolite(item['normalized_smiles'])
            mol.create_molecular_structure_graph()
            mol.compute_graph_attributes(atoms,bonds)
            mol.set_id(item['group_id'])
            mol.set_loss_weight(1.)
            mol.add_metadata(dict(name=item['spectrum_id'], collision_energy=item['collision_energy_ev'],
                                  instrument='timsTOF', precursor_mode='[M+H]+'), covariates, rt_covariates)
            mol.fragment_MOL(depth=1)
            mol.match_fragments_to_peaks(mz.tolist(), intensity.tolist(), tolerance=CONFIG['relative_match_tolerance'])
            stats = {}
            for key,value in mol.match_stats.items():
                number = float(value)
                stats[key] = number if math.isfinite(number) else None
            matched_mask = np.array([float(v) in mol.peak_matches for v in mz], dtype=bool)
            precursor_mz = mol.fragmentation_tree.edge_map[None].mz['[M+H]+']
            precursor_window = max(abs(precursor_mz)*CONFIG['relative_match_tolerance'], CONFIG['native_minimum_absolute_tolerance_da'])
            not_precursor = np.abs(mz-precursor_mz)>precursor_window
            total = float(intensity.sum())
            nonprec_total = float(intensity[not_precursor].sum())
            matched_total = float(intensity[matched_mask].sum())
            matched_nonprec = float(intensity[matched_mask & not_precursor].sum())
            result.update(match_stats=stats, total_peak_intensity=total,
                          matched_peak_intensity=matched_total, unmatched_peak_intensity=total-matched_total,
                          unmatched_peak_fraction=(total-matched_total)/total,
                          nonprecursor_total_intensity=nonprec_total,
                          nonprecursor_matched_intensity=matched_nonprec,
                          nonprecursor_unmatched_intensity=nonprec_total-matched_nonprec,
                          native_matched_intensity_coverage=matched_total/total,
                          nonprecursor_intensity_coverage=matched_nonprec/nonprec_total if nonprec_total>0 else None,
                          native_mass_tolerance_relative=CONFIG['relative_match_tolerance'],
                          native_minimum_absolute_tolerance_da=CONFIG['native_minimum_absolute_tolerance_da'],
                          atoms=mol.MOL.GetNumHeavyAtoms(), directed_edges=len(mol.edges_as_tuples))
            if mol.match_stats['num_non_precursor_matches'] < CONFIG['minimum_real_fragment_matches_for_training']:
                result['status'] = 'filtered_no_real_fragment_supervision'
            elif not torch.isfinite(mol.compiled_probsALL).all() or mol.compiled_probsALL.sum() <= 0:
                result['status'] = 'filtered_invalid_compiled_target'
            else:
                graph = mol.as_geometric_data(with_labels=True).to_dict()
                assert graph['static_edge_features'].shape[1] == 19
                assert graph['static_graph_features'].shape[1] == 19
                assert graph['static_rt_features'].shape[1] == 18
                assert torch.all(graph['static_graph_features'][:,7] == 1)
                assert torch.all(graph['static_graph_features'][:,6] == 0)
                # Plain tensor dict allows safe weights_only loading with no PyG pickle class.
                graph_path = OUT/'graphs'/(item['spectrum_id']+'.pt')
                torch.save(graph, graph_path)
                masses, forward, theoretical_precursor = compiled_mass_map(mol,DEFAULT_MODES)
                assert len(masses) == graph['compiled_probsALL'].numel()
                eval_path = OUT/'evaluation'/(item['spectrum_id']+'.npz')
                np.savez_compressed(eval_path, compiled_mz=masses, compiled_forward_mask=forward,
                    query_mz=mz, query_intensity=intensity,
                    precursor_mz=np.array([theoretical_precursor], dtype=np.float64),
                    measured_precursor_mz=np.array([record['precursor_mz']], dtype=np.float64),
                    query_nonprecursor_mask=not_precursor)
                result.update(status='cache_ready', graph_path=graph_path.relative_to(OUT).as_posix(),
                              graph_sha256=sha(graph_path), eval_path=eval_path.relative_to(OUT).as_posix(),
                              eval_sha256=sha(eval_path), graph_keys=sorted(graph),
                              target_elements=graph['compiled_probsALL'].numel())
                del graph
                csv_rows.append(dict(SMILES=item['normalized_smiles'],group_id=item['group_id'],
                                     datasplit='training' if item['split']=='train' else 'validation',
                                     summary=json.dumps(dict(name=item['spectrum_id'], collision_energy=item['collision_energy_ev'], instrument='timsTOF', precursor_mode='[M+H]+')),
                                     peaks=json.dumps(dict(mz=mz.tolist(),intensity=intensity.tolist()))))
            del mol
        except Exception as exc:
            result.update(status='graph_or_label_error', error_type=type(exc).__name__, error=str(exc),traceback=traceback.format_exc())
        result['prepare_seconds']=time.perf_counter()-begin
        gc.collect()
        result.update(memory())
        save(record_file,result)
        index.append(result)
        print(json.dumps({'stage':'graph_label','done':len(index),'total':len(expected),'split':item['split'],
                          'status':result['status'],'coverage_wo_prec':result.get('nonprecursor_intensity_coverage'),**memory()}),flush=True)
    for item in selection['groups']:
        pin=inputs[item['source_row']]
        path=OUT/pin['path']
        assert sha(path)==pin['sha256']
        with np.load(path,allow_pickle=False) as arrays:
            record=dict(inchikey14=item['raw_key'],collision_energy_ev=[item['collision_energy_ev']],
                        ms2_mzs=arrays['ms2_mzs'],ms2_normalized_intensities=arrays['ms2_normalized_intensities'],
                        precursor_mz=float(arrays['precursor_mz'][0]))
            process(item,record)
    if len(index)!=len(expected):
        raise ValueError('Missing frozen source rows during graph pass')
    def summary(split):
        rows=[r for r in index if r['split']==split]
        values=[r['nonprecursor_intensity_coverage'] for r in rows if r.get('nonprecursor_intensity_coverage') is not None]
        all_values=[r['native_matched_intensity_coverage'] for r in rows if r.get('native_matched_intensity_coverage') is not None]
        return dict(original_structure_denominator=len(rows),original_spectrum_denominator=len(rows),
                    cache_ready=sum(r['status']=='cache_ready' for r in rows),status_counts=dict(Counter(r['status'] for r in rows)),
                    coverage_wo_prec_available=len(values),coverage_wo_prec_mean=float(np.mean(values)) if values else None,
                    coverage_wo_prec_median=float(np.median(values)) if values else None,
                    coverage_wo_prec_p10=float(np.quantile(values,.1)) if values else None,
                    coverage_wo_prec_ge_05=sum(v>=.5 for v in values),coverage_wo_prec_ge_01=sum(v>=.1 for v in values),
                    all_peak_coverage_mean=float(np.mean(all_values)) if all_values else None,
                    total_unmatched_peak_intensity=sum(r.get('unmatched_peak_intensity',0.) for r in rows),
                    total_nonprecursor_unmatched_peak_intensity=sum(r.get('nonprecursor_unmatched_intensity',0.) for r in rows))
    artifact=dict(status='completed_native_graph_and_label_cache',configuration=CONFIG,
                  selection_sha256=sha(OUT/'selection.json'),rows=index,
                  label_contract_sha256=sha(OUT/'label_contract.json'),
                  train=summary('train'),development=summary('development'),
                  elapsed_seconds=time.perf_counter()-start,
                  feature_boundary='No identity, split, source_row, truth, matching-arm or conditions in native model features; group_id is DataLoader grouping metadata only',
                  evaluation_npz_boundary='Query spectra/masses are sidecars for evaluation only, not graph features',
                  ms_nlib_pretraining_exposure='unknown',training_performed=False,
                  source_script_sha256=sha(__file__),**memory())
    save(OUT/'index.json',artifact)
    if csv_rows:
        with (OUT/'native_training.csv').open('w',newline='',encoding='utf-8') as handle:
            writer=csv.DictWriter(handle,fieldnames=['SMILES','group_id','datasplit','summary','peaks'])
            writer.writeheader();writer.writerows(csv_rows)
    print(json.dumps({k:v for k,v in artifact.items() if k!='rows'},indent=2),flush=True)

def main():
    global RUNTIME_RSS_LIMIT
    parser=argparse.ArgumentParser()
    parser.add_argument('--stage',choices=['metadata','spectra','graphs'],required=True)
    parser.add_argument('--rss-limit-mib',type=int,default=1024)
    args=parser.parse_args()
    if args.rss_limit_mib not in (1024,1536):
        raise ValueError('Only fixed approved 1024/1536 MiB process budgets allowed')
    RUNTIME_RSS_LIMIT=args.rss_limit_mib*1024**2
    if args.stage=='graphs':
        save(OUT/'runtime_resources.json',dict(stage='graphs',worker_count=1,
             rss_limit_bytes=RUNTIME_RSS_LIMIT,selection_sha256=sha(OUT/'selection.json'),
             earlier_1gib_failure='graphs_failure_attempt1_arrow_rss.json',
             reason='Root authorized up to1.5GiB for Torch import baseline; Arrow extraction runs in separate exited process',
             source_script_sha256=sha(__file__),no_selection_or_label_policy_change=True))
    os.environ['OMP_NUM_THREADS']='1';os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1'
    try:
        if args.stage=='metadata':metadata()
        elif args.stage=='spectra':spectra()
        else:graphs()
    except Exception as exc:
        save(OUT/(args.stage+'_failure.json'),dict(status='failed',stage=args.stage,error_type=type(exc).__name__,
             error=str(exc),traceback=traceback.format_exc(),source_script_sha256=sha(__file__)))
        raise

if __name__=='__main__':main()
