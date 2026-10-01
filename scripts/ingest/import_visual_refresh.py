#!/usr/bin/env python3
"""Import explicit current VI decisions, retaining replaced automatic evidence."""
import datetime as dt
import json
import pathlib
import yaml
from profile_extensions import rgb,upsert,put_fact

ROOT=pathlib.Path(__file__).resolve().parents[2]
TODAY=dt.date.today().isoformat()


def main():
    decisions=yaml.safe_load((ROOT/'data/review/visual-refresh-decisions-2026.yaml').read_text())
    paths={p.parent.name:p for p in (ROOT/'universities').glob('*/*/profile.yaml')}
    log_path=ROOT/'data/review/visual-refresh-changes-2026.jsonl'
    log=[json.loads(line) for line in log_path.read_text().splitlines()] if log_path.exists() else []
    for d in decisions:
        path=paths[d['school_code']];p=yaml.safe_load(path.read_text())
        if p['identity']['name_zh']!=d['name_zh']:raise ValueError('School identity mismatch')
        def retain(field,current,reason):
            record=dict(school_code=d['school_code'],name_zh=d['name_zh'],field='visual.'+field,previous=current,
                        replacement_source=d['source'],reason=reason,checked_at=TODAY)
            if record not in log:log.append(record)
            if current.get('availability')=='found':
                for entry in p['visual']['color_palette']:
                    if entry.get('source_field')=='visual.'+field and entry['source']==current['source']:
                        entry.update(role='reference',source_field=None,current=False,basis=entry['basis']+'；已有新VI入口依据，保留为历史/取色参考。')
        for spec in d.get('colors',[]):
            entry=dict(value=spec['value'],rgb=rgb(spec['value']),cmyk=spec['cmyk'],pantone=spec['pantone'],label=spec['label'],
                       role=spec['role'],method='official_vi',official=True,source=d['source'],verified='auto',checked_at=TODAY,availability='found',basis=d['basis'])
            if d.get('source_sha256'):entry['source_sha256']=d['source_sha256']
            if spec.get('field'):
                key=spec['field'];current=p['visual'][key]
                replace=current.get('verified')!='human' and (current['availability']=='unresearched' or current.get('method') in spec.get('replace_methods',[]))
                if replace:
                    if current['availability']!='unresearched':retain(key,current,'official_VI_replaces_sample_reference')
                    p['visual'][key]=dict(value=spec['value'],source=d['source'],method='official_vi',label=spec['label'],basis=d['basis'],
                                         cmyk=spec['cmyk'],pantone=spec['pantone'],verified='auto',checked_at=TODAY,availability='found',search_sources=[])
                if p['visual'][key].get('value')==spec['value']:entry['source_field']='visual.'+key
            upsert(p['visual']['color_palette'],entry,lambda x:(x['source'],x['value'],x['method']))
        for spec in d.get('conflicts',[]):
            key=spec['field'];current=p['visual'][key]
            if current.get('verified')=='human':continue
            if current['availability']=='unresearched' or current.get('source') in spec.get('replace_sources',[]):
                if current['availability']!='unresearched':retain(key,current,'current_VI_internal_conflict_replaces_old_mark')
                p['visual'][key]=dict(value=None,source=None,verified='auto',checked_at=TODAY,availability='conflict',search_sources=[],
                    label=spec['label'],note=spec['reason'],candidates=[dict(c,source=d['source']) for c in spec['candidates']])
        vi=p['visual']['vi_url']
        if vi.get('verified')!='human' and vi.get('value') in d.get('replace_vi_sources',[]):
            retain('vi_url',vi,'current_navigation_replaces_old_visual_entry')
            from profile_extensions import empty_fact
            p['visual']['vi_url']=empty_fact()
        put_fact(p,'visual.vi_url',d['vi_url'],dict(source=d['source'],verified='auto',checked_at=TODAY))
        upsert(p['visual']['vi_resources'],dict(title=d['name_zh']+'官方视觉规范',url=d['vi_url'],kinds=['标识规范','标准色'],formats=['PDF'] if d['source'].endswith('.pdf') else ['HTML'],
            access_requirement='公开网页/文件，无需登录；依来源规则使用',source=d['source'],repository=None,commit=None,official=True,verified='auto',checked_at=TODAY,
            availability='found',note=d['basis']),lambda x:(x['url'],x['source']))
        path.write_text(yaml.safe_dump(p,allow_unicode=True,sort_keys=False,width=100),encoding='utf-8')
    log_path.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in log),encoding='utf-8')
    print('Imported %d school VI refresh decisions; retained %d replaced records.'%(len(decisions),len(log)))


if __name__=='__main__':main()
