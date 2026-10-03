#!/usr/bin/env python3
"""Collect only missing PPT name, founding-year and motto facts from public pages."""
import argparse
import concurrent.futures
import csv
import datetime as dt
import json
import pathlib
import urllib.parse

import yaml

from profile_extensions import put_fact
from research_all_schools import Policy, classify, extract_claims, foreign_article, read_page, same_school
from yaml_io import load_yaml
from ppt_core_extraction import additional_claims

ROOT = pathlib.Path(__file__).resolve().parents[2]
FIELDS = {'identity.name_en', 'culture.founded_year', 'culture.motto'}


def missing(profile):
    return {f for f in FIELDS if profile[f.split('.')[0]][f.split('.')[1]]['availability'] == 'unresearched'}


def collect(profile, previous, discovery, max_pages):
    identity = profile['identity']; name = identity['name_zh']
    home = identity['official_website'].get('value')
    result = dict(school_code=identity['school_code'], name_zh=name, home=home,
                  checked_at=dt.date.today().isoformat(), collector='ppt_core_only', pages=[], claims=[],
                  missing_fields=sorted(missing(profile)), status='needs_confirmed_homepage')
    if not home:
        return result
    pending = [(k, discovery[k + '_url']) for k in ('overview', 'history') if discovery.get(k + '_url')]
    pending += [(p['kind'], p.get('source_url') or p['requested_url']) for p in previous.get('pages', [])
                if p['kind'] in {'overview', 'history', 'charter', 'culture', 'english'} and p.get('status') == 'read']
    pending.append(('homepage', home))
    seen = set(); policy = Policy()
    while pending and len(result['pages']) < max_pages:
        kind, url = pending.pop(0)
        if url in seen or not same_school(url, home):
            continue
        seen.add(url)
        attempt = dict(kind=kind, requested_url=url); result['pages'].append(attempt)
        if not policy.allowed(url):
            attempt['status'] = 'robots_disallowed'; continue
        try:
            final, title, text, links, mime, sha = read_page(url, home)
            if foreign_article(title, name) or name not in title + text:
                raise ValueError('school_identity_gap')
            attempt.update(status='read', source_url=final, title=title, sha256=sha, content_kind=mime)
            for claim in extract_claims(name, kind, title, text, final) + additional_claims(name, kind, title, text, final):
                if claim['field'] in result['missing_fields']:
                    result['claims'].append(dict(claim, source_sha256=sha))
            for label, href in links:
                page_kind = classify(label)
                if page_kind in {'overview', 'history', 'charter', 'culture', 'english', 'navigation'}:
                    link = urllib.parse.urljoin(final, href).split('#')[0]
                    if same_school(link, home) and link not in seen:
                        pending.append((page_kind, link))
        except Exception as exc:
            attempt.update(status='access_gap', error_type=type(exc).__name__, detail=str(exc)[:140])
    result['status'] = 'read_partial' if any(p['status'] == 'read' for p in result['pages']) else 'access_gap'
    result['claims'] = list({json.dumps(c, ensure_ascii=False, sort_keys=True): c for c in result['claims']}.values())
    return result


def apply(profile, record):
    changed = False
    for field in FIELDS:
        group, key = field.split('.')
        if profile[group][key]['availability'] != 'unresearched':
            continue
        claims = [c for c in record['claims'] if c['field'] == field]
        values = {json.dumps(c['value'], ensure_ascii=False): c for c in claims}
        if len(values) != 1:
            continue
        claim = next(iter(values.values()))
        changed = put_fact(profile, field, claim['value'], dict(source=claim['source'],
            verified='auto', checked_at=record['checked_at'], source_type='official_website',
            source_sha256=claim['source_sha256'], collector='ppt_core_only'),
            basis=claim.get('basis') or '学校公开页面明确记载的主字段；未采集动态统计') or changed
    return changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='data/review/ppt-core-pass01-2026.jsonl')
    parser.add_argument('--workers', type=int, default=16)
    parser.add_argument('--max-pages', type=int, default=5)
    parser.add_argument('--collect-only', action='store_true')
    parser.add_argument('--import-only', action='store_true')
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    paths = {p.parent.name: p for p in (ROOT / 'universities').glob('*/*/profile.yaml')}
    profiles = {c: load_yaml(p.read_text(encoding='utf-8')) for c, p in paths.items()}
    previous = {r['school_code']: r for r in map(json.loads, (ROOT / 'data/review/school-research-2026.jsonl').read_text().splitlines())}
    with (ROOT / 'data/review/official-page-discovery-2026.csv').open(encoding='utf-8-sig') as f:
        discovery = {r['school_code']: r for r in csv.DictReader(f)}
    target = ROOT / args.output
    records = {r['school_code']: r for r in map(json.loads, target.read_text().splitlines())} if target.exists() else {}
    def save():
        temporary = target.with_suffix('.jsonl.tmp')
        temporary.write_text(''.join(json.dumps(records[c], ensure_ascii=False) + '\n' for c in sorted(records)), encoding='utf-8')
        temporary.replace(target)
    if not args.import_only:
        selected = [p for c, p in profiles.items() if missing(p) and (not args.resume or c not in records)]
        print('PPT core schools queued:', len(selected), flush=True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(collect, p, previous.get(p['identity']['school_code'], {}),
                                  discovery.get(p['identity']['school_code'], {}), args.max_pages) for p in selected]
            for n, future in enumerate(concurrent.futures.as_completed(futures), 1):
                record = future.result(); records[record['school_code']] = record
                if n % 50 == 0:
                    save(); print('Collected %s/%s schools; %s explicit core claims.' % (n, len(selected), sum(len(r['claims']) for r in records.values())), flush=True)
        save()
    if args.collect_only:
        return
    touched = 0
    for code, record in records.items():
        profile = load_yaml(paths[code].read_text(encoding='utf-8'))
        if apply(profile, record):
            paths[code].write_text(yaml.safe_dump(profile, allow_unicode=True, sort_keys=False, width=100), encoding='utf-8'); touched += 1
    print('Core profiles changed:', touched, flush=True)


if __name__ == '__main__':
    main()
