#!/usr/bin/env python3
"""Index source-labelled PPT downloads from confirmed school visual pages.

Read public HTML only. Never run upstream skills or download/execute templates.
Department templates retain their department scope and publisher.
"""
import argparse
import csv
import concurrent.futures
import datetime as dt
import hashlib
import html.parser
import json
import pathlib
import re
import urllib.parse
import yaml
from collect_official_extensions import fetch, decode
from collect_visual_directory import VisualPage, page_identity, resource_entry, FILE
from research_all_schools import Policy, same_school
from discover_official_pages import safe_url
from profile_extensions import put_fact, upsert

ROOT=pathlib.Path(__file__).resolve().parents[2]
TODAY=dt.date.today().isoformat()
PPT=re.compile(r'PPT\s*模[板版]|PowerPoint\s*模[板版]|演示文[稿档].{0,8}模[板版]|(?:20\d{2}版|教学版|通用版)\s*PPT',re.I)
OUTPUT=ROOT/'data/review/ppt-resources-2026.jsonl'


class TemplateBlocks(html.parser.HTMLParser):
    """Bind a generic download anchor to its small surrounding template card."""
    def __init__(self):super().__init__();self.blocks=[];self.links=[];self.anchor=None
    def handle_starttag(self,tag,attrs):
        if tag in {'div','p','li','td'}:self.blocks.append(dict(tag=tag,text=[],links=[]))
        if tag=='a':self.anchor=dict(href=dict(attrs).get('href') or '',label=[])
    def handle_data(self,data):
        for block in self.blocks:block['text'].append(data)
        if self.anchor is not None:self.anchor['label'].append(data)
    def handle_endtag(self,tag):
        if tag=='a' and self.anchor is not None:
            a=dict(href=self.anchor['href'],label=''.join(self.anchor['label']).strip(),footer=False)
            for block in self.blocks:block['links'].append(a)
            self.anchor=None
        if tag in {'div','p','li','td'}:
            for i in range(len(self.blocks)-1,-1,-1):
                if self.blocks[i]['tag']!=tag:continue
                block=self.blocks[i];del self.blocks[i:]
                text=re.sub(r'\s+',' ',''.join(block['text'])).strip()
                download=[a for a in block['links'] if re.fullmatch(r'(?:点击)?下载',a['label'])]
                if len(text)<=220 and PPT.search(text) and len(download)==1:
                    self.links.append(dict(download[0],label=re.sub(r'^(?:点击)?下载\s*','',text)))
                break


def entries(page,source,sha,spec):
    found=[]
    text='\n'.join(t for _,t in page.lines)
    for a in page.links+getattr(page,'template_links',[]):
        label=a['label'].strip();url=urllib.parse.urljoin(source,a['href']).split('#')[0]
        if not safe_url(url) or url==source or a['footer'] or not PPT.search(label):continue
        suffix=FILE.search(url) or FILE.search(label)
        fmt=suffix[1].upper() if suffix else '未知（未读取目标）'
        if fmt not in {'PPT','PPTX','ZIP','RAR','7Z','未知（未读取目标）'}:continue
        entry=resource_entry(label,url,source,sha,False,fmt)
        entry.update(kinds=['PPT模板' if spec['use_scope']=='school' else '院系PPT模板'],
                     publisher=spec['publisher'],use_scope=spec['use_scope'],content_read=False,download_status='indexed_not_fetched',
                     access_requirement='已读取校方发布页；附件目标尚未读取，格式按原链接文件名，动态端点或网盘可能需要登录/提取码',
                     note='发布范围：'+('学校通用' if spec['use_scope']=='school' else spec['publisher'])+'。仅索引入口；未编译、未打开模板，不保证当前可下载或模板中字体与图形的独立授权。')
        year=re.search(r'(20\d{2})(?:年(?:度)?|版)',label)
        if year:entry['edition_year']=int(year[1])
        found.append(entry)
    if found or PPT.search(page.title):
        root=resource_entry(spec['publisher']+' PPT模板发布/下载页',source,source,sha)
        root.update(kinds=['PPT模板' if spec['use_scope']=='school' else '院系PPT模板'],publisher=spec['publisher'],
                    use_scope=spec['use_scope'],content_read=True,download_status='page_read',
                    access_requirement='校方公开HTML页已读取；页面内附件或外部下载目标另行索引',
                    note='发布范围：'+('学校通用' if spec['use_scope']=='school' else spec['publisher'])+'；按发布页说明使用。')
        found.insert(0,root)
    return found


def collect(spec):
    result=dict(school_code=spec['school_code'],name_zh=spec['name_zh'],checked_at=TODAY,pages=[],resources=[],status='no_confirmed_ppt_resources')
    policy=Policy();queue=[spec['url']];seen=set()
    while queue and len(seen)<4:
        url=queue.pop(0)
        if url in seen:continue
        seen.add(url);attempt=dict(requested_url=url);result['pages'].append(attempt)
        try:
            final,body,charset,mime=fetch(url,spec['url'],policy)
            if mime not in {'text/html','application/xhtml+xml'}:raise ValueError('attachment_or_not_html')
            html=decode(body,charset);page=VisualPage();page.feed(html);page.finish()
            blocks=TemplateBlocks();blocks.feed(html);page.template_links=blocks.links
            full_name_in_text=spec['name_zh'] in '\n'.join(t for _,t in page.lines)
            # Curated pages may have a generic title. The already confirmed
            # school host plus its full name in visible text gives a second
            # route; this exception does not apply to uncurated directory URLs.
            confirmed_host=spec.get('confirmed_home') and same_school(final,spec['confirmed_home'])
            if not page_identity(spec['name_zh'],page) and not (confirmed_host and full_name_in_text):raise ValueError('school_identity_gap')
            sha=hashlib.sha256(body).hexdigest();attempt.update(status='school_page_read',source=final,title=page.title[:150],source_sha256=sha)
            result['resources']+=entries(page,final,sha,spec)
            for anchor in page.links:
                target=urllib.parse.urljoin(final,anchor['href']).split('#')[0]
                if PPT.search(anchor['label']) and same_school(target,spec['url']) and not FILE.search(target) and not FILE.search(anchor['label']) and not re.search('download|downcontent',target,re.I):queue.append(target)
        except Exception as exc:
            attempt.update(status='access_or_identity_gap',error_type=type(exc).__name__,detail=str(exc)[:160])
            if isinstance(exc,OSError):
                p=urllib.parse.urlparse(url);alternate=p._replace(scheme='http' if p.scheme=='https' else 'https').geturl()
                if alternate not in seen:queue.insert(0,alternate)
    result['resources']=list({(e['url'],e['source']):e for e in result['resources']}.values())
    if result['resources']:result['status']='confirmed_ppt_resources'
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers',type=int,default=8);parser.add_argument('--import-only',action='store_true');args=parser.parse_args()
    scope={r['name_zh']:r['school_code'] for r in csv.DictReader((ROOT/'data/universities-scope-2026.csv').open(encoding='utf-8-sig'))}
    paths={p.parent.name:p for p in (ROOT/'universities').glob('*/*/profile.yaml')}
    specs=yaml.safe_load((ROOT/'data/review/ppt-source-leads-2026.yaml').read_text())
    specs=[dict(s,school_code=scope[s['name_zh']],confirmed_home=yaml.safe_load(paths[scope[s['name_zh']]].read_text())['identity']['official_website'].get('value')) for s in specs]
    records={r['school_code']:r for r in map(json.loads,OUTPUT.read_text().splitlines())} if OUTPUT.exists() else {}
    if not args.import_only:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            for r in pool.map(collect,specs):records[r['school_code']]=r
    # Read already confirmed directory pages for additional explicitly named
    # templates. These sources remain school-level unless a department is named.
    directory=ROOT/'data/review/visual-directory-2026.jsonl'
    if directory.exists():
        for r in map(json.loads,directory.read_text().splitlines()):
            for attempt in r['pages']:
                if attempt.get('status')!='school_visual_page_read':continue
                source=attempt['source_url'];sha=attempt['source_sha256']
                raw=ROOT/'tmp/visual-directory'/(r['school_code']+'-'+sha[:16]+'.html')
                if not raw.exists():continue
                html=decode(raw.read_bytes(),None);page=VisualPage();page.feed(html);page.finish()
                blocks=TemplateBlocks();blocks.feed(html);page.template_links=blocks.links
                if not page_identity(r['name_zh'],page):continue
                # Never promote a department site's template as school-wide.
                if re.search(r'学院|学部|研究所',page.title.replace(r['name_zh'],'')):continue
                spec=dict(publisher=r['name_zh']+'官网视觉资源页',use_scope='school')
                found=entries(page,source,sha,spec)
                if found:
                    current=records.setdefault(r['school_code'],dict(school_code=r['school_code'],name_zh=r['name_zh'],checked_at=TODAY,pages=[],resources=[],status='confirmed_ppt_resources'))
                    for e in found:upsert(current['resources'],e,lambda x:(x['url'],x['source']))
    added=0
    for code,r in records.items():
        p=yaml.safe_load(paths[code].read_text())
        for e in r['resources']:
            added+=upsert(p['visual']['vi_resources'],e,lambda x:(x['url'],x['source']))
            if e['use_scope']=='school' and e['formats']==['HTML']:
                meta=dict(source=e['source'],verified='auto',checked_at=TODAY)
                put_fact(p,'resources.official_templates_url',e['url'],meta,basis=e['note'])
                put_fact(p,'resources.official_template_publisher',e['publisher'],meta)
        if r['resources']:paths[code].write_text(yaml.safe_dump(p,allow_unicode=True,sort_keys=False,width=100))
    OUTPUT.write_text(''.join(json.dumps(records[c],ensure_ascii=False)+'\n' for c in sorted(records)))
    print('Indexed %s new PPT entries across %s school/department records.'%(added,sum(bool(r['resources']) for r in records.values())))


if __name__=='__main__':main()
