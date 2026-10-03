#!/usr/bin/env python3
"""Recover actual neutral logo colours as explicitly labelled PPT references."""
import collections
import datetime as dt
import hashlib
import io
import json
import pathlib
import zipfile
import xml.etree.ElementTree as ET

from PIL import Image
import yaml

from expand_repository_fields import inspect_bytes, parse_hex
from profile_extensions import put_fact, rgb, upsert
from yaml_io import load_yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]


def cached_bytes(asset):
    sha = asset['sha256']
    for folder in ('targeted-vi', 'community-logo-gaps', 'official-archive-logos', 'chinaschool-core', 'ppt-core-eol'):
        directory = ROOT / 'tmp' / folder
        for path in directory.glob(sha + '.*'):
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() == sha:
                return raw
    if asset.get('download_kind') == 'archive_member':
        candidates = [ROOT / 'tmp/template-files' / (asset['archive_sha256'] + '.bin')]
        if asset.get('commit'):
            candidates.append(ROOT / 'tmp/archives' / (asset['commit'] + '-logos.zip'))
        for path in candidates:
            if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != asset['archive_sha256']:
                continue
            with zipfile.ZipFile(path) as z:
                info = next((member for member in z.infolist()
                             if member.filename == asset['archive_member'] or
                             archive_name(member) == asset['archive_member']), None)
                if info is None:
                    continue
                if info.file_size > 20_000_000:
                    continue
                raw = z.read(info)
                if hashlib.sha256(raw).hexdigest() == sha:
                    return raw
    return None


def archive_name(member):
    """Match the decoded display path without changing the pinned ZIP bytes."""
    if member.flag_bits & 0x800:
        return member.filename
    try:
        return member.filename.encode('cp437').decode('gb18030')
    except (UnicodeEncodeError, UnicodeDecodeError):
        return member.filename


def neutral_color(raw, asset):
    metadata = inspect_bytes(raw, asset['file_name'])
    if metadata['colors']:
        return None  # The chromatic palette path handles these files.
    counts = collections.Counter()
    if metadata['format'] == 'svg':
        # Only simple explicit SVG fills are read here; complex authoring SVG
        # and embedded bitmaps remain in the existing inspection workflow.
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            return None
        for element in root.iter():
            import re
            fills = [element.get('fill') or ''] + re.findall(
                r'(?:^|[;{])\s*fill\s*:\s*([^;}]+)', element.get('style', '') + ';' +
                (element.text or '' if element.tag.endswith('style') else ''))
            for fill in fills:
                value = parse_hex(fill)
                if value and max(rgb(value)) < 230 and max(rgb(value)) - min(rgb(value)) <= 15:
                    counts[value] += 1
        basis = 'SVG明确标注的中性填充色；未按绘制面积加权'
    else:
        with Image.open(io.BytesIO(raw)) as image:
            rgba = image.convert('RGBA')
            rgba.thumbnail((256, 256))
            for r, g, b, alpha in rgba.getdata():
                if alpha >= 240 and max(r, g, b) < 230 and max(r, g, b) - min(r, g, b) <= 15:
                    counts['#%02X%02X%02X' % (r, g, b)] += 1
        basis = '已读位图中非白且不透明的中性像素高频色；不由反白图推造彩色标准'
    if not counts:
        return None
    return counts.most_common(1)[0][0], basis


def main():
    changes = []; cache_gaps = 0
    for path in sorted((ROOT / 'universities').glob('*/*/profile.yaml')):
        p = load_yaml(path.read_text(encoding='utf-8'))
        if p['visual']['color_primary']['availability'] != 'unresearched':
            continue
        assets = [a for a in p['visual']['logo_assets'] if a.get('access_status') == 'content_inspected' and a.get('sha256')]
        assets.sort(key=lambda a: (not a['official'], a['kind'] != 'badge'))
        for asset in assets:
            raw = cached_bytes(asset)
            if raw is None:
                cache_gaps += 1; continue
            result = neutral_color(raw, asset)
            if not result:
                continue
            value, notation = result
            basis = '原标识为单色/灰度；' + notation + '。仅作为PPT中性设计建议色，不是学校官方VI标准色。'
            method = 'manual_derived' if asset['kind'] == 'site_identity' else 'badge_sample'
            meta = dict(source=asset['url'], source_type='official_website' if asset['official'] else 'community_website',
                        verified='auto', checked_at=dt.date.today().isoformat(), method=method,
                        asset_id=asset['asset_id'], source_sha256=asset['sha256'], collector='ppt_core_neutral_sample')
            if put_fact(p, 'visual.color_primary', value, meta, basis=basis):
                upsert(p['visual']['color_palette'], dict(value=value, rgb=rgb(value), cmyk=None, pantone=None,
                    label='PPT中性参考色', role='reference', official=False, availability='found', basis=basis, **meta),
                    lambda c: (c['source'], c['value'], c['method']))
                path.write_text(yaml.safe_dump(p, allow_unicode=True, sort_keys=False, width=100), encoding='utf-8')
                changes.append(dict(school_code=p['identity']['school_code'], name_zh=p['identity']['name_zh'],
                    asset_id=asset['asset_id'], value=value, source=asset['url'], source_sha256=asset['sha256'], basis=basis))
                break
    target = ROOT / 'data/review/ppt-core-neutral-decisions-2026.jsonl'
    old = {r['school_code']:r for r in map(json.loads, target.read_text().splitlines())} if target.exists() else {}
    old.update({r['school_code']:r for r in changes})
    target.write_text(''.join(json.dumps(old[c], ensure_ascii=False) + '\n' for c in sorted(old)), encoding='utf-8')
    print('Added neutral reference primaries:', len(changes), '; missing original file caches:', cache_gaps)


if __name__ == '__main__':
    main()
