pipeline {
    agent {
        label 'go-agent'
    }

    options {
        timestamps()
        disableConcurrentBuilds()
    }

    stages {
        stage('Checkout MR') {
            steps {
                checkout scm

                sh '''
                    git fetch origin master
                '''
            }
        }

        stage('Go Test & Coverage') {
            steps {
                sh '''
                    go test -coverprofile=coverage.out ./...
                '''
            }
        }

        stage('Convert Coverage') {
            steps {

                sh '''
                    gocover-cobertura \
                      < coverage.out > coverage.xml
                '''
            }
        }

        stage('Diff Coverage Gate') {
            steps {
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