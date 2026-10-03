#!/usr/bin/env python3
"""Replay this batch's manually selected homepage and CSS colour evidence."""
import hashlib
import json
import pathlib
import re

import yaml

from collect_official_extensions import decode
from collect_ppt_site_colors import ColorPage
from profile_extensions import put_fact, rgb, upsert
from yaml_io import load_yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]


def main():
    decisions_path = ROOT/'data/review/core-completion-extra-css-decisions-2026.yaml'
    decisions = load_yaml(decisions_path.read_text())
    receipts = {r['school_code']: r for r in map(json.loads,
        (ROOT/'data/review/core-completion-extra-home-sources-2026.jsonl').read_text().splitlines())}
    paths = {p.parent.name: p for p in (ROOT/'universities').glob('*/*/profile.yaml')}
    cache = ROOT/'tmp/core-completion/extra-homes'
    profiles = {}; checked = []
    for d in decisions:
        code = d['school_code']; r = receipts[code]; p = load_yaml(paths[code].read_text())
        if p['identity']['name_zh'] != d['name_zh'] or r['name_zh'] != d['name_zh']:
            raise ValueError('current_school_identity_mismatch')
        html = (cache/(r['source_sha256']+'.html')).read_bytes()
        if hashlib.sha256(html).hexdigest() != r['source_sha256']:
            raise ValueError('homepage_hash_mismatch')
        page = ColorPage(); page.feed(decode(html, None)); page.finish()
        if not set(d['homepage_tokens']).issubset(page.tokens):
            raise ValueError('selected_element_not_in_homepage')
        if d.get('source_kind') == 'homepage_inline':
            raw = html
            text = decode(raw, None)
            if d['evidence'] not in text or d['declaration'] not in text or d['source'] != r['source']:
                raise ValueError('inline_evidence_mismatch')
        else:
            raw = (cache/(d['source_sha256']+'.css')).read_bytes()
            text = re.sub(r'/\*[\s\S]*?\*/', '', decode(raw, None))
            bodies = [body for selectors, body in re.findall(r'([^{}]+)\{([^{}]*)\}', text)
                      if d['selector'] in [s.strip() for s in selectors.split(',')]]
            compact = lambda s: re.sub(r'\s+', '', s).lower()
            if not any(compact(d['declaration']) in compact(b) for b in bodies):
                raise ValueError('css_declaration_mismatch')
        if hashlib.sha256(raw).hexdigest() != d['source_sha256']:
            raise ValueError('colour_source_hash_mismatch')
        literal = d['color_literal']
        if literal.startswith('#'):
            value = literal.upper()
        else:
            match = re.fullmatch(r'rgb\(\s*(\d+),\s*(\d+),\s*(\d+)\s*\)', literal)
            if not match or any(int(v) > 255 for v in match.groups()):
                raise ValueError('invalid_literal_rgb')
            value = '#' + ''.join(f'{int(v):02X}' for v in match.groups())
        if value != d['value'] or literal not in d['declaration']:
            raise ValueError('colour_literal_value_mismatch')
        profiles[code] = p; checked.append((d, r))
    changed = 0
    for d, r in checked:
        code = d['school_code']; p = profiles[code]
        d.update(checked_at='2026-10-03', verified='auto', decision='accept',
                 homepage_source=r['source'], homepage_sha256=r['source_sha256'])
        meta = dict(source=d['source'], source_sha256=d['source_sha256'],
            homepage_source=r['source'], homepage_sha256=r['source_sha256'],
            css_selector=d['selector'], css_declaration=d['declaration'],
            source_type='official_website', verified='auto', checked_at=d['checked_at'],
            method='manual_derived', collector='curated_site_reference', retrieval='hash_matched_source_review')
        basis = d['reason'] + '；仅为PPT设计参考，不是学校官方VI标准；保留原始网页与样式哈希。'
        if put_fact(p, 'visual.color_primary', d['value'], meta, basis=basis):
            upsert(p['visual']['color_palette'], dict(value=d['value'], rgb=rgb(d['value']), cmyk=None,
                pantone=None, label='官网样式PPT建议色', role='reference', official=False,
                availability='found', basis=basis, **meta), lambda c: (c['source'], c['value'], c['method']))
            paths[code].write_text(yaml.safe_dump(p, allow_unicode=True, sort_keys=False, width=100)); changed += 1
    decisions_path.write_text(yaml.safe_dump(decisions, allow_unicode=True, sort_keys=False, width=100))
    print('Source-checked additional CSS decisions:', len(checked), '; new facts:', changed)


if __name__ == '__main__':
    main()
