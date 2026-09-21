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
uv run python tools/check_case_assertions.py
uv run python tools/verify_fixture_digests.py
uv run python tools/check_workflow_pins.py
```

`.github/workflows/` 里的每个 action 都钉在**它那个 release 指向的 commit** 上，release 号写在旁边当注释（`uses: actions/checkout@fbc6f399… # v5`）。tag 是它的所有者能移动的名字，而这个仓库对其它一切取来的东西都做摘要核验（Gradle wrapper、服务端 jar、Bridge jar、buf CLI、夹具、用例判据），action 是同一类东西——外部代码，带着本仓库的凭据运行。`check_workflow_pins.py` 拒绝没钉的，也拒绝**钉了却不说出自哪个 release 的**：一个没人能追溯回 release 的裸 SHA 是没人能复核的钉。换 pin 与换其它 pin 一样是一次评审动作——读 release 的 diff、解析 tag、一次提交里同时改 SHA 和注释。

## 复核一份封存好的证据

`minekin evidence verify <run-id>` 回答的是「字节还是那些字节」。它**不**回答「这些字节是否真的支持写在它们上面的那个判决」——判据（断言）属于测试域，产品代码不该 import `tools/`，所以那件事由测试域里的一个工具来做，对着同一个 bundle：

```text
uv run --no-project python tools/rejudge_evidence.py <bundle 目录>
```

它要求三件事各查各的：bundle 自己站得住、它点名的用例仍是**封存时那一版**、以及从封存字节重判出来的判决（result / expected / observed / failures 逐项）与记录一致。退出码 0 一致、1 不一致、2 判不了（字节站不住、用例版本搬了家、或 bundle 里没有判官当时的输入）。一份被改写过的 manifest——清空 `failures`、把 `observed` 填成 `expected`、`result` 改成 `PASS`，再重新生成 `bundle.sha256`——**能**通过 `evidence verify`，这一条能拒它。

把一份事件流重新过一遍会话状态机、再与它自称应当产生的投影比对：

```text
uv run --no-project python tools/replay_evidence.py --fixture tests/fixtures/replay/session-preparing.v1.json
uv run --no-project python tools/replay_evidence.py <bundle 目录>
```

`--fixture` 是完整的检查：事件逐个核对 `payload_hash`、状态按 `domain/session_state.py` 那张冻结的迁移表折叠、结果与 fixture 自己的 `expected_projection` 相比。**bundle 那条路今天会拒绝**，而且拒绝本身就是结论：Core 的账本记的是「发生了什么」（`PlayableEstablished`、`JoinObserved`……），**不记**「会话走到了哪个状态」，所以一次真实运行的时间线里没有可折叠的东西。从事件名反推状态会是**对记录者的猜测伪装成检查**，而且 run document 已经记下了状态机真正到达的状态。等账本开始记迁移，这条路自己就会开始工作。

Bridge 协议与适配器可在无 Gradle、无 Minecraft 的情况下验证。第一条只编译协议内核；第二条从 Maven Central 按 SHA-1 校验下载固定 protoc 与 javalite，再编译 W20 适配器并跑自测。两条都只要求本机 JDK：

```text
uv run --no-project python tools/check_bridge_scaffold.py
uv run --no-project python tools/check_bridge_host_boundary.py
uv run --no-project python tools/check_bridge_protocol.py
uv run --no-project python tools/check_bridge_proto_java.py
```

`check_bridge_host_boundary.py` 与 `check_bridge_artifacts.py` 是**同一条边的两道门禁**，词汇表在 `tools/bridge_host_rules.py` 里只声明一次：前者读源码（谁被允许写这些名字），后者读构建产物（编出来的 class 常量池、mixin JSON、access widener、entrypoint 与打包依赖里有没有这些引用）。产物门禁**需要产物**，因此它跟着构建走——已接进 Gradle 的 `check`（`./gradlew check` 会因违规而失败，这正是契约要的「构建必须失败」），要单独跑一次：

```text
uv run --no-project python tools/check_bridge_artifacts.py --artifact bridge/build/libs/minekin-bridge-0.0.0.jar
```

两种产物都认：Gradle remap 过的 jar（intermediary 名字）与 `check_bridge_proto_java.py` 桩编译出的 classes 目录（Yarn 名字）。名字表 `bridge/host-boundary-names.json` 由固定 Yarn 构建推导而来，所以两种拼写都能认；Yarn 版本升级时必须重推：

```text
uv run --no-project python tools/check_bridge_artifacts.py --derive-names \
  --mappings <loom cache>/1.21.4/net.fabricmc.yarn.<version>-v2/mappings.tiny
```

Bridge 必须用 Java 21。仓库中的 wrapper 配置不会在检出时下载 Minecraft 或 Gradle 工件；首次执行下列命令才会解析候选依赖：

```text
cd bridge
./gradlew --version
./gradlew check
```

`./gradlew check` **需要 PATH 上有 Python 解释器**：`checkHostBoundaryArtifacts` 把产物门禁接进了 `check`，而那道门禁是一个 Python 脚本。它按 `python3` 再 `python` 的顺序找（裸 Ubuntu 只有前者、Windows 通常只有后者），也认 `-PgatePython=<命令>` 这个属性。找不到时它会**先打一行 warning 说明原因和补救办法，再失败**——不是静默跳过：一道跳过的门禁与没有门禁是同一件事，而这个契约要的正是「构建必须失败」。**这也是为什么容器里那条构建命令要装 `python3`、并且要把 `tools/` 一起拷进去**（门禁与被守卫的模块分居两处，见开发 TODO 里那条实测）。

当前锁定工作流分两步：版本目录固定直接依赖，Gradle dependency locking 固定解析图。Java 21 环境第一次解析依赖后须生成并评审 lockfile 与 verification metadata，禁止把未评审的自动更新与功能变更混在同一提交：

```text
./gradlew dependencies --write-locks
./gradlew help --write-verification-metadata sha256
```

`verification-metadata.xml` 要**同时**记下每个平台会解析到的那一套摘要，而不是「生成它的那台机器」的那一套。按平台分类的依赖今天有九个：`jtracy-1.0.29-natives-*.jar` 与八个 `lwjgl-3.3.3-natives-*.jar`，Windows 与 Linux 两套都在里面（八个 lwjgl 的摘要对着 Maven Central 公布的 SHA-1 核过，jtracy 对着 Mojang 的 1.21.4 version manifest 核过）。补录的方法是在容器里按上面第二条生成、把文件取出来比对：Gradle 是**合并**而不是重写，所以 diff 应当只有新增行——第一次补 Linux 那九条时是 +27 行、−0 行。macOS 仍缺条目：没有人在那个平台上构建过，不凭猜测补。

这道门禁有一条**已知的、与代码无关的红**：Loom 给 remap 出来的依赖 jar 的每个 zip 条目盖上那次 remap 的时间戳，而元数据记的正是当时那一批字节，所以**干净检出上 `./gradlew check` 会在 `:compileJava` 失败**（报五十个 `net_fabricmc_yarn_*` 未核验），本机与容器都一样——它只可能对着生成元数据时那个 `bridge/.gradle` 缓存通过。严格模式在编译类路径就中止，所以运行时 natives 那一类问题反而看不见；想一次看全就用 `--dependency-verification=lenient`（只报不拦，构建照旧完成）。怎么处理是开发 TODO 里那条未决项。

普通 CI 不下载 Minecraft 资产或启动图形客户端；真实 Fabric/Minecraft 矩阵只在受控 runner 执行并产出 evidence。

## 包边界

- `domain` 只包含纯值和规则，不导入 application、adapter 或基础设施模块。
- `application` 只依赖 domain 与 ports；SQLite、socket 和 subprocess 必须经 port。
- `adapters` 实现 ports，不决定 session 状态或生成高层结论。
- `entrypoints`/`cli` 只负责参数解析、装配、信号与退出码映射。
- `generated` 只放协议生成物，不手写领域默认值。
- `test-orchestrator` 与 oracle 属于测试域，不能被打进 `minekin-core` wheel 或 Bridge JAR。
