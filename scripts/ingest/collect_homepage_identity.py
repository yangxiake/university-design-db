#!/usr/bin/env python3
"""Confirm missing homepages from school-owned copyright declarations.

Only previously sourced candidates are considered. A generic title or news
mention alone is insufficient. Robots and school-domain boundaries apply.
"""
import argparse
import concurrent.futures
import csv
import datetime as dt
import hashlib
import json
import pathlib
import re
import urllib.parse

import yaml
from collect_official_extensions import Page, decode, fetch
from discover_official_pages import safe_url, trusted_host
from profile_extensions import put_fact
from research_all_schools import Policy

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUTPUT = ROOT / 'data/review/homepage-identity-2026.jsonl'
PORTAL_HOST = re.compile(r'^(?:en|english|zs|zsb|zsxx|admission|admissions|jwc|xxgk|career|job|jobs)\.', re.I)


def is_school_homepage(url):
    parsed=urllib.parse.urlparse(url)
    return not PORTAL_HOST.search(parsed.hostname or '') and not re.search(r'^/(?:en|english|admissions?|zsxx)(?:/|$)', parsed.path, re.I)


def ownership_evidence(name, lines, names):
    for line in lines:
        compact = re.sub(r'\s+', '', line)
        if name not in compact:
            continue
        # Limit ownership evidence to the declaration, not adjacent news/links.
        for pattern in (
            r'(?:Copyright|版权(?:所有)?|©|Copyright@)[：:©@()\d.\-—]*' + re.escape(name),
            re.escape(name) + r'(?:权所有|版权所有)',
            r'版权所有[：:©@()\d.\-—]*' + re.escape(name),
        ):
            match = re.search(pattern, compact, re.I)
            if match:
                tail = compact[match.end():match.end()+30]
                # Do not accept a parent name as the prefix of a college owner.
                if any(other != name and other.startswith(name) and
                       compact[match.end()-len(name):].startswith(other)
                       for other in names):
                    continue
                return compact[max(0, match.start()-10):match.end()+min(25, len(tail))]
    return None


def collect(row, overrides, names):
    name, code = row['name_zh'], row['school_code']
    result = dict(school_code=code, name_zh=name, checked_at=dt.date.today().isoformat(),
                  status='identity_or_access_gap', attempts=[])
    seeds = [row.get('homepage_url', ''), row.get('candidate_url', '')]
    seeds += row.get('attempted_urls', '').split('|')
    urls = []
    for seed in seeds:
        if not safe_url(seed):
            continue
        u = urllib.parse.urlparse(seed)
        root = u._replace(path='/', params='', query='', fragment='').geturl()
        for url in (root, seed):
            if url not in urls and is_school_homepage(url) and trusted_host(url, overrides.get(code, [])):
                urls.append(url)
    policy = Policy()
    for url in urls[:6]:
        attempt = dict(url=url); result['attempts'].append(attempt)
        try:
            final, body, charset, mime = fetch(url, url, policy)
            if mime not in {'text/html', 'application/xhtml+xml'}:
                raise ValueError('not_html')
            page = Page(); page.feed(decode(body, charset)); page.finish()
            evidence = ownership_evidence(name, [t for _, t in page.lines], names)
            attempt.update(source_url=final, title=page.title[:200], sha256=hashlib.sha256(body).hexdigest())
            if not evidence:
                attempt['status'] = 'no_school_ownership_declaration'
                continue
            parsed = urllib.parse.urlparse(final)
            if not is_school_homepage(final):
                attempt['status']='school_portal_not_main_homepage'
                continue
            if parsed.path in {'', '/', '/index.htm', '/index.html', '/index.php'}:
                home = final
            else:
                homes = [urllib.parse.urljoin(final, a['href']) for a in page.links
                         if re.sub(r'\s+', '', a['label']) in {'首页', '学校首页', '网站首页'}]
                home = next((h for h in homes if urllib.parse.urlparse(h).netloc == parsed.netloc
                             and urllib.parse.urlparse(h).path in {'', '/', '/index.htm', '/index.html', '/index.php'}), None)
                if not home:
                    attempt['status'] = 'owned_page_without_homepage_link'
                    continue
            attempt.update(status='ownership_confirmed', evidence=evidence)
            result.update(status='ownership_confirmed', homepage_url=home, source=final,
                          title=page.title[:200], source_sha256=attempt['sha256'], evidence=evidence,
                          basis='候选学校网站明确版权主体为教育部名单中的完整校名；主页或同主机明确首页链接。标题简称、新闻提及与旧名不作为独立确认依据。')
            cache = ROOT / 'tmp/homepage-identity'; cache.mkdir(parents=True, exist_ok=True)
            (cache / (code + '.html')).write_bytes(body)
            break
        except Exception as exc:
            attempt.update(status='access_gap', error_type=type(exc).__name__, detail=str(exc)[:160])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers', type=int, default=10)
    parser.add_argument('--import-only', action='store_true')
    parser.add_argument('--limit', type=int)
    args = parser.parse_args()
    profiles = [json.loads(s) for s in (ROOT/'indexes/profiles.jsonl').read_text().splitlines()]
    missing = {p['identity']['school_code'] for p in profiles if not p['identity']['official_website'].get('value')}
    names = [p['identity']['name_zh'] for p in profiles]
    with (ROOT/'data/review/official-page-discovery-2026.csv').open(encoding='utf-8-sig') as f:
        rows = [r for r in csv.DictReader(f) if r['school_code'] in missing]
    overrides = {}
    with (ROOT/'data/review/official-site-overrides-2026.csv').open(encoding='utf-8-sig') as f:
        for row in csv.DictReader(f): overrides.setdefault(row['school_code'], []).append(row['candidate_url'])
    if args.limit: rows = rows[:args.limit]
    records = {r['school_code']: r for r in map(json.loads, OUTPUT.read_text().splitlines())} if OUTPUT.exists() else {}
    if not args.import_only:
        def save():
            temporary=OUTPUT.with_suffix('.jsonl.tmp')
            temporary.write_text(''.join(json.dumps(records[c], ensure_ascii=False)+'\n' for c in sorted(records)), encoding='utf-8')
            temporary.replace(OUTPUT)
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(collect, row, overrides, names): row['school_code'] for row in rows}
            for n, future in enumerate(concurrent.futures.as_completed(futures), 1):
                records[futures[future]] = future.result()
                if n % 25 == 0:
                    save()
                    print('Checked %d/%d; confirmed %d.' % (n, len(rows), sum(r['status']=='ownership_confirmed' for r in records.values())), flush=True)
        save()
    paths = {p.parent.name: p for p in (ROOT/'universities').glob('*/*/profile.yaml')}
    changed = 0
    for code, record in records.items():
        if record['status'] != 'ownership_confirmed': continue
        path = paths[code]; profile = yaml.safe_load(path.read_text())
        if profile['identity']['name_zh'] != record['name_zh']: raise ValueError('school_identity_mismatch')
        if put_fact(profile, 'identity.official_website', record['homepage_url'],
                    dict(source=record['source'], verified='auto', checked_at=record['checked_at'], source_type='official_website'),
                    basis=record['basis'], evidence=record['evidence'], source_sha256=record['source_sha256']):
            path.write_text(yaml.safe_dump(profile, allow_unicode=True, sort_keys=False, width=100), encoding='utf-8'); changed += 1
    print('Added %d confirmed homepages from %d recorded candidate schools.' % (changed, len(records)))


if __name__ == '__main__': main()
