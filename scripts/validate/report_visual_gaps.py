#!/usr/bin/env python3
"""Report gap-focused logo, color and presentation enrichment from profiles."""
import collections
import csv
import json
import pathlib
import yaml

ROOT=pathlib.Path(__file__).resolve().parents[2]
LABELS={
    'profiles':'本科院校档案',
    'logo_schools':'有校徽、校名或组合标识入口的学校',
    'logo_entries':'逐文件标识入口',
    'inspected_logo_schools':'至少一个标识文件已读取的学校',
    'inspected_logo_entries':'已读取标识文件',
    'official_logo_schools':'有官网发布标识入口的学校',
    'badge_schools':'有明确校徽类型入口的学校',
    'palette_schools':'有结构化配色的学校，含参考色',
    'palette_entries':'结构化配色条目',
    'official_palette_schools':'有校方公布色值的学校',
    'official_palette_entries':'校方公布色值条目',
    'presentation_records':'读取了结构的PPTX记录，含包内文件',
    'presentation_schools':'有已读取PPTX结构的学校',
    'presentation_slides':'上述PPTX记录的幻灯片总数',
}


def profile_counts(profiles):
    counts=collections.Counter()
    for p in profiles:
        assets=p['visual']['logo_assets'];colors=p['visual']['color_palette']
        inspected=[a for a in assets if a.get('access_status')=='content_inspected']
        official=[c for c in colors if c['method']=='official_vi']
        counts.update(profiles=1,logo_schools=bool(assets),logo_entries=len(assets),
                      inspected_logo_schools=bool(inspected),inspected_logo_entries=len(inspected),
                      official_logo_schools=any(a['official'] for a in assets),badge_schools=any(a['kind']=='badge' for a in assets),
                      palette_schools=bool(colors),palette_entries=len(colors),
                      official_palette_schools=bool(official),official_palette_entries=len(official))
    return counts


def load_lines(name):
    return [json.loads(line) for line in (ROOT/'data/review'/name).read_text().splitlines()]


def main():
    baseline=json.loads((ROOT/'data/review/visual-gap-baseline-2026.json').read_text())
    profiles=[yaml.load(p.read_text(),Loader=yaml.CSafeLoader) for p in sorted((ROOT/'universities').glob('*/*/profile.yaml'))]
    counts=profile_counts(profiles)
    files=list(csv.DictReader((ROOT/'indexes/ppt-template-files.csv').open(encoding='utf-8-sig')))
    counts.update(presentation_records=len(files),presentation_schools=len({f['school_code'] for f in files}),
                  presentation_slides=sum(int(f['slide_count']) for f in files))
    community=load_lines('community-logo-gaps-2026.jsonl');header=load_lines('header-css-marks-2026.jsonl')
    layouts=json.loads((ROOT/'data/review/logo-layout-metadata-2026.json').read_text())
    community_status=dict(collections.Counter(r['status'] for r in community));header_status=dict(collections.Counter(r['status'] for r in header))
    layout_status=collections.Counter(a.get('inspection',{}).get('access_status','indexed_not_fetched') for r in layouts for a in r['assets'])
    excluded=sum(len(r.get('excluded_assets',[])) for r in header)
    paused=sum(r.get('detail')=='renamed_or_suspended_logo' for r in community)
    date=max(r['checked_at'] for r in community+header)
    delta={k:counts[k]-baseline['counts'][k] for k in LABELS}
    summary=dict(checked_at=date,baseline_commit=baseline['reference_commit'],counts=dict(counts),net_changes=delta,
                 community_candidates=len(community),community_results=community_status,renamed_or_suspended_excluded=paused,
                 header_candidates=len(header),header_results=header_status,header_assets_excluded=excluded,
                 layout_file_status=dict(layout_status),remaining=dict(logo_schools=counts['profiles']-counts['logo_schools'],
                                                                     palette_schools=counts['profiles']-counts['palette_schools']))
    lines=['# 校徽、配色与PPT文件缺口补采','',
           '范围为教育部2026名单中的1412所本科院校。以单校profile.yaml为事实源，文件读取状态与来源类型分别记录；所有本批新增条目为auto。','',
           '采集日期：'+date+'；对比提交：`'+baseline['reference_commit']+'`。','',
           '## 覆盖变化','','| 项目 | 本批前 | 当前 | 净变化 |','| --- | ---: | ---: | ---: |']
    for key,label in LABELS.items():lines.append('| %s | %s | %s | %+d |'%(label,baseline['counts'][key],counts[key],delta[key]))
    lines+=['','标识入口覆盖包含校名、组合图和具体徽名构成待确认的官网页头，不能等同于纯校徽覆盖。读取结构表示取得实际文件格式、尺寸或颜色数据，不表示已确认现行版本、独立授权或完整视觉效果。同一模板的不同文件记录未按内容哈希去重，页数为记录合计。','',
            '## 本批资料','',
            '### 官网页头与CSS','',
            '对%s所缺标识入口的已确认官网学校检查静态HTML、惰性加载图片和最多5份同校CSS。%s所读到页头标识文件，%s所未读到可用标识，%s所保留访问或身份缺口。'%(len(header),header_status.get('header_marks_read',0),header_status.get('no_inspected_header_mark',0),header_status.get('access_or_identity_gap',0)),
            '', '排除%s个党务、教务、浏览器弹窗或新闻装饰候选。CSS只用于寻找明确标识文件，不将网站样式色自动当作学校主题色。颜色取样进入参考调色板，保留已有主色及冲突。'%(excluded), '',
            '### 当前校名匹配的社区校徽目录','',
            '对%s所缺标识或配色的学校查阅[urongda校徽目录](https://www.urongda.com)，使用教育部标识码路径、完整现行校名H1、对应图片标签与有效文件列表联合匹配。%s所读到社区预览图，%s所仅确认目录，%s所仍有访问、目录不存在或身份缺口。'%(len(community),community_status.get('community_logo_read',0),community_status.get('community_listing_only',0),community_status.get('access_or_identity_gap',0)),
            '', '明确因更名或暂停下载而排除%s条目录。图片标为official=false；取色标为community_logo_sample/reference，云盘文件仅索引。社区目录对文件的自述不成为本库的校方发布或授权结论。灰色、反白或无法可靠取色的图形继续保留空色值。'%(paused), '',
            '### 固定版本的版式与模板','']
    for r in layouts:
        status=collections.Counter(a.get('inspection',{}).get('access_status','indexed_not_fetched') for a in r['assets'])
        lines+=['- [%s版式库](https://github.com/%s/tree/%s)：%s个SVG/PDF/PNG文件入口，%s个已读取；区分纯校徽、纯校名与徽名组合，保留蓝/黑、横/竖和双语布局。其余文件仅索引。'%(r['name_zh'],r['repository'],r['commit'],len(r['assets']),status['content_inspected'])]
    scut=[f for f in files if f['repository']=='MikeHuang2000/SCUT-PPT-Template-HMK']
    lines+=['- [华南理工大学社区模板4.0](https://github.com/MikeHuang2000/SCUT-PPT-Template-HMK/tree/4fcf55148565ea328bc7102afd12f59a284995d1)：%s份PPTX记录已读取结构，共%s页；页数、画幅、声明字体与主题内部色值进入文件索引，保持社区来源。'%(len(scut),sum(int(f['slide_count']) for f in scut)), '',
            '上述源只读取数据，不执行脚本、SKILL、TeX、宏或外部关系，不安装上游字体。图形、PPT文件、网页原文均只用于本地读取，仓库保存链接和元数据。', '',
            '### 校方印刷色证据','',
            '[成都信息工程大学校名、校标页面](https://www.cuit.edu.cn/index/cxwh/xxxb.htm)明确给出学校标准蓝CMYK 100/50/0/0。档案保存原值及页面哈希；来源没有RGB/HEX，故不进行无配置换算或补造屏幕标准色。','',
            '## 使用与剩余缺口','',
            '- 从[单校PPT素材索引](../indexes/ppt-starter.csv)找文件，再读对应VISUAL.md确认来源、格式与用途。',
            '- [校徽文件索引](../indexes/logo-assets.csv)可以筛选official、kind与access_status；[调色板](../indexes/color-palettes.csv)按method/role筛选标准与参考色。',
            '- [实际PPT文件索引](../indexes/ppt-template-files.csv)给出页数、画幅、字体及哈希；结构读取不等于逐页渲染或所有图形可编辑。',
            '- 尚有%s所无逐文件标识入口、%s所无结构化配色；访问失败或本次未找到不能写成学校没有资料。'%(summary['remaining']['logo_schools'],summary['remaining']['palette_schools']), '',
            '本批台账：community-logo-gaps-2026.jsonl、header-css-marks-2026.jsonl、logo-layout-metadata-2026.json、visual-gap-color-decisions-2026.yaml与template-file-inspections-2026.jsonl，均位于data/review。重试保留实际访问结果，不绕过登录、验证页或访问限制。','']
    (ROOT/'docs/visual-gap-progress-2026.md').write_text('\n'.join(lines))
    (ROOT/'data/review/visual-gap-coverage-2026.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary,ensure_ascii=False))


if __name__=='__main__':main()
