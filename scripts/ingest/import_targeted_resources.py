#!/usr/bin/env python3
"""Replay reviewed resource decisions from a targeted official-source ledger."""
import argparse
import hashlib
import json
import pathlib
import yaml

from collect_official_extensions import apply_record
from expand_repository_fields import inspect_bytes
from inspect_template_files import apply_receipt
from profile_extensions import upsert
from research_all_schools import same_school

ROOT = pathlib.Path(__file__).resolve().parents[2]


def reviewed_asset(spec, receipt, identity):
    kind = spec.get('kind', 'wordmark')
    if kind not in {'badge', 'wordmark', 'combination', 'site_identity'}:
        raise ValueError('Unsupported reviewed school graphic kind')
    if spec.get('identity_text', identity['name_zh']) != identity['name_zh']:
        raise ValueError('Graphic still displays a different school name')
    if not same_school(spec['source'], identity['official_website']['value']):
        raise ValueError('Graphic publication source is outside the confirmed school domain')
    if receipt['status'] != 'source_read' or receipt.get('format') not in {'JPEG', 'PNG', 'SVG', 'GIF', 'WEBP'}:
        raise ValueError('School graphic image not read')
    raw = ROOT / 'tmp/targeted-vi' / (receipt['source_sha256'] + '.' + receipt['format'].lower())
    body = raw.read_bytes()
    if hashlib.sha256(body).hexdigest() != receipt['source_sha256']:
        raise ValueError('School graphic source hash mismatch')
    code, name = identity['school_code'], identity['name_zh']
    asset = dict(asset_id=hashlib.sha256((code + '|' + spec['url']).encode()).hexdigest()[:24],
                 kind=kind, title=spec['title'], url=spec['url'], source=spec['source'],
                 file_name=spec['url'].rsplit('/', 1)[-1], publisher=name, official=True,
                 repository=None, commit=None, repository_license=None, asset_license=None,
                 rights_holder=name, availability='found', verified='auto', checked_at=receipt['checked_at'],
                 usage_note=spec['usage_note'], source_type='official_website',
                 identity_basis=dict(basis=spec['basis']), **inspect_bytes(body, spec['url']))
    if spec.get('page_sha256'):
        asset['source_sha256'] = spec['page_sha256']
    if not spec.get('sample_reference_colors', False):
        asset.pop('colors', None)
    return asset


def resource_from_receipt(spec, source):
    entry = dict(spec)
    entry.pop('receipt_url')
    entry.update(official=True, verified='auto', checked_at=source['checked_at'], availability='found',
                 repository=None, commit=None)
    if source.get('source_sha256'):
        entry['source_sha256'] = source['source_sha256']
    if source['status'] in {'content_inspected', 'format_only', 'inspection_failed', 'target_page_read'}:
        apply_receipt(entry, source)
    elif source['status'] == 'source_read' and source.get('format') == 'HTML':
        if entry['url'] in {source['url'], source['resolved_url']}:
            entry.update(content_read=True, download_status='page_read')
        elif any(r['url'] == entry['url'] for r in source['links']):
            entry.update(content_read=False, download_status='indexed_not_fetched')
        else:
            raise ValueError('Attachment URL is not present in the read publication page')
    elif source['status']=='source_read' and source.get('format')=='PDF':
        if not source.get('identity_match') and not entry.pop('document_identity_reviewed', False):
            raise ValueError('PDF school identity still needs visual review')
        if entry['url'] not in {source['url'], source['resolved_url']}:
            raise ValueError('PDF URL differs from the read document')
        entry.update(content_read=True,download_status='pdf_read',
            document_metadata=dict(format='PDF',page_count=source['page_count'],sha256=source['source_sha256'],byte_size=source['byte_size']))
    else:
        raise ValueError('A resource decision needs a read page or file receipt')
    return entry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--decisions', required=True)
    parser.add_argument('--receipts', required=True, action='append')
    args = parser.parse_args()
    decisions = yaml.safe_load((ROOT / args.decisions).read_text())
    receipts = {(r['school_code'], r['url']): r for path in args.receipts for r in map(json.loads, (ROOT / path).read_text().splitlines())}
    paths = {p.parent.name: p for p in (ROOT / 'universities').glob('*/*/profile.yaml')}
    changed = 0
    for decision in decisions:
        path = paths[decision['school_code']]
        profile = yaml.safe_load(path.read_text())
        if profile['identity']['name_zh'] != decision['name_zh']:
            raise ValueError('School identity mismatch')
        before = json.dumps(profile, sort_keys=True)
        for spec in decision.get('resources', []):
            source = receipts[(decision['school_code'], spec['receipt_url'])]
            entry = resource_from_receipt(spec, source)
            upsert(profile['visual']['vi_resources'], entry, lambda x: (x['url'], x['source']))
        for spec in decision.get('wordmarks', []) + decision.get('reviewed_assets', []):
            receipt = receipts[(decision['school_code'], spec['url'])]
            asset = reviewed_asset(spec, receipt, profile['identity'])
            apply_record(profile, dict(school_code=decision['school_code'], checked_at=receipt['checked_at'],
                                       claims=[], assets=[asset]))
        if json.dumps(profile, sort_keys=True) != before:
            path.write_text(yaml.safe_dump(profile, allow_unicode=True, sort_keys=False, width=100))
            changed += 1
    print('Resource decisions:', len(decisions), '; profiles changed:', changed)


if __name__ == '__main__':
    main()
