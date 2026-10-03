#!/usr/bin/env python3
"""Import source-selected CSS references after checking both cached sources.

These are explicitly labelled website design references, not institutional VI
standards or a claim about the browser's final computed colour.
"""
import hashlib
import json
import pathlib
import re

import yaml

from collect_official_extensions import decode
from collect_ppt_site_colors import ColorPage
from discover_official_pages import matches_school_title
from profile_extensions import put_fact, rgb, upsert
from research_all_schools import SCHOOL_NAMES, same_school
from yaml_io import load_yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]


def normalized(value):
    return re.sub(r'\s+', '', value).lower()


def checked_reference(decision, receipt, identity, html, css):
    if (decision['school_code'] != identity['school_code'] or
            decision['name_zh'] != identity['name_zh'] or
            receipt['name_zh'] != identity['name_zh'] or
            hashlib.sha256(html).hexdigest() != decision['homepage_sha256'] or
            receipt['homepage_sha256'] != decision['homepage_sha256'] or
            hashlib.sha256(css).hexdigest() != decision['source_sha256']):
        raise ValueError('curated_css_source_or_identity_mismatch')
    page = ColorPage(); page.feed(decode(html, None)); page.finish()
    if not matches_school_title(identity['name_zh'], page.title, SCHOOL_NAMES):
        raise ValueError('current_homepage_title_mismatch')
    if not same_school(decision['source'], receipt['homepage_source']):
        raise ValueError('foreign_css_source')
    if not any(p.get('source_url') == decision['source'] and
               p.get('sha256') == decision['source_sha256'] and
               p.get('status') == 'stylesheet_read' for p in receipt['pages']):
        raise ValueError('css_not_in_read_homepage_receipt')
    if not set(decision['homepage_tokens']).issubset(page.tokens):
        raise ValueError('selected_region_not_in_homepage')
    text = re.sub(r'/\*[\s\S]*?\*/', '', decode(css, None))
    rules = [body for selectors, body in re.findall(r'([^{}]+)\{([^{}]*)\}', text)
             if decision['selector'] in [s.strip() for s in selectors.split(',')]]
    if not any(normalized(decision['declaration']) in normalized(body) for body in rules):
        raise ValueError('selected_declaration_not_in_css')
    token = decision['color_literal']
    if normalized(token) not in normalized(decision['declaration']):
        raise ValueError('selected_colour_not_in_declaration')
    if re.fullmatch(r'#[0-9a-fA-F]{6}', token):
        value = token.upper()
    else:
        match = re.fullmatch(r'rgba\(\s*(\d+),\s*(\d+),\s*(\d+),\s*1\s*\)', token)
        if not match or any(int(v) > 255 for v in match.groups()):
            raise ValueError('reference_requires_literal_opaque_rgb')
        value = '#' + ''.join(f'{int(v):02X}' for v in match.groups())
    if value != decision['value']:
        raise ValueError('selected_literal_value_mismatch')
    return value


def main():
    decisions = load_yaml((ROOT/'data/review/core-completion-css-decisions-2026.yaml').read_text())
    receipts = {r['school_code']: r for r in map(json.loads,
        (ROOT/'data/review/ppt-core-site-colors-2026.jsonl').read_text().splitlines())}
    paths = {p.parent.name: p for p in (ROOT/'universities').glob('*/*/profile.yaml')}
    changes = []
    for d in decisions:
        p = load_yaml(paths[d['school_code']].read_text()); r = receipts[d['school_code']]
        cache = ROOT/'tmp/ppt-site-colors'
        value = checked_reference(d, r, p['identity'],
            (cache/(d['homepage_sha256']+'.html')).read_bytes(),
            (cache/(d['source_sha256']+'.css')).read_bytes())
        if p['visual']['color_primary']['availability'] != 'unresearched':
            continue
        meta = dict(source=d['source'], source_type='official_website', verified='auto',
            checked_at=r['checked_at'], method='manual_derived', source_sha256=d['source_sha256'],
            homepage_source=r['homepage_source'], homepage_sha256=d['homepage_sha256'],
            css_selector=d['selector'], css_declaration=d['declaration'],
            collector='curated_site_reference', retrieval='hash_matched_source_review')
        basis = d['reason'] + '；作为PPT设计参考，不是学校官方VI标准；未宣称浏览器最终合成颜色。'
        if put_fact(p, 'visual.color_primary', value, meta, basis=basis):
            upsert(p['visual']['color_palette'], dict(value=value, rgb=rgb(value), cmyk=None,
                pantone=None, label='官网样式PPT建议色', role='reference', official=False,
                availability='found', basis=basis, **meta),
                lambda c: (c['source'], c['value'], c['method']))
            paths[d['school_code']].write_text(yaml.safe_dump(p, allow_unicode=True, sort_keys=False, width=100))
            changes.append(d)
    audit = ROOT/'data/review/core-completion-css-changes-2026.jsonl'
    previous = [json.loads(s) for s in audit.read_text().splitlines()] if audit.exists() else []
    audit.write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in previous+changes))
    print('Curated CSS references added:', len(changes))


if __name__ == '__main__':
    main()
