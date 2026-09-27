# H1k `V1201-LAN-JOINER-ON-CONTROLLED-SERVER-001` — 第二客户端进受控专服世界的默认关闭路径（runner 侧）

- **卡片**：`docs/v1201-lan-control-next-2026-09-27.md` §2.13「### H1k」，逐字取其允许面 / 形状要求 / 硬边界 /
  四条验收 + 两则反证 / 门载荷上界 / 交回前必跑清单；H1k 之后的判据按 §2.16 预登记口径执行，未改一条。
- **Lane / 分支**：`codex/minekin-v1201-joiner-on-controlled-server`（H lane），基线 `29c5187`（= 派工时 `origin/main`，
  未 rebase、未 merge、不推 `main`）。
- **被改字节身份**：
  - `test-orchestrator/runner/domain.sh`：base（`29c5187`）= `baad190aaa5ee1695a88b52e98cc270c8e1a4bc878a0bcd2d0c27f94b74ff6f3`（2882 行）；
    本卡交付字节 = `d9a0acfc07719f0eab35305ba21e5a0821a88e100c86b016a80226e695f51a5c`（3043 行）。
  - `tests/contract/test_runner_scripts.py`：本卡交付字节 = `7fe48b9d6f92db6f966dfc8d854eb5a5f0403dd0d4fc3bec39e883387ca6419d`（+718）。
  - 新记录一份（本文件）。`run.sh`、`src/**`（含 `config.FORWARDED_VARIABLES`）、`tools/**`、fixtures、registry、
    schema 全程 **0 行**（`git status`/`git diff --stat` 见 §7）。
- **恢复现场说明（继承上一会话）**：本卡实现与全部测量脚本由上一会话写在工作树（未提交即死在子代理轮次上限）。
  本会话先按控制器登记的两个 sha256 复确盘上字节（逐字一致），再在**当前字节**上重跑全部读数，未重写、未回滚任何实现。
- **本卡状态**：**PARTIAL — DELIVERED（分支交付）**。①②④ 与两则反证全部有字面输出与可复算产物；
  ③（活体专服 run 的按加入者名回答行 ≥2 且首末不同）**未验证**，第一真实失败层具名在 §5。
  不封证、不写规范卷、不注册 case、不动 registry/mandatory。
  **主干 §2.17（`d45e23e`，晚于本卡派工）登记的三项退回补齐项未在本字节内**，见 §9——本会话按派工单
  「复确盘上字节、不重写实现」执行，未动任何已封读数的字节。
- **↑ 以上是上一轮（`d9a0acfc…`/`7fe48b9d…` 字节、引擎挂死时点）的现场，原文保留。** §2.22 裁决的四项（第七条组合拒止、
  新字节整体重跑、lane 私有卷活体 ③、门载荷前后对）在 **§10** 里补齐，本轮字节身份与四态也只在 §10 申报。

---

## 1. 这条路径是什么（形状要求逐条兑现）

新名 **`MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER`**（lane 自取并按卡面在此申报）：

- **读一次、铸在其它加入者名旁边**：`domain.sh:167`（`join_on_controlled_server="${MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER:-}"`），
  紧跟 H1h 四名的读数区；`""|0|false` ＝ 未请求，`1|true` ＝ 请求，其它值 → 具名拒止 `exit 2`。默认关闭。
- **拒止区**（`domain.sh:461-488`，`joiner-controlled-server-guard`）：无加入者／无 `--server-profile`／
  `MINEKIN_DOMAIN_OPEN_LAN` 同设（两个世界名争同一个加入者）／black-hole／no-server／not-whitelisted，六格各自具名拒止，
  全部在任何 JVM、任何 run 目录存在之前。auto+joiner 既有拒止条款仍最先回答（契约测试钉住先后）。
- **白名单加法**（`:858-874`，`joiner-controlled-server-allowlist`）：仅当被请求时 `allow_args+=(--allow-player "${join_username}")`
  ——加的是**本 run 自己就要启动的那个名字**（arrival grep、ledger baseline、seal 的 `subject_username` 读的都是它），
  `--allow-player` 语义不变，名单不宽一字节；未设名的 run 拿到的是这卡之前每一份 run 都交给服务端的那份名单（§3 有驱动对照）。
- **目标端口只读自本 run 自己的** `${server_directory}/server.properties`（`:1067-1114`，`joiner-controlled-server-target`）：
  `sed -n 's/^server-ip=//p'` 与 `s/^server-port=//p`，端口非数字/文件不可读 → 具名拒止且不留目标；
  `server-ip` 不是字面 `127.0.0.1` → 具名拒止（不拨任何这台容器没启动过的地址）。LAN 形状的 `${lan_port}` 路径原样保留。
- **等待分支**（`:1969-1988`，`joiner-controlled-server-wait`）：新 `elif` 插在 LAN 分支与无世界分支之间，
  到达判据读的是**本 run 自己的** `${server_directory}/server.log` —— 与 `data get entity` 回答行同一份文件。
- **run.sh 转发缺口（交 M 另立窄卡，本卡未越界）**：`run.sh` 不在允许面内，新名今天**只被 harness 读、不被 wrapper 转发**。
  这一格按 H1h 的方式钉成反向断言（`test_runner_scripts.py:153-156`：`JOINER_CONTROLLED_SERVER_KNOB not in delivered`，
  并注明「转发的卡落地时该断言变红 ⇒ 删掉登记缺口」），所以缺口不会静默超期。§5 的活体驱动因此逐字复刻 `run.sh domain`
  的 docker 形状、只多补这一条 `-e`，这一点如实申报。

## 2. 硬边界（逐条字节证据）

- **绝不连远程服／不硬编码地址端口**：目标只从本 run 的 `server.properties` 读出，非 `127.0.0.1` 字面即拒止（§4 读数②两例驱动输出）。
  全程未打开 `.tmp/local-test-server.txt`，无任何非 loopback 拨号。
- **H1h 驱动区与 auto+joiner 条款零移动**。整文件摘要从 `baad190a…` 变成本卡的 `d9a0acfc…`（卡面预告「yours will change」），
  改动普查（`.tmp/h1k-reading1.py` [A] 段，容器内跑在当前字节上，全文 `.tmp/h1k-reading1-full.log`）逐字：

```text
  added lines: 163   removed lines: 2
  removed: '    if [ -z "${open_lan}" ]; then\n'
  removed: '    python - "${lan_port}" /tmp/domain-join-profile.json "${launched_version}" <<\'PY\'\n'
  H1h driver region: base 146 lines sha256 8b5401528aeb04229d5f322e69faa108c6671ef7e399db9a16d0c047831f8463
                    tip  146 lines sha256 8b5401528aeb04229d5f322e69faa108c6671ef7e399db9a16d0c047831f8463
  H1h bounded-control driver region, markers included
    base sha256 8b5401528aeb04229d5f322e69faa108c6671ef7e399db9a16d0c047831f8463
    tip  sha256 8b5401528aeb04229d5f322e69faa108c6671ef7e399db9a16d0c047831f8463
    BYTE-IDENTICAL
  removed line inside H1h's region? False: 'if [ -z "${open_lan}" ]; then'
  removed line inside H1h's region? False: 'python - "${lan_port}" /tmp/domain-join-profile.json "${laun'
  H1h driver + wiring span: base 177 lines sha256 843a671530ce19879fa7184ed2d7452dfb87f5e759757d3ed2bd9057b01ebbbf
                          tip  177 lines sha256 843a671530ce19879fa7184ed2d7452dfb87f5e759757d3ed2bd9057b01ebbbf
  H1h driver + wiring span identical: True
  auto+joiner refusal clause
    base sha256 4e9c0d858b13cfe5036cd39cab8bf64673818ae24dfdf1d384f31ac29bfb7fca
    tip  sha256 4e9c0d858b13cfe5036cd39cab8bf64673818ae24dfdf1d384f31ac29bfb7fca
    BYTE-IDENTICAL
  auto+joiner clause equals the clause the card names verbatim: True
```

  被删的两行（加入者世界前置、profile 写入器交接行）都在 H1h 区之外且各自都有驱动对照（§3）；H1h 的 146 行驱动区
  （`joiner-control-driver begin … end`）与 177 行 driver+wiring 跨度**一个字节都没动**。

---

## 3. 四条验收读数（字面输出，全部重跑在当前盘上字节）

测量脚本 `.tmp/h1k-reading1.py` / `.tmp/h1k-reading2.py`（容器内跑，base/tip 各一份字节），
全文分别存 `.tmp/h1k-reading1-full.log`（672 行）、`.tmp/h1k-reading2-full.log`（163 行）。

### 读数① —— 默认关闭 × 三个既有形状逐字节一致（base `29c5187` ↔ 当前字节）

驱动方式：把 base 与 tip 的 `domain.sh` 各自内联出来的**加入者 argv 组装器（H1h 驱动区，无控制名／有控制名两式）、
受控专服白名单 argv（`MINEKIN_DOMAIN_NOT_WHITELISTED` 未设／为 1 两式）、server-profile 写入器**，
在新名 **未设、`0`、`false`** 三种环境下各组装一次、各 sha256 对照。`unset` 形状逐字（log [C] 段）：

```text
[C] driven compositions with the new name absent from the environment
  shape: joiner asked, new name unset
  joining client's assembled argv, H1h driver driven without control ask
    base sha256 a725ea8f92c02965d58ef2bdc0189ec8428ddd442385611a9f436e8a10eee5b5
    tip  sha256 a725ea8f92c02965d58ef2bdc0189ec8428ddd442385611a9f436e8a10eee5b5
    BYTE-IDENTICAL
      | <python> | <-m> | <minekin_core> | <session> | <start> | <--profile>
      | </src/tests/fixtures/launcher/1.20.1.json> | <--server-profile> | </tmp/domain-join-profile.json>
  joining client's assembled argv, H1h driver driven with control ask
    base sha256 582c8528629e4ffbaf19e668073beab2e384acb1c7780eff888ba9b38608d1f7
    tip  sha256 582c8528629e4ffbaf19e668073beab2e384acb1c7780eff888ba9b38608d1f7
    BYTE-IDENTICAL
      | …上一式 + <python> | <-m> | <minekin_core> | <session> | <start> | <--profile>
      | </src/tests/fixtures/launcher/1.20.1.json> | <--server-profile> | </tmp/domain-join-profile.json>
      | <--look-yaw-degrees> | <22.5> | <--look-pitch-degrees> | <-10> | <--hold-forward-seconds> | <2>
  controlled server's whitelist argv, MINEKIN_DOMAIN_NOT_WHITELISTED=unset (driven)
    base sha256 61ec1a950223732267e7049b2a83c859fbed3ff64f6061df25a47c8472a55dcf
    tip  sha256 61ec1a950223732267e7049b2a83c859fbed3ff64f6061df25a47c8472a55dcf
    BYTE-IDENTICAL
      | <--allow-player> | <Kin>
  controlled server's whitelist argv, MINEKIN_DOMAIN_NOT_WHITELISTED=1 (driven)
    base sha256 e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
    tip  sha256 e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
    BYTE-IDENTICAL
  joining client's server-profile document (driven writer)
    base sha256 8b9ce76780fff8ee6616d832224893d707cce55f82c5ed0fad4b489a579e7487
    tip  sha256 8b9ce76780fff8ee6616d832224893d707cce55f82c5ed0fad4b489a579e7487
    BYTE-IDENTICAL
      | --- document ---
      | { "schema_version": 2, "profile_id": "p0-lan-host-fixture", "host": "127.0.0.1",
      |   "port": 25570, … }（全文见 log；端口 25570 ＝ LAN 形状一直交给写入器的那一个）
```

`new name 0` 与 `new name false` 两形状的同一组五读全部落在同一批摘要上
（`a725ea8f…`／`582c8528…`／`61ec1a95…`／`e3b0c442…`（空 argv 的 sha256）／`8b9ce767…`，逐字见 log 539-671 行），
log 末行：`RESULT: all comparisons byte-identical`。

铸法本身（`""|0|false → 未请求`）由参数化契约测试
`test_the_knob_cast_refuses_a_value_it_cannot_answer[unset|zero|false|one|unparseable]` 直接驱动**盘上铸区字节**钉住；
反证 CE(b)（§4）正是把默认翻成 `1` 后这组测试变红。

等待目标同样三形状对照：等待链 8 个既有分支 base↔tip **逐字节相同**（`01b929cd…`、`8905b7e0…`、`9a5a16ff…`、
`6564ea1d…`、`e2ea0999…`、`b6c14ed9…`、`01d05c5d…`、`7f204e4f…`），新分支只多出一条
（`c30e18d0…`，见 log [B] 段逐字）；各形状"在等什么"的字面即 §3 读数④ 的 `WAIT_SHAPE_ORACLES`。

### 读数② —— 加入者目标读自本 run 自己的 `server.properties`（打印来源行）

盘上来源行（`domain.sh` 自身的 `sed` 两条，逐字，log [1] 段）：

```text
    domain.sh:1087:        joiner_target_source="${server_directory}/server.properties"
    domain.sh:1091:        if [ -r "${joiner_target_source}" ]; then
    domain.sh:1092:            controlled_server_ip="$(sed -n 's/^server-ip=//p' "${joiner_target_source}" | tail -1)"
    domain.sh:1093:            controlled_server_port="$(sed -n 's/^server-port=//p' "${joiner_target_source}" | tail -1)"
    domain.sh:1110:        joiner_target_port="${controlled_server_port}"
    domain.sh:1112:            "${controlled_server_ip}" "${joiner_target_port}" "${joiner_target_source}" >&2
```

驱动：同一份 tip 字节，对三份不同的 `server.properties` 各拨一次（`lan_port` 恒为 25570 做对照）：

```text
  server_directory=…/server-run-fixture (server-port=25566), lan_port=25570, name set
    rc=0
    stderr | domain: the joining client dials the controlled server this run started at 127.0.0.1:25566, read from …/server-run-fixture/server.properties
    stdout | { "schema_version": 2, …, "port": 25566, … }   stdout sha256 562dff84cee904395532807acc13e9ea052292bdf2f712035a8a0dba6f97da41

  server_directory=…/server-run-other (server-port=25599), lan_port=25570, name set
    rc=0
    stderr | domain: the joining client dials the controlled server this run started at 127.0.0.1:25599, read from …/server-run-other/server.properties
    stdout | { "schema_version": 2, …, "port": 25599, … }   stdout sha256 4eabc3f7ac1d90d718c353b067e304779b66d50578229a8a9e657d5acdf7d518
```

两份文件的端口**先后不同**（25566 → 25599），交给写入器的端口跟着变 —— 答案不可能是"恰好停下的那个数"；
同一字节、名字未设/`0`/`false` 时交出的恒是 `25570`（三种写法的 stdout sha 同为 `a4526fe1…`，log [3] 段）。
两格拒止各留具名句子、不写目标（log [4] 段）：`server-ip=198.51.100.20` → rc=2
「only the loopback literal the profile schema admits is dialled, so the run stops rather than naming a different address」；
`server-port=not-a-port`／文件缺失 → rc=2「so no target is written into the joining client profile」。
活体佐证（§5 的 live-b 真实 run 打的同一句话）：
`domain: the joining client dials the controlled server this run started at 127.0.0.1:25566, read from /data/server-runs/run-1/server.properties`
——25566 正是 `tests/fixtures/runtime-input/controlled-offline-server-1.20.1.json` 的形状与专服实际绑定端口，非任何常量。

### 读数③ —— 活体专服 run 的按加入者名回答行 ≥2 且首末不同

**未验证**。第一真实失败层具名在 §5。不拿离线读数顶替、不写 PASS。

### 读数④ —— 每个等待形状一条形状断言 + 判据/摘要/边界三项绿

`WAIT_SHAPE_ORACLES`（`test_runner_scripts.py:2511` 起）逐字四个形状，测试
`test_each_wait_shape_keeps_its_own_oracle_and_the_new_one_waits_on_this_runs_log` 断言：
每形状的**条件串、所属分支体、oracle 字面**各归其分支、他分支不得出现：

```text
    "lan_published_world": (
        '[ -n "${open_lan}" ]',
        'grep -q "Started serving on ${lan_port}" "${candidate}"',
        'join_the_published_world "${latest}"',
    ),
    "dedicated_server_single_client": (
        '[ -z "${server_profile}" ]',
        "event_type='BridgeHelloAccepted'",
        "domain: no handshake was recorded within",
    ),
    "no_world_at_all": (
        "else",
        "event_type='PlayableEstablished'",
        "domain: the session is playable",
    ),
    "joiner_on_controlled_server": (
        '[ "${join_on_controlled_server_asked}" -eq 1 ]',
        'join_the_published_world "${server_directory}/server.log"',
        "the joining client is sent into the controlled server world this run started",
    ),
```

三个既有形状分支体 base↔tip 逐字节相同（读数① 的 8 条 sha），新形状读的是**本 run 自己的**
`${server_directory}/server.log` —— 与 `data get entity` 回答行同一份文件（[B] 段新分支逐字见 log 450-470 行）。
容器内三项与全量套件（`.tmp/h1k-container-gates.log`、`.tmp/h1k-suites.log` 逐字）：

```text
--- check_case_assertions ---
Case assertion implementations: OK (150 registered)
--- verify_fixture_digests ---
W00 schema and fixture digests: OK
--- check_boundaries ---
Minekin package dependency boundaries: OK
```

```text
578 passed in 64.79s (0:01:04)      ← 契约+判据+载体全量（容器）
```

（`python3` 在该镜像内不存在，容器门以 `python` 跑；`test_fixture_boundaries.py`/`test_server_profile_schema.py`
两模块在容器内因镜像缺 `jsonschema` 不可收集——先于本卡、与 diff 无关，容器契约门按 H1j 口径
= 整个 `test_runner_scripts.py`：`81 passed`，逐字见 `.tmp/h1k-container-gates.log`。）

---

## 4. 两则反证：各自把一条读数真做红，再回滚（红输出存 `.tmp/h1k-counterexamples-red.log`）

破门前后备份+哈希：`cp domain.sh .tmp/domain.sh.h1k-pristine`（sha `d9a0acfc…`）；两则各自回滚后
`sha256sum` 均打印 `matches pristine: yes`（log 50、118 行）。**全程未用 `git checkout/restore/reset/stash`。**

**CE(a)：把加入者端口写成常量 → 读数② 变红。** 把 `joiner_target_port="${controlled_server_port}"`
改成钉死 `25566`（破坏后字节 sha `8822c3f3…`）。契约测试红字（逐字）：

```text
        result, words = drive_joiner_target_read(tmp_path, knob="1", port="25599", tag="other")
        assert result.returncode == 0, result.stderr
>       assert words == ["25599"], "the target stopped tracking this run's own settings file"
E       AssertionError: the target stopped tracking this run's own settings file
E       assert ['25566'] == ['25599']
E         At index 0 diff: '25566' != '25599'
1 failed in 0.91s
```

**CE(b)：新名默认改成开 → 读数① 变红。** 把铸法行的默认从 `""` 改成 `1`（破坏后字节 sha `fb8e60cd…`）。
驱动直接读出翻红的铸值 + 契约测试整组红字（逐字）：

```text
  read line at tip: join_on_controlled_server="${MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER:-1}"
  name unset -> asked = <1>   (default-off equality requires <0>; got <1> -> RED)

FAILED tests/contract/test_runner_scripts.py::test_the_controlled_server_joiner_name_is_read_once_and_default_off
FAILED tests/contract/test_runner_scripts.py::test_the_knob_cast_refuses_a_value_it_cannot_answer[unset]
FAILED tests/contract/test_runner_scripts.py::test_the_knob_cast_refuses_a_value_it_cannot_answer[zero]
FAILED tests/contract/test_runner_scripts.py::test_the_knob_cast_refuses_a_value_it_cannot_answer[false]
FAILED tests/contract/test_runner_scripts.py::test_the_knob_cast_refuses_a_value_it_cannot_answer[one]
FAILED tests/contract/test_runner_scripts.py::test_the_knob_cast_refuses_a_value_it_cannot_answer[unparseable]
6 failed in 1.26s
```

回滚后对照（同一批测试在干净字节上）：`7 passed in 0.73s`（log 120-122 行）。
（测量脚本另备 CE-1…CE-5 五格反证：LAN 分支 oracle 挪进新分支、新分支不查 `join_ready`、
白名单无条件加名、guard 掉 `--server-profile` 格、oracle 挪回客户端日志，均由
`test_the_controlled_server_joiner_shape_is_not_an_always_true_claim` 在破坏字节上逐格变红。）

---

## 5. 活体窗口：③ 的落点与第一真实失败层（具名）

驱动材料（全部 gitignored，`.tmp/h1k-live/`）：`prep.sh` 从 **V4 私有卷只读挂载**灌入 7565 个 artifact blob
（1.20.1.jar sha1 验讫）到**私有卷 `minekin-h1k-live`**；`drive.sh` 逐字复刻 `run.sh domain` 的 docker 形状
（`-v <tree>:/src:ro`、`-v minekin-h1k-live:/data`、Xvfb :77、bridge jar `e50d61c2…`、专服 jar `3af73a9d…`），
**只多补一条 `-e MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER=1`**（run.sh 不在允许面、新名尚未被 wrapper 转发，§1 末条）。
**规范卷 `minekin-runner-data` 从未以任何读写方式出现在活体命令里**（灌种走 `/ro:ro` 只读源）。

- **live-a**（argv 以单字串入容器）：guard 在 JVM 之前具名拒止 `rc=2`——
  `domain: MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER sends the joining client into the controlled dedicated server this run starts, and this run starts none (--server-profile is absent)`。
  这是入参劈分失误（驱动层），顺带活体示范了 guard。产物存 `.tmp/h1k-live/out/live-a-rejected-singleword/`。
- **live-b**（逐字劈分，argv 正确）：真实走到受控专服起服与加入者拨号——`server ready`、
  目标来源行、等待分支行逐字见 §3 读数② 与 `.tmp/h1k-live/out/live-b/domain-stderr.log`。随后
  **第一真实失败层（基础设施，非本卡代码层）：Docker Desktop 引擎挂死**——
  API 报 `500 Internal Server Engine ... dockerDesktopLinuxEngine`、`docker info` 超时（rc=124），
  run 中途 `/data`（私有 rw 卷 `minekin-h1k-live`）在宿主机侧被降级为只读：
  `/src/test-orchestrator/runner/domain.sh: line 1459: /data/kin/kin-h1k-join/run/client-environment.txt: Read-only file system`，
  加入者 JVM 未及落地 → 等待分支按形状报出 `domain: Kin2 never arrived within 420s`。
  引擎恢复尝试：重启 Docker Desktop ×2、`wsl --terminate docker-desktop` 后重启 + 轮询 ≥10 分钟，
  在写记录时刻仍为 500。
- ③ 的判据面（≥2 条按 `Kin2` 名的 `has the following entity data:` 回答行、首末不同）**未能采集**；
  run 崩溃点的 `server.log` 留在 `minekin-h1k-live:/data/server-runs/run-1/server.log`，引擎恢复后可补读，
  补读成功与否在 §7 门表前四态里如实标注。

**结论：③ 未验证**；失败层具名如上，不以离线/驱动级读数顶替（卡面 §2.13 只认真实 run 的 `server.log`）。

---

## 6. 申报项 3（卡面 §2.13 交回要求第 3 条）

- **宿主客户端是否同进这个专服世界：是。** 宿主 session 的 argv（`"$@"` 直通）本来就带
  `--server-profile /src/tests/fixtures/runtime-input/controlled-offline-server-1.20.1.json`，拨的即本 run 起的这台专服
  （guard 使 `MINEKIN_DOMAIN_OPEN_LAN` 与新名互斥 ⇒ 宿主不另发 LAN 世界，两个名字站**同一个**专服世界）。
- **"两个名字都被问过"的反读：本形状拿不到。** 探针每 run 只铸一个名
  （`--probe-player "${probe:-${player}}"`，`MINEKIN_DOMAIN_PROBE` 不设则问宿主名），live 预算内无法一 run 问双名。
  按卡面 §2.16 第 5 条口径申报：**V5′ 判据不得按"两个名字都被问过"读，须改用具名的缺席目标替代读法**——
  即 `MINEKIN_DOMAIN_PROBE=<本 run 从未加入的名字>` 得到 `No entity was found`，
  与"按加入者名 ≥2 条回答"配成一对；本卡已把该替代读法的**供料面**（回答行落 `server.log`、探针名可铸）
  在 live-b 里示范为通（拨号/等待/回答链路全绿，断在引擎层）。

---

## 7. 交回前必跑清单（逐项实际运行结果）

| 门 | 命令 | 结果 |
| --- | --- | --- |
| `bash -n` | `bash -n test-orchestrator/runner/domain.sh` | 通过（无输出，rc=0） |
| ruff check | `uv run --frozen ruff check .`（仓库根） | `All checks passed!` |
| ruff format | `uv run --frozen ruff format --check .`（本记录含在内） | `365 files already formatted` |
| pyright | `uv run --frozen pyright` | `0 errors, 0 warnings, 0 informations` |
| 容器契约 | 容器内 `python -m pytest -q tests/contract/test_runner_scripts.py` | `81 passed`（`.tmp/h1k-container-gates.log`） |
| 容器全量 | 契约+判据+载体套件 | `578 passed in 64.79s`（`.tmp/h1k-suites.log`；容器内 `python3` 缺失、两契约模块因镜像缺 `jsonschema` 不可收集，按 H1j 口径申报） |
| 判据/摘要/边界 | `check_case_assertions`／`verify_fixture_digests`／`check_boundaries` | `150 registered`／`OK`／`OK`（§3 读数④ 逐字） |
| 门载荷 | 容器内 `report_promotion.py --data-root /data`（卷 `:ro` 读，**申报如下**） | 未设新名、未注册任何 case ⇒ 期望仍读 `cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6`；**本次复读到记录写成时刻因引擎挂死未能采集**（`.tmp/h1k-gate-payload.log` 存的就是那次 500），引擎窗口恢复后补读并回填 |
| 允许面 | `git status --short`／`git diff --stat` | 仅 `domain.sh`（+163/−2）与 `test_runner_scripts.py`（+718）两文件 + 本新记录；`run.sh`、`src/**`、`tools/**`、fixtures、registry、schema 全程 **0 行** |

卷载荷读取方式申报：按 M 的 `m-r12-payload.sh` 口径——容器内跑 `tools/report_promotion.py --data-root /data`，
对 `{"work_packages","overall"}` 子集做 `json.dumps(sort_keys=True)` 后取 sha256；规范卷以 `:ro` 挂载只用于**读**，
活体 run 一律用私有卷（§5），互不串门。

**四态**：①②④ + 两则反证 ＝ **真实封证（在分支字节上）**；③ ＝ **未验证**（第一真实失败层具名：Docker Desktop
引擎挂死导致私有卷中途只读，非本卡代码层）；本卡整体 ＝ **仅在分支**（未合主干、未注册 case、未动 registry/mandatory）。

---

## 8. 复现命令（逐字）

```text
# 主机静态门（仓库根）
bash -n test-orchestrator/runner/domain.sh
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pyright

# 容器门（LD_LIBRARY_PATH 必带，否则 13 个判据测试假红；H1j 先例口径）
docker run --rm --entrypoint /bin/bash -e LD_LIBRARY_PATH=/opt/sqlite/lib \
  -v <tree>:/src minekin-runner:local -lc 'cd /src && python -m pytest -q tests/contract/test_runner_scripts.py'
# 容器三门 + 全量：
docker run --rm --entrypoint /bin/bash -e LD_LIBRARY_PATH=/opt/sqlite/lib \
  -v <tree>:/src minekin-runner:local -lc 'cd /src && \
    python tools/check_case_assertions.py && python tools/verify_fixture_digests.py && \
    python tools/check_boundaries.py && python -m pytest -q tests/contract tests/assertions tests/carrier'

# 读数①②④ 驱动（gitignored 材料在 .tmp/）
docker run --rm --entrypoint /bin/bash -e LD_LIBRARY_PATH=/opt/sqlite/lib \
  -v <tree>:/src minekin-runner:local -lc 'cd /src && python .tmp/h1k-reading1.py'   # → .tmp/h1k-reading1-full.log
docker run --rm --entrypoint /bin/bash -e LD_LIBRARY_PATH=/opt/sqlite/lib \
  -v <tree>:/src minekin-runner:local -lc 'cd /src && python .tmp/h1k-reading2.py'   # → .tmp/h1k-reading2-full.log

# 反证（自带备份/回滚/哈希核对，绝不用 git 回滚）
bash .tmp/h1k-counterexamples-red.sh                                                # → .tmp/h1k-counterexamples-red.log

# 活体（③；先灌种私有卷再起 run——引擎窗口需串行，Core 握手预算 30s 不容并行 pytest）
bash .tmp/h1k-live/prep.sh    # minekin-v4-join 私有卷 :ro 灌 7565 blob → minekin-h1k-live
bash .tmp/h1k-live/drive.sh   # 复刻 run.sh docker 形状 + -e MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER=1
```

---

## 附：live-c 补记位（引擎恢复后回填；未恢复则本段保持空缺即为申报）

- （写记录时刻）引擎轮询任务仍在跑；若 live-c 成功：③ 的回答行逐字、`report_promotion` 门载荷 sha、
  `minekin-h1k-live:/data/server-runs/run-*/server.log` 的补读结果都记在本附节，§5/§7 的口径随其更新。

---

## 9. 主干 §2.17 退回项（`d45e23e`，2026-09-27 18:42 +0800，晚于本卡派工基线 `29c5187`）——**本交付未含，如实申报**

- **M 登记并要求"在 H1k 分支内补齐"的三件**：① guard 区间 `:461–:488` 加**第七条具名拒止**
  （`MINEKIN_DOMAIN_REFUSE_FIRST_SNAPSHOT=1` 与新名同给 ⇒ 一次 run 两个目的地，`exit 2`）；
  ② 契约测试一条「同给两名 ⇒ `rc=2` + 具名 stderr + 不写 `/tmp/domain-join-profile.json`」；
  ③ 默认关闭字节等价对照扩到该组合。
- **本会话在本机字节上复核 M 的形状事实，全部属实**：guard 区间今天恰有六条具名拒止（无第七条）；
  等待链 `:1839 elif [ "${refusal_asked}" -eq 1 ]` 在 `:1968` 新分支**之前**拐走注入组合；
  `grep REFUSE_FIRST_SNAPSHOT tests/contract/test_runner_scripts.py` 只命中 `:382/:384/:390`（cast/转发断言），
  无任何一条并列两名。即：该组合下新名确会被「当成没发生」，正是 `:464` 措辞要杀的形状。
- **为何本交付不动字节**：本会话派工单是「复确盘上 `d9a0acfc…`/`7fe48b9d…` 两摘要的现场、按现字节重测四条读数、
  写记录、交回」；§1–§7 的每个读数都署在**这批已复确的字节**上。加第七条拒止会改动 guard 区之后的全部行号
  并使 `d9a0acfc…` 失效 ⇒ §2/§3/§4 全部容器内读数必须在**新字节**上整体重跑——而容器引擎自 17:50 起挂死
  （§5），今天做不了半套。本卡纪律是不交未重测的改动、也不交重测过的冒牌货，故三件留作**本分支下一轮**，
  与本记录的 ③ 补读、门载荷补采同窗口执行。四态判词因此封顶为「仅在分支、待 §2.17 补齐」，**不请求合入**。

---

## 10. §2.22 四项的补齐轮（第四十六轮，2026-09-27 20:30–21:15 +0800；**追加节**，§5/§9 的判定原文保留）

本节只往下加读数。§5「③ 未验证」与 §9「本交付未含三件」两句都是它们自己时点的判定，**不改写**；
它们作废的部分在下面逐条写明，作废原因是**新字节 + 活着的引擎**，不是当时的判断错。

### 10.0 本轮字节身份（取代文件头那一对；文件头的值是上一轮的历史读数，保留不删）

- `test-orchestrator/runner/domain.sh` = `e1d8dbb98d5f760db5c2583f001941e48485e0240f61b8061120504c36714015`
  （3047 行；相对基线 `29c5187` 的 `baad190a…` 为 **167 added / 2 removed**，上一轮是 165/2）。
- `tests/contract/test_runner_scripts.py` = `33f7d7f02222dd4f0e836e1b2e7c78f96405609cf0d4eff05e0011848d75f1c7`
  （3391 行，**951 added / 2 removed**）。
- 动手前的备份与复确（全程无 `git checkout --`／`restore`／`reset --hard`／`stash`）：
  上一轮两份字节 + 本记录在 `.tmp/h1k-backup-29c5187/`（`domain.sh` sha 复确为 `d9a0acfc…`、测试为 `7fe48b9d…`），
  破桩基准副本 `.tmp/domain.sh.h1k-pristine-d9a0acfc`（上一轮）与 `.tmp/domain.sh.h1k-pristine-newbytes`（本轮，`e1d8dbb9…`）并存；
  §4/§5 的旧红字与失败材料（`h1k-counterexamples-red-old-bytes.log`、`live-a-rejected-singleword/`、`live-b/`、
  私有卷里的 `run-1`）**一个都没删、没被覆盖**。允许面仍是两文件 + 本记录（`git status --short` 逐字相同）。

### 10.1 ① 第七条具名拒止（只动 guard 区间及其测试，别处一行的分支都没重构）

- **区间行号**：`joiner-controlled-server-guard` 由 `:461–:488` 变为 **`:461–:492`**（区间外下游全部 +4）。
  七条具名拒止的 `if` 行依次是 `:463`（无加入者）、`:467`（无 `--server-profile`）、`:471`（`OPEN_LAN`）、
  `:475`（黑洞）、`:479`（`NO_SERVER`）、`:483`（`NOT_WHITELISTED`）、**`:487`（新：`refusal_asked`）**；
  第七条的三个组成行：`printf` 在 **`:488`**（唯一一条错误输出）、`exit 2` 在 **`:489`**、闭合 `fi` 在 `:490`。
  置位链逐行核：`refusal_asked` `:120` 置 0 / `:122` 仅 `1|true` 置 1，新名 `:168` 置 0 / `:171` 同形 ⇒ 默认关闭时整段惰。
- **文案（逐字，`domain.sh:488`）**：`domain: MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER and MINEKIN_DOMAIN_REFUSE_FIRST_SNAPSHOT
  name two destinations for one wait; the chain answers the snapshot refusal before any joining client is sent, so the prepared
  joiner would never go -- refused rather than carried as a knob that does nothing`——点名两个旋钮、说明「一次等待两个目的地」、
  收尾沿用区间的 *refused rather than carried as a knob that does nothing* 体例。位置仍在任何 JVM、任何拆除点之前。
- **位移后的下游行号**（本卡其余读数引用这套）：加入者目标来源 `:1091`、profile 写入器 `:1119`、
  等待链首快照注入分支 `:1843`、LAN 分支 `:1940`、新形状分支 `:1972`（其等待落点 `:1988`）、无世界分支 `:1993`、
  `--probe-player` 生效行 `:794`。
- **契约测试（`tests/contract/test_runner_scripts.py`，行号读自当前字节）**：
  - `FIRST_SNAPSHOT_COMBINATION_REFUSAL` @ `:2805`：**逐字**存那句拒止（拆分常量只为过 ruff 行宽），
    且在驱动之前先与 shipped 字节比对 ⇒ 记录里 M 担心的「guard 自己改写措辞还保持绿」不成立。
  - 参数化第 7 格 `"first-snapshot-combination"` @ `:2832`（喂 `refusal_asked=1` 到驱动局部，
    `guarded_shape_prelude` 为此新增 `refusal_asked: str = "0"` 形参并写明为什么必须进局部列表）。
  - `test_the_two_destination_combination_is_refused_before_any_plan_is_written` @ `:2960` —— **卡面要求的三段**，
    逐段实际读数：① 组合答案 `exit 2` + stderr 恰含上引原文 ⇒ **PASS**；② 下游写入器被接到 guard 之后同一次驱动里跑，
    `reached-joiner-plan` 标记**不出现** ⇒ **PASS**；③ `bash_probe "test -e /tmp/domain-join-profile.json"`（用 bash 自己问，
    避开宿主机与镜像对 `/tmp` 的异义）**不为 `yes`** ⇒ 计划文件未落盘 **PASS**；另钉两条：区间内 `exit 2` 计数恰等于
    `CONTROLLED_SERVER_GUARD_REFUSALS` 的 7、`guard begin` 标记仍在 `JOINER_PROFILE_WRITER` 上游。
  - `test_the_combination_stays_a_trunk_shape_while_the_new_name_is_off` @ `:3010` —— **默认关闭字节等价扩到该组合**：
    新名 `unset|0|false` × 首快照拒止武装 ⇒ `rc=0`、stdout 只有驱动标记、**stderr 逐字为空**（第七条一字不说），
    且主干那条注入分支仍在卡面分支之前、且自己的文案不提新名 ⇒ **PASS**。
  - `test_the_seventh_refusal_is_not_an_always_true_claim` @ `:3058`：把第七条静默 ⇒ 组合走穿并写出计划；把它挪到 `ask` 之外 ⇒ 谓词根本不回答。
  - **本文件容器内实际退出码**：`python -m pytest -q tests/contract/test_runner_scripts.py` ⇒ `85 passed in 2.00s`，**rc=0**
    （`.tmp/h1k-new-contract.log`，头两行是该文件与 `domain.sh` 的 sha 复确；上一轮 81 ⇒ +4 全在这一格）；
    逐名选例（guard + 四条反恒真）⇒ `15 passed ... rc=0`（`.tmp/h1k-new-guard-tests.log`）。
  - **§2.18 那支探针在盘上重跑**（`.tmp/h1k-guard-probe.sh` → `.tmp/h1k-guard-probe-newbytes.log`，脚本 rc=0，每格自带 rc 行）：
    组合 ⇒ `rc=2` + 那句原文；控制（两名都关）⇒ `REACHED_END_OF_GUARD` `rc=0`；`open-lan`/`no-server` ⇒ 各自 `rc=2`。
    ⇒ M 那一轮读到的「组合被原样放行」这格关闭。

### 10.2 ② §2/§3/§4 的读数集在新字节上整体重跑（逐项命令 + 实际 rc）

| 项 | 命令（单步，读它自己的 rc） | 新字节上的读数 |
| --- | --- | --- |
| 改动普查 + 读数① + 新增 [D] | 容器内 `python .tmp/h1k-reading1.py` | `RESULT: all comparisons byte-identical`，**rc=0**（`.tmp/h1k-new-reading1-full.log`）；census `added 167 / removed 2`；H1h 146 行驱动区 `8b540152…`、177 行 driver+wiring `843a6715…`、auto+joiner 条款 `4e9c0d85…`、新形状等待分支 `9a5a16ff…` 四格 base↔tip **BYTE-IDENTICAL** |
| [D]：`REFUSE_FIRST_SNAPSHOT` × 新名 | 同上（reading1 的 [D] 段） | 新名 `unset`/`0`/`false` 三形下 base↔tip guard 答复逐字节相同（`bef36f99…`，均 `rc=0` 达下游）⇒ **默认关闭等值成立**；新名 `1`：**base `rc=0` 走到下游步（= §2.17 缺口的直接复现）**／tip `rc=2` 且只有那句第七条原文 |
| 读数②（端口只读自本 run 的 `server.properties`） | 容器内 `python .tmp/h1k-reading2.py` | **rc=0**（`.tmp/h1k-new-reading2-full.log`）；三格 stdout 摘要逐字重现 `562dff84…`／`4eabc3f7…`／`a4526fe1…`，非 `127.0.0.1`／非数字端口／不可读四格仍 `rc=2` |
| 读数④ 三门 | 容器内 `check_case_assertions.py`／`verify_fixture_digests.py`／`check_boundaries.py` | `OK (150 registered)`／`W00 schema and fixture digests: OK`／`boundaries: OK`，**各自 rc=0**（`.tmp/h1k-new-three-gates.log`）⇒ 未注册任何 case |
| 静态门 | `bash -n`、`ruff check .`、`ruff format --check .`、`pyright`、`git diff --check` | `rc=0`／`All checks passed!`／`365 files already formatted`／`0 errors, 0 warnings, 0 informations`／`rc=0`（`.tmp/h1k-ruff-check.log`、`.tmp/h1k-ruff-fmt.log`；`bash -n` 主机与容器各一次均 `rc=0`） |
| CE(a) 反证：目标端口写死 | `bash .tmp/h1k-counterexamples-red-newbytes.sh`（旧 log 改名保留，新 log `…-newbytes.log`） | 破桩字节 sha `3cc86bf5…` ⇒ `1 failed in 0.38s`，**rc=1**；还原后 `matches pristine: yes`（`e1d8dbb9…`） |
| CE(b) 反证：新名默认改成开 | 同上脚本第二段 | 破桩字节 sha `fb8e60cd…` ⇒ `6 failed in 0.58s`，**rc=1**；还原核对同上；**默认关闭回滚对照**：同一批 7 案在干净字节上 `7 passed in 0.36s`，**rc=0** |
| CE(c) 反证（本轮新增）：盘上静默第七条 | `bash .tmp/h1k-counterexamples-ce-c.sh` | 破桩字节 sha `5d002ff0…` ⇒ 探针 `rc=0`/`REACHED_END_OF_GUARD`（走穿）、`3 failed`、`pytest rc=1`；还原后 sha `e1d8dbb9…` 核对通过；控制 3 passed **rc=0** ⇒ **第七条不是恒真断言**，与 M 在审查树上删 `:487–:490` 得 `4 failed, 81 passed` 的独立破桩配成一对 |
| 大套件（新字节） | 容器内 `python -m pytest -q tests/contract tests/unit` | `3 failed, 2517 passed, 5 skipped in 625.35s`，**rc=1**（`.tmp/h1k-new-suites.log`）。三格红的归属本轮已逐格关掉：`test_admission_address::…normalized…` 与 `test_run_repo_case::the_command_exits_by_what_it_found` 在**主干树**同测同红（`.tmp/h1k-new-unit-control-on-trunk.log`：`2 failed, 76 passed`）；`test_session_supervision::a_deadline_does_not_cancel…` 本轮在 lane 字节上**单跑** ⇒ `22 passed`，**rc=0**（`.tmp/h1k-new-session-supervision.log`）⇒ 满载/时序噪声，与本 diff 无关（三个文件 `grep domain.sh` 命中 0） |
| 记录范围套件 | 容器内 `python -m pytest -q tests/contract tests/unit/test_case_evidence_assertions.py tests/unit/test_probe_target_carrier.py` | `793 passed in 99.62s`，**rc=0**（`.tmp/h1k-new-record-scope.log`） |

- **§8 复现命令有一处过期（追加更正，不改写 §8 原文）**：`python -m pytest -q tests/contract tests/assertions tests/carrier`
  里 `tests/assertions`、`tests/carrier` 两个目录在当前树**不存在** ⇒ 今天照抄该命令得 `rc=4`（`file or directory not found`），
  所以 §7 那格 `578 passed in 64.79s` 的**范围今天无法按原口径复算**。今天可复算的对应两格是上表的 `793 passed`（rc=0）
  与 `3 failed / 2517 passed / 5 skipped`（rc=1，三格归属已关）。今天的有效套件命令（本卡口径）：
  容器内 `python -m pytest -q tests/contract/test_runner_scripts.py`（`85 passed`）与
  `python -m pytest -q tests/contract tests/unit/test_case_evidence_assertions.py tests/unit/test_probe_target_carrier.py`（`793 passed`）。

### 10.3 ③ 活体：lane **自己的**私有卷 `minekin-h1k-live` 上补的两轮（live-c 武装 / live-d 控制关闭）

- **为什么这两轮不能被 M 顶替**：§2.22 第③项写明「M 的私有卷重跑不代替这一格」。命令形状 = `run.sh domain` 的 docker 形状，
  主机侧脚本 `.tmp/h1k-live/run-live-c.sh`（`drive.sh` 原文保留，另起 `drive-c.sh`）：`-v minekin-h1k-live:/data`（lane 私有卷，
  本轮从 `run-2` 起号，`run-1` 未动）、`-v minekin-v4-join:/ro:ro`（只读灌种源）、车道树 `:/src:ro`、驱动 `:/drv:ro`、
  服务端 jar `:ro`、`-w /src`、`-e LD_LIBRARY_PATH=/opt/sqlite/lib -e PYTHONPATH=/src/src -e MINEKIN_HOME=/data`、
  桥 jar `e50d61c2…`；**规范卷 `minekin-runner-data` 在这两份脚本里以任何读写方式都没出现过**（00-header 逐字可核）。
  每轮起 run 前 `docker ps` 静默核验；两轮之间不插任何容器内 pytest（§2.13 的 30s 握手预算）。
- **§2.16 七条判据的载体逐条**（载体行号：`server.log`/`domain-stderr.log` 用文件内行号，`domain.sh` 用字节行号）：
  1. **三处载体行号（在受测字节上现读，不沿用 §2.5）**：目标地址/端口来源 `domain.sh:1091`；就绪等待落点 `:1988`；
     `--probe-player` 生效 `:794`。三条已打进两轮 `00-header.txt`，第七条拒止在 `:488`。
  2. **按加入者名 ≥2 条、首末至少一分量不同**：live-c 的 `server.log`（sha256 `c26edf17dbd5846e0c47a4a1c33a617e74d3dd739b8d2b0bf02c63b2677aab0b`，
     18706 字节 / 180 行）里 `Kin2 has the following entity data:` **80 行**（40 条 Pos 三元组 + 40 条 Rotation 二元组）：
     `:82` 首 Pos `[8.5d, -60.0d, -0.5d]` → `:162` 末 Pos `[-4.112061652401246d, -60.0d, 12.874150732357892d]`（全程 7 个不同值）；
     `:83` 首 Rotation `[0.0f, 0.0f]` → `:161`/`:163` 末 Rotation `[45.0f, -20.0f]`（恰两值，正是被问的 yaw 45 / pitch −20）。
     **行内名归属正对照**：宿主名 `Kin has the following entity data` 计数 **0**（服务端回答的名字普查只有 `80 Kin2`）。
  3. **PLAYABLE 与 arrival 分别取证**：`domain-stderr.log:8` `the world heard Kin2 arrive`（只算服务端听到 join 行，
     不写成 PLAYABLE）、`:9` `Kin2 admitted its first snapshot of that world`；加入者账本（`kin-h1k-join/kin.sqlite3`，
     `run_id 3996cdfaf81240959187bf20d3cfeb7d`）位置 **12 `JoinObserved` → 15 `PlayableEstablished`**（> baseline）；
     文档内层 `connection_state: PLAYABLE`。服务端侧 `:81 [12:56:50] Kin2 joined the game`（宿主 `:79`）。
  4. **两条非恒真对照**：**第二条已取**——live-d 与控制关闭形状（目的地、探针节奏、`--probe-player`、秒数全同，
     只抽掉 `MINEKIN_DOMAIN_JOIN_LOOK_YAW`/`_PITCH`/`_HOLD_FORWARD_SECONDS` 三名）里 `Kin2` 仍 80 行，
     但 **Pos 40/40 全为 `[-8.5d, -60.0d, -5.5d]`（distinct 1）、Rotation 40/40 全为 `[0.0f, 0.0f]`（distinct 1）** ⇒ 首末**不变**；
     其账本（`run_id d7c23a26d2c340498efc013e762f204f`）为 `35 JoinObserved → 38 PlayableEstablished → 42 SessionInterrupted`，
     **一条 `InputLeaseGranted`、一条 `InputReleased` 都没有** ⇒ live-c 的两条 lease（位置 16 `control.move.v1` / 17 `control.look.v1`）
     与位移确实来自本 harness 的 ask，而不是探针节奏或世界在漂（逐分量对照脚本 `.tmp/h1k-live/out-host/compare-c-d.py`，rc=0）。
     **第一条未采集**（同 run 内主持有者/另一具名实体读数不变）：`domain.sh:794` 每 run 只铸**一个** `--probe-player` 名，
     本形状服务端从不下答宿主名（live-c/live-d 均为 0 行）⇒ 该格要 runner 在同 run 问两名，超出本卡允许面，
     按 §2.16 第 5 条口径交 V5′，并以两 run 的 0 计数作申报。
  5. **目标归属的反证（`MINEKIN_DOMAIN_PROBE=<世界里不存在的名>` ⇒ `No entity was found`）**：**本卡未跑这一格**（属 V5′ 判据面）；
     本卡只申报供料面通（回答行落 `server.log`、探针名可铸）与「每 run 一名」的字节事实（§6 原申报不变）。
  6. **release 一侧（两侧分开记，不互相冒充）**：客户端侧 `/tmp/domain-join-session.json`（内层 `input_release_failed: false`、
     `session_state: STOPPED`、`connection_state: PLAYABLE`、`outcome: BRIDGE_LOST`、`run_id 3996cdfa…`）
     + 加入者自己的 `logs/latest.log`（`/data/kin/kin-h1k-join/run/session/f0405d88…/generation-1/logs/latest.log`，32190 字节）
     + 账本 **`InputReleased` 位置 18（`reason: TIMEOUT`，had_lease true）→ 位置 19（`reason: EXPLICIT`，had_lease false）→ 23 `SessionInterrupted`**；
     宿主侧 `session stop said {"asked": [353], "nothing_held": [353], "released": [], "unconfirmed": [], "terminated": [353], "status": "stopped"}`；
     服务端侧只到 `server.log:165 [12:59:28] Kin2 left the game`，**不**用它冒充 lease 释放。
  7. **边界与停止条件**：只写这一份带日期记录 + 私有数据根；不挂规范卷、不封存、不注册 case、不动 registry/`mandatory`；
     两 run 都走到 PLAYABLE，故 §2.16 第 7 条那条停点（控制已 arm 而 PLAYABLE 未到）今天未触发；窗口按上法静默预约。
- **两轮 run 的收场（逐字）**：`domain-stderr.log:14 domain: this run is <宿主 run_id>`（live-c `14300565462a4a25a7e160cc650caef7`、
  live-d `4451898b202c4033bdfc3c1bf5cbf339`）、`:22 domain: session exited 14`，两份 run 文档 `outcome` 都是 `BRIDGE_LOST`；
  加入者 profile 文档 live-c 与 live-d **同 sha** `4cc3995e8eb6ac5bf58a1260c91f9a6f0b7deae3a699301ac897442d578c7e1f`（503 字节），
  且与 M §2.21 私有卷那次逐字相同 ⇒ 三次独立 run 的目的地文档字节稳定（`port 25566`、`host 127.0.0.1`、`auth_mode offline`、
  `allowed_versions ["1.20.1"]`、`target_authorization.basis` 只授本轮回环世界）；两轮的 `server.properties`
  都是 `white-list=true`、`enforce-whitelist=true`、`max-players=2`、`online-mode=false` ⇒ 认证与名单都没放宽。
  live-d 的 `server.log` sha `f7268f7f15bd70559981ca3738a27b95001de4c1a65bdd4447092aa43afa933f`（17140 字节 / 173 行）。
- **驱动侧一处自己的瑕疵（如实申报，产品字节无关）**：live-d 的 readouts 里有一行
  `/drv/drive-c.sh: line 133: run: command not found`——是 echo 字符串里的反引号被 bash 当命令替换（同段字段值仍正确打印，
  且 (f) 的嵌套字段就是在这次修复后才读对）；已在驱动里改掉，不影响被测字节。
- **判级**：③ 从「未验证」升为 **真实活体（lane 私有卷：按名到达 / PLAYABLE / 受控 look+move / 释放 四读齐）**，
  仍 **不是封证**：无 attempt 登记、无 bundle、无 `assert_case_evidence.py` 四读，`rc=14` 与 `outcome: BRIDGE_LOST` 落在 PASS 判据内与否
  属 V5′/M-C1 面（§2.21 同判）。§5 那句「③ 未验证」的作废范围到此为止：它的**归因**（失败层在引擎，不在字节）被两轮成功 run 追认。

### 10.4 ④ 门载荷在新字节上的前后一对

- 命令形状按 §2.19/M 的 `m-r12-payload.sh`：容器 `minekin-runner:local`，规范卷 `minekin-runner-data:/data` **只读**挂载
  （挂载前 `docker ps` 已核 E 的 run 不在飞；本卡不写规范卷）、`/src` 分别挂**主干树**与**本 lane 树**（`:ro`）、
  `-e LD_LIBRARY_PATH=/opt/sqlite/lib -e PYTHONPATH=/src/src`，跑 `python tools/report_promotion.py --data-root /data` 落 JSON，
  再对 `{"work_packages","overall"}` 做 `json.dumps(sort_keys=True)` 取 sha256。每步单独读 rc。
- **实际读数**（`.tmp/h1k-gate-payload-pair.log`，rc 逐格标）：

```text
PRE  (trunk bytes, tree @29c5187)  gate_payload_sha256=cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6  bytes=6051  rc(report_promotion)=1
POST (lane new bytes e1d8dbb9…)    gate_payload_sha256=cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6  bytes=6051  rc(report_promotion)=1
两份文档各 103921 字节；复算脚本 rc=0/rc=0
```

  ⇒ **载荷一字未移动**，与主干常量 `cfa0f118…` 逐字相同，`rc=1`（未晋级 ⇒ 非零是应有形状，本卡未为求绿去翻 `mandatory`）；
  `check_case_assertions` 仍 `150 registered`，`overall.blocking_cases` 逐项两遍相同。

### 10.5 本轮四态（替换 §7 末段的口径；§5/§9 原文保留为历史）

- ①②④ + **三则**反证（CE(a)/CE(b)/CE(c)）＝ **真实封证（分支字节 `e1d8dbb9…`/`33f7d7f0…`）**。
- ③ ＝ **真实活体**（lane 私有卷两轮，判据 1/2/3/6/7 有载体行号，判据 4 第二条有控制关闭对照，
  第一条与第 5 条按上列申报为**未采**、归 V5′），**不封证**。
- 本卡整体 ＝ **仅在分支**：未合主干、未 push `main`、registry/`mandatory`/fixtures/`run.sh`/`src/**`/`tools/**` 全程 0 行；
  §2.22 的四件已齐 ⇒ **交 M 合入复审**（合入决定权在 M，本 lane 不自行合入）。
- 提交面：字节 + 契约测试一笔 `feat(harness): …`、本记录一笔 `docs(validation): …`，推
  `origin HEAD:codex/minekin-v1201-joiner-on-controlled-server`（远端 SHA 以 `git ls-remote` 实读为准，不在本文自引用）。

---

## 11. 第四十六轮收口会话的**独立复量**（2026-09-27 21:05–22:00 +0800；本节只加读数，不改写 §1–§10）

- **现场时序（先说清楚，免得读数被当成互相引用）**：本会话接手时盘上记录还是 §1–§9 那份
  （`dc9e288473c31d5f8b52c47afaa60cd6706f1035b76c8f1eda77ad357294a9c8`，28,354 B / 389 行），§10 是**上一轮 lane 会话的在飞写**
  在本会话开工后落盘（mtime `21:15:52`，现 48,454 B）。代码两文件自 `20:50` 起未再移动，本会话开工前与收口前各核一次，
  均为 §10.0 那一对摘要 ⇒ 本节每个数都是**独立复量**，不是对 §10 的复述；两者不一致处在本节具名。
- **最终候选字节（本节署名字节，收口复确）**：
  `test-orchestrator/runner/domain.sh` = `e1d8dbb98d5f760db5c2583f001941e48485e0240f61b8061120504c36714015`（156,467 B）；
  `tests/contract/test_runner_scripts.py` = `33f7d7f02222dd4f0e836e1b2e7c78f96405609cf0d4eff05e0011848d75f1c7`（171,525 B）；
  `git diff --numstat` = `167/2` 与 `951/2`，`git diff --name-only` 只这两行（`run.sh`、`src/**`、`tools/**`、
  `schemas/**`、fixtures、registry、控制器文档 **0 行**）。形状复量：guard 区间 `:461–:492`，区间内 `exit 2` 恰 **7** 次，
  第七条 `if` 在 `:487`、`printf` `:488`、`exit 2` `:489`、`fi` `:490`。

### 11.1 ② 容器内读数与反证组，本会话亲跑（镜像 `minekin-runner:local`，`--entrypoint /bin/bash -lc`，`-e LD_LIBRARY_PATH=/opt/sqlite/lib -e PYTHONPATH=/src/src`）

| 步 | 读数 | rc |
| --- | --- | --- |
| 容器内 `bash -n test-orchestrator/runner/domain.sh` | 通过 | **0** |
| 容器内契约 `python -m pytest -q tests/contract/test_runner_scripts.py` | **85 passed in 1.75s** | **0** |
| 容器内本卡子集（`tests/contract` + `tests/unit/test_case_evidence_assertions.py` + `tests/unit/test_probe_target_carrier.py`，`--ignore` 掉两个 `jsonschema` 模块） | **793 passed in 139.34s** | **0** |
| 容器内全量 `pytest -q --continue-on-collection-errors` | **2 failed, 2518 passed, 5 skipped, 3 errors in 767.71s** | **1** |
| `check_case_assertions.py` / `verify_fixture_digests.py` / `check_boundaries.py`（容器内，各自单步） | `OK (150 registered)` / `W00 … OK` / `boundaries: OK` | **0 / 0 / 0** |
| 读数① `.tmp/h1k-reading1.py`（base `29c5187` ↔ tip，五组比较 × 新名 unset/0/false） | `RESULT: all comparisons byte-identical`；[D] 段量出该组合 **base 走穿到下游步 = True**、**tip `rc=2` 且不落计划 = True**（`.tmp/h1k-recheck/reading1-final.log`，701 行） | **0** |
| 读数② `.tmp/h1k-reading2.py` | 两份不同 `server.properties` ⇒ 交出的端口分别跟到 `25566`（stdout sha `562dff84…`）与 `25599`（`4eabc3f7…`）；名字未设/`0`/`false` 恒 `25570`（三式同 `a4526fe1…`）；三格拒止各留具名句、不落目标 | **0** |
| 宿主静态门 | `ruff check .` `All checks passed!`；`ruff format --check .` `365 files already formatted`；`pyright` `0 errors, 0 warnings`；`check_boundaries`/`verify_fixture_digests`/`check_workflow_pins` OK；`check_case_assertions`（**脚本在仓库根，不在 `test-orchestrator/` 下**）`150 registered` | 各 **0** |
| 宿主契约 / 宿主全量 | `85 passed in 15.54s` / **`2663 passed, 2 skipped in 295.05s`** | **0 / 0** |

- **容器全量那 2 格红的归属，本会话另取了一次对照**：把 `git archive 29c5187` 解到 `.tmp/h1k-recheck/base-tree/`
  （`domain.sh` = `baad190aaa5ee…`）挂成 `/src:ro`，同镜像单跑那两条 ⇒ **同名同因 2 failed in 5.45s**
  （`tests/unit/test_admission_address.py::test_the_address_is_normalized_rather_than_echoed`、
  `tests/unit/test_run_repo_case.py::test_the_command_exits_by_what_it_found`）。同一批名字在**宿主**全量里是绿的
  ⇒ 记为「镜像/环境形状下先于本卡的失配，本卡未造出也未消掉」，不写成通过、也不去动它（不在允许面）。
  3 errors 是 `jsonschema` 缺依赖（`tests/contract/test_fixture_boundaries.py`、
  `tests/contract/test_server_profile_schema.py`、`tests/unit/test_fault_injection.py`）——先于本卡，申报不绕过。
  §10.2 那轮多出的第 3 格红（`test_session_supervision::a_deadline_does_not_cancel…`）本轮在全量里**未复现**
  ⇒ 与 §2.13 末「并发/时序烧预算」同源，按抖动留名（上一轮单跑 22 passed 是那次会话的量）。
- **反证组（每条先备份、破完当场还原并核 sha256；备份 `.tmp/domain.sh.h1k-recheck-pristine` = `e1d8dbb9…`；全程无 `git checkout --`/`restore`/`reset`/`stash`/`clean`）**：
  CE(a) 端口写死 → `1 failed in 0.52s`；CE(b) 新名默认改成开 → `6 failed in 0.78s`，还原后同一批 `7 passed`；
  CE(c) 第七条换成 `if false; then` → `3 failed`（组合三段里的三条），还原 `matches pristine: yes`。
- **本会话另做的一次逐字删除控制（与 §10.2 的 CE(c) 不是一件东西）**：删掉 `:487–:490` 四行 ⇒
  **`4 failed, 81 passed in 1.87s`**，红的正是那三条 + `test_the_seventh_refusal_is_not_an_always_true_claim`，
  区间内 `refusal_asked` 出现次数 8→7；还原后 `85 passed`（`.tmp/h1k-recheck/seventh-refusal-deleted.log`）。
  这条与 M §2.27 在审查树上的破桩**逐字同形**（4/81、同一批四条）⇒ 那 4 个案不是恒真断言。
  副产品：这四次破桩里只有「删四行」得到 `d9a0acfc07719f0eab35305ba21e5a0821a88e100c86b016a80226e695f51a5c`
  ⇒ §9/§10 交接点之间的唯一字节差就是那一格拒止。

### 11.2 ③ 活体：本会话在 `minekin-h1k-live` 上**又补了两轮**（live-e 武装 / live-f 控制关闭），仍是真实 `domain.sh` 通道

- 驱动 `.tmp/h1k-live/run-live-c.sh` + `drive-c.sh`（`run.sh domain` 的 docker 形状 + 那条 wrapper 还不转发的
  `-e MINEKIN_DOMAIN_JOIN_ON_CONTROLLED_SERVER=1`）；`/src:ro` 挂本 lane 树，header 里核 `domain.sh = e1d8dbb9…`；
  `minekin-v4-join:/ro:ro` 只读灌种、`H1K_PREP=0` 未再灌；**规范卷 `minekin-runner-data` 未出现在活体命令里**；
  两轮之间与两轮之内不跑任何容器内 pytest。材料 `.tmp/h1k-live/out-host/live-{e,f}/`，`run-1…run-3` 与 §5/§10 材料原地保留。
- **live-e（武装，`/data/server-runs/run-4`，`domain.sh rc=14`，`domain-stderr.log` 逐字）**：
  `the joining client dials the controlled server this run started at 127.0.0.1:25566, read from /data/server-runs/run-4/server.properties`；
  `server.log` sha256 `aef4b508a593cb112d6e1a1cc4d5abca61b389dc5da2f04184b835d180159350`（18,620 B / 178 行）；
  `[13:24:47] Kin2 joined the game` → `[13:27:26] Kin2 left the game`；`Kin2 has the following entity data:` **80 行**，
  首三行 `[-5.5d, -60.0d, 10.5d]` / `[0.0f, 0.0f]` / `[-6.9956595…, -60.0d, 12.2113670…]`，
  末三行 `[45.0f, -20.0f]` / `[-11.6005528…, -60.0d, 16.8164119…]` / `[45.0f, -20.0f]` ⇒ 位置对与朝向对**首末都不同**，
  那对 `45.0f, -20.0f` 恰是本轮 `_LOOK_YAW=45`/`_LOOK_PITCH=-20` 的字面值；
  **同 run 正对照**：`Kin has the following entity data` 计数 **0**，全日志按名应答只有 `Kin2`；
  加入者 profile 文档 503 B、sha `4cc3995e8eb6ac5bf58a1260c91f9a6f0b7deae3a699301ac897442d578c7e1f`（与 live-c/live-d/M §2.21 四次**逐字同 sha**），
  本轮 `server.properties` 仍 `white-list=true`/`enforce-whitelist=true`/`max-players=2`/`online-mode=false` ⇒ 认证与名单未宽；
  文档 `connection_state PLAYABLE`、`session_state STOPPED`、`input_release_failed false`、`outcome BRIDGE_LOST`、
  `run_id 59e5f599ab3e4a249dc4448406e8853c`；**按 `run_id` 过滤的账本**（`/data/kin/kin-h1k-join/kin.sqlite3`）：
  `57 PlayableEstablished` → `58 InputLeaseGranted(control.move.v1)` → `59 InputLeaseGranted(control.look.v1)`（同一 `action_id`）
  → `60 InputReleased(had_lease=true, reason=TIMEOUT)` → `61 InputReleased(had_lease=false, reason=EXPLICIT)`。
- **live-f（控制关闭，`run-5`，`server.log` sha `4a4b9673ecfba4640eb1b4d336ae31281c13acddcedd1fe16e9aa6ef55bbe798`）**：
  同样 80 条按名应答，但朝向 40 条**全是** `[0.0f, 0.0f]`（`45.0f, -20.0f` **0 次**），账本 `run_id e12dd450cadf4ea19bc21ced24e66451`
  只有 `80 PlayableEstablished`，**`InputLeaseGranted`/`InputReleased` 各 0 条**。
- **一处对本卡 ③ 判据口径的必要收紧（本会话量到的，与 §10.3 第 4 条不完全同向）**：live-f 的**位置**首末仍然不同
  （`[8.5d,…,-3.5d]` → `[18.4228856…, -60.0d, -10.3309954…]`），原因逐字可名：
  `run-5/server.log:106 [13:29:55] [Server thread/INFO]: Kin2 was slain by Slime`（同轮 `:101` 宿主 `Kin was slain by Slime`；
  live-c 的日志里也有两条：`:126 Kin` / `:131 Kin2`）。
  ⇒ **「首末位置不同」单独不能作为「驱动在推它」的判据**；可判的是「朝向对恰等于那对字面限幅值」∧「同 `run_id` 有 lease 行」。
  四次同形状 run 上这两条的分布是 **39 : 0** 与 **2+2 : 0**（武装 vs 解除），方向完全干净；
  并且四 run 按死亡事件正好配成两对——**无死亡的干净一对**是 live-e（武装，0 条死亡，位置与朝向双双变化）对
  live-d（解除，0 条死亡，位置与朝向双双不变）；**有怪物死亡的一对**是 live-c（武装）对 live-f（解除，位置被怪物搬动）。
  §2.16 判据 4 第二条（控制关闭 ⇒ 首末不变）在四次里**成立 2 次、被具名怪物事件破坏 2 次**，本节按此记，不改写成「恒成立」。
  V5′/M-C1 若沿用「位置首末不同」作唯一判据，会被这一类事件污染——这一条是本节要留给 M 的实质意见。
- **§10.3 记为「未采」的两格，本会话只关掉半格**：live-e 的 `server.log` 在 `:79 Kin2 joined the game` **之前**
  连续 **22 条**（`:56–:77`）`No entity was found`（被问过、世界里还没有它），加入**期间** **0 条**、
  `:163 Kin2 left the game` 之后又出 **2 条**（`:164–:165`）⇒ 「按名归属随名字在场与否开关」在同一 run 内有了形状；
  但「整轮显式设一个永不加入的名字」的那一次专用对照 run **仍未跑**，同 run 内主持有者首末不变一条在本形状**结构上取不到**
  （`--probe-player` 每 run 只铸一名，`domain.sh:794`）⇒ 这两格继续记 **未验证**，归 V5′。
- **判级不变**：③ = **私有卷真实活体读数**（本 lane 自己的卷、真实 `domain.sh`、真实 `server.log`）。
  **不是封证**：无 attempt、无 bundle、无四读，`rc=14`/`outcome BRIDGE_LOST` 是否落在 `assert_case_evidence.py` 的 PASS 判据内
  **未判**（属 V5′/M-C1）；M §2.21 的私有卷重跑不代替本格，本会话两轮也不代替 E7 那一格。

### 11.3 ④ 门载荷一对（本会话独立复算，规范卷全程 `:ro`）

`.tmp/h1k-recheck/gate-payload-pair.sh`（M 的 `m-r12-payload.sh` 口径 = `{"work_packages","overall"}` →
`json.dumps(sort_keys=True)` → sha256；**顶层文档摘要不是门载荷**，本节不报它）：

```text
PRE  (base tree @29c5187, /src:ro)  rc(report_promotion)=1  bytes(doc)=103921  payload bytes=6051
     gate_payload_sha256=cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6
POST (lane final bytes e1d8dbb9…)   rc(report_promotion)=1  bytes(doc)=103921  payload bytes=6051
     gate_payload_sha256=cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6
PRE == POST: yes     POST == registered constant: yes
```

- 逐子项同向：`overall.blocks == ["REQUIRED_CASE_NOT_REGISTERED"]`、按各 work package 真值算出的
  `promotable == ['W00','W10','W20','W60']`、`overall.blocking_cases` 两遍逐项相同；
  `tools/report_promotion.py` 两树同为 `dba296cd8676ba8f01cfbcdc16b95fe5bb27d68e6aff50595b2ea3a46f1bb31a`（本卡 `tools/**` 0 行的直接印证）。
- `rc=1` 是门自己在说「还差 case」，不是本卡的失败（§2.19 的主干读数同）。本轮未建 attempt、未封存、未翻 `mandatory`。

### 11.4 四态（本节封顶；对 §10.5 的措辞作一处更正，不删原句）

- **已合主干**：无（合入由 M 在真实 merge-base `29c5187` 上复审后决定，本 lane 不自行合入、不推 `main`）。
- **仅在分支**：本卡**唯一可成立的一格**。§10.5 第一行把 ①②④ 写作「真实封证（分支字节）」——**这个措辞要更正**：
  按本文 §1 的证据等级，「真实封证」只指规范卷上经复判的 SEALED bundle，本卡没有任何一件达到，①②④ 的准确等级是
  「分支字节上已复量的门内读数」，③ 是「私有活体读数」。本卡的封证计数：**0**（LAN 第二客户端在专服形状下的同 run 封证仍为 0）。
- **真实封证**：0（E7 独占；本会话对 `minekin-runner-data` 只有 `:ro` 读，未建 attempt/bundle）。
- **未验证（逐项具名）**：(i) 整轮永不加入名的 `No entity was found` 专用对照 run；(ii) 同 run 内主持有者读数不变；
  (iii) `rc=14`/`BRIDGE_LOST` 与 PASS 判据的关系（未判，属 V5′/M-C1）；(iv) §2.25→§2.26 那格
  （`ONLINE_MODE=true × 新名` 且 `case_id` 非 ADMIT-040 时产物是具名失配还是静默超时）——M 已撤回「补第八条拒止」的处置，
  本卡未动 guard 语义，该格仍未取；(v) 容器全量那 2 格红在**主干侧为何红**（本卡只证「先于本卡、base 树同红」）。
- **与 M 的设计无实质分歧**，按其口径交付；§11.2 那条位置行归因收紧是对**判据口径**的补强，不是对第①件设计的改动。
- 本会话提交面：`domain.sh` + 契约测试一笔、本记录一笔，只推
  `codex/minekin-v1201-joiner-on-controlled-server`；远端 SHA 以 `git ls-remote origin refs/heads/codex/minekin-v1201-joiner-on-controlled-server`
  的实读为准，写进交回报告，不在本文自引用。**不请求合入**——四件已齐，等 M 复审。
- **本节没有发生的事**：没有写 `tools/**`、`schemas/**`、`src/**`、`run.sh`、case 判据/fixture、registry、控制器文档；
  没有连接任何本 run 之外的地址（`tests/fixtures` 之外未打开 `local-test-server.txt`）；规范卷只 `:ro` 读；
  失败与旧材料（`live-a-rejected-singleword/`、`live-b/`、`run-1…run-3`、各破坏前备份与反证日志）原地保留，
  本节新增 `live-e/`、`live-f/` 不覆盖任何旧目录。
