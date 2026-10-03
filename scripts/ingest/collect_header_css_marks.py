#!/usr/bin/env python3
"""Find school header identity files in static HTML and explicit CSS rules."""
import argparse
import concurrent.futures
import datetime as dt
import hashlib
import json
import pathlib
import re
import urllib.parse

import yaml
from collect_official_extensions import Page,MARK,EXCLUDED_MARK,decode,fetch,inspect_official_asset,apply_record
from collect_homepage_identity import ownership_evidence, reviewed_homepage_caches
from discover_official_pages import matches_school_title,safe_url
from research_all_schools import Policy,SCHOOL_NAMES,same_school

ROOT=pathlib.Path(__file__).resolve().parents[2]
OUTPUT=ROOT/'data/review/header-css-marks-2026.jsonl'
TODAY=dt.date.today().isoformat()
NOT_HEADER=re.compile(r'djlogo|djszzx|党建|党徽|教务|logo_jw|browser|modal|partner|friend|news-scroll',re.I)


def excluded_header_mark(image):
    # Some school headers wrap the actual logo in a menu-mod layout. The
    # wrapper name does not make that logo a navigation button; direct image
    # labels/paths containing menu, icon, search, etc. remain excluded.
    context=re.sub(r'(?<!\S)menu-mod(?!\S)','',image.get('context') or '')
    evidence=context+' '+(image.get('label') or '')+' '+(image.get('src') or '')
    return bool(NOT_HEADER.search(evidence) or EXCLUDED_MARK.search(evidence))


def is_header_reference(image):
    context=image.get('context') or '';label=image.get('label') or '';src=image.get('src') or ''
    if excluded_header_mark(image):return False
    if image.get('css_url'):return bool(MARK.search(context))
    return image.get('position',99)<=10 or bool(MARK.search(context))


class HeaderPage(Page):
    def __init__(self):
        super().__init__();self.stylesheets=[];self.styles=[];self.style=None;self.extra_images=[];self.inline=[]
    def handle_starttag(self,tag,attrs):
        super().handle_starttag(tag,attrs);a=dict(attrs)
        if tag=='style':self.style=[]
        if tag=='link' and 'stylesheet' in (a.get('rel') or '').lower().split() and a.get('href'):self.stylesheets.append(a['href'])
        hidden,footer=self.flags()
        if hidden or footer:return
        context=' '.join((v.get('class') or '')+' '+(v.get('id') or '') for _,v in self.stack[-4:])
        if a.get('style') and MARK.search(context):self.inline.append((context,a['style']))
        if tag=='img' and self.image_count<=50:
            src=a.get('data-original') or a.get('data-lazy-src') or a.get('data-src') or a.get('src') or ''
            label=' '.join(a.get(k) or '' for k in ('alt','title','class','id'))
            if MARK.search(src+' '+label+' '+context) and not excluded_header_mark(dict(src=src,label=label,context=context)):
                self.extra_images.append(dict(src=src,label=label[:120],context=context[:160],position=self.image_count))
    def handle_data(self,data):
        super().handle_data(data)
        if self.style is not None:self.style.append(data)
    def handle_endtag(self,tag):
        if tag=='style' and self.style is not None:self.styles.append(''.join(self.style));self.style=None
        super().handle_endtag(tag)


def css_candidates(text,base):
    text=re.sub(r'/\*[\s\S]*?\*/','',text);found=[]
    for selector,body in re.findall(r'([^{}]+)\{([^{}]*)\}',text):
        for src in re.findall(r'url\(\s*[\'\"]?([^\)\'\"\s]+)',body,re.I):
            context=selector.strip()[:160]
            if not MARK.search(context+' '+src) or EXCLUDED_MARK.search(context+' '+src) or NOT_HEADER.search(context+' '+src):continue
            if re.search(r'footer|bottom|qrcode|weixin|wechat|nav-icon|icon-logo',context,re.I):continue
            url=urllib.parse.urljoin(base,src)
            if safe_url(url) and re.search(r'\.(png|svg|jpe?g|gif|webp)(?:[?#]|$)',url,re.I):
                found.append(dict(src=url,label='静态CSS标识规则',context=context,css_url=base))
    return found


def collect(identity,cached_home=None):
    code,name,home=identity['school_code'],identity['name_zh'],identity['official_website']['value']
    result=dict(school_code=code,name_zh=name,checked_at=TODAY,home=home,status='access_or_identity_gap',pages=[],assets=[],claims=[])
    policy=Policy();parsed=urllib.parse.urlparse(home)
    for url in dict.fromkeys([home,parsed._replace(scheme='http' if parsed.scheme=='https' else 'https').geturl()]):
        attempt=dict(requested_url=url);result['pages'].append(attempt)
        try:
            if cached_home and url==cached_home['url']:
                body=pathlib.Path(cached_home['path']).read_bytes()
                if hashlib.sha256(body).hexdigest()!=cached_home['sha256']:raise ValueError('homepage_cache_hash_mismatch')
                final,charset,mime=cached_home['url'],None,'text/html'
                attempt.update(retrieval='hash_matched_previous_homepage',retrieved_at=cached_home['checked_at'])
            else:
                final,body,charset,mime=fetch(url,home,policy)
            if mime not in {'text/html','application/xhtml+xml'}:raise ValueError('not_html')
            page=HeaderPage();page.feed(decode(body,charset));page.finish()
            if not (matches_school_title(name,page.title,SCHOOL_NAMES) or ownership_evidence(name,[t for _,t in page.lines],SCHOOL_NAMES)):raise ValueError('homepage_identity_gap')
            sha=hashlib.sha256(body).hexdigest();attempt.update(status='school_page_read',source_url=final,title=page.title[:150],source_sha256=sha)
            cache=ROOT/'tmp/header-css';cache.mkdir(exist_ok=True);(cache/(code+'-'+sha[:16]+'.html')).write_bytes(body)
            candidates=list(page.images+page.extra_images)
            for text in page.styles:candidates+=css_candidates(text,final)
            for selector,style in page.inline:candidates+=css_candidates(selector+'{'+style+'}',final)
            for sheet in list(dict.fromkeys(page.stylesheets))[:5]:
                sheet=urllib.parse.urljoin(final,sheet)
                if not same_school(sheet,home):continue
                css_attempt=dict(requested_url=sheet,kind='stylesheet');result['pages'].append(css_attempt)
                try:
                    css_url,css_body,css_charset,css_mime=fetch(sheet,home,policy,500_000)
                    css_attempt.update(status='stylesheet_read',source_url=css_url,source_sha256=hashlib.sha256(css_body).hexdigest())
                    candidates+=css_candidates(decode(css_body,css_charset),css_url)
                except Exception as exc:css_attempt.update(status='access_gap',detail=str(exc)[:130],error_type=type(exc).__name__)
            unique={}
            for image in candidates:
                target=urllib.parse.urljoin(final,image['src'].strip()).split('#')[0]
                if same_school(target,home) and is_header_reference(image):unique.setdefault(target,image)
            for target,image in list(unique.items())[:3]:
                asset=dict(asset_id=hashlib.sha256((code+'|'+target).encode()).hexdigest()[:24],kind='site_identity',title='学校官网HTML/CSS页眉标识',url=target,
                    source=final,file_name=urllib.parse.unquote(urllib.parse.urlparse(target).path.rsplit('/',1)[-1]),upstream_path=None,publisher=name,official=True,
                    repository=None,commit=None,repository_license=None,asset_license=None,rights_holder=name,format=None,width=None,height=None,vector=None,
                    has_alpha=None,transparent_background=None,sha256=None,access_status='indexed_not_fetched',availability='found',verified='auto',checked_at=TODAY,
                    source_type='official_website',source_sha256=sha,identity_basis=image,
                    usage_note='已确认学校首页身份；文件由页眉标识元素或同校静态CSS标识规则明确引用。具体徽/名构成、现行VI版本及使用许可未独立确认；只保存链接与元数据。')
                inspect_official_asset(asset,home,policy);result['assets'].append(asset)
            result['status']='header_marks_read' if any(a['access_status']=='content_inspected' for a in result['assets']) else 'no_inspected_header_mark'
            return result
        except Exception as exc:
            attempt.update(status='access_or_identity_gap',detail=str(exc)[:140],error_type=type(exc).__name__)
            if not isinstance(exc,OSError):break
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--workers',type=int,default=10)
    parser.add_argument('--collect-only',action='store_true');parser.add_argument('--import-only',action='store_true')
    parser.add_argument('--output',default='data/review/header-css-marks-2026.jsonl',help='Separate batch ledger; earlier evidence stays intact')
    parser.add_argument('--school-code',action='append',help='Read selected schools into this ledger')
    parser.add_argument('--homepage-cache-receipts',help='Use hash-matched, reviewed canonical homepage caches')
    args=parser.parse_args();paths={p.parent.name:p for p in (ROOT/'universities').glob('*/*/profile.yaml')}
    output=ROOT/args.output
    targets=[]
    for code,path in paths.items():
        p=yaml.load(path.read_text(),Loader=yaml.CSafeLoader)
        if not any(a.get('access_status') == 'content_inspected' for a in p['visual']['logo_assets']) and p['identity']['official_website'].get('value'):targets.append(p['identity'])
    if args.school_code:targets=[i for i in targets if i['school_code'] in args.school_code]
    caches=reviewed_homepage_caches(ROOT/args.homepage_cache_receipts,[yaml.load(p.read_text(),Loader=yaml.CSafeLoader)['identity']for p in paths.values()])if args.homepage_cache_receipts else{}
    records={r['school_code']:r for r in map(json.loads,output.read_text().splitlines())} if output.exists() else {}
    def save():
        temporary=output.with_suffix('.pending');temporary.write_text(''.join(json.dumps(records[c],ensure_ascii=False)+'\n' for c in sorted(records)));temporary.replace(output)
    if not args.import_only:
        pending=[i for i in targets if i['school_code'] not in records]
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures={pool.submit(collect,i,caches.get(i['school_code'])):i['school_code'] for i in pending}
            for n,f in enumerate(concurrent.futures.as_completed(futures),1):
                records[futures[f]]=f.result()
                if n%15==0:save();print('Read %s/%s header candidates'%(n,len(pending)),flush=True)
        save()
    if args.collect_only:return
    changed=0
    for code,r in records.items():
        retained=[]
        for a in r['assets']:
            if is_header_reference(a['identity_basis']):retained.append(a)
            else:r.setdefault('excluded_assets',[]).append(dict(asset_id=a['asset_id'],url=a['url'],reason='not_school_header_context'))
        r['assets']=retained
        if r['status']!='access_or_identity_gap':r['status']='header_marks_read' if any(a['access_status']=='content_inspected' for a in retained) else 'no_inspected_header_mark'
        path=paths[code];p=yaml.safe_load(path.read_text());before=json.dumps(p,sort_keys=True);apply_record(p,r)
        if json.dumps(p,sort_keys=True)!=before:path.write_text(yaml.safe_dump(p,allow_unicode=True,sort_keys=False,width=100));changed+=1
    save()
    from collections import Counter
    print('Header results:',dict(Counter(r['status'] for r in records.values())),'; profiles changed:',changed)


if __name__=='__main__':main()
