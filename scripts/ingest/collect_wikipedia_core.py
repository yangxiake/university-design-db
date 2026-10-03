#!/usr/bin/env python3
"""Read current Chinese Wikipedia university infoboxes, keeping fixed revisions."""
import argparse
import concurrent.futures
import csv
import datetime as dt
import hashlib
import json
import pathlib
import re
import urllib.parse
import urllib.request

import yaml
from collect_english_names import field_name
from discover_official_pages import safe_url
from profile_extensions import put_fact
from yaml_io import load_yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
AGENT = 'UniversityDesignDB/0.1 (+https://github.com/yangxiake/university-design-db)'


def norm(value):
    return re.sub(r'\s+', '', value).replace('（', '(').replace('）', ')')


def fields(text):
    start = re.search(r'\{\{[^\S\n]*(?:Infobox[ _]University|Infobox[ _]university|高校|大学|大學)[^\S\n]*(?=\n|\|)', text, re.I)
    if not start:
        return {}
    depth = 1; pos = start.end(); end = len(text)
    for match in re.finditer(r'\{\{|\}\}', text[pos:]):
        depth += 1 if match[0] == '{{' else -1
        if depth == 0:
            end = pos + match.start(); break
    block = text[start.end():end]
    # A line-oriented extraction avoids treating arguments inside a nested
    # template as university data. Only narrow scalar keys are subsequently read.
    return {re.sub(r'[_\s]+', '', m[1].lower()):m[2].strip() for m in re.finditer(
        r'^[^\S\n]*\|[^\S\n]*([^=\n|]+)[^\S\n]*=[^\S\n]*(.*?)(?=\n[^\S\n]*\||\Z)', block, re.M | re.S)}


def scalar(value):
    value = re.sub(r'<ref\b[^>]*(?:/>|>[\s\S]*?</ref>)', '', value, flags=re.I)
    value = re.sub(r'\[\[([^\]|]+)\|([^\]]+)\]\]', r'\2', value)
    value = re.sub(r'\[\[([^\]]+)\]\]', r'\1', value)
    value = value.replace("'''", '').replace("''", '')
    return value.strip()


def core_claims(text):
    info = fields(text); claims = []
    for key in ('englishname', 'nativename', '外文名称', '外文名稱', '英文名称', '英文名稱', '英文名'):
        if key not in info:
            continue
        value = field_name(scalar(info[key]))
        if value:
            claims.append(dict(field='identity.name_en', value=value,
                basis='当前完整校名的中文维基百科大学信息框EnglishName/外文名称字段；社区记录，非校方命名证明。'))
    for key in ('established', '建校', '创建', '創建', '成立', '创办时间', '創辦時間', '建校时间', '建校時間', '創校', '創立', '創校日期', '成立時間'):
        if key not in info:
            continue
        value = scalar(info[key]); years = set(re.findall(r'(?<!\d)(1\d{3}|20\d{2})(?!\d)', value))
        if len(years) == 1 and not re.search(r'\{\{|\}\}|筹建|籌建|更名|迁|遷|拟|擬', value):
            year = int(next(iter(years)))
            if year <= dt.date.today().year:
                claims.append(dict(field='culture.founded_year', value=year,
                    basis='中文维基百科大学信息框Established/建校字段原值；社区记录，未独立确认现名设立与前身起点口径。', evidence=value[:120]))
    return list({(c['field'], str(c['value'])):c for c in claims}.values()), info


def batch(names):
    url = 'https://zh.wikipedia.org/w/api.php?' + urllib.parse.urlencode(dict(action='query', format='json',
        prop='revisions|info', rvprop='ids|content', rvslots='main', titles='|'.join(names), converttitles=1, redirects=1))
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent':AGENT}), timeout=30) as response:
        raw = response.read(15_000_001)
    if len(raw) > 15_000_000:
        raise ValueError('wikipedia_response_size_limit')
    sha = hashlib.sha256(raw).hexdigest(); folder = ROOT / 'tmp/ppt-core-wikipedia'; folder.mkdir(parents=True, exist_ok=True)
    (folder / (sha + '.json')).write_bytes(raw)
    query = json.loads(raw)['query']
    normalized = {r['from']:r['to'] for r in query.get('normalized', []) + query.get('converted', [])}
    redirects = {r['from']:r['to'] for r in query.get('redirects', [])}
    pages = {p['title']:p for p in query.get('pages', {}).values()}
    out = {}
    for name in names:
        title = normalized.get(name, name)
        while title in normalized:
            title = normalized[title]
        if title in redirects and norm(redirects[title]) != norm(title):
            out[name] = dict(status='redirect_to_different_school_name', title=title, redirect_to=redirects[title], claims=[]); continue
        p = pages.get(title)
        if not p or 'missing' in p or not p.get('revisions'):
            out[name] = dict(status='no_current_name_article', title=title, claims=[]); continue
        revision = p['revisions'][0]; text = revision['slots']['main']['*']
        claims, info = core_claims(text)
        source = 'https://zh.wikipedia.org/w/index.php?title=%s&oldid=%s' % (urllib.parse.quote(title), revision['revid'])
        website = info.get('website') or info.get('网站') or info.get('網站') or ''
        found = re.search(r'https?://[^\s|\]}<>]+', website)
        candidate = found[0].rstrip('/.,，。') if found and safe_url(found[0]) else None
        if not candidate:
            found = re.search(r'\*\s*\[(https?://[^\s\]]+)\s+' + re.escape(title) + r'\]', text)
            candidate = found[1] if found and safe_url(found[1]) else None
        out[name] = dict(status='current_name_article_read', title=title, page_id=p['pageid'], revision=revision['revid'],
                        source=source, source_sha256=sha, claims=claims, website_candidate=candidate,
                        raw_infobox_fields=sorted(info), image_lead=info.get('image') or info.get('logo'))
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collect-only', action='store_true'); parser.add_argument('--import-only', action='store_true'); args = parser.parse_args()
    paths = {p.parent.name:p for p in (ROOT / 'universities').glob('*/*/profile.yaml')}
    profiles = {c:load_yaml(p.read_text()) for c,p in paths.items()}
    names = {p['identity']['name_zh']:c for c,p in profiles.items()}
    out = ROOT / 'data/review/ppt-core-wikipedia-2026.jsonl'
    records = {r['school_code']:r for r in map(json.loads, out.read_text().splitlines())} if out.exists() else {}
    def save():
        temp = out.with_suffix('.pending'); temp.write_text(''.join(json.dumps(records[c], ensure_ascii=False) + '\n' for c in sorted(records))); temp.replace(out)
    if not args.import_only:
        targets = [p['identity']['name_zh'] for c,p in profiles.items() if c not in records and (
            p['identity']['name_en']['availability'] == 'unresearched' or p['culture']['founded_year']['availability'] == 'unresearched'
            or not p['identity']['official_website'].get('value') or not p['visual']['logo_assets'])]
        print('Wikipedia current-name articles queued:', len(targets), flush=True)
        groups = [targets[i:i+20] for i in range(0, len(targets), 20)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            futures = {pool.submit(batch, g):g for g in groups}
            for future in concurrent.futures.as_completed(futures):
                try:
                    rows = future.result()
                except Exception as exc:
                    rows = {n:dict(status='access_gap', claims=[], detail=str(exc)[:140]) for n in futures[future]}
                for name,r in rows.items():
                    code = names[name]; r.update(school_code=code, name_zh=name, checked_at=dt.date.today().isoformat())
                    r['claims'] = [c for c in r['claims'] if profiles[code][c['field'].split('.')[0]][c['field'].split('.')[1]]['availability'] == 'unresearched']
                    records[code] = r
                save(); print('Read', len(records), 'articles;', sum(len(r['claims']) for r in records.values()), 'new core candidates.', flush=True)
    if args.collect_only:
        return
    changed = 0; leads = []
    for code,r in records.items():
        p = load_yaml(paths[code].read_text()); touched = False
        by_field = collections_by_field(r['claims'])
        for field, claims in by_field.items():
            group, key = field.split('.')
            if p[group][key]['availability'] != 'unresearched':
                continue
            if len({str(c['value']) for c in claims}) != 1:
                continue
            c = claims[0]
            touched = put_fact(p, field, c['value'], dict(source=r['source'], source_type='community_website', checked_at=r['checked_at'],
                verified='auto', source_sha256=r['source_sha256'], source_revision=r['revision'], collector='wikipedia_core_infobox'), basis=c['basis']) or touched
        if touched:
            paths[code].write_text(yaml.safe_dump(p, allow_unicode=True, sort_keys=False, width=100)); changed += 1
        if r.get('website_candidate') and not p['identity']['official_website'].get('value'):
            leads.append(dict(school_code=code, name_zh=r['name_zh'], url=r['website_candidate'], discovery_source=r['source']))
    with (ROOT / 'data/review/ppt-core-wikipedia-home-leads-2026.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['school_code', 'name_zh', 'url', 'discovery_source']); writer.writeheader(); writer.writerows(leads)
    print('Wikipedia core profiles changed:', changed, '; sourced homepage leads:', len(leads))


def collections_by_field(claims):
    out = {}
    for claim in claims:
        out.setdefault(claim['field'], []).append(claim)
    return out


if __name__ == '__main__':
    main()
