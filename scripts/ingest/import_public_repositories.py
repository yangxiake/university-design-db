#!/usr/bin/env python3
"""Import source-labelled community data; never execute upstream code or treat themes as official VI."""
import argparse,csv,datetime as dt,hashlib,json,pathlib,re,subprocess,urllib.parse
import yaml
import html
import html.parser
from research_all_schools import ROOT
from render_official import render

CONFIG=ROOT/'data/external/repositories.yaml'
CACHE=ROOT/'tmp/upstream'
TODAY=dt.date.today().isoformat()

def read_objects(body):
    """Also accept the upstream file's concatenated JSON objects, without eval/pickle."""
    decoder=json.JSONDecoder();result=[];body=body.strip()
    while body:
        value,n=decoder.raw_decode(body);result.extend(value if isinstance(value,list) else [value]);body=body[n:].lstrip()
    return result

def normalize(name):
    return re.sub(r'\s+','',name).replace('（','(').replace('）',')')

class DirectoryLinks(html.parser.HTMLParser):
    """Retain a plain-text institution prefix immediately before an anchor."""
    def __init__(self):
        super().__init__(); self.previous=''; self.anchor=None; self.links=[]
    def handle_starttag(self, tag, attrs):
        if tag=='a':
            self.anchor=dict(attrs); self.anchor['text']=''; self.anchor['prefix']=self.previous
    def handle_data(self, data):
        if self.anchor is not None:
            self.anchor['text']+=data
        else:
            self.previous=data
    def handle_endtag(self, tag):
        if tag=='a' and self.anchor is not None:
            self.links.append(self.anchor); self.anchor=None; self.previous=''

def directory_candidates(body, schools):
    parser=DirectoryLinks();parser.feed(body); result=[]
    for anchor in parser.links:
        name=normalize(anchor['text'])
        prefix=re.search(r'[\u4e00-\u9fff（）()]+$',anchor['prefix'].strip())
        combined=normalize(prefix.group(0)+name) if prefix else name
        school=schools.get(combined) or schools.get(name)
        if not school:continue
        urls=[]
        href=anchor.get('href','')
        if href.startswith(('https://','http://')):urls.append(href)
        for match in re.finditer(r'(?:https?://)?(?:www\.)?[A-Za-z0-9][A-Za-z0-9.-]*\.(?:edu\.cn|ac\.cn|com\.cn|cn|com)(?:/[^\s，。;]+)?',anchor.get('title','')):
            value=match.group(0)
            urls.append(value if value.startswith(('https://','http://')) else 'https://'+value)
        for url in dict.fromkeys(urls):result.append((school,url))
    return result

def checkout(repo):
    name=repo['repository']
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',name):raise ValueError('Invalid repository')
    path=CACHE/name.replace('/','__');CACHE.mkdir(parents=True,exist_ok=True)
    if not (path/'.git').exists():subprocess.run(['git','clone','--quiet','--depth','1','--filter=blob:none','--no-checkout','https://github.com/'+name+'.git',str(path)],check=True)
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=path,text=True).strip()
    if head!=repo['commit']:
        subprocess.run(['git','fetch','--quiet','--depth','1','origin',repo['commit']],cwd=path,check=True)
    return path

def read(path,commit,filename):
    return subprocess.check_output(['git','show',commit+':'+filename],cwd=path,text=True)

def main():
    with (ROOT/'data/universities-scope-2026.csv').open(encoding='utf-8-sig',newline='') as f:scope=list(csv.DictReader(f))
    schools={normalize(s['name_zh']):s for s in scope};config=yaml.safe_load(CONFIG.read_text());candidates=[];added=kept=0;resources=0
    overrides=ROOT/'data/review/official-site-overrides-2026.csv'
    with overrides.open(encoding='utf-8-sig',newline='') as f:reader=csv.DictReader(f);fields=reader.fieldnames;urls=list(reader)
    seen={(r['school_code'],r['candidate_url']) for r in urls};differences=[]
    for repo in config['repositories']:
        path=checkout(repo);sha=repo['commit'];base='https://github.com/'+repo['repository']+'/blob/'+sha+'/'
        if repo.get('directory_markdown'):
            body=read(path,sha,repo['directory_markdown'])
            leads=directory_candidates(body,schools)
            for school,website in leads:
                if (school['school_code'],website) in seen:continue
                row=dict.fromkeys(fields,'')
                row.update(school_code=school['school_code'],name_zh=school['name_zh'],candidate_url=website,
                           evidence_url=base+repo['directory_markdown'],
                           note='2026社区高校目录入口线索；仅链接事实，不镜像原文或完整目录；须访问并核对学校身份')
                urls.append(row);seen.add((school['school_code'],website))
            print('Community directory matched',len({school['school_code'] for school,url in leads}),'schools')
        if repo.get('website_leads'):
            body = read(path, sha, repo['website_leads'])
            # The old upstream JSON contains a trailing comma at the end of its array.
            body = re.sub(r",\s*]\s*$", "]", body)
            for record in read_objects(body):
                school = schools.get(normalize(record.get('name', '')))
                website = (record.get('website') or '').strip()
                if not school or not website.startswith(('https://', 'http://')):
                    continue
                if (school['school_code'], website) in seen:
                    continue
                row = dict.fromkeys(fields, '')
                row.update(school_code=school['school_code'], name_zh=school['name_zh'],
                           candidate_url=website, evidence_url=base+repo['website_leads'],
                           note='历史社区目录网址线索；没有许可声明，不镜像数据文件；须访问并核对学校身份')
                urls.append(row)
                seen.add((school['school_code'], website))
        if repo.get('career_directory'):
            body = read(path, sha, repo['career_directory']); selected = []
            for line in body.splitlines():
                match = re.match(r'\d+\.\s*([^\s-]+)\s*-.*?\]\((https?://[^)]+)\)', line)
                if not match:
                    continue
                name, website = match.groups(); website=website.strip(); school = schools.get(normalize(name))
                if not school:
                    continue
                host = urllib.parse.urlparse(website).hostname or ''
                options = [website]
                if host.endswith('.edu.cn'):
                    domain = '.'.join(host.split('.')[-3:])
                    options = ['https://www.'+domain+'/', 'https://'+domain+'/', website]
                selected.append(dict(school_code=school['school_code'], name_zh=school['name_zh'],
                                     career_url=website, homepage_candidates=options,
                                     source=base+repo['career_directory']))
                for option in options:
                    if (school['school_code'], option) in seen:
                        continue
                    row = dict.fromkeys(fields, '')
                    row.update(school_code=school['school_code'], name_zh=school['name_zh'],
                               candidate_url=option, evidence_url=base+repo['career_directory'],
                               note='MIT社区高校就业目录；首页为推导候选，须访问并核对完整校名')
                    urls.append(row); seen.add((school['school_code'], option))
            folder=ROOT/'data/external'/repo['repository'].replace('/','__'); folder.mkdir(parents=True,exist_ok=True)
            (folder/'matched-career-links.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in selected))
            (folder/'LICENSE').write_text(read(path,sha,'LICENSE'))
            (folder/'SOURCE.yaml').write_text(yaml.safe_dump(dict(repository=repo['repository'],commit=sha,path=repo['career_directory'],license=repo['license'],matched_records=len(selected),imported_at=TODAY),allow_unicode=True,sort_keys=False))
        if repo.get('dataset'):
            if repo['license']!='MIT':raise ValueError('Dataset redistribution requires configured compatible license')
            text=read(path,sha,repo['dataset']);records=read_objects(text)
            selected=[]
            for r in records:
                name=r.get(repo['name_key'],'');school=schools.get(normalize(name))
                if not school:continue
                english=r.get(repo['english_key']);website=(r.get(repo['website_key']) or '').strip()
                selected.append(dict(school_code=school['school_code'],upstream_name=name,name_en=english,website_candidate=website,source=base+repo['dataset'],upstream_commit=sha,source_as_of=repo.get('data_as_of')))
                if website.startswith(('https://','http://')) and (school['school_code'],website) not in seen:
                    row=dict.fromkeys(fields,'');row.update(school_code=school['school_code'],name_zh=school['name_zh'],candidate_url=website)
                    if 'evidence_url' in row:row['evidence_url']=base+repo['dataset']
                    if 'note' in row:row['note']='社区库网址候选；须另行访问并检查学校身份'
                    urls.append(row);seen.add((school['school_code'],website))
                pp=ROOT/'universities'/school['province']/school['school_code']/'profile.yaml';p=yaml.safe_load(pp.read_text());fact=p['identity']['name_en']
                if not isinstance(english,str) or not re.fullmatch(r"[A-Za-z][A-Za-z ,().&’'/-]{5,130}",english) or not re.search(r'University|College|Institute|Academy|Conservatory',english,re.I):continue
                if p['research'].get('status')=='reviewed':
                    continue
                if fact['availability']=='unresearched':
                    fact.update(value=english.strip(),source=base+repo['dataset'],verified='auto',checked_at=TODAY,availability='found',search_sources=[],source_type='community_dataset',upstream_repository=repo['repository'],upstream_commit=sha,upstream_record_name=name,upstream_license=repo['license'],source_as_of=repo.get('data_as_of'),note='公开社区数据补充；未认定为校方核准的现行英文名。上游数据版本见source_as_of，本轮不要求人工签核。')
                    p['research'].update(status='auto_collected',checked_at=TODAY);pp.write_text(yaml.safe_dump(p,allow_unicode=True,sort_keys=False,width=100));added+=1
                else:
                    kept+=1
                    clean=lambda v:re.sub(r"[\s,’'&.-]",'',str(v)).lower()
                    if fact['availability']=='found' and clean(fact['value'])!=clean(english):differences.append(dict(school_code=school['school_code'],name_zh=school['name_zh'],field='identity.name_en',recorded_value=fact['value'],candidate_value=english,source=base+repo['dataset'],status='community_difference_existing_value_preserved'))
            folder=ROOT/'data/external'/repo['repository'].replace('/','__');folder.mkdir(parents=True,exist_ok=True)
            (folder/'matched-records.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in selected))
            (folder/'LICENSE').write_text(read(path,sha,repo.get('license_file','LICENSE')))
            (folder/'SOURCE.yaml').write_text(yaml.safe_dump({'repository':repo['repository'],'commit':sha,'path':repo['dataset'],'sha256':hashlib.sha256(text.encode()).hexdigest(),'license':repo['license'],'matched_records':len(selected),'data_as_of':repo.get('data_as_of'),'imported_at':TODAY},allow_unicode=True,sort_keys=False))
            candidates.extend(selected)
        for code in repo.get('school_codes',[]):
            school=next(s for s in scope if s['school_code']==code);pp=ROOT/'universities'/school['province']/code/'profile.yaml';p=yaml.safe_load(pp.read_text())
            entry=dict(title=repo['title'],url='https://github.com/'+repo['repository'],source=base+repo.get('readme','README.md'),publisher=repo['repository'].split('/')[0],kind=repo['kind'],official=False,license=repo.get('license'),commit=sha,verified='auto',checked_at=TODAY,usage_note=repo.get('usage_note','社区项目；按上游说明及材料权利人的规则使用。'))
            if repo.get('palette'):entry['palette']=repo['palette']
            items=p['resources'].setdefault('community_resources',[])
            previous=next((index for index,item in enumerate(items) if item['url']==entry['url']),None)
            if previous is None:
                items.append(entry);resources+=1
            elif items[previous].get('verified')!='human':
                items[previous]=entry
            if p['research'].get('status')=='reviewed':
                continue
            p['research'].update(status='auto_collected',checked_at=TODAY);pp.write_text(yaml.safe_dump(p,allow_unicode=True,sort_keys=False,width=100));pp.with_name('OFFICIAL.md').write_text(render(p))
    temporary=overrides.with_suffix('.csv.tmp')
    with temporary.open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(urls)
    temporary.replace(overrides)
    out=ROOT/'data/review/public-repository-differences-2026.csv'
    if differences:
        with out.open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(differences[0]));w.writeheader();w.writerows(differences)
    print(f'Community dataset records: {len(candidates)}; new English names: {added}; existing facts kept: {kept}; community resources: {resources}; differences queued: {len(differences)}')
if __name__=='__main__':main()
