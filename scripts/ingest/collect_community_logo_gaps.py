#!/usr/bin/env python3
"""Read source-labelled community logo pages for current visual gaps.

Exact MOE code/name matching only. Suspended and renamed logos are excluded.
No school facts, source claims of officialness, scripts or cloud files imported.
"""
import argparse
import concurrent.futures
import datetime as dt
import hashlib
import html.parser
import json
import pathlib
import re
import urllib.parse

import yaml
from collect_official_extensions import decode, fetch
from discover_official_pages import safe_url
from expand_repository_fields import inspect_bytes
from profile_extensions import rgb, upsert
from research_all_schools import Policy

ROOT=pathlib.Path(__file__).resolve().parents[2]
BASE='https://www.urongda.com'
OUTPUT=ROOT/'data/review/community-logo-gaps-2026.jsonl'
TODAY=dt.date.today().isoformat()


def normalize(text):
    return re.sub(r'\s+','',text).replace('（','(').replace('）',')')


class LogoPage(html.parser.HTMLParser):
    def __init__(self):
        super().__init__();self.hidden=0;self.heading=None;self.headings=[];self.text=[];self.images=[];self.links=[];self.anchor=None
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag in {'script','style','noscript'}:self.hidden+=1
        if self.hidden:return
        if tag=='h1':self.heading=[]
        if tag=='img':self.images.append(a)
        if tag=='a':self.anchor=dict(url=a.get('href') or '',text=[])
    def handle_endtag(self,tag):
        if tag in {'script','style','noscript'}:self.hidden=max(0,self.hidden-1)
        if self.hidden:return
        if tag=='h1' and self.heading is not None:self.headings.append(''.join(self.heading).strip());self.heading=None
        if tag=='a' and self.anchor is not None:
            self.links.append((self.anchor['url'],''.join(self.anchor['text']).strip()));self.anchor=None
    def handle_data(self,text):
        if self.hidden:return
        self.text.append(text)
        if self.heading is not None:self.heading.append(text)
        if self.anchor is not None:self.anchor['text'].append(text)


def page_candidates(page,name):
    if [normalize(n) for n in page.headings]!=[normalize(name)]:
        raise ValueError('full_school_name_mismatch')
    visible=' '.join(page.text)
    if re.search(r'校徽资源暂停|暂时关闭下载|资源维护中|新版官方校徽正在搜集|学校已由.{0,90}更名',visible):
        raise ValueError('renamed_or_suspended_logo')
    images=[]
    for image in page.images:
        if normalize(image.get('alt') or '')!=normalize(name+'校徽'):continue
        url=urllib.parse.urljoin(BASE,image.get('src') or '')
        if (urllib.parse.urlparse(url).hostname=='cdn.urongda.com' and '/images/normal/' in url
            and re.search(r'\.(png|svg)(?:[?#]|$)',url,re.I)):
            images.append(url)
    if not images:raise ValueError('no_exact_school_logo_preview')
    links=[]
    for url,title in page.links:
        if safe_url(url) and urllib.parse.urlparse(url).hostname in {'url90.ctfile.com','url05.ctfile.com'} and normalize(title).startswith(normalize(name)) and re.search(r'\.(svg|png|ai|cdr|pdf)$',title,re.I):
            links.append(dict(title=title,url=url,format=title.rsplit('.',1)[1].upper()))
    if not links:raise ValueError('no_active_logo_file_listing')
    return list(dict.fromkeys(images))[:1],links


def fetch_page(source,policy,result):
    variants=[source,source.replace('https://www.','https://'),source.replace('https://','http://')]
    for url in variants:
        attempt=dict(url=url,kind='source_page');result['attempts'].append(attempt)
        try:
            data=fetch(url,BASE,policy);attempt['status']='page_read';return data
        except Exception as exc:
            attempt.update(status='access_gap',error_type=type(exc).__name__,detail=str(exc)[:130])
            # Different ordinary public addresses only for transient network
            # failures; a nonexistent, restricted or mismatched page is final.
            import urllib.error
            if not isinstance(exc,OSError) or isinstance(exc,urllib.error.HTTPError):raise
            last=exc
    raise last


def collect(school,policy):
    code,name=school['school_code'],school['name_zh'];source=BASE+'/logos/'+code
    result=dict(school_code=code,name_zh=name,source=source,checked_at=TODAY,status='access_or_identity_gap',attempts=[],assets=[],resources=[])
    try:
        final,body,charset,mime=fetch_page(source,policy,result)
        if mime not in {'text/html','application/xhtml+xml'}:raise ValueError('not_html')
        if urllib.parse.urlparse(final).path!='/logos/'+code:raise ValueError('school_route_redirect')
        page=LogoPage();page.feed(decode(body,charset))
        sha=hashlib.sha256(body).hexdigest();result.update(source=final,source_sha256=sha,page_headings=page.headings)
        cache=ROOT/'tmp/community-logo-gaps';cache.mkdir(exist_ok=True)
        (cache/(code+'-'+sha[:16]+'.html')).write_bytes(body)
        images,links=page_candidates(page,name)
        result['identity_basis']='MOE school code in page route plus one exact current full-name H1, exact logo alt and active named file listing'
        for url in images:
            attempt=dict(url=url);result['attempts'].append(attempt)
            try:
                resolved,payload,_,_=fetch(url,BASE,policy,5_000_000);meta=inspect_bytes(payload,url)
                if not meta.get('width') or not meta.get('height') or min(meta['width'],meta['height'])<100:raise ValueError('not_logo_preview_dimensions')
                colors=meta.pop('colors');color_basis=meta.pop('color_basis','')
                asset=dict(asset_id=hashlib.sha256((code+'|'+url).encode()).hexdigest()[:24],kind='badge',title=name+'社区校徽预览文件',
                           url=resolved,source=final,file_name=urllib.parse.urlparse(url).path.rsplit('/',1)[-1],upstream_path=None,publisher='urongda 校徽大全',
                           official=False,repository=None,commit=None,repository_license=None,asset_license=None,rights_holder=name,availability='found',
                           verified='auto',checked_at=TODAY,source_type='community_website',source_sha256=sha,identity_basis=result['identity_basis'],
                           usage_note='社区按当前完整学校名与标识码整理的预览；非校方直接发布，现行版本与图形授权未独立确认。文件只索引，颜色仅作参考。',
                           **meta)
                result['assets'].append(dict(asset,colors=colors,color_basis=color_basis));attempt.update(status='content_inspected',sha256=meta['sha256'])
                (cache/(meta['sha256']+'.bin')).write_bytes(payload)
            except Exception as exc:attempt.update(status='inspection_failed',error_type=type(exc).__name__,detail=str(exc)[:150])
        for entry in [dict(title=name+'社区校徽目录',url=final,format='HTML')]+links:
            result['resources'].append(dict(title=entry['title'],url=entry['url'],kinds=['社区校徽目录' if entry['format']=='HTML' else '校徽文件入口'],
                formats=[entry['format']],access_requirement='社区公开目录；云盘文件仅索引，可能有提取码或登录条件，未读取目标文件',source=final,source_sha256=sha,
                repository=None,commit=None,publisher='urongda 校徽大全',official=False,verified='auto',checked_at=TODAY,availability='found',
                content_read=entry['format']=='HTML',download_status='page_read' if entry['format']=='HTML' else 'indexed_not_fetched',
                note='当前校名及学校标识码精确匹配；目录可能自称官方文件，本库保持社区来源，未替代校方版本或授权核验。'))
        result['status']='community_logo_read' if result['assets'] else 'community_listing_only'
    except Exception as exc:result.update(error_type=type(exc).__name__,detail=str(exc)[:170])
    return result


def retain_attempt_history(new,old):
    if not old:return new
    history=list(old.get('previous_attempts',[]))
    history.append({k:old[k] for k in ('checked_at','status','source','source_sha256','attempts','error_type','detail') if k in old})
    new['previous_attempts']=history
    if new['status']=='access_or_identity_gap' and (old.get('assets') or old.get('resources')):
        # A transient re-read failure does not invalidate previously read data.
        new['last_attempt_status']=new['status']
        for key in ('assets','resources','source','source_sha256','identity_basis','page_headings'):
            if key in old:new[key]=old[key]
        new['status']=old['status']
    return new


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--workers',type=int,default=4)
    parser.add_argument('--import-only',action='store_true');parser.add_argument('--limit',type=int);parser.add_argument('--retry-errors',action='store_true')
    args=parser.parse_args();paths={p.parent.name:p for p in (ROOT/'universities').glob('*/*/profile.yaml')}
    profiles={code:yaml.load(path.read_text(),Loader=yaml.CSafeLoader) for code,path in paths.items()}
    targets=[p['identity'] for p in profiles.values() if not p['visual']['logo_assets'] or not p['visual']['color_palette']]
    targets.sort(key=lambda i:(bool(profiles[i['school_code']]['visual']['logo_assets']),i['school_code']))
    if args.limit:targets=targets[:args.limit]
    records={r['school_code']:r for r in map(json.loads,OUTPUT.read_text().splitlines())} if OUTPUT.exists() else {}
    def save():
        temporary=OUTPUT.with_suffix('.pending');temporary.write_text(''.join(json.dumps(records[c],ensure_ascii=False)+'\n' for c in sorted(records)));temporary.replace(OUTPUT)
    if not args.import_only:
        policy=Policy()
        for origin in [BASE,'https://urongda.com','http://www.urongda.com','https://cdn.urongda.com']:policy.allowed(origin+'/')
        pending=[i for i in targets if i['school_code'] not in records or args.retry_errors and (records[i['school_code']]['status']=='community_listing_only' or records[i['school_code']]['status']=='access_or_identity_gap' and records[i['school_code']].get('error_type') in {'URLError','TimeoutError','timeout','OSError'})]
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures={pool.submit(collect,i,policy):i['school_code'] for i in pending}
            for n,f in enumerate(concurrent.futures.as_completed(futures),1):
                code=futures[f];records[code]=retain_attempt_history(f.result(),records.get(code))
                if n%20==0:save();print('Read %d/%d community candidates'%(n,len(pending)),flush=True)
        save()
    changed=0
    for code,record in records.items():
        path=paths[code];p=yaml.safe_load(path.read_text());before=json.dumps(p,sort_keys=True)
        for a in record['assets']:
            upsert(p['visual']['logo_assets'],{k:v for k,v in a.items() if k not in {'colors','color_basis'}},lambda x:x['asset_id'])
            for value in a['colors'][:2]:
                entry=dict(value=value,rgb=rgb(value),cmyk=None,pantone=None,label='社区校徽取色参考',role='reference',method='community_logo_sample',official=False,
                           source=a['url'],page_source=a['source'],asset_id=a['asset_id'],verified='auto',checked_at=record['checked_at'],availability='found',
                           basis=a['color_basis']+'；社区预览图取色，不是学校VI标准或指定主色。')
                upsert(p['visual']['color_palette'],entry,lambda x:(x['source'],x['value'],x['method']))
        for r in record['resources']:upsert(p['visual']['vi_resources'],r,lambda x:(x['url'],x['source']))
        if before!=json.dumps(p,sort_keys=True):path.write_text(yaml.safe_dump(p,allow_unicode=True,sort_keys=False,width=100));changed+=1
    from collections import Counter
    print('Community logo results:',dict(Counter(r['status'] for r in records.values())),'; profiles changed:',changed)


if __name__=='__main__':main()
