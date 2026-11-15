"""Prepare dated bounded-subset dispatcher and source-bound gain watcher copies."""
from pathlib import Path
import ast
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'scripts'


def install(name, source):
    ast.parse(source)
    path = SCRIPTS / name
    if path.exists():
        raise FileExistsError('Preserve prepared control source: ' + name)
    path.write_text(source, encoding='utf-8')


def main():
    dispatch = (SCRIPTS / 'dispatch_fixed_batch_20261109.py').read_text(encoding='utf-8')
    old = "if len(manifest['branches'])!=5 or manifest['max_submissions']!=5:raise ValueError('A fixed five-branch manifest is required')"
    new = "if not 1<=len(manifest['branches'])<=5 or manifest['max_submissions']!=5:raise ValueError('A fixed one-to-five branch subset with total batch cap five is required')"
    assert dispatch.count(old) == 1
    dispatch = dispatch.replace(old, new)
    old = "return sum((engine.branch_state(manifest,b)/'submission.json').exists() for b in manifest['branches'])"
    new = "return sum(1 for p in state.glob('*/submission.json') if p.is_file())"
    assert dispatch.count(old) == 1
    dispatch = dispatch.replace(old, new).replace('Dispatch a fixed five-branch batch', 'Dispatch a fixed one-to-five branch subset; count all batch claims')
    install('dispatch_subset_batch_20261112.py', dispatch)

    review = (SCRIPTS / 'review_fixed_batch_dispatch_20261109.py').read_text(encoding='utf-8')
    review = review.replace('dispatch_fixed_batch_20261109', 'dispatch_subset_batch_20261112')
    review = review.replace('fixed_batch_dispatch_review_20261109', 'subset_batch_dispatch_review_20261112')
    marker = "    out=ROOT/'reports/subset_batch_dispatch_review_20261112';out.mkdir(exist_ok=True)"
    assert review.count(marker) == 1
    extra = '''    def subset(e,n):
        e.manifest['branches']=e.manifest['branches'][:n];e.save(e.path,e.manifest)
        for b in e.manifest['branches']:e.cloud_status[b['name']]='COMPLETE'
    cases['one_branch_subset_submits_once']=execute_case('one',lambda e:subset(e,1),lambda e,r:sum(k=='launch' for k,n in e.events)==1 and sum(k=='submit' for k,n in e.events)==1,seconds=181)
    cases['four_branch_subset_submits_four']=execute_case('four',lambda e:subset(e,4),lambda e,r:sum(k=='submit' for k,n in e.events)==4,seconds=181)
    def foreign(e):
        subset(e,1)
        for i in range(5):e.save(e.root/'state'/('prior'+str(i))/'submission.json',dict(status='request_outcome_unknown_no_retry'))
    cases['other_subset_unknown_claims_count_toward_five']=execute_case('foreign',foreign,lambda e,r:not e.events and r['status']=='five_submission_claim_limit_no_more_writes')
'''
    review = review.replace(marker, extra + marker)
    install('review_subset_batch_dispatch_20261112.py', review)

    attrs = {
        'bestval_v80_tri': (
            '固定原0.488其余流程，最终候选神经集成改为0.50 Saner final、0.25原v2、0.25 popwenman best-validation；保留原outsider与晚接入head。',
            '新验证阶段checkpoint的评分互补；不是与原v2逐字节相同的V80 final，也不是完整作者三模型复现。'),
        'bestval_saner_tri': (
            '固定原0.488其余流程，最终候选神经集成改为0.375 Saner final、0.375原v2、0.25 Saner best-validation；保留原outsider与晚接入head。',
            '另一份实际独立checkpoint及其融合配方的整体效果，不单独归因训练epoch或某查询子集。'),
        'adduct_extlib': (
            '固定原0.488前外库管线，将AB匹配换为公开V18中性质量、adduct兼容、15ppm结构质量和native身份提升，并保留官方身份guard。',
            '匹配规则作为整组件变化；不能分别拆给某个门槛或任一谱库。'),
        'generation_expand': (
            '固定原0.488其余组件，扩大真实谱母体生成预算、保留双步并关闭额外同分异构化，新增候选实际进入完整特征和排序。',
            '新的整组生成配方；produre诊断本身不构成此次榜分增益，最终参数与recipe及真实counter为准。'),
        'bestval_v80_adduct': (
            '组合独立popwenman best-validation神经集成与新版AB质量/adduct匹配，原晚接入head及其他排序保留。',
            '两个组件的整组组合效果，只有同批单组件对照支持时才讨论互补；不能将两条Public差值相加。')
    }
    watcher = (SCRIPTS / 'watch_batch_with_ledger_20261110.py').read_text(encoding='utf-8')
    begin = watcher.index('ATTRIBUTIONS={')
    end = watcher.index('\n\n\ndef record_gains', begin)
    watcher = watcher[:begin] + 'ATTRIBUTIONS=' + repr(attrs) + watcher[end:]
    install('watch_batch_with_ledger_20261112.py', watcher)
    review = (SCRIPTS / 'review_gain_ledger_20261110.py').read_text(encoding='utf-8')
    review = review.replace('watch_batch_with_ledger_20261110', 'watch_batch_with_ledger_20261112')
    review = review.replace('gain_ledger_review_20261110', 'gain_ledger_review_20261112')
    old = "expected_names={'extlib_b_only','extlib_a_only','extlib_abe_gap_fill','extlib_abe_compete','extlib_ab_identity_alias'}"
    assert old in review
    review = review.replace(old, 'expected_names=' + repr(set(attrs)))
    review = review.replace('extlib_b_only', 'bestval_v80_tri')
    install('review_gain_ledger_20261112.py', review)
    result = dict(status='prepared_no_network', dispatcher='dispatch_subset_batch_20261112.py',
                  gain_watcher='watch_batch_with_ledger_20261112.py', branches=list(attrs))
    print(json.dumps(result))


if __name__ == '__main__':
    main()
