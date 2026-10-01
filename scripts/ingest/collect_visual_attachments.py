#!/usr/bin/env python3
"""Index explicitly named official VI attachments; never execute downloads."""
import argparse
import datetime as dt
import hashlib
import json
import pathlib
import re
import urllib.parse

import yaml
from collect_official_extensions import Page,decode,fetch
from discover_official_pages import safe_url
from profile_extensions import upsert
from research_all_schools import Policy

ROOT=pathlib.Path(__file__).resolve().parents[2]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--decisions',default='data/review/visual-guides-decisions-2026.yaml')
    args=parser.parse_args()
    decisions=yaml.safe_load((ROOT/args.decisions).read_text())
    paths={p.parent.name:p for p in (ROOT/'universities').glob('*/*/profile.yaml')}
    seen=set();records=[];added=0
    for decision in decisions:
        code,url=decision['school_code'],decision['vi_url']
        if (code,url) in seen or urllib.parse.urlparse(url).path.lower().endswith('.pdf'):continue
        seen.add((code,url));record=dict(school_code=code,name_zh=decision['name_zh'],source=url,checked_at=dt.date.today().isoformat(),attachments=[])
        try:
            final,body,charset,mime=fetch(url,url,Policy())
            if mime not in {'text/html','application/xhtml+xml'}:raise ValueError('not_html')
            page=Page();page.feed(decode(body,charset));page.finish()
            record.update(source=final,source_sha256=hashlib.sha256(body).hexdigest(),status='page_read')
            profile=yaml.safe_load(paths[code].read_text())
            if profile['identity']['name_zh']!=decision['name_zh']:raise ValueError('school_identity_mismatch')
            for anchor in page.links:
                link=urllib.parse.urljoin(final,anchor['href'])
                # Many schools use a download endpoint whose URL has no suffix.
                suffix=re.search(r'\.(ai|cdr|pdf|rar|zip)$',anchor['label'],re.I)
                if not suffix or not safe_url(link) or not re.search('标|校徽|校名|VIS|VI|手册|色',anchor['label'],re.I):continue
                entry=dict(title=anchor['label'][:130],url=link,kinds=['色彩规范' if '色' in anchor['label'] else '标识文件'],formats=[suffix[1].upper()],
                           access_requirement='官网明确提供的附件链接；本轮未读取附件内容或核验其当前下载状态，格式按原链接标签',source=final,
                           repository=None,commit=None,official=True,verified='auto',checked_at=record['checked_at'],availability='found',source_sha256=record['source_sha256'],
                           note='只索引下载入口，不再分发文件；链接可能指向学校明确使用的外部文件主机，图形使用须遵守校方规范。')
                added+=upsert(profile['visual']['vi_resources'],entry,lambda x:(x['url'],x['source']))
                record['attachments'].append(dict(title=entry['title'],url=link,declared_format=suffix[1].upper(),content_read=False))
            paths[code].write_text(yaml.safe_dump(profile,allow_unicode=True,sort_keys=False,width=100),encoding='utf-8')
        except Exception as exc:
            record.update(status='access_gap',error_type=type(exc).__name__,detail=str(exc)[:160])
        records.append(record)
    (ROOT/'data/review/visual-attachments-2026.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Added %d official attachment references across %d inspected pages.'%(added,len(records)))


if __name__=='__main__':main()
