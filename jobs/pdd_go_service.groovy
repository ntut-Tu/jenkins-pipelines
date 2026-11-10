def repo = PIPELINE_REPO
def branchName = PIPELINE_BRANCH
def credentialsId = PIPELINE_CREDENTIALS

pipelineJob('pdd/go-service') {
    description('Go service MR quality check')

    definition {
        cpsScm {
            scm {
                git {
                    remote {
                        url(repo)

                        if (credentialsId) {
                            credentials(credentialsId)
                        }
                    }

                    branch(branchName)
                }
            }

            scriptPath('pipelines/pdd-go-service.Jenkinsfile')
            lightweight(false)
        }
    }
}