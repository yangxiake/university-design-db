#!/usr/bin/env python3
"""Stage only the static viewer and its metadata for GitHub Pages; no network access."""
import argparse
import hashlib
import json
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
VIEWER_FILES = ('index.html', 'app.mjs', 'model.mjs', 'preview-loader.mjs',
                'interactions.mjs', 'styles.css')
REPOSITORY = 'https://github.com/yangxiake/university-design-db'


def build(root, destination, revision):
    root = root.resolve()
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('Expected a full source commit SHA')
    if destination.is_symlink():
        raise ValueError('Output must not be a symbolic link')
    destination = destination.resolve()
    if destination == root / 'tmp' or not destination.is_relative_to(root / 'tmp'):
        raise ValueError('Output must be a directory inside tmp/')
    if destination.exists() and any(destination.iterdir()):
        raise ValueError('Output must be empty; existing files will not be removed')
    catalog = json.loads((root / 'viewer/data/catalog.json').read_text(encoding='utf-8'))
    if catalog['school_count'] != 1412 or len(catalog['schools']) != 1412:
        raise ValueError('Expected the complete 1412-school catalog')
    provinces = catalog['provinces']
    if len(provinces) != 31 or len(set(provinces)) != 31:
        raise ValueError('Expected 31 distinct regional bundles')
    if any(not name or pathlib.Path(name).name != name or name in ('.', '..') for name in provinces):
        raise ValueError('Invalid regional bundle path')
    names = list(VIEWER_FILES) + ['data/catalog.json'] + ['data/provinces/' + name + '.json' for name in provinces]
    entries = {}
    for name in names:
        source = root / 'viewer' / name
        if source.is_symlink() or not source.resolve().is_relative_to(root / 'viewer'):
            raise ValueError('Source must not be a symbolic link: ' + name)
        entries[name] = source.read_bytes()
    base = REPOSITORY + '/blob/' + revision + '/'
    html = entries['index.html'].decode('utf-8')
    for path in ('docs/ppt-export-v1.md', 'README.md'):
        old = 'href="../' + path + '"'
        if html.count(old) != 1:
            raise ValueError('Expected one repository link: ' + path)
        html = html.replace(old, 'href="' + base + path + '"')
    if html.count('</head>') != 1:
        raise ValueError('Expected one HTML head')
    html = html.replace('</head>', '  <meta name="repository-base" content="' + base + '">\n</head>')
    entries['index.html'] = html.encode('utf-8')
    entries['.nojekyll'] = b''
    manifest = dict(site_version=1, source_commit=revision, school_count=catalog['school_count'],
                    region_count=len(provinces), source_export_sha256=catalog['source_sha256'],
                    files={name: hashlib.sha256(raw).hexdigest() for name, raw in sorted(entries.items())})
    entries['deployment.json'] = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    for name, raw in entries.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    return dict(files=len(entries), bytes=sum(map(len, entries.values())), source_commit=revision,
                school_count=1412, region_count=31)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', default='tmp/github-pages')
    args = parser.parse_args()
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    result = build(ROOT, ROOT / args.output_dir, revision)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
