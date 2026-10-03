#!/usr/bin/env python3
"""Build PPT-oriented school and resource indexes from canonical profiles."""
import argparse
import csv
import io
import pathlib
import re
from yaml_io import load_yaml

ROOT=pathlib.Path(__file__).resolve().parents[2]
STARTER_FIELDS=['school_code','name_zh','province','official_website','profile_path','visual_path',
 'logo_url','logo_kind','logo_format','logo_official','logo_access_status','logo_source','logo_asset_id',
 'logo_download_kind','logo_archive_url','logo_archive_member','logo_archive_sha256',
 'color_primary','color_method','color_status','color_label','color_source','color_basis',
 'official_print_color_entries','official_template_url','school_ppt_entries','department_ppt_entries','community_resource_entries',
 'school_ppt_file_count','department_ppt_file_count','community_ppt_file_count']
RESOURCE_FIELDS=['school_code','name_zh','province','category','title','url','publisher','official','use_scope',
 'formats','edition_year','access_requirement','download_status','content_read','source','source_sha256','repository','commit','license','usage_note',
 'file_format','file_sha256','file_byte_size','slide_count','aspect_ratio','font_names','editable_text_runs','file_inspection_status']
TEMPLATE_FIELDS=['school_code','name_zh','province','category','publisher','official','use_scope','edition_year',
 'title','url','download_url','archive_member','source','repository','commit','license',
 'sha256','byte_size','slide_count','width_emu','height_emu','aspect_ratio','font_names','theme_colors',
 'editable_text_runs','textless_slides','media_count','external_relationship_count','macro_enabled','checked_at']


def file_columns(entry):
    meta=entry.get('file_metadata') or {}
    return dict(file_format=meta.get('format'),file_sha256=meta.get('sha256'),file_byte_size=meta.get('byte_size'),
                slide_count=meta.get('slide_count'),aspect_ratio=meta.get('aspect_ratio'),font_names=';'.join(meta.get('font_names',[])),
                editable_text_runs=meta.get('editable_text_runs'),file_inspection_status=entry.get('file_inspection',{}).get('status'))


def template_rows(base,entry):
    meta=entry.get('file_metadata') or {};inspection=entry.get('file_inspection') or {}
    files=[dict(meta,archive_member='')] if meta.get('format')=='PPTX' else [dict(m,archive_member=m['path']) for m in meta.get('presentation_members',[]) if m['status']=='content_inspected']
    rows=[]
    for file in files:
        row={key:base.get(key) for key in TEMPLATE_FIELDS if key in base}
        row.update(download_url=inspection.get('resolved_url') or base['url'],archive_member=file['archive_member'],checked_at=inspection.get('checked_at'))
        row.update({key:file.get(key) for key in TEMPLATE_FIELDS if key in file})
        row['font_names']=';'.join(file.get('font_names',[]));row['theme_colors']=';'.join(file.get('theme_colors',[]))
        rows.append(row)
    return rows


def logo_score(asset):
    inspected=asset.get('access_status')=='content_inspected'
    # This orders candidates, not claims that the graph is current/authorized.
    return (inspected, bool(asset.get('official')),asset.get('kind') in {'badge','combination','wordmark'},
            bool(asset.get('vector')), bool(asset.get('transparent_background')),
            not bool(re.search(r'white|反白|白色',str(asset.get('variant') or '')+' '+str(asset.get('file_name') or ''),re.I)),
            (asset.get('width') or 0)*(asset.get('height') or 0))


def community_category(kind):
    return {'tikz_logo_source':'community_logo_source','logo_reference':'community_logo_reference',
            'history_reference':'community_history_reference','beamer_theme':'community_template',
            'marp_theme':'community_template','pptx_template':'community_template'}.get(kind,'community_reference')


def rows_for(profile,path):
    identity=profile['identity'];visual=profile['visual'];resources=profile['resources']
    base=dict(school_code=identity['school_code'],name_zh=identity['name_zh'],province=identity['province'])
    entries=[];files=[]
    for entry in visual['vi_resources']:
        kinds = entry['kinds'] if isinstance(entry['kinds'], list) else [entry['kinds']]
        if not re.search(r'PPT|演示文[稿档]',entry['title']+' '+' '.join(kinds),re.I):continue
        # A PPTX file containing only a logo is an asset, not a slide template.
        template=any('PPT模板' in k for k in kinds)
        category=('official_template' if template else 'official_visual_resource') if entry['official'] else ('community_template_reference' if template else 'community_visual_resource')
        row=dict(base,category=category,title=re.sub(r'\s+',' ',entry['title']).strip(),url=entry['url'],publisher=entry.get('publisher') or identity['name_zh'],
            official=entry['official'],use_scope=entry.get('use_scope') or 'unspecified',formats=';'.join(entry['formats']),
            edition_year=entry.get('edition_year'),access_requirement=entry['access_requirement'],download_status=entry.get('download_status') or 'indexed_not_fetched',
            content_read=entry.get('content_read'),source=entry['source'],source_sha256=entry.get('source_sha256'),repository=entry.get('repository'),
            commit=entry.get('commit'),license=None,usage_note=entry.get('note'),**file_columns(entry))
        entries.append(row);files+=template_rows(row,entry)
    fact=resources['official_templates_url']
    if fact['availability']=='found' and not any(e['url']==fact['value'] for e in entries):
        publisher=resources['official_template_publisher']
        entries.append(dict(base,category='official_template',title=identity['name_zh']+'官方PPT入口',url=fact['value'],
            publisher=publisher.get('value') or identity['name_zh'],official=True,use_scope='unspecified',formats='HTML/未知',edition_year=None,
            access_requirement=resources['official_template_terms'].get('value') or '访问条件以原发布页为准',download_status='indexed_not_fetched',
            content_read=None,source=fact['source'],source_sha256=None,repository=None,commit=None,license=None,usage_note=fact.get('note') or fact.get('basis')))
    for entry in resources.get('community_resources',[]):
        category=community_category(entry['kind'])
        formats=entry.get('formats') or {'beamer_theme':['LaTeX/Beamer'],'marp_theme':['Markdown/Marp'],'pptx_template':['PPTX']}.get(entry['kind'],['未知'])
        row=dict(base,category=category,title=entry['title'],url=entry['url'],publisher=entry['publisher'],official=False,
            use_scope='community',formats=';'.join(formats),edition_year=None,
            access_requirement='社区项目；格式、工具及素材权利见上游说明',download_status='source_text_read' if entry.get('source_text_read') or entry.get('content_read') else 'indexed_not_fetched',
            content_read=entry.get('source_text_read') or entry.get('content_read'),source=entry['source'],source_sha256=entry.get('source_sha256'),repository=entry.get('repository'),commit=entry['commit'],
            license=entry.get('license'),usage_note=entry['usage_note'])
        entries.append(row)
        for file in entry.get('files',[]):
            file_row=dict(row,title=file['path'],url=file['url'],formats=file['format'],content_read=file.get('content_read',False),
                          download_status=file.get('download_status') or 'indexed_not_fetched',**file_columns(file))
            entries.append(file_row);files+=template_rows(file_row,file)
    files=list({(f['url'],f['archive_member']):f for f in files}.values())
    logo=max(visual['logo_assets'],key=logo_score,default={});color=visual['color_primary']
    print_primary=next((c for c in visual['color_palette'] if c.get('method')=='official_vi' and c.get('role')=='primary' and c.get('value') is None),None)
    if print_primary and color.get('method')!='official_vi' and color['availability']!='conflict':
        if color['availability']=='found' and color.get('value'):
            color=dict(color,basis=color['basis']+'；独立来源的PPT设计参考，官方印刷值另列；此参考不是印刷色换算值或校方数字标准。')
        else:
            color=dict(print_primary,availability='official_print_only',basis=print_primary['basis']+'；无独立屏幕建议值，不换算CMYK/Pantone。')
    starter=dict(base,official_website=identity['official_website'].get('value'),profile_path=path.relative_to(ROOT).as_posix(),
        visual_path=path.with_name('VISUAL.md').relative_to(ROOT).as_posix(),logo_url=logo.get('url'),logo_kind=logo.get('kind'),
        logo_format=logo.get('format'),logo_official=logo.get('official'),logo_access_status=logo.get('access_status'),logo_source=logo.get('source'),logo_asset_id=logo.get('asset_id'),
        logo_download_kind=logo.get('download_kind'),logo_archive_url=logo.get('archive_url'),logo_archive_member=logo.get('archive_member'),logo_archive_sha256=logo.get('archive_sha256'),
        color_primary=color.get('value'),color_method=color.get('method'),color_status=color['availability'],color_label=color.get('label'),
        color_source=color.get('source'),color_basis=color.get('basis'),official_print_color_entries=sum(c.get('method')=='official_vi' and c.get('value') is None for c in visual['color_palette']),
        official_template_url=fact.get('value'),school_ppt_entries=sum(e['category']=='official_template' and e['use_scope']=='school' for e in entries),
        department_ppt_entries=sum(e['category']=='official_template' and e['use_scope']=='department' for e in entries),community_resource_entries=len(resources.get('community_resources',[])),
        school_ppt_file_count=sum(f['use_scope']=='school' for f in files),department_ppt_file_count=sum(f['use_scope']=='department' for f in files),
        community_ppt_file_count=sum(f['use_scope']=='community' for f in files))
    return starter,entries,files


def csv_text(rows,fields):
    buf=io.StringIO(newline='');writer=csv.DictWriter(buf,fieldnames=fields,lineterminator='\n');writer.writeheader();writer.writerows(rows);return '\ufeff'+buf.getvalue()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args()
    starter=[];resources=[];files=[]
    for path in sorted((ROOT/'universities').glob('*/*/profile.yaml')):
        s,r,f=rows_for(load_yaml(path.read_text()),path);starter.append(s);resources+=r;files+=f
    files=list({(f['school_code'],f['url'],f['archive_member']):f for f in files}.values())
    for filename,rows,fields in [('ppt-starter.csv',starter,STARTER_FIELDS),('ppt-resources.csv',resources,RESOURCE_FIELDS),('ppt-template-files.csv',files,TEMPLATE_FIELDS)]:
        output=ROOT/'indexes'/filename;expected=csv_text(rows,fields)
        if args.check:
            if not output.exists() or output.read_text()!=expected:raise ValueError('Stale PPT index: '+filename)
        else:output.write_text(expected,encoding='utf-8')
    print(('Checked' if args.check else 'Generated')+' PPT indexes: %s schools, %s resource references, %s inspected presentation files.'%(len(starter),len(resources),len(files)))


if __name__=='__main__':main()
