# H1g `V1201-JOINER-LOCAL-V2-PROFILE-001` — 1.20.1 加入者改走已审 v2 loopback 目标（runner 侧）

- **卡片**：`docs/v1201-local-join-next-2026-09-27.md` §2「### H1g」，逐字取其允许面 / 实现边界 / 验收 / 停止条款。
- **Lane / 分支**：`codex/minekin-joiner-local-v2-profile`（H lane）。
- **基线 SHA（本分支起点 = 当时的远端 `main`）**：`0da7032ab34403830fbd0a3dea71f5fe65032615`
  （`git merge-base HEAD origin/main` = 同一个 `0da7032`；未 rebase、未 merge、未推 `main`）。
- **被改字节身份**：
  - 改前（主干，与 V3 记录的 H1f 出厂字节同一份）：
    `test-orchestrator/runner/domain.sh` = `f8624ac6713301460288b439ac9644a0b4b1026e218e19f107c9678758ffe0c5`
  - 改后（本卡交付字节）：
    `test-orchestrator/runner/domain.sh` = `ff69c87994f15be37a07090c664c60fdbf8cd620689bfd07fe3a837431e982c4`
  - 本文里每一条活体读数都打印了它所驱动的 `domain.sh` 的 sha256（驱动器首行 `H1G: domain.sh sha256 = …`），
    所以任何一条读数都能被独立判断是「出厂字节」还是「新字节」上量到的。
- **本卡状态**：**DELIVERED**。成功上界按卡片规定＝加入者越过 `launcher.profile` 准入，
  并在 profile/loader 层证成；**不宣称 JOIN**，不封证，不写规范卷。

---

## 1. 允许面与实际改动

只写入了三个路径（`git status --short` 交付前）：

| 路径 | 改动 | 增删 |
|---|---|---|
| `test-orchestrator/runner/domain.sh` | 加入者 profile 写手内新增一条按本次 `launched_version` 分派的分支 | +37 / -0 |
| `tests/contract/test_runner_scripts.py` | 三条新契约测试（形状切换、六条具名拒止、四项反证） | +356 / -0 |
| `docs/validation/v1201-joiner-local-v2-profile-2026-09-27.md` | 本记录 | 新文件 |

未改：`src/**`（含 `server_profile.py`、`metadata.py`）、Bridge、case 判据、registry、`tools/**` 门禁脚本、
封存 schema `minekin.p0.evidence.v1`、`domain.sh:404-407` 的 auto+joiner 拒止、`domain.sh:738-741` 的
无名版本拒止。无新 case id，无门禁/必改项变更。没有动 runner 自带 fixture/脚本
（`tests/fixtures/**` 零改动；`tests/fixtures/launcher/managed-remote-target-example.json` 只被读来对照字段规则）。

### 1.1 新的分支条件（逐字）

改动落在 H1f 写手内部：v1 文档照旧先构造，写手在落盘前按本次启动的版本决定是否换成
已审 v2「受管目标」文档。**分支条件逐字为**（`domain.sh:774`，位于 heredoc 的 Python 内）：

```python
if version != "1.21.4":
```

其中 `version` 就是 H1f 已有的第三个 heredoc 参数（`launched_version`，本次 run 真实启动的版本），
`1.21.4` 是 v1 准入 `server_profile.MINECRAFT_VERSION` 钉住的那一个版本；契约测试
`test_the_joiner_profile_shape_is_chosen_by_the_version_this_run_launched` 断言
`JOINER_V2_DISPATCH == f'if version != "{MINECRAFT_VERSION}":\n'`，
即该字面量与产品常量同源，二者只能经一次具名编辑才可能分开。**没有把 v1 常量改成 1.20.1，
也没有为求绿绕开准入。**

分支体（同样逐字，`domain.sh:775-794`）：

```python
    profile = {
        "schema_version": 2,
        "profile_id": profile["profile_id"],
        "host": profile["host"],
        "port": profile["port"],
        "auth_mode": profile["auth_mode"],
        "version_policy": {
            "mode": "explicit_allowlist",
            "allowed_versions": [version],
        },
        "resource_pack_policy": profile["resource_pack_policy"],
        "target_authorization": {
            "granted_by": "controlled-runner",
            "basis": (
                "the loopback world this controlled runner started for this very run; "
                "no address outside loopback and no operator-supplied target is named here"
            ),
        },
    }
```

设计要点（边界对照）：

- `host` / `port` / `auth_mode` / `profile_id` / `resource_pack_policy` **取自上面那份 v1 文档而不是重写一遍**，
  所以「换形状」不可能顺带换端点；实测量到的仍是 `127.0.0.1:25570`、`offline`、`deny`。
- `allowed_versions` 只有 `[version]` 一项，即本次真实启动的版本；不从 server status 文本、
  聊天、环境取版本（版本仍是 H1f 那条来自 bundle 配方的 `launched_version`）。
- `target_authorization` 是受控 runner 的可归因固定来源：`granted_by="controlled-runner"`，
  basis 明写「本次由该 runner 自己起的 loopback 世界」，不点名任何操作者给的或远程的目标。
- 1.21.4 走原 v1 分支：heredoc 里那份文档的构造与落盘代码一字未动。

---

## 2. 复现命令（所有活体读数共用）

宿主 Git Bash，`cwd` = 本 worktree。容器为受控镜像 `minekin-runner:local`
（Docker server `29.5.3`），`/src` 全程 `:ro`；**没有挂载 `minekin-runner-data`**（本卡不写规范卷、
不建 attempt/bundle、不封存）；`/h1g` 是 `/tmp/h1g` 的只读挂载（驱动器本身，未入库），`/out`
是同目录下可写的暂存区，只放 profile 文档。

```bash
export MSYS_NO_PATHCONV=1
REPO="$(cygpath -m "$PWD")"; TMPD="$(cygpath -m /tmp/h1g)"
docker run --rm --entrypoint /bin/bash -w /src \
  -v "${REPO}:/src:ro" -v "${TMPD}:/h1g:ro" -v "${TMPD}/out:/out:rw" \
  -e PYTHONPATH=/src/src minekin-runner:local -lc 'python /h1g/drive_loader.py <version> 25570 <out>'
```

驱动器 `drive_loader.py` 做的事：从 `/src/test-orchestrator/runner/domain.sh` 里**逐字抽取** H1f 写手
（定位 `    python - "${lan_port}" /tmp/domain-join-profile.json` 到其后的 `PY` 终止行），把 heredoc 的
Python 体作为独立进程按 run 的方式驱动（参数 = `port`、`out`、`launched_version`），然后把它写出的文档
交给真实产品 loader `load_session_server_profile(path, minecraft_version=…)`，打印文档逐字、sha256、
以及 `MinekinError.diagnostic()` 的 `component/category/message`。驱动器每步先打印
`domain.sh sha256`，因此「出厂字节 / 新字节」在读数里不可能是含糊的。

抽取行号（本报告引用）：
- 新字节 `ff69c879…`：写手 `domain.sh:743..795`（53 行 heredoc 体，sha256 `d86dcc0d5271f0c3…`）；
  含无名版本拒止的整块 = `domain.sh:738..795`（59 行）。
- 出厂字节 `f8624ac6…`：写手 `domain.sh:743..758`（16 行，sha256 `854019ac67bd700d…`）。

对照用的出厂字节树：`git show HEAD:test-orchestrator/runner/domain.sh > /tmp/h1g/domain_base.sh`，
容器内以 `H1G_DOMAIN=/h1g/domain_base.sh` 驱动；宿主实测 `sha256sum` = `f8624ac67133…`（与主干一致）。

---

## 3. 验收读数（逐条：复现命令 + 实测输出）

### 读数① 用**改前字节**复现 1.20.1 的 v1 准入红（先红）

命令：`… -lc 'python /h1g/drive_loader.py 1.20.1; echo "rc=$?"'`，且 `/src` 挂载前先确认
`H1G_DOMAIN` 未设置时驱动读的是 worktree 里尚未修改的 `domain.sh`（该次运行打印
`domain.sh sha256 = f8624ac6…`）。输出（逐字）：

```text
H1G: domain.sh sha256 = f8624ac6713301460288b439ac9644a0b4b1026e218e19f107c9678758ffe0c5
H1G: extracted writer lines 743..758 of domain.sh (16 body lines, writer sha256 = 854019ac67bd700d84229eef2d42aeb3bb349c84d558eedef693c5c69323e7f9)
H1G: writer rc=0 stderr=(none)
--- emitted document (verbatim) ---
{
  "schema_version": 1,
  "profile_id": "p0-lan-host-fixture",
  "host": "127.0.0.1",
  "port": 25570,
  "auth_mode": "offline",
  "minecraft_version": "1.20.1",
  "visibility": "isolated_test_only",
  "resource_pack_policy": "deny"
}
--- end document ---
H1G: document sha256 = 24eddf0a93521beadda25c6907841292493a94fdbbb5b1233fb32c6e9c51fc06
H1G: REFUSED component=launcher.profile category=ADMISSION operation=load retryability=OPERATOR_ACTION
H1G: REFUSED message=server profile minecraft_version is outside the pinned bundle
rc=3
```

与 V3 记录里 d1 的 `domain-join-session.json` 那句逐字同一（`"server profile minecraft_version is outside
the pinned bundle"`，`component":"launcher.profile"`），文档 sha256 `24eddf0a…` 即 V3 S-b 抄录的那份文档。
**红已复现，且是在产品 loader 里复现，不是在 harness 里声称。**

镜像的那一句（版本撒谎的形状，出厂字节、`launch_version=1.20.1` 驱动 1.21.4 文档）也一并量到：

```text
H1G: document sha256 = 634abc28ac0c4652fd40f2e82867f632cf68b2354eccd7ba75c62c7f49148137
H1G: REFUSED message=the session launches Minecraft 1.20.1, the profile pins 1.21.4
```

两句互为镜像这一事实（V3 的 F4）在本卡得到第二次独立复现。

### 读数② 新字节下 1.20.1 通过 `load_session_server_profile(..., "1.20.1")`，并且真的越过 `launcher.profile`

**②a profile/loader 层**（命令同①，`/src` 已是新字节；`domain.sh sha256 = ff69c879…`）：

```text
H1G: domain.sh sha256 = ff69c87994f15be37a07090c664c60fdbf8cd620689bfd07fe3a837431e982c4
H1G: extracted writer lines 743..795 of domain.sh (53 body lines, writer sha256 = d86dcc0d5271f0c3c73ab0c7322984a689c69c067698cffd910ba490de30e138)
H1G: writer rc=0 stderr=(none)
--- emitted document (verbatim) ---
{
  "schema_version": 2,
  "profile_id": "p0-lan-host-fixture",
  "host": "127.0.0.1",
  "port": 25570,
  "auth_mode": "offline",
  "version_policy": {
    "mode": "explicit_allowlist",
    "allowed_versions": [
      "1.20.1"
    ]
  },
  "resource_pack_policy": "deny",
  "target_authorization": {
    "granted_by": "controlled-runner",
    "basis": "the loopback world this controlled runner started for this very run; no address outside loopback and no operator-supplied target is named here"
  }
}
--- end document ---
H1G: document sha256 = 038dcf1e7331884a91a7c795d3b1ef8960d80405b049d1c5fc270df9fbb1f771
H1G: LOADED ManagedTargetProfile schema=2 profile_id=p0-lan-host-fixture host=127.0.0.1 port=25570 auth=offline loopback=True revision=7f8843030f23...
H1G: version fields minecraft_version=(v2: carries none) allowed_versions=('1.20.1',)
H1G: profile_version=1.20.1 launch_version=1.20.1 -> launcher.profile admission PASSED
rc=0
```

**②b 用产品自己的版本来源**（`cli/session.py:1006` 那一行的真实输入 = 1.20.1 bundle 配方）：

命令：`… -lc 'python /h1g/drive_refusals.py'`（尾部段落）。逐字：

```text
=== the CLI's own version source (session.py:1006), real 1.20.1 bundle fixture
  launched_minecraft_version(bundle-candidate-1.20.1.json) = '1.20.1'
LOADED  [new v2 document via the CLI's version] -> ManagedTargetProfile 127.0.0.1:25570 versions=('1.20.1',) loopback=True
REFUSED [base v1 1.20.1 document via the CLI's version]
  component=launcher.profile category=ADMISSION operation=load retryability=OPERATOR_ACTION
  message=server profile minecraft_version is outside the pinned bundle
REFUSED [base v1 1.21.4 document via the CLI's version]
  component=launcher.profile category=ADMISSION operation=load retryability=OPERATOR_ACTION
  message=the session launches Minecraft 1.20.1, the profile pins 1.21.4
```

即：同一个真实调用、同一个真实 bundle 版本，旧文档被准入拒、新文档被准入取用。

**②c 真实 `session start` 命令行**（joining client 在 `domain.sh:1179-1182` 拿到的那一条；
本卡改动把它之下的行整体下推了 37 行，主干字节上是 `1142-1145`——同一段命令行，逐字未动），
在一个 `--rm` 容器里用一次性 `/tmp/h1g-home` 根目录驱动（不挂任何卷、不联网取件、不连任何服）：

命令：
```bash
docker run --rm --entrypoint /bin/bash -w /src \
  -v "${REPO}:/src:ro" -v "${TMPD}:/h1g:ro" -v "${TMPD}/out:/out:ro" \
  -e LD_LIBRARY_PATH=/opt/sqlite/lib minekin-runner:local -lc 'bash /h1g/drive_cli.sh'
```
（`drive_cli.sh`：`MINEKIN_HOME=/tmp/h1g-home MINEKIN_USERNAME=Kin2` → `init --kin-id h1g-joiner` →
`MINEKIN_KIN_ID=h1g-joiner timeout 150 python -m minekin_core session start
--profile /src/tests/fixtures/runtime-input/bundle-candidate-1.20.1.json --server-profile <文档>`。）逐字：

```text
----- session start --server-profile /tmp/base-1201.json
H1G cli: rc=17 (124 would mean the timeout fired)
H1G cli: first stderr diagnostic:
{"category": "ADMISSION", "component": "launcher.profile", "context": {}, "evidence_ref": null, "message": "server profile minecraft_version is outside the pinned bundle", "operation": "load", "retryability": "OPERATOR_ACTION"}
H1G cli: launcher.profile named on stderr: 1
----- session start --server-profile /tmp/new-1201.json
H1G cli: rc=11 (124 would mean the timeout fired)
H1G cli: first stderr diagnostic:
{"category": "SUPPLY_CHAIN", "component": "cli.session", "context": {}, "evidence_ref": null, "message": "3638 of 3638 artifacts are not in the store yet, starting with com.mojang:minecraft:1.20.1; fetch them before starting a session", "operation": "start", "retryability": "OPERATOR_ACTION"}
H1G cli: components named on stderr:
"component": "cli.session"
H1G cli: launcher.profile named on stderr: 0
```

**判读**：加入者命令行上第一个具名停点从 `launcher.profile`（rc 17）移到了物料供给（rc 11），
`launcher.profile` 在该轮 stderr 出现 0 次 —— 这就是本卡被要求证的「确实越过了准入」。
这一段先在 `636a3517…`（新字节，注释定稿前）量到，随后在**交付字节 `ff69c879…` 上原样复跑**，
两条 rc 与两句 diagnostic 逐字相同（`launcher.profile named: 1` → `0`）；复跑时该容器的
`drive_loader.py` 段因未带 `-e PYTHONPATH` 在 loader import 处 `ModuleNotFoundError`，
但它已先把两份文档写出，`drive_cli.sh` 自己导出 `PYTHONPATH=/src/src`，所以 CLI 那两条读数成立。
随后那一句是**一次性空 store 的具名拒绝**（产品自己的「别在起 session 时意外下载」守卫，
本轮没有取件、没有连接任何东西），它是本驱动器故意用最小题根造成的输入缺失，
**不是**出厂路径的形状：真正的受控 run 会把 host Kin 的 store 整枚 `cp -a` 给 joiner
（`domain.sh:720-727`），V3 的 d1/d2 也证明 JOIN 路上那堵墙叫
`could not give the joining Kin an artifact store` 而不是这一句。
停点按卡片要求在此具名：**新字节的第一个前沿落在 `cli.session` 供给/取件层，
不再是 `launcher.profile`；`metadata.py` 的默认 `1.21.4` 在本卡的任何一条读数里都没有开火。**

### 读数③ 控制组不漂移：1.21.4 路由的文档与主干**逐字节相同**

命令（同一容器内跑两遍驱动器，分别用 `git show HEAD:` 的字节与新字节）：

```bash
H1G_DOMAIN=/h1g/domain_base.sh python /h1g/drive_loader.py 1.21.4 25570 /out/base-1214.json
python /h1g/drive_loader.py 1.21.4 25570 /out/new-1214.json
cmp /out/base-1214.json /out/new-1214.json
```
实测（宿主侧对两份落盘文档做摘要，两边都从 `/out` 抄回）：

```text
634abc28ac0c4652fd40f2e82867f632cf68b2354eccd7ba75c62c7f49148137 */tmp/h1g/out/base-1214.json
634abc28ac0c4652fd40f2e82867f632cf68b2354eccd7ba75c62c7f49148137 */tmp/h1g/out/new-1214.json
cmp: byte-identical
```
容器侧两条读数各自也打印了同一个文档摘要并都加载为 v1：

```text
H1G: document sha256 = 634abc28ac0c4652fd40f2e82867f632cf68b2354eccd7ba75c62c7f49148137
H1G: LOADED ServerProfile schema=1 profile_id=p0-lan-host-fixture host=127.0.0.1 port=25570 auth=offline loopback=True revision=d58d14d83da6...
H1G: profile_version=1.21.4 launch_version=1.21.4 -> launcher.profile admission PASSED
```
而同一份新字节下 1.20.1 的文档摘要是 `038dcf1e…`，出厂字节的 1.20.1 是 `24eddf0a…`：
三条不同摘要分别对应「钉住路由不变」「非钉路由换形状」「旧行为」，读数不是恒绿。

**v1 的拒止仍然开火**（读数①已量，另在契约测试里钉住）：v1 文档诚实写 1.20.1 →
`server profile minecraft_version is outside the pinned bundle`；v1 文档写 1.21.4 而 run 启动 1.20.1 →
`the session launches Minecraft 1.20.1, the profile pins 1.21.4`。两条都还在。

### 读数④ 六条具名拒止，全部在客户端 JVM 之前

命令：`… -lc 'python /h1g/drive_refusals.py'`（新字节写出的 `/out/new-1201.json` 为母文档，逐字段替换）。逐字：

```text
=== emitted document under test: /out/new-1201.json
REFUSED [empty allowlist]
  component=launcher.profile category=ADMISSION operation=load retryability=OPERATOR_ACTION
  message=server profile version_policy allowed_versions must not be empty
REFUSED [version mismatch (launch 1.21.4)]
  component=launcher.profile category=ADMISSION operation=load retryability=OPERATOR_ACTION
  message=the session launches Minecraft 1.21.4, the target allows 1.20.1
REFUSED [multi-entry allowlist]
  component=launcher.profile category=ADMISSION operation=load retryability=OPERATOR_ACTION
  message=a managed session target must allow exactly one version, this one lists 1.20.1, 1.21.4
REFUSED [non-loopback host]
  component=launcher.profile category=ADMISSION operation=load retryability=OPERATOR_ACTION
  message=a managed session may only join a loopback target; remote joining needs its own authorization card
REFUSED [auth_mode online]
  component=launcher.profile category=ADMISSION operation=load retryability=OPERATOR_ACTION
  message=v2 profiles have no online-mode admission path
REFUSED [missing target_authorization]
  component=launcher.profile category=ADMISSION operation=load retryability=OPERATOR_ACTION
  message=server profile is missing fields: target_authorization
```

「空/无名版本」在 harness 侧的那一句也照旧开火（`domain.sh:738-741`，语义未改；命令
`… -lc 'bash /h1g/drive_gate.sh'`，把 `domain.sh:738..795` 整块按 run 的方式 source 进 bash）：

```text
H1G gate: domain.sh under test = /src/test-orchestrator/runner/domain.sh
ff69c87994f15be37a07090c664c60fdbf8cd620689bfd07fe3a837431e982c4  /src/test-orchestrator/runner/domain.sh
H1G gate: extracted domain.sh lines 738..795 (59 block lines)
----- launched_version=<empty>
domain: the joining client must carry the version this run launched, and this run launched none it could name; refusing to write a joiner profile at a guessed version
H1G gate: rc=2
H1G gate: /tmp/domain-join-profile.json WAS NOT WRITTEN
----- launched_version=1.20.1
H1G gate: rc=0
H1G gate: /tmp/domain-join-profile.json WAS WRITTEN, sha256 = 038dcf1e7331884a91a7c795d3b1ef8960d80405b049d1c5fc270df9fbb1f771
  "schema_version": 2,
----- launched_version=1.21.4
H1G gate: rc=0
H1G gate: /tmp/domain-join-profile.json WAS WRITTEN, sha256 = 634abc28ac0c4652fd40f2e82867f632cf68b2354eccd7ba75c62c7f49148137
  "schema_version": 1,
  "minecraft_version": "1.21.4",
```

非 loopback 那一条用的是 TEST-NET-1 文档地址 `198.51.100.20`（与仓内 v2 示例 fixture 同一族），
**只是一个被拒的字符串**：本轮没有、也不会对任何远程/公网地址发起连接，唯一的本地目标由受控
runner 自己起。`load_managed_target_profile` 还会把该端点再过一次 `decide_endpoint(...)`，
未知字段同样被拒（契约测试里额外钉了「v2 文档带 `minecraft_version` 属 unreviewed fields」）。

### 读数⑤ 正对照（证明分派不是恒绿）

- **版本对照**：同一个新字节写手，`1.21.4` 入 → 冻结 v1 文档出（`634abc28…`，被 v1 分支加载），
  `1.20.1` 入 → v2 文档出（`038dcf1e…`，被 v2 分支加载）。两条路的形状由**版本这一个输入**决定，
  控制组与实验组各落在自己该落的分支上；见读数②与读数③的两段输出。
- **无名版本对照**：`launched_version=<empty>` → rc=2、`WAS NOT WRITTEN`（读数④）。
  写手既不猜版本，也不在没版本时给出一份「看起来绿」的文档。
- **供给链是活的**：读数②c 里 `session start` 在越过准入后立刻被
  `3638 of 3638 artifacts are not in the store yet` 挡住（一次性空 store），
  说明这条线不是一句「准入过了」就自证全局绿。
- 四个不同 rc（`2`／`3`(驱动器的拒用标记)／`11`／`17`／`0`）互不相同，形状与拒止不是糊在一起的常量。

### 读数⑥ 非空转反证（已实测，未入提交）

**做法（一行临时编辑，随后复原；本卡交付的 `domain.sh` 里没有留下它）**：把 `domain.sh:774` 的分支条件
逐字从

```python
if version != "1.21.4":
```

改成

```python
if version != "1.20.1":
```

（即把新版本分派退回「1.20.1 仍旧写 v1 文档」的旧形状，其余一切不动。）

**观察到的红（宿主 `uv run --frozen pytest tests/contract/test_runner_scripts.py -q`）**：

```text
E       assert 0 == 1
E        +  where 0 = <built-in method count of str object at 0x00000267626D00A0>('if version != "1.21.4":\n')
...
FAILED tests/contract/test_runner_scripts.py::test_the_joiner_profile_shape_is_chosen_by_the_version_this_run_launched
FAILED tests/contract/test_runner_scripts.py::test_the_joiner_version_dispatch_is_not_an_always_true_claim
2 failed, 35 passed in 0.28s
```

**同一反向形状的行为红（容器内驱动器，改后即刻量得）**：

```text
  "resource_pack_policy": "deny"
H1G: document sha256 = 24eddf0a93521beadda25c6907841292493a94fdbbb5b1233fb32c6e9c51fc06
H1G: REFUSED component=launcher.profile category=ADMISSION operation=load retryability=OPERATOR_ACTION
H1G: REFUSED message=server profile minecraft_version is outside the pinned bundle
---
H1G: document sha256 = 7f92e7fdc39cb2f48503b5262940d59248ebe74c72ffb4493b709c88f496c0fd
H1G: LOADED ManagedTargetProfile schema=2 ... allowed_versions=('1.21.4',)
H1G: profile_version=1.21.4 launch_version=1.21.4 -> launcher.profile admission PASSED
```

即反向后：1.20.1 退回被拒的 v1 文档（`24eddf0a…`，读数①那一份），
而 1.21.4 控制组漂走成一份 v2 文档（`7f92e7fd…`）——两条读数同时坏，
证明它们各自确实由这一行分派决定。随后一行改回，目标测试重新 37 passed，
`/out/new-1201.json`、`/out/new-1214.json` 摘要回到 `038dcf1e…` / `634abc28…`。

**另外四项写在契约测试里的常驻反证**（`test_the_joiner_version_dispatch_is_not_an_always_true_claim`，
在宿主上跑，不改仓内字节）：
- RV-0 分派永不成立（`if False:`）→ 1.20.1 又写 v1，并被 `outside the pinned bundle` 拒；
- RV-1 分派取反（`if version == "1.21.4":`）→ 控制组的冻结字节消失（`schema_version` 变成 2）；
- RV-2 `allowed_versions` 加第二项 → loader 具名拒「must allow exactly one version」；
- RV-3 `host` 换成非 loopback 字面量 → loader 具名拒「only join a loopback target」。
四项都让被反证的那半句转红，且互不遮蔽（RV-0/RV-1 打的是形状，RV-2/RV-3 打的是准入是否真读字段）。

---

## 4. 门禁表（宿主 Git Bash，`cwd` = 本 worktree；ruff/pytest 一律经 `uv`）

| 门禁 | 命令 | 实测输出 | rc |
|---|---|---|---|
| shell 语法（宿主） | `bash -n test-orchestrator/runner/domain.sh` | 无输出（宿主 bash `5.2.37(1)-release`） | **0** |
| shell 语法（受控镜像） | `docker run … minekin-runner:local -lc 'bash --version \| head -1; bash -n /src/test-orchestrator/runner/domain.sh'` | `GNU bash, version 5.2.21(1)-release (x86_64-pc-linux-gnu)`；`container bash -n rc=0` | **0** |
| 定向契约 | `uv run --frozen pytest tests/contract/test_runner_scripts.py -q` | `37 passed in 3.79s`（交付字节上复跑；含 H1f 原有两条一字未改地通过） | **0** |
| ruff 格式 | `uv run ruff format --check .` | `357 files already formatted`（本记录入库后为 357，先前无本记录时 `356 files already formatted`） | **0** |
| ruff lint | `uv run ruff check .` | `All checks passed!` | **0** |
| 边界检查 | `uv run python tools/check_boundaries.py` | `Minekin package dependency boundaries: OK` | **0** |
| fixture 摘要 | `uv run python tools/verify_fixture_digests.py` | `W00 schema and fixture digests: OK` | **0** |
| 判据登记 | `uv run python tools/check_case_assertions.py` | `Case assertion implementations: OK (150 registered)` | **0** |
| diff 卫生 | `git diff --check` | 无输出 | **0** |
| 全量本地套件 | `uv run --frozen pytest -q` | `2604 passed, 3 skipped in 315.02s (0:05:15)`；见下方逐字 SKIPPED 三条 | **0** |
| pyright（改动文件） | `uv run pyright tests/contract/test_runner_scripts.py` | `0 errors, 0 warnings, 0 informations` | **0** |
| pyright（全仓） | `uv run pyright` | `43 errors, 0 warnings, 0 informations` —— **红**；43 条全部落在 `tests/unit/test_case_evidence_assertions.py`，本卡两个路径 0 条（见下） | **1** |

时态说明（提交本卡时补记，勿把上表 43 条当作当前状态）：这条全仓 pyright 读数是**在本卡基线
`0da7032` 上量的**，当时确实为红，保留以如实反映本卡验证现场；该红属 M 自有测试文件
`tests/unit/test_case_evidence_assertions.py`，与本卡的两个交付路径无关。主干此后已由
`518d199`（`test(evidence): name the asserter members the OFFLINE rows read`，补齐 `_Asserter`
协议）单独修掉，主控侧在该提交上实测全仓 `uv run pyright` 读 `0 errors, 0 warnings,
0 informations` —— 本卡未在本 worktree 复量这个转绿读数，仅具名引用主控结果。本卡只自行核了两件事：
`518d199` 确在 `main`/`origin/main` 上、不是本卡基线 `0da7032` 的祖先（`git merge-base --is-ancestor`
读「否」），且它只改 `tests/unit/test_case_evidence_assertions.py` 一个文件（`git show --stat` = +14/-1），
补的正是上面那 7 个 `_Asserter` 名字。

全仓 pyright 的红不是本卡造成的，且这是量出来的而不是推的：
`git status --short tests/unit/test_case_evidence_assertions.py` 与
`git diff --stat HEAD -- tests/unit/test_case_evidence_assertions.py` 双双为空（该文件与本卡
起点字节一致，本卡没有触碰），`grep test_runner_scripts tests/unit/test_case_evidence_assertions.py`
无命中（它不导入本卡改的那个测试模块）。单指定该文件跑 pyright 也是同样 43 条：

```text
$ uv run pyright tests/unit/test_case_evidence_assertions.py
43 errors, 0 warnings, 0 informations
```

命中的是一族 `_Asserter` 上的未知属性（`Attribute "IDENTITY_ROOT_MERGE_HAS_NO_SEALED_CARRIER" is unknown`、
`Attribute "AUTHENTICATION_FIELD_NAMES" is unknown` 等 7 个去重后的名字），属判据/registry 侧的类型面，
不在本卡允许面内 —— **按停止条款只具名报告，不顺手修**。本卡自己动的那一个 Python 文件是 0 错：

```text
$ uv run pyright tests/contract/test_runner_scripts.py
0 errors, 0 warnings, 0 informations
```

全量逐字尾部（原始失败与复跑并列的要求在这里没有触发——**全量没有失败**，因此没有红可并列；
把已知抖点单独复跑一次仍然记全，两个读数并记）：

```text
=========================== short test summary info ===========================
SKIPPED [1] tests\unit\test_orphans.py:686: this platform cannot answer the question, so it can never say gone
SKIPPED [1] tests\unit\test_silent_listener.py:123: a Windows terminate is not a signal
SKIPPED [1] tests\unit\test_tested_provenance.py:354: bridge-1201/build/libs/minekin-bridge-1201-0.0.0.jar is not built on this host, and the reviewed Bridge bytes are one of the things this check measures
2604 passed, 3 skipped in 315.02s (0:05:15)
full suite rc=0
```

已知资源型抖点（V3 S-g 点名的那一个）在全量里通过，单跑也通过，两值并记：

```text
$ uv run --frozen pytest "tests/unit/test_session_supervision.py::test_a_deadline_does_not_cancel_a_world_the_kin_is_already_in" -q
.                                                                        [100%]
1 passed in 1.90s
```

三条 SKIPPED 都是平台性的，其中第 3 条与 V3 S-e/S-g 的口径一致：本 worktree 里
`bridge-1201/build/libs/` 不存在（本卡没有建树，也没有把任何 jar 放进仓内），所以它是跳过而非失败。
并发口径也说清楚：全量启动前所有容器读数都已退出，全量结束之后才又串行跑了交付字节上的复跑读数
（读数②c 的复跑、pyright 复量），**全量跑期间没有任何容器在跑**，没有并发 JVM 可当抖动借口。

说明：
- `bash -n` 在容器（bash 5.2）里重跑一次，因为 `domain.sh` 只在容器里被执行；宿主 bash 5.2.37 的结果一并记。
- 定向契约的 37 条 = 原 29 条 + 本卡新增 8 条（1 条形状切换、6 条具名拒止的参数化、1 条反证）。
  H1f 的两条（`test_the_joiner_profile_version_comes_from_the_run`、
  `test_the_joiner_version_contract_is_not_an_always_true_claim`）一字未改，仍通过 ——
  1.21.4 的 profile 测试没有漂移。
- 本卡测试里对「字节相同」的比较做的是**内容归一后逐字节**（`as_document_text` 把宿主文本模式写出的
  CRLF 还原为 LF），并在 docstring 里写明理由：写手以默认文本模式打开输出，行分隔符属于宿主平台；
  真正的逐字节等值是在受控 Linux 镜像里量的（`base-1214.json` 与 `new-1214.json` 的 `cmp` + 同一个
  sha256 `634abc28…`）。这是一条平台性事实，不是一条被抹平的差异。

---

## 5. 停点（卡片的停止条款）

第一个真实前沿**没有**留在 profile 准入之外时被我顺手改任何东西：读数②c 量到的新第一停点是
`cli.session` 的供给/取件具名拒绝（一次性空 store 的形状产物），不是 `metadata.py` 的默认 `1.21.4`，
也不是 `launcher.recipe`/Bridge/预算。本卡在此停住：不改 `src/minekin_core/adapters/launcher/metadata.py`，
不改游戏客户端，不接任何远程服，不宣称 JOIN。V4 若要量「1.20.1 客户端真起 JVM」，
需要在**已备好物料的 store** 上驱动受控 run（V 私有卷即可），本卡没有做那一轮，
也不声称 `GLFW 0x1000E` / `XDG_RUNTIME_DIR` 家族在 1.20.1 上已被排除 —— 那仍是 bounded 的。

---

## 6. 四态

- **已合主干**：**无**。本卡没有任何东西由 H 合入 `main`；M 未合入前，改动只存在于分支。
  前置的 H1f（`02a8b4b` 经 `2ef64a8`）、V3 记录在基线 `0da7032` 里，是本卡的输入而不是本卡的产出。
- **仅在分支**（等 M 按真实 merge-base `0da7032` 审后合入）：
  `test-orchestrator/runner/domain.sh` 的 +37（新字节 `ff69c879…`）、
  `tests/contract/test_runner_scripts.py` 的 +356、本记录。
- **真实封证**：**零**。本卡不封存任何东西，不建 attempt/bundle，不写规范卷
  （`minekin-runner-data` 全程未挂载，连 `:ro` 都不需要）。本节「量到」＝在容器/宿主上按上面命令
  复跑可重现，不等于 sealed evidence。
- **未验证**：
  1. 1.20.1 joining 客户端**真起 JVM**、Bridge 握手、`JOIN SUCCEEDED`/首快照 —— 本卡未测（卡片上界之外）。
  2. `GLFW 0x1000E` 与 `XDG_RUNTIME_DIR` 家族在**已启动的** 1.20.1 客户端上是否复现 —— 未测。
  3. 真实受控 run（`domain.sh` 全流程 + 已备料 store + LAN 开放）里 joiner 走 v2 文档的活体一路 —— 未测；
     本卡的 `session start` 驱动是一次性小题根，越过准入后被空 store 挡住（读数②c 已按原样具名，
     **主控侧未复量**该轮在备料卷上的表现）。
  4. `::1`（IPv6 loopback）形状下的加入者文档 —— 未测（本 runner 的 `lan_port` 路径固定写 `127.0.0.1`，
     卡片也只要求 loopback；loader 侧 `::1` 的支持没有在本次任何一条读数里被驱动）。
  5. `--auto-bundle` × joiner 组合 —— 未测且**按原样保持被拒**（`domain.sh:404-407` 一字未改）。
  6. `pinned_bundle_id` 可选字段在 joiner 文档里的用法 —— 未测（本卡不写该字段，以免声称一份
     runner 并没有逐项核过的 bundle 绑定）。
  7. 多 joiner / 并发、任何在线认证、任何非 loopback 或公网服务器 —— 一律未测，按边界声明不去、不用。
  8. pyright：本卡改动面 `0 errors`（已跑，rc 0）；全仓 `43 errors`（已跑，rc 1，全部在未触碰的
     `tests/unit/test_case_evidence_assertions.py`）。**HEAD 口径的全仓 pyright 条数本卡未复量**
     （主控侧未复量），本卡只证明了这 43 条不来自本卡的两个路径。
  9. 卡片验收里「若全量因资源型 flaky 失败则原始失败与复跑并列」这一支**没有触发**：全量一次通过
     （`2604 passed, 3 skipped`，rc 0），没有原始失败可并列；已知抖点单独复跑通过。

## 7. 交付与回读

- 提交：一次，仅上述三个路径。
- 推送：`git push -u origin codex/minekin-joiner-local-v2-profile`，
  并以 `git ls-remote origin refs/heads/codex/minekin-joiner-local-v2-profile` 核远端 SHA。
- M 审查起点（真实 merge-base）：`0da7032ab34403830fbd0a3dea71f5fe65032615`。
- 复现本卡全部活体读数所需的驱动器脚本在 `/tmp/h1g/`（`drive_loader.py`、`drive_refusals.py`、
  `drive_gate.sh`、`drive_cli.sh`），**未入库**（本卡允许面不含它们）；本文已逐字给出其定义与调用形。
