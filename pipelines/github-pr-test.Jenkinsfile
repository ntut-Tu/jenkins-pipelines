pipeline {
    agent { label 'pdd-test' }
    environment {
        APPLICATION_REPO = 'https://github.com/ntut-Tu/cloth_shop_server.git'
    }
    options {
        timestamps()
        timeout(time: 40, unit: 'MINUTES')
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
        stage('Checkout and merge exact revision') {
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
                    withEnv(["HOME=${pwd()}"]) {
                        docker.image('maven:3.9.9-eclipse-temurin-17-noble').inside(
                                "-u 1000:1000 --group-add ${socketGroup} -v /var/run/docker.sock:/var/run/docker.sock") {
                            dir('application') {
                                sh '''
                                    set -eu
                                    export TESTCONTAINERS_HOST_OVERRIDE=host.docker.internal
                                    printf 'Testcontainers host override: %s\\n' "$TESTCONTAINERS_HOST_OVERRIDE"
                                    getent hosts "$TESTCONTAINERS_HOST_OVERRIDE"
                                    sh ./mvnw -B -ntp clean verify
                                '''
                            }
                        }
                    }
                }
            }
        }
    }
    post {
        always {
            junit testResults: 'application/target/surefire-reports/TEST-*.xml,application/target/failsafe-reports/TEST-*.xml', allowEmptyResults: true
            archiveArtifacts artifacts: 'pr-merge-info.txt', allowEmptyArchive: true
        }
        cleanup { deleteDir() }
    }
}
