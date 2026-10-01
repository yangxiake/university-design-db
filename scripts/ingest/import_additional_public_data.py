#!/usr/bin/env python3
"""Import pinned MIT metadata subsets and inspect linked ZIP members locally.

Source programs are never executed. ZIP graphics remain in ignored tmp only.
Historical/estimated community records are snapshots, not official statistics.
"""
import collections
import csv
import datetime as dt
import hashlib
import json
import pathlib
import urllib.parse
import urllib.request
import zipfile

import yaml

from import_public_repositories import checkout, read, normalize
from expand_repository_fields import metadata, asset_entry, inspect_bytes, apply_visual_result
from profile_extensions import put_fact, upsert, FACTS, COLLECTIONS, ENTRY_FIELDS

ROOT=pathlib.Path(__file__).resolve().parents[2]
TODAY=dt.date.today().isoformat()


def matched_domain_rows(rows, profiles):
    hosts=collections.defaultdict(list);english=collections.defaultdict(list)
    for code,p in profiles.items():
        url=p['identity']['official_website'].get('value')
        if url:hosts[(urllib.parse.urlparse(url).hostname or '').removeprefix('www.')].append(code)
        name=p['identity']['name_en'].get('value')
        if name:english[normalize(name).lower()].append(code)
    matched=[];gaps=[]
    for r in rows:
        if r['country']!='China':continue
        hits={c for d in r['domains'] for c in hosts.get(d.removeprefix('www.'),[]) if len(hosts[d.removeprefix('www.')])==1}
        basis='已确认官网的完整主机名唯一匹配；没有用母校根域名匹配独立学院'
        if not hits:
            codes=english.get(normalize(r['name']).lower(),[])
            hits=set(codes) if len(codes)==1 else set();basis='现有英文全名唯一匹配'
        if len(hits)==1:matched.append(dict(school_code=next(iter(hits)),upstream_record_name=r['name'],match_basis=basis,record=r))
        else:gaps.append(dict(name=r['name'],reason='无完整身份唯一匹配',domains=r['domains']))
    return matched,gaps


def save_snapshot(repo, rows, paths):
    if repo['license']!='MIT':raise ValueError('Snapshot requires a compatible data license')
    folder=ROOT/'data/external'/repo['repository'].replace('/','__');folder.mkdir(parents=True,exist_ok=True)
    output=folder/'matched-fields.jsonl';output.write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in rows),encoding='utf-8')
    upstream=checkout(repo);(folder/'LICENSE').write_text(read(upstream,repo['commit'],repo.get('license_file','LICENSE')),encoding='utf-8')
    provenance=dict(repository=repo['repository'],commit=repo['commit'],paths=paths,license='MIT',data_as_of=repo['data_as_of'],imported_at=TODAY,
        matched_records=len(rows),sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
        purpose='可再分发社区匹配子集；含估算与历史信息，不代表官方统计。图像仅保存链接及元数据。')
    (folder/'FIELDS-SOURCE.yaml').write_text(yaml.safe_dump(provenance,allow_unicode=True,sort_keys=False),encoding='utf-8')
    return output.relative_to(ROOT).as_posix()


def sync_catalog(config,reports,archive_count):
    """Keep the source inventory intact after the original importer is rerun."""
    sources={r['repository']:r for r in config['supplemental_repositories']}
    path=ROOT/'data/review/public-repository-assessment-2026.csv'
    with path.open(encoding='utf-8-sig') as handle:
        reader=csv.DictReader(handle);fields=reader.fieldnames;rows=[r for r in reader if r['repository'] not in sources]
    table=[]
    for report in reports:
        repo=sources[report['repository']];count=report['matched_schools']
        rows.append(dict(repository=repo['repository'],commit=repo['commit'],license='MIT',mode='MIT匹配快照',
                         matched_resource_schools=count,notes=repo['notes']))
        table.append('| [%s](https://github.com/%s) | MIT匹配快照 | MIT | %s |'%(repo['repository'],repo['repository'],count))
    with path.open('w',encoding='utf-8-sig',newline='') as handle:
        writer=csv.DictWriter(handle,fields);writer.writeheader();writer.writerows(rows)
    path=ROOT/'data/external/README.md';lines=path.read_text().splitlines()
    lines=[line for line in lines if not any(line.startswith('| ['+name+']') for name in sources)]
    position=next(i for i,line in enumerate(lines) if line.startswith('字段并集模式'))-1
    lines[position:position]=table
    text='\n'.join(lines).split('\n## 追加采集的图形时间说明')[0]
    text+='\n\n## 追加采集的图形时间说明\n\n压缩包内%s个图像只收链接、成员路径与文件元数据；图形版本日期为unspecified。2021排名年份和ZIP内部文件时间均不能当作学校标识设计年份。\n'%archive_count
    path.write_text(text,encoding='utf-8')


def main():
    config=yaml.safe_load((ROOT/'data/external/repositories.yaml').read_text())
    profiles={};paths={}
    for path in (ROOT/'universities').glob('*/*/profile.yaml'):
        p=yaml.safe_load(path.read_text());code=p['identity']['school_code'];profiles[code]=p;paths[code]=path
    names={normalize(p['identity']['name_zh']):code for code,p in profiles.items()}
    reports=[];gaps=[];touched=set()
    for repo in config['supplemental_repositories']:
        upstream=checkout(repo);data=json.loads(read(upstream,repo['commit'],repo['dataset']))
        if repo['field_mode']=='insight_snapshot':
            aliases=json.loads(read(upstream,repo['commit'],repo['aliases']))
            rows=[]
            for name,r in data.items():
                code=names.get(normalize(name))
                if not code:continue
                al=[a for a,n in aliases.items() if normalize(n)==normalize(name)]
                rows.append(dict(school_code=code,upstream_record_name=name,record=r,aliases=al))
            count=len(data);fields=sorted(set(k for r in data.values() for k in r)|{'aliases'})
        else:
            rows,missing=matched_domain_rows(data,profiles);gaps.extend(dict(repository=repo['repository'],**r) for r in missing)
            count=sum(r['country']=='China' for r in data);fields=sorted(set(k for r in data for k in r))
        target=save_snapshot(repo,rows,[repo['dataset']]+([repo['aliases']] if repo.get('aliases') else []))
        for row in rows:
            code=row['school_code'];p=profiles[code]
            entry=dict(repository=repo['repository'],commit=repo['commit'],data_path=target,school_code=code,
                upstream_record_name=row['upstream_record_name'],upstream_fields=sorted(row['record']),source=metadata(repo,row['upstream_record_name'],repo['dataset'])['source'],
                license='MIT',data_as_of=repo['data_as_of'],verified='auto',checked_at=TODAY)
            upsert(p['community']['snapshots'],entry,lambda x:(x['repository'],x['commit'],x['upstream_record_name']));touched.add(code)
            if row.get('aliases'):
                put_fact(p,'identity.aliases',row['aliases'],metadata(repo,row['upstream_record_name'],repo['aliases']),
                    basis='社区检索别名；不是学校正式中文简称或全部历史校名')
        reports.append(dict(repository=repo['repository'],mode=repo['field_mode'],records=count,matched=len(rows),
                            matched_schools=len({r['school_code'] for r in rows}),fields=fields))
        print(repo['repository'],'matched',len(rows),'/',count,flush=True)
    # The original data repository also contains a larger, separately named
    # logo ZIP. Read member bytes directly; no filesystem extraction or exec.
    repo=next(r for r in config['repositories'] if r['repository']=='xioajiumi/Chinese_Universities')
    archive=ROOT/'tmp/archives'/(repo['commit']+'-logos.zip');archive.parent.mkdir(parents=True,exist_ok=True)
    url='https://raw.githubusercontent.com/%s/%s/%s'%(repo['repository'],repo['commit'],repo['logo_archive'])
    if not archive.exists():
        with urllib.request.urlopen(url,timeout=30) as response:payload=response.read(40_000_001)
        if len(payload)>40_000_000:raise ValueError('archive_size_limit')
        archive.write_bytes(payload)
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest!=repo['logo_archive_sha256']:raise ValueError('Pinned archive content hash mismatch')
    matched=[];unmatched=[];excluded=[]
    with zipfile.ZipFile(archive) as z:
        for member in z.infolist():
            if member.is_dir():continue
            name=member.filename if member.flag_bits&0x800 else member.filename.encode('cp437').decode('gb18030')
            code=names.get(normalize(pathlib.PurePosixPath(name).stem))
            if not code:unmatched.append(dict(member=name,reason='未与2026完整校名匹配，不推断更名关系'));continue
            if '..' in pathlib.PurePosixPath(name).parts or member.file_size>5_000_000 or member.file_size>max(member.compress_size,1)*200:raise ValueError('unsafe_archive_member')
            p=profiles[code];asset=asset_entry(repo,p['identity']['name_zh'],'logo.zip')
            asset.update(asset_id=hashlib.sha256((repo['repository']+'\0logo.zip\0'+name).encode()).hexdigest()[:16],
                file_name=pathlib.PurePosixPath(name).name,upstream_path='logo.zip!/'+name,download_kind='archive_member',
                archive_url=url,archive_member=name,archive_sha256=digest,source_as_of='unspecified',
                usage_note='来自固定版本logo.zip中的独立PNG文件；须下载压缩包并按archive_member选择文件，URL不是PNG直链。历史社区校徽，不认定为现行VI，图形授权归学校。')
            payload=z.read(member)
            if payload.lstrip().lower().startswith((b'<!doctype html',b'<html')):
                # A source file named.png can actually contain an HTML page.
                # Preserve the rejection, and retract only our automatic entry.
                excluded.append(dict(school_code=code,name_zh=p['identity']['name_zh'],member=name,
                    sha256=hashlib.sha256(payload).hexdigest(),reason='成员文件实际为HTML网页，不是校徽图像'))
                p['visual']['logo_assets']=[a for a in p['visual']['logo_assets'] if a['asset_id']!=asset['asset_id'] or a.get('verified')=='human']
                touched.add(code);continue
            asset['format']=None
            try:result=inspect_bytes(payload,name)
            except Exception as exc:
                result=dict(access_status='inspection_failed',inspection_error={'type':type(exc).__name__,'detail':str(exc)[:120]})
            apply_visual_result(p,asset,result);touched.add(code)
            matched.append(dict(school_code=code,name_zh=p['identity']['name_zh'],member=name,asset_id=asset['asset_id'],access_status=asset['access_status']))
    archive_report=dict(repository=repo['repository'],commit=repo['commit'],archive_url=url,archive_sha256=digest,
        archive_byte_size=archive.stat().st_size,graphic_version_date='unspecified',matched=matched,unmatched=unmatched,excluded=excluded,images_redistributed=False)
    (ROOT/'data/review/logo-archive-2026.json').write_text(json.dumps(archive_report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (ROOT/'data/review/supplemental-repositories-2026.json').write_text(json.dumps(dict(updated_at=TODAY,repositories=reports,unmatched=gaps),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    sync_catalog(config,reports,len(matched))
    for code in touched:
        paths[code].write_text(yaml.safe_dump(profiles[code],allow_unicode=True,sort_keys=False,width=100),encoding='utf-8')
    schema=yaml.safe_load((ROOT/'data/profile-schema-v3.yaml').read_text());schema['entry_fields']=ENTRY_FIELDS
    (ROOT/'data/profile-schema-v3.yaml').write_text(yaml.safe_dump(schema,allow_unicode=True,sort_keys=False),encoding='utf-8')
    print('Updated',len(touched),'profiles; inspected archive matches',len(matched),flush=True)


if __name__=='__main__':main()
