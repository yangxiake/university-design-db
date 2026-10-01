#!/usr/bin/env python3
"""Follow a public URL directory to school-owned visual pages and downloads.

The directory is a discovery source only. Exact MOE school identities, school
hosts, visible page headings and resource labels are checked independently.
No copied directory prose or downloaded graphic files are redistributed.
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

import yaml
from collect_official_extensions import Page, decode, fetch, inspect_official_asset, EXCLUDED_MARK, apply_record
from collect_homepage_identity import ownership_evidence
from discover_official_pages import matches_school_title, safe_url
from profile_extensions import put_fact, upsert
from research_all_schools import Policy, SCHOOL_NAMES, same_school, foreign_article

ROOT=pathlib.Path(__file__).resolve().parents[2]
DIRECTORY='https://www.cnblogs.com/cdz-111/articles/22432508'
OUTPUT=ROOT/'data/review/visual-directory-2026.jsonl'
LEADS=ROOT/'data/review/visual-directory-leads-2026.json'
TODAY=dt.date.today().isoformat()
RESOURCE=re.compile(r'视觉(?:识别|形象)|形象识别|标识(?:系统|规范|下载)|校徽|校标(?!准)|校名|标准色|[Vv][Ii][Ss]?(?:系统|手册|设计)|PPT模板|演示文稿模板|PowerPoint模板')
TEMPLATE=re.compile(r'PPT\s*模板|演示文稿模板|PowerPoint\s*模板',re.I)
ANNIVERSARY=re.compile(r'校庆|周年|anniversary',re.I)
FILE=re.compile(r'\.(ai|cdr|eps|pdf|zip|rar|7z|svg|png|jpe?g|pptx?)(?:[?#]|$)',re.I)


class Table(html.parser.HTMLParser):
    def __init__(self):
        super().__init__();self.rows=[];self.row=None;self.cell=None;self.anchor=None
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='tr':self.row=[]
        elif tag in {'td','th'} and self.row is not None:self.cell=dict(text=[],links=[])
        elif tag=='a' and self.cell is not None:self.anchor=dict(href=attrs.get('href') or '',text=[])
    def handle_data(self,data):
        if self.cell is not None:self.cell['text'].append(data)
        if self.anchor is not None:self.anchor['text'].append(data)
    def handle_endtag(self,tag):
        if tag=='a' and self.anchor is not None:
            self.anchor['text']=''.join(self.anchor['text']).strip()
            if self.cell is not None:self.cell['links'].append(self.anchor)
            self.anchor=None
        if tag in {'td','th'} and self.cell is not None:
            self.cell['text']=''.join(self.cell['text']).strip();self.row.append(self.cell);self.cell=None
        if tag=='tr' and self.row is not None:self.rows.append(self.row);self.row=None


class VisualPage(Page):
    def __init__(self):
        super().__init__();self.headings=[];self.heading=None
    def handle_starttag(self,tag,attrs):
        super().handle_starttag(tag,attrs)
        chrome=any(t in {'nav','header','aside','footer'} or re.search(r'nav|menu|footer|header',str(a.get('class') or '')+' '+str(a.get('id') or ''),re.I) for t,a in self.stack)
        if tag in {'h1','h2','h3'} and not self.flags()[0] and not chrome:self.heading=[]
    def handle_data(self,data):
        super().handle_data(data)
        if self.heading is not None and not self.flags()[0]:self.heading.append(data)
    def handle_endtag(self,tag):
        if tag in {'h1','h2','h3'} and self.heading is not None:
            self.headings.append(''.join(self.heading).strip());self.heading=None
        super().handle_endtag(tag)


def directory_leads(body,charset,scope):
    table=Table();table.feed(decode(body,charset));rows=[]
    for row in table.rows:
        if len(row)!=7 or row[1]['text'] not in scope:continue
        def urls(cell):return list(dict.fromkeys(a['href'] for a in cell['links'] if safe_url(a['href'])))
        rows.append(dict(school_code=scope[row[1]['text']],name_zh=row[1]['text'],
                         home_leads=urls(row[3]),visual_leads=urls(row[4]),download_leads=urls(row[5])))
    return rows


def page_identity(name,page):
    text=[t for _,t in page.lines]
    return not foreign_article(page.title,name) and (
        matches_school_title(name,page.title,SCHOOL_NAMES) or
        bool(ownership_evidence(name,text,SCHOOL_NAMES)))


def visual_heading(page):
    # A navigation item alone is insufficient: reject ordinary news/home pages.
    return RESOURCE.search(page.title) or any(RESOURCE.search(h) for h in page.headings)


def resource_entry(title,url,source,sha,anniversary=False,fmt=None):
    title=re.sub(r'\s+',' ',title).strip()
    template=bool(TEMPLATE.search(title))
    kinds=['PPT模板'] if template else (['视觉识别规范/资源'] if re.search(r'视觉|形象识别|VI|VIS|标准色',title,re.I) else ['校徽/校名介绍及资源'])
    if anniversary:kinds.append('校庆专用')
    return dict(title=title[:150],url=url,kinds=kinds,formats=[fmt] if fmt else ['HTML'],
        access_requirement='公开校方页面；附件链接仅按页面索引，下载状态与文件内容未经本轮核验',
        source=source,repository=None,commit=None,official=True,verified='auto',checked_at=TODAY,availability='found',source_sha256=sha,
        note='第三方目录只用于发现网址；已读取校方页并核对完整学校身份及标识/模板标题。'+
             ('本条为校庆专用资料，不作为通用VI或学校主题色。' if anniversary else '图形与模板使用须遵守校方规范；库内仅保留入口和元数据。'))


def collect(lead,profile):
    code=lead['school_code'];name=lead['name_zh'];policy=Policy()
    result=dict(school_code=code,name_zh=name,checked_at=TODAY,directory=DIRECTORY,pages=[],resources=[],assets=[],claims=[],status='no_verified_visual_page')
    home=profile['identity']['official_website'].get('value')
    if not home:home=next((u for u in lead['home_leads'] if urllib.parse.urlparse(u).hostname.endswith(('.edu.cn','.ac.cn'))),None)
    if not home:result['status']='school_host_not_confirmed';return result
    pending=list(dict.fromkeys(lead['visual_leads']+lead['download_leads']))
    seen=set();good=0
    while pending and len(seen)<4:
        requested=pending.pop(0)
        if requested in seen or not same_school(requested,home):continue
        seen.add(requested);attempt=dict(requested_url=requested);result['pages'].append(attempt)
        try:
            final,body,charset,mime=fetch(requested,home,policy,5_000_000)
            if mime not in {'text/html','application/xhtml+xml'}:raise ValueError('not_html_page')
            page=VisualPage();page.feed(decode(body,charset));page.finish()
            sha=hashlib.sha256(body).hexdigest();attempt.update(source_url=final,title=page.title.strip()[:160],source_sha256=sha)
            cache=ROOT/'tmp/visual-directory';cache.mkdir(exist_ok=True)
            (cache/(code+'-'+sha[:16]+'.html')).write_bytes(body)
            if not page_identity(name,page):raise ValueError('school_identity_gap')
            if not visual_heading(page):raise ValueError('no_visual_resource_heading')
            attempt['status']='school_visual_page_read';good+=1
            title=next((h for h in page.headings if RESOURCE.search(h)),page.title.strip()) or name+'标识页面'
            special=bool(ANNIVERSARY.search(title));result['resources'].append(resource_entry(title,final,final,sha,special))
            for anchor in page.links:
                label=anchor['label'].strip();url=urllib.parse.urljoin(final,anchor['href']).split('#')[0]
                if not safe_url(url) or anchor['footer']:continue
                suffix=FILE.search(url) or FILE.search(label)
                if suffix and (RESOURCE.search(label) or re.search(r'手册|标志|LOGO',label,re.I)):
                    fmt=suffix[1].upper();result['resources'].append(resource_entry(label,url,final,sha,special or bool(ANNIVERSARY.search(label)),fmt))
                elif same_school(url,home) and RESOURCE.search(label) and not ANNIVERSARY.search(label) and url not in seen:
                    pending.append(url)
            if not special:
                for image in page.images[:2]:
                    url=urllib.parse.urljoin(final,image['src'].strip()).split('#')[0]
                    if not same_school(url,home) or EXCLUDED_MARK.search(url+' '+image['label']):continue
                    result['assets'].append(dict(asset_id=hashlib.sha256((code+'|'+url).encode()).hexdigest()[:24],kind='site_identity',
                        title='校方标识页面页眉文件',url=url,source=final,file_name=urllib.parse.unquote(urllib.parse.urlparse(url).path.rsplit('/',1)[-1]),
                        upstream_path=None,publisher=name,official=True,repository=None,commit=None,repository_license=None,asset_license=None,
                        rights_holder=name,format=None,width=None,height=None,vector=None,has_alpha=None,transparent_background=None,sha256=None,
                        access_status='indexed_not_fetched',availability='found',verified='auto',checked_at=TODAY,source_type='official_website',identity_basis=image,
                        usage_note='完整学校身份与标识页面标题已自动核对；此文件为页眉标识，具体徽/名构成未判定。只索引文件，不再分发，按校方规范使用。'))
            # Color numerals are leads for a subsequent source-level decision.
            lines=[t for _,t in page.lines if re.search(r'RGB|CMYK|Pantone|标准色|色值|#[0-9a-fA-F]{6}',t)]
            if lines:attempt['color_evidence_leads']=[t[:350] for t in lines[:10]]
        except Exception as exc:
            attempt.update(status='access_or_identity_gap',error_type=type(exc).__name__,detail=str(exc)[:160])
            if isinstance(exc,OSError):
                parsed=urllib.parse.urlparse(requested);alternate=parsed._replace(scheme='http' if parsed.scheme=='https' else 'https').geturl()
                if alternate not in seen:pending.insert(0,alternate)
    # Read at most two new file URLs per school; preserve the actual format.
    unique={a['asset_id']:a for a in result['assets']}
    result['assets']=list(unique.values())[:2]
    existing={a['asset_id'] for a in profile['visual']['logo_assets']}
    result['assets']=[a for a in result['assets'] if a['asset_id'] not in existing]
    for asset in result['assets']:inspect_official_asset(asset,home,policy)
    result['status']='verified_visual_resources' if good else result['status']
    return result


def recover_cached_pages(records,profiles):
    """Recover generic-title pages on the exact already confirmed main host."""
    count=0
    for code,record in records.items():
        home=profiles[code]['identity']['official_website'].get('value')
        if not home:continue
        host=(urllib.parse.urlparse(home).hostname or '').removeprefix('www.')
        for attempt in record['pages']:
            if attempt.get('detail')!='school_identity_gap' or not attempt.get('source_sha256'):continue
            url=attempt['source_url']
            if host!=(urllib.parse.urlparse(url).hostname or '').removeprefix('www.'):continue
            raw=ROOT/'tmp/visual-directory'/(code+'-'+attempt['source_sha256'][:16]+'.html')
            if not raw.exists():continue
            page=VisualPage();page.feed(decode(raw.read_bytes(),None));page.finish()
            if not visual_heading(page) or foreign_article(page.title,record['name_zh']) or record['name_zh'] not in '\n'.join(t for _,t in page.lines):continue
            attempt.update(status='school_visual_page_read',identity_basis='exact confirmed main hostname, visible full MOE school name and dedicated visual heading')
            attempt.pop('detail',None);attempt.pop('error_type',None)
            title=next((h for h in page.headings if RESOURCE.search(h)),page.title.strip())
            special=bool(ANNIVERSARY.search(title))
            record['resources'].append(resource_entry(title,url,url,attempt['source_sha256'],special))
            for anchor in page.links:
                target=urllib.parse.urljoin(url,anchor['href']).split('#')[0];suffix=FILE.search(target) or FILE.search(anchor['label'])
                if safe_url(target) and not anchor['footer'] and suffix and (RESOURCE.search(anchor['label']) or re.search(r'手册|标志|LOGO',anchor['label'],re.I)):
                    record['resources'].append(resource_entry(anchor['label'],target,url,attempt['source_sha256'],special or bool(ANNIVERSARY.search(anchor['label'])),suffix[1].upper()))
            record['status']='verified_visual_resources';count+=1
    print('Recovered %s generic-title school visual pages on confirmed main hosts.'%count)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers',type=int,default=12);parser.add_argument('--limit',type=int)
    parser.add_argument('--resume',action='store_true');parser.add_argument('--import-only',action='store_true')
    parser.add_argument('--collect-only',action='store_true')
    parser.add_argument('--recover-confirmed-host',action='store_true',help='Recheck cached identity gaps on the exact confirmed main hostname')
    args=parser.parse_args()
    scope={r['name_zh']:r['school_code'] for r in csv.DictReader((ROOT/'data/universities-scope-2026.csv').open(encoding='utf-8-sig'))}
    if args.import_only or (args.resume and LEADS.exists()):directory=json.loads(LEADS.read_text())
    else:
        final,body,charset,mime=fetch(DIRECTORY,DIRECTORY,Policy())
        directory=dict(source=final,source_sha256=hashlib.sha256(body).hexdigest(),checked_at=TODAY,role='URL discovery only; no directory prose mirrored',schools=directory_leads(body,charset,scope))
        LEADS.write_text(json.dumps(directory,ensure_ascii=False,indent=2)+'\n')
    paths={p.parent.name:p for p in (ROOT/'universities').glob('*/*/profile.yaml')}
    profiles={code:yaml.load(p.read_text(),Loader=yaml.CSafeLoader) for code,p in paths.items()}
    leads=[r for r in directory['schools'] if r['visual_leads'] or r['download_leads']]
    # Schools without graphics and specific downloads take precedence.
    leads.sort(key=lambda r:(bool(profiles[r['school_code']]['visual']['logo_assets']),not bool(r['download_leads']),r['school_code']))
    if args.limit:leads=leads[:args.limit]
    records={r['school_code']:r for r in map(json.loads,OUTPUT.read_text().splitlines())} if OUTPUT.exists() else {}
    def save():
        temp=OUTPUT.with_suffix('.jsonl.tmp');temp.write_text(''.join(json.dumps(records[c],ensure_ascii=False)+'\n' for c in sorted(records)));temp.replace(OUTPUT)
    if not args.import_only:
        pending=[r for r in leads if not args.resume or r['school_code'] not in records]
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures={pool.submit(collect,r,profiles[r['school_code']]):r['school_code'] for r in pending}
            for n,future in enumerate(concurrent.futures.as_completed(futures),1):
                code=futures[future];records[code]=future.result()
                if n%25==0:save();print('Collected',n,'/',len(pending),flush=True)
        save()
    if args.collect_only:return
    if args.recover_confirmed_host:recover_cached_pages(records,profiles)
    resources=assets=0
    for code,record in records.items():
        # Apply revised heading criteria to cached pages before importing.
        accepted={a.get('source_url') for a in record['pages'] if a.get('status')=='school_visual_page_read' and RESOURCE.search(a.get('title',''))}
        for attempt in record['pages']:
            if attempt.get('status')!='school_visual_page_read' or attempt.get('source_url') in accepted:continue
            raw=ROOT/'tmp/visual-directory'/(code+'-'+attempt['source_sha256'][:16]+'.html')
            if raw.exists():
                page=VisualPage();page.feed(decode(raw.read_bytes(),None));page.finish()
                if visual_heading(page):accepted.add(attempt['source_url'])
                else:attempt.update(status='access_or_identity_gap',detail='no_visual_resource_heading')
        record['resources']=[e for e in record['resources'] if e['source'] in accepted]
        record['assets']=[a for a in record['assets'] if a['source'] in accepted]
        record['status']='verified_visual_resources' if accepted else record['status'] if record['status']=='school_host_not_confirmed' else 'no_verified_visual_page'
        # Reload facts before mutation so collection never overwrites newer work.
        p=yaml.safe_load(paths[code].read_text());before=json.dumps(p,sort_keys=True)
        for entry in record['resources']:
            entry['title']=re.sub(r'\s+',' ',entry['title']).strip()
            # Reclassify older receipts too: a school emblem introduction is
            # useful, but is not necessarily a downloadable VI manual.
            entry['kinds']=resource_entry(entry['title'],entry['url'],entry['source'],entry['source_sha256'],'校庆专用' in entry['kinds'],entry['formats'][0])['kinds']
            resources+=upsert(p['visual']['vi_resources'],entry,lambda x:(x['url'],x['source']))
            if entry['formats']==['HTML'] and '校庆专用' not in entry['kinds']:
                field='resources.official_templates_url' if TEMPLATE.search(entry['title']) else 'visual.vi_url'
                put_fact(p,field,entry['url'],dict(source=entry['source'],verified='auto',checked_at=TODAY),basis=entry['note'])
        assets+=len(record['assets']);apply_record(p,record)
        if json.dumps(p,sort_keys=True)!=before:paths[code].write_text(yaml.safe_dump(p,allow_unicode=True,sort_keys=False,width=100))
    save()
    print('Imported %d visual resource entries and %d inspected asset candidates across %d schools.'%(resources,assets,len(records)))


if __name__=='__main__':main()
