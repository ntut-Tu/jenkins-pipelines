#!/usr/bin/env bash
# Run only inside the Jenkins agent's Maven container.
set -euo pipefail
application="$(cd -- "${1:?application directory required}" && pwd)"
producer="$(cd -- "${2:?producer directory required}" && pwd)"
: "${HEAD_SHA:?PR head SHA required}" "${JOB_NAME:?Jenkins job required}" "${BUILD_NUMBER:?Jenkins build required}" "${MAVEN_USER_HOME:?workspace Maven directory required}"
[[ "$HEAD_SHA" =~ ^[a-f0-9]{40}$ ]] || { echo 'Invalid PR head SHA' >&2; exit 1; }
cd -- "$application"
trap 'rm -f -- "$application/.ci-trace-pom.xml" "$application/.ci-trace-classes.txt"' EXIT
test "$(git rev-parse HEAD)" = "$HEAD_SHA"
test -s .ci-trace-pom.xml
test -s .ci-trace-classes.txt

# Install producer modules into this build's Maven repository; no fixture tests.
(cd -- "$producer" && sh ./mvnw -B -ntp \
    -Dmaven.repo.local="$MAVEN_USER_HOME/repository" \
    -pl trace-agent,trace-test-support -am -DskipTests clean install)

export TESTCONTAINERS_HOST_OVERRIDE=host.docker.internal
getent hosts "$TESTCONTAINERS_HOST_OVERRIDE"
sh ./mvnw -B -ntp -f .ci-trace-pom.xml \
    -Dmaven.repo.local="$MAVEN_USER_HOME/repository" -Dmaven.test.failure.ignore=true \
    clean org.jacoco:jacoco-maven-plugin:0.8.15:prepare-agent \
    verify org.jacoco:jacoco-maven-plugin:0.8.15:report

test -s target/jacoco.exec
test -s target/site/jacoco/jacoco.xml
test -s target/trace-observations.json
sh ./mvnw -B -ntp -f .ci-trace-pom.xml \
    -Dmaven.repo.local="$MAVEN_USER_HOME/repository" \
    -Dtrace.revision="$HEAD_SHA" -Dtrace.buildId="$JOB_NAME/$BUILD_NUMBER" \
    org.codehaus.mojo:exec-maven-plugin:3.5.0:java@ci-finalize-trace
test -s target/java-test-trace.json
