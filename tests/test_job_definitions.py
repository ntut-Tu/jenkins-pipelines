"""Repository checks for Job DSL inputs consumed by the Jenkins seed."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class JobDefinitionTests(unittest.TestCase):
    def test_seed_script_names_are_valid_groovy_identifiers(self):
        scripts = list((ROOT / 'jobs').rglob('*.groovy'))
        self.assertTrue(scripts)
        for script in scripts:
            with self.subTest(script=script.name):
                self.assertRegex(script.name, r'^[A-Za-z_][A-Za-z0-9_]*\.groovy$')

    def test_jobs_have_unique_names_and_existing_pipeline_files(self):
        jobs = {}
        for script in (ROOT / 'jobs').rglob('*.groovy'):
            content = script.read_text()
            for name in re.findall(r"pipelineJob\('([^']+)'\)", content):
                self.assertNotIn(name, jobs, f'{name} defined in {script} and {jobs.get(name)}')
                jobs[name] = script
            paths = re.findall(r"scriptPath\('([^']+)'\)", content)
            for path in paths:
                with self.subTest(script=script.name, path=path):
                    self.assertTrue((ROOT / path).is_file(), f'Missing pipeline: {path}')
        self.assertTrue(jobs)


if __name__ == '__main__':
    unittest.main()
