from pathlib import Path
import re
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from render_jobs import DEFAULT_OUTPUT, DEFAULT_VALUES, load_jobs, main, render


class RendererTests(unittest.TestCase):
    def test_checked_in_dsl_matches_values(self):
        self.assertRegex(DEFAULT_OUTPUT.name, r'^[A-Za-z_][A-Za-z0-9_]*\.groovy$')
        content = render(load_jobs(DEFAULT_VALUES))
        self.assertIn("binding.hasVariable('GITHUB_API_CREDENTIALS') ? GITHUB_API_CREDENTIALS : 'none'", content)
        self.assertEqual(DEFAULT_OUTPUT.read_text(), content)

    def test_multiple_jobs_and_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            values = Path(directory) / 'values.yaml'
            output = Path(directory) / 'jobs.groovy'
            values.write_text('''fetch_pr_jobs:
  - name: fetch-pr-a
    repository: example/server
    head_branch: ci
    test_job: /pdd/test-a
  - name: fetch-pr-b
    repository: example/api
    head_branch: test
    base_branch: release
    test_job: /pdd/test-b
    poll: 'H/45 * * * *'
''')
            self.assertEqual(main(['--values', str(values), '--output', str(output)]), 0)
            self.assertEqual(main(['--values', str(values), '--output', str(output), '--check']), 0)
            content = output.read_text()
            self.assertIn("pipelineJob('pdd/fetch-pr-a')", content)
            self.assertIn("choiceParam('BASE_BRANCH', ['main']", content)
            self.assertIn("pipelineJob('pdd/fetch-pr-b')", content)
            self.assertIn("spec('H/45 * * * *')", content)
            self.assertIn("choiceParam('MAX_EMPTY_POLLS', ['5']", content)
            self.assertIn("booleanParam('FORCE_RETEST', false", content)
            values.write_text(values.read_text().replace('example/api', 'example/new-api'))
            self.assertEqual(main(['--values', str(values), '--output', str(output), '--check']), 1)

    def test_rejects_duplicate_names_and_groovy_injection(self):
        with tempfile.TemporaryDirectory() as directory:
            values = Path(directory) / 'values.yaml'
            values.write_text('''fetch_pr_jobs:
  - name: fetch-pr
    repository: example/server
    head_branch: ci
    test_job: /pdd/test-a
  - name: fetch-pr
    repository: example/api
    head_branch: test
    test_job: /pdd/test-b
''')
            with self.assertRaisesRegex(ValueError, 'duplicated'):
                load_jobs(values)
            values.write_text(values.read_text().replace('example/server', "example/server'); queue('evil"))
            with self.assertRaises(ValueError):
                load_jobs(values)

    def test_rejects_names_owned_by_static_jobs(self):
        root = Path(__file__).resolve().parents[1]
        names = []
        for script in (root / 'jobs').glob('*.groovy'):
            if script == DEFAULT_OUTPUT:
                continue
            names.extend(re.findall(r"pipelineJob\('pdd/([^']+)'\)", script.read_text()))
        self.assertTrue(names, 'Expected statically defined jobs')
        with tempfile.TemporaryDirectory() as directory:
            values = Path(directory) / 'values.yaml'
            for name in names:
                with self.subTest(name=name):
                    values.write_text(
                        f'fetch_pr_jobs:\n  - name: {name}\n'
                        '    repository: example/server\n'
                        '    head_branch: ci\n'
                        '    test_job: /pdd/test-a\n'
                    )
                    with self.assertRaisesRegex(ValueError, 'invalid or duplicated'):
                        load_jobs(values)

    def test_rejects_duplicate_yaml_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            values = Path(directory) / 'values.yaml'
            values.write_text('fetch_pr_jobs: []\nfetch_pr_jobs: []\n')
            with self.assertRaisesRegex(ValueError, 'duplicate YAML key'):
                load_jobs(values)

    def test_rejects_invalid_empty_poll_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            values = Path(directory) / 'values.yaml'
            values.write_text('''fetch_pr_jobs:
  - name: fetch-pr
    repository: example/server
    head_branch: ci
    test_job: /pdd/test-a
    max_empty_polls: 0
''')
            with self.assertRaisesRegex(ValueError, 'max_empty_polls'):
                load_jobs(values)


if __name__ == '__main__':
    unittest.main()
