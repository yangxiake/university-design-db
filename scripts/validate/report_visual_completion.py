#!/usr/bin/env python3
"""Report official visual evidence, missing homepages and this batch's changes."""
import collections
import datetime as dt
import json
import pathlib
import yaml

ROOT=pathlib.Path(__file__).resolve().parents[2]
LABELS={
    'official_website':'已确认学校主站',
    'logo_schools':'校徽/校名文件资源覆盖学校',
    'logo_entries':'校徽/校名资源条目',
    'palette_schools':'有结构化配色的学校（含建议色）',
    'palette_entries':'结构化配色条目',
    'official_palette_schools':'有校方公布色值的学校',
    'official_palette_entries':'校方公布色值条目',
    'official_primary_schools':'有官方屏幕主色的学校',
    'print_only_palette_entries':'仅公布CMYK/Pantone的条目',
    'vi_schools':'标识介绍、VI规范及文件入口覆盖学校',
    'vi_entries':'标识介绍、VI规范及文件入口条目',
    'official_template_schools':'官方PPT主入口字段覆盖学校',
    'summary_zh':'附来源中文短摘要',
}


def main():
    baseline=json.loads((ROOT/'data/review/visual-baseline-2026.json').read_text())
    counts=collections.Counter()
    for path in (ROOT/'universities').glob('*/*/profile.yaml'):
        p=yaml.safe_load(path.read_text());colors=p['visual']['color_palette']
        official=[c for c in colors if c['method']=='official_vi']
        counts.update(profiles=1,official_website=bool(p['identity']['official_website'].get('value')),
                      logo_schools=bool(p['visual']['logo_assets']),logo_entries=len(p['visual']['logo_assets']),
                      palette_schools=bool(colors),palette_entries=len(colors),official_palette_schools=bool(official),official_palette_entries=len(official),
                      official_primary_schools=p['visual']['color_primary'].get('method')=='official_vi',
                      print_only_palette_entries=sum(c.get('value') is None for c in official),
                      vi_schools=bool(p['visual']['vi_resources']),vi_entries=len(p['visual']['vi_resources']),
                      official_template_schools=p['resources']['official_templates_url']['availability']=='found',
                      summary_zh=p['overview']['summary_zh']['availability']=='found')
    delta={key:counts[key]-baseline['counts'][key] for key in LABELS}
    homes=[json.loads(s) for s in (ROOT/'data/review/homepage-identity-2026.jsonl').read_text().splitlines()]
    guides=json.loads((ROOT/'data/review/official-visual-guides-2026.json').read_text())
    decisions=yaml.safe_load((ROOT/'data/review/visual-guides-decisions-2026.yaml').read_text())
    attachments=json.loads((ROOT/'data/review/visual-attachments-2026.json').read_text())
    date=dt.date.today().isoformat()
    lines=['# 官方视觉规范与官网入口补采','','本报告从当前单校事实源生成。范围保持教育部2026名单内1412所本科院校；所有新记录仍为AI自动核对，未认定为人工签核。','',
           '采集日期：'+date+'。对比基线提交：`'+baseline['reference_commit']+'`。','',
           '## 覆盖变化','','| 项目 | 本批前 | 当前 | 净变化 |','| --- | ---: | ---: | ---: |']
    for key,label in LABELS.items():lines.append('| %s | %s | %s | %+d |'%(label,baseline['counts'][key],counts[key],delta[key]))
    lines+=['','校徽/校名覆盖包括组合标识和具体构成尚未核验的官网页眉文件，不等于纯校徽或现行授权均已确认。配色学校数含校徽取色和社区参考；官方主色另计。只公布印刷色的条目不会补造RGB/HEX。标识介绍、模板页与VI手册均在视觉入口集合中，学校数不能称为已有完整VI手册的数量。','',
            '## 本批新增官方色彩证据','','| 学校 | 官方记录 | 来源入口 |','| --- | --- | --- |']
    for name in dict.fromkeys(d['name_zh'] for d in decisions):
        rows=[d for d in decisions if d['name_zh']==name];notes=[]
        for d in rows:
            notes += [c['label']+' '+(c['value'] or '仅印刷色') for c in d['colors']]
            notes += [c['label']+'：RGB/HEX冲突' for c in d.get('conflicts',[])]
        lines.append('| %s | %s | [校方页面/手册](%s) |'%(name,'；'.join(notes),rows[0]['vi_url']))
    lines+=['','青岛黄海学院蓝色卡RGB15/50/133与印出HEX#0C3386不一致，保留两个候选；浅蓝与珠山红按一致数字记录。成都中医药大学仅采用通知明确的学校LOGO赭红色，周年数字的红橙渐变未写成通用主题色。天津、南京和上海大学相关来源只公布印刷色，保持屏幕色空值。','',
            '本批检查%s个视觉来源，采用%s所学校的证据。官方附件入口另采到%s条，AI/CDR/PDF/ZIP/RAR格式按原链接标签；未读取这些附件，动态端点也不认定为已成功下载。'%(len(guides['sources']),guides['school_count'],sum(len(r['attachments']) for r in attachments)),'',
            '湖北工业大学文件为2022年70周年专用标识，未当作通用标准色；三江学院链接返回登录页；无锡学院不同页面及两种协议本次仍超时；其他访问限制及失败保留台账，不绕过。','',
            '## 广泛视觉入口与PPT资源补采','']
    directory=[json.loads(s) for s in (ROOT/'data/review/visual-directory-2026.jsonl').read_text().splitlines()]
    leads=json.loads((ROOT/'data/review/visual-directory-leads-2026.json').read_text())
    ppt=[json.loads(s) for s in (ROOT/'data/review/ppt-resources-2026.jsonl').read_text().splitlines()]
    cnlogo=json.loads((ROOT/'data/review/cnlogo-metadata-2026.json').read_text())
    community=json.loads((ROOT/'data/review/community-ppt-metadata-2026.json').read_text())
    school_ppt={r['school_code'] for r in ppt if any(e['use_scope']=='school' for e in r['resources'])}
    dept_ppt={r['school_code'] for r in ppt if any(e['use_scope']=='department' for e in r['resources'])}
    lines+=['目录与当前本科范围精确匹配%s所，其中%s所提供视觉网址并已逐校尝试。实际通过学校身份及页面主题核对的有%s所，留下%s条页面/附件引用。目录本身只提供线索；错误网址、无身份依据或无视觉主题的页面不进入资源集合。'%(len(leads['schools']),len(directory),sum(r['status']=='verified_visual_resources' for r in directory),sum(len(r['resources']) for r in directory)),'',
            'PPT补采台账确认%s所学校通用资源、%s所院系专用资源，共%s条页面/文件引用。清华2025系列、东华2026版及嘉庚2026系列等按来源标签保留版本；每条发布网页、文件结构及未读取目标分别标注状态。'%(len(school_ppt),len(dept_ppt),sum(len(r['resources']) for r in ppt)),'',
            '新增固定版本cnlogo社区TikZ源码入口%s所，排除旧校名、疑似笔误与缺城市限定的中国地质大学。另收录%s个社区PPTX/Marp项目及%s个具体PPTX文件入口；不运行上游SKILL或再分发模板、字体和校徽。'%(cnlogo['matched'],len(community),sum(len(r['files']) for r in community)),'',
            '按PPT制作查找的派生索引见`indexes/ppt-starter.csv`、`indexes/ppt-resources.csv`和`indexes/ppt-template-files.csv`；分类、配色方法、压缩包定位与AI读取示例见[ppt-guide.md](ppt-guide.md)。','',
            '## 补确认学校主站','','候选网站只在完整学校名明确出现在版权声明且页面可定位为主站时采用。母校名称、新闻提及、旧版权名、英文/招生部门站点不足以确认。','']
    for r in homes:
        if r['status']=='ownership_confirmed':lines.append('- [%s](%s)：完整版权主体已自动匹配。'%(r['name_zh'],r['homepage_url']))
    lines+=['','已变成小说站的历史海都学院候选地址仍排除。',
            '新增入口继续用于英文校名、建校年及标识文件补采。人数、占地、就业、招生和联系方式等高维护字段已从当前档案及派生索引移除；当前覆盖以PPT主字段报告为准。','',
            '## 仍待补采','','- 学校主站尚未确认：%s所。'%(counts['profiles']-counts['official_website']),
            '- 暂无逐文件校徽/校名资源：%s所。'%(counts['profiles']-counts['logo_schools']),
            '- 暂无结构化配色：%s所。'%(counts['profiles']-counts['palette_schools']),
            '- 无官方屏幕主色值：%s所；可能只有印刷色、图片参考或来源数字冲突。'%(counts['profiles']-counts['official_primary_schools']),'',
            '台账：`data/review/homepage-identity-2026.jsonl`、`official-visual-guides-2026.json`、`visual-guides-decisions-2026.yaml`与`visual-attachments-2026.json`。原始网页、PDF和色卡只在忽略目录中用于读取，仓库保存链接、数字、哈希及短依据。','']
    file_ledger=ROOT/'data/review/template-file-inspections-2026.jsonl'
    if file_ledger.exists():
        receipts=[json.loads(s) for s in file_ledger.read_text().splitlines()]
        status=collections.Counter(r['status'] for r in receipts)
        presentations=sum(r.get('file_metadata',{}).get('format')=='PPTX' for r in receipts)+sum(m['status']=='content_inspected' for r in receipts for m in r.get('file_metadata',{}).get('presentation_members',[]))
        schools={r['school_code'] for r in receipts if r.get('file_metadata',{}).get('format')=='PPTX' or any(m['status']=='content_inspected' for m in r.get('file_metadata',{}).get('presentation_members',[]))}
        section=['## 模板文件结构补充','',
                 '已尝试%s个公开目标：%s个读取了PPTX/ZIP结构，%s个确认实际为发布网页，%s个仅识别格式头，%s个保留访问/解析缺口。PPTX及压缩包内PPTX共%s份记录，涉及%s所学校；保留页数、精确画幅、声明字体、可编辑文本节点、内部主题色、外部关系数量与SHA256。'%(len(receipts),status['content_inspected'],status['target_page_read'],status['format_only'],status['inspection_failed'],presentations,len(schools)),'',
                 '仅读取文件数据，不运行宏或外部关系，也未逐页渲染；主题色不作为学校官方VI。仍有验证页、超时、旧格式和超过读取上限的目标，均保留实际尝试记录。','']
        insert=lines.index('## 补确认学校主站');lines[insert:insert]=section
    (ROOT/'docs/visual-completion-progress-2026.md').write_text('\n'.join(lines),encoding='utf-8')
    stats=dict(checked_at=date,baseline_commit=baseline['reference_commit'],counts=dict(counts),net_changes=delta)
    (ROOT/'data/review/visual-completion-coverage-2026.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(stats,ensure_ascii=False))


if __name__=='__main__':main()
