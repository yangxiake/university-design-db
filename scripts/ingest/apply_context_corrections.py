#!/usr/bin/env python3
"""Apply explicit AI context decisions and retain rejected historical candidates."""
import csv,datetime as dt,json,pathlib,re
import yaml
ROOT=pathlib.Path(__file__).resolve().parents[2]

def normalized(value):
    return re.sub(r'[\s，,、；;·]','',str(value))

def main():
    decisions=yaml.safe_load((ROOT/'data/review/context-corrections-2026.yaml').read_text())
    with (ROOT/'data/universities-scope-2026.csv').open(encoding='utf-8-sig') as handle:
        scope={r['school_code']:r for r in csv.DictReader(handle)}
    ledger_path=ROOT/'data/review/school-research-2026.jsonl'
    ledger=[json.loads(line) for line in ledger_path.read_text().splitlines()]
    by_code={r['school_code']:r for r in ledger};today=dt.date.today().isoformat();facts=removed=0
    for decision in decisions:
        row=scope[decision['school_code']]
        if row['name_zh']!=decision['name_zh']:raise ValueError('Scope identity differs')
        path=ROOT/'universities'/row['province']/row['school_code']/'profile.yaml'
        profile=yaml.safe_load(path.read_text())
        if profile['research']['status']=='reviewed':continue
        record=by_code.get(row['school_code'])
        if record:
            for exclusion in decision.get('excluded_claims',[]):
                values={normalized(value) for value in exclusion['values']};retained=[]
                for claim in record['claims']:
                    if claim['field']==exclusion['field'] and normalized(claim['value']) in values:
                        rejected=dict(claim,reason=exclusion['reason'],context_source=exclusion['context_source'])
                        items=record.setdefault('rejected_context_claims',[])
                        if rejected not in items:items.append(rejected);removed+=1
                    else:retained.append(claim)
                record['claims']=retained
        for field, specification in decision['facts'].items():
            group,key=field.split('.');old=profile[group][key]
            if old.get('verified')=='human':continue
            old.clear();old.update(specification,verified='auto',availability='found',checked_at=today,search_sources=[])
            facts+=1
        events=profile['culture']['history_events']
        for event in decision.get('history_events',[]):
            if not any(item['year']==event['year'] and item['event']==event['event'] for item in events) and len(events)<5:
                events.append(dict(event,verified='auto',checked_at=today))
        profile['research'].update(status='auto_collected',checked_at=today)
        path.write_text(yaml.safe_dump(profile,allow_unicode=True,sort_keys=False,width=100))
    temporary=ledger_path.with_suffix('.jsonl.tmp')
    temporary.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in ledger));temporary.replace(ledger_path)
    print('Applied',facts,'context decisions; retained',removed,'excluded claims in the audit ledger.')
if __name__=='__main__':main()
