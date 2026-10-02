#!/usr/bin/env python3
"""Index pinned school logo layouts; read selected SVG/PNG as data only."""
import argparse
import concurrent.futures
import copy
import hashlib
import json
import pathlib
import re
import subprocess
import urllib.request

import yaml
from expand_repository_fields import asset_entry,inspect_asset,apply_visual_result

ROOT=pathlib.Path(__file__).resolve().parents[2]
OUTPUT=ROOT/'data/review/logo-layout-metadata-2026.json'


def layout_kind(folder):
    if folder=='校徽':return 'badge'
    if folder.startswith('中文校名'):return 'wordmark'
    if folder.startswith('校徽+'):return 'combination'
    return None


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--collect-only',action='store_true');parser.add_argument('--import-only',action='store_true');args=parser.parse_args()
    specs=yaml.safe_load((ROOT/'data/review/logo-layout-sources-2026.yaml').read_text())
    if not args.import_only:
        receipts=[]
        for spec in specs:
            repo,commit=spec['repository'],spec['commit']
            url='https://raw.githubusercontent.com/'+repo+'/'+commit+'/README.md'
            req=urllib.request.Request(url,headers={'User-Agent':'university-design-db/1.0'})
            with urllib.request.urlopen(req,timeout=20) as response:body=response.read(200001)
            if len(body)>200000 or spec['name_zh'] not in body.decode():raise ValueError('README identity or size gap')
            tree=json.loads(subprocess.check_output(['gh','api','repos/'+repo+'/git/trees/'+commit+'?recursive=1']))
            if tree.get('truncated'):raise ValueError('incomplete file tree')
            assets=[]
            for file in tree['tree']:
                path=file['path'];folder=path.split('/')[0];kind=layout_kind(folder)
                if file['type']!='blob' or not kind or not re.search(r'\.(svg|pdf|png)$',path,re.I):continue
                a=asset_entry(spec,spec['name_zh'],path,kind=kind)
                a.update(title=spec['name_zh']+'：'+path,variant=folder+'；'+('黑色' if '_黑色' in path else '蓝色' if '_蓝色' in path else '原标签'),
                         identity_basis=spec['identity_basis'],source_type='community_repository',source_sha256=hashlib.sha256(body).hexdigest())
                dimensions=re.search(r'_(\d+x\d+)\.png$',path)
                if dimensions:a['dimensions_in_filename']=dimensions[1]
                selected=path.lower().endswith('.svg') or '_蓝色' in path and path.lower().endswith('.png') and dimensions and '1024' in dimensions[1]
                assets.append(dict(asset=a,inspect=bool(selected)))
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                pending=[r for r in assets if r['inspect']]
                for r,meta in zip(pending,pool.map(lambda r:inspect_asset(r['asset']),pending)):r['inspection']=meta
            receipts.append(dict(spec,readme_sha256=hashlib.sha256(body).hexdigest(),assets=assets))
        OUTPUT.write_text(json.dumps(receipts,ensure_ascii=False,indent=2)+'\n')
    if args.collect_only:return
    paths={p.parent.name:p for p in (ROOT/'universities').glob('*/*/profile.yaml')}
    for r in json.loads(OUTPUT.read_text()):
        path=paths[r['school_code']];p=yaml.safe_load(path.read_text())
        if p['identity']['name_zh']!=r['name_zh']:raise ValueError('school identity gap')
        for a in r['assets']:apply_visual_result(p,copy.deepcopy(a['asset']),copy.deepcopy(a.get('inspection') or {}))
        path.write_text(yaml.safe_dump(p,allow_unicode=True,sort_keys=False,width=100))
    print('Imported pinned logo layout metadata.')


if __name__=='__main__':main()
