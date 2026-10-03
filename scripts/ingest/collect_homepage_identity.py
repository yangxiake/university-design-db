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
from discover_official_pages import safe_url, trusted_host, normalize_school_name, matches_school_title
from profile_extensions import put_fact
from research_all_schools import Policy

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUTPUT = ROOT / 'data/review/homepage-identity-2026.jsonl'
PORTAL_HOST = re.compile(r'^(?:en|english|zs|zsb|zsxx|admission|admissions|jwc|xxgk|career|job|jobs|grad|graduate|yjs|yjsy|yz|gs|lib|library|login|my|cas|portal|rsc|cwc|kyc|xcb|bwc|xyh|alumni|xgb|nm)\.', re.I)


def reviewed_homepage_caches(receipts_path, identities):
    bycode={i['school_code']:i for i in identities}
    caches={}
    for r in map(json.loads,receipts_path.read_text().splitlines()):
        identity=bycode[r['school_code']]
        if r.get('status')!='ownership_confirmed' or r['name_zh']!=identity['name_zh'] or r['homepage_url']!=identity['official_website'].get('value'):
            raise ValueError('reviewed_homepage_cache_identity_mismatch')
        sha=r.get('homepage_sha256')or r['source_sha256']
        candidates=[ROOT/'tmp/targeted-vi'/(sha+'.html'),ROOT/'tmp/homepage-identity'/(r['school_code']+'.html')]
        cached=next((p for p in candidates if p.exists()and hashlib.sha256(p.read_bytes()).hexdigest()==sha),None)
        if not cached:raise ValueError('reviewed_homepage_cache_missing_or_changed')
        caches[r['school_code']]=dict(url=r['homepage_url'],sha256=sha,path=str(cached),checked_at=r['checked_at'])
    return caches


def is_school_homepage(url):
    parsed=urllib.parse.urlparse(url)
    host = (parsed.hostname or '').lower().removeprefix('www.')
    if host == 'jysd.com' or host.endswith('.jysd.com') or host == 'bysjy.com.cn' or host.endswith('.bysjy.com.cn'):
        return False
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


def standard_main_host(url):
    host = (urllib.parse.urlparse(url).hostname or '').lower().removeprefix('www.')
    return not host.endswith(('.edu.cn', '.ac.cn')) or len(host.split('.')) == 3


def homepage_title_evidence(name, title, url, names):
    """A sourced main-site candidate must identify the current whole school."""
    parsed=urllib.parse.urlparse(url)
    if parsed.path not in {'','/','/index.htm','/index.html','/index.php'} or not is_school_homepage(url):return None
    heading=normalize_school_name(title)
    if not matches_school_title(name,title,names):return None
    own=normalize_school_name(name)
    if not heading.startswith(own):return None
    suffix=heading[len(own):].strip('-—_|·:：')
    if not suffix or suffix in {'官网','官方网站','官方主页','首页','欢迎您','欢迎访问','门户网站','中文网'}:
        return title
    return None


def collect(row, overrides, names):
    name, code = row['name_zh'], row['school_code']
    result = dict(school_code=code, name_zh=name, checked_at=dt.date.today().isoformat(),
                  status='identity_or_access_gap', attempts=[])
    seeds = row.get('_additional_candidates', []) + [row.get('homepage_url', ''), row.get('candidate_url', '')]
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
    for url in urls[:12]:
        attempt = dict(url=url); result['attempts'].append(attempt)
        if not standard_main_host(url):
            attempt['status'] = 'nonstandard_main_host_requires_independent_evidence'
            continue
        try:
            final, body, charset, mime = fetch(url, url, policy, timeout=row.get('_collection_timeout',10))
            if mime not in {'text/html', 'application/xhtml+xml'}:
                raise ValueError('not_html')
            page = Page(); page.feed(decode(body, charset)); page.finish()
            if re.search(r'学院|学部|附属|研究生|招生|就业|教务|实验室|图书馆|研究院|财务|人事',page.title.replace(name,'')):
                attempt.update(status='school_portal_not_main_homepage',title=page.title[:200]);continue
            evidence = ownership_evidence(name, [t for _, t in page.lines], names)
            basis='候选学校网站明确版权主体为教育部名单中的完整校名；主页或同主机明确首页链接。标题简称、新闻提及与旧名不作为独立确认依据。'
            if not evidence:
                evidence=homepage_title_evidence(name,page.title,final,names)
                if evidence:basis='已有来源的学校主站候选实际返回主首页，标题为当前学校完整名称或完整名称加官网/首页等明确后缀；排除院系、招生子站、新闻题名、母校与旧名。'
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
                          basis=basis)
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
    parser.add_argument('--output', default='data/review/homepage-identity-2026.jsonl', help='Separate batch ledger')
    parser.add_argument('--collect-only', action='store_true')
    parser.add_argument('--timeout', type=int, default=10)
    parser.add_argument('--candidate-file', help='Additional sourced URL leads; every homepage still requires identity evidence')
    parser.add_argument('--school-code', action='append', help='Limit this batch to selected missing school identities')
    args = parser.parse_args()
    if not 1 <= args.timeout <= 60:parser.error('--timeout must be between 1 and 60 seconds')
    output = ROOT / args.output
    profiles = [yaml.load(p.read_text(),Loader=yaml.CSafeLoader) for p in (ROOT/'universities').glob('*/*/profile.yaml')]
    missing = {p['identity']['school_code'] for p in profiles if not p['identity']['official_website'].get('value')}
    names = [p['identity']['name_zh'] for p in profiles]
    with (ROOT/'data/review/official-page-discovery-2026.csv').open(encoding='utf-8-sig') as f:
        rows = [r for r in csv.DictReader(f) if r['school_code'] in missing]
    overrides = {}
    with (ROOT/'data/review/official-site-overrides-2026.csv').open(encoding='utf-8-sig') as f:
        for row in csv.DictReader(f): overrides.setdefault(row['school_code'], []).append(row['candidate_url'])
    if args.candidate_file:
        by_code = {r['school_code']: r for r in rows}
        current_names = {p['identity']['school_code']: p['identity']['name_zh'] for p in profiles}
        with (ROOT/args.candidate_file).open(encoding='utf-8-sig') as f:
            for candidate in csv.DictReader(f):
                code = candidate['school_code']
                if current_names.get(code) != candidate['name_zh']:
                    raise ValueError('candidate_school_identity_mismatch')
                if code not in missing or not safe_url(candidate['url']) or not safe_url(candidate['discovery_source']):
                    continue
                row = by_code.setdefault(code, dict(school_code=code, name_zh=candidate['name_zh']))
                row.setdefault('_additional_candidates', []).append(candidate['url'])
                overrides.setdefault(code, []).append(candidate['url'])
        rows = list(by_code.values())
    if args.school_code: rows = [r for r in rows if r['school_code'] in args.school_code]
    if args.limit: rows = rows[:args.limit]
    records = {r['school_code']: r for r in map(json.loads, output.read_text().splitlines())} if output.exists() else {}
    if not args.import_only:
        def save():
            temporary=output.with_suffix('.jsonl.tmp')
            temporary.write_text(''.join(json.dumps(records[c], ensure_ascii=False)+'\n' for c in sorted(records)), encoding='utf-8')
            temporary.replace(output)
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            for row in rows:row['_collection_timeout']=args.timeout
            futures = {pool.submit(collect, row, overrides, names): row['school_code'] for row in rows}
            for n, future in enumerate(concurrent.futures.as_completed(futures), 1):
                records[futures[future]] = future.result()
                if n % 25 == 0:
                    save()
                    print('Checked %d/%d; confirmed %d.' % (n, len(rows), sum(r['status']=='ownership_confirmed' for r in records.values())), flush=True)
        save()
    if args.collect_only:
        return
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
