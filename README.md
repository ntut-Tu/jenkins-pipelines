# Jenkins Pipelines

存放 Jenkins 工作定義與執行步驟。`jenkins-config` 的 seed 工作讀取 `jobs/`，
建立工作後由各工作執行 `pipelines/` 中的 Jenkinsfile。

## 現有工作

| Jenkins 工作 | 用途 |
| --- | --- |
| `pdd/integration-test` | 示範成功、測試失敗與建置失敗的結果，並顯示 JUnit 報告 |
| `pdd/cloth-shop-api-test` | 執行 `cloth_shop_server` 的產品服務單元測試與搜尋 API 整合測試 |
| `pdd/fetch-pr` | 由 `value.yaml` 產生的範例：主動查詢 `cloth_shop_server` PR，符合分支規則時排入測試 |
| `pdd/test-all-server` | 將指定 PR head 合併到目標分支固定版本，再執行完整 `clean verify` |

`pdd/cloth-shop-api-test` 會產生並封存 JaCoCo XML。執行成功後，可在該次建置的
**Artifacts** 找到 `cloth_shop_server/target/site/jacoco/jacoco.xml`。若 Jenkins 根網址是
`http://localhost:18080/`，供同一台主機上的程式讀取最近一次成功建置的報告 URL 為：

```text
http://localhost:18080/job/pdd/job/cloth-shop-api-test/lastSuccessfulBuild/artifact/cloth_shop_server/target/site/jacoco/jacoco.xml
```

其他主機讀取時，需將 `localhost:18080` 換成該主機可連入的 Jenkins 位址。
需要登入才能下載 artifact 時，讀取端須使用 Jenkins 帳號及該帳號的 API Token。

`pdd/fetch-pr` 可按 **Build with Parameters** 執行，也會依 `value.yaml` 的排程輪詢。
每次建置查完 GitHub、排入需要的測試後便結束；下次由 cron 啟動新建置。
若連續 `max_empty_polls` 次成功查詢都沒有符合分支規則的 PR，會移除該 Job 的 cron，
停止自動輪詢。範例值為 5，因此每 30 分鐘查一次時，第 5 次空查詢後停止。
已符合規則但測試早已排入的 PR 仍算「有符合 PR」，會把空查詢計數歸零。
API 錯誤、rate limit 冷卻和因最短間隔沿用快取都不增加計數。
停止後仍可手動勾選 `RESET_POLLING` 執行，清除計數並恢復 cron；重新執行 seed 也可能重設 Job 的 cron，
下一次建置會依保存的計數狀態再次移除。計數保存在 Job workspace 的 `.github-pr-cache.json`。
目前的 `value.yaml` 只處理 `cloth_shop_server` 中 `range-filtering → main` 的開啟中 PR。
同一 PR 的 head SHA 或 base SHA 更新後，會再次排入設定的測試 Job。
若測試 Job 失敗但 PR 的 SHA 沒變，手動執行 `fetch-pr` 時勾選 `FORCE_RETEST`，
即可對目前符合規則的 PR 再排一次測試；一般輪詢仍只排入新版本。
只接受來源分支位於同一個 repo 的 PR，fork PR 不會自動執行。
符合來源與目標分支的 PR 清單封存在 `github-prs.json`，包含 PR 編號、連結、標題、head/base SHA 與分支。

`pdd/test-all-server` 會用固定的 PR head SHA 與 base SHA 驗證抓取到的 ref，
在本地將 head 合併到 base，再於 JDK 17／Maven 容器執行 `sh ./mvnw -B -ntp clean verify`。
容器透過現有 Docker socket 執行 server 測試所需的 Testcontainers。
測試會執行 PR 內的 Maven Wrapper 與程式碼，因此此 Job 應只供可信的同 repo 寫入者使用。
合併衝突或 ref 在排隊期間更新時，該次建置會失敗，不會改用新的 commit。
測試報告由 JUnit 收集，合併版本資訊封存為 `pr-merge-info.txt`。
輪詢 Job 在成功排入測試後記錄該版本，避免下次輪詢重複排入。

輪詢使用 GitHub REST `GET /repos/{owner}/{repo}/pulls`，以 `head` 和 `base` 限定分支，
每頁最多 100 筆，依 `Link` 標頭逐頁讀取。
各 Job workspace 的 `.github-pr-cache.json` 會保留每頁 ETag 和 PR 清單；下一次送出 `If-None-Match`，
收到 `304` 便沿用快取。工作不可並行；遇到 rate limit 時依 `Retry-After` 或 reset 時間暫停，
同一 repo 至少間隔 60 秒；遇到 `X-Poll-Interval` 會依較長的間隔延後查詢。
Console 會顯示 GitHub 回傳的剩餘額度與重置時間（若有提供）。
GitHub 一般 REST 額度為未認證每 IP 每小時 60 次，個人 token 每小時 5,000 次；
已認證且回傳 `304` 的條件式請求不消耗主要額度。參見
[GitHub rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api) 與
[GitHub API best practices](https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api)。
workspace 被清理時，下次會完整重抓並重新排入目前符合條件的 PR。

建議在 `jenkins-config/settings.local.yaml` 啟用 `credentials.github_api`，填入對所有設定 repo
具有 **Pull requests: read** 權限的 fine-grained token。Private repo 必須啟用；public repo
若不設定 token，仍可查詢，但共用未認證的較低 API 額度，且 `304` 不享有已認證請求的免額度待遇。
多個 Job 共用同一 token 的 GitHub 額度；依需求調整各自 `poll`，避免所有 repo 頻繁輪詢。
不要將 token 填在 Jenkins Job 參數。
若目前的 seed 尚未提供 `GITHUB_API_CREDENTIALS`，產生的 Job 會先使用 `none`；
要啟用已認證查詢，仍需部署提供該參數與憑證的 `jenkins-config` 設定。

## 新增 fetch PR Job

在 [value.yaml](value.yaml) 的 `fetch_pr_jobs` 增加一筆。例如：

```yaml
fetch_pr_jobs:
  - name: fetch-api-pr
    repository: your-org/your-api
    head_branch: jenkins-testing
    test_job: /pdd/test-your-api
```

`base_branch` 預設為 `main`，`poll` 預設為 `'H/30 * * * *'`，`max_empty_polls` 預設為 5，
需要時可逐筆覆寫。
`test_job` 必須是已存在的 Jenkins Job，接受 `PR_NUMBER`、`HEAD_SHA`、`BASE_SHA`、
`BASE_BRANCH`、`APPLICATION_GIT_CREDENTIALS` 五個參數；renderer 只建立 fetch Job。
新增目標 repo 的 private Git checkout 仍需設定 `credentials.application_git` 或對應的憑證方案。

本機需有 Python 3.12+ 與 PyYAML，或使用 uv 自動安裝鎖定的相依。用 shell 產生並檢查 Job DSL：

```bash
./render-jobs.sh
./render-jobs.sh --check
```

產物為 [jobs/generated_fetch_pr.groovy](jobs/generated_fetch_pr.groovy)，由既有 seed 的
`jobs/**/*.groovy` 規則載入。將 `value.yaml` 與產物一起送到配置的 pipeline repo 分支，
再執行 `jenkins-config` 的 `uv run --locked python -m jenkins_config seed`。

示範工作的 `SCENARIO` 可選擇：

| 值 | Jenkins 結果 |
| --- | --- |
| `success` | SUCCESS |
| `unstable` | UNSTABLE（測試失敗） |
| `failure` | FAILURE（測試指令失敗） |

## 使用

1. 在 `jenkins-config/settings.local.yaml` 設定 `pipeline.repository.url` 與 `pipeline.repository.branch`。
2. 執行該專案的 `./deploy.sh`；Jenkins 的 seed 工作會建立上述工作。
3. 在 Jenkins 開啟工作，選擇 **Build with Parameters** 執行。

## 修改

| 要修改的內容 | 檔案 |
| --- | --- |
| 固定測試 Job 與示範工作 | [jobs/smoke.groovy](jobs/smoke.groovy) |
| fetch PR Job 清單與渲染器 | [value.yaml](value.yaml)、[scripts/render_jobs.py](scripts/render_jobs.py) |
| 示範測試流程 | [pipelines/smoke.Jenkinsfile](pipelines/smoke.Jenkinsfile) |
| 被測專案 URL、分支與 Maven 測試指令 | [pipelines/cloth-shop-api.Jenkinsfile](pipelines/cloth-shop-api.Jenkinsfile) |
| PR 擷取、排入測試與 API 邏輯 | [pipelines/github-pr-poll.Jenkinsfile](pipelines/github-pr-poll.Jenkinsfile)、[scripts/fetch_github_prs.py](scripts/fetch_github_prs.py) |
| 完整 server PR 測試 | [pipelines/github-pr-test.Jenkinsfile](pipelines/github-pr-test.Jenkinsfile) |

私有被測專案的 Git 帳號與 token 設在 `jenkins-config` 的 `credentials.application_git`。
更新工作定義後，可執行該專案的 `uv run --locked python -m jenkins_config seed`。

## 測試

本機測試需要 Python 3.12 以上與 PyYAML。

```bash
python3 -m unittest discover -s tests -v
```
