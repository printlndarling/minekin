# 数据根目录与身份创建：提案（未批准）

状态：**提案**。2026-09-19 编写；2026-09-20 增加决定四（证据 bundle 的位置），它是 `evidence verify` 落地时被逼出来的：命令只拿到一个 run id，就必须有一个 run id 能算出来的地址。所有契约文档都没有规定 Minekin 的数据根位置，也没有规定"受信任配置"（`configured_username` 的来源）究竟是一个文件、一个环境变量还是一次命令行输入，因此 `minekin init` 一直没有落地。本文把一个最小实现方案写下来，好让它可以被审阅、被否决、被替换，而不是悄悄藏进代码里。

若本文与任何契约冲突，以契约为准，并修改本文。改动本文的成本应当很低：它只决定两件事，实现里对应的位置也很少。

## 决定一：数据根来自环境变量 `MINEKIN_HOME`

- 必需，**没有默认值**。未设置或为空即 `CONFIG` 失败，并在消息里指明变量名。
- 必须是绝对路径；相对路径在 `resolve()` 之前就被拒绝（否则它会悄悄相对当前目录）。
- 只解析、不创建。任何命令读取它都不产生副作用；只有 `init` 会在其下新建目录。
- 这样做不会在用户主目录里凭空造出任何东西：不设置就不运行。

没有采用默认路径（如 `~/.minekin`）的理由：那会在运行者没有表态的情况下于其主目录建目录，而且主目录语义与"绝不读取宿主 `.minecraft`"的既有红线相邻，容易让人误以为这两者是一回事。

没有采用 `--root` 命令行参数的理由：根是主机层面的事实，而需要它的命令不止一个（`init`、`session start`、`session status`、`evidence verify`），而冻结的 CLI schema 里这些命令都没有该参数。加一个只对 `init` 生效的参数解决不了后面几个。

**没有采用配置文件**的理由：契约说 username 属于"受信任配置"，但没有规定格式与位置。引入一个文件格式是本提案里最大的一笔发明，而它并不能带来额外保证——`init` 只运行一次，结果立刻持久化进身份根，之后所有读取都来自数据库，不再来自配置。

## 决定二：身份输入来自环境变量 `MINEKIN_USERNAME`

- `init` 必需，其他命令不读它。
- 必须满足原版 `[A-Za-z0-9_]{3,16}` 规则，否则 `CONFIG` 失败——服务端本来也会拒绝，早失败比晚失败好。
- 与 `--kin-id` 的分工：`kin_id` 是 Minekin 自己的不变标识，适合作为命令行参数；username 是 Kin 在世界里的名字，之后可能因改名产生新的 identity revision，把它固定在环境里而不是每次输入，可以减少"顺手改一下"造成的身份漂移。

选择环境变量而非 `init --username` 的理由：不改冻结的 CLI schema。这一条是本提案里最容易被替换的部分——若运营者更希望它出现在 `--help` 里，加一个参数即可，本文与实现同步改。

## 决定三：两个只在需要时才读的变量

- `MINEKIN_JAVA`（可选）：受管客户端用哪个 Java 可执行文件。不设置时在 `PATH` 上找 `java`；设置了就必须是存在的绝对路径。之所以允许显式指定，是因为"受控 runner 上装了多个 JDK"是很正常的情况，而 PATH 顺序不该决定 Kin 跑在哪个 JVM 上。
- `MINEKIN_KIN_ID`（可选）：当数据根下不止一个 Kin 时指名要启动哪一个。根下只有一个时不需要它，多于一个而不指定则拒绝——启动错的 Kin 是后续步骤挽不回来的。

## 决定四：每次运行的证据封存在 `run/evidence/<run-id>/`

- 一次 Core 进程生命周期就是**一个 run id**（uuid4 的 hex），它的 evidence bundle 封存在 `<kin>/run/evidence/<run-id>/`。**目录名就是 run id**，没有第二套编号：封存端只有一个地址函数（`cli/evidence.py` 的 `bundle_directory`），校验端也只有一处按这个名字去找。
- 校验端（`minekin evidence verify <run-id>`）拿到的只有 run id，所以在数据根下的**每一个** Kin 里找这个名字。找到 0 个是 `CONFIG` 失败，找到 2 个也是 `CONFIG` 失败而**不是挑一个**：run id 是 uuid4，撞名意味着其中一份不是它自称的那份，挑任何一个都会把一次运行的证据记到另一次头上。这也是不要求 `MINEKIN_KIN_ID` 的原因——bundle 是拿来交给别人的，查它的人通常不是跑它的人，身份根、账本与 artifact 缓存都不是回答「这份证据还立不立得住」所需要的东西。
- bundle 不放进 `session/`：`session/<session_id>/generation-N/` 是**客户端的工作目录**（游戏目录、日志、natives 都在里面），每次会话可写、会被就地改；证据是不可变的、每次*运行*一份、属于运行而不属于客户端。放进同一个 `run/` 只是沿用已有的做法——一次运行的东西都在一处。
- 校验**只读**：`verify` 不写一个字节，也不动封存位。`sealed`（权限位）与 `verified`（摘要）是两件事，一起报出来：摘要才是保证，权限位只是提醒。
- 目录名与 manifest 里的 `test_run_id` 必须一致，不一致即 `RUN_ID_MISMATCH`。目录名是 bundle 与 run 之间唯一的对应关系，把它搬到另一个 run id 下必须立刻被发现。
- run id 变成路径段之前要按**标识符**规则校验（`domain.ids` 那一条），不是去找 `..`：run id 本来就是 uuid，不是 uuid 的 run id 指不到任何一次运行，于是它连碰文件系统都不该碰。

## 目录布局

```
$MINEKIN_HOME/
  kin/
    <kin_id>/
      kin.sqlite3          身份根与事件账本（单 writer-thread）
      run/                 交给 ClientProcessSpec 的 run root
        artifact-store/    内容寻址缓存（按 sha1 分层）
        bundle/            只读包（assets 等）
        session/           本次会话的可写 overlay
          game/            客户端的 working directory
          natives/         解压后的 native 库
        evidence/          封存的证据，每次运行一份
          <run-id>/        manifest.json、bundle.sha256 与工件
```

- 计划里的相对路径（`artifact-store/…`、`bundle/…`、`session/…`）就是相对这个 `run/`，这一点已经在 `launch-plan` 的输出里冻结，本提案只是把它落到具体位置。
- `artifact-store/` 与 `bundle/` 按 Kin 共享：内容寻址且不可变，重复下载没有意义。P0 只有单 Kin，多 Kin 时是否跨 Kin 共享留给以后（涉及磁盘与信任边界）。
- `session/` 每次会话各自一份，与"为每次世界会话创建独立 managed run directory"一致。
- 同一 `kin_id` 目录下只允许一个 Core 实例（单实例锁），这一条沿用既有契约，本提案不新增。

## 明确不决定的事

- 备份、保留期、加密与云端同步：属于持久化契约，本提案不碰。
- 多 Kin 的根共享与配额。
- `session start` 的进程监管（PID identity、接管/终止判定）。数据根只是把它解锁，不替它做决定。
- Windows 与 Linux 的路径差异：只要求绝对路径，两边都成立。
- **证据封存的时机**：本提案只定 bundle 住在哪、怎么被找到，不定一次运行在什么时刻、由谁把哪些工件封进去（`session start` 自己封、还是 orchestrator 封，取决于运行时用例的断言谓词语义尚未定的那一半）。仓库自检类用例（`W00-CONTRACT-001` 这种根本没启动客户端的）不能套用为运行时设计的 manifest 形状，因此没有为它们伪造 launcher 摘要。

## 何时应当推翻本提案

1. 运行者希望数据根有默认位置（例如容器镜像里约定 `/data`）——改一个函数的默认值即可。
2. 运营团队要求身份输入来自被审计的配置文件而非环境变量——加 `adapters/` 里的一个加载器，`init` 的读取点只有一处。
3. 多 Kin 需要共享 artifact 缓存——布局要变，但 `run/` 三段的相对结构不变，因为它是计划契约的一部分，而不是本提案发明的。
