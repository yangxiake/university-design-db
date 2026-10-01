#!/usr/bin/env python3
"""Import the union of public dataset fields and per-file visual metadata."""
import argparse
import base64
import collections
import concurrent.futures
import csv
import datetime as dt
import hashlib
import html
import io
import json
import pathlib
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

import yaml

from import_public_repositories import ROOT, checkout, normalize, read, read_objects
from profile_extensions import FACTS, COLLECTIONS, ENTRY_FIELDS, migrate, put_fact, rgb, upsert
from static_js_data import extract_assignment, extract_universities

TODAY = dt.date.today().isoformat()
CONFIG = ROOT / 'data/external/repositories.yaml'
CACHE = ROOT / 'tmp/visual-inspection'
MAX_IMAGE_BYTES = 20_000_000
TYPE_NAMES = {'comprehensive': '综合', 'stem': '理工', 'normal': '师范',
              'agriculture': '农林', 'forestry': '林业', 'medical': '医药',
              'finance': '财经', 'arts': '艺术', 'sports': '体育', 'language': '语言'}


def blob_url(repo, filename):
    return 'https://github.com/%s/blob/%s/%s' % (
        repo['repository'], repo['commit'], urllib.parse.quote(filename, safe='/'))


def metadata(repo, name, filename, note='社区数据原值；没有认定为校方现行声明。'):
    return dict(source=blob_url(repo, filename), verified='auto', checked_at=TODAY,
                source_type='community_dataset', upstream_repository=repo['repository'],
                upstream_commit=repo['commit'], upstream_record_name=name,
                upstream_license=repo.get('license'), source_as_of=repo.get('data_as_of') or 'unspecified', note=note)


def snapshot(repo, rows, source_paths):
    """Only configured MIT data files are redistributed, with their notices."""
    if repo.get('license') != 'MIT':
        raise ValueError('A compatible license is required for data snapshots')
    folder = ROOT / 'data/external' / repo['repository'].replace('/', '__')
    folder.mkdir(parents=True, exist_ok=True)
    output = folder / 'matched-fields.jsonl'
    output.write_text(''.join(json.dumps(row, ensure_ascii=False, sort_keys=True)+'\n'
                              for row in rows), encoding='utf-8')
    path = checkout(repo)
    (folder / 'LICENSE').write_text(read(path, repo['commit'], 'LICENSE'), encoding='utf-8')
    (folder / 'FIELDS-SOURCE.yaml').write_text(yaml.safe_dump(dict(
        repository=repo['repository'], commit=repo['commit'], paths=source_paths,
        license=repo['license'], data_as_of=repo['data_as_of'], imported_at=TODAY,
        matched_records=len(rows), sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
        purpose='上游字段匹配子集；原记录不代表本库采纳全部结论。素材仅链接，不再分发图像。'),
        allow_unicode=True, sort_keys=False), encoding='utf-8')
    return output.relative_to(ROOT).as_posix()


def attach_snapshot(profile, repo, data_path, record, filename):
    entry = dict(repository=repo['repository'], commit=repo['commit'], data_path=data_path,
                 school_code=profile['identity']['school_code'], upstream_record_name=record.get('name_zh') or record.get('name') or record.get('title'),
                 upstream_fields=sorted(record), source=blob_url(repo, filename),
                 license=repo['license'], data_as_of=repo['data_as_of'],
                 verified='auto', checked_at=TODAY)
    upsert(profile['community']['snapshots'], entry, lambda x: (x['repository'], x['commit']))


def asset_entry(repo, name, filename, kind='badge', external_url=None):
    url = external_url or ('https://raw.githubusercontent.com/%s/%s/%s' % (
        repo['repository'], repo['commit'], urllib.parse.quote(filename, safe='/')))
    source = blob_url(repo, filename)
    format_hint = pathlib.PurePosixPath(urllib.parse.urlparse(url).path).suffix.lstrip('.').lower()
    key = hashlib.sha256((repo['repository']+'\0'+url).encode()).hexdigest()[:16]
    return dict(asset_id=key, title=name+'校徽资源' if kind=='badge' else name+'校名文字资源',
                kind=kind, url=url, source=source, file_name=pathlib.PurePosixPath(urllib.parse.urlparse(url).path).name,
                upstream_path=filename, publisher=repo['repository'].split('/')[0],
                official=False, repository=repo['repository'], commit=repo['commit'],
                repository_license=repo.get('license'), asset_license=None, rights_holder=name,
                format=format_hint or None, width=None, height=None, vector=None,
                has_alpha=None, transparent_background=None, sha256=None,
                access_status='indexed_not_fetched', availability='found', verified='auto',
                checked_at=TODAY, usage_note='具体文件地址来自社区记录。仓库代码/数据许可不等于校徽图形或商标授权；素材只链接，使用时查看学校与上游说明。')


def upsert_asset(profile,entry):
    items=profile['visual']['logo_assets']
    existing=next((item for item in items if item['asset_id']==entry['asset_id']),None)
    if existing and existing.get('commit')==entry['commit'] and existing.get('access_status')=='content_inspected' and entry.get('access_status')=='indexed_not_fetched':
        for key in ('format','width','height','vector','representation','has_alpha','transparent_background',
                    'sha256','byte_size','access_status','resolved_url','inspection_source','encoding','view_box',
                    'intrinsic_width','intrinsic_height','attempts'):
            if key in existing:entry[key]=existing[key]
    return upsert(items,entry,lambda x:x['asset_id'])


def parse_hex(value):
    value = value.strip()
    if re.fullmatch(r'#[0-9a-fA-F]{3}', value):
        return '#' + ''.join(char*2 for char in value[1:]).upper()
    if re.fullmatch(r'#[0-9a-fA-F]{6}', value):
        return value.upper()
    match = re.fullmatch(r'rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)', value)
    if match and max(map(int, match.groups())) <= 255:
        return '#%02X%02X%02X' % tuple(map(int, match.groups()))
    return None


def chromatic(value):
    channels = rgb(value)
    return max(channels)-min(channels) >= 25 and max(channels) > 40 and min(channels) < 240


def inspect_bytes(body, filename):
    """Read intrinsic metadata only; do not render or modify upstream imagery."""
    result = dict(sha256=hashlib.sha256(body).hexdigest(), access_status='content_inspected',
                  byte_size=len(body), colors=[])
    # Some upstream .svg names actually contain JPEG bytes; inspect the content.
    encoding='utf-16' if body.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-8-sig'
    try:
        prefix=body[:5000].decode(encoding)
    except UnicodeError:
        prefix=''
    looks_svg = bool(re.search(r'<svg(?:\s|[/>])',prefix))
    if looks_svg:
        text = body.decode(encoding)
        if '<!ENTITY' in text.upper():
            # Illustrator exports literal namespace aliases in its internal DTD.
            # Resolve only a small whitelist of literal namespace URIs locally;
            # never load external DTDs, process nested entities or read files.
            declarations=re.findall(r'<!ENTITY\s+([A-Za-z_][\w.-]*)\s+"([^"<>]*)"\s*>',text)
            if len(declarations)>16 or len(declarations)!=text.upper().count('<!ENTITY'):
                raise ValueError('Unsupported SVG entity declarations')
            for name,value in declarations:
                if not name.startswith('ns_') or len(value)>200 or not re.fullmatch(r'https?://(?:ns\.adobe\.com|www\.w3\.org)/[A-Za-z0-9/._-]+',value):
                    raise ValueError('Only literal SVG namespace aliases are supported')
                text=text.replace('&'+name+';',value)
            text=re.sub(r'<!DOCTYPE\s+svg\b[^[]*\[[\s\S]*?\]>', '', text, count=1)
            if '<!ENTITY' in text.upper():raise ValueError('Unresolved SVG entity declaration')
        root = ET.fromstring(text)
        if root.tag.rsplit('}', 1)[-1] != 'svg':
            raise ValueError('Not an SVG document')
        for element in root.iter():
            tag = element.tag.rsplit('}', 1)[-1].lower()
            authoring_metadata=(tag=='foreignobject' and
                (element.get('requiredExtensions') or '').startswith('http://ns.adobe.com/AdobeIllustrator/') and
                all(child.tag.rsplit('}',1)[-1]=='pgfRef' for child in element))
            if tag=='script' or (tag=='foreignobject' and not authoring_metadata):
                raise ValueError('Active SVG content')
            for key, value in element.attrib.items():
                key = key.rsplit('}', 1)[-1].lower()
                if key.startswith('on') or (key == 'href' and value and not value.startswith(('#','data:image/'))):
                    raise ValueError('Active or external SVG reference')
                if re.search(r'url\(\s*[\'\"]?(?:https?:|//)', value, re.I):
                    raise ValueError('External SVG style reference')
            if tag == 'style' and element.text and re.search(r'@import|url\(\s*[\'\"]?(?:https?:|//)', element.text, re.I):
                raise ValueError('External SVG stylesheet')
        def dimension(value):
            match = re.fullmatch(r'\s*([0-9.]+)(?:px)?\s*', value or '')
            return float(match.group(1)) if match else None
        embedded_images=[element for element in root.iter() if element.tag.rsplit('}',1)[-1]=='image']
        result.update(format='svg', vector=not bool(embedded_images),
                      representation='vector' if not embedded_images else 'svg_with_raster', width=dimension(root.get('width')),
                      height=dimension(root.get('height')), has_alpha=None,
                      transparent_background=None, view_box=root.get('viewBox'))
        result.update(encoding=encoding,intrinsic_width=root.get('width'),intrinsic_height=root.get('height'))
        fills = collections.Counter()
        for element in root.iter():
            fill = element.get('fill')
            if fill and parse_hex(fill):
                fills[parse_hex(fill)] += 1
            for fill in re.findall(r'(?:^|[;{])\s*fill\s*:\s*([^;}]+)', element.get('style', '')+';'+(element.text or '' if element.tag.endswith('style') else '')):
                if parse_hex(fill):
                    fills[parse_hex(fill)] += 1
        result['colors'] = [value for value, count in fills.most_common() if chromatic(value)][:3]
        result['color_basis'] = 'SVG填充属性/样式的色值频次，未按图形面积加权；仅作社区标识配色参考。'
        if not result['colors'] and embedded_images:
            for image in embedded_images:
                href=next((value for key,value in image.attrib.items() if key.rsplit('}',1)[-1]=='href'), '')
                match=re.match(r'data:image/(?:png|jpe?g);base64,([\s\S]+)',href)
                if match:
                    embedded=base64.b64decode(re.sub(r'\s+','',match.group(1)),validate=True)
                    if len(embedded)>MAX_IMAGE_BYTES:raise ValueError('Embedded image exceeds size limit')
                    sampled=inspect_bytes(embedded,'embedded.png')
                    result['colors']=sampled['colors']
                    result['color_basis']='SVG内嵌位图取样；'+sampled['color_basis']
                    break
    else:
        from PIL import Image
        with Image.open(io.BytesIO(body)) as image:
            if image.width*image.height > 20_000_000:
                raise ValueError('Image pixel count exceeds limit')
            image.load()
            alpha = image.mode in {'RGBA', 'LA'} or 'transparency' in image.info
            rgba = image.convert('RGBA')
            colors = collections.Counter()
            for red, green, blue, opacity in rgba.resize((128, 128)).getdata():
                if opacity < 200:
                    continue
                value = '#%02X%02X%02X' % (red//8*8, green//8*8, blue//8*8)
                if chromatic(value):
                    colors[value] += 1
            result.update(format=image.format.lower(), vector=False, width=image.width,
                          representation='raster',
                          height=image.height, has_alpha=alpha,
                          transparent_background=(rgba.getextrema()[3][0] < 255) if alpha else False,
                          colors=[value for value, count in colors.most_common(3)],
                          color_basis='社区标识图像缩小取样并按8级量化，过滤透明及灰度像素；仅作PPT建议色。')
    return result


def inspect_asset(entry):
    CACHE.mkdir(parents=True, exist_ok=True)
    cache = CACHE / (entry['asset_id']+'-'+entry['commit']+'-v2.json')
    if cache.exists():
        return json.loads(cache.read_text())
    urls = [entry['url'], entry['url'].replace('https://raw.githubusercontent.com/', 'https://github.com/').replace('/'+entry['commit']+'/', '/raw/'+entry['commit']+'/')]
    attempts = []
    result = None
    for url in dict.fromkeys(urls):
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'university-design-db/0.3 public-metadata-research'})
            with urllib.request.urlopen(request, timeout=15) as response:
                body = response.read(MAX_IMAGE_BYTES+1)
                if len(body) > MAX_IMAGE_BYTES:
                    raise ValueError('Asset exceeds byte limit')
                result = inspect_bytes(body, urllib.parse.urlparse(entry['url']).path)
                result['resolved_url'] = response.url
                result['inspection_source'] = url
            break
        except (ValueError, OSError, ET.ParseError, UnicodeError) as exc:
            attempts.append(dict(url=url, error=str(exc)[:240]))
    if result is None:
        result = dict(access_status='inspection_failed', attempts=attempts, colors=[])
    result['attempts'] = attempts
    # Failed network requests remain retryable on the next run.
    if result['access_status'] == 'content_inspected':
        cache.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
    return result


def seed_palettes(profile):
    for key, role in [('color_primary', 'primary'), ('color_secondary', 'secondary')]:
        fact = profile['visual'][key]
        if fact['availability'] == 'found':
            entry = dict(value=fact['value'].upper(), rgb=rgb(fact['value']), cmyk=fact.get('cmyk'),
                         pantone=fact.get('pantone'), label=fact.get('label'), role=role, method=fact['method'], official=fact['method']=='official_vi',
                         source=fact['source'], verified=fact['verified'], checked_at=fact['checked_at'],
                         availability='found', basis=fact.get('basis') or fact.get('note') or '现有附来源颜色字段。',
                         source_field='visual.'+key)
            previous=next((item for item in profile['visual']['color_palette'] if
                (item['source'],item['value'],item['method'])==(entry['source'],entry['value'],entry['method'])),{})
            # Reprojecting scalar colours must retain the richer VI colour-card
            # metadata collected later, including print standards and file hash.
            for metadata_key in ('cmyk','pantone','label'):
                if entry.get(metadata_key) is None and previous.get(metadata_key) is not None:
                    entry[metadata_key]=previous[metadata_key]
            entry=dict(previous,**entry)
            upsert(profile['visual']['color_palette'], entry, lambda x: (x['source'], x['value'], x['method']))
    for resource in profile['resources'].get('community_resources', []):
        for color in resource.get('palette', []):
            entry = dict(value=color['value'], rgb=rgb(color['value']), cmyk=None, pantone=None,
                         role='reference', method='community_theme', official=False,
                         source=color.get('source') or resource['source'], verified='auto', checked_at=TODAY,
                         availability='found', basis=color['basis'], repository=resource['publisher'],
                         commit=resource['commit'])
            upsert(profile['visual']['color_palette'], entry, lambda x: (x['source'], x['value'], x['method']))


def assessment_entries(record, meta):
    grades=collections.defaultdict(set)
    for key,grade in [('aplus','A+'),('a','A'),('aminus','A-')]:
        for subject in record.get(key) or []:
            grades[subject].add(grade)
    entries=[]
    for subject,values in grades.items():
        entry=dict(subject=subject,grade=next(iter(values)) if len(values)==1 else None,
                   round=4,assessment_year=2017,publisher='教育部学位与研究生教育发展中心',
                   completeness='upstream_selection',availability='found' if len(values)==1 else 'conflict',**meta)
        if len(values)>1:
            entry['candidates']=[dict(grade=grade,source=meta['source']) for grade in sorted(values)]
            entry['note']='同一上游记录把本学科列在多个等级；保留冲突，不自动选择。'
        entries.append(entry)
    return entries


def apply_visual_result(profile,asset,result):
    colors=result.pop('colors',[])
    basis=result.pop('color_basis','')
    asset.update(result)
    upsert_asset(profile,asset)
    if asset['kind']=='badge':
        for value in colors:
            entry=dict(value=value,rgb=rgb(value),cmyk=None,pantone=None,role='reference',
                       method='community_logo_sample',official=False,source=asset['source'],
                       verified='auto',checked_at=TODAY,availability='found',basis=basis,
                       repository=asset['repository'],commit=asset['commit'],asset_id=asset['asset_id'])
            upsert(profile['visual']['color_palette'],entry,lambda x:(x['source'],x['value'],x['method']))


def retry_visual_errors():
    affected={};pending=[]
    for path in sorted((ROOT/'universities').glob('*/*/profile.yaml')):
        profile=yaml.safe_load(path.read_text())
        failed=[asset for asset in profile['visual'].get('logo_assets',[]) if asset['access_status']=='inspection_failed']
        if failed:
            affected[path]=profile
            pending.extend((path,asset) for asset in failed)
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        jobs={executor.submit(inspect_asset,asset):(path,asset) for path,asset in pending}
        for future in concurrent.futures.as_completed(jobs):
            path,asset=jobs[future]
            apply_visual_result(affected[path],asset,future.result())
    for path,profile in affected.items():
        path.write_text(yaml.safe_dump(profile,allow_unicode=True,sort_keys=False,width=100))
    remaining=sum(asset['access_status']=='inspection_failed' for profile in affected.values() for asset in profile['visual']['logo_assets'])
    print('Retried',len(pending),'visual files; unresolved',remaining,flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skip-asset-inspection', action='store_true')
    parser.add_argument('--retry-visual-errors', action='store_true',help='Retry only visual files whose content inspection failed')
    args = parser.parse_args()
    if args.retry_visual_errors:
        retry_visual_errors()
        return
    with (ROOT/'data/universities-scope-2026.csv').open(encoding='utf-8-sig', newline='') as handle:
        scope = list(csv.DictReader(handle))
    schools = {normalize(row['name_zh']): row for row in scope}
    paths = {row['school_code']: ROOT/'universities'/row['province']/row['school_code']/'profile.yaml' for row in scope}
    profiles = {code: migrate(yaml.safe_load(path.read_text())) for code, path in paths.items()}
    for profile in profiles.values():
        seed_palettes(profile)
    config = yaml.safe_load(CONFIG.read_text())
    reports, rejected, pending = [], [], []

    for repo in config['repositories']:
        mode = repo.get('field_mode')
        if not mode:
            continue
        path = checkout(repo)
        records, files, full = [], {}, []
        if mode in {'basic_2021', 'basic_2026'}:
            filename = repo['dataset']
            records = read_objects(read(path, repo['commit'], filename))
            files = {id(record): filename for record in records}
        elif mode == 'panorama':
            for filename in repo['data_files']:
                batch = extract_universities(read(path, repo['commit'], filename))
                records.extend(batch)
                files.update({id(record): filename for record in batch})
            logos = extract_assignment(read(path, repo['commit'], 'data/logos.js'), 'LOGOS')
        elif mode == 'svg_metadata':
            filename = 'static/library/school/_meta.yaml'
            records = yaml.safe_load(read(path, repo['commit'], filename))['items']
            files = {id(record): filename for record in records}
        elif mode == 'vi_directory':
            body = read(path, repo['commit'], 'README.md')
            for line in body.splitlines():
                if not line.startswith('|'):
                    continue
                cells = [cell.strip() for cell in line.strip('|').split('|')]
                if len(cells) < 7:
                    continue
                name = re.sub(r'\([A-Za-z0-9-]+\)$', '', cells[0])
                school = schools.get(normalize(name))
                if not school:
                    continue
                links = re.findall(r'\[([^]]+)\]\((https?://[^)]+)\)', cells[2])
                profile = profiles[school['school_code']]
                for title, url in links:
                    entry = dict(title=title, url=url, kinds=cells[3],
                                 formats=re.findall(r'\.(ai|pdf|svg|eps|png|jpg|ppt|cdr)\b', cells[4], re.I),
                                 access_requirement=cells[5], campus_district=cells[1],
                                 source=blob_url(repo, 'README.md'), repository=repo['repository'],
                                 commit=repo['commit'], official=False, verified='auto', checked_at=TODAY,
                                 availability='found', note='社区索引指向学校页面；格式与访问限制为上游记录，未认定当前仍可下载。')
                    upsert(profile['visual']['vi_resources'], entry, lambda x: x['url'])
                if links:
                    abbr = re.search(r'\(([A-Za-z0-9-]+)\)$', cells[0])
                    if abbr:
                        meta = metadata(repo, name, 'README.md'); meta['source_type'] = 'community_directory'
                        put_fact(profile, 'identity.short_name_en', abbr.group(1), meta)
            reports.append(dict(repository=repo['repository'], mode=mode, records=len(body.splitlines()),
                                matched=sum(any(e['repository']==repo['repository'] for e in p['visual']['vi_resources']) for p in profiles.values()), fields=['school_name','campus_district','vi_urls','kinds','formats','access_requirement']))
            continue
        elif mode == 'logo_tree':
            english=collections.defaultdict(set)
            def english_key(value):
                return ''.join(re.findall('[a-z0-9]+',value.lower()))
            for code,profile in profiles.items():
                fact=profile['identity']['name_en']
                if fact['availability']=='found':
                    english[english_key(fact['value'])].add(code)
            filenames=subprocess.check_output(['git','ls-tree','-r','--name-only','-z',repo['commit']],cwd=path).decode().split('\0')
            matched_codes=set();selected=0
            for filename in filenames:
                if '/' not in filename or not filename.lower().endswith(('.png','.svg','.jpg','.jpeg')):
                    continue
                directory=filename.split('/')[0]
                codes=english.get(english_key(directory),set())
                if len(codes)!=1:
                    rejected.append(dict(repository=repo['repository'],name=directory,field='logo_directory',reason='英文目录未与本库英文全名唯一匹配；不采用模糊匹配'))
                    continue
                code=next(iter(codes));profile=profiles[code]
                asset=asset_entry(repo,profile['identity']['name_zh'],filename)
                variant=re.search(r'logo_([^_.]+)',pathlib.PurePosixPath(filename).name)
                size=re.search(r'(\d+)x(\d+)',pathlib.PurePosixPath(filename).name)
                asset['variant']=variant.group(1) if variant else None
                asset['dimensions_in_filename']=[int(value) for value in size.groups()] if size else None
                upsert_asset(profile,asset)
                pending.append((code,asset));selected+=1;matched_codes.add(code)
            reports.append(dict(repository=repo['repository'],mode=mode,records=len(filenames),matched=len(matched_codes),
                                selected_assets=selected,fields=['english_directory','logo_file','color_variant','dimensions_in_filename']))
            print(repo['repository'],'matched',len(matched_codes),'schools;',selected,'files',flush=True)
            continue
        else:
            raise ValueError('Unknown field import mode: '+mode)

        matched = []
        for record in records:
            name = record.get(repo.get('name_key', 'name')) or record.get('title')
            school = schools.get(normalize(name or ''))
            if not school:
                rejected.append(dict(repository=repo['repository'], name=name, reason='未与2026范围完整校名匹配，未自动归并到母校或改名学校'))
                continue
            code, filename = school['school_code'], files[id(record)]
            profile = profiles[code]
            meta = metadata(repo, name, filename)
            matched.append((profile, record, filename))
            full.append(dict(school_code=code, name_zh=school['name_zh'], source=meta['source'], upstream_record=record))
            if mode in {'basic_2021', 'basic_2026'}:
                school_type = record.get('type') if mode=='basic_2021' else TYPE_NAMES.get(record.get('category'), record.get('category'))
                put_fact(profile, 'institution.school_type', school_type, meta)
                if mode == 'basic_2026':
                    for dotted, key in [('identity.slug_aliases','slug_aliases'), ('institution.country','country'), ('institution.languages_of_instruction','languages_of_instruction')]:
                        put_fact(profile, dotted, record.get(key), meta)
                    put_fact(profile, 'institution.nature', {'public':'公办', 'private':'民办'}.get(record.get('uni_type')), meta)
                    if record.get('slug'):
                        upsert(profile['identity']['external_identifiers'], dict(namespace=repo['repository'], value=record['slug'], **meta), lambda x:(x['namespace'],x['value']))
                    ranking = record.get('shanghairanking') or {}
                    if ranking.get('national_rank') is not None:
                        entry = dict(publisher='ShanghaiRanking', ranking_name='软科中国大学排名',
                                     year=ranking['year'], scope='中国大学主榜', rank=ranking['national_rank'],
                                     score=ranking.get('score'), indicators=ranking.get('indicators') or {},
                                     upstream_url=ranking.get('url'), **meta)
                        upsert(profile['rankings']['entries'], entry, lambda x:(x['publisher'],x['year'],x['source']))
                    put_fact(profile, 'institution.groups', ranking.get('tags'), meta)
                    logo = record.get('logo_url')
                    if logo:
                        rejected.append(dict(repository=repo['repository'], name=name, field='logo_url', value=logo,
                                             reason='上游logo_url实际为Pexels照片链接，未当作校徽导入'))
                    if record.get('website') and re.search(r'english\.|/en(?:/|$)', record['website']):
                        put_fact(profile, 'resources.english_website', record['website'], meta)
                else:
                    if record.get('rank') is not None:
                        entry = dict(publisher='ShanghaiRanking', ranking_name='软科中国大学排名', year=2021,
                                     scope='中国大学主榜', rank=record['rank'], score=record.get('total_score'),
                                     indicators={'school_level':record.get('school_level')}, **meta)
                        upsert(profile['rankings']['entries'], entry, lambda x:(x['publisher'],x['year'],x['source']))
                    if (record.get('logo') or '').startswith(('http://','https://')):
                        asset = asset_entry(repo, name, filename, external_url=record['logo'])
                        asset['usage_note'] += ' 上游2021年排名站点图片地址，未验证当前图形或访问状态。'
                        upsert_asset(profile,asset)
            elif mode == 'panorama':
                put_fact(profile, 'identity.name_en', record.get('en'), meta)
                if profile['culture']['founded_year']['availability']=='unresearched' and isinstance(record.get('founded'),int):
                    put_fact(profile, 'culture.founded_year', record['founded'], meta,
                             basis='社区founded字段；上游未区分前身创立、合并或现行学校设立年份，保留其历史起点口径。')
                for dotted, key in [('identity.short_name_zh','abbr'), ('identity.short_name_en','enAbbr'),
                                    ('institution.school_type','type'), ('institution.groups','tags')]:
                    put_fact(profile, dotted, record.get(key), meta)
                put_fact(profile, 'location.coordinates', dict(longitude=record['lng'], latitude=record['lat'],
                         crs='unspecified', precision='approximate', location_kind='community_map_point'), meta,
                         basis='上游地图定位点；未声明WGS84/GCJ02，不能用于精密定位或推断完整校区位置。')
                # Preserve editorial descriptions in snapshots; avoid turning subjective promotion into facts.
                if record.get('intro'):
                    rejected.append(dict(repository=repo['repository'],name=name,field='intro/emp/tier',
                                         reason='简介、就业评论及主观梯队完整保存在社区快照；未混入客观学校事实或现行就业率'))
                first = record.get('firstClass') or []
                if first and not any('全部' in value or '数量' in value for value in first):
                    put_fact(profile, 'academics.double_first_class_disciplines', first, meta,
                             list_year=2022, completeness='upstream_selection',
                             basis='社区整理双一流学科名单，可能节选；不是教育部原表替代品。')
                for entry in assessment_entries(record,meta):
                    upsert(profile['academics']['subject_assessments'],entry,lambda x:(x['subject'],x['round'],x['source']))
                for key, curriculum in [('wl','物理类'), ('ls','历史类')]:
                    cutoff = (record.get('score') or {}).get(key)
                    if cutoff:
                        entry = dict(year=2025, region='重庆市', curriculum=curriculum, batch='普通类本科批',
                                     enrollment_type='上游参考整理', minimum_score=cutoff['min'],
                                     minimum_rank=cutoff['rank'], major_group=None, score_difference=None,
                                     enrolled_count=None, reference_only=True, **meta)
                        entry['note'] = '社区2025重庆录取参考值，未逐条提供招生官方证据；不作为实际志愿填报依据。'
                        upsert(profile['admissions']['cutoffs'], entry, lambda x:(x['year'],x['region'],x['curriculum'],x['source']))
                logo = logos.get(record['id'])
                if logo:
                    logo_name = logo['f'].rsplit(' ',1)[0]
                    if normalize(logo_name) != normalize(name):
                        rejected.append(dict(repository=repo['repository'], name=name,field='logo',reason='文件校名与数据全称不一致，待独立确认'))
                    else:
                        asset = asset_entry(repo, name, 'assets/'+logo['dir']+'/'+logo['f'])
                        upsert_asset(profile,asset)
                        pending.append((code,asset))
            elif mode == 'svg_metadata':
                for key, kind in [('file','badge'), ('wordmark','wordmark')]:
                    if record.get(key):
                        asset = asset_entry(repo, name, 'static/library/school/'+record[key], kind)
                        if key=='file' and '_wordmark' in record[key]:
                            asset['kind']='wordmark'
                            asset['title']=name+'校名文字资源'
                        upsert_asset(profile,asset)
                        pending.append((code,asset))

        data_path = snapshot(repo, full, sorted(set(files.values())))
        for profile, record, filename in matched:
            attach_snapshot(profile, repo, data_path, record, filename)
        reports.append(dict(repository=repo['repository'], mode=mode, records=len(records),
                            matched=len(matched), fields=sorted(set().union(*(set(r) for r in records)))))
        print(repo['repository'], 'matched', len(matched), '/', len(records), flush=True)

    # Add known employment portals from the existing, licensed exact-name directory.
    career = ROOT/'data/external/PotoYang__UniversityCareerWebPage/matched-career-links.jsonl'
    career_repo = next(r for r in config['repositories'] if r['repository']=='PotoYang/UniversityCareerWebPage')
    for line in career.read_text().splitlines():
        record=json.loads(line)
        profile=profiles[record['school_code']]
        put_fact(profile,'resources.career_url',record['career_url'],metadata(career_repo,record['name_zh'],career_repo['career_directory']))

    if not args.skip_asset_inspection:
        inspected=0
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            jobs = {executor.submit(inspect_asset,asset):(code,asset) for code,asset in pending}
            for future in concurrent.futures.as_completed(jobs):
                code,asset=jobs[future]
                result=future.result()
                apply_visual_result(profiles[code],asset,result)
                inspected+=1
                if inspected%40==0:
                    print('Visual files inspected',inspected,'/',len(pending),flush=True)

    for code,profile in profiles.items():
        paths[code].write_text(yaml.safe_dump(profile,allow_unicode=True,sort_keys=False,width=100),encoding='utf-8')
    report = dict(updated_at=TODAY,schema_version=3,scope_count=len(profiles),repositories=reports,
                  schema_facts={k:dict(type=v[0],description=v[1]) for k,v in FACTS.items()},
                  schema_collections=COLLECTIONS, rejected_or_snapshot_only=rejected,
                  visual_files_selected=len(pending))
    (ROOT/'data/review/github-field-union-2026.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (ROOT/'data/profile-schema-v3.yaml').write_text(yaml.safe_dump(dict(schema_version=3,
        facts=report['schema_facts'],collections=COLLECTIONS,entry_fields=ENTRY_FIELDS,
        provenance_fields=['source','verified','checked_at','source_type','upstream_repository',
                           'upstream_commit','upstream_record_name','upstream_license','source_as_of','note']),allow_unicode=True,sort_keys=False),encoding='utf-8')
    print('Migrated',len(profiles),'profiles; typed fields',len(FACTS),'collections',len(COLLECTIONS),flush=True)


if __name__=='__main__':
    main()
