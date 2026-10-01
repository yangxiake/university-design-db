#!/usr/bin/env python3
"""Read pinned TikZ source files as text and index explicit school references.

No TeX compilation, source-code execution or graphic redistribution occurs.
"""
import concurrent.futures
import csv
import datetime as dt
import hashlib
import json
import pathlib
import re
import urllib.request
import yaml
from profile_extensions import upsert

ROOT=pathlib.Path(__file__).resolve().parents[2]
REPOSITORY='yuxtech/cnlogo'
COMMIT='daca8906123ca61186218ddda7369f95cc65a664'
TODAY=dt.date.today().isoformat()
RAW='https://raw.githubusercontent.com/'+REPOSITORY+'/'+COMMIT+'/'
BLOB='https://github.com/'+REPOSITORY+'/blob/'+COMMIT+'/'


def read(path):
    request=urllib.request.Request(RAW+path,headers={'User-Agent':'university-design-db/1.0 source-metadata-reader'})
    with urllib.request.urlopen(request,timeout=20) as response:body=response.read(2_000_001)
    if len(body)>2_000_000:raise ValueError('source_too_large')
    return body.decode('utf-8'),hashlib.sha256(body).hexdigest()


def main():
    readme,readme_sha=read('README.md');license_text,license_sha=read('LICENSE')
    # Explicit README names and identifiers; do not infer identity from a slug.
    support=next(line for line in readme.splitlines() if line.startswith('目前支持：'))
    candidates=re.findall(r'([\u4e00-\u9fff]+)\s*\(([a-z0-9]+)\)',support)
    schools={r['name_zh']:r for r in csv.DictReader((ROOT/'data/universities-scope-2026.csv').open(encoding='utf-8-sig'))}
    paths={p.parent.name:p for p in (ROOT/'universities').glob('*/*/profile.yaml')}
    def inspect(candidate):
        name,slug=candidate;path='cnlogo/'+slug+'.tex';text,sha=read(path)
        first=text.splitlines()[0].lstrip('% ').strip()
        return dict(name_zh=name,upstream_path=path,source=BLOB+path,source_sha256=sha,
                    comment_name=first,status='exact_school_match' if name in schools and first==name else 'identity_gap',
                    school_code=schools[name]['school_code'] if name in schools and first==name else None)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:records=list(pool.map(inspect,candidates))
    added=0
    for record in records:
        if record['status']!='exact_school_match':continue
        path=paths[record['school_code']];p=yaml.safe_load(path.read_text())
        entry=dict(title=record['name_zh']+'社区TikZ矢量标识源码',url=record['source'],source=BLOB+'README.md',publisher='yuxtech/cnlogo',
            kind='tikz_logo_source',official=False,repository=REPOSITORY,commit=COMMIT,
            license='源代码声明AGPL-3.0；LICENSE将Logos/graphics排除在该许可之外',verified='auto',checked_at=TODAY,
            upstream_path=record['upstream_path'],source_sha256=record['source_sha256'],formats=['TeX/TikZ'],content_read=True,
            usage_note='README与文件首行中文学校名均精确匹配教育部名称。源码为社区转换，需用户自行使用LaTeX/TikZ导出后用于PPT；本库没有编译或保证图形现行版本。代码许可不等于校徽图形许可；只保存固定版本源码入口、格式和内容哈希，不再分发代码或校徽。')
        added+=upsert(p['resources'].setdefault('community_resources',[]),entry,lambda x:x['url'])
        if p['research'].get('status')!='reviewed':p['research'].update(status='auto_collected',checked_at=TODAY)
        path.write_text(yaml.safe_dump(p,allow_unicode=True,sort_keys=False,width=100))
    report=dict(repository=REPOSITORY,commit=COMMIT,checked_at=TODAY,readme_sha256=readme_sha,license_sha256=license_sha,
                license_basis='Pinned LICENSE contains an AGPL v3 source-code notice and an explicit exception for Logos/graphics; do not treat it as a graphic license.',
                source_files_read=len(records),matched=sum(r['status']=='exact_school_match' for r in records),records=records,
                excluded_identity_note='贵阳师范大学、西南农业大学、西南师范大学不按旧名或疑似笔误绑定现行学校；中国地质大学没有城市限定，不选武汉或北京。')
    (ROOT/'data/review/cnlogo-metadata-2026.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print('Indexed %s exact school TikZ references; %s new entries.'%(report['matched'],added))


if __name__=='__main__':main()
