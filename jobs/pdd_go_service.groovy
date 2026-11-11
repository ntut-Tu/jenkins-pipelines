def repo = PIPELINE_REPO
def branchName = PIPELINE_BRANCH
def credentialsId = PIPELINE_CREDENTIALS
def webhookSecret = binding.hasVariable('gitlabWebhookSecret')
        ? binding.getVariable('gitlabWebhookSecret')
        : ''
pipelineJob('pdd/go-service') {
    description('Go service MR quality check')
    triggers {
        gitlab {
            // Trigger only on Merge Request events
            triggerOnPush(false)
            triggerOnMergeRequest(true)

            // Ignore other events
            triggerOnNoteRequest(false)
            triggerOnPipelineEvent(false)
            triggerOnAcceptedMergeRequest(false)
            triggerOnClosedMergeRequest(false)
            triggerOnApprovedMergeRequest(false)

            // Only MR targeting master
            targetBranchRegex('^master$')

            // Skip draft / WIP merge requests
            skipWorkInProgressMergeRequest(true)

            // Webhook authentication
            secretToken(webhookSecret)
        }
    }
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