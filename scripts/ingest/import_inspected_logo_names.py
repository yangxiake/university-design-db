#!/usr/bin/env python3
"""Import English inscriptions reviewed on a school's actual logo bytes.

The selected text is a review decision, not generated translation. Every
decision must match the canonical school, inspected asset and SHA256.
"""
import datetime as dt
import json
import pathlib

import yaml
from collect_english_names import field_name
from profile_extensions import put_fact
from yaml_io import load_yaml

ROOT=pathlib.Path(__file__).resolve().parents[2]


def eligible(profile, decision):
    if profile['identity']['name_zh']!=decision['name_zh']:
        return None
    if field_name(decision['value'])!=decision['value']:
        return None
    return next((a for a in profile['visual']['logo_assets']
        if a['asset_id']==decision['asset_id'] and a.get('sha256')==decision['sha256']
        and a.get('access_status')=='content_inspected' and a.get('visual_review')=='auto'),None)


def main():
    decisions=load_yaml((ROOT/'data/review/ppt-core-logo-name-decisions-2026.yaml').read_text())
    paths={p.parent.name:p for p in (ROOT/'universities').glob('*/*/profile.yaml')}
    changes=[]
    for d in decisions:
        p=load_yaml(paths[d['school_code']].read_text());a=eligible(p,d)
        if a is None:raise ValueError('English inscription decision identity/hash mismatch')
        if p['identity']['name_en']['availability']!='unresearched':continue
        basis='实际查看图形所印完整英文名，保留图中拼写；'+d['basis']
        meta=dict(source=a['url'],page_source=a['source'],asset_id=a['asset_id'],source_sha256=a['sha256'],
            source_type='official_website' if a['official'] else 'community_website',verified='auto',
            checked_at=d['checked_at'],collector='inspected_logo_english_inscription',evidence=d['value'])
        if put_fact(p,'identity.name_en',d['value'],meta,basis=basis):
            paths[d['school_code']].write_text(yaml.safe_dump(p,allow_unicode=True,sort_keys=False,width=100))
            changes.append(d)
    audit=ROOT/'data/review/ppt-core-logo-name-changes-2026.jsonl'
    old={r['school_code']:r for r in map(json.loads,audit.read_text().splitlines())} if audit.exists() else {}
    old.update({d['school_code']:d for d in changes})
    audit.write_text(''.join(json.dumps(old[c],ensure_ascii=False)+'\n' for c in sorted(old)))
    print('Inspected logo English names added:',len(changes))


if __name__=='__main__':main()
