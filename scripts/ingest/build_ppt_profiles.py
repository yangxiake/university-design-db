#!/usr/bin/env python3
"""Export source-preserving PPT records from canonical profiles; never fetch files."""
import argparse
import copy
import csv
import io
import json
import pathlib
import re

from build_ppt_indexes import logo_score, rows_for
from yaml_io import load_yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
EXPORT_VERSION = 1
LOGO_FIELDS = (
    'asset_id', 'kind', 'title', 'url', 'source', 'checked_at', 'verified', 'availability',
    'official', 'publisher', 'variant', 'file_name', 'format', 'width', 'height',
    'intrinsic_width', 'intrinsic_height', 'dimensions_in_filename', 'vector',
    'representation', 'transparent_background', 'has_alpha', 'access_status',
    'sha256', 'byte_size', 'resolved_url', 'inspection_source', 'view_box',
    'download_kind', 'archive_url', 'archive_member', 'archive_member_display', 'archive_sha256',
    'repository', 'commit', 'repository_license', 'asset_license', 'rights_holder',
    'usage_note', 'source_type', 'source_as_of', 'source_sha256', 'upstream_path',
)
CSV_FIELDS = (
    'export_version', 'school_code', 'name_zh', 'province', 'city', 'scope_tags',
    'profile_path', 'website', 'website_status', 'logo_status', 'logo_asset_id',
    'logo_url', 'logo_kind', 'logo_access_status', 'logo_official', 'logo_source',
    'logo_checked_at', 'logo_verified', 'logo_reason', 'logo_download_kind',
    'logo_archive_member', 'screen_color', 'screen_color_status', 'screen_color_method',
    'screen_color_source', 'screen_color_checked_at', 'screen_color_verified',
    'logo_candidate_count', 'official_digital_color_count', 'official_print_color_count',
    'reference_color_count', 'ppt_resource_count', 'inspected_presentation_count',
    'identity_json', 'logos_json', 'colors_json', 'templates_json', 'content_json',
)


def project(entry, fields):
    return {key: copy.deepcopy(entry[key]) for key in fields if key in entry}


def logos_for(visual):
    candidates = [project(asset, LOGO_FIELDS) for asset in visual['logo_assets']]
    for asset in candidates:
        # A filename hint is not a measured pixel color or an official VI rule.
        if re.search(r'white|反白|白色', str(asset.get('variant') or '') + ' ' +
                     str(asset.get('file_name') or ''), re.I):
            asset['preview_background_hint'] = {
                'value': 'dark', 'basis': 'variant/file_name含白色或反白标签；仅为预览提示，未验证VI背景规则。'}
    readable = [a for a in candidates if a.get('access_status') == 'content_inspected']
    selected = max(readable, key=logo_score, default=None)
    if selected:
        reasons = ['文件内容已读取']
        reasons.append('校方网页发布' if selected.get('official') else '社区来源，保留固定版本或来源日期')
        kinds = {'badge': '纯校徽', 'combination': '徽名组合', 'wordmark': '校名文字',
                 'site_identity': '官网页眉标识，具体构成待核验'}
        reasons.append(kinds.get(selected.get('kind'), '图形类型见候选记录'))
        if selected.get('vector') is True:
            reasons.append('已记录矢量表示')
        if selected.get('transparent_background') is True:
            reasons.append('已记录透明背景')
        if selected.get('download_kind') == 'archive_member':
            reasons.append('须按压缩包成员路径获取，URL为压缩包入口')
        reasons.append('排序不判断现行版本或图形授权')
        status = 'inspected_candidate'
    else:
        status = 'no_inspected_candidate' if candidates else 'no_candidate'
        reasons = ['暂无已读取文件可推荐；各候选的访问状态保持原记录。' if candidates else
                   '逐文件标识集合为空；官网和VI检索状态另见lookup_status，不能推断学校没有标识。']
    return dict(status=status, recommended_asset_id=selected['asset_id'] if selected else None,
                reason='；'.join(reasons), candidates=candidates,
                lookup_status={key: copy.deepcopy(visual[key]) for key in ('vi_url', 'badge_description')})


def colors_for(visual):
    palette = copy.deepcopy(visual['color_palette'])
    digital = [c for c in palette if c.get('method') == 'official_vi' and c.get('value') is not None]
    printing = [c for c in palette if c.get('method') == 'official_vi' and c.get('value') is None]
    reference = [c for c in palette if c.get('method') != 'official_vi']
    primary = copy.deepcopy(visual['color_primary'])
    secondary = copy.deepcopy(visual['color_secondary'])
    conflicts = [{'field': 'visual.' + key, 'fact': copy.deepcopy(visual[key])}
                 for key in ('color_primary', 'color_secondary') if visual[key]['availability'] == 'conflict']
    print_primary = [c for c in printing if c.get('role') == 'primary']
    selected = None
    if primary['availability'] == 'conflict':
        status, reason = 'conflict', '主色来源冲突；保留候选和依据，暂停自动选择。'
    elif primary['availability'] == 'found' and primary.get('method') == 'official_vi':
        selected = primary
        status, reason = 'official_vi', '已记录校方数字色；具体标准色用途以basis为准。'
    elif primary['availability'] == 'found':
        selected = primary
        status = 'design_reference'
        reason = ('采用独立来源的PPT设计参考色；官方印刷色另列，建议色不由CMYK/Pantone换算，也不是校方标准色。'
                  if print_primary else '已记录的PPT设计参考色；不是校方公布的标准色。')
    elif print_primary:
        status, reason = 'official_print_only', '官方主色仅有印刷值且无独立屏幕建议，屏幕色留空；不换算CMYK/Pantone。'
    else:
        status, reason = primary['availability'], '尚无可选择的屏幕主色；保留原调查状态与全部配色证据。'
    return dict(screen_primary=selected, screen_status=status, reason=reason,
                official_digital=digital, official_print_only=printing, references=reference,
                conflicts=conflicts, primary_fact=primary, secondary_fact=secondary)


def templates_for(profile, path):
    _, entries, files = rows_for(profile, path)
    # Match each normalized row back to its complete canonical provenance.
    originals = {(e['url'], e['source']): e for e in profile['visual']['vi_resources']}
    for entry in profile['resources'].get('community_resources', []):
        originals[(entry['url'], entry['source'])] = entry
        for file in entry.get('files', []):
            originals[(file['url'], entry['source'])] = dict(entry, **file)
    resources = []
    for entry in entries:
        # Logo/history references remain in their canonical collection, not the template export.
        if not ('template' in entry['category'] or 'visual_resource' in entry['category']):
            continue
        item = {key: copy.deepcopy(value) for key, value in entry.items()
                if key not in {'school_code', 'name_zh', 'province'}}
        item['formats'] = item['formats'].split(';')
        original = originals.get((item['url'], item['source']), profile['resources']['official_templates_url'])
        for key in ('verified', 'checked_at', 'availability', 'file_metadata', 'file_inspection', 'document_metadata',
                    'source_type', 'source_as_of', 'upstream_path', 'note'):
            if key in original:
                item[key] = copy.deepcopy(original[key])
        resources.append(item)
    presentations = []
    for file in files:
        # Scope/category remain explicit even when PPTX only contains a logo.
        item = {key: copy.deepcopy(value) for key, value in file.items()
                if key not in {'school_code', 'name_zh', 'province'}}
        for key in ('font_names', 'theme_colors'):
            item[key] = item[key].split(';') if item.get(key) else []
        original = originals.get((item['url'], item['source']), profile['resources']['official_templates_url'])
        item['format'] = 'PPTX'
        if item['archive_member']:
            item['container_sha256'] = (original.get('file_metadata') or {}).get('sha256')
        item['verified'] = original['verified']
        item['availability'] = original.get('availability', 'found')
        presentations.append(item)
    return dict(status='resources_recorded' if resources else 'no_resource_recorded',
                official_lookup=copy.deepcopy(profile['resources']['official_templates_url']),
                resources=resources, inspected_presentations=presentations)


def record_for(profile, path):
    identity = profile['identity']
    record = dict(export_version=EXPORT_VERSION, profile_schema_version=profile['schema_version'],
                  school_code=identity['school_code'], name_zh=identity['name_zh'],
                  province=identity['province'], city=identity['city'],
                  scope_tags=copy.deepcopy(profile['classification']['scope_tags']),
                  scope_category=profile['classification']['scope_category'],
                  registry_source=identity['registry_source'],
                  profile_path=path.relative_to(ROOT).as_posix())
    record['identity'] = {key: copy.deepcopy(identity[key]) for key in
                          ('name_en', 'short_name_zh', 'short_name_en', 'aliases', 'official_website')}
    record['logos'] = logos_for(profile['visual'])
    record['colors'] = colors_for(profile['visual'])
    record['templates'] = templates_for(profile, path)
    record['content'] = dict(summary_zh=copy.deepcopy(profile['overview']['summary_zh']),
                             motto=copy.deepcopy(profile['culture']['motto']),
                             founded_year=copy.deepcopy(profile['culture']['founded_year']))
    return record


def csv_row(record):
    selected = next((a for a in record['logos']['candidates']
                     if a['asset_id'] == record['logos']['recommended_asset_id']), {})
    color = record['colors']['screen_primary'] or {}
    row = {key: record[key] for key in ('export_version', 'school_code', 'name_zh', 'province', 'city', 'profile_path')}
    row.update(scope_tags='|'.join(record['scope_tags']),
               website=record['identity']['official_website']['value'],
               website_status=record['identity']['official_website']['availability'],
               logo_status=record['logos']['status'], logo_reason=record['logos']['reason'],
               screen_color=color.get('value'), screen_color_status=record['colors']['screen_status'],
               screen_color_method=color.get('method'), screen_color_source=color.get('source'),
               screen_color_checked_at=color.get('checked_at'), screen_color_verified=color.get('verified'),
               logo_candidate_count=len(record['logos']['candidates']),
               official_digital_color_count=len(record['colors']['official_digital']),
               official_print_color_count=len(record['colors']['official_print_only']),
               reference_color_count=len(record['colors']['references']),
               ppt_resource_count=len(record['templates']['resources']),
               inspected_presentation_count=len(record['templates']['inspected_presentations']))
    for key in ('asset_id', 'url', 'kind', 'access_status', 'official', 'source', 'checked_at',
                'verified', 'download_kind', 'archive_member'):
        row['logo_' + key] = selected.get(key)
    # Structured columns retain all provenance; convenience cells are not complete fact envelopes.
    for key in ('identity', 'logos', 'colors', 'templates', 'content'):
        row[key + '_json'] = json.dumps(record[key], ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return row


def serialize(records):
    jsonl = ''.join(json.dumps(r, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n' for r in records)
    buf = io.StringIO(newline='')
    writer = csv.DictWriter(buf, fieldnames=CSV_FIELDS, lineterminator='\n')
    writer.writeheader()
    writer.writerows(csv_row(r) for r in records)
    coverage = dict(export_version=EXPORT_VERSION, schools=len(records),
                    logo_candidates=sum(len(r['logos']['candidates']) for r in records),
                    schools_with_inspected_logo=sum(r['logos']['status'] == 'inspected_candidate' for r in records),
                    screen_status_counts={s: sum(r['colors']['screen_status'] == s for r in records)
                                          for s in sorted({r['colors']['screen_status'] for r in records})},
                    ppt_resources=sum(len(r['templates']['resources']) for r in records),
                    inspected_presentations=sum(len(r['templates']['inspected_presentations']) for r in records))
    return {'ppt-profiles.jsonl': jsonl, 'ppt-profiles.csv': '\ufeff' + buf.getvalue(),
            'ppt-profiles-coverage.json': json.dumps(coverage, ensure_ascii=False, indent=2, sort_keys=True) + '\n'}


def assert_scope(records, scope):
    codes = [r['school_code'] for r in records]
    if len(codes) != len(set(codes)):
        raise ValueError('PPT export school_code: duplicate identity')
    expected = {r['school_code']: r for r in scope}
    if len(expected) != len(scope) or len(scope) != 1412 or set(codes) != set(expected):
        raise ValueError('PPT export school_code: must match 1412 unique scope identities')
    for record in records:
        for key in ('name_zh', 'province', 'city'):
            if record[key] != expected[record['school_code']][key]:
                raise ValueError(record['school_code'] + ': ' + key + ' differs from MOE scope')


def check_output(path, expected):
    if not path.exists() or path.read_text(encoding='utf-8') != expected:
        raise ValueError('Stale PPT export: ' + path.name + '; run scripts/ingest/build_ppt_profiles.py')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    paths = sorted((ROOT / 'universities').glob('*/*/profile.yaml'))
    records = [record_for(load_yaml(p.read_text(encoding='utf-8')), p) for p in paths]
    with (ROOT / 'data/universities-scope-2026.csv').open(encoding='utf-8-sig', newline='') as handle:
        assert_scope(records, list(csv.DictReader(handle)))
    for name, content in serialize(records).items():
        path = ROOT / 'indexes' / name
        if args.check:
            check_output(path, content)
        else:
            path.write_text(content, encoding='utf-8')
    print(('Checked' if args.check else 'Generated') + ' PPT export v1: %d unique schools.' % len(records))


if __name__ == '__main__':
    main()
