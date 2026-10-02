#!/usr/bin/env python3
"""Offline JSON Schema validation with school codes and field paths in diagnostics."""
import json
import pathlib
import sys
from jsonschema import Draft202012Validator, FormatChecker

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/ingest'))
from yaml_io import load_yaml


def schema_validator(name):
    schema = json.loads((ROOT / 'data' / name).read_text(encoding='utf-8'))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def diagnostics(validator, record, school_code):
    return [str(school_code) + ': ' + '.'.join(map(str, error.absolute_path)) + ': ' + error.message
            for error in validator.iter_errors(record)]


def main():
    errors = []
    canonical = schema_validator('profile-schema-v3.json')
    export = schema_validator('ppt-export-schema-v1.json')
    paths = sorted((ROOT / 'universities').glob('*/*/profile.yaml'))
    for path in paths:
        errors.extend(diagnostics(canonical, load_yaml(path.read_text(encoding='utf-8')), path.parent.name))
    export_count = 0
    with (ROOT / 'indexes/ppt-profiles.jsonl').open(encoding='utf-8') as handle:
        for line in handle:
            record = json.loads(line)
            errors.extend(diagnostics(export, record, record.get('school_code', '?')))
            export_count += 1
    print('Schemas: %d canonical profiles, %d PPT records; errors: %d' % (len(paths), export_count, len(errors)))
    for error in errors[:100]:
        print('ERROR:', error)
    raise SystemExit(bool(errors))


if __name__ == '__main__':
    main()
