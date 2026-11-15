"""Refresh local model and scored-submission indexes without network or model loading."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import math
import os

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 << 20), b''):
            h.update(block)
    return h.hexdigest()


def rel(path):
    return path.relative_to(ROOT).as_posix()


def link(path, title=None):
    return f'[{title or path}](../{path})'


def role(path):
    s = path.as_posix()
    if 'mist_msg_20261114' in s and path.name == 'mist_msg_noaug.ckpt':
        return 'MIST MSG real-only公开权重；实际加载后出现近恒定指纹，原生MSG/CASMI均复现，暂不部署，见20261115审计'
    if path.name.startswith('head_seed') and '/code/' in s:
        return 'head部署/实际canary副本；按SHA追溯原始训练权重'
    if '/isomer_head_' in s:
        return '自训练同式残差头；当前配方未超过冠军'
    if '/candidate_head_' in s:
        return '自训练多谱头；2500步权重用于晚接入，500步为中间检查点'
    if 'popwenman' in s and 'kit_staged' in s:
        return 'V80输出附带的原Saner副本；不是独立新模型'
    if 'popwenman' in s and path.name == 'final_model.pt':
        return '公开V80 final；与冠军v2逐字节相同，不能作独立新模型集成'
    if 'popwenman' in s and path.name == 'best_validation_model.pt':
        return '公开V80验证阶段best checkpoint；独立权重，11/12新增评分候选'
    if 'popwenman' in s and path.name == 'last_validation_model.pt':
        return '公开V80验证阶段last checkpoint；独立于final，当前保留未单独部署'
    if 'popwenman' in s:
        return '公开V80；待与冠军做受控对照'
    if 'scorer-v4-model' in s:
        return '公开v4；固定tri组合曾降分，架构不可套v1加载'
    if 'scorer-v2-model' in s:
        return '冠军使用的v2神经评分器'
    if 'sanpier/casmi-spectrum' in s:
        return ('Saner验证阶段best checkpoint；独立权重，11/12新增评分候选'
                if path.name == 'best_validation_model.pt' else '公开Saner v1 final；用于冠军')
    if 'fold-safe-fpnet' in s:
        return 'fold0指纹模型；验证隔离仍需检查预训练曝光'
    if 'v4b-models' in s:
        return 'E006基座组件；生成/特征/ranker体系'
    return '公开基座/历史复现组件；用途须结合配方核对'


def model_paths():
    for base in ('assets', 'runs'):
        for folder, dirs, files in os.walk(ROOT / base, followlinks=False):
            dirs[:] = sorted(d for d in dirs if d not in ('ice_site', '__pycache__', 'attached_input', 'input_view')
                             and not (Path(folder) / d).is_symlink())
            for name in sorted(files):
                p = Path(folder) / name
                if p.is_symlink() or name == 'head_features.pt':
                    continue
                suffix = p.suffix.lower()
                is_weight = suffix in ('.pt', '.pth', '.ckpt', '.joblib')
                is_ranker = suffix in ('.pkl', '.txt') and any(x in name.lower() for x in ('ranker', 'booster', 'model'))
                if is_weight or is_ranker:
                    yield p


def models():
    inode_hash = {}
    rows = []
    for p in sorted(model_paths()):
        stat = p.stat()
        identity = (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)
        if identity not in inode_hash:
            inode_hash[identity] = sha(p)
        nearby = [rel(p.parent / n) for n in ('config.json', 'config_used.json', 'training_result.json', 'summary.json')
                  if (p.parent / n).is_file()]
        rows.append(dict(path=rel(p), bytes=stat.st_size, sha256=inode_hash[identity],
                         role=role(p), related_metadata=nearby, hardlink_count=stat.st_nlink))
    return rows


def submissions():
    candidates = []
    for folder, dirs, files in os.walk(ROOT / 'reports'):
        dirs[:] = [d for d in dirs if not any(x in d for x in ('fixture', 'review', 'test'))]
        for name in files:
            if not (name == 'score.json' or name == 'latest_status.json' or name.endswith('_submission_status.json')
                    or name.startswith('public_tri_v30_submission_status_')):
                continue
            p = Path(folder) / name
            try:
                data = read(p)
            except (ValueError, OSError):
                continue
            rows = data.get('branches') if isinstance(data, dict) else None
            if not isinstance(rows, list):
                rows = [data]
            for row in rows:
                if not isinstance(row, dict):
                    continue
                ref = row.get('submission_ref')
                if type(ref) is not int or ref <= 0 or not row.get('target', row.get('actual_target', '')).startswith('stormseye/'):
                    continue
                candidates.append(dict(submission_ref=ref, target=row.get('actual_target', row.get('target')),
                    branch=row.get('branch'), status=row.get('status'), public_score=row.get('public_score'),
                    error_description_present=row.get('error_description_present',
                        bool(row['error_description']) if 'error_description' in row else None),
                    checked_at_utc=row.get('checked_at_utc', data.get('checked_at_utc', '')),
                    evidence=rel(p)))
    chosen = {}
    # At the same readback time prefer the complete per-submission receipt;
    # older batch summaries may omit the explicit error-presence field.
    for row in sorted(candidates, key=lambda x: (x['checked_at_utc'] or '',
                                                x['evidence'].endswith('/score.json'), x['evidence'])):
        chosen[row['submission_ref']] = row
    for row in chosen.values():
        score = row['public_score']
        # Kaggle saved API snapshots often encode a valid score as a string.
        try:
            parsed = float(score) if score is not None and not isinstance(score, bool) else None
            finite = parsed is not None and math.isfinite(parsed)
        except (ValueError, TypeError):
            parsed, finite = None, False
        row['reported_public_score'] = score
        row['public_score'] = parsed if finite else None
        row['valid_scored_result'] = (row['status'] == 'COMPLETE' and row['error_description_present'] is False
                                      and finite)
    return sorted(chosen.values(), key=lambda x: x['submission_ref'])


def refresh():
    DOCS.mkdir(exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    ms, ss = models(), submissions()
    groups = {}
    for row in ms:
        groups.setdefault(row['sha256'], []).append(row['path'])
    registry = dict(updated_at_utc=now, local_read_only_inventory=True, models=ms,
                    identical_weight_groups=[dict(sha256=k, paths=v) for k, v in groups.items() if len(v) > 1])
    (DOCS / 'model_registry.json').write_text(json.dumps(registry, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    (DOCS / 'submission_registry.json').write_text(json.dumps(dict(updated_at_utc=now, submissions=ss), indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    text = ['# 模型位置索引', '', f'本地扫描时间（UTC）：{now}。未加载任何权重。登记{len(ms)}个文件、{len(groups)}种不同内容；下表按SHA去重，全部原路径保留在JSON。SHA相同不能当独立模型集成。', '',
            '当前冠军完整部署以 [固定Notebook](../submission/optimization_20261109/mass_guarded_extlib/notebook.ipynb) 和其配方为准；权重路径不能单独代替整套配方。', '',
            '| 权重文件 | MiB | 用途/状态 | 同内容路径数 | SHA256前12位 |', '| --- | ---: | --- | ---: | --- |']
    canonical = {}
    def priority(row):
        path = row['path']
        return (0 if path.startswith('assets/') else 1 if path.startswith(('runs/candidate_head_', 'runs/isomer_head_')) else 2, path)
    for row in sorted(ms, key=priority):
        canonical.setdefault(row['sha256'], row)
    for row in canonical.values():
        text.append(f"| {link(row['path'])} | {row['bytes']/2**20:.2f} | {row['role']} | {len(groups[row['sha256']])} | `{row['sha256'][:12]}` |")
    text += ['', '完整SHA、相同权重分组、配置和训练记录见 [model_registry.json](model_registry.json)。', '',
             '刷新：在项目根目录运行 `.venv\\Scripts\\python.exe scripts/refresh_project_index.py`。只读本地资产并重建索引，不下载、不加载模型。', '']
    (DOCS / 'MODELS.md').write_text('\n'.join(text), encoding='utf-8')
    text = ['# 正式提交结果索引', '', f'生成时间（UTC）：{now}。数据来自已保存的官方读回快照；此脚本不联网，PENDING不是零分，ERROR不是有效分。', '',
            '本表包含已确认提交编号，不包含只创建Notebook但未正式提交的草稿。来源与参数解释见 [失败与经验](LESSONS.md) 和 [实验路线](EXPERIMENTS.md)。', '',
            '| 提交编号 | 分支/目标 | 状态 | Public | 读回时间UTC | 证据 |', '| --- | --- | --- | ---: | --- | --- |']
    for row in ss:
        score = f"{row['public_score']:.3f}" if row['valid_scored_result'] else '—'
        status = row['status'] + (' / 有错误' if row['error_description_present'] else '')
        text.append(f"| {row['submission_ref']} | {row['branch'] or row['target']} | {status} | {score} | {row['checked_at_utc']} | {link(row['evidence'], '快照')} |")
    text += ['', '唯一提升账本：[improvement_ledger.json](../reports/improvement_ledger.json)；本索引不会修改它或推断Private收益。', '']
    (DOCS / 'SUBMISSIONS.md').write_text('\n'.join(text), encoding='utf-8')
    return dict(models=len(ms), unique_model_contents=len(groups), submissions=len(ss), identical_weight_groups=len(registry['identical_weight_groups']))


def check():
    registry = read(DOCS / 'model_registry.json')
    for row in registry['models']:
        p = ROOT / row['path']
        assert p.is_file() and p.stat().st_size == row['bytes'], row['path']
        assert len(row['sha256']) == 64
    for row in read(DOCS / 'submission_registry.json')['submissions']:
        assert (ROOT / row['evidence']).is_file(), row['evidence']
    return dict(status='passed', models_checked=len(registry['models']))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    print(json.dumps(check() if args.check else refresh(), ensure_ascii=False))
