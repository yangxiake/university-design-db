#!/usr/bin/env python3
"""Read source-selected core candidates; import only text-bound evidence.

The candidate file is data for review, never instructions. An exact current
school name and the selected evidence phrase must occur in the fetched text.
Existing positive facts and human decisions are preserved.
"""
import argparse
import concurrent.futures
import copy
import datetime as dt
import hashlib
import io
import json
import pathlib
import urllib.parse

import yaml
from pypdf import PdfReader
from collect_official_extensions import Page, decode, fetch
from ppt_scope import is_core_field
from profile_extensions import put_fact
from research_all_schools import Policy
from research_all_schools import same_school
from yaml_io import load_yaml

ROOT=pathlib.Path(__file__).resolve().parents[2]
CACHE=ROOT/'tmp/ppt-core-curated'


def norm(s): return ''.join(str(s).split())


def identity_matches(candidate, text, profile):
    if norm(candidate['name_zh']) in norm(text):
        return True
    home = profile['identity']['official_website']
    return (candidate.get('identity_basis') == 'confirmed_current_school_domain' and
            candidate['source_type'] == 'official_website' and home['availability'] == 'found' and
            same_school(candidate['source'], home['value']))


def collect(job):
    code,name,url=job
    r=dict(school_code=code,name_zh=name,source=url,checked_at=dt.date.today().isoformat(),status='access_or_identity_gap',attempts=[])
    policy=Policy();parsed=urllib.parse.urlparse(url)
    for target in dict.fromkeys([url,parsed._replace(scheme='http' if parsed.scheme=='https' else 'https').geturl()]):
        attempt=dict(url=target);r['attempts'].append(attempt)
        try:
            final,raw,charset,mime=fetch(target,url,policy,20_000_000,timeout=12)
            if raw.startswith(b'%PDF-'):
                text='\n'.join(p.extract_text() or '' for p in PdfReader(io.BytesIO(raw)).pages);suffix='.pdf';title=''
            elif mime in {'text/html','application/xhtml+xml'}:
                page=Page();page.feed(decode(raw,charset));page.finish();text='\n'.join(t for _,t in page.lines);title=page.title;suffix='.html'
            else:raise ValueError('source_not_text_document')
            if norm(name) not in norm(text):raise ValueError('current_full_school_name_not_in_source')
            sha=hashlib.sha256(raw).hexdigest();CACHE.mkdir(parents=True,exist_ok=True);(CACHE/(sha+suffix)).write_bytes(raw)
            r.update(source=final,source_sha256=sha,status='current_school_source_read',title=title[:180],cache_suffix=suffix)
            attempt.update(status='source_read',source=final,source_sha256=sha);break
        except Exception as exc:
            attempt.update(status='access_or_identity_gap',detail=str(exc)[:140],error_type=type(exc).__name__)
            if str(exc) in {'robots_disallowed','redirect_robots_disallowed','cross_school_redirect'}:break
    return r


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collect-only',action='store_true');parser.add_argument('--import-only',action='store_true');parser.add_argument('--retry-errors',action='store_true')
    parser.add_argument('--workers',type=int,default=4);args=parser.parse_args()
    candidates=load_yaml((ROOT/'data/review/ppt-core-curated-candidates-2026.yaml').read_text())
    paths={p.parent.name:p for p in (ROOT/'universities').glob('*/*/profile.yaml')}
    for c in candidates:
        p=load_yaml(paths[c['school_code']].read_text())
        if p['identity']['name_zh']!=c['name_zh'] or not is_core_field(c['field']):raise ValueError('candidate_identity_or_field_mismatch')
    out=ROOT/'data/review/ppt-core-curated-sources-2026.jsonl'
    records={(r['school_code'],r['requested_source']):r for r in map(json.loads,out.read_text().splitlines())} if out.exists() else {}
    def save():
        temp=out.with_suffix('.pending');temp.write_text(''.join(json.dumps(records[k],ensure_ascii=False)+'\n' for k in sorted(records)));temp.replace(out)
    if not args.import_only:
        jobs=list(dict.fromkeys((c['school_code'],c['name_zh'],c['source']) for c in candidates if (c['school_code'],c['source']) not in records or
            (args.retry_errors and records[(c['school_code'],c['source'])]['status']!='current_school_source_read')))
        print('Curated core sources queued:',len(jobs),flush=True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures={pool.submit(collect,j):j for j in jobs}
            for future in concurrent.futures.as_completed(futures):
                code,name,url=futures[future];r=future.result();r['requested_source']=url;records[(code,url)]=r;save()
    if args.collect_only:return
    web_path=ROOT/'data/review/ppt-core-web-evidence-2026.yaml'
    web_evidence={(r['school_code'],r['source']):r for r in load_yaml(web_path.read_text())} if web_path.exists() else {}
    changes=[]
    for c in candidates:
        r=records.get((c['school_code'],c['source']))
        if not r or r['status']!='current_school_source_read':
            same=next((s for s in records.values() if s['requested_source']==c['source'] and s['status']=='current_school_source_read'),None)
            if same:r=dict(same,school_code=c['school_code'],name_zh=c['name_zh'],retrieval='hash_matched_same_source')
            else:
                proof=web_evidence.get((c['school_code'],c['source']))
                if not proof or proof['name_zh']!=c['name_zh'] or proof['retrieval'] not in {'web_text_view','web_search_excerpt'}:continue
                text=proof['evidence_excerpt'];r=dict(proof,status='current_school_source_read',source_sha256=None)
        if r.get('source_sha256'):
            raw=(CACHE/(r['source_sha256']+r['cache_suffix'])).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=r['source_sha256']:raise ValueError('curated_source_hash_mismatch')
            if r['cache_suffix']=='.pdf':text='\n'.join(p.extract_text() or '' for p in PdfReader(io.BytesIO(raw)).pages)
            else:
                page=Page();page.feed(decode(raw,None));page.finish();text='\n'.join(t for _,t in page.lines)
        else:
            text=r['evidence_excerpt']
        path=paths[c['school_code']];p=load_yaml(path.read_text())
        if not identity_matches(c,text,p):continue
        if norm(c['evidence_phrase']) not in norm(text):
            c['evidence_status']='selected_phrase_not_in_fetched_text';continue
        g,k=c['field'].split('.')
        previous=p[g][k]
        resolve=(c.get('resolve_conflict') is True and previous['availability']=='conflict'
                 and previous.get('verified')!='human'
                 and sorted(str(x['value']) for x in previous.get('candidates',[]))==
                     sorted(str(x) for x in c.get('expected_candidates',[])))
        if previous['availability']!='unresearched' and not resolve:continue
        meta=dict(source=r['source'],source_type=c['source_type'],verified='auto',checked_at=r['checked_at'],
            evidence=c['evidence_phrase'],collector='curated_ppt_core',retrieval=r.get('retrieval','direct_http'))
        if r.get('source_sha256'):meta['source_sha256']=r['source_sha256']
        if resolve:
            p[g][k]=dict(value=c['value'],availability='found',search_sources=[],basis=c['basis'],**meta)
            changed=True
        else:
            changed=put_fact(p,c['field'],c['value'],meta,basis=c['basis'])
        if changed:
            path.write_text(yaml.safe_dump(p,allow_unicode=True,sort_keys=False,width=100))
            change=dict(c,source_sha256=r.get('source_sha256'))
            if resolve:change.update(previous=copy.deepcopy(previous),status='source_checked_historical_basis_resolution')
            changes.append(change)
    audit=ROOT/'data/review/ppt-core-curated-changes-2026.jsonl'
    old=[json.loads(s) for s in audit.read_text().splitlines()] if audit.exists() else []
    audit.write_text(''.join(json.dumps(c,ensure_ascii=False)+'\n' for c in old+changes))
    print('Curated core facts added:',len(changes),'; source receipts:',len(records),flush=True)


if __name__=='__main__':main()
