pipeline {
    agent {
        label 'go-agent'
    }

    options {
        timestamps()
        disableConcurrentBuilds()
        gitLabConnection('gitlab')
                    gitlabBuilds(builds: ['go-test', 'go-build'])
    }

    stages {
        stage('Checkout MR') {
            steps gitlabCommitStatus('Checkout MR'){
                checkout scm

                sh '''
                    git fetch origin master
                '''
            }
        }

        stage('Go Test & Coverage') {
            steps gitlabCommitStatus('Go Test & Coverage'){
                sh '''
                    go test -coverprofile=coverage.out ./...
                '''
            }
        }

        stage('Convert Coverage') {
            steps gitlabCommitStatus('Convert Coverage'){

                sh '''
                    gocover-cobertura \
                      < coverage.out > coverage.xml
                '''
            }
        }

        stage('Diff Coverage Gate') {
            steps gitlabCommitStatus('Diff Coverage Gate'){
                sh '''
                    diff-cover coverage.xml \
                      --compare-branch=origin/master \
                      --fail-under=85.01 \
                      --html-report=diff-coverage.html
                '''
            }
        }
    }

    post {
        always {
            archiveArtifacts artifacts:
                'coverage.out,coverage.xml,diff-coverage.html',
                allowEmptyArchive: true

            cleanWs()
        }
    }
}