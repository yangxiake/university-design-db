#!/usr/bin/env python3
"""Read English main sites explicitly linked from confirmed Chinese homepages."""
import argparse
import concurrent.futures
import datetime as dt
import hashlib
import json
import pathlib
import re
import urllib.parse

import yaml

from collect_official_extensions import Page, decode, fetch
from discover_official_pages import matches_school_title
from profile_extensions import put_fact
from research_all_schools import Policy, same_school, SCHOOL_NAMES
from yaml_io import load_yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]


def field_name(value):
    """Read an explicitly labelled name for an exactly matched school.

    Independent colleges can officially use 'School Of' or 'Faculty of' in
    their own names; the stricter main-site title filter remains separate.
    """
    name = re.sub(r'\s+', ' ', value.replace('，', ',')).strip()
    if not re.fullmatch(r"[A-Za-z][A-Za-z ,&.'’()\-]{5,180}", name):
        return None
    if not re.search(r'\b(?:University|College|Institute|Academy|Conservatory|Polytechnic)\b', name, re.I):
        return None
    if re.search(r'\b(?:Office|Admission|Admissions|News|Journal|Library|Research Center)\b', name, re.I):
        return None
    return name


def title_name(title):
    name = re.sub(r'^(?:Welcome\s+to\s+|The\s+Official\s+Website\s+of\s+)', '', title.strip(), flags=re.I)
    name = re.split(r'\s*[|｜]\s*|\s+-\s+|\s+—\s+', name)[0].strip()
    if not re.fullmatch(r"[A-Za-z][A-Za-z ,&.'’()\-]{5,130}", name):
        return None
    if not re.search(r'\b(?:University|College|Institute|Academy|Conservatory|Polytechnic)\b', name, re.I):
        return None
    if re.search(r'\b(?:Department|Office|Admission|Admissions|News|Journal|Library|School of|Faculty of|Research Center)\b', name, re.I):
        return None
    return name


def collect(identity):
    code, name, home = identity['school_code'], identity['name_zh'], identity['official_website']['value']
    result = dict(school_code=code, name_zh=name, home=home, checked_at=dt.date.today().isoformat(),
                  status='access_or_name_gap', attempts=[], claims=[])
    policy = Policy()
    try:
        final, body, charset, mime = fetch(home, home, policy, timeout=10)
        if mime not in {'text/html', 'application/xhtml+xml'}:
            raise ValueError('homepage_not_html')
        page = Page(); page.feed(decode(body, charset)); page.finish()
        if not matches_school_title(name, page.title, SCHOOL_NAMES):
            raise ValueError('homepage_current_name_gap')
        home_sha = hashlib.sha256(body).hexdigest(); result['homepage_sha256'] = home_sha
        links = [urllib.parse.urljoin(final, a['href']) for a in page.links
                 if re.sub(r'\s+', '', a['label']).lower() in {'english', 'en', '英文版', '英文', 'englishversion'}]
        for url in list(dict.fromkeys(links))[:2]:
            if not same_school(url, home):
                continue
            attempt = dict(requested_url=url); result['attempts'].append(attempt)
            try:
                english_url, payload, encoding, kind = fetch(url, home, policy, timeout=10)
                if kind not in {'text/html', 'application/xhtml+xml'}:
                    raise ValueError('english_main_site_not_html')
                english = Page(); english.feed(decode(payload, encoding)); english.finish()
                value = title_name(english.title)
                if value is None:
                    raise ValueError('english_title_is_not_school_name')
                sha = hashlib.sha256(payload).hexdigest()
                attempt.update(status='english_school_name_read', source_url=english_url, title=english.title, sha256=sha)
                result['claims'].append(dict(field='identity.name_en', value=value, source=english_url,
                    source_sha256=sha, homepage_source=final, homepage_sha256=home_sha,
                    basis='当前中文主站明确English/英文版链接指向的同校英文主页，标题列出完整英文学校名；非院系或招生页。'))
                result['status'] = 'english_name_read'; break
            except Exception as exc:
                attempt.update(status='access_or_name_gap', detail=str(exc)[:140], error_type=type(exc).__name__)
        if not result['attempts']:
            result['status'] = 'no_explicit_english_homepage_link'
    except Exception as exc:
        result.update(error_type=type(exc).__name__, detail=str(exc)[:140])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collect-only', action='store_true'); parser.add_argument('--import-only', action='store_true')
    parser.add_argument('--workers', type=int, default=12); args = parser.parse_args()
    paths = {p.parent.name:p for p in (ROOT / 'universities').glob('*/*/profile.yaml')}
    profiles = {c:load_yaml(p.read_text(encoding='utf-8')) for c,p in paths.items()}
    out = ROOT / 'data/review/ppt-core-english-sites-2026.jsonl'
    records = {r['school_code']:r for r in map(json.loads, out.read_text().splitlines())} if out.exists() else {}
    def save():
        temporary = out.with_suffix('.jsonl.tmp'); temporary.write_text(''.join(json.dumps(records[c], ensure_ascii=False) + '\n' for c in sorted(records)), encoding='utf-8'); temporary.replace(out)
    if not args.import_only:
        targets = [p['identity'] for c,p in profiles.items() if p['identity']['name_en']['availability']=='unresearched'
                   and p['identity']['official_website'].get('value') and c not in records]
        print('Official English homepages queued:', len(targets), flush=True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(collect, i) for i in targets]
            for n,future in enumerate(concurrent.futures.as_completed(futures),1):
                record = future.result(); records[record['school_code']] = record
                if n%30 == 0:
                    save(); print('Read %s/%s; English names %s.' % (n, len(targets), sum(r['status']=='english_name_read' for r in records.values())), flush=True)
        save()
    if args.collect_only:
        return
    changed = 0
    for code,record in records.items():
        p = load_yaml(paths[code].read_text(encoding='utf-8'))
        for claim in record['claims']:
            group, key = claim['field'].split('.')
            if p[group][key]['availability'] != 'unresearched':
                continue
            if put_fact(p, claim['field'], claim['value'], dict(source=claim['source'], source_type='official_website',
                verified='auto', checked_at=record['checked_at'], source_sha256=claim['source_sha256'],
                homepage_source=claim['homepage_source'], homepage_sha256=claim['homepage_sha256'], collector='official_english_main_site'), basis=claim['basis']):
                paths[code].write_text(yaml.safe_dump(p, allow_unicode=True, sort_keys=False, width=100), encoding='utf-8'); changed += 1
    print('Official English names added:', changed)


if __name__ == '__main__':
    main()
