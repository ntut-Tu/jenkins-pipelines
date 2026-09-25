// Capture binding values before entering DSL closures (whose delegates have their own properties).
// Seed supplies only the source location and credential ID, never secret values.
def sourceRepo = PIPELINE_REPO
def sourceBranch = PIPELINE_BRANCH
def sourceCredentials = PIPELINE_CREDENTIALS
folder('pdd') {
    displayName('PDD')
    description('Jobs managed by the pipelines repository')
}
pipelineJob('pdd/integration-test') {
    description('Sample test; managed by seed from jenkins-pipelines.')
    parameters {
        choiceParam('SCENARIO', ['success', 'unstable', 'failure'], 'Expected test outcome')
    }
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
            scriptPath('pipelines/smoke.Jenkinsfile')
            lightweight(false)
        }
    }
}
