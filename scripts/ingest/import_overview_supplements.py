#!/usr/bin/env python3
"""Validate selected school counter cards against live HTML, then import facts."""
import hashlib
import json
import pathlib
import re

import yaml
from collect_official_extensions import Page,fetch,decode
from research_all_schools import Policy
from collect_official_overviews import apply_record,summary

ROOT=pathlib.Path(__file__).resolve().parents[2]


def main():
    decisions=yaml.safe_load((ROOT/'data/review/overview-supplement-decisions-2026.yaml').read_text())
    paths={p.parent.name:p for p in (ROOT/'universities').glob('*/*/profile.yaml')}
    records=[]
    for school in decisions['schools']:
        path=paths[school['school_code']];profile=yaml.safe_load(path.read_text())
        home=profile['identity']['official_website']['value']
        final,body,charset,mime=fetch(school['source'],home,Policy())
        page=Page();page.feed(decode(body,charset));page.finish()
        compact=re.sub(r'\s+','',''.join(t for foot,t in page.lines if not foot))
        if page.title.strip()!=school['title'] or not re.search(school['date_pattern'],compact):raise ValueError('School/date evidence changed')
        sha=hashlib.sha256(body).hexdigest();claims=[]
        for claim in school['claims']:
            if not re.search(claim['evidence_pattern'],compact):raise ValueError('Counter evidence changed: '+claim['field'])
            claims.append(dict(field=claim['field'],value=claim['value'],source=final,basis=claim['basis']+'；统计时间'+school['source_as_of'],
                source_as_of=school['source_as_of'],date_basis=school['date_pattern'],original_notation=claim['original_notation'],approximate=False,source_sha256=sha))
        campuses=[]
        if school.get('campuses'):
            if not re.search(school['campus_pattern'],compact):raise ValueError('Campus evidence changed')
            campuses=[dict(name=name,address=None,coordinates=None,source=final,basis='官网简介明确列出的校区，校园与校区层级分开；地址/坐标未推断',verified='auto',checked_at=decisions['checked_at']) for name in school['campuses']]
        claims.append(dict(field='overview.summary_zh',value=summary(profile,claims,campuses),source=final,
            basis='根据教育部身份表与官网结构化统计/校区事实重新组织的短摘要；不复制简介原文',source_as_of=school['source_as_of']))
        record=dict(school_code=school['school_code'],name_zh=profile['identity']['name_zh'],checked_at=decisions['checked_at'],
            pages=[dict(source_url=final,title=page.title,sha256=sha)],claims=claims,campuses=campuses,status='counter_cards_inspected')
        apply_record(profile,record);path.write_text(yaml.safe_dump(profile,allow_unicode=True,sort_keys=False,width=100),encoding='utf-8');records.append(record)
    (ROOT/'data/review/overview-supplement-results-2026.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Imported verified counter cards:',len(records),'schools')


if __name__=='__main__':main()
