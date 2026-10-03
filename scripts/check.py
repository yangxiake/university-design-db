#!/usr/bin/env python3
"""Run all offline quality gates without generating or collecting data."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import os
import pathlib
import shutil
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
PYTHON = sys.executable
JOBS = [
    ('profile semantics', [PYTHON, 'scripts/validate/validate_profiles.py', '--automatic-draft']),
    ('JSON schemas', [PYTHON, 'scripts/validate/validate_schemas.py']),
    ('unit tests', [PYTHON, '-m', 'unittest', 'discover', '-s', 'scripts/validate', '-p', 'test_*.py']),
    *[(name, [PYTHON, 'scripts/ingest/' + name + '.py', '--check']) for name in
      ('render_official', 'render_community', 'render_enriched', 'build_indexes', 'build_ppt_indexes', 'build_ppt_profiles', 'build_viewer')],
    ('whitespace', ['git', 'diff', '--check']),
]


def snapshot():
    result = subprocess.run(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'],
                            cwd=ROOT, check=True, stdout=subprocess.PIPE)
    files = {}
    for name in set(result.stdout.decode('utf-8').split('\0')) - {''}:
        path = ROOT / name
        if not path.exists():
            files[name] = 'missing'
            continue
        data = path.read_bytes() if not path.is_symlink() else str(path.readlink()).encode('utf-8')
        files[name] = hashlib.sha256(data).hexdigest()
    return files


def run_job(name, command):
    start = time.monotonic()
    result = subprocess.run(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding='utf-8', errors='replace')
    return name, result.returncode, result.stdout, time.monotonic() - start


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jobs', type=int, default=2, help='Bounded independent checks (1–4)')
    parser.add_argument('--node', default=os.environ.get('NODE_BINARY', 'node'), help='Node.js 24 executable for viewer checks')
    args = parser.parse_args()
    if not 1 <= args.jobs <= 4:
        parser.error('--jobs must be 1–4')
    node = shutil.which(args.node)
    if not node:
        parser.error('Node.js 24 is required; install it or pass --node /absolute/path/to/node')
    tests = sorted(str(p.relative_to(ROOT)) for p in (ROOT / 'viewer/tests').glob('*.test.mjs'))
    jobs = JOBS + [('viewer model tests', [node, '--test', *tests])]
    before = snapshot()
    failed = []
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = [pool.submit(run_job, name, command) for name, command in jobs]
        for future in as_completed(futures):
            name, code, output, seconds = future.result()
            print('[%s] %s (%.1fs)' % ('FAIL' if code else 'PASS', name, seconds), flush=True)
            if output.strip():
                print(output.strip(), flush=True)
            if code:
                failed.append(name)
    after = snapshot()
    changed = sorted(name for name in set(before) | set(after) if before.get(name) != after.get(name))
    if changed:
        failed.append('read-only repository check')
        print('[FAIL] Check modified files:', *changed[:20], sep='\n', flush=True)
    else:
        print('[PASS] Check left all repository files unchanged.', flush=True)
    print('Quality gates: %d/%d passed.' % (len(jobs) + 1 - len(failed), len(jobs) + 1), flush=True)
    raise SystemExit(bool(failed))


if __name__ == '__main__':
    main()
