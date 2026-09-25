# Jenkins Pipelines

此 repo 管理 `jobs/smoke.groovy` 與 `pipelines/smoke.Jenkinsfile`。
Config 的 seed 同步 Job 定義；實際流程使用標準 Docker Pipeline，不含 K8s 分支。

## 新增與更新工作

- 在 jobs/ 加入 Job DSL，在 pipelines/ 加入 Jenkinsfile。
- seed 傳入 PIPELINE_REPO、PIPELINE_BRANCH、PIPELINE_CREDENTIALS，範例先將參數存為區域變數再進入 DSL closures。
- seed polling 同步來源；移除定義會停用 Job 並保留歷史，不需更改 config。

流程 repo 是受信任的管理程式碼；Job DSL 在 sandbox 執行。
範例 Job `pdd/integration-test` 仍由使用者手動觸發，未加入 PR／MR webhook。

## 範例測試

Pipeline 在 pdd-test 節點啟動固定 digest 的官方 Python 容器，執行相同測試腳本並發布 JUnit。
此流程產生 Jenkins Job／Build／測試資料供 PDD 串接，不測 PDD 業務功能。

| SCENARIO | Build 結果 | JUnit total / fail / skip |
| --- | --- | --- |
| success | SUCCESS | 3 / 0 / 1 |
| unstable | UNSTABLE | 3 / 1 / 1 |
| failure | FAILURE | 3 / 1 / 1 |

封存 reports/junit.xml、清理 workspace；禁止同時建置，保留 30 筆 Build。
更新 Jenkinsfile 或測試映像不需要重建 Jenkins 映像；agent 維持 Java／Git／Docker CLI。

## 驗證

```bash
uv run --locked python -m unittest discover -s tests -v
uv run --locked python scripts/sample_tests.py --scenario success --output reports/junit.xml
```

完整驗證由 config repo 的 tests/integration.py 執行；測試用依賴由 uv 管理。
Pipeline 內 Python 已由容器提供，執行標準庫測試不需要另裝 uv。
