"""Independently audit an already-complete GL observer canary; never infer or read truth."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import math
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inside(path):
    path = path.resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError('All audit paths must remain in the D: workspace')
    return path


def from_relative(value):
    return inside(ROOT/value.replace('\\','/'))


def coverage(sp):
    mode=sp.get('mode')
    positive=mode==1 or isinstance(mode,str) and mode.lower() in ('positive','pos','+','1')
    return bool(positive and sp.get('adduct') in ('[M+H]+','[M+Na]+'))


def bucket(sp):
    import numpy as np
    if 'ce_units' in sp or 'ce_ev' in sp:
        if sp.get('ce_units')=='NCE':
            values=[float(x) for x in re.findall(r'[0-9]+\.?[0-9]*',str(sp.get('ce_orig')))]
        else:
            values=sp.get('ce_ev')
        ce=float(np.mean(values)) if values is not None and len(values) else float('nan')
    else:
        value=sp.get('ce');ce=float(value) if value is not None and math.isfinite(float(value)) else float('nan')
    if not math.isfinite(ce):return None
    return max(5.0,float(np.round(ce/5.0)*5.0))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,default=ROOT/'runs/exp003_gl_trace_canary_20261106')
    args=parser.parse_args();base=inside(args.input)
    destination=base/'canary_verification.json'
    if destination.exists():
        raise ValueError('Preserve the existing independent audit instead of overwriting it')
    required=[base/'prepare.json',base/'input.json',base/'official_identities.json',
        *[base/arm/name for arm in ('control','trace') for name in
            ('gl_out.json','gl_out.json.meta.json','gl_out.json.trace_run.json')],base/'trace/per_spectrum.jsonl']
    missing=[str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    if missing:
        print(json.dumps(dict(status='not_complete',missing=missing),indent=2));return 2
    import numpy as np
    from validation import metric
    rdkit=metric.assert_official_rdkit()
    prepared=read(base/'prepare.json');items=read(base/'input.json');identities=read(base/'official_identities.json')
    source=from_relative(prepared['source_input']);source_items=read(source)
    original_by_mid={str(item['mid']):item for item in source_items}
    original_runner=ROOT/'assets/kaggle/dmitriigluzdov/casmi26-attributed-v4g-reproduction-assets/v9/casmi26-glacier/gl_runner.py'
    output={arm:read(base/arm/'gl_out.json') for arm in ('control','trace')}
    meta={arm:read(base/arm/'gl_out.json.meta.json') for arm in ('control','trace')}
    receipts={arm:read(base/arm/'gl_out.json.trace_run.json') for arm in ('control','trace')}
    with (base/'trace/per_spectrum.jsonl').open(encoding='utf-8') as stream:
        events=[json.loads(line) for line in stream if line.strip()]
    starts=[e for e in events if e['event']=='run_start'];ends=[e for e in events if e['event']=='run_end']
    spectra=[e for e in events if e['event']=='spectrum_coverage']
    scores=[e for e in events if e['event']=='candidate_spectrum_score']
    checks={
        'prepared_input_sha':sha(base/'input.json')==prepared['input_sha256'],
        'original_source_input_unchanged':sha(source)==prepared['source_input_sha256'],
        'official_identity_sidecar_sha':sha(base/'official_identities.json')==prepared['identity_sidecar_sha256'],
        'original_gl_runner_unchanged':sha(original_runner)==prepared['upstream_runner_sha256'],
        'wrapper_unchanged_since_preparation':sha(ROOT/'scripts/forward_trace_runner.py')==prepared['wrapper_sha256'],
        'two_queries_sixteen_candidates':len(items)==2 and sum(len(item['cands']) for item in items)==16,
        'source_fields_and_candidate_prefix_preserved':all(
            item==dict(original_by_mid[str(item['mid'])],cands=original_by_mid[str(item['mid'])]['cands'][:8]) for item in items),
        'official2026_identity_values':all(metric.identity(smiles)==key for smiles,key in identities.items()),
        'control_and_trace_input_source_binding':all(
            value['input_sha256']==prepared['input_sha256'] and value['source_sha256']==prepared['upstream_runner_sha256']
            and value['status']=='complete' and value['upstream_status']=='ok' for value in receipts.values()),
        'control_and_trace_modes':receipts['control']['trace_enabled'] is False and receipts['trace']['trace_enabled'] is True,
        'output_bytes_identical':(base/'control/gl_out.json').read_bytes()==(base/'trace/gl_out.json').read_bytes(),
        'output_json_identical':output['control']==output['trace'],
        'output_receipt_shas':all(sha(base/arm/'gl_out.json')==receipts[arm]['output_sha256'] for arm in receipts),
        'upstream_health':all(value['status']=='ok' and not value['errors'] and value.get('n_pred_fail',0)==0
            and value.get('n_feat_fail',0)==0 and value.get('n_bad_smiles',0)==0 for value in meta.values()),
        'upstream_full_coverage':all(value['n_mols']==value['n_mols_covered']==value['n_mols_scored']==2
            and value['n_cands']==value['n_scored']==16 for value in meta.values()),
        'legacy2025_cuda_environment':all(value['rdkit']=='2025.03.6' and value['device']=='cuda' for value in meta.values()),
        'upstream_prediction_counts_equal':all(meta['control'][key]==meta['trace'][key]
            for key in ('n_pred','n_mols_covered','n_mols_scored','n_cands','n_scored')),
        'trace_start_and_end_complete':len(starts)==len(ends)==1 and ends[0]['status']=='complete',
    }
    if len(starts)==1:
        checks['trace_header_bindings']=all(starts[0][key]==prepared[reference] for key,reference in
            [('source_sha256','upstream_runner_sha256'),('input_sha256','input_sha256'),
             ('wrapper_sha256','wrapper_sha256'),('identity_map_sha256','identity_sidecar_sha256')])
    expected_pairs=[];expected_spectra={};expected_order={};ce_groups=set()
    for item in items:
        mid=str(item['mid']);expected_order[mid]=list(dict.fromkeys(item['cands']))
        covered_indices=[]
        for index,sp in enumerate(item['spectra']):
            payload={key:sp.get(key) for key in ('mz','it','prec','adduct','mode')}
            expected_spectra[(mid,index)]=dict(covered=coverage(sp),adduct=sp.get('adduct'),
                ionization_mode=sp.get('mode'),instrument_raw=sp.get('instrument'),
                ce_ev=sp.get('ce_ev'),ce_orig=sp.get('ce_orig'),ce_units=sp.get('ce_units'),
                spectrum_content_sha256=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest())
            if coverage(sp):
                covered_indices.append(index);ce_groups.add((mid,bucket(sp)))
        for candidate in expected_order[mid]:
            expected_pairs.extend((mid,candidate,index) for index in covered_indices)
    checks['output_query_and_candidate_order']=all(list(value)==[str(item['mid']) for item in items]
        and all(list(value[mid])==candidates for mid,candidates in expected_order.items()) for value in output.values())
    spectrum_keys=[(e['mid'],e['spectrum_index']) for e in spectra]
    checks['all_spectrum_coverage_records_exact']=len(spectrum_keys)==len(set(spectrum_keys))==len(expected_spectra) and all(
        (event['mid'],event['spectrum_index']) in expected_spectra and all(event.get(key)==value for key,value in
        expected_spectra[(event['mid'],event['spectrum_index'])].items()) for event in spectra)
    pairs=[(e['mid'],e['candidate_smiles'],e['spectrum_index']) for e in scores]
    checks['all_applicable_pairs_once_in_original_order']=pairs==expected_pairs and len(pairs)==len(set(pairs))
    checks['trace_identities_match_official_sidecar']=all(e['candidate_official_identity']==identities.get(e['candidate_smiles'])
        and e['candidate_official_identity'] is not None for e in scores)
    checks['all_score_events_finite_and_covered']=all(e['status']=='scored' and e['covered'] is True
        and isinstance(e['score'],(float,int)) and math.isfinite(e['score']) for e in scores)
    checks['score_spectrum_metadata_matches_coverage']=all(
        (e['mid'],e['spectrum_index']) in expected_spectra and all(e.get(key)==value for key,value in
        expected_spectra[(e['mid'],e['spectrum_index'])].items()) and e.get('ce_bucket')==bucket(items[
            next(i for i,m in enumerate(items) if str(m['mid'])==e['mid'])]['spectra'][e['spectrum_index']]) for e in scores)
    grouped=defaultdict(list)
    for event in scores:grouped[(event['mid'],event['candidate_smiles'])].append(event['score'])
    reconstructed=[]
    for mid,candidates in expected_order.items():
        for candidate in candidates:
            values=grouped[(mid,candidate)]
            mean=float(np.mean(values)) if values else None;original=output['control'][mid][candidate]
            delta=abs(mean-original) if mean is not None and original is not None else None
            reconstructed.append(dict(mid=mid,candidate_smiles=candidate,finite_spectra=len(values),
                reconstructed_mean=mean,original_score=original,exact=mean==original,absolute_difference=delta))
    checks['all_sixteen_means_reconstructed']=len(reconstructed)==16 and all(r['absolute_difference'] is not None
        and r['absolute_difference']<=1e-12 for r in reconstructed)
    statistics=receipts['trace']['trace_statistics']
    checks['trace_statistics_match_file']=statistics==dict(coverage_events=len(spectra),score_events=len(scores),
        missing_prediction_events=sum(e['status']=='prediction_missing' for e in scores),
        nonfinite_events=sum(e['status']=='nonfinite_similarity' for e in scores),aggregate_exact_checks=16)
    site=from_relative(prepared['site']['path']);marker=site/'.ice_site_ok'
    checks['old_site_marker_unchanged']=sha(marker)==prepared['site']['old_marker_sha256']
    checks['site_bootstrap_noop_confirmed']=marker.read_text()=='\n'.join(prepared['site']['expected_wheel_basenames']) and all(
        any('site ready (marker matches)' in line for line in value.get('log_tail',[])) for value in meta.values())
    checks['frozen_commands_unchanged']=all(sha(base/(arm+'.sh'))==digest for arm,digest in prepared['generated_script_sha256'].items())
    result=dict(status='passed' if all(checks.values()) else 'failed',checked_at_utc=datetime.now(timezone.utc).isoformat(),
        scope='Observation equivalence canary only; no truth or ranking-performance evaluation.',checks=checks,
        check_count=len(checks),checks_passed=sum(checks.values()),failed_checks=[name for name,ok in checks.items() if not ok],
        molecules=len(items),candidate_rows=16,spectra=len(expected_spectra),applicable_pairs=len(expected_pairs),
        ce_groups=len(ce_groups),trace_records=len(events),event_counts=dict(Counter(e['event'] for e in events)),
        official_identity_rdkit=rdkit,forward_rdkit=meta['trace']['rdkit'],device=meta['trace']['device'],
        output_sha256=sha(base/'control/gl_out.json'),input_sha256=sha(base/'input.json'),
        trace_sha256=sha(base/'trace/per_spectrum.jsonl'),means_reconstructed_exactly=sum(r['exact'] for r in reconstructed),
        maximum_mean_absolute_difference=max(r['absolute_difference'] for r in reconstructed if r['absolute_difference'] is not None),
        mean_reconstructions=reconstructed,elapsed_seconds_by_arm={arm:value['seconds'] for arm,value in meta.items()},
        predicted_jobs_by_arm={arm:value['n_pred'] for arm,value in meta.items()},
        model_inference_performed_by_verifier=False,truth_or_locked250_read=False,
        limitations=['This canary tests instrumentation, not accuracy or leaderboard gains.',
            'Two queries were chosen by spectrum/CE metadata and candidate count, with no truth consulted.',
            'Repeated CE groups or duplicate spectra must not become independent votes in later feature design.',
            'Old input and site marker hashes are unchanged; the verifier does not hash every installed site file.',
            'Different wall times include model loading and are not an isolated trace-overhead benchmark.'])
    destination.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    report=ROOT/'reports/EXP003_GL_TRACE_CANARY_2026-11-06.md'
    text=(f'# EXP003：GL逐谱观测等价检查\n\n2026-11-06。独立只读核验：**{result["status"]}，{result["checks_passed"]}/{result["check_count"]}项通过**。'
        '这里只检查trace观测是否改变原计算，没有读取真值、评估排序或预测锁定250。\n\n'
        f'- 2个query、16个候选、17张原始H+谱、15个不同query/CE组；适用候选—谱对为{len(expected_pairs)}，不是跨query的笛卡尔积。\n'
        '- control与trace输出字节、JSON数值以及query/候选顺序完全一致。\n'
        f'- 逐谱记录{len(scores)}条，覆盖记录{len(spectra)}条；无重复或缺失pair，官方2026身份映射全部一致。\n'
        f'- 16个候选均值均可由逐谱值重构；独立重构精确相等{result["means_reconstructed_exactly"]}/16，最大差{result["maximum_mean_absolute_difference"]:.3g}。\n'
        '- 两臂均CUDA、RDKit2025.03.6，模型status=ok、2/2分子与16/16候选评分完成，预测/特征错误0；每臂120个预测job。\n'
        '- 原45分子输入、冻结canary输入、官方身份sidecar、GL原源码、wrapper、执行脚本和旧site marker哈希均符合准备回执。两臂日志均确认site marker匹配，bootstrap直接复用，未重新安装。\n\n'
        f'输出SHA：`{result["output_sha256"]}`。原始独立检查为`{destination.relative_to(ROOT).as_posix()}`；准备回执与两臂产物在同一目录。\n\n'
        '该结果只允许进入逐谱一致性特征设计，不能据此声称MRR或Public Score提高。谱图记录和CE组也不自动等于独立证据；后续须处理重复谱。两次总耗时含模型装载，不能当作纯trace开销对照。\n')
    report.write_text(text,encoding='utf-8')
    print(json.dumps({key:result[key] for key in ('status','check_count','checks_passed','failed_checks','applicable_pairs',
        'means_reconstructed_exactly','maximum_mean_absolute_difference','output_sha256')},indent=2))
    return 0 if result['status']=='passed' else 1


if __name__=='__main__':
    sys.dont_write_bytecode=True
    raise SystemExit(main())
