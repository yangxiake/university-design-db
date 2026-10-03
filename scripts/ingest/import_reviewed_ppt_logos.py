#!/usr/bin/env python3
"""Import selected official graphics after hash-bound actual-image review."""
import datetime as dt
import hashlib
import json
import pathlib

import yaml

from expand_repository_fields import inspect_bytes
from profile_extensions import rgb, upsert
from research_all_schools import same_school
from yaml_io import load_yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]


def checked_asset(decision, receipt, parent, identity, raw):
    """Reject stale review, foreign domains and unconfirmed source pages."""
    if (decision['school_code'] != identity['school_code'] or
            decision['name_zh'] != identity['name_zh'] or
            receipt['school_code'] != identity['school_code'] or
            parent['school_code'] != identity['school_code'] or
            receipt['status'] != 'source_read' or parent['status'] != 'source_read' or
            not parent.get('identity_match') or
            decision['sha256'] != receipt['source_sha256'] or
            hashlib.sha256(raw).hexdigest() != decision['sha256'] or
            decision.get('decision') != 'accept' or decision.get('verified') != 'auto' or
            decision['kind'] not in {'badge', 'wordmark', 'combination', 'site_identity'}):
        raise ValueError('review_source_or_identity_mismatch')
    home = identity['official_website'].get('value') or receipt['home']
    if not all(same_school(url, home) for url in (receipt['resolved_url'], parent['resolved_url'])):
        raise ValueError('foreign_school_source')
    metadata = inspect_bytes(raw, receipt['resolved_url'])
    colors = metadata.pop('colors'); color_basis = metadata.pop('color_basis')
    asset_id = hashlib.sha256((identity['school_code']+'|'+receipt['resolved_url']).encode()).hexdigest()[:24]
    asset = dict(asset_id=asset_id, kind=decision['kind'], title=identity['name_zh']+'官网标识图形',
        url=receipt['resolved_url'], source=parent['resolved_url'],
        file_name=receipt['resolved_url'].split('/')[-1], upstream_path=None,
        publisher=identity['name_zh'], official=True, repository=None, commit=None,
        repository_license=None, asset_license=None, rights_holder=identity['name_zh'],
        verified='auto', checked_at=dt.date.today().isoformat(), availability='found',
        source_type='official_website', source_sha256=parent['source_sha256'],
        visual_review='auto', visual_review_basis=decision['reason'],
        identity_basis='已读取本校标识说明页、该页引用的实际文件及当前完整校名；图形另作内容检查。',
        usage_note=decision.get('usage_note','仅保存官网链接与文件元数据；图形使用仍遵循学校说明和权利，不再分发图形。'),
        **metadata)
    return asset, colors, color_basis


def main():
    decisions = load_yaml((ROOT/'data/review/ppt-core-official-logo-decisions-2026.yaml').read_text())
    receipts = {(r['school_code'], r['url']): r for r in map(json.loads,
        (ROOT/'data/review/ppt-core-logo-directory-image-sources-2026.jsonl').read_text().splitlines())}
    parents = {(r['school_code'], r['url']): r for r in map(json.loads,
        (ROOT/'data/review/ppt-core-logo-directory-sources-2026.jsonl').read_text().splitlines())}
    paths = {p.parent.name:p for p in (ROOT/'universities').glob('*/*/profile.yaml')}
    changes = []
    for d in decisions:
        if d['decision'] != 'accept':
            continue
        path=paths[d['school_code']];p=load_yaml(path.read_text())
        receipt=receipts[(d['school_code'],d['url'])];parent=parents[(d['school_code'],d['source'])]
        raw=(ROOT/'tmp/targeted-vi'/(d['sha256']+'.'+receipt['format'].lower())).read_bytes()
        asset,colors,basis=checked_asset(d,receipt,parent,p['identity'],raw)
        before=json.dumps(p['visual'],sort_keys=True)
        upsert(p['visual']['logo_assets'],asset,lambda a:a['asset_id'])
        for value in colors[:2]:
            entry=dict(value=value,rgb=rgb(value),cmyk=None,pantone=None,role='reference',
                label='官网标识PPT建议色',method='badge_sample',official=False,
                basis='从实际查看的本校标识图形取色；'+basis.replace('社区标识','官网标识')+'；不是学校官方VI标准色。',
                source=asset['url'],page_source=asset['source'],asset_id=asset['asset_id'],
                source_sha256=asset['sha256'],verified='auto',checked_at=asset['checked_at'],availability='found')
            upsert(p['visual']['color_palette'],entry,lambda c:(c['source'],c['value'],c['method']))
        if before!=json.dumps(p['visual'],sort_keys=True):
            path.write_text(yaml.safe_dump(p,allow_unicode=True,sort_keys=False,width=100))
            changes.append(dict(school_code=d['school_code'],asset_id=asset['asset_id'],sha256=asset['sha256']))
    audit=ROOT/'data/review/ppt-core-official-logo-changes-2026.jsonl'
    old=[json.loads(s) for s in audit.read_text().splitlines()] if audit.exists() else []
    audit.write_text(''.join(json.dumps(c,ensure_ascii=False)+'\n' for c in old+changes))
    print('Reviewed official graphics added:',len(changes))


if __name__=='__main__':
    main()
