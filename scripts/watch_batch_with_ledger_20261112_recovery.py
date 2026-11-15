"""Read fixed competition submissions and record every new confirmed Public best.

Plan-only by default. This never pushes, runs, submits, or selects a Notebook.
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse,json,logging,math,os,time
import kaggle_batch as batch
from watch_kaggle_batch_20261107 import snapshot

ROOT=Path(__file__).resolve().parents[1]
ATTRIBUTIONS={'bestval_v80_tri': ('固定原0.488其余流程，最终候选神经集成改为0.50 Saner final、0.25原v2、0.25 popwenman best-validation；保留原outsider与晚接入head。', '新验证阶段checkpoint的评分互补；不是与原v2逐字节相同的V80 final，也不是完整作者三模型复现。'), 'bestval_saner_tri': ('固定原0.488其余流程，最终候选神经集成改为0.375 Saner final、0.375原v2、0.25 Saner best-validation；保留原outsider与晚接入head。', '另一份实际独立checkpoint及其融合配方的整体效果，不单独归因训练epoch或某查询子集。'), 'adduct_extlib': ('固定原0.488前外库管线，将AB匹配换为公开V18中性质量、adduct兼容、15ppm结构质量和native身份提升，并保留官方身份guard。', '匹配规则作为整组件变化；不能分别拆给某个门槛或任一谱库。'), 'generation_expand_r3': ('固定原0.488其余组件，扩大真实谱母体生成预算、保留双步并关闭额外同分异构化，新增候选实际进入完整特征和排序。', '新的整组生成配方；produre诊断本身不构成此次榜分增益，最终参数与recipe及真实counter为准。'), 'bestval_v80_adduct': ('组合独立popwenman best-validation神经集成与新版AB质量/adduct匹配，原晚接入head及其他排序保留。', '两个组件的整组组合效果，只有同批单组件对照支持时才讨论互补；不能将两条Public差值相加。')}


def record_gains(manifest,result):
    """Require exact branch-bound API score receipts; no score from a title/UI."""
    ledger_path=ROOT/'reports/improvement_ledger.json';ledger=batch.read(ledger_path)
    known={x['ref'] for x in ledger['records']};added=[]
    specs={b['name']:b for b in manifest['branches']}
    for row in result['branches']:
        if row.get('public_score_available') is not True or row.get('error_description_present'):continue
        if row.get('status')!='COMPLETE' or type(row.get('submission_ref')) is not int or row['submission_ref']<=0:
            raise ValueError('Contradictory snapshot score identity')
        spec=specs[row['branch']]
        receipt=batch.bound_receipt(manifest,spec,'submission.json')
        score=batch.bound_receipt(manifest,spec,'score.json')
        if (receipt.get('status') not in ('accepted','accepted_reconciled_by_unique_description')
            or type(receipt.get('submission_ref')) is not int or receipt['submission_ref']<=0
            or score.get('status')!='COMPLETE' or score.get('public_score_available') is not True
            or score.get('error_description_present') is not False
            or score.get('submission_ref')!=receipt.get('submission_ref')
            or score.get('actual_target')!=receipt.get('actual_target',spec['target'])
            or row.get('actual_target')!=score.get('actual_target')
            or score.get('submission_ref')!=row['submission_ref']):
            raise ValueError('Unconfirmed gain identity')
        value=float(score['public_score'])
        if not math.isfinite(value) or not 0<=value<=1:raise ValueError('Invalid score')
        if value!=float(row['public_score']):raise ValueError('Snapshot score mismatch')
        if score['submission_ref'] in known or value<=float(ledger['current_best']):continue
        if spec['name'] not in ATTRIBUTIONS:raise ValueError('Missing explicit gain attribution')
        batch.local_preflight(manifest,spec)
        stage=ROOT/spec['stage_dir'];recipe=batch.read(stage/'recipe.json')
        recipe_pins={a['expected_fields']['recipe_sha256'] for a in spec['required_runtime_audits']
            if a.get('expected_fields',{}).get('branch')==spec['name'] and 'recipe_sha256' in a['expected_fields']}
        if len(recipe_pins)!=1 or batch.sha(stage/'recipe.json')!=next(iter(recipe_pins)):
            raise ValueError('Gain recipe differs from the frozen branch observer contract')
        source,limit=ATTRIBUTIONS[spec['name']]
        entry=dict(verified_at_utc=score['checked_at_utc'],verified_date_beijing=datetime.fromisoformat(score['checked_at_utc']).astimezone(ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M'),
            before=ledger['current_best'],after=value,ref=score['submission_ref'],target=score['actual_target'],version=1,
            comparison_anchor_ref=58156482,comparison_anchor_public_score=.488,shared_pre_external_parent_ref=58129661,shared_pre_external_parent_public_score=.482,notebook_sha256=spec['notebook_sha256'],
            recipe_path=str((stage/'recipe.json').relative_to(ROOT)).replace('\\','/'),recipe_sha256=batch.sha(stage/'recipe.json'),
            source=source,attribution_limit=limit,recipe=recipe,private_gain_verified=False,
            paired_comparison=dict(parent_ref=58156482,parent_score=.488,current_score=value,displayed_delta=round(value-.488,9)),
            evidence=str((batch.branch_state(manifest,spec)/'score.json').relative_to(ROOT)).replace('\\','/'))
        ledger['records'].append(entry);ledger['current_best']=value;known.add(entry['ref']);added.append(entry['ref'])
    if added:
        ledger['updated_at_beijing']=datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M')
        batch.save(ledger_path,ledger)
    # Reconcile prose if a previous process stopped between the two local writes.
    md=ROOT/'reports/IMPROVEMENT_LEDGER.md';prose=md.read_text(encoding='utf-8');changed=False
    for entry in ledger['records'][4:]:
        marker='<!-- gain-ref: '+str(entry['ref'])+' -->'
        if marker in prose:continue
        prose+='\n\n'+marker+'\n\n'+str(entry['verified_date_beijing'])+' 官方确认 **'+str(entry['before'])+' → '+str(entry['after'])+'**，提交 **'+str(entry['ref'])+'**。\n\n'
        prose+='提升来源：'+entry['source']+'\n\n归因限制：'+entry['attribution_limit']+'\n\n'
        prose+='固定源码 SHA：`'+entry['notebook_sha256']+'`。证据：['+entry['target']+'](https://www.kaggle.com/code/'+entry['target']+')、['+entry['evidence']+']('+entry['evidence'].removeprefix('reports/')+')。\n'
        changed=True
    if changed:
        temporary=md.with_suffix('.md.tmp');temporary.write_text(prose,encoding='utf-8');temporary.replace(md)
    return added

def watch(path,hours):
    manifest=batch.load_manifest(path);frozen=batch.sha(path)
    state=ROOT/manifest['state_root'];state.mkdir(exist_ok=True,parents=True)
    lock=state/'watcher.lock';started=time.monotonic();terminal={};refs={}
    record=dict(status='monitoring',pid=os.getpid(),manifest_sha256=frozen,started_at_utc=batch.now(),read_only_network=True,new_submission_performed=False)
    batch.claim(lock,record)
    try:
        api=batch.make_api()
        while time.monotonic()-started<hours*3600:
            if batch.sha(path)!=frozen:raise ValueError('Active manifest changed')
            result=snapshot(manifest,poller=lambda m,b:batch.poll_submission(m,b,api=api),terminal=terminal,fixed_refs=refs)
            added=record_gains(manifest,result)
            record.update(result,ledger_added_refs=added,ledger_current_best=batch.read(ROOT/'reports/improvement_ledger.json')['current_best'])
            if result['all_branches_terminal']:record.update(status='finished',finished_at_utc=batch.now())
            batch.save(state/'latest_status.json',record)
            if result['all_branches_terminal']:return record
            time.sleep(min(45,max(0,hours*3600-(time.monotonic()-started))))
        record.update(status='monitor_timeout',finished_at_utc=batch.now());batch.save(state/'latest_status.json',record);return record
    except Exception as error:
        record.update(status='watcher_stopped',finished_at_utc=batch.now(),**batch.safe_error(error));batch.save(state/'latest_status.json',record);return record
    finally:lock.unlink(missing_ok=True)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--watch',action='store_true');p.add_argument('--max-hours',type=float,default=12);a=p.parse_args()
    if not 0<a.max_hours<=12:raise ValueError('Maximum twelve hours')
    path=batch.inside(a.manifest);manifest=batch.load_manifest(path)
    if not a.watch:return dict(status='plan_only_no_network',branches=[b['name'] for b in manifest['branches']])
    return watch(path,a.max_hours)

if __name__=='__main__':
    for k,v in [('TEMP','.cache/tmp'),('TMP','.cache/tmp'),('PYTHONPYCACHEPREFIX','.cache/pycache-win')]:os.environ[k]=str(ROOT/v)
    logging.disable(logging.CRITICAL)
    print(json.dumps(main(),indent=2))
