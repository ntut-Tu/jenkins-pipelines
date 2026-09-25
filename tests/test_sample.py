import importlib.util
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('sample_tests', ROOT / 'scripts/sample_tests.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ReportTests(unittest.TestCase):
    def test_all_scenarios(self):
        for scenario, code, failures in [('success', 0, 0), ('unstable', 0, 1), ('failure', 1, 1)]:
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as directory:
                report = Path(directory) / 'reports/junit.xml'
                self.assertEqual(module.run(scenario, report), code)
                root = ET.parse(report).getroot()
                self.assertEqual(root.attrib['tests'], '3')
                self.assertEqual(root.attrib['skipped'], '1')
                self.assertEqual(len(root.findall('testcase/failure')), failures)
                self.assertEqual(len(root.findall('testcase')), 3)
