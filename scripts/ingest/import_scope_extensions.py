#!/usr/bin/env python3
"""Fill v3 school nature only from explicit Ministry registry remarks."""
import csv
import datetime as dt
import pathlib
import yaml
from profile_extensions import put_fact

ROOT=pathlib.Path(__file__).resolve().parents[2]


def main():
    with (ROOT/'data/universities-scope-2026.csv').open(encoding='utf-8-sig') as f:rows={r['school_code']:r for r in csv.DictReader(f)}
    count=0
    for path in sorted((ROOT/'universities').glob('*/*/profile.yaml')):
        p=yaml.safe_load(path.read_text());i=p['identity'];row=rows[i['school_code']];note=row['note'].strip()
        # Empty remarks do not imply public ownership. Cooperative education
        # remarks describe a distinct arrangement, not necessarily ownership.
        if note!='民办':continue
        meta=dict(source=i['registry_source'],source_type='official_registry',verified='auto',checked_at=dt.date.today().isoformat(),source_as_of='2026-06-17')
        if put_fact(p,'institution.nature','民办',meta,basis='教育部2026全国高等学校名单的本科院校备注明确记为“民办”。空备注未据此推断为公办。'):
            path.write_text(yaml.safe_dump(p,allow_unicode=True,sort_keys=False,width=100),encoding='utf-8');count+=1
    print('Explicit Ministry school-nature facts added:',count)


if __name__=='__main__':main()
