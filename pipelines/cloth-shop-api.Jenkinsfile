pipeline {
    agent { label 'pdd-test' }
    environment {
        APPLICATION_REPO = 'https://github.com/ntut-Tu/cloth_shop_server.git'
        APPLICATION_BRANCH = 'jenkins-test'
    }
    options {
        timestamps()
        timeout(time: 20, unit: 'MINUTES')
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '30'))
        skipDefaultCheckout()
    }
    stages {
        stage('Checkout application') {
            steps {
                dir('cloth_shop_server') {
                    checkout([$class: 'GitSCM',
                        branches: [[name: "*/${env.APPLICATION_BRANCH}"]],
                        userRemoteConfigs: [[url: env.APPLICATION_REPO]]])
                }
            }
        }
        stage('Product unit and API tests') {
            steps {
                dir('cloth_shop_server') {
                    sh 'sh ./mvnw -B -ntp -Dtest=ProductServiceTest,ProductApiIntegrationTest test'
                }
            }
        }
    }
    post {
        always {
            junit testResults: 'cloth_shop_server/target/surefire-reports/TEST-*.xml', allowEmptyResults: false
        }
        cleanup { deleteDir() }
    }
}
