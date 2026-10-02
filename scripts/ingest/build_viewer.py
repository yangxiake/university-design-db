#!/usr/bin/env python3
"""Build a lightweight catalog and regional metadata bundles; no media/network access."""
import argparse
from collections import defaultdict
import hashlib
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / 'viewer/data'


def dumps(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n'


def descriptors(record):
    items = []
    for asset in record['logos']['candidates']:
        items.append(dict(type='logo', official=asset['official'],
                          formats=[str(asset['format']).upper()] if asset.get('format') else [],
                          kind=asset['kind'], transparent=asset.get('transparent_background'),
                          status=asset['access_status']))
    for group in ('official_digital', 'official_print_only', 'references'):
        for color in record['colors'][group]:
            items.append(dict(type='color', official=color['method'] == 'official_vi', formats=[],
                              status='print_only' if color.get('value') is None else color['method']))
    for resource in record['templates']['resources']:
        items.append(dict(type='template' if 'template' in resource['category'] else 'visual_file',
                          official=resource['official'], formats=[f.upper() for f in resource['formats']],
                          status=resource.get('file_inspection_status') or resource.get('download_status') or 'indexed_not_fetched'))
    for file in record['templates']['inspected_presentations']:
        items.append(dict(type='presentation', official=file['official'], formats=['PPTX'], status='content_inspected'))
    # Identical predicates need one search descriptor; full records stay in regional bundles.
    return list({dumps(item): item for item in items}.values())


def catalog_row(record):
    search_names = []
    for key in ('name_en', 'short_name_en', 'short_name_zh', 'aliases'):
        fact = record['identity'][key]
        if fact['availability'] == 'found':
            search_names.extend(fact['value'] if isinstance(fact['value'], list) else [fact['value']])
    return dict(school_code=record['school_code'], name_zh=record['name_zh'], province=record['province'],
                city=record['city'], scope_tags=record['scope_tags'], search_names=search_names,
                color_status=record['colors']['screen_status'], logo_count=len(record['logos']['candidates']),
                inspected_logo_count=sum(a['access_status'] == 'content_inspected' for a in record['logos']['candidates']),
                color_count=sum(len(record['colors'][k]) for k in ('official_digital', 'official_print_only', 'references')),
                template_count=sum('template' in r['category'] for r in record['templates']['resources']),
                presentation_count=len(record['templates']['inspected_presentations']), materials=descriptors(record))


def build(records, source_bytes):
    if len(records) != 1412 or len({r['school_code'] for r in records}) != 1412:
        raise ValueError('Viewer school_code: expected 1412 unique identities')
    groups = defaultdict(dict)
    for record in records:
        groups[record['province']][record['school_code']] = record
    rows = [catalog_row(r) for r in records]
    catalog = dict(viewer_data_version=1, ppt_export_version=1,
                   source_path='indexes/ppt-profiles.jsonl', source_sha256=hashlib.sha256(source_bytes).hexdigest(),
                   school_count=len(rows), provinces=sorted(groups),
                   tags=sorted({t for r in rows for t in r['scope_tags']}),
                   formats=sorted({f for r in rows for m in r['materials'] for f in m['formats']}),
                   schools=rows)
    files = {'catalog.json': dumps(catalog)}
    for province, schools in sorted(groups.items()):
        files['provinces/' + province + '.json'] = dumps(dict(viewer_data_version=1, province=province, schools=schools))
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    raw = (ROOT / 'indexes/ppt-profiles.jsonl').read_bytes()
    records = [json.loads(line) for line in raw.decode('utf-8').splitlines()]
    expected = build(records, raw)
    found = {p.relative_to(OUT).as_posix() for p in OUT.rglob('*.json')}
    stale = sorted(found - set(expected))
    if stale:
        raise ValueError('Unexpected viewer metadata files: ' + ', '.join(stale))
    for name, content in expected.items():
        path = OUT / name
        if args.check:
            if not path.exists() or path.read_text(encoding='utf-8') != content:
                raise ValueError('Stale viewer metadata: viewer/data/' + name)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')
    print(('Checked' if args.check else 'Generated') + ' viewer: 1412 schools, %d regional bundles.' % (len(expected)-1))


if __name__ == '__main__':
    main()
