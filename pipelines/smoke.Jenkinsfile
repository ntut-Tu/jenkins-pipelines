pipeline {
    agent {
        docker {
            label 'pdd-test'
            image 'python:3.13-slim-bookworm@sha256:2325bb286ec344af3e5898cc224b5844e2707ac6e26b1632516fd3edc84a5e26'
            args '-u 1000:1000'
        }
    }
    options {
        timestamps()
        timeout(time: 10, unit: 'MINUTES')
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '30'))
    }
    parameters {
        choice(name: 'SCENARIO', choices: ['success', 'unstable', 'failure'], description: 'Expected integration-test outcome')
    }
    stages {
        stage('Test') {
            steps {
                sh 'python3 --version'
                sh 'python3 scripts/sample_tests.py --scenario "$SCENARIO" --output reports/junit.xml'
            }
        }
    }
    post {
        always {
            junit testResults: 'reports/junit.xml', allowEmptyResults: false
            archiveArtifacts artifacts: 'reports/junit.xml', allowEmptyArchive: false
        }
        cleanup { deleteDir() }
    }
}
