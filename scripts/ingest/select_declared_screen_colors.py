#!/usr/bin/env python3
"""Offer a declared web HEX as a PPT suggestion while preserving VI conflicts."""
import copy
import datetime as dt
import json
import pathlib

import yaml

from profile_extensions import rgb, upsert
from yaml_io import load_yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]


def select(fact, decision):
    if fact['availability'] != 'conflict' or fact.get('verified') == 'human':
        return None
    if sorted(c['value'] for c in fact.get('candidates', [])) != sorted(decision['expected_candidates']):
        raise ValueError('source_numeric_candidates_changed')
    chosen = next((c for c in fact['candidates'] if c['value'] == decision['value']), None)
    if not chosen:
        raise ValueError('screen_hex_not_a_sourced_candidate')
    basis = ('PPT屏幕设计建议：采用学校原文明确列出的WEB/HEX色值%s。原资料的RGB与HEX仍不一致，'
             '原始数值冲突完整保留；此为建议色选择，不是校方确认的唯一官方标准。%s' %
             (chosen['value'], decision['evidence_basis']))
    return dict(value=chosen['value'], source=chosen['source'], source_type='official_website',
        verified='auto', checked_at=dt.date.today().isoformat(), availability='found', search_sources=[],
        method='manual_derived', official=False, basis=basis,
        collector='declared_hex_ppt_suggestion', official_numeric_conflict=copy.deepcopy(fact))


def main():
    paths={p.parent.name:p for p in (ROOT/'universities').glob('*/*/profile.yaml')}
    decisions=load_yaml((ROOT/'data/review/ppt-core-screen-color-decisions-2026.yaml').read_text())
    changes=[]
    for d in decisions:
        path=paths[d['school_code']];p=load_yaml(path.read_text())
        if p['identity']['name_zh']!=d['name_zh']:
            raise ValueError('screen_decision_identity_mismatch')
        result=select(p['visual']['color_primary'],d)
        if result is None:
            continue
        previous=copy.deepcopy(p['visual']['color_primary']);p['visual']['color_primary']=result
        entry={k:v for k,v in result.items() if k not in {'search_sources','official_numeric_conflict'}}
        entry.update(rgb=rgb(result['value']),cmyk=None,pantone=None,role='reference',label='官网HEX的PPT屏幕建议色')
        upsert(p['visual']['color_palette'],entry,lambda c:(c['source'],c['value'],c['method']))
        path.write_text(yaml.safe_dump(p,allow_unicode=True,sort_keys=False,width=100))
        changes.append(dict(decision=d,previous=previous,ppt_suggestion=result['value'],basis=result['basis']))
    audit=ROOT/'data/review/ppt-core-screen-color-changes-2026.jsonl'
    old=[json.loads(s) for s in audit.read_text().splitlines()] if audit.exists() else []
    audit.write_text(''.join(json.dumps(c,ensure_ascii=False)+'\n' for c in old+changes))
    print('Sourced screen suggestions added:',len(changes),'; original VI conflicts preserved')


if __name__=='__main__':
    main()
