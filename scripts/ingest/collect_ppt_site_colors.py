#!/usr/bin/env python3
"""Read explicit homepage header/navigation colours as sourced PPT suggestions."""
import argparse
import collections
import concurrent.futures
import datetime as dt
import hashlib
import json
import pathlib
import re
import urllib.parse

import yaml

from collect_header_css_marks import HeaderPage
from collect_homepage_identity import ownership_evidence
from collect_official_extensions import decode, fetch
from discover_official_pages import matches_school_title
from expand_repository_fields import parse_hex
from profile_extensions import put_fact, rgb, upsert
from research_all_schools import Policy, SCHOOL_NAMES, same_school
from yaml_io import load_yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
REGION = re.compile(r'^(?:header|head|nav|navbox|navbar|navigation|topnav|top_nav|topbar|mainnav|main-nav|g-header)\d*$|(?:^|[_-])(?:header|head|nav)(?:$|[_-])|^top_info_bg$', re.I)
EXCLUDE = re.compile(r'footer|bottom|slide|news|search|login|wechat|qrcode|dropdown|submenu|subnav|small|mobile|hover|active|focus|after|before', re.I)
FRAMEWORK = re.compile(r'/_css/|/_js/|/system/resource/|(?:^|/)(?:swiper[^/]*|slick[^/]*|animate[^/]*|reset|iconfont|aos|bootstrap[^/]*)\.css(?:\?|$)', re.I)


def school_stylesheets(stylesheets):
    """Read the school's own styles before generic plugin and framework CSS."""
    return sorted(dict.fromkeys(stylesheets), key=lambda url: bool(FRAMEWORK.search(url)))[:8]


class ColorPage(HeaderPage):
    def __init__(self):
        super().__init__(); self.tokens = set(); self.tag_regions = set(); self.color_inline = []

    def handle_starttag(self, tag, attrs):
        super().handle_starttag(tag, attrs); attrs = dict(attrs)
        hidden, footer = self.flags()
        if hidden or footer:
            return
        for key in ('class', 'id'):
            self.tokens.update((attrs.get(key) or '').split())
        if tag in {'header', 'nav'}:
            self.tag_regions.add(tag)
        tokens = (attrs.get('class') or '').split() + [attrs.get('id') or '']
        if attrs.get('style') and (tag in {'header', 'nav'} or any(REGION.search(t) for t in tokens)):
            selector = tag + ''.join('.' + t for t in tokens if t)
            self.color_inline.append(selector + '{' + attrs['style'] + '}')


def candidates(css, tokens, tags):
    """Require the named header/nav region to exist in the inspected homepage."""
    out = []; css = re.sub(r'/\*[\s\S]*?\*/', '', css)
    for selectors, body in re.findall(r'([^{}]+)\{([^{}]*)\}', css):
        backgrounds = re.findall(r'(?:^|;)\s*background(?:-color)?\s*:\s*([^;]+)', body, re.I)
        if not backgrounds:
            continue
        for selector in selectors.split(','):
            selector = selector.strip()
            if not selector or EXCLUDE.search(selector) or re.search(r'[:\[\]@]|\b(?:li|a|p|span|img|button|input)\b', selector):
                continue
            named = re.findall(r'[.#]([A-Za-z_][\w-]*)', selector)
            if any(t not in tokens for t in named):
                continue
            terminal = re.split(r'\s+|[>+~]', selector)[-1]
            regions = [t for t in re.findall(r'[.#]([A-Za-z_][\w-]*)', terminal) if REGION.search(t)]
            region_tags = [t for t in tags if re.match(r'^' + t + r'(?:$|[.#])', terminal)]
            if not regions and not region_tags:
                continue
            for declaration in backgrounds:
                # A gradient or background image needs rendered interpretation;
                # this collector accepts only a literal single CSS colour.
                value = parse_hex(re.sub(r'\s*!important\s*$', '', declaration).strip())
                if value and max(rgb(value)) < 246:
                    out.append(dict(value=value, selector=selector[:160], declaration=declaration[:120]))
    return out


def collect(identity, previous=None):
    code, name, home = identity['school_code'], identity['name_zh'], identity['official_website']['value']
    r = dict(school_code=code, name_zh=name, home=home, checked_at=dt.date.today().isoformat(),
             status='access_or_identity_gap', pages=[], candidates=[], claims=[])
    policy = Policy()
    try:
        attempts=[]; r['attempts']=attempts
        parsed=urllib.parse.urlparse(home); response=None
        cache = ROOT / 'tmp/ppt-site-colors'; cache.mkdir(parents=True, exist_ok=True)
        if previous and previous.get('home') == home and previous.get('homepage_sha256'):
            cached = cache / (previous['homepage_sha256'] + '.html')
            if cached.exists() and hashlib.sha256(cached.read_bytes()).hexdigest() == previous['homepage_sha256']:
                response = (previous['homepage_source'], cached.read_bytes(), None, 'text/html')
                r['homepage_retrieval'] = 'hash_matched_previous_read'
                r['homepage_original_checked_at'] = previous['checked_at']
        variants = [home,parsed._replace(scheme='http' if parsed.scheme=='https' else 'https').geturl()]
        if parsed.path not in {'', '/'}:
            variants += [parsed._replace(path='/', query='', fragment='').geturl()]
        for url in dict.fromkeys(variants if response is None else []):
            attempt=dict(url=url);attempts.append(attempt)
            try:
                response=fetch(url,home,policy,timeout=12);attempt['status']='homepage_read';break
            except Exception as exc:
                attempt.update(status='access_gap',detail=str(exc)[:140])
                if str(exc) in {'robots_disallowed','redirect_robots_disallowed'}:break
        if response is None:raise ValueError('homepage_variants_unavailable')
        final, body, charset, mime = response
        if mime not in {'text/html', 'application/xhtml+xml'}:
            raise ValueError('homepage_not_html')
        page = ColorPage(); page.feed(decode(body, charset)); page.finish()
        if not (matches_school_title(name, page.title, SCHOOL_NAMES) or ownership_evidence(name, [t for _, t in page.lines], SCHOOL_NAMES)):
            raise ValueError('current_school_homepage_identity_gap')
        sha = hashlib.sha256(body).hexdigest(); r.update(homepage_sha256=sha, homepage_source=final)
        sources = [(final, sha, '\n'.join(page.styles + page.color_inline))]
        cached_sheets = {a.get('requested_url'): a for a in (previous or {}).get('pages', []) if a.get('status') == 'stylesheet_read'}
        for sheet in school_stylesheets(page.stylesheets):
            sheet = urllib.parse.urljoin(final, sheet)
            if not same_school(sheet, home):
                continue
            attempt = dict(requested_url=sheet); r['pages'].append(attempt)
            try:
                old = cached_sheets.get(sheet, {})
                saved = cache / (str(old.get('sha256')) + '.css')
                if saved.exists() and hashlib.sha256(saved.read_bytes()).hexdigest() == old.get('sha256'):
                    url, raw, encoding, kind = old['source_url'], saved.read_bytes(), None, 'text/css'
                    attempt['retrieval'] = 'hash_matched_previous_read'
                else:
                    url, raw, encoding, kind = fetch(sheet, home, policy, limit=800_000, timeout=15)
                digest = hashlib.sha256(raw).hexdigest()
                raw_cache=ROOT/'tmp/ppt-site-colors';raw_cache.mkdir(parents=True,exist_ok=True)
                (raw_cache/(digest+'.css')).write_bytes(raw)
                sources.append((url, digest, decode(raw, encoding)))
                attempt.update(status='stylesheet_read', source_url=url, sha256=digest)
            except Exception as exc:
                attempt.update(status='access_gap', detail=str(exc)[:120])
        cache = ROOT / 'tmp/ppt-site-colors'; cache.mkdir(parents=True, exist_ok=True)
        (cache / (sha + '.html')).write_bytes(body)
        for url, digest, css in sources:
            if not css:
                continue
            (cache / (digest + '.css.txt')).write_text(css, encoding='utf-8')
            r['candidates'] += [dict(c, source=url, source_sha256=digest) for c in candidates(css, page.tokens, page.tag_regions)]
        counts = collections.Counter(c['value'] for c in r['candidates'])
        if counts:
            value = counts.most_common(1)[0][0]
            chosen = next(c for c in r['candidates'] if c['value'] == value)
            basis = '已确认学校主页实际存在的页眉/主导航元素，其静态CSS规则明确背景色。按该颜色提供PPT设计建议，不认定学校官方VI标准；未执行脚本或宣称渲染后的最终视觉。'
            r['claims'].append(dict(chosen, field='visual.color_primary', basis=basis,
                                    homepage_source=final, homepage_sha256=sha))
            r['status'] = 'explicit_site_reference_color'
        else:
            r['status'] = 'no_literal_header_navigation_color'
    except Exception as exc:
        r.update(error_type=type(exc).__name__, detail=str(exc)[:140])
    return r


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collect-only', action='store_true'); parser.add_argument('--import-only', action='store_true')
    parser.add_argument('--workers', type=int, default=10)
    parser.add_argument('--retry-errors',action='store_true');args=parser.parse_args()
    paths = {p.parent.name:p for p in (ROOT / 'universities').glob('*/*/profile.yaml')}
    profiles = {c:load_yaml(p.read_text()) for c,p in paths.items()}
    out = ROOT / 'data/review/ppt-core-site-colors-2026.jsonl'
    records = {r['school_code']:r for r in map(json.loads, out.read_text().splitlines())} if out.exists() else {}
    def save():
        temp = out.with_suffix('.pending'); temp.write_text(''.join(json.dumps(records[c], ensure_ascii=False) + '\n' for c in sorted(records))); temp.replace(out)
    if not args.import_only:
        targets = [p['identity'] for c,p in profiles.items() if (c not in records or args.retry_errors and not records[c].get('claims')) and
                   p['visual']['color_primary']['availability'] == 'unresearched' and p['identity']['official_website'].get('value')]
        print('Homepage colour targets:', len(targets), flush=True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(collect, i, records.get(i['school_code'])) for i in targets]
            for n,f in enumerate(concurrent.futures.as_completed(futures), 1):
                r = f.result(); previous=records.get(r['school_code'])
                if previous:r['previous_attempts']=previous.get('previous_attempts',[])+[{k:v for k,v in previous.items() if k!='previous_attempts'}]
                records[r['school_code']] = r
                if n % 20 == 0:
                    save(); print('Read', n, '/', len(targets), '; explicit colours:', sum(bool(r['claims']) for r in records.values()), flush=True)
        save()
    if args.collect_only:
        return
    changed = 0
    for code,r in records.items():
        p = load_yaml(paths[code].read_text())
        for c in r['claims']:
            group, key = c['field'].split('.')
            if p[group][key]['availability'] != 'unresearched':
                continue
            meta = dict(source=c['source'], source_type='official_website', checked_at=r['checked_at'], verified='auto',
                        method='manual_derived', source_sha256=c['source_sha256'], homepage_source=c['homepage_source'],
                        homepage_sha256=c['homepage_sha256'], css_selector=c['selector'], css_declaration=c['declaration'], collector='ppt_site_reference')
            if put_fact(p, c['field'], c['value'], meta, basis=c['basis']):
                upsert(p['visual']['color_palette'], dict(value=c['value'], rgb=rgb(c['value']), cmyk=None, pantone=None,
                    label='官网页眉/导航PPT建议色', role='reference', official=False, availability='found', basis=c['basis'], **meta),
                    lambda x:(x['source'], x['value'], x['method']))
                paths[code].write_text(yaml.safe_dump(p, allow_unicode=True, sort_keys=False, width=100)); changed += 1
    print('Site reference colours added:', changed)


if __name__ == '__main__':
    main()
