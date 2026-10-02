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

ROOT = pathlib.Path(__file__).resolve().parents[2]


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
    else:
        raise ValueError('A resource decision needs a read page or file receipt')
    return entry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--decisions', required=True)
    parser.add_argument('--receipts', required=True)
    args = parser.parse_args()
    decisions = yaml.safe_load((ROOT / args.decisions).read_text())
    receipts = {(r['school_code'], r['url']): r for r in map(json.loads, (ROOT / args.receipts).read_text().splitlines())}
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
        for spec in decision.get('wordmarks', []):
            receipt = receipts[(decision['school_code'], spec['url'])]
            if receipt['status'] != 'source_read' or receipt.get('format') not in {'JPEG', 'PNG'}:
                raise ValueError('Wordmark image not read')
            raw = ROOT / 'tmp/targeted-vi' / (receipt['source_sha256'] + '.' + receipt['format'].lower())
            body = raw.read_bytes()
            if hashlib.sha256(body).hexdigest() != receipt['source_sha256']:
                raise ValueError('Wordmark source hash mismatch')
            asset = dict(asset_id=hashlib.sha256((decision['school_code'] + '|' + spec['url']).encode()).hexdigest()[:24],
                         kind='wordmark', title=spec['title'], url=spec['url'], source=spec['source'],
                         file_name=spec['url'].rsplit('/', 1)[-1], publisher=decision['name_zh'], official=True,
                         repository=None, commit=None, repository_license=None, asset_license=None,
                         rights_holder=decision['name_zh'], availability='found', verified='auto',
                         checked_at=receipt['checked_at'], usage_note=spec['usage_note'],
                         source_type='official_website', identity_basis=dict(basis=spec['basis']), **inspect_bytes(body, spec['url']))
            # A published display sheet is not a sampled school colour standard.
            asset.pop('colors', None)
            apply_record(profile, dict(school_code=decision['school_code'], checked_at=receipt['checked_at'],
                                       claims=[], assets=[asset]))
        if json.dumps(profile, sort_keys=True) != before:
            path.write_text(yaml.safe_dump(profile, allow_unicode=True, sort_keys=False, width=100))
            changed += 1
    print('Resource decisions:', len(decisions), '; profiles changed:', changed)


if __name__ == '__main__':
    main()
