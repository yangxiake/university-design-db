#!/usr/bin/env python3
"""Re-read existing inspected logo URLs only when their colour cache is absent."""
import argparse
import concurrent.futures
import datetime as dt
import hashlib
import json
import pathlib

from collect_official_extensions import fetch
from fill_monochrome_primary import cached_bytes
from research_all_schools import Policy
from yaml_io import load_yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]


def read(job):
    code, name, asset = job
    result = dict(school_code=code, name_zh=name, asset_id=asset['asset_id'], url=asset['url'],
                  expected_sha256=asset['sha256'], checked_at=dt.date.today().isoformat())
    try:
        final, body, charset, mime = fetch(asset['url'], asset['url'], Policy(), limit=20_000_000, timeout=12)
        sha = hashlib.sha256(body).hexdigest()
        result.update(source_url=final, sha256=sha, byte_size=len(body))
        if sha != asset['sha256']:
            result['status'] = 'content_changed_requires_new_inspection'
        else:
            folder = ROOT / 'tmp/targeted-vi'; folder.mkdir(parents=True, exist_ok=True)
            (folder / (sha + '.graphic')).write_bytes(body)
            result['status'] = 'previous_inspection_hash_matched'
    except Exception as exc:
        result.update(status='access_gap', detail=str(exc)[:140], error_type=type(exc).__name__)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--retry-errors', action='store_true')
    args = parser.parse_args()
    jobs = []
    for path in (ROOT / 'universities').glob('*/*/profile.yaml'):
        p = load_yaml(path.read_text())
        if p['visual']['color_primary']['availability'] != 'unresearched' and p['identity']['name_en']['availability'] == 'found':
            continue
        for asset in p['visual']['logo_assets']:
            if asset.get('access_status') == 'content_inspected' and asset.get('sha256') and cached_bytes(asset) is None:
                jobs.append((p['identity']['school_code'], p['identity']['name_zh'], asset))
    out = ROOT / 'data/review/ppt-core-logo-cache-2026.jsonl'
    records = {r['asset_id']: r for r in map(json.loads, out.read_text().splitlines())} if out.exists() else {}
    jobs = [j for j in jobs if j[2]['asset_id'] not in records or
            args.retry_errors and records[j[2]['asset_id']]['status'] == 'access_gap']
    print('Existing logo files queued:', len(jobs), flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for n, r in enumerate(pool.map(read, jobs), 1):
            previous = records.get(r['asset_id'])
            if previous:
                r['previous_attempts'] = previous.get('previous_attempts', []) + [
                    {k: v for k, v in previous.items() if k != 'previous_attempts'}]
            records[r['asset_id']] = r
            if n % 20 == 0:
                print('Read', n, '/', len(jobs), flush=True)
                out.write_text(''.join(json.dumps(records[k], ensure_ascii=False) + '\n' for k in sorted(records)))
    out.write_text(''.join(json.dumps(records[k], ensure_ascii=False) + '\n' for k in sorted(records)))
    from collections import Counter
    print(dict(Counter(r['status'] for r in records.values())), flush=True)


if __name__ == '__main__':
    main()
