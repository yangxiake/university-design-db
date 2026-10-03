#!/usr/bin/env python3
"""Create an ignored local preview cache from already inspected local files; no network."""
import argparse
import collections
import hashlib
import json
import pathlib
import re
import zipfile
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[1]
FORMATS = {'svg', 'png', 'jpeg', 'jpg', 'gif', 'webp', 'bmp', 'ico', 'avif'}
MAX_BYTES = 20_000_000


def safe_image(raw, fmt):
    if fmt != 'svg':
        signatures = {'png': b'\x89PNG\r\n\x1a\n', 'jpeg': b'\xff\xd8', 'jpg': b'\xff\xd8',
                      'gif': b'GIF8', 'bmp': b'BM', 'ico': b'\x00\x00\x01\x00'}
        if fmt in signatures:
            return raw.startswith(signatures[fmt])
        if fmt == 'webp':
            return raw.startswith(b'RIFF') and raw[8:12] == b'WEBP'
        return fmt == 'avif' and b'ftypavif' in raw[:32]
    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        return False
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return False
    if root.tag.split('}')[-1] != 'svg':
        return False
    for node in root.iter():
        if node.tag.split('}')[-1].lower() in {'script', 'foreignobject'}:
            return False
        for key, value in node.attrib.items():
            name = key.split('}')[-1].lower()
            if name.startswith('on'):
                return False
            if name in {'href', 'src'} and value and not value.startswith(('#', 'data:image/png;', 'data:image/jpeg;')):
                return False
        text = (node.text or '') + ' '.join(node.attrib.values())
        if re.search(r'@import|url\(\s*[\"\']?\s*(?!#)[^\s\"\')]', text, flags=re.I):
            return False
    return True


def decoded_member(info):
    if info.flag_bits & 0x800:
        return info.filename
    try:
        return info.filename.encode('cp437').decode('gb18030')
    except (UnicodeError, LookupError):
        return info.filename


def prepare(root=ROOT):
    assets = [a for line in (root / 'indexes/ppt-profiles.jsonl').read_text().splitlines()
              for a in json.loads(line)['logos']['candidates']
              if a.get('access_status') == 'content_inspected' and re.fullmatch('[a-f0-9]{64}', a.get('sha256') or '')
              and a.get('format') in FORMATS and a.get('download_kind') != 'document_page']
    wanted = {a['sha256']: a['format'] for a in assets}
    out = root / 'tmp/viewer-previews'; out.mkdir(parents=True, exist_ok=True)
    found = {}; archives = {}; archive_members = collections.defaultdict(dict)

    def keep(raw, sha):
        if sha not in wanted or sha in found or len(raw) > MAX_BYTES or hashlib.sha256(raw).hexdigest() != sha:
            return
        fmt = wanted[sha]
        if not safe_image(raw, fmt):
            return
        (out / (sha + '.' + fmt)).write_bytes(raw)
        found[sha] = dict(format=fmt, bytes=len(raw))

    for a in assets:
        if a.get('download_kind') == 'archive_member' and a.get('archive_sha256') and a.get('archive_member'):
            archive_members[a['archive_sha256']][a['archive_member']] = a['sha256']
    extensions = FORMATS | {'bin', 'graphic', 'zip'}
    for path in (root / 'tmp').rglob('*'):
        if not path.is_file() or path.is_symlink() or 'releases' in path.relative_to(root / 'tmp').parts:
            continue
        if path.suffix.lower().lstrip('.') not in extensions or path.stat().st_size > 250_000_000:
            continue
        raw = path.read_bytes(); sha = hashlib.sha256(raw).hexdigest()
        if sha in archive_members:
            archives[sha] = path
        if len(raw) <= MAX_BYTES:
            keep(raw, sha)
    for sha, path in archives.items():
        try:
            with zipfile.ZipFile(path) as archive:
                for info in archive.infolist():
                    member = info.filename if info.filename in archive_members[sha] else decoded_member(info)
                    target = archive_members[sha].get(member)
                    if target and info.file_size <= MAX_BYTES:
                        keep(archive.read(info), target)
        except (zipfile.BadZipFile, RuntimeError, OSError):
            continue
    # Write the manifest last. Stale or unrelated cache files are never advertised.
    manifest = dict(cache_version=1, files=dict(sorted(found.items())))
    (out / 'index.json').write_text(json.dumps(manifest, ensure_ascii=False, separators=(',', ':')) + '\n')
    return dict(preview_files=len(found), inspected_image_files=len(wanted),
                schools_with_local_preview=sum(any(a.get('sha256') in found for a in json.loads(line)['logos']['candidates'])
                                              for line in (root / 'indexes/ppt-profiles.jsonl').read_text().splitlines()))


if __name__ == '__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    print(json.dumps(prepare(), ensure_ascii=False))
