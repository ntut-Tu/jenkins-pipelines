#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export MAVEN_USER_HOME="${TRACE_MAVEN_USER_HOME:-$PROJECT_ROOT/.cache/maven-user}"
cd -- "$PROJECT_ROOT/tools/java-test-trace"
exec ./mvnw -B -ntp -Dmaven.repo.local="${TRACE_MAVEN_REPO:-$PROJECT_ROOT/.cache/maven}" clean verify
