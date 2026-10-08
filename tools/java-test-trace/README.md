# Java test trace producer spike

此 Maven 子專案屬於測試執行環境。由 Jenkins agent 或 sandbox 在測試 JVM
載入 trace agent 與 test-scope 支援；LLM Agent pod 不執行 Maven 或載入這些 JAR。
已新增獨立 `pdd/java-trace-spike` 的 Job DSL 與 Jenkinsfile；發布來源並執行 seed 後，
請在 Jenkins 按 Build Now 驗證。操作步驟見 [專案 README](../../README.md#jenkins-手動驗證)。
目前已通過本機測試及 Jenkinsfile 語法驗證，尚無 Jenkins spike 執行結果。

Jenkinsfile 會在 agent 的 Maven 容器中，從 jenkins-pipelines 根目錄呼叫：

```bash
./scripts/trace-spike.sh
```

需要 JDK 17；Maven Wrapper 提供 Maven 3.9.9。此指令不依賴 Python Agent 專案。
Maven 完成測試、JaCoCo XML 後，由 Java TraceArtifactAssembler 計算 XML SHA-256
並產生 `spike-fixture/target/java-test-trace.json`。

三個 JUnit fixture 包含普通方法呼叫與兩個並行 RANDOM_PORT HTTP 測試。
合成 trace 使用全零 revision、`complete=false`，不能用作真實 PR 證據。

## Modules

- `trace-runtime`：test token、context scope 與 observations。
- `trace-agent`：Byte Buddy 方法入口 instrumentation，透過 `-javaagent` 載入。
- `trace-test-support`：JUnit listener、Spring HTTP 上下文、source mapping、JSON 輸出與 finalizer。
- `spike-fixture`：Spring Boot 3.3.4／Java 17 測試，驗證 JAR 與 JaCoCo 同時載入。

尚未驗證任意 async／Reactor／多 JVM、多 Surefire fork、多 module 與 Spring AOP。
正式整合須使用實際 PR head、build ID、scope，並在 Jenkins 歸檔 XML 與最終 JSON。
