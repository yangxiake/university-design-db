#!/usr/bin/env python3
"""Read PPT records by stable identity, region, name or material state (standard library only)."""
import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--school-code')
    parser.add_argument('--province')
    parser.add_argument('--query', help='Current name, sourced aliases, short names or English name')
    parser.add_argument('--has-inspected-logo', action='store_true')
    parser.add_argument('--color-status', choices=['official_vi', 'design_reference', 'official_print_only',
                                                 'conflict', 'unresearched', 'not_found'])
    args = parser.parse_args()
    count = 0
    with (ROOT / 'indexes/ppt-profiles.jsonl').open(encoding='utf-8') as handle:
        for line in handle:
            record = json.loads(line)
            if args.school_code and record['school_code'] != args.school_code:
                continue
            if args.province and record['province'] != args.province:
                continue
            if args.query:
                terms = [record['name_zh'], record['school_code']]
                for key in ('name_en', 'short_name_en', 'short_name_zh', 'aliases'):
                    fact = record['identity'][key]
                    if fact['availability'] == 'found':
                        terms.extend(fact['value'] if isinstance(fact['value'], list) else [fact['value']])
                if not any(args.query.casefold() in term.casefold() for term in terms):
                    continue
            if args.has_inspected_logo and record['logos']['status'] != 'inspected_candidate':
                continue
            if args.color_status and record['colors']['screen_status'] != args.color_status:
                continue
            print(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(',', ':')))
            count += 1
    if count == 0:
        print('No matching PPT records; identities and states are exact filters.', file=sys.stderr)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
