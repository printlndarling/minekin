# P0 开发环境与工程门禁

## 固定基线

| 组件 | W00 基线 |
| --- | --- |
| Python | `>=3.12,<3.14`，由 uv 管理单项目锁文件 |
| Python runtime 依赖 | Protobuf；并发、SQLite、CLI 与 socket 使用标准库 |
| Python dev 依赖 | Ruff、Pyright、pytest |
| Java | 21 toolchain |
| Minecraft | 1.21.4 |
| Fabric | Loader 0.16.9、API 0.119.4+1.21.4、Yarn 1.21.4+build.8 |
| Bridge build | Gradle Wrapper、Fabric Loom、JUnit 5、依赖锁 |
| Node.js | P0 不需要，也不得成为构建前置 |

Web、Node、FastAPI、Pydantic、ORM/Alembic、Agent 框架、Baritone、媒体和容器均不属于 P0 core 依赖。Fabric/Minecraft 版本目前是候选执行基线，不代表已完成真实客户端验证。

## 本地初始化

```text
uv sync --locked --dev
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
uv run python tools/check_boundaries.py
```

Bridge 协议与适配器可在无 Gradle、无 Minecraft 的情况下验证。第一条只编译协议内核；第二条从 Maven Central 按 SHA-1 校验下载固定 protoc 与 javalite，再编译 W20 适配器并跑自测。两条都只要求本机 JDK：

```text
uv run --no-project python tools/check_bridge_scaffold.py
uv run --no-project python tools/check_bridge_protocol.py
uv run --no-project python tools/check_bridge_proto_java.py
```

Bridge 必须用 Java 21。仓库中的 wrapper 配置不会在检出时下载 Minecraft 或 Gradle 工件；首次执行下列命令才会解析候选依赖：

```text
cd bridge
./gradlew --version
./gradlew check
```

当前锁定工作流分两步：版本目录固定直接依赖，Gradle dependency locking 固定解析图。Java 21 环境第一次解析依赖后须生成并评审 lockfile 与 verification metadata，禁止把未评审的自动更新与功能变更混在同一提交：

```text
./gradlew dependencies --write-locks
./gradlew help --write-verification-metadata sha256
```

普通 CI 不下载 Minecraft 资产或启动图形客户端；真实 Fabric/Minecraft 矩阵只在受控 runner 执行并产出 evidence。

## 包边界

- `domain` 只包含纯值和规则，不导入 application、adapter 或基础设施模块。
- `application` 只依赖 domain 与 ports；SQLite、socket 和 subprocess 必须经 port。
- `adapters` 实现 ports，不决定 session 状态或生成高层结论。
- `entrypoints`/`cli` 只负责参数解析、装配、信号与退出码映射。
- `generated` 只放协议生成物，不手写领域默认值。
- `test-orchestrator` 与 oracle 属于测试域，不能被打进 `minekin-core` wheel 或 Bridge JAR。
