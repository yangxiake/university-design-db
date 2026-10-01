#!/usr/bin/env python3
"""Build rich per-school views and flat indexes from version 3 profiles."""
import argparse
import collections
import csv
import io
import json
import pathlib
import re

import yaml

from profile_extensions import FACTS
from build_indexes import write

ROOT = pathlib.Path(__file__).resolve().parents[2]
STATUS = {'unresearched':'尚未采集', 'not_found':'检索后未找到', 'conflict':'来源存在差异', 'found':'有来源记录'}
METHODS = {'official_vi':'官方VI标准值', 'badge_sample':'校徽取样建议',
           'manual_derived':'官网标识取色/推导建议', 'community_theme':'社区主题配色',
           'community_logo_sample':'社区标识取色建议'}
KINDS = {'badge':'校徽','wordmark':'校名文字','combination':'组合标识','anniversary':'校庆标识','site_identity':'官网页眉标识（构成待核验）'}
BASE_FACTS = {
    'identity.name_en':'英文名称', 'identity.official_website':'官网',
    'culture.founded_year':'创办年份', 'culture.motto':'校训',
    'culture.flower':'校花', 'culture.mascot':'吉祥物', 'culture.anthem':'校歌',
    'resources.official_templates_url':'官方PPT入口',
    'resources.official_template_publisher':'官方资源发布方',
    'resources.official_template_terms':'官方资源使用说明',
}


def cell(value):
    if isinstance(value,(dict,list)):
        value=json.dumps(value,ensure_ascii=False,sort_keys=True)
    return re.sub(r'\s+',' ',str(value if value is not None else '')).replace('|','\\|')


def render_visual(profile):
    name=profile['identity']['name_zh'];visual=profile['visual']
    lines=['# '+name+'：校徽与配色','','由profile.yaml生成。自动采集资料；逐项查看来源、取值方法和资源使用条件。','',
           '## 逐文件校徽与校名资源','','| 类型 | 文件 | 格式 | 尺寸 | 内容检查 | 图形许可 |','| --- | --- | --- | --- | --- | --- |']
    for asset in visual['logo_assets']:
        dimensions=('%s × %s'%(asset['width'],asset['height'])) if asset.get('width') and asset.get('height') else '未声明'
        link=('[压缩包](%s) 内 `%s`'%(asset['archive_url'],cell(asset['archive_member']))) if asset.get('download_kind')=='archive_member' else '[文件](%s)'%asset['url']
        lines.append('| %s | %s · [来源](%s) | %s | %s | %s | %s |'%(KINDS[asset['kind']],link,asset['source'],asset.get('format') or '未知',dimensions,asset['access_status'],asset.get('asset_license') or '未独立声明'))
    if not visual['logo_assets']:
        lines+=['','尚无逐文件校徽记录；可继续查官方VI入口或社区资源。']
    lines+=['','仓库许可和学校标识图形的授权分开记录。content_inspected只说明读取了文件结构，不代表人工确认其现行版本。官网页眉标识的具体构成尚未核验；official表示校方网页发布，不代表VI授权。SVG的viewBox是内部坐标，不等于像素尺寸。','',
            '## 调色板','','| 色名 | HEX | RGB | 用途 | CMYK | Pantone | 取值方法 | 来源 |','| --- | --- | --- | --- | --- | --- | --- | --- |']
    for entry in visual['color_palette']:
        role=entry['role']+('（历史参考）' if entry.get('current') is False else '')
        hex_value='`%s`'%entry['value'] if entry.get('value') else '未公布'
        rgb_value=','.join(map(str,entry['rgb'])) if entry.get('rgb') else '未公布'
        lines.append('| %s | %s | %s | %s | %s | %s | %s | [依据](%s) |'%(cell(entry.get('label')),hex_value,rgb_value,role,cell(entry.get('cmyk')),cell(entry.get('pantone')),METHODS[entry['method']],entry['source']))
    if not visual['color_palette']:
        lines+=['','尚无附来源配色。']
    for key,label in [('color_primary','主色'),('color_secondary','辅色/并列色')]:
        fact=visual[key]
        if fact['availability']=='conflict':
            lines+=['',label+'来源存在差异：'+fact.get('note','')]
            lines+=['- `%s`：[来源](%s)；%s'%(item['value'],item['source'],item.get('basis','')) for item in fact['candidates']]
    lines+=['','建议色和社区主题色不能表述为学校官方标准色；CMYK、Pantone没有来源时留空。仅公布印刷色的规范保留CMYK/Pantone，HEX与RGB标为未公布，不自动转换。current=false的条目是保留的历史参考。','', '## VI资源与下载条件','']
    vi=visual['vi_url']
    if vi['availability']=='found':lines+=['- 现有VI入口：[%s](%s)'%(vi['value'],vi['value'])]
    for entry in visual['vi_resources']:
        lines+=['- [%s](%s)：%s；格式 %s；访问条件 %s。%s[来源](%s)。'%(cell(entry['title']),entry['url'],cell(entry['kinds']),','.join(entry['formats']) or '未知',cell(entry['access_requirement']),'官网记录' if entry.get('official') else '社区记录',entry['source'])]
        if entry.get('publisher') or entry.get('use_scope'):
            scope={'school':'学校通用','department':'院系专用'}.get(entry.get('use_scope'),entry.get('use_scope') or '未明确')
            lines+=['  - 发布者：%s；适用范围：%s%s。'%(cell(entry.get('publisher') or '原发布页'),scope,'；版本年：'+str(entry['edition_year']) if entry.get('edition_year') else '')]
        meta=entry.get('file_metadata') or {}
        if meta.get('format')=='PPTX':
            lines+=['  - 文件结构已读取：%s页；画幅%s；声明字体%s；可编辑文本节点%s；文件SHA256 `%s`。'%(meta['slide_count'],meta['aspect_ratio'],cell('、'.join(meta['font_names']) or '未声明'),meta['editable_text_runs'],meta['sha256'])]
        elif meta:
            lines+=['  - 文件容器已读取：%s；%s字节；读取类型%s；文件SHA256 `%s`。'%(meta['format'],meta['byte_size'],meta['read_kind'],meta['sha256'])]
            for member in meta.get('presentation_members',[]):
                if member['status']=='content_inspected':lines+=['    - 包内 `%s`：%s页；画幅%s。'%(cell(member['path']),member['slide_count'],member['aspect_ratio'])]
        elif entry.get('file_inspection'):
            lines+=['  - 文件读取结果：%s；错误与已尝试网址见profile.yaml。'%entry['file_inspection']['status']]
    lines+=['','更完整的身份、文化、学科和历史数据见[PROFILE.md](PROFILE.md)，机器数据见[profile.yaml](profile.yaml)。','']
    return '\n'.join(lines)


def render_profile(profile):
    identity=profile['identity'];labels=dict(BASE_FACTS,**{key:value[1] for key,value in FACTS.items()})
    lines=['# '+identity['name_zh']+'：资料档案','',
           '学校标识码：`'+identity['school_code']+'`；'+identity['province']+' / '+identity['city']+'；'+identity['level']+'；主管部门：'+identity['authority']+'。','',
           '逐字段资料来自官方或标注的社区来源。自动采集状态不表示全部字段完整，历史记录不等于现行数据。','',
           '## 有来源的信息','','| 字段 | 值 | 来源类型 | 采集日期 | 来源 |','| --- | --- | --- | --- | --- |']
    missing=[]
    for dotted,label in labels.items():
        group,key=dotted.split('.');fact=profile[group][key]
        if fact['availability']=='found':
            lines.append('| %s | %s | %s | %s | [来源](%s) |'%(cell(label),cell(fact['value']),fact.get('source_type','official_or_curated'),fact['checked_at'],fact['source']))
            if fact.get('basis'):
                lines.append('| %s口径 | %s | | | |'%(cell(label),cell(fact['basis'])))
            if fact.get('source_as_of'):
                lines.append('| %s资料时间 | %s | | | |'%(cell(label),'统计日期未标注' if fact['source_as_of']=='undated' else cell(fact['source_as_of'])))
        else:
            missing.append('%s：%s'%(label,STATUS[fact['availability']]))
    lines+=['','## 官网列示校区','','| 校区 | 地址 | 来源 |','| --- | --- | --- |']
    for campus in profile['location']['campuses']:
        lines.append('| %s | %s | [来源](%s) |'%(cell(campus['name']),cell(campus.get('address') or '尚未确认'),campus['source']))
    if not profile['location']['campuses']:lines.append('| 尚未取得明确校区列表 | | |')
    lines+=['','## 视觉资料','','- [校徽、校名文件与调色板](VISUAL.md)','- [官方PPT入口](OFFICIAL.md)']
    if profile['resources'].get('community_resources'):lines+=['- [社区主题与参考资料](COMMUNITY.md)']
    lines+=['','## 排名历史','','| 发布方/榜单 | 年份 | 范围 | 名次 | 分数 | 来源 |','| --- | --- | --- | --- | --- | --- |']
    for item in profile['rankings']['entries']:
        lines.append('| %s / %s | %s | %s | %s | %s | [社区记录](%s) |'%(item['publisher'],item['ranking_name'],item['year'],item['scope'],item['rank'],cell(item['score']),item['source']))
    lines+=['','## 学科评估记录','','| 学科 | 轮次 | 等级 | 来源 |','| --- | --- | --- | --- |']
    for item in profile['academics']['subject_assessments']:
        grade=item['grade'] if item.get('availability','found')=='found' else '冲突：'+'/'.join(c['grade'] for c in item['candidates'])
        lines.append('| %s | %s | %s | [社区节选](%s) |'%(cell(item['subject']),item['round'],grade,item['source']))
    lines+=['','## 录取历史参考','','社区参考值带地区、年份、科类和批次；请查招生官方记录后用于实际报考。','',
            '| 年份 | 地区 | 科类 | 批次 | 最低分 | 最低位次 | 来源 |','| --- | --- | --- | --- | --- | --- | --- |']
    for item in profile['admissions']['cutoffs']:
        lines.append('| %s | %s | %s | %s | %s | %s | [来源](%s) |'%(item['year'],item['region'],item['curriculum'],item['batch'],item['minimum_score'],item['minimum_rank'],item['source']))
    lines+=['','## 可追溯社区快照','']
    for item in profile['community']['snapshots']:
        # Three parent segments reach the repository root from a school folder.
        lines+=['- [%s](../../../%s)：`%s`；资料年份/版本 %s，保留原字段及许可。'%(item['repository'],item['data_path'],item['commit'][:12],item['data_as_of'])]
    lines+=['','## 尚未确认的信息','','、'.join(missing)+'。','',
            '完整字段与出处见[profile.yaml](profile.yaml)。','']
    return '\n'.join(lines)


def save(path,expected,check):
    if check:
        if not path.exists() or path.read_text(encoding='utf-8')!=expected:
            raise ValueError('Stale generated view: '+str(path))
    else:path.write_text(expected,encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args()
    indexes={key:[] for key in ('logo-assets','color-palettes','color-conflicts','extended-facts','rankings','admission-cutoffs','subject-assessments','campuses')}
    enriched=[];exports=[]
    for path in sorted((ROOT/'universities').glob('*/*/profile.yaml')):
        p=yaml.safe_load(path.read_text(encoding='utf-8'));i=p['identity'];base=dict(school_code=i['school_code'],name_zh=i['name_zh'])
        save(path.with_name('VISUAL.md'),render_visual(p),args.check)
        save(path.with_name('PROFILE.md'),render_profile(p),args.check)
        exports.append(json.dumps(p,ensure_ascii=False,sort_keys=True)+'\n')
        for asset in p['visual']['logo_assets']:
            indexes['logo-assets'].append(dict(base,**{key:asset.get(key) for key in (
                'asset_id','kind','url','source','file_name','upstream_path','official','format','width','height','intrinsic_width','intrinsic_height','vector','representation','has_alpha','transparent_background','access_status','repository_license','asset_license','rights_holder','repository','commit','sha256','byte_size','source_type','resolved_url','download_kind','archive_url','archive_member','archive_sha256')}))
        for campus in p['location']['campuses']:
            indexes['campuses'].append(dict(base,**{key:cell(campus.get(key)) for key in ('name','address','coordinates','basis','source','checked_at')}))
        for entry in p['visual']['color_palette']:
            indexes['color-palettes'].append(dict(base,**{key:cell(entry.get(key)) for key in (
                'value','rgb','label','role','method','official','current','basis','source','cmyk','pantone')}))
        for key in ('color_primary','color_secondary'):
            fact=p['visual'][key]
            if fact['availability']=='conflict':
                for candidate in fact['candidates']:
                    indexes['color-conflicts'].append(dict(base,field='visual.'+key,label=fact.get('label',''),value=candidate['value'],
                        source=candidate['source'],basis=candidate.get('basis',''),reason=fact.get('note',''),checked_at=fact['checked_at']))
        found=0
        for dotted,(value_type,label) in FACTS.items():
            group,key=dotted.split('.');fact=p[group][key];found+=fact['availability']=='found'
            if fact['availability']=='found':
                indexes['extended-facts'].append(dict(base,field=dotted,value=json.dumps(fact['value'],ensure_ascii=False),source=fact['source'],source_type=fact.get('source_type','official_or_curated'),source_as_of=fact.get('source_as_of',''),basis=fact.get('basis',''),original_notation=fact.get('original_notation',''),approximate=fact.get('approximate',''),date_basis=fact.get('date_basis',''),verified=fact['verified'],checked_at=fact['checked_at']))
        for name,group,key,columns in [
            ('rankings','rankings','entries',('publisher','ranking_name','year','scope','rank','score','indicators','source','source_as_of')),
            ('admission-cutoffs','admissions','cutoffs',('year','region','curriculum','batch','enrollment_type','minimum_score','minimum_rank','reference_only','source')),
            ('subject-assessments','academics','subject_assessments',('subject','grade','availability','candidates','round','assessment_year','publisher','completeness','source'))]:
            for entry in p[group][key]:
                indexes[name].append(dict(base,**{key:cell(entry.get(key)) for key in columns}))
        enriched.append(dict(base,extended_fact_count=found,logo_asset_count=len(p['visual']['logo_assets']),palette_count=len(p['visual']['color_palette']),
                             ranking_count=len(p['rankings']['entries']),admission_count=len(p['admissions']['cutoffs']),
                             subject_assessment_count=len(p['academics']['subject_assessments']),snapshot_count=len(p['community']['snapshots']),
                             profile_view_path=path.with_name('PROFILE.md').relative_to(ROOT).as_posix(),visual_view_path=path.with_name('VISUAL.md').relative_to(ROOT).as_posix()))
    for name,rows in indexes.items():
        if not rows:raise ValueError('Expected populated index: '+name)
        write(name+'.csv',list(rows[0]),rows,args.check)
    write('enriched-catalog.csv',list(enriched[0]),enriched,args.check)
    save(ROOT/'indexes/profiles.jsonl',''.join(exports),args.check)
    print(('Checked' if args.check else 'Built'),len(enriched),'profile/visual views and enriched indexes.')


if __name__=='__main__':main()
