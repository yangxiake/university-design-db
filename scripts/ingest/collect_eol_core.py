#!/usr/bin/env python3
"""Read missing PPT facts from the public Education Online school cache.

The cache's current full Chinese school name must match the MOE scope. Only
core scalar facts, website leads and actual image metadata are retained.
Graphics additionally require a hash-bound visual decision before import.
"""
import argparse
import collections
import concurrent.futures
import csv
import datetime as dt
import hashlib
import json
import pathlib
import re
from html import unescape

import yaml
from collect_english_names import title_name
from collect_official_extensions import fetch
from expand_repository_fields import inspect_bytes
from profile_extensions import put_fact, rgb, upsert
from research_all_schools import Policy
from yaml_io import load_yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
BASE = 'https://static-data.gaokao.cn'
DIRECTORY = BASE + '/www/2.0/school/name.json'
CACHE = ROOT / 'tmp/ppt-core-eol'


def norm(s):
    return re.sub(r'\s+', '', s).replace('（', '(').replace('）', ')')


def claims_for(name, data, missing):
    out = []
    if 'culture.founded_year' in missing and re.fullmatch(r'(?:1\d{3}|20\d{2})', str(data.get('create_date', ''))):
        year = int(data['create_date'])
        if year <= dt.date.today().year:
            out.append(dict(field='culture.founded_year', value=year,
                basis='教育在线同校资料缓存create_date原值；平台整理记录，未独立确认前身、现名设立或升本口径。'))
    if 'identity.name_en' in missing:
        content = unescape(re.sub(r'<[^>]+>', '', data.get('content') or ''))
        patterns = [re.escape(name) + r'\s*[（(]\s*([A-Za-z][A-Za-z ,&.\-]{5,130})\s*[）)]',
                    r'英文(?:名|名称|校名|译名)(?:为|是)?\s*[:：]?\s*[“"\']?([A-Za-z][A-Za-z ,&.\-]{5,130})']
        for pattern in patterns:
            for match in re.finditer(pattern, content[:3000]):
                value = title_name(match[1].strip())
                if value:
                    out.append(dict(field='identity.name_en', value=value, evidence=match[0][:200],
                        basis='教育在线同校简介明确英文名标注或当前完整中文名紧邻的英文括注；平台二手记录，非校方命名证明。'))
    return list({(c['field'], str(c['value'])): c for c in out}.values())


def collect(job, policy, previous=None):
    code, name, school_id, missing, need_image = job
    source = BASE + '/www/2.0/school/' + school_id + '/info.json'
    r = dict(school_code=code, name_zh=name, platform_school_id=school_id, source=source,
        checked_at=dt.date.today().isoformat(), status='access_or_identity_gap', claims=[], assets=[], attempts=[])
    try:
        variants = [source, source.replace('https://', 'http://', 1),
                    source.replace('static-data.gaokao.cn', 'static-data.eol.cn')]
        payload = None
        if previous and previous.get('status')=='current_school_core_read' and previous.get('source_sha256'):
            cache=CACHE/(previous['source_sha256']+'.json')
            if cache.exists():
                body=cache.read_bytes()
                if hashlib.sha256(body).hexdigest()!=previous['source_sha256']:raise ValueError('school_cache_hash_mismatch')
                payload=json.loads(body)['data'];final=previous['source']
                r['attempts'].append(dict(url=final,status='school_cache_read',retrieval='hash_matched_previous_read',retrieved_at=previous['checked_at']))
        for candidate in variants if payload is None else []:
            attempt = dict(url=candidate); r['attempts'].append(attempt)
            try:
                final, body, _, _ = fetch(candidate, candidate, policy, 5_000_000, timeout=12)
                payload = json.loads(body)['data']; attempt.update(status='school_cache_read', source=final)
                break
            except Exception as exc:
                attempt.update(status='access_gap', detail=str(exc)[:140])
                if str(exc) in {'robots_disallowed', 'redirect_robots_disallowed'}: break
        if payload is None: raise ValueError('school_cache_variants_unavailable')
        data = payload
        if norm(data.get('name', '')) != norm(name) or str(data.get('school_id')) != school_id:
            raise ValueError('current_name_or_platform_id_mismatch')
        sha = hashlib.sha256(body).hexdigest(); CACHE.mkdir(parents=True, exist_ok=True)
        (CACHE / (sha + '.json')).write_bytes(body)
        r.update(status='current_school_core_read', source=final, source_sha256=sha,
            claims=claims_for(name, data, missing), website_candidate=data.get('school_site') or None)
        if need_image and str(data.get('is_logo')) == '1':
            # Public cache convention; identity is checked in the actual graphic
            # before this candidate can be imported, never inferred from the ID.
            url = BASE + '/upload/logo/' + school_id + '.jpg'
            try:
                response=None
                for graphic_url in [url,url.replace('https://','http://',1),url.replace('static-data.gaokao.cn','static-data.eol.cn')]:
                    attempt=dict(url=graphic_url);r['attempts'].append(attempt)
                    try:
                        response=fetch(graphic_url,graphic_url,policy,5_000_000,timeout=10);break
                    except Exception as exc:
                        attempt.update(status='access_or_inspection_gap',detail=str(exc)[:150])
                        if str(exc) in {'robots_disallowed','redirect_robots_disallowed'}:break
                if response is None:raise ValueError('logo_public_variants_unavailable')
                target, raw, _, _ = response
                meta = inspect_bytes(raw, url); colors = meta.pop('colors'); basis = meta.pop('color_basis', '')
                if not meta.get('width') or not meta.get('height') or min(meta['width'], meta['height']) < 60:
                    raise ValueError('preview_dimensions_too_small')
                (CACHE / (meta['sha256'] + '.graphic')).write_bytes(raw)
                asset = dict(asset_id=hashlib.sha256((code+'|'+url).encode()).hexdigest()[:24],
                    title=name+'教育在线标识预览', kind='badge', url=target, source=final,
                    file_name=school_id+'.jpg', upstream_path=None, publisher='教育在线 gaokao.cn', official=False,
                    repository=None, commit=None, repository_license=None, asset_license=None,
                    rights_holder=name, verified='auto', checked_at=r['checked_at'], availability='found',
                    source_type='community_website', source_sha256=sha,
                    identity_basis='学校目录与详情的当前完整中文名、平台ID一致；图形另外逐图核对校名，不凭ID认定归属。',
                    usage_note='教育在线学校资料缓存链接；不认定校方现行VI或图形授权，仅保存实际文件元数据，不再分发图形。',
                    colors=colors, color_basis=basis, **meta)
                r['assets'].append(asset); attempt.update(status='content_inspected', sha256=meta['sha256'])
            except Exception as exc:
                attempt.update(status='access_or_inspection_gap', detail=str(exc)[:150])
    except Exception as exc:
        r.update(detail=str(exc)[:150], error_type=type(exc).__name__)
    return r


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collect-only', action='store_true'); parser.add_argument('--import-only', action='store_true')
    parser.add_argument('--workers', type=int, default=4); parser.add_argument('--retry-errors', action='store_true')
    parser.add_argument('--retry-image-gaps',action='store_true');args=parser.parse_args()
    paths={p.parent.name:p for p in (ROOT/'universities').glob('*/*/profile.yaml')}
    profiles={c:load_yaml(p.read_text()) for c,p in paths.items()}
    names={norm(p['identity']['name_zh']):c for c,p in profiles.items()}
    out=ROOT/'data/review/ppt-core-eol-2026.jsonl'
    records={r['school_code']:r for r in map(json.loads,out.read_text().splitlines())} if out.exists() else {}
    def save():
        pending=out.with_suffix('.pending'); pending.write_text(''.join(json.dumps(records[c],ensure_ascii=False)+'\n' for c in sorted(records)));pending.replace(out)
    if not args.import_only:
        policy=Policy(); policy.allowed(BASE+'/')
        final, raw, _, _=fetch(DIRECTORY,BASE,policy,8_000_000,timeout=15)
        sha=hashlib.sha256(raw).hexdigest();CACHE.mkdir(parents=True,exist_ok=True);(CACHE/(sha+'.json')).write_bytes(raw)
        leads={}
        for row in json.loads(raw)['data']:
            code=names.get(norm(row['name']))
            if code: leads.setdefault(code,[]).append(str(row['school_id']))
        (ROOT/'data/review/ppt-core-eol-directory-2026.json').write_text(json.dumps(dict(source=final,
            source_sha256=sha,checked_at=dt.date.today().isoformat(),exact_name_matches={c:ids[0] for c,ids in leads.items() if len(set(ids))==1}),ensure_ascii=False,indent=2)+'\n')
        jobs=[]
        for code, ids in leads.items():
            if len(set(ids))!=1:continue
            previous=records.get(code)
            retry_image=bool(args.retry_image_gaps and previous and not previous['assets'] and
                any(a.get('status')=='access_or_inspection_gap' for a in previous['attempts']))
            if previous and not (args.retry_errors and previous['status']=='access_or_identity_gap') and not retry_image:continue
            p=profiles[code];missing=[f for f in ('identity.name_en','culture.founded_year') if p[f.split('.')[0]][f.split('.')[1]]['availability']=='unresearched']
            need_image=not any(a.get('access_status')=='content_inspected' for a in p['visual']['logo_assets']) or p['visual']['color_primary']['availability']=='unresearched'
            if missing or need_image:jobs.append((code,p['identity']['name_zh'],ids[0],missing,need_image))
        print('Education Online core schools queued:',len(jobs),flush=True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures=[pool.submit(collect,j,policy,records.get(j[0]) if args.retry_image_gaps else None) for j in jobs]
            for n,f in enumerate(concurrent.futures.as_completed(futures),1):
                r=f.result(); previous=records.get(r['school_code'])
                if previous: r['previous_attempts'] = previous.get('previous_attempts', []) + [{k:v for k,v in previous.items() if k!='previous_attempts'}]
                records[r['school_code']]=r
                if n%25==0:
                    save();print('Read',n,'/',len(jobs),'; core candidates',sum(len(r['claims']) for r in records.values()),'; images',sum(len(r['assets']) for r in records.values()),flush=True)
        save()
    if args.collect_only:return
    review_path=ROOT/'data/review/ppt-core-eol-visual-decisions-2026.yaml'
    reviews={d['asset_id']:d for d in load_yaml(review_path.read_text()).get('decisions',[])} if review_path.exists() else {}
    owners=collections.defaultdict(set)
    for code,r in records.items():
        for a in r['assets']:owners[a['sha256']].add(code)
    changed=0;home_leads=[]
    for code,r in records.items():
        p=load_yaml(paths[code].read_text());touched=False;by_field=collections.defaultdict(list)
        for c in r['claims']:by_field[c['field']].append(c)
        for field,claims in by_field.items():
            g,k=field.split('.')
            if p[g][k]['availability']!='unresearched' or len({str(c['value']) for c in claims})!=1:continue
            c=claims[0];touched=put_fact(p,field,c['value'],dict(source=r['source'],source_sha256=r['source_sha256'],
                source_type='community_website',verified='auto',checked_at=r['checked_at'],collector='eol_core'),basis=c['basis']) or touched
        for a in r['assets']:
            d=reviews.get(a['asset_id'],{})
            if len(owners[a['sha256']])>1 or d.get('sha256')!=a['sha256'] or d.get('school_code')!=code or d.get('decision')!='accept':continue
            entry={k:v for k,v in a.items() if k not in {'colors','color_basis'}}
            entry.update(kind=d.get('kind',a['kind']),visual_review='auto',visual_review_basis=d['reason'])
            before=json.dumps(p['visual'],sort_keys=True);upsert(p['visual']['logo_assets'],entry,lambda x:x['asset_id'])
            for value in a['colors'][:2]:
                upsert(p['visual']['color_palette'],dict(value=value,rgb=rgb(value),cmyk=None,pantone=None,
                    label='平台标识取色参考',role='reference',method='community_logo_sample',official=False,
                    source=a['url'],page_source=a['source'],asset_id=a['asset_id'],source_sha256=a['sha256'],
                    verified='auto',checked_at=r['checked_at'],availability='found',
                    basis=a['color_basis']+'；实际读取平台标识文件所得PPT设计参考，不是学校官方VI标准。'),lambda c:(c['source'],c['value'],c['method']))
            touched=json.dumps(p['visual'],sort_keys=True)!=before or touched
        if touched:paths[code].write_text(yaml.safe_dump(p,allow_unicode=True,sort_keys=False,width=100));changed+=1
        if r.get('website_candidate') and not p['identity']['official_website'].get('value'):
            home_leads.append(dict(school_code=code,name_zh=r['name_zh'],url=r['website_candidate'],discovery_source=r['source']))
    with (ROOT/'data/review/ppt-core-eol-home-leads-2026.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['school_code','name_zh','url','discovery_source']);w.writeheader();w.writerows(home_leads)
    print('Education Online core profiles changed:',changed,'; homepage leads:',len(home_leads))


if __name__=='__main__':main()
