"""Create dated strict gain bookkeeping without changing prior frozen workers."""
from pathlib import Path
import ast
import json

ROOT=Path(__file__).resolve().parents[1]
ATTRIBUTIONS={
    'generation_production':(
        '保留原0.488神经/质量/晚接入head/AB流程，实际使用12谱母体、300产物预算、双步且无额外同分异构化；先修复实际生产engine源码指纹。',
        '新生成配方的整体效果；修复工程错误不单独算算法增益，不能拆分母体/预算/枚举贡献，候选数不是正确召回。'),
    'generation_budget_only':(
        '保留原0.488生成母体与枚举策略，仅放宽每查询生成预算，实际配置见固定recipe。',
        '仅在确实改变生成候选并通过真实生产路径后采用；不是增加模型或produre复现，不能承诺隐藏收益。')}


def write_new(path,text):
    ast.parse(text)
    if path.exists():raise FileExistsError('Preserve existing dated worker')
    path.write_text(text,encoding='utf-8')


def main():
    source=(ROOT/'scripts/watch_batch_with_ledger_20261112_recovery.py').read_text(encoding='utf-8')
    a=source.index('ATTRIBUTIONS=');z=source.index('\n\n\ndef record_gains',a)
    source=source[:a]+'ATTRIBUTIONS='+repr(ATTRIBUTIONS)+source[z:]
    write_new(ROOT/'scripts/watch_batch_with_ledger_20261113.py',source)
    review=(ROOT/'scripts/review_gain_ledger_20261112_recovery.py').read_text(encoding='utf-8')
    review=review.replace('watch_batch_with_ledger_20261112_recovery','watch_batch_with_ledger_20261113')
    review=review.replace('gain_ledger_review_20261112_recovery','gain_ledger_review_20261113')
    lines=review.splitlines(keepends=True)
    tree=ast.parse(review)
    assignment=next(n for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='expected_names' for t in n.targets))
    lines[assignment.lineno-1:assignment.end_lineno]=['        expected_names='+repr(set(ATTRIBUTIONS))+'\n']
    review=''.join(lines).replace('bestval_v80_tri','generation_production')
    write_new(ROOT/'scripts/review_gain_ledger_20261113.py',review)
    print(json.dumps(dict(status='prepared_no_network',branches=list(ATTRIBUTIONS))))


if __name__=='__main__':main()
