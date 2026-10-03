#!/usr/bin/env python3
"""Read only missing PPT facts and explicitly labelled school badge previews."""
import argparse
import collections
import concurrent.futures
import csv
import datetime as dt
import hashlib
import json
import pathlib
import re
import urllib.parse

import yaml
from collect_english_names import field_name
from collect_official_extensions import Page, decode, fetch
from discover_official_pages import safe_url
from expand_repository_fields import inspect_bytes
from profile_extensions import put_fact, rgb, upsert
from research_all_schools import Policy
from yaml_io import load_yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
BASE = 'https://www.chinaschool.com.cn'
SITEMAP = BASE + '/k_about/contact_en.html'


def norm(text):
    return re.sub(r'\s+', '', text).replace('（', '(').replace('）', ')')


class SchoolPage(Page):
    def __init__(self):
        super().__init__(); self.badges = []
    def handle_starttag(self, tag, attrs):
        super().handle_starttag(tag, attrs)
        if tag == 'img':
            a = dict(attrs)
            if a.get('src') and a.get('alt'): self.badges.append(dict(src=a['src'], alt=a['alt']))


def info_claims(name, lines):
    """Accept only an exact current Chinese-name block with narrow scalar labels."""
    values = [re.sub(r'\s+', ' ', t).strip() for _, t in lines if t.strip()]
    starts = [i for i,t in enumerate(values) if norm(t) == '中文名' and i+1 < len(values) and norm(values[i+1]) == norm(name)]
    claims = []
    for start in starts:
        window = values[start:start+70]
        for i,label in enumerate(window[:-1]):
            label = norm(label); value = window[i+1]
            if label in {'外文名', '外文名称', '英文名', '英文名称'}:
                english = field_name(value)
                if english:
                    claims.append(dict(field='identity.name_en', value=english,
                        basis='大学志同校资料页“中文名”精确匹配后，“外文名”栏原值；该栏注明整理自百科，属于社区二手记录，非校方命名证明。'))
            if label == '创办时间':
                years = set(re.findall(r'(?<!\d)(1\d{3}|20\d{2})(?!\d)', value))
                if len(years) == 1 and len(value) <= 35 and not re.search(r'筹|更名|拟|迁', value):
                    year = int(next(iter(years)))
                    if year <= dt.date.today().year:
                        claims.append(dict(field='culture.founded_year', value=year, evidence=value,
                            basis='大学志同校资料页“创办时间”栏原值；社区二手记录，未独立确认前身、现名设立或升本口径。'))
    return list({(c['field'],str(c['value'])):c for c in claims}.values())


def collect(job, policy=None):
    identity, source, missing_fields, need_badge = job
    code, name = identity['school_code'], identity['name_zh']
    r = dict(school_code=code, name_zh=name, source=source, checked_at=dt.date.today().isoformat(),
             status='access_or_identity_gap', claims=[], assets=[], attempts=[])
    policy = policy or Policy()
    try:
        final, raw, charset, mime = fetch(source, BASE, policy, timeout=15)
        if mime not in {'text/html', 'application/xhtml+xml'}: raise ValueError('school_page_not_html')
        page = SchoolPage(); page.feed(decode(raw, charset)); page.finish()
        title = re.split(r'\s+-\s+|\s*｜\s*', page.title)[0]
        if norm(title) != norm(name): raise ValueError('current_full_name_page_title_mismatch')
        sha = hashlib.sha256(raw).hexdigest(); r.update(source=final, source_sha256=sha, title=page.title)
        cache = ROOT / 'tmp/chinaschool-core'; cache.mkdir(parents=True, exist_ok=True)
        (cache / (sha + '.html')).write_bytes(raw)
        r['claims'] = [dict(c, source=final, source_sha256=sha) for c in info_claims(name, page.lines) if c['field'] in missing_fields]
        r['website_candidates'] = list(dict.fromkeys(a['href'] for a in page.links if norm(a['label'])==norm(name)
            and safe_url(a['href']) and urllib.parse.urlparse(a['href']).hostname not in {'www.chinaschool.com.cn', 'm.chinaschool.com.cn'}))[:2]
        if need_badge:
            targets = list(dict.fromkeys(urllib.parse.urljoin(final,a['src']) for a in page.badges
                if norm(re.sub(r'[-—·：:]', '', a['alt'])) == norm(name+'校徽')))
            for url in targets[:1]:
                attempt = dict(url=url); r['attempts'].append(attempt)
                try:
                    target, body, _, _ = fetch(url, BASE, policy, limit=8_000_000, timeout=12)
                    meta = inspect_bytes(body, url); colors = meta.pop('colors'); color_basis = meta.pop('color_basis', '')
                    if not meta.get('width') or not meta.get('height') or min(meta['width'],meta['height']) < 80:
                        raise ValueError('badge_preview_too_small_or_no_dimensions')
                    (cache / (meta['sha256'] + '.graphic')).write_bytes(body)
                    asset = dict(asset_id=hashlib.sha256((code+'|'+url).encode()).hexdigest()[:24], title=name+'社区校徽预览', kind='badge',
                        url=target, source=final, file_name=urllib.parse.unquote(urllib.parse.urlparse(url).path.rsplit('/',1)[-1]),
                        upstream_path=None, publisher='大学志 chinaschool.com.cn', official=False, repository=None, commit=None,
                        repository_license=None, asset_license=None, rights_holder=name, verified='auto', checked_at=r['checked_at'], availability='found',
                        source_type='community_website', source_sha256=sha, identity_basis='页面标题为当前完整校名且图像alt精确标注同校校徽；社区关联证据，现行版本未独立确认。',
                        usage_note='社区学校资料页校徽预览；不是校方直接发布，不认定现行VI或图形授权。只保存链接与实际文件元数据，不再分发图形。',
                        colors=colors, color_basis=color_basis, **meta)
                    r['assets'].append(asset); attempt.update(status='content_inspected', sha256=meta['sha256'])
                except Exception as exc: attempt.update(status='access_or_inspection_gap', detail=str(exc)[:140])
        r['status'] = 'school_core_page_read'
    except Exception as exc: r.update(detail=str(exc)[:140], error_type=type(exc).__name__)
    return r


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collect-only', action='store_true'); parser.add_argument('--import-only', action='store_true')
    parser.add_argument('--workers', type=int, default=4); args = parser.parse_args()
    paths = {p.parent.name:p for p in (ROOT / 'universities').glob('*/*/profile.yaml')}
    profiles = {c:load_yaml(p.read_text()) for c,p in paths.items()}; names = {norm(p['identity']['name_zh']):c for c,p in profiles.items()}
    out = ROOT / 'data/review/ppt-core-chinaschool-2026.jsonl'
    records = {r['school_code']:r for r in map(json.loads,out.read_text().splitlines())} if out.exists() else {}
    def save():
        temp = out.with_suffix('.pending'); temp.write_text(''.join(json.dumps(records[c],ensure_ascii=False)+'\n' for c in sorted(records))); temp.replace(out)
    if not args.import_only:
        policy = Policy(); policy.allowed(BASE + '/')
        final, body, encoding, mime = fetch(SITEMAP, BASE, policy, limit=8_000_000, timeout=20)
        page = Page(); page.feed(decode(body,encoding)); page.finish(); sha = hashlib.sha256(body).hexdigest()
        cache = ROOT / 'tmp/chinaschool-core'; cache.mkdir(parents=True, exist_ok=True); (cache / (sha+'.html')).write_bytes(body)
        leads = {}
        for a in page.links:
            name = norm(a['label']); url = urllib.parse.urljoin(final,a['href'])
            if name in names and urllib.parse.urlparse(url).hostname=='www.chinaschool.com.cn' and re.search(r'/i_region/i_[^/]+/a_\d+/a_\d+\.html$',url):
                leads.setdefault(names[name],url)
        regional = ROOT / 'data/review/ppt-core-chinaschool-region-leads-2026.json'
        if regional.exists():
            for code,url in json.loads(regional.read_text())['exact_name_matched_leads'].items():
                if code in profiles and urllib.parse.urlparse(url).hostname=='www.chinaschool.com.cn' and re.search(r'/i_region/i_[^/]+/a_\d+/a_\d+\.html$',url):
                    leads.setdefault(code,url)
        (ROOT / 'data/review/ppt-core-chinaschool-directory-2026.json').write_text(json.dumps(dict(source=final,source_sha256=sha,
            checked_at=dt.date.today().isoformat(), exact_name_matched_leads=leads),ensure_ascii=False,indent=2)+'\n')
        jobs = []
        for code,source in leads.items():
            p = profiles[code]; missing = [f for f in ('identity.name_en','culture.founded_year') if p[f.split('.')[0]][f.split('.')[1]]['availability']=='unresearched']
            need_badge = not any(a.get('access_status')=='content_inspected' for a in p['visual']['logo_assets']) or p['visual']['color_primary']['availability']=='unresearched'
            if (missing or need_badge) and code not in records: jobs.append((p['identity'],source,missing,need_badge))
        print('Exact-name community core pages queued:',len(jobs),'; matched directory schools:',len(leads),flush=True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(collect,j,policy) for j in jobs]
            for n,f in enumerate(concurrent.futures.as_completed(futures),1):
                r = f.result(); records[r['school_code']] = r
                if n%20==0:
                    save(); print('Read',n,'/',len(jobs),'; scalar candidates',sum(len(r['claims']) for r in records.values()),'; inspected badges',sum(len(r['assets']) for r in records.values()),flush=True)
        save()
    if args.collect_only: return
    # A repeated graphic used for different universities needs inspection;
    # reject it here so a generic placeholder cannot inflate badge coverage.
    owners = collections.defaultdict(set)
    for code,r in records.items():
        for a in r['assets']: owners[a['sha256']].add(code)
    review_path = ROOT / 'data/review/ppt-core-chinaschool-visual-decisions-2026.yaml'
    reviews = {d['asset_id']: d for d in load_yaml(review_path.read_text()).get('decisions', [])} if review_path.exists() else {}
    changed = 0; home_leads = []
    for code,r in records.items():
        p = load_yaml(paths[code].read_text()); touched = False
        by_field = collections.defaultdict(list)
        for c in r['claims']: by_field[c['field']].append(c)
        for field,claims in by_field.items():
            g,k = field.split('.')
            if p[g][k]['availability']!='unresearched' or len({str(c['value']) for c in claims})!=1: continue
            c = claims[0]; touched = put_fact(p,field,c['value'],dict(source=c['source'],source_sha256=c['source_sha256'],
                source_type='community_website',verified='auto',checked_at=r['checked_at'],collector='chinaschool_core'),basis=c['basis']) or touched
        for a in r['assets']:
            if len(owners[a['sha256']]) > 1:
                upsert(r.setdefault('excluded_duplicate_graphics',[]),dict(asset_id=a['asset_id'],sha256=a['sha256'],reason='shared_graphic_for_multiple_school_names'),lambda x:x['asset_id']); continue
            decision = reviews.get(a['asset_id'], {})
            if decision.get('sha256') != a['sha256'] or decision.get('school_code') != code or decision.get('decision') != 'accept':
                upsert(r.setdefault('excluded_visual_graphics', []), dict(asset_id=a['asset_id'], sha256=a['sha256'],
                    reason=decision.get('reason', 'visual_review_pending')), lambda x:x['asset_id']); continue
            entry = {k:v for k,v in a.items() if k not in {'colors','color_basis'}}
            entry.update(kind=decision.get('kind', a['kind']), visual_review='auto', visual_review_basis=decision['reason'])
            before = json.dumps(p['visual'],sort_keys=True); upsert(p['visual']['logo_assets'],entry,lambda x:x['asset_id'])
            for value in a['colors'][:2]:
                upsert(p['visual']['color_palette'],dict(value=value,rgb=rgb(value),cmyk=None,pantone=None,label='社区校徽取色参考',role='reference',
                    method='community_logo_sample',official=False,source=a['url'],page_source=a['source'],asset_id=a['asset_id'],source_sha256=a['sha256'],
                    verified='auto',checked_at=r['checked_at'],availability='found',basis=a['color_basis']+'；社区校徽预览的PPT设计参考，不是校方官方VI标准。'),
                    lambda c:(c['source'],c['value'],c['method']))
            touched = json.dumps(p['visual'],sort_keys=True)!=before or touched
        if touched: paths[code].write_text(yaml.safe_dump(p,allow_unicode=True,sort_keys=False,width=100)); changed += 1
        if not p['identity']['official_website'].get('value'):
            for url in r.get('website_candidates',[]): home_leads.append(dict(school_code=code,name_zh=r['name_zh'],url=url,discovery_source=r['source']))
    save()
    with (ROOT / 'data/review/ppt-core-chinaschool-home-leads-2026.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['school_code','name_zh','url','discovery_source']);writer.writeheader();writer.writerows(home_leads)
    print('Core profiles changed:',changed,'; homepage leads:',len(home_leads),flush=True)


if __name__=='__main__': main()
