#!/usr/bin/env python3
"""Apply source-checked core conflict decisions, preserving the prior audit."""
import json
import pathlib
import sys
import hashlib

import yaml

from collect_official_extensions import Page, decode
from ppt_scope import is_core_field
from research_all_schools import same_school
from yaml_io import load_yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]


def main():
    decisions = load_yaml((ROOT / 'data/review/ppt-core-conflict-decisions-2026.yaml').read_text(encoding='utf-8'))
    paths = {p.parent.name: p for p in (ROOT / 'universities').glob('*/*/profile.yaml')}
    audit = []; changed = 0
    for item in decisions:
        path = paths[item['school_code']]; p = load_yaml(path.read_text(encoding='utf-8'))
        if item['name_zh'] != p['identity']['name_zh'] or not is_core_field(item['field']):
            raise ValueError('Core decision identity mismatch')
        if not same_school(item['source'], p['identity']['official_website']['value']):
            raise ValueError('Core decision outside school source')
        raw = (ROOT / 'tmp/targeted-vi' / (item['source_sha256'] + '.html')).read_bytes()
        if hashlib.sha256(raw).hexdigest() != item['source_sha256']:
            raise ValueError('Core source hash mismatch')
        page = Page(); page.feed(decode(raw, None)); page.finish()
        text = ''.join(t for foot, t in page.lines if not foot)
        normalize = lambda s: ''.join(str(s).split())
        if normalize(item['evidence_phrase']) not in normalize(text):
            raise ValueError('Core decision evidence changed: ' + item['school_code'])
        group, key = item['field'].split('.'); old = p[group][key]
        if old.get('verified') == 'human':
            continue
        if old['availability'] == 'found' and old['value'] == item['value']:
            continue
        audit.append(dict(school_code=item['school_code'], field=item['field'], previous=old,
                          adopted=dict(item), status='source_checked_correction'))
        p[group][key] = dict(value=item['value'], source=item['source'], verified='auto',
            checked_at=item['checked_at'], availability='found', search_sources=[], source_type='official_website',
            source_sha256=item['source_sha256'], basis=item['basis'], collector='ppt_core_source_reconciliation')
        path.write_text(yaml.safe_dump(p, allow_unicode=True, sort_keys=False, width=100), encoding='utf-8'); changed += 1
    target = ROOT / 'data/review/ppt-core-conflict-changes-2026.jsonl'
    old = [json.loads(line) for line in target.read_text().splitlines()] if target.exists() else []
    target.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in old + audit), encoding='utf-8')
    print('Reconciled PPT core facts:', changed)


if __name__ == '__main__':
    main()
