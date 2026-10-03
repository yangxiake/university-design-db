#!/usr/bin/env python3
"""Package current PPT data and viewer, excluding raw caches and research logs."""
import argparse
import datetime as dt
import hashlib
import json
import pathlib
import subprocess
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]


def release_files():
    tracked = set(subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode('utf-8').split('\0'))
    files = []
    for folder in ('universities', 'indexes', 'viewer', 'data/external'):
        files.extend(p for p in (ROOT / folder).rglob('*') if p.is_file()
                     and p.relative_to(ROOT).as_posix() in tracked
                     and not p.relative_to(ROOT).as_posix().startswith('viewer/tests/'))
    names = ['LICENSE', 'LICENSE-DATA.md', 'data/ppt-core-fields.yaml',
             'data/universities-scope-2026.csv', 'data/source-manifest.yaml',
             'data/profile-schema-v4.json', 'data/profile-schema-v4.yaml',
             'data/ppt-export-schema-v1.json', 'data/review/ppt-core-coverage-2026.json',
             'data/review/ppt-core-queue-2026.csv', 'docs/data-guide.md', 'docs/ppt-guide.md',
             'docs/ppt-export-v1.md', 'docs/viewer-guide.md', 'docs/schema.md', 'docs/quality-checks.md',
             'docs/ppt-core-coverage-2026.md', 'docs/handoff-2026-10-03.md',
             'docs/core-completion-remaining-2026.md',
             'docs/releases/2026-10-03-ppt-core.md']
    files.extend(ROOT / name for name in names)
    files.extend(p for p in (ROOT / 'docs/releases').glob('*.md')
                 if p.relative_to(ROOT).as_posix() in tracked)
    return sorted(set(files), key=lambda p: p.relative_to(ROOT).as_posix())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', required=True)
    parser.add_argument('--output-dir', default='tmp/releases')
    args = parser.parse_args()
    coverage = json.loads((ROOT / 'data/review/ppt-core-coverage-2026.json').read_text())
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    dirty = subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True)
    if dirty.strip():
        parser.error('Commit the verified repository before packaging a release')
    if coverage['profiles'] != 1412:
        parser.error('Expected the complete 1412-school registry')
    files = release_files()
    if any(not p.exists() for p in files):
        parser.error('Missing release input')
    if len([p for p in files if p.name == 'profile.yaml']) != 1412:
        parser.error('Expected 1412 canonical school profiles')
    entries = {p.relative_to(ROOT).as_posix(): p.read_bytes() for p in files}
    entries['README.md'] = ('# 高校PPT主字段资料包\n\n'
        '版本：%s。来源提交：%s。数据日期：%s。\n\n'
        '共1412所本科院校，PPT主字段可用%s所，剩余%s项缺口。仅印刷主色不计入屏幕可用。自动整理版，保留来源、核对状态与使用边界。\n\n'
        '制作PPT先读取`indexes/ppt-profiles.jsonl`或CSV；机器可读唯一事实源为各校`profile.yaml`。\n\n'
        '检索目录：在解压目录运行`python3 -m http.server 8765 --bind 127.0.0.1`，打开`http://127.0.0.1:8765/viewer/`。\n\n'
        '主字段范围、剩余缺口和使用方法见`data/ppt-core-fields.yaml`、`docs/ppt-core-coverage-2026.md`和`docs/data-guide.md`。\n\n'
        '校徽和模板为上游链接；本包不包含第三方图形、照片或字体。取样/CSS配色为PPT建议，不等于校方官方标准。\n\n'
        '本包不含采集日志和开发环境。可复现脚本及完整源仓库：https://github.com/yangxiake/university-design-db/tree/%s 。\n\n'
        '脚本许可MIT；原创数据整理CC BY 4.0；上游资料遵循其独立许可与学校权利。详见`LICENSE-DATA.md`和`data/external/`。\n'
        % (args.version, revision, coverage['checked_at'], coverage['main_fields_complete_schools'],
           coverage['missing_main_field_items'], args.version)).encode('utf-8')
    manifest = dict(version=args.version, source_commit=revision, schema_version=4, coverage=coverage,
                    files={name: dict(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
                           for name, raw in entries.items()})
    entries['MANIFEST.json'] = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    stamp = dt.date.fromisoformat(coverage['checked_at'])
    output = ROOT / args.output_dir; output.mkdir(parents=True, exist_ok=True)
    path = output / ('university-ppt-core-' + stamp.isoformat() + '.zip')
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, raw in sorted(entries.items()):
            entry = zipfile.ZipInfo(name, (stamp.year, stamp.month, stamp.day, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, raw, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError('corrupt_release_zip')
        for name, info in manifest['files'].items():
            if hashlib.sha256(archive.read(name)).hexdigest() != info['sha256']:
                raise ValueError('release_manifest_hash_mismatch')
        if any(name.startswith(('tmp/', 'scripts/', '.git/')) for name in archive.namelist()):
            raise ValueError('unexpected_release_content')
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    path.with_suffix('.zip.sha256').write_text(digest + '  ' + path.name + '\n')
    print(json.dumps(dict(path=str(path), files=len(entries), bytes=path.stat().st_size,
                          sha256=digest, source_commit=revision), ensure_ascii=False))


if __name__ == '__main__':
    main()
