#!/usr/bin/env python3
"""Report M4 batch 01 against its frozen Git baseline and current derived data."""
import collections
import csv
import datetime as dt
import json
import pathlib
import subprocess
import sys

import yaml
from report_visual_gaps import profile_counts

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/ingest'))
from build_ppt_profiles import colors_for


def main():
    baseline = json.loads((ROOT / 'data/review/m4-batch01-baseline-2026.json').read_text())
    paths = list((ROOT / 'universities').glob('*/*/profile.yaml'))
    profiles = [yaml.load(p.read_text(), Loader=yaml.CSafeLoader) for p in paths]
    counts = profile_counts(profiles)
    templates = list(csv.DictReader((ROOT / 'indexes/ppt-template-files.csv').open(encoding='utf-8-sig')))
    scope = list(csv.DictReader((ROOT / 'data/universities-scope-2026.csv').open(encoding='utf-8-sig')))
    double = {r['school_code'] for r in scope if 'double_first' in r['scope_tags']}
    df_profiles = [p for p in profiles if p['identity']['school_code'] in double]
    changed_paths = subprocess.check_output(['git','-c','core.quotePath=false','diff','--name-only',baseline['base_commit'],'--','universities/*/*/profile.yaml'],cwd=ROOT,text=True).splitlines()
    changes = []
    for relative in changed_paths:
        # Git can quote non-ASCII paths; request unquoted UTF-8 paths below.
        if relative.startswith('"'):
            raise ValueError('Run with git core.quotePath=false for the batch report')
        current = yaml.load((ROOT / relative).read_text(), Loader=yaml.CSafeLoader)
        previous = yaml.safe_load(subprocess.check_output(['git','show',baseline['base_commit']+':'+relative],cwd=ROOT,text=True))
        old, new = previous['visual'], current['visual']
        changes.append(dict(school_code=current['identity']['school_code'],name_zh=current['identity']['name_zh'],
            logo_delta=len(new['logo_assets'])-len(old['logo_assets']),palette_delta=len(new['color_palette'])-len(old['color_palette']),
            resource_delta=len(new['vi_resources'])-len(old['vi_resources']),screen_status=colors_for(new)['screen_status']))
    sources = [json.loads(line) for line in (ROOT / 'data/review/m4-batch01-sources-2026.jsonl').read_text().splitlines()]
    headers = [json.loads(line) for line in (ROOT / 'data/review/m4-batch01-header-marks-2026.jsonl').read_text().splitlines()]
    report = dict(checked_at=dt.date.today().isoformat(),base_commit=baseline['base_commit'],before=baseline['counts'],after=counts,
                  delta={k:counts[k]-baseline['counts'][k] for k in counts},
                  remaining=dict(no_logo_schools=counts['profiles']-counts['logo_schools'],no_palette_schools=counts['profiles']-counts['palette_schools'],
                    unknown_homepages=sum(not p['identity']['official_website'].get('value') for p in profiles)),
                  double_first=profile_counts(df_profiles),school_changes=changes,
                  source_statuses=dict(collections.Counter(r['status'] for r in sources)),
                  header_statuses=dict(collections.Counter(r['status'] for r in headers)),
                  pptx_records=len(templates),pptx_schools=len({r['school_code'] for r in templates}),
                  pptx_slides=sum(int(r['slide_count']) for r in templates))
    (ROOT / 'data/review/m4-batch01-coverage-2026.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    labels={'logo_schools':'有逐文件标识入口的学校','inspected_logo_schools':'至少一个标识已读的学校','logo_entries':'标识文件记录','palette_schools':'有结构化配色的学校','official_palette_schools':'有校方公布数字色的学校（含仅印刷）','official_palette_entries':'校方数字色记录'}
    lines=['# M4 首批针对性补采','',f"日期：{report['checked_at']}。对比提交：`{report['base_commit']}`。范围仍为1412所教育部本科院校，军校不额外纳入。新增事实为自动采集，未作人工签核。",'',
      '## 覆盖变化','','| 指标 | 补采前 | 本批后 | 增量 |','| --- | ---: | ---: | ---: |']
    lines += ['| %s | %s | %s | +%s |'%(label,baseline['counts'][key],counts[key],report['delta'][key]) for key,label in labels.items()]
    lines += ['',f"实际读取的PPTX结构：{baseline['pptx_records']} → {len(templates)}份记录，涉及{report['pptx_schools']}所学校，共{report['pptx_slides']}页。这是结构读取记录数，不是唯一文件数或逐页渲染数量。",'',
      '## 本批重点','',
      '- 中央美术学院：读完官网视觉系统13幅图，补入五组CMYK印刷标准和中英文校名展示稿；该页未找到校级RGB/HEX或唯一主色排序。',
      '- 北航、华东师大、晋中信息学院、黄河科技学院：补入原规范中的RGB、CMYK、Pantone及明确用途；辅助色不自动提升为第二主色。',
      '- 四川大学、华中农业大学、湖北科技学院：补入官方CMYK标准与辅助色。湖北科技学院现有图片取色保留为设计参考，屏幕主色选择显示仅印刷标准。',
      '- 北大：PDF第4页再次确认既有RGB/Web冲突，补入印刷及专色值，继续暂停屏幕主色自动选择。',
      '- 西南大学、中国地质大学（武汉）：补入明确的其他用途色、专色或中性色。',
      '- 大湾区大学：修复页头容器误判，读取两个官网标识文件和对应参考色。',
      '- 华中农业大学信息学院：四份PPTX各两页、零可编辑文本，是图片背景模板，标为院系专用；保存原始EMU画幅、字体声明、哈希及结构，未运行或渲染。',
      '- 中国科大：读到公用模板ZIP结构，共六个成员；没有PPTX结构记录，不据包名虚构页数。北航2026标志组合只读发布页，附件保持未读取。','',
      '## 访问限制与剩余缺口','',
      f"当前缺逐文件标识{report['remaining']['no_logo_schools']}所、缺结构化配色{report['remaining']['no_palette_schools']}所、尚未确认官网{report['remaining']['unknown_homepages']}所。144所范围内双一流均已有配色条目，但只有{report['double_first']['official_palette_schools']}所有校方数字色证据（含仅印刷）。",'',
      '- 三江学院VI入口转到统一登录，保留限制记录；当前官网标识取色仍只是设计参考。',
      '- 重庆理工大学主页返回验证/访问异常，VI文件未完整读到；南京信息工程大学手册超时。保留候选网址，未靠检索摘要生成已读色值。',
      '- 华东师大地理学院两份PPTX尝试HTTPS及公开HTTP入口仍受下载时间限制；华中农大另外两份模板未成功读取，保存原发布页入口及失败回执。',
      f"- 重试59所缺标识且已有官网的学校：{report['header_statuses']}。没有新成功时不删除历史证据；另一次大湾区大学修复后的成功访问单列台账。",'',
      '## 逐校变化','','| 学校 | 新标识记录 | 新配色记录 | 新资源记录 | 当前屏幕主色状态 |','| --- | ---: | ---: | ---: | --- |']
    lines += ['| %s | %s | %s | %s | `%s` |'%(r['name_zh'],r['logo_delta'],r['palette_delta'],r['resource_delta'],r['screen_status']) for r in changes]
    lines += ['', '## 复现与层级','',
      '入口与短回执见`data/review/m4-batch01-targets-2026.yaml`及`m4-batch01-sources-2026.jsonl`；判读文件只保存数字、用途、来源及哈希，单校`profile.yaml`仍是唯一事实源。原网页、图形、PDF和模板只缓存于忽略目录`tmp/`。','',
      '```bash',
      'python scripts/ingest/collect_targeted_vi.py --targets data/review/m4-batch01-targets-2026.yaml --output data/review/m4-batch01-sources-2026.jsonl',
      'python scripts/ingest/import_visual_refresh.py --decisions data/review/m4-batch01-color-decisions-2026.yaml --changes data/review/m4-batch01-visual-changes-2026.jsonl',
      'python scripts/ingest/import_targeted_resources.py --decisions data/review/m4-batch01-resource-decisions-2026.yaml --receipts data/review/m4-batch01-sources-2026.jsonl',
      'python scripts/ingest/collect_header_css_marks.py --import-only --output data/review/m4-batch01-header-recovery-2026.jsonl',
      '# 顺序重建README所列七项派生数据后：',
      'python scripts/validate/report_targeted_batch.py',
      'python scripts/check.py', '```','',
      '联网采集按保存回执跳过成功来源。`--retry-errors --format PPTX`仅重试所选模板失败；不同学校/文件批次顺序写入同一台账，避免并发覆盖。缓存丢失时可重新读取固定网址并比对SHA-256，变更哈希须重新判读。','',
      '## 验收','',
      '档案语义、JSON Schema、派生索引与素材目录一致性及新增回归测试使用统一检查入口；实际本地和GitHub结果见[质量检查](quality-checks.md)。下一批继续补缺VI、标识及实际模板；当前仍有上述缺口，M4为持续批次工作。','']
    (ROOT / 'docs/m4-batch01-progress-2026.md').write_text('\n'.join(lines))
    print(json.dumps(dict(delta=report['delta'],pptx_records=len(templates),remaining=report['remaining']),ensure_ascii=False))


if __name__=='__main__':
    main()
