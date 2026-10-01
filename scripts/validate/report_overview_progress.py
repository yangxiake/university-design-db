#!/usr/bin/env python3
"""Measure current official overview facts and collection gaps."""
import collections
import json
import pathlib
import yaml

ROOT=pathlib.Path(__file__).resolve().parents[2]
FIELDS={'overview.summary_zh':'重新组织的短摘要','statistics.student_count':'学生人数（看总数/本科等口径）',
        'statistics.faculty_count':'教职工/专任教师（看口径）','statistics.campus_area_hectares':'校园面积（公顷）',
        'academics.degree_authorizations':'学位授权点层次与数量'}


def main():
    records=[json.loads(s) for s in (ROOT/'data/review/official-overviews-2026.jsonl').read_text().splitlines()]
    counts=collections.Counter();dates=collections.defaultdict(collections.Counter)
    for path in (ROOT/'universities').glob('*/*/profile.yaml'):
        p=yaml.safe_load(path.read_text())
        for field in FIELDS:
            group,key=field.split('.');fact=p[group][key]
            if fact['availability']=='found':
                counts[field]+=1
                if field.startswith('statistics.'):
                    dates[field]['undated' if fact.get('source_as_of')=='undated' else 'dated']+=1
                    dates[field]['approximate' if fact.get('approximate') else 'as_printed']+=1
        counts['campus_schools']+=bool(p['location']['campuses']);counts['campus_entries']+=len(p['location']['campuses'])
    status=dict(collections.Counter(r['status'] for r in records))
    archive=json.loads((ROOT/'data/review/logo-archive-2026.json').read_text())
    sources=json.loads((ROOT/'data/review/supplemental-repositories-2026.json').read_text())
    stats=dict(checked_at=max(r['checked_at'] for r in records),scope=len(records),counts=dict(counts),statistics_basis={k:dict(v) for k,v in dates.items()},
               collection_status=status,page_attempts=sum(len(r['pages']) for r in records),
               matched_archive_files=len(archive['matched']),unmatched_archive_files=len(archive['unmatched']),excluded_archive_files=len(archive.get('excluded',[])))
    (ROOT/'data/review/overview-coverage-2026.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    lines=['# 官网简介、校区与开源补采进度','',
        '本轮按教育部2026本科范围1412所采集。学校数、取得的字段数与资料时效分别统计；当前资料仍为自动采集版本。','',
        '## 当前档案覆盖','','| 字段 | 学校数 |','| --- | ---: |']
    for field,label in FIELDS.items():lines.append('| %s | %s |'%(label,counts[field]))
    lines+=['| 官网明确校区 | %s所，%s条 |'%(counts['campus_schools'],counts['campus_entries']),
        '', '## 数值口径','','| 字段 | 原文标注统计时间 | 未标统计时间 | 近似/下界数 |','| --- | ---: | ---: | ---: |']
    for field in dates:lines.append('| %s | %s | %s | %s |'%(FIELDS[field],dates[field]['dated'],dates[field]['undated'],dates[field]['approximate']))
    lines+=['','source_as_of=undated表示原文没有可归属到该数值的统计日期，checked_at仅为采集日期。不得把这些数值表述为2026年精确统计。approximate与original_notation保留“约/近/余/多/以上”等标注；专任教师不改称全部教职工，本科生不改称全体学生。面积换算按1公顷=15亩=10000平方米。','',
        '摘要根据教育部身份信息与官网结构化事实重新组织，不复制宣传段落。校区记录只收明确列示的名称；缺失的地址/坐标保持空值。解析器排除部门简介、其他学校报道、规划人数、新校区面积及留学生内部子群人数。', '',
        '## 追加的开源资料','','| 仓库 | 固定版本 | 匹配记录数 |','| --- | --- | ---: |']
    config=yaml.safe_load((ROOT/'data/external/repositories.yaml').read_text());repos={r['repository']:r for r in config['supplemental_repositories']}
    for r in sources['repositories']:
        repo=repos[r['repository']];lines.append('| [%s](https://github.com/%s) | `%s` | %s |'%(r['repository'],r['repository'],repo['commit'][:12],r['matched']))
    lines+=['','两库均保留MIT许可、固定commit、字段子集哈希和逐校匹配依据。科研经费、实验室、生源细分、性别比例、师资估算、就业行业/雇主等原字段进入可追溯社区快照；估算院士数、笼统就业率与未经校方确认的数据不进入官方统计。Hipo中的历史英文名和域名不覆盖现行官方名称。','',
        '### 开源校徽压缩包','','xioajiumi/Chinese_Universities的固定版本logo.zip中，%s个独立文件按2026完整校名匹配，%s个历史/未匹配名称留在待调查列表，不凭近似名称绑定。'%(len(archive['matched']),len(archive['unmatched'])),
        '文件以元数据和压缩包内路径纳入档案，图像不再分发。download_kind=archive_member的URL不是PNG直链；按archive_member从archive_url下载的压缩包中读取文件，并分别核对archive_sha256与sha256。社区校徽取色仅为参考，不覆盖官方VI颜色。','',
        '另排除%s个假图像文件：上游吕梁学院.png实际为HTML网页，未当作校徽纳入；该校已有另一官网标识文件读取成功。'%len(archive.get('excluded',[])),'',
        '## 访问与缺项','','记录%s次页面读取/失败尝试。'%stats['page_attempts'],'']
    for key,n in sorted(status.items()):lines.append('- `%s`：%s所。'%(key,n))
    lines+=['','失败页会尝试已发现的不同简介URL、首页重新发现的导航入口或另一协议。robots限制与跨校跳转停止；状态只描述本次访问，不认定永久无法获取。阳光高考公开目录本轮返回HTTP 412，未绕过限制；未将搜索摘要直接当作批量统计依据。','',
        '本轮同时评估blyenso-del/gaokao-score、ZsTs119/china-university-database、dataxiv/data-universities及woojoo520/china-university-logos：未取得明确数据再分发许可或对核心视觉/简介缺项无显著新增覆盖，未镜像这些仓库的数据。','',
        '逐校事实见universities/*/*/profile.yaml；批量用indexes/extended-facts.csv、indexes/campuses.csv、indexes/logo-assets.csv和indexes/profiles.jsonl。完整检索及版本台账见data/review/official-overviews-2026.jsonl、logo-archive-2026.json与supplemental-repositories-2026.json。','']
    (ROOT/'docs/overview-enrichment-progress-2026.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(stats,ensure_ascii=False))


if __name__=='__main__':main()
