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
                    script {
                        def applicationRemote = [url: env.APPLICATION_REPO]
                        if (params.APPLICATION_GIT_CREDENTIALS == 'application-git') {
                            if (!env.APPLICATION_REPO.startsWith('https://')) {
                                error 'Private application checkout requires HTTPS'
                            }
                            applicationRemote.credentialsId = 'application-git'
                        } else if (params.APPLICATION_GIT_CREDENTIALS != 'none') {
                            error 'Invalid application Git credential selection'
                        }
                        checkout([$class: 'GitSCM',
                            branches: [[name: "*/${env.APPLICATION_BRANCH}"]],
                            userRemoteConfigs: [applicationRemote]])
                    }
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
