#!/usr/bin/env python3
"""Index verified VI pages and follow their explicit school-owned links.

Only cached responses with matching receipt hashes are replayed. Dedicated
visual headings, school identity and host boundaries are required. Linked
files are indexed separately from actually read documents.
"""
import argparse
import datetime as dt
import hashlib
import json
import pathlib
import re
import urllib.parse

import yaml
from collect_official_extensions import decode
from collect_visual_directory import VisualPage, page_identity, visual_heading, resource_entry, FILE, RESOURCE, ANNIVERSARY
from import_targeted_resources import resource_from_receipt
from profile_extensions import put_fact, upsert
from research_all_schools import same_school, extract_claims

ROOT = pathlib.Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipts', required=True, action='append')
    parser.add_argument('--audit', required=True)
    parser.add_argument('--related-targets', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    paths = {p.parent.name: p for p in (ROOT/'universities').glob('*/*/profile.yaml')}
    profiles = {c: yaml.load(p.read_text(), Loader=yaml.CSafeLoader) for c, p in paths.items()}
    receipts = {(r['school_code'], r['url']): r for f in args.receipts
                for r in map(json.loads, (ROOT/f).read_text().splitlines())}
    known_urls = {key[1] for key in receipts}
    audit, related, changed = [], {}, set()
    for key, receipt in sorted(receipts.items()):
        if receipt.get('status') != 'source_read' or receipt.get('format') != 'HTML':
            continue
        code, url = key
        profile = profiles[code]
        identity = profile['identity']
        home = identity['official_website'].get('value')
        if receipt['name_zh'] != identity['name_zh']:
            raise ValueError('school_identity_mismatch')
        if not home or not same_school(url, home):
            continue
        raw = ROOT/'tmp/targeted-vi'/(receipt['source_sha256']+'.html')
        body = raw.read_bytes()
        if hashlib.sha256(body).hexdigest() != receipt['source_sha256']:
            raise ValueError('cached_source_hash_mismatch')
        page = VisualPage(); page.feed(decode(body, None)); page.finish()
        if not page_identity(identity['name_zh'], page):
            audit.append(dict(school_code=code, url=url, status='school_identity_gap'))
            continue
        source = receipt['resolved_url']
        text = '\n'.join(t for _, t in page.lines)
        kind = 'charter' if '章程' in page.title else 'visual'
        claims = extract_claims(identity['name_zh'], kind, page.title, text, source)
        fact_changes = []
        for claim in claims:
            if claim['field'] == 'visual.vi_url' and not visual_heading(page):
                continue
            group, field = claim['field'].split('.')
            if profile[group][field]['availability'] != 'unresearched':
                continue
            if put_fact(profile, claim['field'], claim['value'], dict(source=source,
                    source_type='official_website', verified='auto', checked_at=receipt['checked_at'],
                    source_sha256=receipt['source_sha256'], collector='read_official_vi_metadata'),
                    basis=claim.get('basis', '官网学校文化/标识页明确记载的本校事实')):
                fact_changes.append(claim)
                changed.add(code)
        if not visual_heading(page):
            audit.append(dict(school_code=code, url=url, status='no_dedicated_visual_heading', facts=fact_changes))
            continue
        title = next((h for h in page.headings if RESOURCE.search(h)), page.title.strip())
        special = bool(ANNIVERSARY.search(title))
        specifications = [resource_entry(title, source, source, receipt['source_sha256'], special)]
        for link in page.links:
            label = re.sub(r'\s+', ' ', link['label']).strip()
            target = urllib.parse.urljoin(source, link['href']).split('#')[0]
            if link['footer'] or not same_school(target, home):
                continue
            suffix = FILE.search(target) or FILE.search(label)
            if suffix and label and (RESOURCE.search(label) or re.search(r'附件|下载|手册|标志|LOGO|基础', label, re.I)):
                specifications.append(resource_entry(label, target, source, receipt['source_sha256'],
                    special or bool(ANNIVERSARY.search(label)), suffix[1].upper()))
            if target not in known_urls and (RESOURCE.search(label) or re.search(r'色彩规范|标准配色|色彩系统', label)):
                if re.search(r'javascript:|mailto:|tel:', target, re.I) or ANNIVERSARY.search(label):
                    continue
                if suffix and suffix[1].lower() not in {'pdf', 'ai', 'pptx', 'zip'}:
                    continue
                item = dict(school_code=code, name_zh=identity['name_zh'], home=home, url=target,
                            purpose='已读取学校视觉规范页明确链接：'+label[:120])
                if suffix and suffix[1].lower() in {'pptx', 'zip'}:
                    item['format'] = suffix[1].upper(); item['source'] = source
                related.setdefault((code, target), item)
        additions = 0
        for spec in specifications:
            spec['receipt_url'] = url
            entry = resource_from_receipt(spec, receipt)
            before = json.dumps(profile['visual']['vi_resources'], sort_keys=True)
            upsert(profile['visual']['vi_resources'], entry, lambda x: (x['url'], x['source']))
            if before != json.dumps(profile['visual']['vi_resources'], sort_keys=True):
                additions += 1; changed.add(code)
        audit.append(dict(school_code=code, name_zh=identity['name_zh'], url=url,
                          source_sha256=receipt['source_sha256'], status='visual_page_indexed',
                          resources=len(specifications), changes=additions, facts=fact_changes))
    if args.apply:
        for code in changed:
            paths[code].write_text(yaml.safe_dump(profiles[code], allow_unicode=True, sort_keys=False, width=100), encoding='utf-8')
    (ROOT/args.audit).write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in audit), encoding='utf-8')
    (ROOT/args.related_targets).write_text(yaml.safe_dump(list(related.values()), allow_unicode=True, sort_keys=False, width=100), encoding='utf-8')
    print('Read pages:', len(audit), '; changed profiles:', len(changed), '; additional links:', len(related))


if __name__ == '__main__':
    main()
