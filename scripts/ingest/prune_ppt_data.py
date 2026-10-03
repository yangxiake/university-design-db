#!/usr/bin/env python3
"""Apply the approved PPT scope to profiles and licensed upstream subsets."""
import hashlib
import json
import pathlib

import yaml

from ppt_scope import core_profile
from yaml_io import load_yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
RECORD_KEYS = {
    'Hipo__university-domains-list': {'name', 'domains', 'web_pages'},
    'realJerryKing__university-insight': {'网址'},
    'Magicdover__China-Universities-2026': {'name', 'abbr', 'en', 'enAbbr', 'founded', 'province', 'city', 'admin'},
    'xioajiumi__Chinese_Universities': {'name', 'name_eng', 'location', 'link', 'logo'},
    'damitheswitch__china-universities-dataset': {'name', 'name_zh', 'province', 'city', 'website'},
}


def main():
    changed = 0
    for path in sorted((ROOT / 'universities').glob('*/*/profile.yaml')):
        before = load_yaml(path.read_text(encoding='utf-8'))
        after = core_profile(before)
        if after != before:
            path.write_text(yaml.safe_dump(after, allow_unicode=True, sort_keys=False, width=100), encoding='utf-8'); changed += 1
    for folder, allowed in RECORD_KEYS.items():
        path = ROOT / 'data/external' / folder / 'matched-fields.jsonl'
        rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
        for row in rows:
            key = 'record' if 'record' in row else 'upstream_record'
            row[key] = {k: v for k, v in row[key].items() if k in allowed}
        raw = ''.join(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n' for row in rows).encode('utf-8')
        path.write_bytes(raw)
        manifest_path = path.with_name('FIELDS-SOURCE.yaml')
        manifest = load_yaml(manifest_path.read_text(encoding='utf-8'))
        manifest.update(sha256=hashlib.sha256(raw).hexdigest(), retained_record_fields=sorted(allowed),
                        projection_scope='data/ppt-core-fields.yaml', projected_at='2026-10-02',
                        purpose='仅保留PPT身份主字段与素材入口；原上游commit与许可保持。')
        manifest_path.write_text(yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False), encoding='utf-8')
    print('Core projection changed profiles:', changed, '; projected upstream subsets:', len(RECORD_KEYS))


if __name__ == '__main__':
    main()
