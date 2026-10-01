#!/usr/bin/env python3
"""Index fixed GitHub PPT/Marp references without executing upstream skills."""
import datetime as dt
import hashlib
import json
import pathlib
import subprocess
import urllib.parse
import urllib.request
import yaml
from profile_extensions import upsert

ROOT=pathlib.Path(__file__).resolve().parents[2]
TODAY=dt.date.today().isoformat()


def main():
    specs=yaml.safe_load((ROOT/'data/review/community-ppt-sources-2026.yaml').read_text())
    paths={p.parent.name:p for p in (ROOT/'universities').glob('*/*/profile.yaml')}
    receipts=[];added=0
    for spec in specs:
        repo=spec['repository'];commit=spec['commit'];base='https://github.com/'+repo+'/blob/'+commit+'/'
        request=urllib.request.Request('https://raw.githubusercontent.com/'+repo+'/'+commit+'/README.md',headers={'User-Agent':'university-design-db/1.0'})
        with urllib.request.urlopen(request,timeout=20) as response:body=response.read(200_001)
        if len(body)>200_000:raise ValueError('README too large')
        text=body.decode('utf-8');sha=hashlib.sha256(body).hexdigest()
        if spec['name_zh'] not in text and not (spec['name_zh']=='哈尔滨工业大学' and '哈工大' in text):raise ValueError('school identity gap')
        tree=json.loads(subprocess.check_output(['gh','api','repos/'+repo+'/git/trees/'+commit+'?recursive=1']))
        if tree.get('truncated'):raise ValueError('incomplete file listing')
        files=[dict(path=x['path'],url=base+urllib.parse.quote(x['path'],safe='/'),format='PPTX',byte_size=x.get('size'),git_blob=x['sha'],content_read=False)
               for x in tree['tree'] if x['path'].lower().endswith('.pptx')]
        p=yaml.safe_load(paths[spec['school_code']].read_text())
        if p['identity']['name_zh']!=spec['name_zh']:raise ValueError('profile identity gap')
        entry=dict(title=spec['title'],url='https://github.com/'+repo+'/tree/'+commit,source=base+'README.md',publisher=repo,
            repository=repo,kind=spec['kind'],official=False,license=spec['license'],commit=commit,formats=spec['formats'],
            source_sha256=sha,source_text_read=True,verified='auto',checked_at=TODAY,files=files,
            usage_note=spec['identity_basis']+' 已读取固定版本README并确认文件目录；未读取PPTX内容、未运行上游脚本或SKILL、未镜像模板/字体/校徽。'+
                       ('代码MIT许可不替代字体和图形权利，按上游及校方说明使用。' if spec['license'] else '许可未声明，仅索引入口，使用或再发布前查看上游和校方要求。'))
        added+=upsert(p['resources'].setdefault('community_resources',[]),entry,lambda x:x['url'])
        paths[spec['school_code']].write_text(yaml.safe_dump(p,allow_unicode=True,sort_keys=False,width=100))
        receipts.append(dict(spec,readme_sha256=sha,files=files,checked_at=TODAY,redistribution='metadata only'))
    (ROOT/'data/review/community-ppt-metadata-2026.json').write_text(json.dumps(receipts,ensure_ascii=False,indent=2)+'\n')
    print('Added %s community PPT/Marp projects with %s concrete PPTX file references.'%(added,sum(len(r['files']) for r in receipts)))


if __name__=='__main__':main()
