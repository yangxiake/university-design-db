#!/usr/bin/env python3
"""Read selected official VI sources; keep receipts without changing school facts."""
import argparse
import concurrent.futures
import datetime as dt
import hashlib
import io
import json
import pathlib
import re
import urllib.parse
import unicodedata
from html.parser import HTMLParser

import yaml
from pypdf import PdfReader
from collect_official_extensions import decode, fetch
from research_all_schools import Policy, same_school
from inspect_template_files import collect as collect_template
from expand_repository_fields import inspect_bytes

ROOT = pathlib.Path(__file__).resolve().parents[2]


class References(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ''
        self.in_title = False
        self.links = []
        self.images = []
        self.current = None
        self.text = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'title':
            self.in_title = True
        if tag == 'a' and a.get('href'):
            self.current = dict(url=a['href'], label='')
            self.links.append(self.current)
        if tag == 'img':
            src = a.get('data-original') or a.get('data-src') or a.get('src')
            if src:
                self.images.append(dict(url=src, label=a.get('alt') or a.get('title') or ''))

    def handle_endtag(self, tag):
        if tag == 'title':
            self.in_title = False
        if tag == 'a':
            self.current = None

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        if self.current is not None:
            self.current['label'] += data.strip()
        self.text.append(data)


def collect(target):
    result = {k: target[k] for k in ('school_code', 'name_zh', 'home', 'url', 'purpose')}
    result.update(checked_at=dt.date.today().isoformat(), status='access_gap', attempts=[])
    if target.get('format') in {'PPTX', 'ZIP'}:
        receipt = collect_template(dict(school_code=target['school_code'], name_zh=target['name_zh'],
                                        url=target['url'], source=target.get('source', target['home']), community=False))
        result.update(receipt)
        return result
    policy = Policy()
    parsed = urllib.parse.urlparse(target['url'])
    urls = [target['url'], parsed._replace(scheme='http' if parsed.scheme == 'https' else 'https').geturl()]
    for url in dict.fromkeys(urls):
        attempt = dict(requested_url=url)
        result['attempts'].append(attempt)
        try:
            final, body, charset, mime = fetch(url, target['home'], policy, 50_000_000, timeout=target.get('timeout', 10))
            sha = hashlib.sha256(body).hexdigest()
            metadata = dict(resolved_url=final, source_sha256=sha, byte_size=len(body), mime=mime)
            if body.startswith(b'%PDF-'):
                reader = PdfReader(io.BytesIO(body))
                text = '\n'.join(p.extract_text() or '' for p in reader.pages)
                compact = ''.join(unicodedata.normalize('NFKC', text).split())
                identity_match = any(''.join(unicodedata.normalize('NFKC', token).split()) in compact for token in [target['name_zh']] + target.get('identity_tokens', []))
                metadata.update(format='PDF', page_count=len(reader.pages), identity_match=identity_match,
                                identity_review='text_matched' if identity_match else 'requires_visual_review')
            elif mime in {'text/html', 'application/xhtml+xml'}:
                html = decode(body, charset)
                if re.search(r'/authserver/|/cas/login|/login(?:[.?/]|$)', final, re.I) or re.search(r'<input[^>]+type\s*=\s*[\"\']?password(?:[\s\"\'>]|$)', html, re.I):
                    raise ValueError('authentication_required')
                page = References()
                page.feed(html)
                if not any(token in ''.join(page.text) for token in [target['name_zh']] + target.get('identity_tokens', [])):
                    raise ValueError('HTML school identity not confirmed by text')
                def refs(values):
                    unique = {}
                    for v in values:
                        u = urllib.parse.urljoin(final, v['url']).split('#')[0]
                        if same_school(u, target['home']):
                            unique.setdefault(u, dict(url=u, label=v['label'].strip()[:140]))
                    return list(unique.values())
                metadata.update(format='HTML', title=page.title.strip()[:180], identity_match=True,
                                identity_review='text_matched', links=refs(page.links), images=refs(page.images))
            elif mime.startswith('image/'):
                picture = inspect_bytes(body, final)
                metadata.update(format=picture['format'].upper(), width=picture.get('width'), height=picture.get('height'),
                                vector=picture.get('vector'), identity_match=False, identity_review='requires_visual_review')
            else:
                raise ValueError('Expected an official HTML, PDF or image source')
            cache = ROOT / 'tmp/targeted-vi'
            cache.mkdir(parents=True, exist_ok=True)
            suffix = '.html' if metadata['format'] == 'HTML' else '.' + metadata['format'].lower()
            (cache / (sha + suffix)).write_bytes(body)
            attempt.update(status='source_read', **metadata)
            result.update(status='source_read', **metadata)
            break
        except Exception as exc:
            attempt.update(status='access_gap', error_type=type(exc).__name__, detail=str(exc)[:180])
            if not isinstance(exc, OSError):
                break
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--targets', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--timeout', type=int, default=10, help='Bounded request/read timeout (1-60 seconds)')
    parser.add_argument('--retry-errors', action='store_true')
    parser.add_argument('--format', choices=['PPTX', 'ZIP'], help='Collect only selected file formats')
    parser.add_argument('--school-code', action='append', help='Read only selected schools')
    args = parser.parse_args()
    if not 1 <= args.timeout <= 60:
        parser.error('--timeout must be between 1 and 60 seconds')
    targets = yaml.safe_load((ROOT / args.targets).read_text())
    if args.format:
        targets = [t for t in targets if t.get('format') == args.format]
    if args.school_code:
        targets = [t for t in targets if t['school_code'] in args.school_code]
    paths = {p.parent.name: p for p in (ROOT / 'universities').glob('*/*/profile.yaml')}
    for target in targets:
        target['timeout'] = args.timeout
        p = yaml.load(paths[target['school_code']].read_text(), Loader=yaml.CSafeLoader)
        if p['identity']['name_zh'] != target['name_zh'] or not same_school(target['url'], target['home']):
            raise ValueError('School or source domain mismatch')
        known_home = p['identity']['official_website'].get('value')
        if known_home and not same_school(target['home'], known_home):
            raise ValueError('Target conflicts with the recorded school domain')
    output = ROOT / args.output
    records = {(r['school_code'], r['url']): r for r in map(json.loads, output.read_text().splitlines())} if output.exists() else {}
    pending = [t for t in targets if (t['school_code'], t['url']) not in records or
               (args.retry_errors and records[(t['school_code'], t['url'])]['status'] not in {'source_read', 'content_inspected', 'format_only', 'target_page_read'})]
    def save():
        temporary = output.with_suffix('.pending')
        temporary.write_text(''.join(json.dumps(records[k], ensure_ascii=False, sort_keys=True) + '\n' for k in sorted(records)))
        temporary.replace(output)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        jobs = {pool.submit(collect, t): (t['school_code'], t['url']) for t in pending}
        for job in concurrent.futures.as_completed(jobs):
            key = jobs[job]
            current = job.result()
            if key in records:
                previous = {k: v for k, v in records[key].items() if k != 'previous_attempts'}
                current['previous_attempts'] = records[key].get('previous_attempts', []) + [previous]
            records[key] = current
            save()
            print(current['name_zh'], current['status'], current.get('format'), flush=True)
    print('Receipts:', len(records), '; sources read:', sum(r['status'] == 'source_read' for r in records.values()))


if __name__ == '__main__':
    main()
