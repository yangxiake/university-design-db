#!/usr/bin/env python3
"""Import visually inspected PPT suggestions while preserving recorded colors."""
import datetime as dt
import csv
import pathlib
import re
import yaml
from seed_profiles import profile_for
from render_official import render
ROOT = pathlib.Path(__file__).resolve().parents[2]

def main():
    with (ROOT / 'data/universities-scope-2026.csv').open(encoding='utf-8-sig') as handle:
        scope = {r['school_code']: r for r in csv.DictReader(handle)}
    decisions = yaml.safe_load((ROOT / 'data/review/sampled-color-decisions-2026.yaml').read_text())
    if len({d['school_code'] for d in decisions}) != len(decisions):
        raise ValueError('Duplicate school in sampled color decisions')
    added = kept = created = 0
    for d in decisions:
        row = scope[d['school_code']]
        if row['name_zh'] != d['name_zh'] or not re.fullmatch(r'#[0-9A-F]{6}', d['value']):
            raise ValueError('Invalid sampled decision')
        if d['method'] not in {'badge_sample', 'manual_derived'}:
            raise ValueError('Sampling cannot assert official VI')
        path = ROOT / 'universities' / row['province'] / row['school_code'] / 'profile.yaml'
        new = not path.exists()
        p = profile_for(row) if new else yaml.safe_load(path.read_text())
        fact = p['visual']['color_primary']
        if p['research']['status'] == 'reviewed' or fact['availability'] != 'unresearched':
            kept += 1
            continue
        fact.update(value=d['value'], source=d['source'], verified='auto',
                    availability='found', checked_at=d['checked_at'], search_sources=[],
                    method=d['method'], label=d['label'], basis=d['basis'],
                    role_note=d['role_note'], page_source=d['page_source'],
                    image_sha256=d['image_sha256'])
        p['research'].update(status='auto_collected', checked_at=d['checked_at'])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(p, allow_unicode=True, sort_keys=False, width=100))
        path.with_name('OFFICIAL.md').write_text(render(p))
        added += 1
        created += new
    print(f'Added {added} labelled color suggestions; kept {kept} recorded colors; {created} new profiles.')

if __name__ == '__main__':
    main()
