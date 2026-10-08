"""Protect application POM isolation and supported tracing boundaries."""

from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from prepare_trace_pom import prepare, tag


class TracePomTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.app = self.root / 'application'
        self.app.mkdir()
        self.pom = self.app / 'pom.xml'
        self.original = '''<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion><groupId>example</groupId><artifactId>app</artifactId><version>1</version>
  <build><plugins><plugin><artifactId>maven-surefire-plugin</artifactId><configuration>
    <systemPropertyVariables><postgres.image>${postgres.image}</postgres.image></systemPropertyVariables>
    <includes><include>**/*Test.java</include></includes>
  </configuration></plugin></plugins></build>
</project>'''
        self.pom.write_text(self.original)
        for base, name in [('src/main/java', 'Service'), ('src/test/java', 'ServiceTest'),
                           ('target/generated-sources/jooq', 'GeneratedTable')]:
            path = self.app / base / 'example/app' / f'{name}.java'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f'package example.app; public class {name} {{}}')

    def test_preserves_source_and_existing_test_configuration(self):
        output = prepare(self.app, self.root / 'producer', 'example.app.')
        self.assertEqual(self.pom.read_text(), self.original)
        project = ET.parse(output).getroot()
        config = project.find(f"{tag('build')}/{tag('plugins')}/{tag('plugin')}/{tag('configuration')}")
        self.assertEqual(config.findtext(f"{tag('systemPropertyVariables')}/{tag('postgres.image')}"), '${postgres.image}')
        self.assertEqual(config.findtext(f"{tag('includes')}/{tag('include')}"), '**/*Test.java')
        self.assertIn('@{argLine}', config.findtext(tag('argLine')))
        self.assertEqual(config.findtext(tag('forkCount')), '1')
        dependencies = project.find(tag('dependencies'))
        self.assertEqual(dependencies.findtext(f"{tag('dependency')}/{tag('scope')}"), 'test')
        self.assertEqual((self.app / '.ci-trace-classes.txt').read_text(), 'example.app.Service\n')

    def test_uses_runtime_provenance_not_fixture_revision(self):
        content = prepare(self.app, self.root / 'producer', 'example.app.').read_text()
        self.assertIn('${trace.revision}', content)
        self.assertIn('${trace.buildId}', content)
        self.assertNotIn('local-java-trace-spike', content)
        self.assertNotIn('0' * 40, content)

    def test_rejects_unsupported_test_configurations(self):
        cases = {
            'modules': '<modules><module>child</module></modules>',
            'profiles': '<profiles><profile><id>integration</id></profile></profiles>',
        }
        for label, element in cases.items():
            with self.subTest(label=label):
                self.pom.write_text(self.original.replace('</project>', element + '</project>'))
                with self.assertRaises(ValueError):
                    prepare(self.app, self.root / 'producer', 'example.app.')
        self.pom.write_text(self.original.replace('maven-surefire-plugin', 'maven-failsafe-plugin'))
        with self.assertRaisesRegex(ValueError, 'Failsafe'):
            prepare(self.app, self.root / 'producer', 'example.app.')

    def test_existing_jvm_arguments_are_not_silently_overwritten(self):
        self.pom.write_text(self.original.replace('<configuration>', '<configuration><argLine>-Xmx2g</argLine>'))
        with self.assertRaisesRegex(ValueError, 'argLine'):
            prepare(self.app, self.root / 'producer', 'example.app.')

    def test_no_matching_classes_is_an_error(self):
        with self.assertRaisesRegex(ValueError, 'No application classes'):
            prepare(self.app, self.root / 'producer', 'other.')


if __name__ == '__main__':
    unittest.main()
