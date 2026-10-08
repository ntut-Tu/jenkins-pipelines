pipeline {
    agent { label 'pdd-test' }
    options {
        timestamps()
        timeout(time: 10, unit: 'MINUTES')
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '30'))
    }
    stages {
        stage('Fetch open PRs') {
            steps {
                sh 'rm -f github-prs.json github-pr-candidates.tsv github-pr-poll-status.json'
                script {
                    def fetch = {
                        docker.image('python:3.12.12-slim-bookworm').inside('-u 1000:1000') {
                            sh '''if [ "$RESET_POLLING" = true ]; then set -- --reset-polling; else set --; fi
python3 scripts/fetch_github_prs.py --owner "$OWNER" --repository "$REPOSITORY" --head-branch "$HEAD_BRANCH" --base-branch "$BASE_BRANCH" --state .github-pr-cache.json --output github-prs.json --dispatch-state .github-pr-dispatched.tsv --candidates github-pr-candidates.tsv --max-empty-polls "$MAX_EMPTY_POLLS" --status github-pr-poll-status.json "$@"'''
                        }
                    }
                    if (params.GITHUB_API_CREDENTIALS == 'github-api') {
                        withCredentials([string(credentialsId: 'github-api', variable: 'GITHUB_API_TOKEN')]) {
                            fetch()
                        }
                    } else if (params.GITHUB_API_CREDENTIALS == 'none') {
                        fetch()
                    } else {
                        error 'Invalid GitHub API credential selection'
                    }
                }
            }
        }
        stage('Queue matching PR tests') {
            steps {
                script {
                    if (!(params.TEST_JOB ==~ /^\/[A-Za-z0-9_.-]+(\/[A-Za-z0-9_.-]+)+$/)) {
                        error 'Invalid downstream test job path'
                    }
                    def lines = readFile(file: 'github-pr-candidates.tsv').readLines().findAll { it }
                    def dispatched = fileExists('.github-pr-dispatched.tsv') ? readFile(file: '.github-pr-dispatched.tsv') : ''
                    for (line in lines) {
                        def fields = line.split('\t', -1)
                        if (fields.length != 6 || fields[0] != params.OWNER || fields[1] != params.REPOSITORY) {
                            error 'Invalid PR candidate record'
                        }
                        build job: params.TEST_JOB, wait: false,
                            parameters: [
                                string(name: 'PR_NUMBER', value: fields[2]),
                                string(name: 'HEAD_SHA', value: fields[3]),
                                string(name: 'BASE_SHA', value: fields[4]),
                                string(name: 'BASE_BRANCH', value: fields[5]),
                                string(name: 'APPLICATION_GIT_CREDENTIALS', value: params.APPLICATION_GIT_CREDENTIALS)
                            ]
                        dispatched += fields.take(5).join('\t') + '\n'
                        writeFile file: '.github-pr-dispatched.tsv', text: dispatched
                        echo "Queued ${fields[0]}/${fields[1]} PR #${fields[2]} at ${fields[3].take(12)}"
                    }
                }
            }
        }
    }
    post {
        always {
            archiveArtifacts artifacts: 'github-prs.json', allowEmptyArchive: true
            script {
                if (!(params.POLL ==~ /^[A-Za-z0-9H*\/ ,\-]+$/) || params.POLL.tokenize(' ').size() != 5) {
                    error 'Invalid polling schedule'
                }
                def statusFile = fileExists('github-pr-poll-status.json') ? 'github-pr-poll-status.json' : '.github-pr-cache.json'
                def stopped = fileExists(statusFile) && readFile(file: statusFile).contains('"stopped": true')
                properties([
                    pipelineTriggers(stopped ? [] : [cron(params.POLL)]),
                    parameters([
                        choice(name: 'OWNER', choices: [params.OWNER], description: 'Configured GitHub owner'),
                        choice(name: 'REPOSITORY', choices: [params.REPOSITORY], description: 'Configured GitHub repository'),
                        choice(name: 'HEAD_BRANCH', choices: [params.HEAD_BRANCH], description: 'PR source branch'),
                        choice(name: 'BASE_BRANCH', choices: [params.BASE_BRANCH], description: 'PR target branch'),
                        choice(name: 'TEST_JOB', choices: [params.TEST_JOB], description: 'Downstream Jenkins test job'),
                        choice(name: 'POLL', choices: [params.POLL], description: 'Jenkins cron schedule'),
                        choice(name: 'MAX_EMPTY_POLLS', choices: [params.MAX_EMPTY_POLLS], description: 'Maximum consecutive empty polls'),
                        booleanParam(name: 'RESET_POLLING', defaultValue: false, description: 'Reset counter and resume automatic polling'),
                        choice(name: 'GITHUB_API_CREDENTIALS', choices: [params.GITHUB_API_CREDENTIALS], description: 'Managed GitHub credential'),
                        choice(name: 'APPLICATION_GIT_CREDENTIALS', choices: [params.APPLICATION_GIT_CREDENTIALS], description: 'Managed application Git credential')
                    ]),
                    buildDiscarder(logRotator(numToKeepStr: '30')),
                    disableConcurrentBuilds()
                ])
                echo stopped ? 'Stopped automatic polling; manual Build with Parameters remains available.' : 'Automatic polling remains active.'
            }
        }
    }
}
