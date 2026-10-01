# Jenkins Pipelines

存放 Jenkins 工作定義與執行步驟。`jenkins-config` 的 seed 工作讀取 `jobs/`，
建立工作後由各工作執行 `pipelines/` 中的 Jenkinsfile。

## 現有工作

| Jenkins 工作 | 用途 |
| --- | --- |
| `pdd/integration-test` | 示範成功、測試失敗與建置失敗的結果，並顯示 JUnit 報告 |
| `pdd/cloth-shop-api-test` | 執行 `cloth_shop_server` 的產品服務單元測試與搜尋 API 整合測試 |

兩個工作都由使用者在 Jenkins 手動啟動。示範工作的 `SCENARIO` 可選擇：

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
| 工作名稱、參數、使用的 Jenkinsfile | [jobs/smoke.groovy](jobs/smoke.groovy) |
| 示範測試流程 | [pipelines/smoke.Jenkinsfile](pipelines/smoke.Jenkinsfile) |
| 被測專案 URL、分支與 Maven 測試指令 | [pipelines/cloth-shop-api.Jenkinsfile](pipelines/cloth-shop-api.Jenkinsfile) |

私有被測專案的 Git 帳號與 token 設在 `jenkins-config` 的 `credentials.application_git`。
更新工作定義後，可執行該專案的 `uv run --locked python -m jenkins_config seed`。

## 測試

本機測試需要 Python 3.12 以上與 uv。

```bash
uv run --locked python -m unittest discover -s tests -v
```
