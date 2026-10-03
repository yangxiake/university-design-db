#!/usr/bin/env python3
"""Import hash-bound, visually reviewed current marks from public secondary sources.

No fetching occurs here. A PDF mark remains a PDF page reference, never a direct
PNG or a vector asset. Every decision is checked before any profile is written.
"""
import collections
import hashlib
import html
import json
import pathlib
import urllib.parse

import yaml
from PIL import Image
from pypdf import PdfReader

from expand_repository_fields import inspect_bytes
from collect_official_extensions import decode
from profile_extensions import empty_fact, put_fact, rgb, upsert
from yaml_io import load_yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
DECISIONS = ROOT / 'data/review/other-sources-current-mark-decisions-2026.jsonl'


def cached(record):
    path = (ROOT / record['cache']).resolve()
    if ROOT / 'tmp/other-sources/cache' not in path.parents:
        raise ValueError('cache outside reviewed source folder')
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != record['sha256']:
        raise ValueError('source cache hash mismatch')
    return body


def pdf_details(body, decision):
    import io
    reader = PdfReader(io.BytesIO(body))
    page = decision['document_page']
    if type(page) is not int or not 1 <= page <= len(reader.pages):
        raise ValueError('invalid document page')
    embedded = reader.pages[page - 1].images[decision['document_image_index']]
    if hashlib.sha256(embedded.data).hexdigest() != decision['document_image_sha256']:
        raise ValueError('embedded image hash mismatch')
    image = embedded.image.convert('RGB')
    bounds = decision['document_mark_region']
    if (len(bounds) != 4 or any(type(v) is not int for v in bounds)
            or not 0 <= bounds[0] < bounds[2] <= image.width
            or not 0 <= bounds[1] < bounds[3] <= image.height):
        raise ValueError('invalid mark region')
    pixels = collections.Counter(tuple(v // 8 * 8 for v in p)
        for p in image.crop(bounds).getdata()
        if p[2] - p[0] >= 70 and p[0] < 80 and p[2] < 185)
    if not pixels:
        raise ValueError('no eligible mark pixels')
    color = '#' + ''.join('%02X' % v for v in pixels.most_common(1)[0][0])
    metadata = dict(format='pdf', representation='document_embedded_raster', vector=False,
        width=None, height=None, has_alpha=False, transparent_background=False,
        document_page=page, document_page_count=len(reader.pages),
        document_image_index=decision['document_image_index'],
        document_image_sha256=decision['document_image_sha256'],
        document_image_dimensions=[image.width, image.height], document_mark_region=bounds,
        download_kind='document_page', access_status='content_inspected',
        sha256=hashlib.sha256(body).hexdigest(), byte_size=len(body))
    return metadata, color


def checked(decision, profile):
    if (decision['school_code'] != profile['identity']['school_code']
            or decision['name_zh'] != profile['identity']['name_zh']
            or decision['decision'] != 'include_current_mark' or not decision['visual_confirmation']):
        raise ValueError('school or decision mismatch')
    receipts = [json.loads(line) for line in (ROOT / decision['asset_receipt']).read_text().splitlines()]
    record = next(r for r in receipts if r['school_code'] == decision['school_code']
                  and r.get('sha256') == decision['sha256'] and r.get('resolved_url') == decision['url'])
    body = cached(record)
    if decision.get('download_kind') == 'document_page':
        meta, color = pdf_details(body, decision)
        if decision['source'] != decision['url'] or decision['source_sha256'] != record['sha256']:
            raise ValueError('document source mismatch')
    else:
        parent = next(json.loads(line) for line in (ROOT / decision['page_receipt']).read_text().splitlines()
            if json.loads(line).get('url') == decision['source']
            and json.loads(line)['school_code'] == decision['school_code'])
        text = decode(cached(parent), None)
        if (parent['sha256'] != decision['source_sha256'] or not parent['name_in_page']
                or urllib.parse.urlparse(decision['url']).path not in html.unescape(text)):
            raise ValueError('parent page identity or image link mismatch')
        meta = inspect_bytes(body, decision['url'])
        color = decision['screen_reference']
        if decision.get('color_mode') == 'full_rgb_mode':
            image = Image.open(ROOT / record['cache']).convert('RGB')
            counts = collections.Counter(p for p in image.getdata() if max(p) - min(p) >= 30 and max(p) < 225)
            color = '#' + ''.join('%02X' % v for v in counts.most_common(1)[0][0])
        elif color not in meta['colors']:
            raise ValueError('color absent from inspected palette')
        meta = {k: v for k, v in meta.items() if k not in {'colors', 'color_basis'}}
    if color != decision['screen_reference']:
        raise ValueError('screen reference does not match reviewed pixels')
    return meta, color


def main():
    paths = {p.parent.name: p for p in (ROOT / 'universities').glob('*/*/profile.yaml')}
    pending = []
    for decision in map(json.loads, DECISIONS.read_text().splitlines()):
        path = paths[decision['school_code']]
        profile = load_yaml(path.read_text())
        meta, color = checked(decision, profile)
        pending.append((decision, path, profile, meta, color))
    for d, path, profile, meta, color in pending:
        code, name = d['school_code'], d['name_zh']
        asset_id = hashlib.sha256((code + '|' + d['url']).encode()).hexdigest()[:24]
        document = d.get('download_kind') == 'document_page'
        note = ('公开PDF第1页右上角的学校组合标识；嵌入图为位图。记录原PDF与页内位置，'
                '需从原文档提取，不是独立透明图片。' if document else
                '公开来源预览原图，已逐图确认完整现行校名；不把目录自述的官网来源或付费矢量格式当作校方发布或实测格式。')
        asset = dict(asset_id=asset_id, kind=d['kind'], title=name + ('公开PDF中的组合标识' if document else '现行标识公开预览'),
            url=d['url'], source=d['source'], source_sha256=d['source_sha256'],
            file_name=urllib.parse.unquote(urllib.parse.urlparse(d['url']).path.rsplit('/', 1)[-1]),
            publisher=d['publisher'], official=False, rights_holder=name,
            asset_license=None, repository=None, commit=None, repository_license=None,
            source_type='community_website', availability='found', verified='auto', checked_at=d['checked_at'],
            identity_basis=d['visual_confirmation'], usage_note=note + '图形权利仍归学校，仅索引，不镜像原图；屏幕取色仅作PPT参考。', **meta)
        upsert(profile['visual']['logo_assets'], asset, lambda a: a['asset_id'])
        basis = d['color_basis'] + '；从已逐图确认的现行标识取得，仅作PPT建议色，不是官方VI标准。'
        palette = dict(value=color, rgb=rgb(color), cmyk=None, pantone=None, label='现行标识屏幕取色参考',
            role='reference', method='community_logo_sample', official=False, source=d['url'],
            page_source=d['source'], source_sha256=d['sha256'], asset_id=asset_id,
            verified='auto', checked_at=d['checked_at'], availability='found', basis=basis)
        upsert(profile['visual']['color_palette'], palette, lambda a: (a['source'], a['value'], a['method']))
        current = profile['visual']['color_primary']
        if current['availability'] in {'unresearched', 'not_found'}:
            profile['visual']['color_primary'] = empty_fact()
            put_fact(profile, 'visual.color_primary', color, dict(source=d['url'], source_sha256=d['sha256'],
                source_type='community_website', checked_at=d['checked_at'], verified='auto', method='manual_derived',
                collector='other_source_current_mark', asset_id=asset_id), basis=basis)
        path.write_text(yaml.safe_dump(profile, allow_unicode=True, sort_keys=False, width=100))
    print('Imported reviewed current marks:', len(pending))


if __name__ == '__main__':
    main()
