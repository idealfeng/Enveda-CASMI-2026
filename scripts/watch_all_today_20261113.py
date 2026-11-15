"""Read the two fixed daily manifests and serialize confirmed gain recording.

Plan-only unless --watch. Never push, launch, submit, or select Kaggle entries.
The earlier one-branch ledger watcher must be stopped before this starts.
"""
from pathlib import Path
import argparse
import json
import logging
import math
import os
import time

import kaggle_batch as batch
import watch_batch_with_ledger_20261113 as strict
from watch_kaggle_batch_20261107 import snapshot

ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = (
    ROOT/'submission/optimization_20261113/manifest.json',
    ROOT/'submission/optimization_20261113/exploration_manifest.json',
)
ATTRIBUTIONS = {
    'generation_production': strict.ATTRIBUTIONS['generation_production'],
    'generation_noiso_control': (
        '固定0.488整套神经、质量、晚接入head及AB，仅关闭额外同分异构化，保持6母体/150总预算/双步。',
        '单因素生成枚举开关的Public净效果；不把既有Class3小面板数字算作新增收益，不保证Private。'),
    'generation_budget_only': (
        '固定0.488原6母体、双步与同分异构化，仅将每查询生成总预算150放宽至300。',
        '固定母体及枚举策略的预算变化整体效果；实际新增候选未必正确，不归因于新模型或新训练。'),
    'spectral_network_explore': (
        '在原0.488最终输出后加入固定公开N1c目标间谱网络与邻居结构一致性排序，保留强原库及AB命中行。',
        '此固定网络排序与保护规则的Public整体效果；旧面板预筛负向仍按用户授权探索，不事后调参归因。'),
    'head_mean_ab': (
        '固定0.488主流水线和原AB，晚接入尾部trained two-head替换为原v2 mean，仍保护前7及同式原槽位。',
        '仅当前head替换与既有AB的净效果；无新训练、无新增谱库，不能推断所有训练head无用。'),
}


def prepare(paths=MANIFESTS):
    manifests = [batch.load_manifest(p) for p in paths]
    branches = [b for m in manifests for b in m['branches']]
    names = [b['name'] for b in branches]
    if len(branches) != 5 or set(names) != set(ATTRIBUTIONS):
        raise ValueError('Exactly the fixed five daily branches are required')
    if len({b['target'] for b in branches}) != 5:
        raise ValueError('Daily targets must be distinct')
    for m in manifests:
        for b in m['branches']:
            batch.local_preflight(m, b)
    return manifests, [batch.sha(p) for p in paths]


def plan(paths=MANIFESTS):
    manifests, pins = prepare(paths)
    return dict(status='plan_only_no_network', manifest_sha256=pins,
                branches=[b['name'] for m in manifests for b in m['branches']],
                network_write_performed=False, single_ledger_writer=True)


def run(hours, paths=MANIFESTS):
    if not math.isfinite(hours) or not 0 < hours <= 12:
        raise ValueError('Maximum twelve hours')
    manifests, pins = prepare(paths)
    state = ROOT/'reports/optimization_20261113'
    if (state/'watcher.lock').exists():
        raise ValueError('Earlier ledger watcher must be stopped first')
    lock = ROOT/'reports/.improvement_ledger.writer.lock'
    record = dict(status='monitoring', pid=os.getpid(), started_at_utc=batch.now(),
                  manifest_sha256=pins, read_only_network=True,
                  new_run_or_submission_performed=False, single_ledger_writer=True)
    batch.claim(lock, record)
    terminal = [{} for _ in manifests]
    refs = [{} for _ in manifests]
    started = time.monotonic()
    strict.ATTRIBUTIONS = ATTRIBUTIONS.copy()
    try:
        api = batch.make_api()
        while time.monotonic() - started < hours * 3600:
            if [batch.sha(p) for p in paths] != pins:
                raise ValueError('A fixed active daily manifest changed')
            rows = []
            added = []
            for i, m in enumerate(manifests):
                current = snapshot(m, poller=lambda mm, bb: batch.poll_submission(mm, bb, api=api),
                                   terminal=terminal[i], fixed_refs=refs[i])
                added.extend(strict.record_gains(m, current))
                rows.extend(current['branches'])
            record.update(checked_at_utc=batch.now(), branches=rows, ledger_added_refs=added,
                          ledger_current_best=batch.read(ROOT/'reports/improvement_ledger.json')['current_best'],
                          all_branches_terminal=all(r['status'] in ('COMPLETE', 'ERROR') for r in rows))
            if record['all_branches_terminal']:
                record.update(status='finished', finished_at_utc=batch.now())
            batch.save(state/'all_today_status.json', record)
            if record['all_branches_terminal']:
                return record
            time.sleep(min(45, max(0, hours * 3600 - (time.monotonic() - started))))
        record.update(status='monitor_timeout', finished_at_utc=batch.now())
    except Exception as error:
        record.update(status='watcher_stopped', finished_at_utc=batch.now(), **batch.safe_error(error))
    finally:
        lock.unlink(missing_ok=True)
    batch.save(state/'all_today_status.json', record)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--watch', action='store_true')
    parser.add_argument('--max-hours', type=float, default=12)
    args = parser.parse_args()
    if not math.isfinite(args.max_hours) or not 0 < args.max_hours <= 12:
        raise ValueError('Maximum twelve hours')
    return run(args.max_hours) if args.watch else plan()


if __name__ == '__main__':
    for key, value in [('TEMP', '.cache/tmp'), ('TMP', '.cache/tmp'),
                       ('PYTHONPYCACHEPREFIX', '.cache/pycache-win')]:
        os.environ[key] = str(ROOT/value)
    logging.disable(logging.CRITICAL)
    try:
        print(json.dumps(main(), ensure_ascii=False))
    except Exception as error:
        print(json.dumps(dict(status='watcher_stopped', **batch.safe_error(error))))
        raise SystemExit(1)
