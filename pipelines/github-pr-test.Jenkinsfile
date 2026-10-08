pipeline {
    agent { label 'pdd-test' }
    environment {
        APPLICATION_REPO = 'https://github.com/ntut-Tu/cloth_shop_server.git'
    }
    options {
        timestamps()
        timeout(time: 80, unit: 'MINUTES')
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '30'))
        skipDefaultCheckout()
    }
    stages {
        stage('Validate PR revision') {
            steps {
                script {
                    if (!(params.PR_NUMBER ==~ /^[1-9][0-9]*$/)
                            || !(params.HEAD_SHA ==~ /^[a-f0-9]{40}$/)
                            || !(params.BASE_SHA ==~ /^[a-f0-9]{40}$/)
                            || !(params.BASE_BRANCH ==~ '^[A-Za-z0-9_][A-Za-z0-9_./-]*$')
                            || params.BASE_BRANCH.contains('..') || params.BASE_BRANCH.endsWith('/')) {
                        error 'Invalid PR revision parameters'
                    }
                    if (!(params.APPLICATION_GIT_CREDENTIALS in ['none', 'application-git'])) {
                        error 'Invalid application Git credential selection'
                    }
                }
            }
        }
        stage('Checkout trace tools') {
            steps {
                dir('pipeline-tools') {
                    deleteDir()
                    checkout scm
                }
            }
        }
        stage('Checkout exact PR head') {
            steps {
                dir('application') {
                    script {
                        deleteDir()
                        def remote = [
                            url: env.APPLICATION_REPO,
                            refspec: "+refs/heads/${params.BASE_BRANCH}:refs/remotes/origin/${params.BASE_BRANCH} +refs/pull/${params.PR_NUMBER}/head:refs/remotes/origin/pr-${params.PR_NUMBER}"
                        ]
                        if (params.APPLICATION_GIT_CREDENTIALS == 'application-git') {
                            remote.credentialsId = 'application-git'
                        }
                        checkout([$class: 'GitSCM',
                            branches: [[name: "*/${params.BASE_BRANCH}"]],
                            extensions: [[$class: 'CloneOption', honorRefspec: true]],
                            userRemoteConfigs: [remote]])
                    }
                    sh '''
                        set -eu
                        test "$(git rev-parse "refs/remotes/origin/$BASE_BRANCH")" = "$BASE_SHA"
                        test "$(git rev-parse "refs/remotes/origin/pr-$PR_NUMBER")" = "$HEAD_SHA"
                        git checkout --detach "$HEAD_SHA"
                    '''
                }
            }
        }
        stage('PR head coverage and trace for Agent') {
            steps {
                // Keep merge verification runnable when the head build itself fails.
                catchError(buildResult: 'FAILURE', stageResult: 'FAILURE', catchInterruptions: false) {
                    script {
                        dir('agent-analysis') { deleteDir() }
                        docker.image('python:3.12.12-slim-bookworm').inside('-u 1000:1000') {
                            sh 'python3 pipeline-tools/scripts/prepare_trace_pom.py application pipeline-tools/tools/java-test-trace --include com.clothingstore.shop.'
                        }
                        def socketGroup = sh(script: 'stat -c %g /var/run/docker.sock', returnStdout: true).trim()
                        if (!(socketGroup ==~ /^[0-9]+$/)) {
                            error 'Invalid Docker socket group'
                        }
                        withEnv(["MAVEN_USER_HOME=${pwd()}/.m2"]) {
                            docker.image('maven:3.9.9-eclipse-temurin-17-noble').inside(
                                    "-u 1000:1000 --group-add ${socketGroup} -v /var/run/docker.sock:/var/run/docker.sock") {
                                sh 'bash pipeline-tools/scripts/pr-head-trace.sh application pipeline-tools/tools/java-test-trace'
                            }
                        }
                        sh '''
                            set -eu
                            test "$(git -C application rev-parse HEAD)" = "$HEAD_SHA"
                            mkdir -p agent-analysis
                            cp application/target/site/jacoco/jacoco.xml agent-analysis/jacoco.xml
                            cp application/target/java-test-trace.json agent-analysis/java-test-trace.json
                        '''
                        def digest = sh(script: "sha256sum agent-analysis/jacoco.xml | cut -d ' ' -f 1", returnStdout: true).trim()
                        if (!(digest ==~ /^[a-f0-9]{64}$/)) {
                            error 'Invalid coverage digest'
                        }
                        writeFile file: 'agent-analysis/coverage-metadata.json', text: groovy.json.JsonOutput.toJson([
                            schema_version: 1,
                            revision: params.HEAD_SHA,
                            coverage_sha256: digest,
                            build_id: "${env.JOB_NAME}/${env.BUILD_NUMBER}".toString(),
                            scope: 'PR head; Maven clean verify; tests selected by project POM; test failures retained in JUnit'
                        ])
                        archiveArtifacts artifacts: 'agent-analysis/jacoco.xml,agent-analysis/coverage-metadata.json,agent-analysis/java-test-trace.json',
                            allowEmptyArchive: false, fingerprint: true
                    }
                }
            }
            post {
                always {
                    archiveArtifacts artifacts: 'application/target/trace-observations.json', allowEmptyArchive: true
                    // Publish before the merged build's clean removes the head reports.
                    junit testResults: 'application/target/surefire-reports/TEST-*.xml,application/target/failsafe-reports/TEST-*.xml',
                        allowEmptyResults: true, checksName: 'PR head tests'
                }
            }
        }
        stage('Merge exact revision') {
            steps {
                dir('application') {
                    sh '''
                        set -eu
                        git checkout --detach "$BASE_SHA"
                        git -c user.name='PDD Jenkins' -c user.email='ci@example.invalid' merge --no-ff --no-edit "$HEAD_SHA"
                        {
                            printf 'PR=%s\\nHEAD_SHA=%s\\nBASE_SHA=%s\\n' "$PR_NUMBER" "$HEAD_SHA" "$BASE_SHA"
                            git rev-parse HEAD
                            git rev-parse HEAD^{tree}
                        } > ../pr-merge-info.txt
                    '''
                }
            }
        }
        stage('Test all server') {
            steps {
                script {
                    def socketGroup = sh(script: 'stat -c %g /var/run/docker.sock', returnStdout: true).trim()
                    if (!(socketGroup ==~ /^[0-9]+$/)) {
                        error 'Invalid Docker socket group'
                    }
                    withEnv(["MAVEN_USER_HOME=${pwd()}/.m2"]) {
                        docker.image('maven:3.9.9-eclipse-temurin-17-noble').inside(
                                "-u 1000:1000 --group-add ${socketGroup} -v /var/run/docker.sock:/var/run/docker.sock") {
                            dir('application') {
                                sh '''
                                    set -eu
                                    export TESTCONTAINERS_HOST_OVERRIDE=host.docker.internal
                                    printf 'Testcontainers host override: %s\\n' "$TESTCONTAINERS_HOST_OVERRIDE"
                                    getent hosts "$TESTCONTAINERS_HOST_OVERRIDE"
                                    sh ./mvnw -B -ntp -Dmaven.repo.local="$MAVEN_USER_HOME/repository" clean verify
                                '''
                            }
                        }
                    }
                }
            }
            post {
                always {
                    junit testResults: 'application/target/surefire-reports/TEST-*.xml,application/target/failsafe-reports/TEST-*.xml',
                        allowEmptyResults: true, checksName: 'Merged tests'
                }
            }
        }
    }
    post {
        always {
            archiveArtifacts artifacts: 'pr-merge-info.txt', allowEmptyArchive: true
        }
        cleanup { deleteDir() }
    }
}
