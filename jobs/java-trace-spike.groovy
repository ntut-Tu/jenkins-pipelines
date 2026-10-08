def sourceRepo = PIPELINE_REPO
def sourceBranch = PIPELINE_BRANCH
def sourceCredentials = PIPELINE_CREDENTIALS

folder('pdd') {
    displayName('PDD')
    description('Jobs managed by the pipelines repository')
}
pipelineJob('pdd/java-trace-spike') {
    description('Synthetic Java trace fixture on pdd-test; not PR coverage evidence.')
    definition {
        cpsScm {
            scm {
                git {
                    remote {
                        url(sourceRepo)
                        if (sourceCredentials) { credentials(sourceCredentials) }
                    }
                    branch(sourceBranch)
                }
            }
            scriptPath('pipelines/java-trace-spike.Jenkinsfile')
            lightweight(false)
        }
    }
}
