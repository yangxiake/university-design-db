#!/usr/bin/env python3
"""Read school overview pages and extract bounded facts with counting bases.

No source prose is republished. Summaries are composed from structured facts;
undated and approximate statistics remain labelled, not dated by fetch time.
"""
import argparse
import concurrent.futures
import datetime as dt
import hashlib
import json
import pathlib
import re
import urllib.parse

import yaml

from collect_official_extensions import Page, decode, fetch
from research_all_schools import Policy, foreign_article, same_school
from profile_extensions import put_fact, upsert, empty_fact

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUTPUT = ROOT / 'data/review/official-overviews-2026.jsonl'
TODAY = dt.date.today().isoformat()
NUM = r'(?P<qual>约|近|超过|超|逾|达)?(?P<num>\d[\d,，]*(?:\.\d+)?)(?P<scale>万)?(?P<tail>余|多|左右|以上|近)?'
STUDENTS = re.compile(r'(?P<label>(?:各类)?(?:全日制)?(?:普通)?(?:在校(?:学生|本专科生|本科生|生)|在学学生|本科(?:学生|生)))\s*(?:总数|人数|规模)?\s*(?:为|有|共|达|计|：|:)?\s*' + NUM + r'\s*(?:名|人)')
FACULTY = re.compile(r'(?P<label>在职教职(?:员工|工)|教职(?:员工|工)|专任教师)\s*(?:总数|人数)?\s*(?:为|有|共|达|计|：|:)?\s*' + NUM + r'\s*(?:名|人)')
AREA = re.compile(r'(?P<label>(?:学校|校园)?(?:总)?占地(?:总)?面积)\s*(?:为|共|达|：|:)?\s*' + NUM + r'\s*(?P<unit>平方公里|平方米|公顷|亩)')
DEGREES = re.compile(r'(?P<label>(?:专业学位类别)?(?:一级学科)?(?:专业)?(?:博士|硕士)(?:专业)?学位(?:一级学科)?授权(?:点|学科)|(?:博士|硕士)(?:学位授权)?一级学科)\s*(?:为|有|共|达|：|:)?\s*(?P<n>\d+)\s*(?:个|项)')
DATE = re.compile(r'(?:截至|截止|统计时间|数据截至|数据截止|数据统计截至)[：:\s]*(20\d{2})(?:[年./-](\d{1,2})(?:[月./-](\d{1,2})日?)?月?)?')
OVERVIEW_LINK=re.compile(r'(?:[\u4e00-\u9fff]{1,5})?(?:简介|概况|概览)|关于[\u4e00-\u9fff]{2,5}|学校基本情况')


def amount(match):
    value = float(match['num'].replace(',', '').replace('，', '')) * (10000 if match['scale'] else 1)
    return int(value) if value.is_integer() else value


def date_for(paragraph, body):
    # A date within the same paragraph belongs to this claim. A single explicit
    # page-wide census date can be used; publication/history dates cannot.
    matches = list(DATE.finditer(paragraph))
    if not matches:
        all_dates = list(DATE.finditer(body))
        unique = {m.group(0) for m in all_dates}
        if len(unique) == 1: matches = all_dates[:1]
    if not matches: return 'undated', '页面未标注此项统计日期；采集日不等于统计日'
    m = matches[-1]
    year, month, day = int(m[1]), int(m[2] or 1), int(m[3] or 1)
    try: date = dt.date(year, month, day)
    except ValueError: return 'undated', '统计日期格式无效'
    if date > dt.date.today(): return 'undated', '页面标注日期晚于采集日，未采用'
    value = str(year) + ('-%02d' % month if m[2] else '') + ('-%02d' % day if m[3] else '')
    return value, m.group(0)


def valid_overview(name, title, lines):
    if foreign_article(title, name): return False
    rest = title.replace(name, '').replace('学院简介', '').replace('学院概况', '')
    if re.search(r'学院|学部|附属|中学|小学|招标|招聘|新闻', rest): return False
    body = '\n'.join(lines)
    # Require a narrative self-identification, not merely the school footer.
    escaped = re.escape(name).replace(r'\（', '[（(]').replace(r'\）', '[）)]')
    return bool(re.search(escaped + r'(?:[（(][^）)]{0,150}[）)])?(?:简称[^。]{0,25})?[，,是为坐位始成创]', body)) and len(body) > 150


def extract(name, title, lines, source):
    if not valid_overview(name, title, lines): return [], []
    body = '\n'.join(lines)
    claims = []; campuses = []
    for field, pattern, lower, upper in [
        ('statistics.student_count', STUDENTS, 100, 500000),
        ('statistics.faculty_count', FACULTY, 30, 50000),
        ('statistics.campus_area_hectares', AREA, 1, 20000),
    ]:
        candidates = []
        for line in lines:
            if len(line) < 30: continue
            for match in pattern.finditer(line):
                # Past periods, individual colleges and construction plans are
                # not current whole-school counts. An explicit local basis is
                # retained even when only本科生/专任教师 is available.
                sentence = re.split(r'[。！？；]', line[:match.start()])[-1]
                if re.search(r'曾有|当时|建校初|创办初|规划|拟建|计划|预计|将达到|附属医院|附属学校|新增|增加|招收', sentence[-50:]): continue
                if re.search(r'一期工程|二期工程|按照.{0,12}(?:在校|办学).{0,6}规模|可容纳|设计(?:容量|规模)',sentence[-90:]):continue
                if field.endswith('hectares') and re.search(r'新校区|新区|校区位于|建设[^，,]*校区',sentence[-60:]): continue
                # A留学生 paragraph can contain本科生 subcounts. Those are not
                # the school's本科人数. Reject nested subgroup statements.
                if field.endswith('student_count') and re.search(r'(?:留学生|成人学生|继续教育学生)[^。；]{0,60}[（(]',sentence[-90:]): continue
                value = amount(match)
                basis = match['label']
                local=re.split(r'[，,]',sentence)[-1][-22:]
                if field.endswith('student_count'):
                    scope=re.search(r'(全日制本硕博|全日制本专科|普通本专科|在校研究生和|学历继续教育|成人教育|高职专科|本专科|留学生)(?:等)?$',local)
                    if scope:basis=scope[1]+basis
                if field.endswith('hectares'):
                    unit = match['unit']; factor = {'平方米': 0.0001, '平方公里': 100, '公顷': 1, '亩': 1/15}[unit]
                    value = round(value * factor, 6)
                    basis += '；原单位' + unit + '，换算公顷（1公顷=15亩=10000平方米）'
                if not lower <= value <= upper: continue
                raw = match.group(0)
                approximate = bool(match['qual'] or match['tail'])
                basis += '；' + ('近似/下界数，保留原标注：' if approximate else '原标注：') + raw
                as_of, date_basis = date_for(line, body)
                basis += '；' + date_basis
                rank = 0
                if field.endswith('student_count'):
                    rank = 2 if '本科' in match['label'] else 0
                if field.endswith('faculty_count'):
                    rank = 1 if match['label'] == '专任教师' else 0
                candidates.append(dict(field=field, value=value, source=source, basis=basis, source_as_of=as_of,
                                       date_basis=date_basis, approximate=approximate, original_notation=raw, rank=rank))
        if candidates:
            best = min(x['rank'] for x in candidates)
            chosen = [x for x in candidates if x['rank'] == best]
            # Distinct counts with the same basis stay in the ledger for review.
            values = {(x['value'], x['source_as_of'], x['original_notation']) for x in chosen}
            if len(values) == 1:
                claim = chosen[0]; claim.pop('rank'); claims.append(claim)
    degrees = []
    for line in lines:
        if re.search(r'曾有|当时|规划|拟建|计划|预计|新增|获批', line[:80]): continue
        for match in DEGREES.finditer(line):
            as_of, basis = date_for(line, body)
            text = '%s：%s个；统计时间%s' % (match['label'], match['n'], as_of)
            if text not in degrees: degrees.append(text)
    if degrees:
        claims.append(dict(field='academics.degree_authorizations', value=degrees[:12], source=source,
                           basis='官网简介列出的授权点数量及层次，非全部授权学科名单；未标注日期用undated'))
    for line in lines:
        # Only explicit lists or independently suffixed校区 names; no invented
        # split of addresses into campus names.
        for m in re.finditer(r'(?:现有|拥有|设有|学校有|(?:^|[。；，,])有|分为|建成)((?:[\u4e00-\u9fff]{2,12}[、，,和及]){1,7}[\u4e00-\u9fff]{2,12}?)(?:等)?([一二三四五六七八九十两\d]+)(?:个|大|处)?(?:主要)?校区', line):
            if re.search(r'规划|拟建|计划|历史上|曾经',re.split(r'[。；，,]',line[:m.start()])[-1][-20:]):continue
            names = [x.strip().removesuffix('校区') for x in re.split(r'[、，,和及]', m[1])]
            if any(re.search(r'管理|已建|建设|工业|原属|总公司|正在|面积', x) for x in names): continue
            for campus in names:
                if 2 <= len(campus) <= 10 and not re.search(r'学校|大学|学院|包括|分别|位于|拥有|目前|全日制', campus):
                    campuses.append(dict(name=campus+'校区', address=None, coordinates=None, source=source,
                                         basis='官网简介明确列出的校区；地址/坐标未推断', verified='auto', checked_at=TODAY))
        for m in re.finditer(r'(?:^|[，,。；\s])([\u4e00-\u9fff]{2,10}校区)[（(:：]\s*([^。；\n]{8,90})', line):
            address = m[2].split('邮编')[0].strip(' ）)；;，,')
            if re.search(r'(?:路|街|道|镇|村).*(?:号|校区)|\d+号', address):
                campuses.append(dict(name=m[1], address=address, coordinates=None, source=source,
                                     basis='官网简介校区地址明确标注', verified='auto', checked_at=TODAY))
    return claims, list({(c['name'],c['address']):c for c in campuses}.values())


def summary(profile, claims, campuses):
    # A fresh composition from facts, no copied introductory paragraph.
    parts = []
    i = profile['identity']; parts.append('%s位于%s%s，主管部门为%s。' % (i['name_zh'], i['province'], '' if i['province']==i['city'] else i['city'], i['authority']))
    for claim in claims:
        if claim['field'].startswith('statistics.'):
            label = claim['basis'].split('；')[0]
            value = claim['original_notation']
            date = claim['source_as_of']
            parts.append('官网列示%s（%s）。' % (value, '统计时间'+date if date!='undated' else '统计日期未注明'))
    if campuses: parts.append('简介列出%s。' % '、'.join(dict.fromkeys(c['name'] for c in campuses)))
    if not claims and not campuses: return None
    return ''.join(parts)[:480]


def collect(profile, previous):
    i = profile['identity']; home = i['official_website'].get('value')
    record = dict(school_code=i['school_code'], name_zh=i['name_zh'], checked_at=TODAY, home=home,
                  pages=[], claims=[], campuses=[], status='no_confirmed_homepage', collector_revision=1)
    if not home: return record
    policy = Policy(); urls = []
    for page in previous.get('pages', []):
        if page['kind']=='overview':
            url=page.get('source_url', page['requested_url'])
            if same_school(url, home) and url not in urls: urls.append(url)
    # The homepage navigation supplies different entry URLs when old URLs fail.
    def read(url):
        attempt=dict(requested_url=url, status='access_gap');record['pages'].append(attempt)
        try:
            final, body, charset, mime = fetch(url, home, policy)
            if mime not in {'text/html','application/xhtml+xml'}: raise ValueError('not_html')
            page=Page();page.feed(decode(body,charset));page.finish()
            attempt.update(source_url=final,title=page.title,sha256=hashlib.sha256(body).hexdigest(),status='read')
            # Raw HTML stays in ignored research cache, never public source.
            cache=ROOT/'tmp/overviews'/i['school_code'];cache.mkdir(parents=True,exist_ok=True)
            (cache/(attempt['sha256']+'.html')).write_bytes(body)
            return page
        except Exception as e:
            attempt.update(error_type=type(e).__name__,detail=str(e)[:120]);return None
    used=set();home_scanned=False
    for turn in range(4):
        if not any(u not in used for u in urls) and not home_scanned:
            home_scanned=True
            page=read(home)
            if page:
                urls += [urllib.parse.urljoin(home,a['href']) for a in page.links if OVERVIEW_LINK.fullmatch(re.sub(r'\s+','',a['label'])) and same_school(urllib.parse.urljoin(home,a['href']),home)]
        url=next((u for u in urls if u not in used),None)
        if not url: break
        used.add(url);page=read(url)
        if page:
            lines=[re.sub(r'\s+','',t) for foot,t in page.lines if not foot and len(t)>20]
            if valid_overview(i['name_zh'],page.title,lines):
                final=record['pages'][-1]['source_url']
                claims,campuses=extract(i['name_zh'],page.title,lines,final)
                record['claims']=claims;record['campuses']=campuses;record['status']='researched_partial'
                text=summary(profile,claims,campuses)
                if text:
                    record['claims'].append(dict(field='overview.summary_zh',value=text,source=final,
                        basis='根据教育部身份表与官网结构化统计/校区事实重新组织的短摘要；不复制简介原文',source_as_of='mixed'))
                if claims or campuses: break
            # A general overview index may link to the actual overview article.
            urls += [urllib.parse.urljoin(url,a['href']) for a in page.links if OVERVIEW_LINK.fullmatch(re.sub(r'\s+','',a['label'])) and same_school(urllib.parse.urljoin(url,a['href']),home)]
        else:
            parsed=urllib.parse.urlparse(url)
            if record['pages'][-1].get('detail')!='robots_disallowed':
                alt=parsed._replace(scheme='http' if parsed.scheme=='https' else 'https').geturl()
                if alt not in urls:urls.append(alt)
    if record['status']!='researched_partial':record['status']='overview_access_or_identity_gap'
    return record


def apply_record(profile, record):
    sources={p.get('source_url') for p in record['pages']}
    for dotted in ('statistics.student_count','statistics.faculty_count','statistics.campus_area_hectares','overview.summary_zh','academics.degree_authorizations'):
        group,key=dotted.split('.');current=profile[group][key]
        owned=(current.get('collector')=='official_overview' or ('original_notation' in current and 'date_basis' in current)
               or current.get('basis','').startswith(('根据教育部身份表与官网结构化','官网简介列出的授权点数量及层次')))
        if current.get('verified')=='auto' and current.get('source') in sources and owned:profile[group][key]=empty_fact()
    profile['location']['campuses']=[c for c in profile['location']['campuses'] if c.get('verified')=='human'
        or c.get('source') not in sources or not c.get('basis','').startswith('官网简介')]
    for claim in record['claims']:
        metadata=dict(source=claim['source'],source_type='official_website',verified='auto',checked_at=record['checked_at'],collector='official_overview')
        extra={k:v for k,v in claim.items() if k not in {'field','value','source'}}
        put_fact(profile,claim['field'],claim['value'],metadata,**extra)
    for campus in record['campuses']:
        upsert(profile['location']['campuses'],campus,lambda x:(x['name'],x['source']))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers',type=int,default=12);parser.add_argument('--limit',type=int)
    parser.add_argument('--resume',action='store_true');parser.add_argument('--import-only',action='store_true');parser.add_argument('--collect-only',action='store_true')
    parser.add_argument('--reparse-cache',action='store_true',help='Re-extract the ignored cached HTML without new requests')
    parser.add_argument('--retry-missing',action='store_true',help='Try alternate homepage navigation for schools with no overview claims')
    parser.add_argument('--school-code',action='append',help='Collect only these schools; preserve the rest of the ledger')
    args=parser.parse_args()
    # This export is a read-only seed. Imports reload the current canonical YAML.
    profiles=[json.loads(s) for s in (ROOT/'indexes/profiles.jsonl').read_text().splitlines()]
    old={r['school_code']:r for r in map(json.loads,(ROOT/'data/review/school-research-2026.jsonl').read_text().splitlines())}
    records={r['school_code']:r for r in map(json.loads,OUTPUT.read_text().splitlines())} if OUTPUT.exists() else {}
    pending=[p for p in profiles if not args.resume or p['identity']['school_code'] not in records]
    if args.retry_missing:pending=[p for p in profiles if not records.get(p['identity']['school_code'],{}).get('claims') and p['identity']['official_website'].get('value')]
    if args.school_code:pending=[p for p in pending if p['identity']['school_code'] in args.school_code]
    if args.limit:pending=pending[:args.limit]
    def save():
        temp=OUTPUT.with_suffix('.tmp');temp.write_text(''.join(json.dumps(records[c],ensure_ascii=False)+'\n' for c in sorted(records)),encoding='utf-8');temp.replace(OUTPUT)
    if args.reparse_cache:
        by_code={p['identity']['school_code']:p for p in profiles}
        for code,record in records.items():
            if args.school_code and code not in args.school_code:continue
            record['claims']=[];record['campuses']=[]
            for attempt in record['pages']:
                cache=ROOT/'tmp/overviews'/code/(attempt.get('sha256','')+'.html')
                if not cache.is_file():continue
                page=Page();page.feed(decode(cache.read_bytes(),None));page.finish()
                lines=[re.sub(r'\s+','',t) for foot,t in page.lines if not foot and len(t)>20]
                claims,campuses=extract(record['name_zh'],page.title,lines,attempt['source_url'])
                if claims or campuses:
                    record['claims']=claims;record['campuses']=campuses
                    text=summary(by_code[code],claims,campuses)
                    if text:record['claims'].append(dict(field='overview.summary_zh',value=text,source=attempt['source_url'],
                        basis='根据教育部身份表与官网结构化统计/校区事实重新组织的短摘要；不复制简介原文',source_as_of='mixed'))
                    break
        save()
    elif not args.import_only:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures={pool.submit(collect,p,old.get(p['identity']['school_code'],{})):p['identity']['school_code'] for p in pending}
            for n,f in enumerate(concurrent.futures.as_completed(futures),1):
                code=futures[f];record=f.result()
                previous_pages=records.get(code,{}).get('pages',[])
                record['pages']=list({json.dumps(p,sort_keys=True):p for p in previous_pages+record['pages']}.values())
                records[code]=record
                if n%40==0:save();print('Overviews %s/%s; facts %s; campus entries %s'%(n,len(pending),sum(len(r['claims']) for r in records.values()),sum(len(r['campuses']) for r in records.values())),flush=True)
        save()
    if args.collect_only:return
    changed=0
    for path in (ROOT/'universities').glob('*/*/profile.yaml'):
        if args.school_code and path.parent.name not in args.school_code:continue
        profile=yaml.safe_load(path.read_text());record=records.get(profile['identity']['school_code'])
        if not record:continue
        before=json.dumps(profile,sort_keys=True,ensure_ascii=False);apply_record(profile,record)
        if before!=json.dumps(profile,sort_keys=True,ensure_ascii=False):
            path.write_text(yaml.safe_dump(profile,allow_unicode=True,sort_keys=False,width=100),encoding='utf-8');changed+=1
    print('Imported overview facts: %s profiles changed.'%changed)


if __name__=='__main__':main()
