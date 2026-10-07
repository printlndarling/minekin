# 经历调查的实际 Gateway 接线验收

基线 `9be5606`；运行期间主干前移到 `8d9de72`（仅合成执行器、其测试和记录）。后台经历筛选的组件与浏览器替身测试此前通过，但替身不证明实际 Gateway 接线。

本次以隔离临时根初始化测试身份，经 `SessionEventLog` 写入两条明确的**合成测试记录**：`collect_dropped / UNKNOWN / model` 与 `turn_to / CONFIRMED / local_reflection`。未复制、改写或迁移历史证据，未调用模型、启动 JVM 或连接游戏服务器。

真实 `GatewayServer` 仅绑定 `127.0.0.1:18791`；Vite preview 代理到该实例。启用 `E2E_LIVE_EXPERIENCES=1` 后，`pnpm exec playwright test e2e/experiences-live.spec.ts` 为 **1 passed**：实际 GET 数据进入页面、保留结果与来源、展开事件引用、按事件 ID 筛选、清除后恢复完整已加载列表；浏览器未发 API 写请求。截图人工检查为 768px 宽，控件与事件引用可见。网关在 90 秒有界窗口后自行退出，数据库文件 SHA-256 前后一致（`LEDGER_UNCHANGED=True`）。

这证明实际 HTTP→Gateway→页面的只读接线与筛选，不是当前构建真实模型决策、真实游玩、完整历史覆盖或 sealed evidence。真实 3×3 终产物与完整 S0–S11 交付仍未完成。
