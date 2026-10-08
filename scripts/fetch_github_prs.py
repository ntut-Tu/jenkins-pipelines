"""Poll a configured GitHub repository with conditional REST requests and a local cache."""
import argparse
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import os
from pathlib import Path
import re
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


API_ROOT = 'https://api.github.com'
API_VERSION = '2022-11-28'
IDENTIFIER = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]*\Z')


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        return None


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.pr-poll-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write('\n')
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_state(path):
    if not path.exists():
        return {'repos': {}, 'blocked_until': 0, 'rate_limit_strikes': 0}
    state = json.loads(path.read_text())
    if not isinstance(state, dict) or not isinstance(state.get('repos'), dict):
        raise ValueError('Invalid PR poll state')
    return state


def next_link(header, owner, repository, head_branch, base_branch):
    for part in header.split(','):
        match = re.fullmatch(r'\s*<([^>]+)>;\s*rel="next"\s*', part)
        if match:
            url = match.group(1)
            validate_url(url, owner, repository, head_branch, base_branch)
            return url
    return None


def validate_url(url, owner, repository, head_branch, base_branch):
    parts = urlsplit(url)
    expected = f'/repos/{owner}/{repository}/pulls'
    query = parse_qs(parts.query, strict_parsing=True)
    if (parts.scheme != 'https' or parts.netloc != 'api.github.com' or parts.path.casefold() != expected.casefold()
            or parts.fragment or query.get('state') != ['open']
            or query.get('per_page') != ['100'] or query.get('head') != [f'{owner}:{head_branch}']
            or query.get('base') != [base_branch]
            or not set(query) <= {'state', 'per_page', 'head', 'base', 'page'}):
        raise ValueError('Unexpected pagination URL from GitHub')


def rate_limit_delay(headers, strikes):
    retry_after = headers.get('Retry-After')
    if retry_after:
        try:
            return max(60, int(retry_after))
        except ValueError:
            try:
                return max(60, int(parsedate_to_datetime(retry_after).timestamp() - time.time()))
            except (TypeError, ValueError):
                pass
    if headers.get('X-RateLimit-Remaining') == '0':
        try:
            return max(60, int(headers['X-RateLimit-Reset']) - int(time.time()) + 5)
        except (KeyError, ValueError):
            pass
    return min(3600, 60 * (2 ** min(strikes, 6)))


def request_page(opener, url, etag, token):
    headers = {
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': API_VERSION,
        'User-Agent': 'pdd-jenkins-pr-poll',
    }
    if token:
        headers['Authorization'] = f'Bearer {token}'
    if etag:
        headers['If-None-Match'] = etag
    request = Request(url, headers=headers)
    try:
        with opener.open(request, timeout=15) as response:
            if response.status != 200:
                raise RuntimeError(f'Unexpected GitHub HTTP {response.status}')
            return 200, response.headers, json.load(response)
    except HTTPError as error:
        if error.code == 304:
            return 304, error.headers, None
        message = error.read(4096).decode('utf-8', errors='replace').lower()
        if error.code in (403, 429) and (error.headers.get('Retry-After') or error.headers.get('X-RateLimit-Remaining') == '0'
                                         or error.code == 429 or 'rate limit' in message):
            raise RateLimited(error.headers) from None
        raise RuntimeError(f'GitHub API returned HTTP {error.code}') from None
    except URLError as error:
        raise RuntimeError(f'GitHub API connection failed: {error.reason}') from None


class RateLimited(Exception):
    def __init__(self, headers):
        self.headers = headers


def compact_pr(item):
    return {
        'number': item['number'], 'title': item['title'], 'url': item['html_url'],
        'draft': item['draft'], 'updated_at': item['updated_at'],
        'head_sha': item['head']['sha'], 'base_sha': item['base']['sha'],
        'head_ref': item['head']['ref'], 'head_repo': (item['head'].get('repo') or {}).get('full_name'),
        'base_ref': item['base']['ref'],
    }


def fetch_repository(opener, owner, repository, head_branch, base_branch, previous, token):
    query = urlencode({'state': 'open', 'per_page': 100, 'head': f'{owner}:{head_branch}', 'base': base_branch})
    url = f'{API_ROOT}/repos/{owner}/{repository}/pulls?{query}'
    old_pages = previous.get('pages', {})
    pages = {}
    next_allowed = int(time.time()) + 60
    while url:
        validate_url(url, owner, repository, head_branch, base_branch)
        cached = old_pages.get(url, {})
        status, headers, body = request_page(opener, url, cached.get('etag'), token)
        if status == 304:
            if 'items' not in cached:
                raise RuntimeError('GitHub returned 304 without a cached page')
            page = cached
        else:
            if not isinstance(body, list):
                raise RuntimeError('GitHub returned an unexpected PR response')
            page = {'etag': headers.get('ETag'), 'items': [compact_pr(item) for item in body],
                    'next': next_link(headers.get('Link', ''), owner, repository, head_branch, base_branch)}
        pages[url] = page
        interval = headers.get('X-Poll-Interval')
        if interval:
            try:
                next_allowed = max(next_allowed, int(time.time()) + max(0, int(interval)))
            except ValueError:
                pass
        print(f'{repository}: page {len(pages)} HTTP {status}, {len(page["items"])} open PRs')
        remaining = headers.get('X-RateLimit-Remaining')
        if remaining is not None:
            print(f'{repository}: GitHub API remaining={remaining}, reset={headers.get("X-RateLimit-Reset", "unknown")}')
        url = page['next']
        if len(pages) > 100:
            raise RuntimeError('Too many GitHub PR pages')
        if headers.get('X-RateLimit-Remaining') == '0':
            raise RateLimited(headers)
    return {'pages': pages, 'next_allowed_at': next_allowed}


def snapshot(owner, repository, entry):
    items = []
    for page in entry.get('pages', {}).values():
        items.extend(page['items'])
    return {'repository': f'{owner}/{repository}', 'open_pull_requests': items}


def read_dispatched(path):
    if not path or not path.exists():
        return {}
    dispatched = {}
    for line in path.read_text().splitlines():
        fields = line.split('\t')
        if len(fields) == 4:  # State written when only ntut-Tu was supported.
            fields.insert(0, 'ntut-Tu')
        if (len(fields) != 5 or not IDENTIFIER.fullmatch(fields[0]) or not IDENTIFIER.fullmatch(fields[1])
                or not fields[2].isdigit()
                or any(not re.fullmatch(r'[a-f0-9]{40}', value) for value in fields[3:])):
            raise ValueError('Invalid dispatched PR state')
        dispatched[(fields[0], fields[1], fields[2])] = (fields[3], fields[4])
    return dispatched


def write_lines(path, lines):
    descriptor, temporary = tempfile.mkstemp(prefix='.pr-lines-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w') as stream:
            stream.write(''.join('\t'.join(line) + '\n' for line in lines))
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def run(owner, repository, state_path, output_path, token=None, opener=None, *, head_branch='jenkins-testing',
        base_branch='main', dispatch_state=None, candidates_path=None, max_empty_polls=5,
        status_path=None, reset_polling=False, force_retest=False):
    if not IDENTIFIER.fullmatch(owner) or not IDENTIFIER.fullmatch(repository):
        raise ValueError('Invalid GitHub repository owner or name')
    if type(max_empty_polls) is not int or max_empty_polls < 1:
        raise ValueError('max_empty_polls must be a positive integer')
    state = read_state(state_path)
    watch_key = [owner, repository, head_branch, base_branch]
    watch = state.get('watch', {})
    watch_changed = watch.get('key') != watch_key
    if watch_changed or reset_polling:
        watch = {'key': watch_key, 'empty_polls': 0, 'stopped': False}
    state['watch'] = watch
    now = int(time.time())
    if not watch['stopped'] and state.get('blocked_until', 0) > now:
        raise RuntimeError(f'GitHub rate limit cooldown until {datetime.fromtimestamp(state["blocked_until"], timezone.utc).isoformat()}')
    opener = opener or build_opener(NoRedirect())
    repo_key = f'{owner}/{repository}'
    if watch_changed:
        state['repos'].pop(repo_key, None)
    old = state['repos'].get(repo_key, {})
    polled = False
    if watch['stopped']:
        print(f'{repo_key}: automatic polling stopped after {watch["empty_polls"]} empty polls; use RESET_POLLING to resume')
    elif old.get('next_allowed_at', 0) > int(time.time()):
        print(f'{repo_key}: poll interval has not elapsed; using cached PRs')
    else:
        try:
            state['repos'][repo_key] = fetch_repository(opener, owner, repository, head_branch, base_branch, old, token)
        except RateLimited as error:
            strikes = state.get('rate_limit_strikes', 0)
            state['blocked_until'] = int(time.time()) + rate_limit_delay(error.headers, strikes)
            state['rate_limit_strikes'] = strikes + 1
            write_json(state_path, state)
            raise RuntimeError(f'GitHub rate limited polling; paused until {datetime.fromtimestamp(state["blocked_until"], timezone.utc).isoformat()}') from None
        state['rate_limit_strikes'] = 0
        polled = True
    result = {'generated_at': datetime.now(timezone.utc).isoformat(),
              'repositories': [snapshot(owner, repository, state['repos'].get(repo_key, {}))]}
    write_json(output_path, result)
    matching = [item for item in result['repositories'][0]['open_pull_requests']
                if item['head_ref'] == head_branch and item['base_ref'] == base_branch
                and isinstance(item['head_repo'], str)
                and item['head_repo'].casefold() == repo_key.casefold()]
    if polled:
        watch['empty_polls'] = 0 if matching else watch['empty_polls'] + 1
        if watch['empty_polls'] >= max_empty_polls:
            watch['stopped'] = True
            print(f'{repo_key}: {watch["empty_polls"]} consecutive polls without a matching PR; stopping automatic polling')
    write_json(state_path, state)
    if status_path:
        write_json(status_path, {'empty_polls': watch['empty_polls'], 'stopped': watch['stopped'],
                                 'reset_polling': reset_polling, 'matching_prs': len(matching), 'polled': polled})
    if dispatch_state and candidates_path:
        dispatched = read_dispatched(dispatch_state)
        candidates = []
        entry = result['repositories'][0]
        open_numbers = {str(item['number']) for item in entry['open_pull_requests']}
        dispatched = {key: value for key, value in dispatched.items()
                      if key[:2] != (owner, repository) or key[2] in open_numbers}
        for item in entry['open_pull_requests']:
            key = (owner, repository, str(item['number']))
            signature = (item['head_sha'], item['base_sha'])
            if item in matching and (force_retest or dispatched.get(key) != signature) and not watch['stopped']:
                candidates.append((*key, *signature, base_branch))
        write_lines(dispatch_state, [(*key, *value) for key, value in dispatched.items()])
        write_lines(candidates_path, candidates)
        print(f'{len(candidates)} matching PR revisions require tests' + (' (force retest)' if force_retest else ''))
    for entry in result['repositories']:
        print(f'{entry["repository"]}: {len(entry["open_pull_requests"])} open PRs')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--owner', required=True)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--head-branch', required=True)
    parser.add_argument('--base-branch', required=True)
    parser.add_argument('--dispatch-state', type=Path, required=True)
    parser.add_argument('--candidates', type=Path, required=True)
    parser.add_argument('--max-empty-polls', type=int, default=5)
    parser.add_argument('--status', type=Path, required=True)
    parser.add_argument('--reset-polling', action='store_true')
    parser.add_argument('--force-retest', action='store_true')
    arguments = parser.parse_args()
    for name in ('head_branch', 'base_branch'):
        value = getattr(arguments, name)
        if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_./-]*', value) or '..' in value or value.endswith('/'):
            parser.error(f'invalid {name}')
    run(arguments.owner, arguments.repository, arguments.state, arguments.output, os.getenv('GITHUB_API_TOKEN'),
        head_branch=arguments.head_branch, base_branch=arguments.base_branch,
        dispatch_state=arguments.dispatch_state, candidates_path=arguments.candidates,
        max_empty_polls=arguments.max_empty_polls, status_path=arguments.status,
        reset_polling=arguments.reset_polling, force_retest=arguments.force_retest)


if __name__ == '__main__':
    main()
