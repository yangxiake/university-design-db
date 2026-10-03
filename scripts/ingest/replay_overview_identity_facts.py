#!/usr/bin/env python3
"""Recover unambiguous school identity/culture facts from read overview pages."""
import argparse
import collections
import hashlib
import json
import pathlib
import re
import yaml
from collect_official_extensions import Page, decode
from collect_visual_directory import page_identity
from profile_extensions import put_fact
from ppt_core_extraction import additional_claims
from research_all_schools import extract_claims, same_school

ROOT = pathlib.Path(__file__).resolve().parents[2]
FIELDS = {'identity.name_en', 'culture.founded_year', 'culture.motto', 'culture.anthem', 'culture.flower', 'culture.mascot'}


def institution_claims(name, lines, source):
    """Read explicit present school descriptions, excluding predecessor claims."""
    out=[]
    subject = r'(?:'+re.escape(name)+r'(?!学报|研究院|附属|实验室|[\u4e00-\u9fff]{1,6}联合学院)|学校|我校)'
    for line in lines:
        line=re.sub(r'\s+','',line)
        for sentence in re.split(r'[。！？;；\n]',line):
            if len(sentence)>700:continue
            match=re.search(subject+r'[^。]{0,60}?(?:是一所|是|系|现已成为|现已发展为|为一所)([^。]{0,150})',sentence)
            if not match or re.search(r'前身|原为|曾经|曾是|民办转公办|公办转民办',match[0]):continue
            description=match[1]
            natures=list(dict.fromkeys(re.findall(r'(公办|民办)(?:全日制|省属|普通|本科|应用型|理工类|综合性|高等|职业|教育|新型|研究型|传媒类|的|、|本科层次|专科|艺术类|全日制普通){0,10}(?:大学|学院|高等学校|高校|院校|学校)',description)))
            if len(natures)==1 and not re.search(r'非公办|非民办|其他高校|另一所|合作高校|(?:德国|美国|英国|法国|韩国|日本|加拿大|澳大利亚)公办',description):
                out.append(dict(field='institution.nature',value=natures[0],source=source,
                    basis='官网简介明确描述本校当前办学性质；未从教育部空备注或主管单位推断。',evidence=match[0]))
            types=re.findall(r'(综合性|理工类|师范类|医药类|艺术类|体育类|财经类|语言类|农业类|林业类)(?:应用型|全日制|地方性|本科|普通|职业|民办|公办|高等|研究型|教学型|的|、|，|多科性|艺术|本科层次){0,10}(?:大学|学院|院校|高校|高等学校|学府)',description)
            if len(set(types))==1:
                value={'综合性':'综合'}.get(types[0],types[0].replace('类',''))
                out.append(dict(field='institution.school_type',value=value,source=source,
                    basis='官网简介明示的学校类型；不是从校名或专业名称推断的分类。',evidence=match[0]))
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipts', required=True, action='append')
    parser.add_argument('--output', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    paths = {p.parent.name: p for p in (ROOT/'universities').glob('*/*/profile.yaml')}
    profiles = {c: yaml.load(p.read_text(), Loader=yaml.CSafeLoader) for c, p in paths.items()}
    candidates = collections.defaultdict(list)
    seen = set()
    for f in args.receipts:
        for record in map(json.loads, (ROOT/f).read_text().splitlines()):
            code, name = record['school_code'], record['name_zh']
            profile = profiles[code]
            if name != profile['identity']['name_zh']:
                raise ValueError('school_identity_mismatch')
            home = profile['identity']['official_website'].get('value')
            if not home: continue
            for page_record in record.get('pages', []):
                source = page_record.get('source_url')
                sha = page_record.get('sha256')
                if not source or not sha or page_record.get('status') != 'read' or source == record.get('home'):
                    continue
                if (code, source, sha) in seen or not same_school(source, home): continue
                seen.add((code, source, sha))
                cache = ROOT/'tmp/overviews'/code/(sha+'.html')
                if not cache.exists(): continue
                body = cache.read_bytes()
                if hashlib.sha256(body).hexdigest() != sha: raise ValueError('source_hash_mismatch')
                page = Page(); page.feed(decode(body, None)); page.finish()
                if not page_identity(name, page): continue
                text = '\n'.join(t for _, t in page.lines)
                kind = 'charter' if '章程' in page.title else 'overview'
                for claim in extract_claims(name, kind, page.title, text, source) + additional_claims(name, kind, page.title, text, source):
                    if claim['field'] not in FIELDS: continue
                    group, field = claim['field'].split('.')
                    if profile[group][field]['availability'] not in {'unresearched', 'not_found'} or profile[group][field].get('verified') == 'human': continue
                    claim.update(source_sha256=sha, checked_at=record['checked_at'])
                    candidates[(code, claim['field'])].append(claim)
    audit, changed = [], set()
    for (code, field), claims in sorted(candidates.items()):
        by_value = {json.dumps(c['value'], ensure_ascii=False, sort_keys=True): c for c in claims}
        status = 'multiple_values_require_review' if len(by_value) > 1 else 'unambiguous_fact'
        entry = dict(school_code=code, name_zh=profiles[code]['identity']['name_zh'], field=field, status=status, candidates=list(by_value.values()))
        if len(by_value) == 1:
            claim = next(iter(by_value.values())); group, key = field.split('.')
            current = profiles[code][group][key]
            previous_status = current['availability']
            # An actual positive official statement may resolve an earlier
            # bounded negative search. Conflicts and human decisions are kept.
            if previous_status == 'not_found':
                from profile_extensions import empty_fact
                profiles[code][group][key] = empty_fact()
            if put_fact(profiles[code], field, claim['value'], dict(source=claim['source'],
                    source_type='official_website', verified='auto', checked_at=claim['checked_at'],
                    source_sha256=claim['source_sha256'], collector='read_overview_identity_facts'),
                    basis=claim.get('basis', '学校官网简介页直接记载的本校事实'), previous_status=previous_status):
                changed.add(code)
        audit.append(entry)
    if args.apply:
        for code in changed:
            paths[code].write_text(yaml.safe_dump(profiles[code], allow_unicode=True, sort_keys=False, width=100), encoding='utf-8')
    (ROOT/args.output).write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in audit), encoding='utf-8')
    print('Cached overview pages:', len(seen), '; changed schools:', len(changed), '; facts:', sum(r['status']=='unambiguous_fact' for r in audit), '; ambiguous:', sum(r['status']!='unambiguous_fact' for r in audit))


if __name__ == '__main__': main()
