#!/usr/bin/env python3
"""Report a collection batch and every remaining scalar/list gap from facts."""
import argparse
import collections
import csv
import datetime as dt
import io
import json
import pathlib
import subprocess

import yaml
from report_visual_gaps import profile_counts, LABELS
import sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'ingest'))
from ppt_scope import FACT_FIELDS, LIST_FIELDS, REQUIRED

ROOT = pathlib.Path(__file__).resolve().parents[2]


def fact_coverage(profiles):
    fields = collections.defaultdict(collections.Counter)
    gaps = []
    for p in profiles:
        identity = p['identity']
        for group, values in p.items():
            if not isinstance(values, dict) or group in {'research', 'classification'}:
                continue
            for key, value in values.items():
                field = group + '.' + key
                if field not in FACT_FIELDS and field not in LIST_FIELDS:
                    continue
                if isinstance(value, dict) and 'availability' in value:
                    status = value['availability']
                    fields[field][status] += 1
                    if status != 'found':
                        gaps.append(dict(school_code=identity['school_code'], name_zh=identity['name_zh'],
                            field=field, status=status, known_homepage=identity['official_website'].get('value') or '',
                            searched_sources='|'.join(value.get('search_sources', [])),
                            note=value.get('note', '') or '保留缺口；尚无可采用的正向事实'))
                elif isinstance(value, list) and field not in {'identity.scope_tags'}:
                    fields[field]['nonempty' if value else 'empty'] += 1
                    if not value:
                        gaps.append(dict(school_code=identity['school_code'], name_zh=identity['name_zh'],
                            field=field, status='empty_collection', known_homepage=identity['official_website'].get('value') or '',
                            searched_sources='', note='尚无条目；不表示学校不存在这类信息'))
    return dict(sorted(fields.items())), gaps


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch', required=True, help='For example m4-batch02')
    args = parser.parse_args()
    if not args.batch.replace('-', '').isalnum():parser.error('Invalid batch name')
    prefix = args.batch
    baseline = json.loads((ROOT / ('data/review/' + prefix + '-baseline-2026.json')).read_text())
    profiles = [yaml.load(p.read_text(), Loader=yaml.CSafeLoader) for p in (ROOT / 'universities').glob('*/*/profile.yaml')]
    counts = profile_counts(profiles)
    fields, gaps = fact_coverage(profiles)
    sources = {}
    for path in sorted((ROOT / 'data/review').glob(prefix + '-*.jsonl')):
        rows = [json.loads(s) for s in path.read_text().splitlines() if s]
        sources[path.name] = dict(records=len(rows), statuses=dict(collections.Counter(r['status'] for r in rows if 'status' in r)))
    changed_paths = subprocess.check_output(['git', '-c', 'core.quotePath=false', 'diff', '--name-only', baseline['base_commit'], '--', 'universities/*/*/profile.yaml'], cwd=ROOT, text=True).splitlines()
    changes = []
    for path in changed_paths:
        p = yaml.load((ROOT / path).read_text(), Loader=yaml.CSafeLoader)
        old = yaml.load(subprocess.check_output(['git', 'show', baseline['base_commit'] + ':' + path], cwd=ROOT, text=True), Loader=yaml.CSafeLoader)
        found = [field for field in fields if isinstance(p.get(field.split('.')[0], {}).get(field.split('.')[1]), dict)
                 and p[field.split('.')[0]][field.split('.')[1]].get('availability') == 'found'
                 and old[field.split('.')[0]][field.split('.')[1]].get('availability') != 'found']
        changes.append(dict(school_code=p['identity']['school_code'], name_zh=p['identity']['name_zh'],
            logo_delta=len(p['visual']['logo_assets'])-len(old['visual']['logo_assets']),
            palette_delta=len(p['visual']['color_palette'])-len(old['visual']['color_palette']),
            resource_delta=len(p['visual']['vi_resources'])-len(old['visual']['vi_resources']),new_found_fields=found))
    report = dict(checked_at=dt.date.today().isoformat(),base_commit=baseline['base_commit'],before=baseline['counts'],after=counts,
        delta={k:counts[k]-baseline['counts'][k] for k in counts},
        homepage_schools=sum(p['identity']['official_website'].get('availability')=='found' for p in profiles),
        field_coverage=fields,remaining_scalar_gaps=sum(r['status']!='empty_collection' for r in gaps),
        empty_collections=sum(r['status']=='empty_collection' for r in gaps),source_ledgers=sources,school_changes=changes)
    target=ROOT/('data/review/'+prefix+'-coverage-2026.json')
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=['school_code','name_zh','field','status','known_homepage','searched_sources','note']);writer.writeheader();writer.writerows(gaps)
    (ROOT/'data/review/remaining-field-gaps-2026.csv').write_bytes(stream.getvalue().encode('utf-8-sig'))
    report['scope'] = 'data/ppt-core-fields.yaml'
    report['required_remaining_gaps'] = sum(r['field'] in REQUIRED for r in gaps)
    report['optional_and_support_remaining_gaps'] = sum(r['field'] not in REQUIRED for r in gaps)
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    lines=['# M4 PPT主字段补采状态','',f"日期：{report['checked_at']}。基线提交：`{report['base_commit']}`。范围1412所本科院校，军校不额外纳入。事实为自动采集，未作人工签核。",'',
        '2026-10-02按用户决定收窄为PPT主字段。招生、就业、排名、人数、面积、联系方式等已从当前档案与数据索引剔除，不参与补齐验收。主字段与可选项由[ppt-core-fields.yaml](../data/ppt-core-fields.yaml)统一定义。','',
        '## 当前覆盖','','| 指标 | 采集前 | 当前 | 增量 |','| --- | ---: | ---: | ---: |']
    for key,label in LABELS.items():
        if key in counts:lines.append('| %s | %s | %s | %+d |'%(label,baseline['counts'][key],counts[key],report['delta'][key]))
    lines += ['',f"已确认官网：{baseline['homepage_schools']} → {report['homepage_schools']}所。当前尚缺逐文件标识{counts['profiles']-counts['logo_schools']}所、结构化配色{counts['profiles']-counts['palette_schools']}所、官网{counts['profiles']-report['homepage_schools']}所。",'',
        '## 采集与分类','',
        '- 官网页头图逐张核对当前完整校名，区分纯校徽、纯校名与徽名组合；旧名、装饰背景、导航图标及返回HTML的假图片保留排除记录。',
        '- 色卡以校方明确公布的数值为准。CMYK-only保留空RGB/HEX；辅助、旗帜、校徽部位及院系纪念用途分别注明。已有颜色补充印刷及专色信息，不把元数据补充计为新学校覆盖。',
        '- 开源VI目录使用固定Git提交，仅提取学校与候选网址；成功读取并确认官方页面后才能采用。目录不是校方色值或图形许可的证明。',
        '- 缺官网、已知VI入口与缺简介按全库队列重试。网络失败保留短回执，成功采用的事实保留来源和哈希。短摘要根据已有结构化事实重新组织。','',
        '## 逐字段缺口','',f"主字段尚有{report['required_remaining_gaps']}项缺口；可选与来源支持字段另有{report['optional_and_support_remaining_gaps']}项空缺。队列见[remaining-field-gaps-2026.csv](../data/review/remaining-field-gaps-2026.csv)。可选模板、校歌等不要求每校都有；缺年份、英文名或可读标识不算补齐。",'',
        '| 字段 | found / nonempty | 未调查 / empty | 未找到 | 冲突 |','| --- | ---: | ---: | ---: | ---: |']
    for field,c in fields.items():lines.append('| `%s` | %s | %s | %s | %s |'%(field,c.get('found',c.get('nonempty',0)),c.get('unresearched',c.get('empty',0)),c.get('not_found',0),c.get('conflict',0)))
    lines += ['', '## 台账','','| 台账 | 记录数 | 实际状态 |','| --- | ---: | --- |']
    for path,r in sources.items():lines.append('| [%s](../data/review/%s) | %s | `%s` |'%(path,path,r['records'],json.dumps(r['statuses'],ensure_ascii=False)))
    lines += ['', '## 逐校新增','','| 学校 | 标识记录增量 | 配色记录增量 | 资源记录增量 | 新找到字段 |','| --- | ---: | ---: | ---: | --- |']
    for r in changes:lines.append('| %s | %+d | %+d | %+d | %s |'%(r['name_zh'],r['logo_delta'],r['palette_delta'],r['resource_delta'],'、'.join(r['new_found_fields']) or '既有证据补充/状态更新'))
    lines += ['', '## 复现','', '单校profile.yaml为唯一事实源。按本批targets及sources台账重新采集，色值和图形判读由decisions文件导入，再依README顺序重建七项派生内容。已读图形的重放需要忽略目录tmp/中的原缓存；缓存丢失应重新下载并比对原SHA-256，哈希变化需重新判读。', '',
        '报告命令：`python scripts/validate/report_collection_batch.py --batch '+prefix+'`。统一验收及实际CI结果见[质量检查](quality-checks.md)。本轮仍存在以上缺口，持续采集不等同全字段完成。','']
    (ROOT/('docs/'+prefix+'-progress-2026.md')).write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(dict(delta=report['delta'],changed_schools=len(changes),scalar_gaps=report['remaining_scalar_gaps']),ensure_ascii=False))


if __name__=='__main__':main()
