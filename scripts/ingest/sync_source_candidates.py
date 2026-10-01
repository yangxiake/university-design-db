#!/usr/bin/env python3
"""Make unresolved website leads available in the school archive without asserting ownership."""
import collections
import csv
import datetime as dt
import pathlib
import yaml
ROOT=pathlib.Path(__file__).resolve().parents[2]

def main():
    leads=collections.defaultdict(list)
    with (ROOT/'data/review/official-site-overrides-2026.csv').open(encoding='utf-8-sig',newline='') as f:
        for row in csv.DictReader(f):
            if row['evidence_url']:
                leads[row['school_code']].append(dict(url=row['candidate_url'].strip(),source=row['evidence_url'],note=row['note'],status='unverified_candidate'))
    count=0
    for path in (ROOT/'universities').glob('*/*/profile.yaml'):
        p=yaml.safe_load(path.read_text(encoding='utf-8'))
        if p['identity']['official_website']['availability']=='found':
            p['research'].pop('website_candidates',None)
            p['research'].pop('website_candidates_updated_at',None)
        else:
            seen=set();items=[]
            for item in leads[p['identity']['school_code']]:
                if item['url'] in seen:continue
                seen.add(item['url']);items.append(item)
                if len(items)==5:break
            if items:
                p['research']['website_candidates']=items;count+=1
                p['research']['website_candidates_updated_at']=dt.date.today().isoformat()
        path.write_text(yaml.safe_dump(p,allow_unicode=True,sort_keys=False,width=100),encoding='utf-8')
    print('Recorded sourced, unconfirmed website candidates in',count,'school archives.')
if __name__=='__main__':main()
