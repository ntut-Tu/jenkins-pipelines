#!/usr/bin/env python3
"""Run real sample tests with an explicit failure scenario for PDD integration checks."""
import argparse
import io
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET


def run(scenario, output):
    class SampleTests(unittest.TestCase):
        def test_success(self):
            self.assertEqual(sum([1, 2, 3]), 6)

        def test_scenario(self):
            self.assertEqual(scenario, 'success', 'Intentional failure selected for integration testing')

        @unittest.skip('Intentional skipped case for report verification')
        def test_skipped(self):
            self.fail('This case must be skipped')

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SampleTests)
    cases = list(suite)
    result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=2).run(suite)
    failures = {test.id(): detail for test, detail in result.failures}
    errors = {test.id(): detail for test, detail in result.errors}
    skipped = {test.id(): reason for test, reason in result.skipped}
    root = ET.Element('testsuite', name='pdd-integration', tests=str(result.testsRun), failures=str(len(failures)), errors=str(len(errors)), skipped=str(len(skipped)))
    for test in cases:
        node = ET.SubElement(root, 'testcase', classname='pdd.SampleTests', name=test._testMethodName)
        if test.id() in failures:
            ET.SubElement(node, 'failure', message='Intentional test failure').text = failures[test.id()]
        if test.id() in errors:
            ET.SubElement(node, 'error').text = errors[test.id()]
        if test.id() in skipped:
            ET.SubElement(node, 'skipped', message=skipped[test.id()])
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(output, encoding='utf-8', xml_declaration=True)
    print(f'scenario={scenario} tests={result.testsRun} failures={len(failures)} skipped={len(skipped)}')
    # UNSTABLE is assigned by Jenkins junit; FAILURE is an explicit failed shell step.
    return 1 if scenario == 'failure' else 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenario', choices=['success', 'unstable', 'failure'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    arguments = parser.parse_args()
    raise SystemExit(run(arguments.scenario, arguments.output))
