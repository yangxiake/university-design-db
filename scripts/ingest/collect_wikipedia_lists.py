#!/usr/bin/env python3
"""Read labelled founding-year columns and website leads from provincial lists."""
import argparse
import concurrent.futures
import csv
import datetime as dt
import hashlib
import html.parser
import json
import pathlib
import re
import urllib.parse
import urllib.request

import yaml
from collect_wikipedia_core import AGENT, norm
from discover_official_pages import safe_url
from profile_extensions import put_fact
from yaml_io import load_yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
TITLES = [p + '高等学校列表' for p in ['北京市', '天津市', '河北省', '山西省', '内蒙古自治区', '辽宁省', '吉林省',
    '黑龙江省', '上海市', '江苏省', '浙江省', '安徽省', '福建省', '江西省', '山东省', '河南省', '湖北省', '湖南省',
    '广东省', '广西壮族自治区', '海南省', '重庆市', '四川省', '贵州省', '云南省', '西藏自治区', '陕西省', '甘肃省',
    '青海省', '宁夏回族自治区', '新疆维吾尔自治区']]


class Tables(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(); self.tables = []; self.depth = 0; self.table = None; self.row = None; self.cell = None; self.suppressed = 0
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'table':
            self.depth += 1
            if self.depth == 1 and 'wikitable' in (a.get('class') or ''):
                self.table = []
        if self.table is None or self.depth != 1:
            return
        if tag == 'tr': self.row = []
        if tag in {'th', 'td'}: self.cell = dict(text=[], urls=[], header=tag=='th', colspan=int(a.get('colspan') or 1), rowspan=int(a.get('rowspan') or 1))
        if tag == 'sup': self.suppressed += 1
        if tag == 'a' and self.cell is not None and not self.suppressed and safe_url(a.get('href') or ''):
            self.cell['urls'].append(a['href'])
    def handle_data(self, data):
        if self.cell is not None and not self.suppressed: self.cell['text'].append(data)
    def handle_endtag(self, tag):
        if tag == 'sup' and self.suppressed: self.suppressed -= 1
        if tag in {'td', 'th'} and self.cell is not None:
            self.cell['text'] = re.sub(r'\s+', '', ''.join(self.cell['text'])); self.row.append(self.cell); self.cell = None
        if tag == 'tr' and self.row is not None:
            if self.table is not None: self.table.append(self.row)
            self.row = None
        if tag == 'table':
            if self.depth == 1 and self.table is not None: self.tables.append(self.table); self.table = None
            self.depth = max(0, self.depth - 1)


def labelled_rows(tables):
    out = []
    for table in tables:
        headers = None; spans = {}
        for row in table:
            if row and all(c['header'] for c in row):
                if all(c['colspan'] == c['rowspan'] == 1 for c in row): headers = [c['text'] for c in row]; spans = {}
                else: headers = None
                continue
            if not headers:
                continue
            expanded = []; pending = iter(row); next_spans = {}
            for col in range(len(headers)):
                if col in spans:
                    cell, remaining = spans[col]
                    if remaining > 1: next_spans[col] = (cell, remaining-1)
                else:
                    cell = next(pending, None)
                    if cell is None: break
                    if cell['rowspan'] > 1: next_spans[col] = (cell, cell['rowspan']-1)
                if cell['colspan'] != 1: break
                expanded.append(cell)
            spans = next_spans
            if len(expanded) != len(headers) or next(pending, None) is not None:
                continue
            mapping = dict(zip(headers, expanded))
            name = next((mapping[k]['text'] for k in ('学校名称', '学校', '院校名称', '名称') if k in mapping), None)
            year = next((mapping[k]['text'] for k in ('建校时间', '创办时间', '成立时间', '建立时间', '创办年份') if k in mapping), None)
            website = next((u for k in ('网址', '网站', '官方网站') if k in mapping for u in mapping[k]['urls']
                            if 'web.archive.org' not in u), None)
            if name and (year or website): out.append(dict(name_zh=name, founded_year_text=year, website_candidate=website))
    return out


def read(title):
    url = 'https://zh.wikipedia.org/w/api.php?' + urllib.parse.urlencode(dict(action='parse', page=title,
            prop='text|revid', format='json', variant='zh-cn'))
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent':AGENT}), timeout=30) as response:
        raw = response.read(8_000_001)
    if len(raw) > 8_000_000: raise ValueError('wikipedia_list_size_limit')
    data = json.loads(raw)
    if 'parse' not in data: return dict(title=title, status='no_list', rows=[])
    sha = hashlib.sha256(raw).hexdigest(); folder = ROOT / 'tmp/ppt-wikipedia-lists'; folder.mkdir(parents=True, exist_ok=True)
    (folder / (sha + '.json')).write_bytes(raw)
    parser = Tables(); parser.feed(data['parse']['text']['*']); parser.close()
    revision = data['parse']['revid']; source = 'https://zh.wikipedia.org/w/index.php?title=%s&oldid=%s' % (urllib.parse.quote(title), revision)
    return dict(title=title, status='labelled_list_read', source=source, revision=revision, source_sha256=sha,
                checked_at=dt.date.today().isoformat(), rows=labelled_rows(parser.tables))


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--apply', action='store_true'); args = parser.parse_args()
    paths = {p.parent.name:p for p in (ROOT / 'universities').glob('*/*/profile.yaml')}
    profiles = {c:load_yaml(p.read_text()) for c,p in paths.items()}; names = {norm(p['identity']['name_zh']):c for c,p in profiles.items()}
    records = []; changes = []; leads = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(read, t):t for t in TITLES}
        for f in concurrent.futures.as_completed(futures):
            try: r = f.result()
            except Exception as exc: r = dict(title=futures[f], status='access_gap', rows=[], detail=str(exc)[:140])
            r['rows'] = [row for row in r['rows'] if norm(row['name_zh']) in names]
            records.append(r); print('Read provincial lists:', len(records), '/', len(TITLES), '; matched rows', len(r['rows']), flush=True)
    for r in records:
        for row in r['rows']:
            code = names[norm(row['name_zh'])]; p = profiles[code]; year_text = row['founded_year_text'] or ''
            years = set(re.findall(r'(?<!\d)(1\d{3}|20\d{2})(?!\d)', year_text))
            if len(years) == 1 and len(year_text) <= 30 and p['culture']['founded_year']['availability'] == 'unresearched':
                year = int(next(iter(years)))
                if year <= dt.date.today().year and not re.search(r'筹|更名|拟|迁|待', year_text):
                    claim = dict(school_code=code, name_zh=p['identity']['name_zh'], field='culture.founded_year', value=year,
                        source=r['source'], source_sha256=r['source_sha256'], source_revision=r['revision'],
                        checked_at=r['checked_at'], verified='auto', source_type='community_website', collector='wikipedia_labelled_year_column',
                        basis='中文维基百科省级高校列表的明确建校/创办时间栏，按完整现校名匹配；社区数据，未独立确认前身与现名设立口径。', evidence=year_text)
                    changes.append(claim)
                    if args.apply:
                        put_fact(p, claim['field'], year, {k:v for k,v in claim.items() if k not in {'school_code', 'name_zh', 'field', 'value'}})
                        paths[code].write_text(yaml.safe_dump(p, allow_unicode=True, sort_keys=False, width=100))
            if row.get('website_candidate') and not p['identity']['official_website'].get('value'):
                leads.append(dict(school_code=code, name_zh=p['identity']['name_zh'], url=row['website_candidate'], discovery_source=r['source']))
    target = ROOT / 'data/review/ppt-core-wikipedia-lists-2026.json'
    target.write_text(json.dumps(dict(checked_at=dt.date.today().isoformat(), lists=records, new_year_claims=changes), ensure_ascii=False, indent=2)+'\n')
    with (ROOT / 'data/review/ppt-core-wikipedia-list-homes-2026.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['school_code', 'name_zh', 'url', 'discovery_source']); writer.writeheader(); writer.writerows(leads)
    print('New founding-year claims:', len(changes), '; homepage leads:', len(leads))


if __name__ == '__main__':
    main()
