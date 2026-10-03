#!/usr/bin/env python3
# coding: utf-8
"""Compare retained upstream PPT fields; do not rebuild discarded extensions."""
import collections
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/ingest'))
from yaml_io import load_yaml
from report_visual_gaps import profile_counts


def main():
    rows = []
    for path in sorted((ROOT / 'data/external').glob('*/FIELDS-SOURCE.yaml')):
        metadata = load_yaml(path.read_text(encoding='utf-8'))
        data = path.with_name('matched-fields.jsonl')
        entries = [json.loads(line) for line in data.read_text(encoding='utf-8').splitlines()]
        fields = sorted({key for entry in entries for key in entry.get('record', entry.get('upstream_record', {}))})
        digest = hashlib.sha256(data.read_bytes()).hexdigest()
        if digest != metadata['sha256']:
            raise ValueError('Upstream subset SHA256 mismatch: ' + str(data))
        rows.append(dict(repository=metadata['repository'], commit=metadata['commit'], license=metadata['license'],
                         matched=len(entries), retained_fields=fields, data_path=data.relative_to(ROOT).as_posix(), sha256=digest))
    profiles = [load_yaml(p.read_text(encoding='utf-8')) for p in (ROOT / 'universities').glob('*/*/profile.yaml')]
    counts = profile_counts(profiles)
    report = dict(checked_at='2026-10-02', scope='data/ppt-core-fields.yaml', repositories=rows, counts=dict(counts))
    (ROOT / 'data/review/github-field-union-2026.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = ['# 开源来源与PPT核心映射', '', '2026-10-02按用户决定裁剪字段；本报告只比较实际保留的主字段子集。固定上游版本、匹配身份和许可继续可复核。', '',
             '| 仓库 | 匹配学校 | 当前保留上游字段 |', '| --- | ---: | --- |']
    for row in rows:
        lines.append('| [%s](https://github.com/%s/tree/%s) | %s | %s |' % (
            row['repository'], row['repository'], row['commit'], row['matched'], '、'.join(row['retained_fields'])))
    lines += ['', '名称、简称与英文名映射到identity；建校年映射到culture并保留来源口径；网址作为官网候选；具体标识与色卡映射到visual。模板仓库和无许可VI目录保存入口与元数据，详见[来源层级](../data/external/README.md)。', '',
              '招生、就业、排名、学科统计、人数、面积与联系方式已从档案、索引和许可子集删除，不参与后续采集及验收。不是按字段数量评估本库。', '',
              '| 素材 | 有记录学校 | 条目 |', '| --- | ---: | ---: |',
              '| 标识 | %s | %s |' % (counts['logo_schools'], counts['logo_entries']),
              '| 配色（含建议色） | %s | %s |' % (counts['palette_schools'], counts['palette_entries']),
              '| 校方色值 | %s | %s |' % (counts['official_palette_schools'], counts['official_palette_entries']), '',
              '逐校必备缺口见[主字段覆盖](ppt-core-coverage-2026.md)；机器读取用 `indexes/ppt-profiles.jsonl`。`indexes/core-facts.csv`、`logo-assets.csv` 和 `color-palettes.csv` 支持按字段筛选。', '']
    (ROOT / 'docs/github-field-union-2026.md').write_text('\n'.join(lines), encoding='utf-8')
    print('Retained PPT upstream subsets:', len(rows), '; profiles:', len(profiles))


if __name__ == '__main__':
    main()
