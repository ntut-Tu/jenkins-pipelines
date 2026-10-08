import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from fetch_github_prs import run


class Response(io.BytesIO):
    def __init__(self, body, headers):
        super().__init__(json.dumps(body).encode())
        self.status = 200
        self.headers = headers


class FakeOpener:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.requests = []

    def open(self, request, timeout):
        self.requests.append(request)
        assert timeout == 15
        reply = next(self.replies)
        if isinstance(reply, Exception):
            raise reply
        return reply


def pr(number):
    return {'number': number, 'title': f'PR {number}', 'html_url': f'https://github.com/ntut-Tu/cloth_shop_server/pull/{number}',
            'draft': False, 'updated_at': '2026-10-08T00:00:00Z',
            'head': {'sha': 'a' * 40, 'ref': 'jenkins-testing', 'repo': {'full_name': 'ntut-Tu/cloth_shop_server'}},
            'base': {'sha': 'b' * 40, 'ref': 'main'}}


class FetchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state = Path(self.tmp.name) / 'state.json'
        self.output = Path(self.tmp.name) / 'prs.json'
        self.first = 'https://api.github.com/repos/ntut-Tu/cloth_shop_server/pulls?state=open&per_page=100&head=ntut-Tu%3Ajenkins-testing&base=main'
        self.second = self.first + '&page=2'

    def test_pagination_and_conditional_requests_reuse_cached_pages(self):
        opener = FakeOpener([
            Response([pr(1)], {'ETag': '"first"', 'Link': f'<{self.second}>; rel="next"'}),
            Response([pr(2)], {'ETag': '"second"'}),
        ])
        result = run('ntut-Tu', 'cloth_shop_server', self.state, self.output, 'secret-token', opener)
        self.assertEqual([item['number'] for item in result['repositories'][0]['open_pull_requests']], [1, 2])
        self.assertEqual(opener.requests[0].get_header('Authorization'), 'Bearer secret-token')
        self.assertIn('head=ntut-Tu%3Ajenkins-testing&base=main', opener.requests[0].full_url)
        soon = FakeOpener([])
        run('ntut-Tu', 'cloth_shop_server', self.state, self.output, 'secret-token', soon)
        self.assertEqual(soon.requests, [])
        state = json.loads(self.state.read_text())
        state['repos']['ntut-Tu/cloth_shop_server']['next_allowed_at'] = 0
        self.state.write_text(json.dumps(state))
        cached = FakeOpener([
            HTTPError(self.first, 304, 'Not Modified', {}, io.BytesIO()),
            HTTPError(self.second, 304, 'Not Modified', {}, io.BytesIO()),
        ])
        result = run('ntut-Tu', 'cloth_shop_server', self.state, self.output, 'secret-token', cached)
        self.assertEqual([item['number'] for item in result['repositories'][0]['open_pull_requests']], [1, 2])
        self.assertEqual(cached.requests[0].get_header('If-none-match'), '"first"')
        self.assertEqual(cached.requests[1].get_header('If-none-match'), '"second"')
        self.assertNotIn('secret-token', self.state.read_text() + self.output.read_text())

    def test_rate_limit_stores_cooldown_and_blocks_next_run(self):
        limited = HTTPError(self.first, 429, 'Too Many Requests', {'Retry-After': '120'}, io.BytesIO(b'{}'))
        with self.assertRaisesRegex(RuntimeError, 'rate limited'):
            run('ntut-Tu', 'cloth_shop_server', self.state, self.output, 'secret-token', FakeOpener([limited]))
        self.assertGreater(json.loads(self.state.read_text())['blocked_until'], 0)
        next_opener = FakeOpener([])
        with self.assertRaisesRegex(RuntimeError, 'cooldown'):
            run('ntut-Tu', 'cloth_shop_server', self.state, self.output, 'secret-token', next_opener)
        self.assertEqual(next_opener.requests, [])

    def test_rejects_pagination_to_another_host(self):
        opener = FakeOpener([Response([pr(1)], {'Link': '<https://example.org/path>; rel="next"'})])
        with self.assertRaisesRegex(ValueError, 'pagination URL'):
            run('ntut-Tu', 'cloth_shop_server', self.state, self.output, None, opener)

    def test_only_matching_new_revision_is_dispatched(self):
        dispatched = Path(self.tmp.name) / 'dispatched.tsv'
        candidates = Path(self.tmp.name) / 'candidates.tsv'
        opener = FakeOpener([Response([pr(1), pr(2)], {'ETag': '"first"'})])
        run('ntut-Tu', 'cloth_shop_server', self.state, self.output, opener=opener,
            dispatch_state=dispatched, candidates_path=candidates)
        self.assertEqual(len(candidates.read_text().splitlines()), 2)
        dispatched.write_text('ntut-Tu\tcloth_shop_server\t1\t' + 'a' * 40 + '\t' + 'b' * 40 + '\n')
        cache = json.loads(self.state.read_text())
        cache['repos']['ntut-Tu/cloth_shop_server']['next_allowed_at'] = 0
        self.state.write_text(json.dumps(cache))
        cached = FakeOpener([HTTPError(self.first, 304, 'Not Modified', {}, io.BytesIO())])
        run('ntut-Tu', 'cloth_shop_server', self.state, self.output, opener=cached,
            dispatch_state=dispatched, candidates_path=candidates)
        self.assertEqual(len(candidates.read_text().splitlines()), 1)
        self.assertTrue(candidates.read_text().startswith('ntut-Tu\tcloth_shop_server\t2\t'))
        dispatched.write_text(dispatched.read_text() + candidates.read_text().rsplit('\t', 1)[0] + '\n')
        cache = json.loads(self.state.read_text())
        cache['repos']['ntut-Tu/cloth_shop_server']['next_allowed_at'] = 0
        self.state.write_text(json.dumps(cache))
        updated = pr(2)
        updated['base']['sha'] = 'c' * 40
        run('ntut-Tu', 'cloth_shop_server', self.state, self.output,
            opener=FakeOpener([Response([pr(1), updated], {'ETag': '"new"'})]),
            dispatch_state=dispatched, candidates_path=candidates)
        self.assertEqual(candidates.read_text().splitlines()[0].split('\t')[2], '2')

    def test_force_retest_queues_an_already_dispatched_revision(self):
        dispatched = Path(self.tmp.name) / 'dispatched.tsv'
        candidates = Path(self.tmp.name) / 'candidates.tsv'
        dispatched.write_text('ntut-Tu\tcloth_shop_server\t1\t' + 'a' * 40 + '\t' + 'b' * 40 + '\n')
        run('ntut-Tu', 'cloth_shop_server', self.state, self.output,
            opener=FakeOpener([Response([pr(1)], {})]),
            dispatch_state=dispatched, candidates_path=candidates)
        self.assertEqual(candidates.read_text(), '')
        run('ntut-Tu', 'cloth_shop_server', self.state, self.output,
            opener=FakeOpener([]), dispatch_state=dispatched, candidates_path=candidates,
            force_retest=True)
        self.assertTrue(candidates.read_text().startswith('ntut-Tu\tcloth_shop_server\t1\t'))

    def test_other_branch_and_fork_are_not_dispatched(self):
        dispatched = Path(self.tmp.name) / 'dispatched.tsv'
        candidates = Path(self.tmp.name) / 'candidates.tsv'
        other_branch = pr(2)
        other_branch['head']['ref'] = 'feature'
        fork = pr(3)
        fork['head']['repo']['full_name'] = 'someone/cloth_shop_server'
        opener = FakeOpener([Response([pr(1), other_branch, fork], {'ETag': '"first"'})])
        run('ntut-Tu', 'cloth_shop_server', self.state, self.output, opener=opener,
            dispatch_state=dispatched, candidates_path=candidates)
        self.assertEqual(len(candidates.read_text().splitlines()), 1)
        self.assertTrue(candidates.read_text().startswith('ntut-Tu\tcloth_shop_server\t1\t'))

    def test_legacy_dispatch_state_is_migrated(self):
        dispatched = Path(self.tmp.name) / 'dispatched.tsv'
        candidates = Path(self.tmp.name) / 'candidates.tsv'
        dispatched.write_text('cloth_shop_server\t1\t' + 'a' * 40 + '\t' + 'b' * 40 + '\n')
        run('ntut-Tu', 'cloth_shop_server', self.state, self.output,
            opener=FakeOpener([Response([pr(1)], {'ETag': '"first"'})]),
            dispatch_state=dispatched, candidates_path=candidates)
        self.assertEqual(candidates.read_text(), '')
        self.assertTrue(dispatched.read_text().startswith('ntut-Tu\tcloth_shop_server\t1\t'))

    def test_configured_owner_and_repository_are_used(self):
        item = pr(7)
        item['head']['repo']['full_name'] = 'example/api'
        dispatched = Path(self.tmp.name) / 'dispatched.tsv'
        candidates = Path(self.tmp.name) / 'candidates.tsv'
        opener = FakeOpener([Response([item], {'ETag': '"first"'})])
        run('example', 'api', self.state, self.output, opener=opener,
            dispatch_state=dispatched, candidates_path=candidates)
        self.assertIn('/repos/example/api/pulls?', opener.requests[0].full_url)
        self.assertTrue(candidates.read_text().startswith('example\tapi\t7\t'))

    def test_five_empty_polls_stop_requests_until_manual_reset(self):
        status = Path(self.tmp.name) / 'status.json'
        for expected in range(1, 6):
            if self.state.exists():
                cache = json.loads(self.state.read_text())
                cache['repos']['ntut-Tu/cloth_shop_server']['next_allowed_at'] = 0
                self.state.write_text(json.dumps(cache))
            run('ntut-Tu', 'cloth_shop_server', self.state, self.output,
                opener=FakeOpener([Response([], {})]), status_path=status)
            self.assertEqual(json.loads(status.read_text())['empty_polls'], expected)
        self.assertTrue(json.loads(status.read_text())['stopped'])
        no_request = FakeOpener([])
        run('ntut-Tu', 'cloth_shop_server', self.state, self.output,
            opener=no_request, status_path=status)
        self.assertEqual(no_request.requests, [])
        self.assertEqual(json.loads(status.read_text())['empty_polls'], 5)
        cache = json.loads(self.state.read_text())
        cache['repos']['ntut-Tu/cloth_shop_server']['next_allowed_at'] = 0
        self.state.write_text(json.dumps(cache))
        run('ntut-Tu', 'cloth_shop_server', self.state, self.output,
            opener=FakeOpener([Response([pr(1)], {})]), status_path=status, reset_polling=True)
        self.assertEqual(json.loads(status.read_text())['empty_polls'], 0)
        self.assertFalse(json.loads(status.read_text())['stopped'])

    def test_cached_skip_does_not_count_and_matching_pr_resets_count(self):
        status = Path(self.tmp.name) / 'status.json'
        run('ntut-Tu', 'cloth_shop_server', self.state, self.output,
            opener=FakeOpener([Response([], {})]), status_path=status)
        run('ntut-Tu', 'cloth_shop_server', self.state, self.output,
            opener=FakeOpener([]), status_path=status)
        self.assertEqual(json.loads(status.read_text())['empty_polls'], 1)
        cache = json.loads(self.state.read_text())
        cache['repos']['ntut-Tu/cloth_shop_server']['next_allowed_at'] = 0
        self.state.write_text(json.dumps(cache))
        run('ntut-Tu', 'cloth_shop_server', self.state, self.output,
            opener=FakeOpener([Response([pr(1)], {})]), status_path=status)
        self.assertEqual(json.loads(status.read_text())['empty_polls'], 0)


if __name__ == '__main__':
    unittest.main()
