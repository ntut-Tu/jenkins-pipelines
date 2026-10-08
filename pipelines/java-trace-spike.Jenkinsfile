pipeline {
    agent { label 'pdd-test' }
    options {
        timestamps()
        timeout(time: 20, unit: 'MINUTES')
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '10'))
        skipDefaultCheckout(true)
    }
    stages {
        stage('Checkout producer') {
            steps {
                deleteDir()
                checkout scm
                sh '''
                    printf 'Jenkins node: %s\\nWorkspace: %s\\nBuild: %s\\n' "$NODE_NAME" "$WORKSPACE" "$BUILD_URL"
                    git rev-parse HEAD > trace-spike-source-revision.txt
                '''
            }
        }
        stage('Run Java trace fixture') {
            steps {
                script {
                    withEnv(["MAVEN_USER_HOME=${pwd()}/.cache/maven-user"]) {
                        docker.image('maven:3.9.9-eclipse-temurin-17-noble').inside('-u 1000:1000') {
                            sh 'bash scripts/trace-spike.sh'
                        }
                    }
                }
            }
            post {
                always {
                    junit testResults: 'tools/java-test-trace/spike-fixture/target/surefire-reports/TEST-*.xml', allowEmptyResults: false
                }
                success {
                    // Required artifacts must all exist before declaring the spike successful.
                    sh '''
                        test -s tools/java-test-trace/spike-fixture/target/java-test-trace.json
                        test -s tools/java-test-trace/spike-fixture/target/trace-observations.json
                        test -s tools/java-test-trace/spike-fixture/target/site/jacoco/jacoco.xml
                    '''
                }
            }
        }
    }
    post {
        always {
            archiveArtifacts artifacts: 'trace-spike-source-revision.txt,tools/java-test-trace/spike-fixture/src/**,tools/java-test-trace/spike-fixture/target/surefire-reports/**,tools/java-test-trace/spike-fixture/target/site/jacoco/**,tools/java-test-trace/spike-fixture/target/trace-observations.json,tools/java-test-trace/spike-fixture/target/java-test-trace.json', allowEmptyArchive: true, fingerprint: true
        }
        cleanup { deleteDir() }
    }
}
