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
| Node.js | 产品不需要；构建不前置；**但 Pyright 门禁需要 Node 运行时**，见下文 |

Web、Node、FastAPI、Pydantic、ORM/Alembic、Agent 框架、Baritone、媒体和容器均不属于 P0 core 依赖。Fabric/Minecraft 版本目前是候选执行基线，不代表已完成真实客户端验证。

`uv run pyright` 是本仓库唯一需要 Node 的步骤，而它并不自带运行时：Pyright 先找 `PATH` 上的 `node`（默认 `PYRIGHT_PYTHON_GLOBAL_NODE=1`），找不到就用 `nodeenv` 从网络安装一个到 `%USERPROFILE%\.cache\pyright-python\nodeenv`。实测：本机 `PATH` 上的 node 是 v22.22.3，把 node 移出 `PATH` 后 Pyright 下载了 26.9.0。因此**同一份代码在不同主机上会跑在不同 Node 版本下**，且完全离线的环境跑不了这道门禁。

现在这道门禁**已经固定**：开发依赖写成 `pyright[nodejs]`，锁文件里因此多了一个逐平台记摘要的 `nodejs-wheel-binaries`（当前 24.19.0），Pyright 只使用它。两条实测证据：把 `PATH` 上的 node 全部去掉（只留 `System32`），`pyright --version` 照常返回；先在最前面放一个必然失败的假 `node`，Pyright 仍然正常通过——两次都说明它根本没看 `PATH`。

注意**没有**按另一条路去设 `PYRIGHT_PYTHON_GLOBAL_NODE=0`：装上 `nodejs` extra 之后那个变量不改变结果，而留一个不控制任何东西的设置正是本仓库一路在清理的那类问题（参见 W10 关于 `isPreserveFileTimestamps` 的结论）。

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
