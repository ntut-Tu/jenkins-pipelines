def sourceRepo = PIPELINE_REPO
def sourceBranch = PIPELINE_BRANCH
def sourceCredentials = PIPELINE_CREDENTIALS
def webhookSecret = GITLAB_WEBHOOK_SECRET   // 由 seed 從 Jenkins credential 傳入

if (!webhookSecret) {
    // config 沒啟用 GitLab：不產生 Job，seed 會停用舊的
    return
}

// Job DSL 每個 script 各自建立 Job，順序不固定，所以這裡也要宣告資料夾
folder('pdd') {
    displayName('PDD')
    description('Jobs managed by the pipelines repository')
}

pipelineJob('pdd/go-service') {
    description('Go CI for GitLab merge requests targeting master. Reports commit status "jenkins/go-ci".')
    properties {
        gitLabConnection {
            gitLabConnection('gitlab')
        }
        pipelineTriggers {
            triggers {
                gitlab {
                    triggerOnPush(false)
                    triggerOnMergeRequest(true)
                    triggerOnlyIfNewCommitsPushed(true)
                    triggerOpenMergeRequestOnPush('never')
                    triggerOnNoteRequest(false)
                    triggerOnPipelineEvent(false)
                    triggerOnAcceptedMergeRequest(false)
                    triggerOnClosedMergeRequest(false)
                    triggerOnApprovedMergeRequest(false)
                    branchFilterType('RegexBasedFilter')
                    targetBranchRegex('^master$')
                    skipWorkInProgressMergeRequest(true)
                    ciSkip(true)
                    setBuildDescription(true)
                    pendingBuildName('jenkins/go-ci')
                    cancelPendingBuildsOnUpdate(true)
                    secretToken(webhookSecret)
                }
            }
        }
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
            scriptPath('pipelines/pdd-go-service.Jenkinsfile')
            lightweight(false)
        }
    }
}