# ADR 0001：P0 使用两进程模块化单体

- 状态：Accepted
- 日期：2026-09-18
- 范围：W00–W70

## 背景

P0 要验证真实 Minecraft 客户端的启动、握手、入服、受限观察、短输入 lease、松键和崩溃恢复。它还没有远程管理、多 Kin 调度、模型编排或复杂关系型迁移需求。提前引入产品终态的服务和框架，会扩大故障面并削弱证据归因。

## 决策

P0 仅运行两个主要进程：一个 Python 3.12–3.13 `minekin-core` 模块化单体，以及一个加载 Java 21 Fabric Thin Bridge 的 Minecraft JVM。

- 不引入 Web API 或 Dashboard；P0 的管理入口是本地 CLI。
- 不引入 ORM；持久化使用标准库 `sqlite3`，经单 writer-thread/repository 边界访问。
- 不引入通用 Agent 框架；P0 没有模型或 PlayerMind，session、generation、lease 与恢复语义由领域内核持有。
- 不拆成多个 Python 服务；`domain → application ports ← adapters` 的包边界保留未来拆分可能，但当前共享一个进程和锁文件。
- Thin Bridge 只持有客户端线程相关的观察、反射和输入安全职责，不持有人格、长期记忆或高层决策。

## 后果

构建、部署和故障注入保持足够小，P0 evidence 可以指向单一责任边界。代价是未来引入 Dashboard、复杂迁移或独立权限域时需要新增进程/API；只有相应升级触发条件出现时才做该拆分。

CI 必须阻止领域/应用层反向导入 adapters，产品包不得包含测试 oracle。完整约束见 `docs/p0-core-internal-architecture.md` 与 `docs/technical-stack-selection.md`。
