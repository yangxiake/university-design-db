#!/usr/bin/env python3
"""Collect explicitly labelled school contacts, portals and homepage identity marks.

Only verified school homepages seed collection. Public HTML is read without
executing scripts; robots, redirects, page identity and size limits are checked.
The ledger contains short evidence and hashes, never complete pages or images.
"""
import argparse
import concurrent.futures
import csv
import datetime as dt
import hashlib
import html.parser
import json
import pathlib
import re
import urllib.parse
import urllib.request

import yaml

from discover_official_pages import AGENT, matches_school_title, read_bounded
from research_all_schools import Policy, SCHOOL_NAMES, same_school, foreign_article
from expand_repository_fields import inspect_bytes
from profile_extensions import put_fact, upsert, rgb

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUTPUT = ROOT / 'data/review/official-extensions-2026.jsonl'
TODAY = dt.date.today().isoformat()
BLOCKS = {'div','p','li','ul','ol','section','header','footer','article','table','tr','td','h1','h2','h3','h4','br'}
VOID = {'br','img','input','meta','link','hr','source','area','base','wbr','embed','param','col'}
FOOT = re.compile(r'footer|copyright|(?:^|[ _-])foot(?:$|[ _-])|bottom|copy(?:right)?|页脚', re.I)
MARK = re.compile(r'logo|xiaohui|badge|校徽|校标|校名|标识', re.I)
EXCLUDED_MARK = re.compile(r'sydw|事业单位|党政|政务|beian|备案|国徽|公安|微信|微博|weibo|wechat|qrcode|二维码|anniversary|校庆|\d{2,3}周年|favicon|icon|footer|bottom|logo_banner|logo_bg|logo-bg|slogan|spacer|(?:top|header)[_-]?(?:slog|bg)|menu|close|search|arrow|搜索', re.I)
EMAIL = r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}'
PORTALS = {
    'resources.admissions_url': re.compile(r'^(?:本科招生(?:网|信息网|信息|网站)?|招生(?:网|信息网|信息|网站|工作|就业)|招生就业(?:网|处|信息网)?|本专科招生)$'),
    'resources.career_url': re.compile(r'^(?:就业(?:网|信息网|指导|服务|服务网|创业|中心)|就业创业网|就业指导中心)$'),
    'resources.information_disclosure_url': re.compile(r'^(?:信息公开(?:网|网站|平台)?|校务公开)$'),
    'resources.english_website': re.compile(r'^(?:English|EN|英文(?:版|网|网站))$', re.I),
}


class Page(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(); self.stack=[]; self.title=''; self.lines=[]; self.parts=[]
        self.links=[]; self.images=[]; self.documents=[]; self.anchor=None; self.image_count=0; self.parts_footer=False

    def flags(self):
        hidden=any(tag in {'script','style','noscript','template','title'} or attrs.get('aria-hidden')=='true'
                   or 'display:none' in (attrs.get('style') or '').replace(' ','') for tag,attrs in self.stack)
        footer=any(tag=='footer' or FOOT.search((attrs.get('class') or '')+' '+(attrs.get('id') or '')) for tag,attrs in self.stack)
        return hidden,footer

    def flush(self):
        text=re.sub(r'\s+',' ',''.join(self.parts)).strip()
        if text:self.lines.append((self.parts_footer,text))
        self.parts=[]

    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        for key in ('pdfsrc','data','src'):
            value=attrs.get(key) or ''
            if (key=='pdfsrc' or tag in {'iframe','object','embed'}) and re.search(r'\.pdf(?:[?#]|$)',value,re.I):
                self.documents.append(dict(url=value,title=(attrs.get('title') or '网页嵌入PDF')[:100],attribute=key))
        if tag in BLOCKS:self.flush()
        if tag not in VOID:self.stack.append((tag,attrs))
        hidden,footer=self.flags()
        if hidden:return
        if tag=='a':self.anchor=dict(href=attrs.get('href') or '', label=[], title=attrs.get('title') or '',footer=footer)
        if tag=='img':
            self.image_count+=1
            label=' '.join(attrs.get(k) or '' for k in ('alt','title','class','id'))
            context=' '.join((a.get('class') or '')+' '+(a.get('id') or '') for _,a in self.stack[-4:])
            src=attrs.get('data-src') or attrs.get('src') or ''
            if self.anchor and attrs.get('alt'):self.anchor['label'].append(attrs['alt'])
            if not footer and self.image_count<=10 and MARK.search(src+' '+label+' '+context) and not EXCLUDED_MARK.search(src+' '+label+' '+context):
                self.images.append(dict(src=src,label=label[:120],context=context[:160],position=self.image_count))

    def handle_startendtag(self,tag,attrs):
        self.handle_starttag(tag,attrs)
        if tag not in VOID:self.handle_endtag(tag)

    def handle_endtag(self,tag):
        if tag in BLOCKS:self.flush()
        if tag=='a' and self.anchor:
            a=self.anchor;a['label']=''.join(a['label']).strip() or a['title'];self.links.append(a);self.anchor=None
        for i in range(len(self.stack)-1,-1,-1):
            if self.stack[i][0]==tag:
                del self.stack[i:];break

    def handle_data(self,data):
        if any(tag=='title' for tag,_ in self.stack):self.title+=data
        hidden,footer=self.flags()
        if hidden:return
        if data.strip():
            if self.parts and footer!=self.parts_footer:self.flush()
            self.parts_footer=footer;self.parts.append(data)
            if self.anchor:self.anchor['label'].append(data)

    def finish(self):self.flush();return self


def decode(data,charset):
    hint=re.search(br'charset\s*=\s*["\']?([A-Za-z0-9_-]+)',data[:5000],re.I)
    for enc in dict.fromkeys([charset,hint.group(1).decode() if hint else None,'utf-8','gb18030']):
        if not enc:continue
        try:return data.decode(enc)
        except (UnicodeError,LookupError):pass
    return data.decode('utf-8','replace')


def fetch(url,home,policy,limit=3_000_000):
    if not same_school(url,home):raise ValueError('cross_school_url')
    if not policy.allowed(url):raise ValueError('robots_disallowed')
    request=urllib.request.Request(url,headers={'User-Agent':AGENT})
    with urllib.request.urlopen(request,timeout=10) as response:
        final=response.geturl()
        if not same_school(final,home):raise ValueError('cross_school_redirect')
        if not policy.allowed(final):raise ValueError('redirect_robots_disallowed')
        return final,read_bounded(response,limit,12),response.headers.get_content_charset(),response.headers.get_content_type()


def inspect_official_asset(asset,home,policy):
    origin=urllib.parse.urlparse(asset['url']);variants=[asset['url'],origin._replace(scheme='http' if origin.scheme=='https' else 'https').geturl()]
    raw=asset.get('identity_basis',{}).get('src')
    if raw:
        normalized=urllib.parse.urljoin(asset['source'],raw.strip()).split('#')[0]
        if normalized not in variants:variants.insert(0,normalized)
    attempts=[]
    for url in dict.fromkeys(variants):
        attempt=dict(url=url);attempts.append(attempt)
        try:
            final,body,_,_=fetch(url,home,policy,5_000_000)
            meta=inspect_bytes(body,asset['file_name'])
            if meta.get('width') and meta.get('height') and (min(meta['width'],meta['height'])<15 or meta['width']*meta['height']>3_000_000):raise ValueError('not_identity_mark_dimensions')
            attempt['status']='content_inspected';asset.update(meta,resolved_url=final,inspection_attempts=attempts)
            if raw and urllib.parse.urljoin(asset['source'],raw.strip())==url:asset['url']=url
            asset.pop('inspection_error',None)
            return asset
        except Exception as exc:
            attempt.update(status='access_or_parse_gap',error_type=type(exc).__name__,detail=str(exc)[:160])
            if str(exc) in {'robots_disallowed','redirect_robots_disallowed','not_identity_mark_dimensions','cross_school_redirect'}:break
    asset.update(access_status='inspection_failed',inspection_attempts=attempts,inspection_error={k:v for k,v in attempts[-1].items() if k!='url'})
    return asset


def contact_claims(page,kind):
    # A home page's news stories may contain other schools' or personal contacts.
    footer=[text for is_footer,text in page.lines if is_footer]
    if kind=='contacts':lines=[text for _,text in page.lines]
    elif footer:lines=footer
    else:
        text='\n'.join(text for _,text in page.lines)
        lines=text[-1600:].splitlines()
    claims=[];addresses=[];postal=[];phones=[];emails=[]
    for line in lines:
        line=line.translate(str.maketrans({'：':':','（':'(','）':')','－':'-','—':'-','＠':'@'}))
        line=re.sub(r'邮\s*政\s*编\s*码','邮政编码',line);line=re.sub(r'邮\s*编','邮编',line)
        line=re.sub(r'网\s*址','网址',line)
        if re.search(r'网络安全|举报|违法|廉政|监督|传真|fax|技术支持',line,re.I):
            # Keep addresses/postcodes below, but never call a fax or hotline an office phone.
            phone_safe=False
        else:phone_safe=True
        for m in re.finditer(r'(?:通信|通讯|学校|学院|联系)?地址\s*:?\s*([^\n]{4,180})',line):
            address=re.split(r'(?:邮编|邮政编码|电话|联系电话|招生热线|热线|电子邮|邮箱|传真|网址|Copyright|版权所有|备案|建议在|[\u4e00-\u9fff]{0,4}公网安备|[\u4e00-\u9fff]{0,2}ICP备|\||；|;)',m.group(1),maxsplit=1,flags=re.I)[0].strip(' :,，。(')
            if 4<=len(address)<=120 and re.search(r'路|街|大道|巷|校区|镇|村|大学|学院|号|园',address) and not re.search(r'https?://|@|地址更新|查看|地图|点击|获取|送达',address):
                addresses.append((address,line[:260]))
        for m in re.finditer(r'(?:邮政编码|邮编|Postal\s*Code|Zip\s*Code)\s*:?\s*([1-9]\d{5})(?!\d)',line,re.I):postal.append((m.group(1),line[:260]))
        if phone_safe:
            for m in re.finditer(r'(?P<label>(?:联系|咨询|招生咨询|招生|办公|办公室|总机|值班)?电话|Tel(?:ephone)?\.?)\s*:?\s*(?P<phone>\(?0\d{2,3}\)?[ -]*\d{7,8}(?:\s*转\s*\d{1,5})?)(?!\d)',line,re.I):
                phones.append((m.group('label')+': '+m.group('phone'),line[:260]))
        for m in re.finditer(r'(?:电子邮箱|电子邮件|联系邮箱|邮箱|E-?mail)\s*:?\s*('+EMAIL+')',line,re.I):emails.append((m.group(1),line[:260]))
    for a in page.links:
        if a['href'].lower().startswith('mailto:') and (a['footer'] or kind=='contacts'):
            email=urllib.parse.unquote(a['href'][7:].split('?')[0])
            if re.fullmatch(EMAIL,email):emails.append((email,(a['label']+' '+email)[:260]))
    # Preserve multi-address pages as one labelled communications field; do not
    # invent which campus is the headquarters or pair unlabelled postal codes.
    for field,items in [('location.address',addresses),('location.postal_code',postal),('contacts.phone',phones),('contacts.email',emails)]:
        unique=list(dict.fromkeys(value for value,_ in items))
        if not unique or (field=='location.postal_code' and len(unique)>1):continue
        value='；'.join(unique[:4])
        if len(value)>490:continue
        claims.append(dict(field=field,value=value,evidence=list(dict.fromkeys(e for _,e in items))[:4],
                           basis=('学校官网联系页明确列出的联系方式' if kind=='contacts' else '学校官网首页页脚或末尾明确标注的通讯信息')+'；保留原标签，未认定为全部校区或统一总机。'))
    return claims


def portal_claims(page,final,home):
    out=[];seen=set()
    for a in page.links:
        label=re.sub(r'\s+','',a['label']);href=a['href']
        if not href or href.startswith(('#','javascript:')):continue
        url=urllib.parse.urljoin(final,href).split('#')[0]
        if not same_school(url,home):continue
        target=urllib.parse.urlparse(url);origin=urllib.parse.urlparse(final)
        if target.hostname==origin.hostname and (target.path==origin.path or target.path in {'','/','/index.htm','/index.html','/index.jsp','/main.htm'}) and not target.query:continue
        for field,pattern in PORTALS.items():
            if field not in seen and pattern.fullmatch(label):
                out.append(dict(field=field,value=url,evidence=[a['label'][:80]],
                                basis='学校官网首页导航中标明用途的同校网址；只确认链接出处，目标页访问状态另记。'))
                seen.add(field)
    return out


def collect(school,discovery):
    code=school['school_code'];name=school['name_zh']
    result=dict(school_code=code,name_zh=name,checked_at=TODAY,pages=[],claims=[],assets=[],status='no_confirmed_homepage',collector_revision=1)
    website=school.get('home') or discovery.get('homepage_url')
    if not website:return result
    result['home']=website;policy=Policy();home_page=None;final_home=website
    # Only a failed request allows a same-path protocol variant. The final page
    # must still pass the full school identity check, with independent colleges excluded.
    p=urllib.parse.urlparse(website);variants=[website,p._replace(scheme='http' if p.scheme=='https' else 'https').geturl()]
    for url in dict.fromkeys(variants):
        attempt=dict(requested_url=url,kind='homepage');result['pages'].append(attempt)
        try:
            final,body,charset,mime=fetch(url,website,policy)
            if mime not in {'text/html','application/xhtml+xml'}:raise ValueError('not_html')
            page=Page();page.feed(decode(body,charset));page.finish()
            if not matches_school_title(name,page.title,SCHOOL_NAMES):
                from collect_homepage_identity import ownership_evidence
                if not school.get('home') or not ownership_evidence(name,[t for _,t in page.lines],SCHOOL_NAMES):
                    raise ValueError('homepage_identity_mismatch')
            attempt.update(status='read',source_url=final,title=page.title.strip()[:180],sha256=hashlib.sha256(body).hexdigest())
            home_page=page;final_home=final;break
        except Exception as exc:
            attempt.update(status='access_gap',error_type=type(exc).__name__,detail=str(exc)[:140])
            if str(exc) in {'robots_disallowed','redirect_robots_disallowed','homepage_identity_mismatch','cross_school_redirect'}:break
    if home_page is None:result['status']='homepage_access_gap';return result
    result['status']='researched_partial'
    for claim in contact_claims(home_page,'homepage')+portal_claims(home_page,final_home,website):
        claim['source']=final_home;result['claims'].append(claim)
    # One dedicated contact page, on the same hostname and with an exact label.
    for a in home_page.links:
        if re.sub(r'\s+','',a['label']) not in {'联系我们','联系方式','联系学校'}:continue
        url=urllib.parse.urljoin(final_home,a['href']).split('#')[0]
        if urllib.parse.urlparse(url).hostname!=urllib.parse.urlparse(final_home).hostname or url==final_home:continue
        attempt=dict(requested_url=url,kind='contacts');result['pages'].append(attempt)
        try:
            final,body,charset,mime=fetch(url,website,policy)
            if mime not in {'text/html','application/xhtml+xml'}:raise ValueError('not_html')
            page=Page();page.feed(decode(body,charset));page.finish()
            if foreign_article(page.title,name) or re.search(r'研究生院|附属|学院办公室|招生办|教务处|图书馆|信息中心|网络中心',page.title):raise ValueError('department_or_foreign_contact_page')
            if name not in ''.join(text for _,text in page.lines)+page.title:raise ValueError('contact_page_identity_gap')
            attempt.update(status='read',source_url=final,title=page.title.strip()[:180],sha256=hashlib.sha256(body).hexdigest())
            existing={c['field'] for c in result['claims']}
            for claim in contact_claims(page,'contacts'):
                if claim['field'] not in existing:claim['source']=final;result['claims'].append(claim)
        except Exception as exc:attempt.update(status='access_gap',error_type=type(exc).__name__,detail=str(exc)[:140])
        break
    used=set()
    for image in home_page.images:
        url=urllib.parse.urljoin(final_home,image['src'].strip()).split('#')[0]
        if not same_school(url,website) or url in used:continue
        used.add(url)
        if len(used)>2:break
        asset_id=hashlib.sha256((code+'|'+url).encode()).hexdigest()[:24]
        label=image['label'];kind='badge' if re.search(r'校徽|xiaohui|badge',label+' '+url,re.I) else ('wordmark' if re.search(r'校名',label) else 'site_identity')
        asset=dict(asset_id=asset_id,kind=kind,title='学校官网页眉标识',url=url,source=final_home,
                   file_name=urllib.parse.unquote(urllib.parse.urlparse(url).path.rsplit('/',1)[-1]),upstream_path=None,
                   publisher=name,official=True,repository=None,commit=None,repository_license=None,asset_license=None,
                   rights_holder=name,format=None,width=None,height=None,vector=None,has_alpha=None,transparent_background=None,
                   sha256=None,access_status='indexed_not_fetched',availability='found',verified='auto',checked_at=TODAY,
                   source_type='official_website',identity_basis=image,
                   usage_note='官网首页标题匹配教育部完整校名、页眉标识元素匹配且排除页脚/二维码/政务/校庆图。official表示校方网页发布；site_identity的具体校徽/校名构成及现行VI版本尚未核验。图形授权未单独声明；只索引文件与元数据。')
        inspect_official_asset(asset,website,policy)
        result['assets'].append(asset)
    return result


def sanitize_record(record):
    """Reapply current exclusions to a saved ledger, preserving rejected evidence."""
    retained=[];rejected=record.setdefault('excluded_claims',[])
    for claim in record['claims']:
        if claim['field']=='location.address':
            old=claim['value'];clean=re.split(r'(?:[\u4e00-\u9fff]{0,4}公网安备|[\u4e00-\u9fff]{0,2}ICP备|版权所有|备案)',old,maxsplit=1)[0].strip()
            if claim.get('evidence'):
                parsed=Page();parsed.lines=[(True,line) for line in claim['evidence']]
                fresh=[c['value'] for c in contact_claims(parsed,'homepage') if c['field']=='location.address']
                if fresh:clean=fresh[0]
            if clean!=old:claim['previous_value']=old;claim['value']=clean
            if not re.search(r'路|街|大道|巷|校区|镇|村|大学|学院|号|园',clean):
                rejected.append(dict(claim,reason='incomplete_address'));continue
        if claim['field'].startswith('resources.'):
            target=urllib.parse.urlparse(claim['value']);origin=urllib.parse.urlparse(claim['source'])
            if target.hostname==origin.hostname and (target.path==origin.path or target.path in {'','/','/index.htm','/index.html','/index.jsp','/main.htm'}) and not target.query:
                rejected.append(dict(claim,reason='portal_label_points_to_main_homepage'));continue
        retained.append(claim)
    record['claims']=retained
    retained=[];excluded=record.setdefault('excluded_assets',[])
    for asset in record['assets']:
        basis=asset.get('identity_basis',{})
        if EXCLUDED_MARK.search(asset['url']+' '+basis.get('label','')+' '+basis.get('context','')) or asset.get('inspection_error',{}).get('detail')=='not_identity_mark_dimensions':
            excluded.append(dict(url=asset['url'],asset_id=asset['asset_id'],reason='excluded_mark_context'));continue
        retained.append(asset)
    record['assets']=retained
    return record


def apply_record(profile,record):
    changed=False
    for excluded in record.get('excluded_claims',[]):
        group,key=excluded['field'].split('.');current=profile[group][key]
        if current.get('source_type')=='official_website' and current.get('verified')=='auto' and current.get('value')==excluded['value'] and current.get('source')==excluded['source']:
            from profile_extensions import empty_fact
            profile[group][key]=empty_fact()
    for claim in record['claims']:
        if claim.get('previous_value'):
            group,key=claim['field'].split('.');current=profile[group][key]
            if current.get('source_type')=='official_website' and current.get('verified')=='auto' and current.get('value')==claim['previous_value'] and current.get('source')==claim['source']:
                from profile_extensions import empty_fact
                profile[group][key]=empty_fact()
    removed={a['asset_id'] for a in record.get('excluded_assets',[])}
    profile['visual']['logo_assets']=[a for a in profile['visual']['logo_assets'] if a['asset_id'] not in removed or a.get('verified')=='human']
    profile['visual']['color_palette']=[a for a in profile['visual']['color_palette'] if a.get('asset_id') not in removed or a.get('verified')=='human']
    for claim in record['claims']:
        meta=dict(source=claim['source'],source_type='official_website',verified='auto',checked_at=record['checked_at'])
        changed=put_fact(profile,claim['field'],claim['value'],meta,basis=claim['basis'],evidence=claim['evidence']) or changed
    for asset in record['assets']:
        upsert(profile['visual']['logo_assets'],{k:v for k,v in asset.items() if k not in {'colors','color_basis','attempts'}},lambda x:x['asset_id']);changed=True
        # These are reference colours sampled from a website mark. They never
        # update color_primary/secondary or an official VI conclusion.
        if asset['access_status']=='content_inspected':
            for color in asset.get('colors',[])[:2]:
                value=color['value'] if isinstance(color,dict) else color
                entry=dict(value=value,rgb=rgb(value),cmyk=None,pantone=None,role='reference',method='manual_derived',official=False,
                           basis='官网页眉标识文件的自动取色建议；'+asset.get('color_basis','文件高频色').replace('社区标识','官网标识')+'；未认定为学校VI标准色。',
                           source=asset['url'],page_source=asset['source'],asset_id=asset['asset_id'],verified='auto',checked_at=record['checked_at'],availability='found')
                upsert(profile['visual']['color_palette'],entry,lambda x:(x['source'],x['value'],x['method']))
    return changed


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers',type=int,default=16);parser.add_argument('--limit',type=int)
    parser.add_argument('--school-code',action='append',help='Collect only these schools; preserve the rest of the ledger')
    parser.add_argument('--resume',action='store_true');parser.add_argument('--retry-gaps',action='store_true');parser.add_argument('--import-only',action='store_true')
    parser.add_argument('--retry-asset-errors',action='store_true',help='Retry only failed official image files from the saved ledger')
    args=parser.parse_args()
    with (ROOT/'data/universities-scope-2026.csv').open(encoding='utf-8-sig') as f:schools=list(csv.DictReader(f))
    with (ROOT/'data/review/official-page-discovery-2026.csv').open(encoding='utf-8-sig') as f:discovery={r['school_code']:r for r in csv.DictReader(f)}
    profiles={};paths={}
    for path in sorted((ROOT/'universities').glob('*/*/profile.yaml')):
        profile=yaml.safe_load(path.read_text());code=profile['identity']['school_code'];profiles[code]=profile;paths[code]=path
    for school in schools:
        fact=profiles[school['school_code']]['identity']['official_website']
        school['home']=fact.get('value') if fact.get('availability')=='found' else None
    results={r['school_code']:r for r in map(json.loads,OUTPUT.read_text().splitlines())} if OUTPUT.exists() else {}
    selected=schools[:args.limit] if args.limit else schools
    if args.school_code:selected=[s for s in selected if s['school_code'] in args.school_code]
    pending=[s for s in selected if (not args.resume or s['school_code'] not in results) and
             (not args.retry_gaps or results.get(s['school_code'],{}).get('status')=='homepage_access_gap')]
    def save():
        temp=OUTPUT.with_suffix('.jsonl.tmp');temp.write_text(''.join(json.dumps(results[s['school_code']],ensure_ascii=False)+'\n' for s in schools if s['school_code'] in results),encoding='utf-8');temp.replace(OUTPUT)
    if not args.import_only and not args.retry_asset_errors:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures={pool.submit(collect,s,discovery.get(s['school_code'],{})):s['school_code'] for s in pending}
            for n,future in enumerate(concurrent.futures.as_completed(futures),1):
                results[futures[future]]=sanitize_record(future.result())
                if n%40==0:save();print('Collected %d/%d schools; %d labelled claims; %d identity files.'%(n,len(pending),sum(len(r['claims']) for r in results.values()),sum(len(r['assets']) for r in results.values())),flush=True)
        save()
    if args.retry_asset_errors:
        for record in results.values():sanitize_record(record)
        jobs=[(record,asset) for record in results.values() for asset in record['assets'] if asset['access_status']=='inspection_failed']
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures=[pool.submit(inspect_official_asset,asset,record['home'],Policy()) for record,asset in jobs]
            for future in concurrent.futures.as_completed(futures):future.result()
        print('Retried %d official identity files.'%len(jobs))
    for record in results.values():sanitize_record(record)
    save()
    touched=0
    for code,record in results.items():
        if args.school_code and code not in args.school_code:continue
        # A long network run must merge into the current fact source, preserving
        # any school or reviewed fields added while collection was in progress.
        profiles[code]=yaml.safe_load(paths[code].read_text())
        before=json.dumps(profiles[code],sort_keys=True,ensure_ascii=False);apply_record(profiles[code],record)
        if before!=json.dumps(profiles[code],sort_keys=True,ensure_ascii=False):
            paths[code].write_text(yaml.safe_dump(profiles[code],allow_unicode=True,sort_keys=False,width=100),encoding='utf-8');touched+=1
    print('Official extension ledger: %d schools; changed profiles: %d.'%(len(results),touched))


if __name__=='__main__':main()
