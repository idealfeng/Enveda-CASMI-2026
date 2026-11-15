"""Read fixed daily submissions and record confirmed gains with one ledger writer."""
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
MANIFEST = ROOT/'submission/optimization_20261114/manifest.json'
ATTRIBUTIONS = {
    'head_prefix1_ab': (
        '固定0.488主流水线及AB，原晚接入trained two-head的同式原槽重排范围由第8–25名扩为第2–25名，保留首选。',
        '当前晚接入保护范围改变的Public净效果；不称新增训练目标或新增谱信息，不保证Private。'),
    'mean_prefix1_ab': (
        '固定原主流水线及AB，用既有v2 mean晚接入同式原槽重排第2–25名，保留首选。',
        '相对冠军同时改变尾评分器和保护范围，收益先归整体；相对昨日mean＋AB可检验范围变化，不能单归训练head。'),
    'gl_evidence_early': (
        '在完整0.488输出后，以实际生产GL候选聚合分数及原排名先验重排早位，保留首选、同式槽位与强参考证据。',
        '固定GL证据接法的整体Public效果；没有逐CE新模型，聚合分数不冒称逐谱支持率或新信息采集。'),
    'dual_evidence_agreement': (
        '在完整0.488输出后，候选仅在GL与ICE实际分数都明确胜过当前首选时，按平均标准化优势门控升首，强参考命中保护。',
        '固定双证据pairwise优势门控的Public效果；两模型均胜过原首选不等于正确，不保证Private或候选召回增加。'),
    'library_consensus_early': (
        '在完整0.488后重用原两外库真实匹配，加入多个去重查询谱对现有候选的支持分布用于同式排序，允许挑战首选并保留强AB命中行。',
        '当前多谱库支持排序及放开首选保护的整体效果；无新谱库或训练，不能归因于单一库、单CE或候选正确召回。'),
}


def prepare():
    manifest = batch.load_manifest(MANIFEST)
    if len(manifest['branches']) != 5 or {b['name'] for b in manifest['branches']} != set(ATTRIBUTIONS):
        raise ValueError('Exactly the fixed five attributed branches are required')
    for b in manifest['branches']: batch.local_preflight(manifest, b)
    return manifest, batch.sha(MANIFEST)


def watch(hours):
    manifest, pin = prepare()
    state = ROOT/manifest['state_root']
    lock = ROOT/'reports/.improvement_ledger.writer.lock'
    local_lock = state/'watcher.lock'
    record = dict(status='monitoring', pid=os.getpid(), started_at_utc=batch.now(),
                  manifest_sha256=pin, read_only_network=True, new_submission_performed=False,
                  single_ledger_writer=True)
    batch.claim(lock, record)
    try:
        batch.claim(local_lock, record)
    except BaseException:
        lock.unlink(missing_ok=True)
        raise
    strict.ATTRIBUTIONS = ATTRIBUTIONS.copy()
    terminal = {}; refs = {}; started = time.monotonic()
    try:
        api = batch.make_api()
        while time.monotonic()-started < hours*3600:
            if batch.sha(MANIFEST) != pin: raise ValueError('Active manifest changed')
            current = snapshot(manifest, poller=lambda m,b: batch.poll_submission(m,b,api=api),
                               terminal=terminal, fixed_refs=refs)
            added = strict.record_gains(manifest, current)
            record.update(current, ledger_added_refs=added,
                          ledger_current_best=batch.read(ROOT/'reports/improvement_ledger.json')['current_best'])
            if current['all_branches_terminal']:
                record.update(status='finished', finished_at_utc=batch.now())
            batch.save(state/'latest_status.json', record)
            if current['all_branches_terminal']: return record
            time.sleep(min(45, max(0, hours*3600-(time.monotonic()-started))))
        record.update(status='monitor_timeout', finished_at_utc=batch.now())
    except Exception as error:
        record.update(status='watcher_stopped', finished_at_utc=batch.now(), **batch.safe_error(error))
    finally:
        local_lock.unlink(missing_ok=True); lock.unlink(missing_ok=True)
    batch.save(state/'latest_status.json', record)
    return record


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--watch', action='store_true')
    parser.add_argument('--max-hours', type=float, default=12)
    args=parser.parse_args()
    if not math.isfinite(args.max_hours) or not 0<args.max_hours<=12: raise ValueError('Maximum twelve hours')
    if not args.watch:
        m,pin=prepare(); return dict(status='plan_only_no_network',manifest_sha256=pin,branches=[b['name'] for b in m['branches']])
    return watch(args.max_hours)


if __name__=='__main__':
    for k,v in [('TEMP','.cache/tmp'),('TMP','.cache/tmp'),('PYTHONPYCACHEPREFIX','.cache/pycache-win')]: os.environ[k]=str(ROOT/v)
    logging.disable(logging.CRITICAL)
    try: print(json.dumps(main(),ensure_ascii=False))
    except Exception as error:
        print(json.dumps(dict(status='watcher_stopped', **batch.safe_error(error))));raise SystemExit(1)
