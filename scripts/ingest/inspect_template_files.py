#!/usr/bin/env python3
"""Read public presentation containers as data; retain metadata, never execute.

Canonical sources remain the authority for school identity and usage scope.
PPTX XML is bounded and entities are rejected. Archives are never extracted.
"""
import argparse
import concurrent.futures
import datetime as dt
import fractions
import hashlib
import io
import json
import pathlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

import yaml
from discover_official_pages import AGENT, safe_url
from research_all_schools import Policy, same_school
from collect_official_extensions import decode
from collect_visual_directory import VisualPage, page_identity

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUTPUT = ROOT / 'data/review/template-file-inspections-2026.jsonl'
TODAY = dt.date.today().isoformat()
MAX_FILE = 128 * 1024 * 1024
MAX_EXPANDED = 384 * 1024 * 1024
MAX_XML = 5 * 1024 * 1024
NS = {'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
      'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}


def xml_read(archive, name):
    info = archive.getinfo(name)
    if info.file_size > MAX_XML:
        raise ValueError('xml_size_limit')
    data = archive.read(info)
    if re.search(br'<!\s*(?:DOCTYPE|ENTITY)\b', data.replace(b'\x00', b''), re.I):
        raise ValueError('xml_entity_declaration')
    return ET.fromstring(data)


def bounded_zip(body):
    archive = zipfile.ZipFile(io.BytesIO(body))
    infos = archive.infolist()
    if len(infos) > 4000 or sum(i.file_size for i in infos) > MAX_EXPANDED:
        archive.close()
        raise ValueError('archive_expansion_limit')
    names = [i.filename for i in infos]
    if len(names) != len(set(names)):
        archive.close()
        raise ValueError('duplicate_archive_members')
    if any(i.flag_bits & 1 for i in infos):
        archive.close()
        raise ValueError('encrypted_archive')
    # UTF-8 member names are metadata only; nothing is written to their paths.
    return archive


def pptx_metadata(archive):
    names = archive.namelist()
    root = xml_read(archive, 'ppt/presentation.xml')
    size = root.find('p:sldSz', NS)
    if size is None:
        raise ValueError('presentation_size_missing')
    width, height = int(size.attrib['cx']), int(size.attrib['cy'])
    if width <= 0 or height <= 0:
        raise ValueError('invalid_slide_size')
    slides = sorted(n for n in names if re.fullmatch(r'ppt/slides/slide\d+\.xml', n))
    declared = root.find('p:sldIdLst', NS)
    if declared is None or len(declared) != len(slides):
        raise ValueError('slide_count_disagreement')
    fonts, theme_colors, runs, textless, external = set(), set(), 0, 0, 0
    for name in names:
        if not re.fullmatch(r'ppt/(?:slides|slideMasters|slideLayouts|theme)/[^/]+\.xml', name):
            continue
        tree = xml_read(archive, name)
        for node in tree.iter():
            font = node.attrib.get('typeface')
            if font and not font.startswith('+'):
                fonts.add(font)
        if name.startswith('ppt/theme/'):
            for color in tree.findall('.//a:clrScheme//a:srgbClr', NS):
                value = color.attrib.get('val', '')
                if re.fullmatch('[0-9a-fA-F]{6}', value):
                    theme_colors.add('#' + value.upper())
        if name in slides:
            count = sum(bool((n.text or '').strip()) for n in tree.findall('.//a:t', NS))
            runs += count
            textless += count == 0
    for name in names:
        if name.endswith('.rels'):
            external += sum(n.attrib.get('TargetMode') == 'External' for n in xml_read(archive, name))
    ratio = fractions.Fraction(width, height)
    return dict(format='PPTX', read_kind='ooxml_structure', slide_count=len(slides),
                width_emu=width, height_emu=height, aspect_ratio='%d:%d' % (ratio.numerator, ratio.denominator),
                font_names=sorted(fonts), theme_colors=sorted(theme_colors),
                editable_text_runs=runs, textless_slides=textless,
                media_count=sum(n.startswith('ppt/media/') and not n.endswith('/') for n in names),
                external_relationship_count=external,
                macro_enabled=any(n.lower().endswith('vbaproject.bin') for n in names))


def inspect_bytes(body):
    base = dict(sha256=hashlib.sha256(body).hexdigest(), byte_size=len(body))
    if body.startswith(b'PK\x03\x04'):
        with bounded_zip(body) as archive:
            if 'ppt/presentation.xml' in archive.namelist():
                return dict(base, **pptx_metadata(archive))
            members = []
            for info in archive.infolist():
                if not info.filename.lower().endswith(('.pptx', '.potx')):
                    continue
                if info.file_size > MAX_FILE:
                    members.append(dict(path=info.filename, status='file_size_limit'))
                    continue
                data = archive.read(info)
                try:
                    with bounded_zip(data) as inner:
                        meta = dict(sha256=hashlib.sha256(data).hexdigest(), byte_size=len(data), **pptx_metadata(inner))
                    members.append(dict(path=info.filename, status='content_inspected', **meta))
                except (ValueError, zipfile.BadZipFile, KeyError, ET.ParseError) as exc:
                    members.append(dict(path=info.filename, status='inspection_failed', detail=str(exc)[:120]))
            return dict(base, format='ZIP', read_kind='archive_structure',
                        member_count=len(archive.infolist()), presentation_members=members)
    if body.startswith(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'):
        return dict(base, format='OLE', read_kind='format_header_only')
    if body.startswith(b'Rar!\x1a\x07'):
        return dict(base, format='RAR', read_kind='format_header_only')
    if body.startswith(b'7z\xbc\xaf\x27\x1c'):
        return dict(base, format='7Z', read_kind='format_header_only')
    raise ValueError('not_a_supported_presentation_container')


def pinned_raw(url):
    parsed = urllib.parse.urlparse(url)
    parts = parsed.path.split('/')
    if parsed.hostname != 'github.com' or len(parts) < 6 or parts[3] != 'blob' or not re.fullmatch('[0-9a-f]{40}', parts[4]):
        raise ValueError('unfixed_community_file_url')
    return 'https://raw.githubusercontent.com/' + '/'.join(parts[1:3] + parts[4:])


def read_file(url, source, policy, community):
    if not safe_url(url) or (not community and not same_school(url, source)):
        raise ValueError('untrusted_download_origin')
    if not policy.allowed(url):
        raise ValueError('robots_disallowed')
    request = urllib.request.Request(urllib.parse.quote(url, safe=':/?&=%+#@!,$;\'()*[]'), headers={'User-Agent': AGENT, 'Referer': urllib.parse.quote(source, safe=':/?&=%+#@!,$;\'()*[]')})
    with urllib.request.urlopen(request, timeout=12) as response:
        final = response.geturl()
        if not safe_url(final) or (not community and not same_school(final, source)):
            raise ValueError('untrusted_download_redirect')
        if community and urllib.parse.urlparse(final).hostname not in {'raw.githubusercontent.com', 'github.com'}:
            raise ValueError('untrusted_community_redirect')
        if not policy.allowed(final):
            raise ValueError('redirect_robots_disallowed')
        if int(response.headers.get('Content-Length') or 0) > MAX_FILE:
            raise ValueError('download_size_limit')
        chunks, size, start = [], 0, time.monotonic()
        while True:
            chunk = response.read(65536)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_FILE:
                raise ValueError('download_size_limit')
            if time.monotonic() - start > 90:
                raise ValueError('download_time_limit')
            chunks.append(chunk)
        return final, b''.join(chunks), response.headers.get_content_charset(), response.headers.get_content_type()


def collect(target):
    receipt = dict(target, checked_at=TODAY, attempts=[], status='inspection_failed')
    url = pinned_raw(target['url']) if target['community'] else target['url']
    variants = [url]
    parsed = urllib.parse.urlparse(url)
    if not target['community']:
        variants.append(parsed._replace(scheme='http' if parsed.scheme == 'https' else 'https').geturl())
    else:
        variants.append(target['url'].replace('/blob/', '/raw/'))
    policy = Policy()
    for requested in variants:
        attempt = dict(url=requested)
        receipt['attempts'].append(attempt)
        try:
            resolved, body, charset, mime = read_file(requested, target['source'], policy, target['community'])
            try:
                meta = inspect_bytes(body)
            except ValueError as exc:
                if str(exc)!='not_a_supported_presentation_container' or mime not in {'text/html','application/xhtml+xml'} or target['community']:
                    raise
                page=VisualPage();page.feed(decode(body,charset));page.finish()
                if (not urllib.parse.urlparse(resolved).path.lower().endswith(('.htm','.html'))
                    or not (page_identity(target['name_zh'],page) or target['name_zh'] in '\n'.join(t for _,t in page.lines))
                    or re.search('404|403|验证|错误|Error|Forbidden|Not Found',page.title,re.I)):
                    raise ValueError('download_returned_html_or_verification_page')
                attempt.update(status='target_page_read',resolved_url=resolved)
                receipt.update(status='target_page_read',resolved_url=resolved,page_metadata=dict(title=page.title[:180],sha256=hashlib.sha256(body).hexdigest(),byte_size=len(body)))
                return receipt
            attempt.update(status='file_read', resolved_url=resolved)
            receipt.update(status='content_inspected' if meta['read_kind'] != 'format_header_only' else 'format_only',
                           resolved_url=resolved, file_metadata=meta)
            cache = ROOT / 'tmp/template-files' / (meta['sha256'] + '.bin')
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_bytes(body)
            return receipt
        except Exception as exc:
            attempt.update(status='access_or_parse_gap', error_type=type(exc).__name__, detail=str(exc)[:180])
            # Protocol fallback is only for request errors, never identity,
            # robots, valid HTML responses, parse or size restrictions.
            if not isinstance(exc, OSError) or str(exc) in {'robots_disallowed', 'redirect_robots_disallowed'}:
                break
    return receipt


def apply_receipt(entry, receipt):
    if entry.get('verified') == 'human':
        return
    entry['file_inspection'] = {k: receipt[k] for k in ('status', 'checked_at', 'attempts')}
    if receipt.get('resolved_url'):
        entry['file_inspection']['resolved_url'] = receipt['resolved_url']
    if receipt.get('page_metadata'):
        entry['file_inspection']['page_metadata'] = receipt['page_metadata']
    if receipt['status']=='target_page_read':
        entry.update(content_read=True,download_status='page_read',formats=['HTML'])
    if receipt['status'] in {'content_inspected', 'format_only'}:
        entry.update(file_metadata=receipt['file_metadata'], content_read=True,
                     download_status='content_inspected' if receipt['status'] == 'content_inspected' else 'downloaded_format_only')
        if 'access_requirement' in entry:
            entry['access_requirement']='公开文件在本次采集时已读取；未渲染或运行，后续可用性及使用条件以原发布页为准'
            entry['note']=entry.get('note','').replace('仅索引入口；未编译、未打开模板，不保证当前可下载或模板中字体与图形的独立授权。','已读取公开文件数据；未运行或渲染，字体与图形的独立授权以原发布页为准。')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--import-only', action='store_true')
    parser.add_argument('--retry-errors', action='store_true')
    args = parser.parse_args()
    targets, paths = {}, {}
    for path in sorted((ROOT / 'universities').glob('*/*/profile.yaml')):
        p = yaml.load(path.read_text(), Loader=yaml.CSafeLoader)
        code = p['identity']['school_code']; paths[code] = path
        for e in p['visual']['vi_resources']:
            if not e['official'] or e.get('content_read') is True or 'PPT模板' not in ' '.join(e['kinds']):
                continue
            if any('HTML' in fmt for fmt in e['formats']):
                continue
            key = (code, e['url'])
            targets[key] = dict(school_code=code, name_zh=p['identity']['name_zh'], url=e['url'], source=e['source'], community=False)
        for e in p['resources'].get('community_resources', []):
            for file in e.get('files', []):
                key = (code, file['url'])
                targets[key] = dict(school_code=code, name_zh=p['identity']['name_zh'], url=file['url'], source=e['source'], community=True)
    records = {(r['school_code'], r['url']): r for r in map(json.loads, OUTPUT.read_text().splitlines())} if OUTPUT.exists() else {}
    pending = [t for key, t in targets.items() if key not in records or (args.retry_errors and records[key]['status'] == 'inspection_failed')]
    if not args.import_only:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            for receipt in pool.map(collect, pending):
                records[(receipt['school_code'], receipt['url'])] = receipt
                temporary = OUTPUT.with_suffix('.pending')
                temporary.write_text(''.join(json.dumps(records[key], ensure_ascii=False)+'\n' for key in sorted(records)))
                temporary.replace(OUTPUT)
    changed = 0
    for code in sorted({key[0] for key in records}):
        path = paths[code]; p = yaml.safe_load(path.read_text()); before = json.dumps(p, sort_keys=True)
        for e in p['visual']['vi_resources']:
            if (code, e['url']) in records:
                apply_receipt(e, records[(code, e['url'])])
        for e in p['resources'].get('community_resources', []):
            if e.get('verified') == 'human':
                continue
            for file in e.get('files', []):
                if (code, file['url']) in records:
                    apply_receipt(file, records[(code, file['url'])])
            if any(file.get('content_read') for file in e.get('files',[])):
                e['usage_note']=e['usage_note'].replace('未读取PPTX内容','PPTX文件结构的读取结果逐文件列出，未渲染幻灯片')
        if before != json.dumps(p, sort_keys=True):
            path.write_text(yaml.safe_dump(p, allow_unicode=True, sort_keys=False, width=100)); changed += 1
    from collections import Counter
    print('Template file receipts:', dict(Counter(r['status'] for r in records.values())), '; profiles updated:', changed)


if __name__ == '__main__':
    main()
