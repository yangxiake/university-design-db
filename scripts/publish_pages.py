#!/usr/bin/env python3
"""Publish a clean, CI-verified main commit to the static Pages branch."""
import json
import pathlib
import subprocess
import tempfile

from build_pages import ROOT, build

REPOSITORY = 'yangxiake/university-design-db'
REMOTE = 'https://github.com/' + REPOSITORY + '.git'
BRANCH = 'codex/gh-pages'


def quality_passed(runs, revision):
    return any(run.get('headSha') == revision and run.get('status') == 'completed'
               and run.get('conclusion') == 'success' for run in runs)


def run(*args, cwd=ROOT):
    return subprocess.check_output(args, cwd=cwd, text=True).strip()


def main():
    if run('git', 'status', '--porcelain'):
        raise ValueError('Commit all source changes before publishing')
    if run('git', 'remote', 'get-url', 'origin') != REMOTE:
        raise ValueError('Publishing target must match this repository')
    revision = run('git', 'rev-parse', 'HEAD')
    if run('git', 'ls-remote', 'origin', 'refs/heads/main').split()[0] != revision:
        raise ValueError('Publish the current source commit to main first')
    repository = json.loads(run('gh', 'repo', 'view', REPOSITORY, '--json', 'visibility'))
    if repository['visibility'] != 'PUBLIC':
        raise ValueError('This free publishing route requires a public repository')
    checks = json.loads(run('gh', 'run', 'list', '--repo', REPOSITORY, '--workflow', 'quality.yml',
                            '--commit', revision, '--branch', 'main', '--limit', '20',
                            '--json', 'headSha,status,conclusion'))
    if not quality_passed(checks, revision):
        raise ValueError('Wait for Data quality to pass for this exact source commit')
    previous = run('git', 'ls-remote', 'origin', 'refs/heads/' + BRANCH)
    (ROOT / 'tmp').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='pages-publish-', dir=ROOT / 'tmp') as folder:
        destination = pathlib.Path(folder)
        result = build(ROOT, destination, revision)
        run('git', 'init', '--quiet', '--initial-branch', BRANCH, cwd=destination)
        run('git', 'remote', 'add', 'origin', REMOTE, cwd=destination)
        if previous:
            run('git', 'fetch', '--quiet', 'origin', BRANCH, cwd=destination)
            prior = json.loads(run('git', 'show', 'FETCH_HEAD:deployment.json', cwd=destination))
            if prior.get('site_version') != 1 or prior.get('school_count') != 1412:
                raise ValueError('Existing branch is not a recognized website deployment')
            run('git', 'update-ref', 'refs/heads/' + BRANCH,
                run('git', 'rev-parse', 'FETCH_HEAD', cwd=destination), cwd=destination)
        run('git', 'add', '--all', cwd=destination)
        if previous and subprocess.call(['git', 'diff', '--cached', '--quiet'], cwd=destination) == 0:
            result.update(branch=BRANCH, already_current=True)
        else:
            run('git', '-c', 'user.name=University Design DB Publisher',
                '-c', 'user.email=pages-publisher@users.noreply.github.com',
                'commit', '--quiet', '-m', 'Publish website from ' + revision, cwd=destination)
            run('git', 'push', 'origin', 'HEAD:refs/heads/' + BRANCH, cwd=destination)
            result.update(branch=BRANCH, deployment_commit=run('git', 'rev-parse', 'HEAD', cwd=destination))
    print(json.dumps(result))


if __name__ == '__main__':
    main()
