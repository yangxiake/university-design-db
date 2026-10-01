#!/usr/bin/env python3
"""Report measured field adoption and visual coverage, without global superlatives."""
import collections
import json
import pathlib
import sys

import yaml

ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/ingest'))
from profile_extensions import FACTS, COLLECTIONS

MAPS={
 'basic_2021':{'rank':'rankings.entries[].rank (2021)', 'logo':'visual.logo_assets[].url',
  'name':'identity.name_zh，教育部值优先','name_eng':'identity.name_en','note':'community.snapshots历史标签原值',
  'location':'identity.province，教育部值优先；快照保留原值','type':'institution.school_type',
  'total_score':'rankings.entries[].score','school_level':'rankings.entries[].indicators.school_level','link':'官网候选与社区快照'},
 'basic_2026':{'slug':'identity.external_identifiers','slug_aliases':'identity.slug_aliases','name':'identity.name_en',
  'name_zh':'identity.name_zh，教育部值优先','city':'identity.city，教育部值优先；英文原值保留快照',
  'province':'identity.province，教育部值优先；英文原值保留快照','country':'institution.country',
  'category':'institution.school_type','uni_type':'institution.nature','languages_of_instruction':'institution.languages_of_instruction',
  'website':'官网候选 / resources.english_website','logo_url':'排除已发现的图库照片；原记录保留快照',
  'shanghairanking':'rankings.entries（publisher/year/scope/rank/score/indicators/upstream_url），tags为institution.groups'},
 'panorama':{'id':'community.snapshots原始标识','name':'identity.name_zh，教育部值优先','en':'identity.name_en',
  'abbr':'identity.short_name_zh','enAbbr':'identity.short_name_en','province':'identity.province，教育部值优先',
  'city':'identity.city，教育部值优先','lng':'location.coordinates.longitude','lat':'location.coordinates.latitude',
  'founded':'culture.founded_year，保留社区历史口径','type':'institution.school_type','admin':'identity.authority，教育部值优先',
  'tags':'institution.groups / community.snapshots','tier':'community.snapshots（主观梯队不作客观学校类别）',
  'firstClass':'academics.double_first_class_disciplines；概括/占位文字仅保留快照',
  'aplus':'academics.subject_assessments[].grade=A+','a':'academics.subject_assessments[].grade=A',
  'aminus':'academics.subject_assessments[].grade=A-',
  'score':'admissions.cutoffs（year/region/curriculum/batch/minimum_score/minimum_rank）',
  'emp':'community.snapshots（评论不替代就业率）','intro':'community.snapshots（原始简介，不作为客观事实摘要）'},
 'svg_metadata':{'title':'教育部完整校名匹配','file':'visual.logo_assets（badge）','url':'community.snapshots原始网站线索，未直接覆盖官网',
  'wordmark':'visual.logo_assets（wordmark）'},
 'vi_directory':{'school_name':'identity.short_name_en及学校全称匹配','campus_district':'visual.vi_resources[].campus_district',
  'vi_urls':'visual.vi_resources[].url','kinds':'visual.vi_resources[].kinds','formats':'visual.vi_resources[].formats',
  'access_requirement':'visual.vi_resources[].access_requirement'},
 'logo_tree':{'english_directory':'唯一英文全名匹配','logo_file':'visual.logo_assets[].url/upstream_path',
  'color_variant':'visual.logo_assets[].variant（原文件标记，不自动生成HEX）',
  'dimensions_in_filename':'visual.logo_assets[].dimensions_in_filename（仅提示；尺寸以内容检查为准）'},
 'insight_snapshot':{'层次':'community.snapshots历史标签','城市':'身份表优先；社区快照保留原值',
  '类型':'community.snapshots院校类型原值','一流学科':'community.snapshots，概括/占位文字不当学科名单',
  '网址':'community.snapshots网址线索，不覆盖已确认官网','就业概况':'community.snapshots，保留就业率/深造率/行业/雇主/年份，不作官方统计',
  '科研概况':'community.snapshots，保留经费/实验室/平台/年份，未逐项校方确认',
  '生源概况':'community.snapshots，保留规模/本科硕士博士/性别比/年份，约数不改为精确统计',
  '师资概况':'community.snapshots，完整保留估算/兼职/双聘/来源与核实说明','aliases':'identity.aliases社区检索别名，非正式简称'},
 'domain_snapshot':{'name':'community.snapshots历史英文名称，不覆盖现行英文名','country':'community.snapshots国家原值',
  'domains':'community.snapshots域名数组，完整主机名唯一匹配','web_pages':'community.snapshots网址数组',
  'alpha_two_code':'community.snapshots国家两字母代码','state-province':'community.snapshots省级名称/空值'},
}


def main():
    union=json.loads((ROOT/'data/review/github-field-union-2026.json').read_text())
    supplemental=ROOT/'data/review/supplemental-repositories-2026.json'
    if supplemental.exists():union['repositories']+=json.loads(supplemental.read_text())['repositories']
    counts=collections.Counter();field_counts=collections.Counter();methods=collections.Counter();access=collections.Counter()
    for path in (ROOT/'universities').glob('*/*/profile.yaml'):
        p=yaml.safe_load(path.read_text());a=p['visual']['logo_assets'];c=p['visual']['color_palette']
        counts.update(profiles=1,logo_schools=bool(a),logo_entries=len(a),palette_schools=bool(c),palette_entries=len(c),
                      vi_schools=bool(p['visual']['vi_resources']),vi_entries=len(p['visual']['vi_resources']),
                      ranking_schools=bool(p['rankings']['entries']),ranking_entries=len(p['rankings']['entries']),
                      subject_schools=bool(p['academics']['subject_assessments']),subject_entries=len(p['academics']['subject_assessments']),
                      subject_conflicts=sum(e.get('availability')=='conflict' for e in p['academics']['subject_assessments']),
                      admission_schools=bool(p['admissions']['cutoffs']),admission_entries=len(p['admissions']['cutoffs']),
                      snapshot_schools=bool(p['community']['snapshots']),snapshot_entries=len(p['community']['snapshots']))
        counts.update(campus_schools=bool(p['location']['campuses']),campus_entries=len(p['location']['campuses']),
                      archive_logo_entries=sum(item.get('download_kind')=='archive_member' for item in a))
        official_assets=[item for item in a if item.get('source_type')=='official_website']
        counts.update(official_logo_schools=bool(official_assets),official_logo_entries=len(official_assets),
                      site_identity_entries=sum(item.get('kind')=='site_identity' for item in a))
        access.update(e['access_status'] for e in a);methods.update(e['method'] for e in c)
        for dotted in FACTS:
            group,key=dotted.split('.');field_counts[dotted]+=p[group][key]['availability']=='found'
    lines=['# GitHub字段并集与视觉资料覆盖','','本报告比较本轮实际读取的仓库，不声称穷尽GitHub或已经达到全网最多字段。字段扩展与数据填充分别验收；未找到有来源数值的字段保持未采集。','',
           '## 仓库覆盖比较','','| 仓库 | 原记录数 | 本科完整身份匹配数 | 字段组数 |','| --- | ---: | ---: | ---: |']
    for repo in union['repositories']:
        lines.append('| [%s](https://github.com/%s) | %s | %s | %s |'%(repo['repository'],repo['repository'],repo['records'],repo['matched'],len(repo['fields'])))
    lines+=['','基础数据两库各582条，高校全景库188条且字段较细；地区VI目录和校徽资源库补充下载格式、校名文字、资源访问条件与逐文件内容元数据。范围始终以教育部2026本科名单1412所为准。','',
            '## 上游字段逐项落点','']
    for repo in union['repositories']:
        mode=repo['mode'];mapping=MAPS[mode]
        missing=set(repo['fields'])-set(mapping)
        if missing:raise ValueError('Unmapped upstream fields: '+str(missing))
        lines+=['### '+repo['repository'],'','| 上游字段 | 本库落点/处理 |','| --- | --- |']
        for field in repo['fields']:lines.append('| `%s` | %s |'%(field,mapping[field]))
        lines+=['']
    lines+=['## v3覆盖情况','','| 项目 | 学校数 | 记录数 |','| --- | ---: | ---: |',
            '| 逐文件校徽/校名资源 | %s | %s |'%(counts['logo_schools'],counts['logo_entries']),
            '| 其中官网发布标识文件 | %s | %s |'%(counts['official_logo_schools'],counts['official_logo_entries']),
            '| 结构化配色 | %s | %s |'%(counts['palette_schools'],counts['palette_entries']),
            '| VI规范与下载线索 | %s | %s |'%(counts['vi_schools'],counts['vi_entries']),
            '| 历史排名 | %s | %s |'%(counts['ranking_schools'],counts['ranking_entries']),
            '| 学科评估节选 | %s | %s |'%(counts['subject_schools'],counts['subject_entries']),
            '| 重庆2025录取参考 | %s | %s |'%(counts['admission_schools'],counts['admission_entries']),
            '| 上游字段快照 | %s | %s |'%(counts['snapshot_schools'],counts['snapshot_entries']),
            '| 官网明确列示校区 | %s | %s |'%(counts['campus_schools'],counts['campus_entries']),
            '', '### 校徽文件检查','','| 状态 | 文件数 |','| --- | ---: |']
    for status,n in sorted(access.items()):lines.append('| %s | %s |'%(status,n))
    lines+=['','只有content_inspected读取了文件内容；历史外部CDN地址仅索引，不等于当前可下载。学校现行版本与图形授权未作人工签核。site_identity有%s条，是具体构成待核验的官网页眉标识，不能计为已确认纯校徽。'%counts['site_identity_entries'],'',
            '其中%s条为压缩包内文件：download_kind=archive_member，须读取archive_url、archive_member与archive_sha256；主URL不是PNG直链，文件内容哈希和压缩包哈希分别保存。'%counts['archive_logo_entries'],'',
            '### 配色方法','','| 方法 | 颜色记录数 |','| --- | ---: |']
    for method,n in sorted(methods.items()):lines.append('| %s | %s |'%(method,n))
    lines+=['','颜色数包含多源同色、主/辅色和建议色，不等于有官方标准色的学校数量。社区主题与校徽取色不覆盖主色官方结论。','',
            '### 新增事实字段','','| 字段 | 有来源值的学校数 |','| --- | ---: |']
    for dotted,n in field_counts.items():lines.append('| `%s` | %s |'%(dotted,n))
    lines+=['','## 扩展字段的完整性与口径','','新增27个事实字段与12个结构化集合。地址、校区、邮编、办公联系方式、学生/教职工人数、面积、学位授权、专业录取、招生计划与就业指标已有明确字段，当前无可可靠导入的数据时为空；不从现有字段推断这些数值。','',
            '学科来源内部出现同一学科多个等级时，availability=conflict、grade=null并保留candidates；当前%s条，不自动选择。'%counts['subject_conflicts'],'',
            '学生/教职工人数、面积保留统计日期和basis；未标注日期明确为source_as_of=undated，不能把checked_at当作统计日期。近似/下界数保留original_notation和approximate，专任教师/本科生与全校总量的口径分别标明。录取与计划须带年份、地区、科类、批次和招生类型；排名须带发布方、榜单、年份和范围。校徽保留文件地址、真实格式、宽高、纯矢量判断、透明信息、哈希、独立图形许可与仓库许可。','',
            '原始简介、就业评论、主观tier，以及已发现的占位学科文本完整保存在MIT社区快照中；未当作学校官方事实。发现的Pexels照片不加入校徽集合。','',
            '字段定义见[data/profile-schema-v3.yaml](../data/profile-schema-v3.yaml)，导入台账见[data/review/github-field-union-2026.json](../data/review/github-field-union-2026.json)。','',
            'AI批量读取用indexes/profiles.jsonl；逐项筛选用logo-assets.csv、color-palettes.csv、extended-facts.csv、rankings.csv、subject-assessments.csv和admission-cutoffs.csv。','']
    (ROOT/'docs/github-field-union-2026.md').write_text('\n'.join(lines),encoding='utf-8')
    stats=dict(updated_at=union['updated_at'],counts=dict(counts),asset_access=dict(access),palette_methods=dict(methods),extended_facts=dict(field_counts))
    (ROOT/'data/review/enriched-coverage-2026.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Enriched coverage',json.dumps(dict(counts),ensure_ascii=False))


if __name__=='__main__':main()
