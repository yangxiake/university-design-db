#!/usr/bin/env python3
"""Select a PPT reference primary from already inspected and sourced logo palettes."""
import datetime as dt
import json
import pathlib

import yaml

from profile_extensions import empty_fact, put_fact
from yaml_io import load_yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]


def candidate(profile):
    visual = profile['visual']
    assets = {a['asset_id']: a for a in visual['logo_assets'] if a.get('access_status') == 'content_inspected'
              and a.get('kind') in {'badge', 'combination', 'wordmark', 'site_identity'}}
    choices = []
    for entry in visual['color_palette']:
        if not entry.get('value') or entry.get('current') is False:
            continue
        if entry['method'] == 'official_vi' and entry.get('role') == 'primary':
            choices.append(((2, 0, 0), entry, None)); continue
        if entry['method'] not in {'badge_sample', 'manual_derived', 'community_logo_sample'}:
            continue
        asset = assets.get(entry.get('asset_id'))
        if asset is None:
            asset = next((a for a in assets.values() if a['url'] == entry['source']), None)
        rgb = entry.get('rgb') or []
        if asset is None or len(rgb) != 3 or min(rgb) > 210:
            continue
        choices.append(((1, int(bool(asset.get('official'))), int(max(rgb) - min(rgb) >= 25), int(asset['kind'] == 'badge')), entry, asset))
    return max(choices, key=lambda row: row[0], default=None)


def main():
    decisions = []
    for path in sorted((ROOT / 'universities').glob('*/*/profile.yaml')):
        p = load_yaml(path.read_text(encoding='utf-8')); current = p['visual']['color_primary']
        if current['availability'] not in {'unresearched', 'not_found'} or current.get('verified') == 'human':
            continue
        selected = candidate(p)
        if not selected:
            continue
        _, entry, asset = selected; previous = current['availability']
        if previous == 'not_found':
            p['visual']['color_primary'] = empty_fact()
        official = entry['method'] == 'official_vi'
        metadata = dict(source=entry['source'], checked_at=dt.date.today().isoformat(), verified='auto',
                        method='official_vi' if official else ('manual_derived' if asset['kind'] == 'site_identity' else 'badge_sample'),
                        source_type='official_website' if official or asset.get('official') else 'community_website',
                        collector='ppt_core_palette_selection', previous_status=previous,
                        original_palette_method=entry['method'])
        if asset:
            metadata.update(asset_id=asset['asset_id'], source_sha256=asset.get('sha256'))
        basis = entry['basis'] if official else (
            '从已读取的%s文件及已有取色记录选择PPT设计建议主色；%s；不是学校官方VI标准色。' %
            ('官网标识' if asset.get('official') else '社区标识', entry['basis']))
        if put_fact(p, 'visual.color_primary', entry['value'], metadata, basis=basis[:480]):
            path.write_text(yaml.safe_dump(p, allow_unicode=True, sort_keys=False, width=100), encoding='utf-8')
            decisions.append(dict(school_code=p['identity']['school_code'], name_zh=p['identity']['name_zh'],
                                  value=entry['value'], source=entry['source'], method=metadata['method'],
                                  asset_id=metadata.get('asset_id'), previous_status=previous, basis=basis))
    out = ROOT / 'data/review/ppt-core-primary-decisions-2026.jsonl'
    old = {r['school_code']: r for r in map(json.loads, out.read_text().splitlines())} if out.exists() else {}
    old.update({r['school_code']: r for r in decisions})
    out.write_text(''.join(json.dumps(old[c], ensure_ascii=False) + '\n' for c in sorted(old)), encoding='utf-8')
    print('Added sourced PPT primary colors:', len(decisions))


if __name__ == '__main__':
    main()
