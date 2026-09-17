"""Dispatch a registered workflow on the exact, pushed Codex branch.

No branch switching, rebasing, model commits, or credential output. --check
only reads repository/workflow metadata. The caller must complete the bench,
replays and readiness before requesting an actual dispatch.
"""
import argparse
import json
import subprocess
import urllib.error
import urllib.parse
import urllib.request


def git(*args):
    return subprocess.check_output(['git', *args], text=True).strip()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--check', action='store_true')
    p.add_argument('--workflow', choices=['drytest.yml', 'update.yml'], default='drytest.yml')
    p.add_argument('--company', default='CLP')
    p.add_argument('--period', default='FY25')
    args = p.parse_args()
    branch = git('branch', '--show-current')
    if not branch.startswith('codex/'):
        raise SystemExit('Refusing: this is not a Codex branch')
    origin = urllib.parse.urlparse(git('remote', 'get-url', 'origin'))
    if origin.scheme != 'https' or origin.hostname != 'github.com':
        raise SystemExit('Expected the existing HTTPS GitHub remote')
    repo = origin.path.strip('/').removesuffix('.git')
    credential = subprocess.run(['git', 'credential', 'fill'], input='protocol=https\nhost=github.com\n\n',
                                text=True, capture_output=True, check=True)
    fields = dict(line.split('=', 1) for line in credential.stdout.splitlines() if '=' in line)
    token = fields.get('password')
    if not token:
        raise SystemExit('No GitHub credential available')

    def request(path, data=None):
        req = urllib.request.Request('https://api.github.com/repos/' + repo + path,
                                     data=json.dumps(data).encode() if data is not None else None,
                                     headers={'Authorization': 'Bearer ' + token,
                                              'Accept': 'application/vnd.github+json',
                                              'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=30) as response:
            body = response.read()
            return json.loads(body) if body else {}
    if args.check:
        metadata = request('')
        workflow = request('/actions/workflows/' + args.workflow)
        print(json.dumps({'repo': repo, 'branch': branch, 'permissions': metadata.get('permissions'),
                          'workflow': workflow.get('path'), 'state': workflow.get('state')}, indent=2))
        return
    sha = git('rev-parse', 'HEAD')
    remote = git('ls-remote', 'origin', 'refs/heads/' + branch).split()
    if not remote or remote[0] != sha or git('status', '--porcelain'):
        raise SystemExit('Refusing: commit, verify and push this exact clean branch first')
    inputs = ({'script': 'tools/codex_validate.py', 'company': 'companies/' + args.company, 'args': ''}
              if args.workflow == 'drytest.yml' else
              {'company': args.company, 'period': args.period, 'action': 'pipeline', 'persist_results': 'false'})
    request('/actions/workflows/' + args.workflow + '/dispatches', {'ref': branch, 'inputs': inputs})
    print(json.dumps({'dispatched': args.workflow, 'branch': branch, 'sha': sha, 'inputs': inputs}, indent=2))


if __name__ == '__main__':
    try:
        main()
    except urllib.error.HTTPError as e:
        raise SystemExit(f'GitHub API returned HTTP {e.code}; no credentials printed')
