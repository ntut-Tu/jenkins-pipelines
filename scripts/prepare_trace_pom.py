"""Prepare a disposable Maven test POM for the single-module PR head job."""

import argparse
from pathlib import Path
import re
import xml.etree.ElementTree as ET


NS = 'http://maven.apache.org/POM/4.0.0'
VERSION = '0.1.0-SNAPSHOT'
ET.register_namespace('', NS)


def tag(name):
    return f'{{{NS}}}{name}'


def child(parent, name):
    """Return or create one direct Maven element."""
    found = parent.find(tag(name))
    return found if found is not None else ET.SubElement(parent, tag(name))


def value(parent, name, text):
    child(parent, name).text = text


def plugin(plugins, artifact):
    for item in plugins.findall(tag('plugin')):
        if item.findtext(tag('artifactId')) == artifact:
            return item
    item = ET.SubElement(plugins, tag('plugin'))
    value(item, 'artifactId', artifact)
    return item


def prepare(application: Path, producer: Path, include: str) -> Path:
    """Add test-only tracing; preserve source POM and existing test properties.

    Supports one conventional Maven module and top-level application classes.
    Rejects multi-module/Failsafe projects until separate trace outputs are supported.
    """
    application, producer = application.resolve(), producer.resolve()
    if not re.fullmatch(r'(?:[A-Za-z_]\w*\.)+', include):
        raise ValueError('include must be a Java package prefix ending in a dot')
    source = application / 'pom.xml'
    tree = ET.parse(source)
    project = tree.getroot()
    if project.tag != tag('project') or project.find(tag('modules')) is not None:
        raise ValueError('Trace integration requires a single-module Maven project')
    # Fail closed on configurations requiring per-fork / per-phase trace merging.
    for item in project.iter(tag('plugin')):
        if item.findtext(tag('artifactId')) == 'maven-failsafe-plugin':
            raise ValueError('Failsafe trace merging is not supported by this integration')
    if project.find(tag('profiles')) is not None:
        raise ValueError('Profile-specific test configuration requires explicit integration')

    classes = []
    sources = application / 'src/main/java'
    for path in sorted(sources.rglob('*.java')):
        name = '.'.join(path.relative_to(sources).with_suffix('').parts)
        if name.startswith(include) and path.stem not in {'package-info', 'module-info'}:
            classes.append(name)
    if not classes:
        raise ValueError('No application classes match trace.include')
    classes_file = application / '.ci-trace-classes.txt'
    classes_file.write_text('\n'.join(classes) + '\n')

    dependencies = child(project, 'dependencies')
    dependency = ET.SubElement(dependencies, tag('dependency'))
    for key, text in [('groupId', 'dev.codebase.trace'), ('artifactId', 'trace-test-support'),
                      ('version', VERSION), ('scope', 'test')]:
        value(dependency, key, text)
    plugins = child(child(project, 'build'), 'plugins')
    surefire = plugin(plugins, 'maven-surefire-plugin')
    value(surefire, 'groupId', 'org.apache.maven.plugins')
    value(surefire, 'version', '3.2.5')
    config = child(surefire, 'configuration')
    existing = config.findtext(tag('argLine'), '').strip()
    if existing:
        raise ValueError('Existing Surefire argLine requires explicit integration')
    agent = producer / f'trace-agent/target/trace-agent-{VERSION}.jar'
    value(config, 'argLine', f'@{{argLine}} -Dtrace.include={include} '
          f'"-Dtrace.classes={classes_file}" "-javaagent:{agent}"')
    value(config, 'forkCount', '1')
    value(config, 'reuseForks', 'true')
    props = child(config, 'systemPropertyVariables')
    for key, text in [('trace.enabled', 'true'), ('trace.sourceRoot', str(application)),
                      ('trace.output', str(application / 'target/trace-observations.json'))]:
        value(props, key, text)
    runner = plugin(plugins, 'exec-maven-plugin')
    value(runner, 'groupId', 'org.codehaus.mojo')
    value(runner, 'version', '3.5.0')
    execution = ET.SubElement(child(runner, 'executions'), tag('execution'))
    value(execution, 'id', 'ci-finalize-trace')
    value(child(execution, 'goals'), 'goal', 'java')
    config = child(execution, 'configuration')
    value(config, 'mainClass', 'dev.codebase.trace.output.TraceArtifactAssembler')
    value(config, 'classpathScope', 'test')
    arguments = child(config, 'arguments')
    for text in ['${project.build.directory}/trace-observations.json',
                 '${project.build.directory}/site/jacoco/jacoco.xml',
                 '${trace.revision}', '${trace.buildId}',
                 'PR head; single-module Surefire, one fork; source-backed top-level classes; '
                 'direct JUnit and synchronous in-JVM servlet HTTP; no arbitrary async propagation',
                 '${project.build.directory}/java-test-trace.json']:
        ET.SubElement(arguments, tag('argument')).text = text
    output = application / '.ci-trace-pom.xml'
    ET.indent(tree)
    tree.write(output, encoding='utf-8', xml_declaration=True)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('application', type=Path)
    parser.add_argument('producer', type=Path)
    parser.add_argument('--include', required=True)
    args = parser.parse_args()
    print(f'[PASS] Prepared trace test POM: {prepare(args.application, args.producer, args.include)}')


if __name__ == '__main__':
    main()
