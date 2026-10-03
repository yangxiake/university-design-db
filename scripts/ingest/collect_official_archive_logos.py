#!/usr/bin/env python3
"""Inspect official archive graphics and replay explicit identity decisions.

Read members as bounded byte streams; never extract their names to disk. A
successful image parser is insufficient for importing a school logo.
"""
import argparse
import datetime as dt
import hashlib
import json
import pathlib
import yaml

from expand_repository_fields import inspect_bytes
from inspect_template_files import bounded_zip
from profile_extensions import upsert
from research_all_schools import same_school

ROOT = pathlib.Path(__file__).resolve().parents[2]


def display_name(info):
    if info.flag_bits & 0x800:
        return info.filename
    for encoding in ('utf-8', 'gbk'):
        try:
            return info.filename.encode('cp437').decode(encoding)
        except UnicodeError:
            pass
    return info.filename


def inspect_members(receipt, body):
    metadata = receipt['file_metadata']
    if hashlib.sha256(body).hexdigest() != metadata['sha256']:
        raise ValueError('archive_content_hash_mismatch')
    rows = []
    with bounded_zip(body) as archive:
        for member in archive.infolist():
            name = member.filename
            if (member.is_dir() or name.startswith('__MACOSX/') or
                    '..' in pathlib.PurePosixPath(name.replace('\\', '/')).parts or
                    pathlib.PurePosixPath(name).is_absolute() or
                    pathlib.PurePosixPath(name).suffix.lower() not in {'.png', '.jpg', '.jpeg', '.svg'}):
                continue
            row = dict(school_code=receipt['school_code'], name_zh=receipt['name_zh'],
                       archive_url=receipt.get('resolved_url', receipt['url']),
                       archive_sha256=metadata['sha256'], archive_member=name,
                       archive_member_display=display_name(member), checked_at=receipt['checked_at'],
                       status='image_inspection_gap', identity_review='requires_visual_review')
            try:
                if member.file_size > 12_000_000:
                    raise ValueError('member_byte_size_limit')
                data = archive.read(member)
                row.update(inspect_bytes(data, name))
                row.pop('colors', None); row.pop('color_basis', None)
                row['status'] = 'image_content_read'
                cache = ROOT/'tmp/official-archive-logos'
                cache.mkdir(parents=True, exist_ok=True)
                (cache/(row['sha256']+'.'+row['format'])).write_bytes(data)
            except Exception as exc:
                row.update(detail=str(exc)[:160], error_type=type(exc).__name__)
            rows.append(row)
    return rows


def reviewed_entry(row, decision, identity):
    if (row['status'] != 'image_content_read' or decision['name_zh'] != identity['name_zh'] or
            row['name_zh'] != identity['name_zh'] or decision['kind'] not in {'badge', 'wordmark', 'combination'} or
            not decision.get('basis') or not identity['official_website'].get('value') or
            not same_school(row['archive_url'], identity['official_website']['value'])):
        raise ValueError('archive_graphic_identity_not_confirmed')
    name = identity['name_zh']
    entry = dict(row)
    for key in ('status', 'identity_review', 'school_code', 'name_zh'):
        entry.pop(key, None)
    entry.update(asset_id=hashlib.sha256((identity['school_code']+'|'+row['archive_sha256']+'|'+row['archive_member']).encode()).hexdigest()[:24],
                 kind=decision['kind'], title=name+'官方附件内标识：'+row['archive_member_display'].rsplit('/',1)[-1],
                 url=row['archive_url'], source=row['archive_url'], publisher=name, official=True,
                 download_kind='archive_member', file_name=row['archive_member_display'].rsplit('/',1)[-1],
                 repository=None, commit=None, repository_license=None, asset_license=None, rights_holder=name,
                 availability='found', verified='auto', source_type='official_website',
                 identity_basis=dict(basis=decision['basis']),
                 usage_note='AI读取并核对该成员图形身份；需下载上游压缩包后按archive_member获取。archive_member是ZIP解析器保留的成员名，archive_member_display供阅读；文件哈希用于核对。只发布链接与元数据，图形授权按学校规则。')
    return entry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipts', action='append', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--decisions')
    parser.add_argument('--import-only', action='store_true')
    args = parser.parse_args()
    output = ROOT/args.output
    if args.import_only:
        rows = [json.loads(l) for l in output.read_text().splitlines()]
    else:
        receipts = {(r['school_code'], (r.get('file_metadata') or {}).get('sha256')):r
                    for file in args.receipts for r in map(json.loads, (ROOT/file).read_text().splitlines())
                    if r.get('status')=='content_inspected' and (r.get('file_metadata') or {}).get('format')=='ZIP'}
        rows = []
        for r in receipts.values():
            rows.extend(inspect_members(r, (ROOT/'tmp/template-files'/(r['file_metadata']['sha256']+'.bin')).read_bytes()))
        output.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
        print('Archive graphics inspected:',len(rows),'read:',sum(r['status']=='image_content_read' for r in rows))
    if not args.decisions:
        return
    paths = {p.parent.name:p for p in (ROOT/'universities').glob('*/*/profile.yaml')}
    bykey = {(r['school_code'],r['archive_sha256'],r['archive_member']):r for r in rows}
    changed = set()
    for d in map(json.loads,(ROOT/args.decisions).read_text().splitlines()):
        if d.get('decision')!='accept':
            continue
        r = bykey[(d['school_code'],d['archive_sha256'],d['archive_member'])]
        path = paths[d['school_code']];p = yaml.safe_load(path.read_text())
        entry = reviewed_entry(r,d,p['identity'])
        before = json.dumps(p,sort_keys=True)
        upsert(p['visual']['logo_assets'],entry,lambda a:a['asset_id'])
        if before != json.dumps(p,sort_keys=True):
            path.write_text(yaml.safe_dump(p,allow_unicode=True,sort_keys=False,width=100),encoding='utf-8');changed.add(d['school_code'])
    print('Archive graphic profiles changed:',len(changed))


if __name__=='__main__':
    main()
