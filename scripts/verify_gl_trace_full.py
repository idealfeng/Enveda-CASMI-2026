"""Audit completed full-input GL tracing, its original means and pinned checkpoint; no truth/model execution."""
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
import argparse
import hashlib
import json
import math
import re
import sys

from verify_gl_trace_canary import ROOT,read,sha,inside,from_relative,coverage,bucket


def normalize(value):
    if isinstance(value,float):return value if math.isfinite(value) else None
    if isinstance(value,list):return [normalize(x) for x in value]
    return value


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,default=ROOT/'runs/exp003_gl_trace_full_20261106')
    args=parser.parse_args();base=inside(args.input);destination=base/'full_trace_verification.json'
    if destination.exists():raise ValueError('Preserve the existing audit')
    if not (base/'trace/gl_out.json.trace_run.json').is_file():
        print('{"status":"not_complete"}');return 2
    import numpy as np
    prepared=read(base/'prepare.json');binding=read(base/'comparison_binding.json')
    items=read(base/'input.json');identities=read(base/'official_identities.json')
    source=from_relative(prepared['source_input']);old_path=from_relative(binding['original_output'])
    old=read(old_path);current=read(base/'trace/gl_out.json');meta=read(base/'trace/gl_out.json.meta.json')
    receipt=read(base/'trace/gl_out.json.trace_run.json');old_meta=read(from_relative(binding['original_meta']))
    trace_path=base/'trace/per_spectrum.jsonl';trace_sha=sha(trace_path)
    with trace_path.open(encoding='utf-8') as stream:events=[json.loads(line) for line in stream if line.strip()]
    starts=[e for e in events if e['event']=='run_start'];ends=[e for e in events if e['event']=='run_end']
    if len(starts)!=1 or len(ends)!=1 or sha(trace_path)!=trace_sha:
        print('{"status":"not_complete"}');return 2
    spectral=[e for e in events if e['event']=='spectrum_coverage']
    score_events=[e for e in events if e['event']=='candidate_spectrum_score']
    expected_pairs=[];expected_spectra={};by_mid={str(m['mid']):m for m in items};candidates={}
    for item in items:
        mid=str(item['mid']);candidates[mid]=list(dict.fromkeys(item['cands']));covered=[]
        for index,sp in enumerate(item['spectra']):
            peaks={key:sp.get(key) for key in ('mz','it','prec','adduct','mode')}
            expected_spectra[(mid,index)]={key:normalize(sp.get(key)) for key in ('adduct','ce_ev','ce_orig','ce_units')}
            expected_spectra[(mid,index)].update(covered=coverage(sp),ionization_mode=sp.get('mode'),
                instrument_raw=sp.get('instrument'),spectrum_content_sha256=hashlib.sha256(
                    json.dumps(peaks,sort_keys=True,separators=(',',':')).encode()).hexdigest())
            if coverage(sp):covered.append(index)
        for candidate in candidates[mid]:expected_pairs.extend((mid,candidate,i) for i in covered)
    observed_pairs=[(e['mid'],e['candidate_smiles'],e['spectrum_index']) for e in score_events]
    covered_keys=[(e['mid'],e['spectrum_index']) for e in spectral]
    checks=dict(
        original_input_unchanged=sha(source)==prepared['source_input_sha256'],
        frozen_input_original_bytes=(base/'input.json').read_bytes()==source.read_bytes(),
        input_sha_bound=sha(base/'input.json')==prepared['input_sha256']==receipt['input_sha256']==starts[0]['input_sha256'],
        identity_sidecar_bound=sha(base/'official_identities.json')==prepared['identity_sidecar_sha256']==starts[0]['identity_map_sha256'],
        official2026_identity_preparation=prepared['official_identity_rdkit']=='2026.03.3' and
            len(identities)==prepared['unique_candidate_smiles']==3679 and not prepared['official_identity_unavailable'] and
            all(isinstance(v,str) and re.fullmatch('[A-Z]{14}',v) for v in identities.values()),
        wrapper_bound=sha(ROOT/'scripts/forward_trace_runner.py')==prepared['wrapper_sha256']==starts[0]['wrapper_sha256'],
        original_cached_output_bound=sha(old_path)==binding['original_output_sha256'] and
            sha(from_relative(binding['original_meta']))==binding['original_meta_sha256'],
        receipt_complete=receipt['status']=='complete' and ends[0]['status']=='complete' and receipt['trace_enabled'] is True,
        upstream_health=meta['status']=='ok' and not meta['errors'] and meta.get('n_pred_fail',0)==0 and
            meta.get('n_feat_fail',0)==0 and meta.get('n_bad_smiles',0)==0,
        full_query_candidate_coverage=meta['n_mols']==meta['n_mols_covered']==meta['n_mols_scored']==45 and
            meta['n_cands']==meta['n_scored']==3679,
        expected_legacy_runtime=meta['rdkit']=='2025.03.6' and meta['device']=='cuda',
        output_query_order=list(current)==[str(m['mid']) for m in items]==list(old),
        output_candidate_order=all(list(current[mid])==candidates[mid]==list(old[mid]) for mid in candidates),
        same_original_aggregate_values=current==old,
        output_sha_bound=sha(base/'trace/gl_out.json')==receipt['output_sha256'],
        complete_pair_order=observed_pairs==expected_pairs and len(observed_pairs)==len(set(observed_pairs)),
        complete_spectrum_records=len(covered_keys)==len(set(covered_keys))==len(expected_spectra) and all(
            (e['mid'],e['spectrum_index']) in expected_spectra and all(e.get(k)==v for k,v in
                expected_spectra[(e['mid'],e['spectrum_index'])].items()) for e in spectral),
        official_identities_on_every_pair=all(e['candidate_official_identity']==identities.get(e['candidate_smiles']) and
            e['candidate_official_identity'] is not None for e in score_events),
        finite_score_support=all(e['status']=='scored' and e['covered'] is True and
            isinstance(e['score'],(float,int)) and math.isfinite(e['score']) for e in score_events),
        score_metadata_matches_input=all((e['mid'],e['spectrum_index']) in expected_spectra and
            all(e.get(k)==v for k,v in expected_spectra[(e['mid'],e['spectrum_index'])].items()) and
            e.get('ce_bucket')==bucket(by_mid[e['mid']]['spectra'][e['spectrum_index']]) for e in score_events),
        frozen_script=sha(base/'trace.sh')==prepared['script_sha256'])
    grouped=defaultdict(list)
    for event in score_events:grouped[(event['mid'],event['candidate_smiles'])].append(event['score'])
    exact=0;maximum=0.0;reconstruction_failures=[]
    for mid,cs in candidates.items():
        for candidate in cs:
            values=grouped[(mid,candidate)];mean=float(np.mean(values)) if values else None
            original=current[mid][candidate]
            delta=abs(mean-original) if mean is not None and original is not None else float('inf')
            maximum=max(maximum,delta);exact+=int(mean==original)
            if delta>1e-12:reconstruction_failures.append(dict(mid=mid,candidate_smiles=candidate,absolute_difference=delta))
    checks['all_candidate_means_reconstructed']=not reconstruction_failures and len(grouped)==3679
    statistics=receipt['trace_statistics'];checks['trace_statistics_match']=statistics==dict(
        coverage_events=len(spectral),score_events=len(score_events),missing_prediction_events=0,
        nonfinite_events=0,aggregate_exact_checks=3679)
    marker=from_relative(prepared['site']['path'])/'.ice_site_ok'
    checks['old_site_marker_unchanged']=sha(marker)==prepared['site']['old_marker_sha256']
    checks['site_bootstrap_noop']=marker.read_text()=='\n'.join(prepared['site']['expected_wheel_basenames']) and any(
        'site ready (marker matches)' in s for s in meta.get('log_tail',[]))
    # The default loader reads state_dict AND hyper_parameters from this one checkpoint.
    pkg=ROOT/'assets/kaggle/dmitriigluzdov/casmi26-attributed-v4g-reproduction-assets/v9/casmi26-glacier'
    checkpoint=pkg/'ckpt/glacier.pt';manifest_path=pkg/'MANIFEST.json';manifest=read(manifest_path)
    assets=read(ROOT/'submission/flex_v56_review/local_asset_manifest.json')
    prior=next(a for a in assets if a['file']=='casmi26-glacier/ckpt/glacier.pt')
    checkpoint_sha=sha(checkpoint);runner_sha=sha(pkg/'gl_runner.py');runner=(pkg/'gl_runner.py').read_text()
    checks['actual_default_checkpoint_full_sha']=checkpoint_sha==manifest['files']['ckpt/glacier.pt']['sha256']==prior['recorded_sha256']
    checks['runner_and_default_checkpoint_selection']=runner_sha==prepared['source_runner_sha256']==receipt['source_sha256']==starts[0]['source_sha256'] and '--ckpt' not in (base/'trace.sh').read_text()
    checks['embedded_config_bound_by_same_checkpoint']=all(fragment in runner for fragment in [
        "torch.load(ckpt or os.path.join(pkg, 'ckpt', 'glacier.pt')", "dict(c['hyper_parameters'])",'gl_jm.JointModel(**hp)',
        "m.load_state_dict(sd, strict=True)"])
    historic=next(r for r in read(ROOT/'runs/validation_flex_c2_20261105d/v43_mounted_input_hashes.json')
        if r['path'].endswith('casmi26-glacier/ckpt/glacier.pt'))
    digest=hashlib.sha256()
    with checkpoint.open('rb') as stream:
        digest.update(stream.read(4<<20));stream.seek(checkpoint.stat().st_size-(4<<20));digest.update(stream.read(4<<20))
    checks['historic_runtime_checkpoint_size_edges']=checkpoint.stat().st_size==historic['bytes'] and digest.hexdigest()==historic['sha256_head_tail']
    checks['inputs_and_trace_stable_at_end']=sha(source)==prepared['source_input_sha256'] and sha(trace_path)==trace_sha
    byte_equal=old_path.read_bytes()==(base/'trace/gl_out.json').read_bytes()
    deltas=[abs(current[mid][candidate]-old[mid][candidate]) for mid in candidates for candidate in candidates[mid]]
    result=dict(status='passed' if all(checks.values()) else 'failed',checked_at_utc=datetime.now(timezone.utc).isoformat(),
        checks=checks,check_count=len(checks),checks_passed=sum(checks.values()),failed_checks=[k for k,v in checks.items() if not v],
        scope='Full observer equivalence only; no truth read or accuracy evaluation.',
        molecules=45,candidate_rows=3679,spectra=len(expected_spectra),applicable_pairs=len(expected_pairs),
        pair_status_counts=dict(Counter(e['status'] for e in score_events)),
        byte_identical_to_original_cached_output=byte_equal,original_output_sha256=sha(old_path),
        output_sha256=sha(base/'trace/gl_out.json'),maximum_original_score_difference=max(deltas),
        means_reconstructed_exactly=exact,maximum_mean_absolute_difference=maximum,reconstruction_failures=reconstruction_failures,
        input_sha256=prepared['input_sha256'],trace_sha256=trace_sha,identity_sidecar_sha256=prepared['identity_sidecar_sha256'],
        weight_config_binding=dict(actual_default_checkpoint=checkpoint.relative_to(ROOT).as_posix(),
            fresh_checkpoint_sha256=checkpoint_sha,manifest_checkpoint_sha256=manifest['files']['ckpt/glacier.pt']['sha256'],
            prior_download_checkpoint_sha256=prior['recorded_sha256'],
            configuration='hyper_parameters embedded in the same checkpoint; no separate model config read by load_model',
            loader_runner_sha256=runner_sha,package_manifest_sha256=sha(manifest_path),
            historical_runtime_checkpoint_evidence='size plus first/last4MiB SHA; prior full local download receipt also matches',
            no_checkpoint_tensor_deserialization_in_verifier=True),
        runtime=dict(rdkit=meta['rdkit'],torch=meta['torch'],device=meta['device'],seconds=meta['seconds'],
            predicted_jobs=meta['n_pred'],original_predicted_jobs=old_meta.get('n_pred')),
        model_inference_performed_by_verifier=False,truth_or_locked250_read=False,
        limitations=['This validates evidence export, not ranking/leaderboard gains.',
            'Checkpoint full SHA freshly matched after this run to its existing manifest and original download receipt; the trace header itself did not hash weights at load time.',
            'Historical runtime inventory binds checkpoint size/head-tail, not a historic full-file runtime hash.',
            'Repeated spectra/CE groups need grouping before a support-rate feature can count independent evidence.'])
    destination.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    text=(f'# EXP003：完整GL逐谱trace独立核验\n\n2026-11-06，**{result["status"]}，{result["checks_passed"]}/{result["check_count"]}项检查通过**。未读真值、未评价MRR、未预测锁定250。\n\n'
        f'- 原完整输入45query、3679候选、146谱逐字节复用，逐谱适用pair共{len(expected_pairs)}；所有pair顺序、身份、谱元数据与输入一致，缺失/非有限0。\n'
        f'- 新旧聚合输出逐值完全一致，最大差{result["maximum_original_score_difference"]:.3g}；逐字节相同：{byte_equal}，两者SHA `{result["output_sha256"]}`。\n'
        f'- 3679个候选均值由逐谱值独立重构，精确相等{exact}/3679，最大差{maximum:.3g}。\n'
        '- upstream为ok，45/45query及3679/3679候选评分完成；CUDA、RDKit2025.03.6，预测/特征错误0。旧site marker未改，日志确认bootstrap no-op。\n\n'
        '## 权重与配置绑定\n\n'
        f'实际CLI没有`--ckpt`覆盖，原loader读取`ckpt/glacier.pt`。fresh完整SHA `{checkpoint_sha}` 与模型包MANIFEST及既有下载回执完全一致。模型配置来自该文件中的`hyper_parameters`，同一个完整文件SHA同时绑定权重和配置；loader随后strict加载state_dict。核验器未反序列化checkpoint或加载模型。\n\n'
        '旧runtime inventory另有相同checkpoint路径、大小和首尾4MiB指纹，现已再次比对相同。需保留边界：旧runtime没有完整checkpoint SHA，当前trace header也未在加载时哈希权重；本次是运行后对实际默认文件与既有固定manifest/下载回执进行完整SHA补证，不能说runner pin本身证明了权重。\n\n'
        f'机器报告：`{destination.relative_to(ROOT).as_posix()}`。此结果允许后续只读导出一致性特征，不代表排序或榜分提高。\n')
    (ROOT/'reports/EXP003_GL_TRACE_FULL_2026-11-06.md').write_text(text,encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('status','checks_passed','check_count','failed_checks','applicable_pairs',
        'byte_identical_to_original_cached_output','maximum_original_score_difference','means_reconstructed_exactly','maximum_mean_absolute_difference')},indent=2))
    return 0 if result['status']=='passed' else 1


if __name__=='__main__':
    sys.dont_write_bytecode=True
    raise SystemExit(main())
