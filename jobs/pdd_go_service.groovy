def repo = PIPELINE_REPO
def branchName = PIPELINE_BRANCH
def credentialsId = PIPELINE_CREDENTIALS

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

            // Cancel outdated builds when MR is updated
            cancelPendingBuildsOnUpdate(true)
            cancelRunningBuildsOnUpdate(true)

            // Webhook authentication
            secretToken(System.getenv('GITLAB_WEBHOOK_SECRET'))
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