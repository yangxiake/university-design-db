#!/usr/bin/env python3
"""Report actual mandatory PPT coverage separately from optional materials."""
import collections
import csv
import datetime as dt
import io
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/ingest'))
from ppt_scope import SCOPE
from build_ppt_profiles import colors_for
from yaml_io import load_yaml


def required_gaps(profile):
    """A recorded reference is insufficient when the PPT export has no screen value."""
    gaps = [field for field in SCOPE['required_facts']
            if profile[field.split('.')[0]][field.split('.')[1]]['availability'] != 'found']
    if not any(a.get('access_status') == 'content_inspected' for a in profile['visual']['logo_assets']):
        gaps.append('visual.logo_assets')
    recorded_gaps = list(gaps)
    colors = colors_for(profile['visual'])
    if colors['screen_primary'] is None and 'visual.color_primary' not in gaps:
        gaps.append('visual.color_primary')
    return gaps, recorded_gaps, colors['screen_status']


def main():
    fields = {k: collections.Counter() for k in SCOPE['required_facts']}
    rows = []; inspected = 0; complete = 0; recorded_complete = 0
    screen_states = collections.Counter()
    for path in sorted((ROOT / 'universities').glob('*/*/profile.yaml')):
        p = load_yaml(path.read_text(encoding='utf-8')); identity = p['identity']
        for field in fields:
            group, key = field.split('.'); status = p[group][key]['availability']; fields[field][status] += 1
        readable = any(a.get('access_status') == 'content_inspected' for a in p['visual']['logo_assets'])
        inspected += readable
        gaps, recorded_gaps, screen_status = required_gaps(p)
        screen_states[screen_status] += 1
        complete += not gaps
        recorded_complete += not recorded_gaps
        rows.append(dict(priority=1 if 'double_first' in p['classification']['scope_tags'] else 2,
            school_code=identity['school_code'], name_zh=identity['name_zh'], province=identity['province'],
            main_fields_complete=not gaps, field_records_complete=not recorded_gaps,
            screen_color_status=screen_status, missing_count=len(gaps), missing_main_fields='|'.join(gaps),
            known_homepage=identity['official_website'].get('value') or '', profile_path=path.relative_to(ROOT).as_posix()))
    rows.sort(key=lambda r: (r['priority'], -r['missing_count'], r['school_code']))
    stream = io.StringIO(newline=''); writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    (ROOT / 'data/review/ppt-core-queue-2026.csv').write_bytes(stream.getvalue().encode('utf-8-sig'))
    checked_at = dt.date.today().isoformat()
    report = dict(checked_at=checked_at, scope='data/ppt-core-fields.yaml', profiles=len(rows),
                  main_fields_complete_schools=complete, missing_main_field_items=sum(r['missing_count'] for r in rows),
                  recorded_main_fields_complete_schools=recorded_complete,
                  schools_with_main_field_gaps=len(rows) - complete,
                  screen_primary_schools=screen_states['official_vi'] + screen_states['design_reference'],
                  print_only_screen_gaps=screen_states['official_print_only'], screen_status_counts=dict(screen_states),
                  field_coverage={k: dict(v) for k, v in fields.items()}, inspected_logo_schools=inspected,
                  optional_fields_are_completion_gates=False)
    (ROOT / 'data/review/ppt-core-coverage-2026.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = ['# PPT必备字段覆盖', '', '日期：%s。档案范围1412所，已剔除军校。各校主字段缺口独立统计，未填满不得称为全部完成。' % checked_at, '',
             '必备数据：教育部身份、英文校名、建校年及口径、附来源主色、至少一个读到实际文件的校徽/校名标识。校训、官方模板、辅色、VI、校史节点等为可选补充；不要求每校都有。', '',
             '| 主字段 | 可供PPT使用 / 已读文件 | 缺口或冲突 |', '| --- | ---: | ---: |']
    for field, counter in fields.items():
        usable = report['screen_primary_schools'] if field == 'visual.color_primary' else counter['found']
        lines.append('| %s | %s | %s |' % (SCOPE['required_facts'][field], usable, len(rows) - usable))
    lines += ['| 可读校徽 / 校名标识 | %s | %s |' % (inspected, len(rows) - inspected), '',
              '主字段可用：%s所；%s所学校尚有%s项主字段缺口。' % (complete, report['schools_with_main_field_gaps'], report['missing_main_field_items']), '',
              '按档案是否已有来源记录统计为%s所。%s所只有官方印刷主色，屏幕值为空，不能计入屏幕PPT就绪，也不换算或补造HEX。主色来源记录共%s所，其中可用屏幕主色%s所。' % (
                  recorded_complete, report['print_only_screen_gaps'], fields['visual.color_primary']['found'], report['screen_primary_schools']), '',
              '主色可以是有依据的PPT设计建议色，方法与来源保留；不能把取样颜色称为校方官方标准。英文名、建校年和校训采用社区数据时明确标记社区来源；不冒充校方直接发布。', '',
              '下一批只读取[主字段补采队列](../data/review/ppt-core-queue-2026.csv)。[字段定义](../data/ppt-core-fields.yaml)是范围依据；[当前PPT数据](../indexes/ppt-profiles.jsonl)保留逐项来源。', '']
    (ROOT / 'docs/ppt-core-coverage-2026.md').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
