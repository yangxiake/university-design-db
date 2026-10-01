#!/usr/bin/env python3
"""Report collected official extensions separately from school/profile counts."""
import collections
import json
import pathlib
import yaml

ROOT=pathlib.Path(__file__).resolve().parents[2]
FIELDS={'institution.nature':'办学性质','location.address':'通讯地址','location.postal_code':'邮编',
        'contacts.phone':'公开办公/招生电话','contacts.email':'公开邮箱','resources.admissions_url':'招生入口',
        'resources.career_url':'就业入口','resources.english_website':'英文网站','resources.information_disclosure_url':'信息公开入口'}


def main():
    ledger=[json.loads(line) for line in (ROOT/'data/review/official-extensions-2026.jsonl').read_text().splitlines()]
    status=collections.Counter(r['status'] for r in ledger);errors=collections.Counter();visits=collections.Counter()
    facts=collections.Counter();official=collections.Counter();assets=collections.Counter();palette=collections.Counter()
    claims=collections.Counter(c['field'] for r in ledger for c in r['claims'])
    for row in ledger:
        for visit in row['pages']:
            visits[visit['status']]+=1
            if visit['status']=='access_gap':errors[visit.get('detail','unknown')]+=1
    for path in (ROOT/'universities').glob('*/*/profile.yaml'):
        p=yaml.safe_load(path.read_text())
        for dotted in FIELDS:
            group,key=dotted.split('.');fact=p[group][key]
            if fact['availability']=='found':
                facts[dotted]+=1
                official[dotted]+=fact.get('source_type') in {'official_website','official_registry'}
        school_assets=[a for a in p['visual']['logo_assets'] if a.get('source_type')=='official_website']
        assets.update(schools=bool(school_assets),entries=len(school_assets));assets.update(a['access_status'] for a in school_assets)
        references=[a for a in p['visual']['color_palette'] if a.get('asset_id') in {asset['asset_id'] for asset in school_assets}]
        palette.update(schools=bool(references),entries=len(references))
    stats=dict(ledger_schools=len(ledger),school_status=dict(status),page_visits=dict(visits),claim_fields=dict(claims),
               current_facts=dict(facts),official_facts=dict(official),official_identity_assets=dict(assets),official_mark_sample_references=dict(palette),
               excluded_claims=sum(len(r.get('excluded_claims',[])) for r in ledger),excluded_assets=sum(len(r.get('excluded_assets',[])) for r in ledger))
    (ROOT/'data/review/official-extension-coverage-2026.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    lines=['# 官网扩展补采进度','','范围为教育部2026本科名单1412所；已建档数量、实际读取网页和有来源字段分别统计。','',
           '## 联系、性质与门户覆盖','','| 字段 | 有来源学校数 | 其中本轮明确官网/教育部来源 |','| --- | ---: | ---: |']
    for dotted,label in FIELDS.items():lines.append('| %s | %s | %s |'%(label,facts[dotted],official[dotted]))
    lines+=['','办学性质只从教育部明确“民办”备注补入；空备注不推断公办。官网联系方式保留短证据和用途口径。门户确认的是官网导航中的链接，未把链接发现当作目标页访问成功。','',
            '## 官网标识与参考色','','- 官网发布标识文件：%s所，%s条；读取内容元数据成功%s条，仍访问/解析失败%s条。'%(assets['schools'],assets['entries'],assets['content_inspected'],assets['inspection_failed']),
            '- 官网标识取色建议：%s所，%s条；均为非官方参考色，不替代VI标准色。'%(palette['schools'],palette['entries']),
            '- 已排除%s条占位/不完整联系或门户线索、%s条不合格标识图片；排除原因保留在采集台账。'%(stats['excluded_claims'],stats['excluded_assets']),
            '','site_identity表示页眉标识构成待核验；不能把这项学校数写作“已确认纯校徽学校数”。只保存文件链接与内容元数据，不分发图像。','',
            '## 采集状态','','| 状态 | 学校数 |','| --- | ---: |']
    for state,count in sorted(status.items()):lines.append('| %s | %s |'%(state,count))
    lines+=['','| 页面状态 | 次数 |','| --- | ---: |']
    for state,count in sorted(visits.items()):lines.append('| %s | %s |'%(state,count))
    lines+=['','无可用主页候选的学校本轮未访问；已确认官网优先，既有候选主页须再次通过完整校名检查后才采集字段。机器人策略、访问失败及身份不符单独记账，不推断资料不存在。每校首先读取首页，再按必要尝试同路径另一协议、学校联系页和最多两个页眉标识文件。','',
            '完整台账见[data/review/official-extensions-2026.jsonl](../data/review/official-extensions-2026.jsonl)，汇总见[official-extension-coverage-2026.json](../data/review/official-extension-coverage-2026.json)。','']
    (ROOT/'docs/official-extension-progress-2026.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(stats,ensure_ascii=False))


if __name__=='__main__':main()
