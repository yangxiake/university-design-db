#!/usr/bin/env python3
"""Read fixed Wikidata revisions for PPT core facts after exact school matching."""
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

from profile_extensions import put_fact
from yaml_io import load_yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
TODAY = dt.date.today().isoformat()


def norm(value):
    return re.sub(r'\s+', '', value).replace('（', '(').replace('）', ')')


def claims_for(entity, name, require_education_description=False):
    names = [v['value'] for k, v in entity.get('labels', {}).items() if k.startswith('zh')]
    names += [v['value'] for k, values in entity.get('aliases', {}).items() if k.startswith('zh') for v in values]
    if norm(name) not in {norm(n) for n in names}:
        return [], 'exact_chinese_name_gap'
    descriptions = ' '.join(v['value'] for k, v in entity.get('descriptions', {}).items()
                            if k.startswith('zh') or k == 'en')
    if require_education_description and (not re.search(r'大学|学院|高等|学校|本科|university|college|higher education', descriptions, re.I)
            or re.search(r'disambiguation|消歧义|学报|journal|football|球队|附属中学|高中|primary school', descriptions, re.I)):
        return [], 'education_entity_identity_gap'
    out = []
    for prop, field in [('P571', 'culture.founded_year'), ('P1451', 'culture.motto')]:
        statements = [c for c in entity.get('claims', {}).get(prop, []) if c.get('rank') != 'deprecated'
                      and c.get('mainsnak', {}).get('snaktype') == 'value' and not c.get('qualifiers')]
        preferred = [c for c in statements if c.get('rank') == 'preferred']
        if preferred:
            statements = preferred
        values = {}
        for statement in statements:
            value = statement['mainsnak']['datavalue']['value']
            if prop == 'P571':
                match = re.match(r'^\+(\d{4})-', value.get('time', ''))
                if not match or value.get('precision', 0) < 9 or value.get('before') or value.get('after'):
                    continue
                result = int(match[1])
                if not 1000 <= result <= dt.date.today().year:
                    continue
                basis = 'Wikidata P571成立时间；社区结构化记录，未独立确认为学校现名设立年或前身起点。'
            else:
                if not value.get('language', '').startswith('zh') or not 2 <= len(value.get('text', '')) <= 40:
                    continue
                result = value['text']; basis = 'Wikidata P1451中文校训；社区记录，不标作校方直接发布。'
            references = [snak['datavalue']['value'] for reference in statement.get('references', [])
                          for snak in reference.get('snaks', {}).get('P854', []) if snak.get('snaktype') == 'value']
            values[json.dumps(result, ensure_ascii=False)] = dict(field=field, value=result, property=prop,
                statement_id=statement['id'], basis=basis, reference_urls=references)
        if len(values) == 1:
            out.append(next(iter(values.values())))
    english = entity.get('labels', {}).get('en', {}).get('value')
    if english and re.search(r'University|College|Institute|Academy|School', english) and not re.search(r'former|former university|campus|department', english, re.I):
        out.append(dict(field='identity.name_en', value=english, property='label:en',
                        basis='同校Wikidata条目英文标签；社区名称记录，非校方命名证明。'))
    return out, 'exact_school_matched'


def read_batch(ids):
    url = 'https://www.wikidata.org/w/api.php?' + urllib.parse.urlencode(dict(action='wbgetentities',
        ids='|'.join(ids), format='json', props='labels|aliases|descriptions|claims|info'))
    request = urllib.request.Request(url, headers={'User-Agent': 'UniversityDesignDB/0.1 (+https://github.com/yangxiake/university-design-db)'})
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read(12_000_001)
    if len(body) > 12_000_000:
        raise ValueError('entity_response_size_limit')
    entities = json.loads(body)['entities']; sha = hashlib.sha256(body).hexdigest()
    cache = ROOT / 'tmp/ppt-core-wikidata'; cache.mkdir(parents=True, exist_ok=True)
    (cache / (sha + '.json')).write_bytes(body)
    return entities, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--apply', action='store_true')
    parser.add_argument('--include-label-only', action='store_true', help='Require a current university/college description for exact-label candidates')
    args = parser.parse_args()
    paths = {p.parent.name: p for p in (ROOT / 'universities').glob('*/*/profile.yaml')}
    profiles = {c: load_yaml(p.read_text(encoding='utf-8')) for c, p in paths.items()}
    with (ROOT / 'data/review/wikidata-candidates-2026.csv').open(encoding='utf-8-sig') as f:
        accepted = {'exact_unique_classed', 'exact_unique_label_only'} if args.include_label_only else {'exact_unique_classed'}
        rows = [r for r in csv.DictReader(f) if r['match_status'] in accepted and '|' not in r['wikidata_items']]
    selected = {r['wikidata_items'].rsplit('/', 1)[-1]: r for r in rows if r['wikidata_items'] and any(
        profiles[r['school_code']][g][k]['availability'] == 'unresearched' for g, k in
        [('identity', 'name_en'), ('culture', 'founded_year'), ('culture', 'motto')])}
    ids = list(selected); records = []; touched = set()
    print('Wikidata core entities queued:', len(ids), flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(read_batch, ids[i:i+40]): ids[i:i+40] for i in range(0, len(ids), 40)}
        for future in concurrent.futures.as_completed(futures):
            try:
                entities, sha = future.result()
            except Exception as exc:
                for qid in futures[future]:
                    records.append(dict(school_code=selected[qid]['school_code'], entity=qid, status='access_gap', detail=str(exc)[:120]))
                continue
            for qid, entity in entities.items():
                row = selected[qid]; code = row['school_code']; claims, status = claims_for(entity, row['name_zh'], row['match_status'] == 'exact_unique_label_only')
                revision = entity.get('lastrevid'); source = 'https://www.wikidata.org/w/index.php?title=%s&oldid=%s' % (qid, revision)
                usable = [c for c in claims if profiles[code][c['field'].split('.')[0]][c['field'].split('.')[1]]['availability'] == 'unresearched']
                records.append(dict(school_code=code, name_zh=row['name_zh'], entity=qid, revision=revision,
                    status=status, source=source, source_sha256=sha, checked_at=TODAY, claims=usable))
                if args.apply and revision and status == 'exact_school_matched':
                    profile = load_yaml(paths[code].read_text(encoding='utf-8'))
                    for claim in usable:
                        if put_fact(profile, claim['field'], claim['value'], dict(source=source, source_type='wikidata',
                            checked_at=TODAY, verified='auto', source_revision=revision, source_sha256=sha,
                            wikidata_property=claim['property'], collector='ppt_core_wikidata'), basis=claim['basis']):
                            touched.add(code)
                    paths[code].write_text(yaml.safe_dump(profile, allow_unicode=True, sort_keys=False, width=100), encoding='utf-8')
            print('Read', len(records), 'entities;', sum(len(r.get('claims', [])) for r in records), 'core claims.', flush=True)
    target = ROOT / 'data/review/ppt-core-wikidata-2026.jsonl'
    previous = {r['school_code']:r for r in map(json.loads, target.read_text().splitlines())} if target.exists() else {}
    for record in records:
        old = previous.get(record['school_code'])
        if old:
            record['previous_collections'] = old.get('previous_collections', []) + [{k:v for k,v in old.items() if k != 'previous_collections'}]
        previous[record['school_code']] = record
    target.write_text(''.join(json.dumps(previous[c], ensure_ascii=False) + '\n' for c in sorted(previous)), encoding='utf-8')
    print('Wikidata core profiles changed:', len(touched))


if __name__ == '__main__':
    main()
