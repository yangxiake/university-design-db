#!/usr/bin/env python3
"""Retry core-only visual gaps from sourced school URL leads, before review."""
import argparse
import collections
import concurrent.futures
import copy
import csv
import hashlib
import json
import pathlib
import urllib.parse

import yaml
from collect_header_css_marks import collect
from collect_official_extensions import apply_record
from profile_extensions import put_fact
from yaml_io import load_yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUTPUT = ROOT / 'data/review/core-handoff-visual-sources-2026.jsonl'


def sourced_leads(profiles):
    leads = collections.defaultdict(list)
    for code, profile in profiles.items():
        home = profile['identity']['official_website'].get('value')
        if home:
            leads[code].append(home)
    previous = ROOT / 'data/review/ppt-core-logo-directory-home-sources-2026.jsonl'
    for record in map(json.loads, previous.read_text().splitlines()):
        for attempt in record.get('attempts', []):
            url = attempt.get('url')
            if url and attempt.get('status') != 'robots_disallowed':
                leads[record['school_code']].append(url)
    for path in sorted((ROOT / 'data/review').glob('*home*leads*.csv')):
        for row in csv.DictReader(path.open(encoding='utf-8-sig')):
            for key in ('homepage_url', 'candidate_url'):
                if row.get(key):
                    leads[row['school_code']].append(row[key])
    result = {}
    for code, urls in leads.items():
        hosts = set(); result[code] = []
        for url in urls:
            host = urllib.parse.urlparse(url).hostname
            if host and host not in hosts:
                hosts.add(host); result[code].append(url)
        result[code] = result[code][:3]
    return result


def retry(identity, urls):
    history = []
    for url in urls:
        candidate = copy.deepcopy(identity)
        candidate['official_website']['value'] = url
        record = collect(candidate)
        if any(a.get('access_status') == 'content_inspected' for a in record['assets']):
            record['previous_candidates'] = history
            return record
        history.append(record)
    return dict(school_code=identity['school_code'], name_zh=identity['name_zh'],
                status='no_inspected_current_mark', pages=[], assets=[], claims=[],
                previous_candidates=history)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers', type=int, default=6)
    parser.add_argument('--collect-only', action='store_true')
    parser.add_argument('--decisions', help='Hash-bound decisions for the actual images read')
    args = parser.parse_args()
    paths = {p.parent.name: p for p in (ROOT / 'universities').glob('*/*/profile.yaml')}
    profiles = {code: load_yaml(p.read_text()) for code, p in paths.items()}
    records = {r['school_code']: r for r in map(json.loads, OUTPUT.read_text().splitlines())} if OUTPUT.exists() else {}
    if args.collect_only:
        leads = sourced_leads(profiles)
        jobs = [(p['identity'], leads.get(code, [])) for code, p in profiles.items()
                if code not in records and not any(a.get('access_status') == 'content_inspected' for a in p['visual']['logo_assets'])]
        print('Core visual retry schools:', len(jobs), flush=True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(retry, identity, urls) for identity, urls in jobs]
            for future in concurrent.futures.as_completed(futures):
                record = future.result(); records[record['school_code']] = record
                temporary = OUTPUT.with_suffix('.pending')
                temporary.write_text(''.join(json.dumps(records[c], ensure_ascii=False) + '\n' for c in sorted(records)))
                temporary.replace(OUTPUT)
                print(record['name_zh'], record['status'], flush=True)
        return
    if not args.decisions:
        parser.error('Use --collect-only or supply inspected image --decisions')
    decisions = load_yaml((ROOT / args.decisions).read_text())
    changes = []
    for decision in decisions:
        if decision['decision'] != 'accept':
            continue
        code = decision['school_code']; record = records[code]; p = profiles[code]
        if p['identity']['name_zh'] != decision['name_zh'] or record['name_zh'] != decision['name_zh']:
            raise ValueError('school_identity_mismatch')
        asset = next(a for a in record['assets'] if a['asset_id'] == decision['asset_id'])
        cached = ROOT / 'tmp/targeted-vi' / (asset['sha256'] + '.graphic')
        if asset['sha256'] != decision['sha256'] or hashlib.sha256(cached.read_bytes()).hexdigest() != decision['sha256']:
            raise ValueError('image_review_hash_mismatch')
        selected = copy.deepcopy(asset)
        selected.update(kind=decision['kind'], visual_review='auto', visual_review_basis=decision['reason'])
        selected['usage_note'] += '；当前图形已按学校完整名称作内容核对：' + decision['reason']
        apply_record(p, dict(record, assets=[selected]))
        home_page = next(a for a in record['pages'] if a.get('status') == 'school_page_read')
        if not p['identity']['official_website'].get('value'):
            put_fact(p, 'identity.official_website', home_page['source_url'],
                     dict(source=home_page['source_url'], source_type='official_website', verified='auto',
                          checked_at=record['checked_at'], source_sha256=home_page['source_sha256']),
                     basis='已有来源候选实际返回本校主页，当前完整校名标题或版权主体匹配；同时读取并核对该页引用的现行校名标识。')
        paths[code].write_text(yaml.safe_dump(p, allow_unicode=True, sort_keys=False, width=100))
        changes.append(dict(decision, source=asset['source'], url=asset['url']))
    audit = ROOT / 'data/review/core-handoff-visual-changes-2026.jsonl'
    old = [json.loads(s) for s in audit.read_text().splitlines()] if audit.exists() else []
    audit.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in old + changes))
    print('Current school graphics added:', len(changes))


if __name__ == '__main__':
    main()
