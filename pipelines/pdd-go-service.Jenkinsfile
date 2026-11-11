pipeline {
    agent { label 'pdd-test' }
    options {
        timestamps()
        timeout(time: 30, unit: 'MINUTES')
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '50'))
        skipDefaultCheckout()   // 預設的 checkout 會拉到 pipelines repo，不是 Go 專案
    }
    environment {
        STATUS_NAME = 'jenkins/go-ci'
        DIFF_COVERAGE_FAIL_UNDER = '85.01'
    }
    stages {
        stage('Checkout MR') {
            steps {
                script {
                    if (!(env.gitlabMergeRequestIid ==~ /\d+/) || !(env.gitlabMergeRequestLastCommit ==~ /[0-9a-f]{40}/)
                            || !env.gitlabTargetRepoHttpUrl || !(env.gitlabTargetBranch ==~ /[A-Za-z0-9._\/-]+/)) {
                        error('This job only runs from a GitLab merge request webhook; merge request data is missing.')
                    }
                }
                updateGitlabCommitStatus name: env.STATUS_NAME, state: 'running'
                checkout([$class: 'GitSCM',
                    branches: [[name: env.gitlabMergeRequestLastCommit]],
                    userRemoteConfigs: [[
                        name: 'origin',
                        url: env.gitlabTargetRepoHttpUrl,
                        credentialsId: 'gitlab-git',
                        refspec: "+refs/heads/${env.gitlabTargetBranch}:refs/remotes/origin/${env.gitlabTargetBranch} " +
                                 "+refs/merge-requests/${env.gitlabMergeRequestIid}/head:refs/remotes/origin/merge-requests/${env.gitlabMergeRequestIid}"
                    ]],
                    extensions: [
                        [$class: 'CloneOption', noTags: true, shallow: false, honorRefspec: true],
                        [$class: 'CleanBeforeCheckout']
                    ]
                ])
            }
        }
        stage('Go test & coverage') {
            agent {
                docker {
                    image 'golang:1.27-bookworm@sha256:4fa7c968ba93f1635670522dbb01a2c78150443e1385746924566079f36570ea'
                    reuseNode true
                }
            }
            steps {
                sh '''
                    export HOME="$WORKSPACE/.ci/home" GOPATH="$WORKSPACE/.ci/go" GOCACHE="$WORKSPACE/.ci/go-build" GOFLAGS=-modcacherw
                    mkdir -p "$HOME" reports
                    go version
                    go run gotest.tools/gotestsum@v1.13.0 --format testname --junitfile reports/junit.xml -- \
                        -covermode=atomic -coverprofile=coverage.out ./...
                    go run github.com/boumenot/gocover-cobertura@v1.5.0 < coverage.out > coverage.xml
                '''
            }
        }
        stage('Diff coverage gate') {
            agent {
                docker {
                    image 'python:3.13-bookworm@sha256:cc55e4ded9c95f6ce2133b3d096db43f214d280c2a8af65d83e246c8fa7d168c'
                    reuseNode true
                }
            }
            steps {
                sh '''
                    export HOME="$WORKSPACE/.ci/home" PIP_DISABLE_PIP_VERSION_CHECK=1
                    python3 -m venv .ci/venv
                    .ci/venv/bin/pip install --quiet --no-cache-dir diff-cover==11.0.1
                    .ci/venv/bin/diff-cover coverage.xml \
                        --compare-branch="origin/$gitlabTargetBranch" \
                        --fail-under="$DIFF_COVERAGE_FAIL_UNDER" \
                        --total-percent-float \
                        --format "html:diff-coverage.html"
                '''
            }
        }
    }
    post {
        always {
            junit testResults: 'reports/junit.xml', allowEmptyResults: true
            archiveArtifacts artifacts: 'coverage.out,coverage.xml,diff-coverage.html,reports/junit.xml', allowEmptyArchive: true
        }
        success { updateGitlabCommitStatus name: env.STATUS_NAME, state: 'success' }
        unstable { updateGitlabCommitStatus name: env.STATUS_NAME, state: 'failed' }
        failure { updateGitlabCommitStatus name: env.STATUS_NAME, state: 'failed' }
        aborted { updateGitlabCommitStatus name: env.STATUS_NAME, state: 'canceled' }
        cleanup { deleteDir() }
    }
}