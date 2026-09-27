# V1201-PROBE-TARGET-CARRIER-001 — 服务端探针的「问的是谁」第一次有了封存载体（M-C0 lane）

日期：2026-09-27。执行 lane：M-C0（tools 面）。
基线：`origin/main` @ `5d0cd2a44f55cca714bf74ff02e847c6bcd71bf6`（`git rev-parse HEAD` 于 worktree 实读一致）。
分支：`codex/minekin-probe-target-carrier`，worktree `../minekin-wt-mc0`。
容器：`minekin-runner:local`，image id `b67a4d917306`；仓库挂载 `:ro`，规范卷 `minekin-runner-data` **全程 `:ro`**，
本卡零封存写入规范卷、零写 `/data` 任何路径。
改动面（`git diff --name-only 5d0cd2a HEAD` 恰四条）：`tools/seal_run_evidence.py`、
`tools/assert_case_evidence.py`、新测试 `tests/unit/test_probe_target_carrier.py`、本记录。
未动：`test-orchestrator/**`（含 `domain.sh`，另一 lane 正在改）、`schemas/**`、`minekin.p0.evidence.v1` 封存
schema、`tests/fixtures/cases/**`、`tests/fixtures/registry/**`、任何 `mandatory`、任何 case id、任何既有测试。

## 一、卡面前提逐条复量（在基线字节上，不是在读文档上）

| 卡面断言 | 实测（基线 `5d0cd2a`） |
| --- | --- |
| 探针是控制台命令，名字只在命令里 | `tools/run_controlled_server.py:489 position_probe_command` → `:504 return f"data get entity {player} Pos"`；`:507 rotation_probe_command` → `:520 Rotation`。名字进命令，不进回话 |
| 真封 `server/server.log` 里零行带玩家名 | 规范卷只读统计：含 `server/server.log` 的 bundle **78** 份，`has the following entity data: [` 回答行 **460** 行，携带 `data get entity` 的行 **0** 行 |
| 判据只按分量数区分位置/旋转，不按名字 | `tools/assert_case_evidence.py:246 _PROBE`、`:266 probe_readings(log, components)`、`:1599 the_server_saw_the_kin_move` 取 `positions[0]` 与 `positions[-1]`，全 log 首尾，无名字维度 |
| 100 份 `orchestrator-trace.json` 不记被探者 | 只读统计：bundle **100** 份，trace **100** 份，全部 trace 顶层键并集恰为 `case_id / orchestrator / run_id / schema_version / sealed_at_utc / server_directory / session_argv / verdict`，无 player/probe 类键 |
| `asserter-inputs.json` 在 `:795` 由 `asserter_inputs_bytes(...)` 写出，常量 `ASSERTER_INPUTS` | `tools/seal_run_evidence.py:795`（基线）；常量与读回路径见下 |
| 判据注册表在 `:4101` 附近 | 基线 `ASSERTIONS: dict[...]` 起于 `tools/assert_case_evidence.py:4036`、止于 `:4178`（卡面行号 `:4101` 落在表体内，位置成立） |

**读回路径不是猜的**：`ASSERTER_INPUTS` 声明在 `tools/assert_case_evidence.py:713`（注释就写着「a sealer that
wrote a name the reader did not know would not fail, it would read as "this run had none of that"」），
写方 `asserter_inputs_bytes()` 在 `:772`，读方 `read_sealed_material()` 在 `:941` 经 `_sealed_json` 取回，
并把 `username` 一并交回 `RunMaterial`。今天卷上 66 份 bundle 带 `asserter-inputs.json`，其中 **0** 份含本字段。

## 二、一处卡面矛盾：注册一条判据的最小面比卡面允许路径多一个文件

卡面「允许路径」只给 `tools/seal_run_evidence.py` + `tools/assert_case_evidence.py` + 一个新测试 + 一个记录，
但仓库自己有一道等式闸：`tests/unit/test_case_evidence_assertions.py:2177-2184`

```python
def test_the_registry_and_the_asserter_name_the_same_assertions() -> None:
    registered = {name for name, implementation in CHECKER.IMPLEMENTATIONS.items()
                  if implementation.target == CHECKER.RUNTIME_ASSERTER}
    assert registered == set(ASSERTER_MODULE.ASSERTIONS)
```

基线实测两侧恰为 `ASSERTIONS 72 / runtime-registered 72`，交集为空、差集为空。于是只往 `ASSERTIONS`
加一条必然把这道理所当然的等式打破，而补它的那一行在 **`tools/check_case_assertions.py`**（`_runtime(...)`
条目块，最后一条在 `:391-393`，dict 止于 `:766`）—— 不在本卡允许路径内，也不在允许改的测试内。

按卡面「发现前提与基线不符就停下来报，不要绕」执行：**没有**改 `check_case_assertions.py`，**没有**改
既有测试，也**没有**自造第二条闸绕开它。红读数（临时在 `ASSERTIONS` 加一条同名条目后单点跑该测试）：

```text
$ docker run --rm --entrypoint /bin/bash -v "$(cygpath -m .../minekin-wt-mc0):/src:ro" \
    -e PYTHONPATH=/src/src -e LD_LIBRARY_PATH=/opt/sqlite/lib -v /tmp/mc0-pytest-tmp:/tmp \
    minekin-runner:local -lc 'cd /src && python -m pytest \
    tests/unit/test_case_evidence_assertions.py::test_the_registry_and_the_asserter_name_the_same_assertions -q'
>       assert registered == set(ASSERTER_MODULE.ASSERTIONS)
E       AssertionError: assert {...} == {...}
E         Extra items in the right set:
E         'probe_target_is_this_run_s_kin'
tests/unit/test_case_evidence_assertions.py:2184: AssertionError
1 failed in 5.01s
```

该临时改动已 `cp` 还原，`git status` 复净（还原后基线复跑该测试通过）。**因此本卡的判据函数已落地并按名
拒绝/放行，但仍未进 `ASSERTIONS`**：函数在 `tools/assert_case_evidence.py:1664`，注册它需要主控把
`tools/check_case_assertions.py` 划进本卡（或 M-C1）的允许面，两行同时落地即可——

```python
# tools/assert_case_evidence.py:4254（`}` 之前）
    "the_probed_player_is_this_run_s_kin": the_probed_player_is_this_run_s_kin,
# tools/check_case_assertions.py:394（`_runtime` 条目块内）
    "the_probed_player_is_this_run_s_kin": _runtime("the_probed_player_is_this_run_s_kin"),
```

不注册不影响本卡要闭的那一半：载体（写、封、读回、判据、四类具名拒绝）已可从纯封存字节走到结论，
M-C1 注册时缺的只是那两行，而不是任何判据材料。

## 三、落地：一个 CLI 输入，一个已有文档里的字段，一条新判据

1. **sealer 输入**（`tools/seal_run_evidence.py`）：`--probed-player`（`action="append"`，可重复，默认空，
   `:929`）→ `seal(probed_players=...)`（`:581`）→ 同时交给两处：
   它自己拉起的判据子进程 `run_asserter(... probed_players=...)`（`:277`，逐名 `--probed-player`，`:337-338`），
   和写进 `asserter-inputs.json` 的那一份（`:805`）。走这条双投递是因为仓库已有的同一先例
   `--session-argv-json`：这些名字除这次封存之外不落任何磁盘文件，「没被告知」的判据会答
   `NOT_RECORDED`，而同一次封存的 bundle 却写着问的是谁 —— 同一 seal 出两个答案是 bundle 不可重判。
2. **字段形状**（不新建工件、不动 schema）：`asserter_inputs_bytes()`（`tools/assert_case_evidence.py:813`）
   在原有五键之上，**只在有名字可写时**追加 `"probed_players": [...]`，集合语义（`recorded_probed_players()`
   `:526` 去重 + 排序，空集读作 `None`，与 `recorded_argv()` `:512` 同一条「presence, not emptiness」规则）。
   读回 `_sealed_probed_players()`（`:796`）与 `_trace_argv`（`:754`）同规矩：不是名字列表 = 这份 bundle 没说过，
   而不是 = 它说了些读不懂的东西。于是 `RunMaterial.probed_players`（`:456`）只有两种值：`None`（没说）
   与非空名字元组（说了谁）。
3. **一条新判据**（`tools/assert_case_evidence.py:1664`），紧贴 `the_server_saw_the_kin_move` 之后，
   因为它就是那句话缺的后半句：具名三种拒绝 ——
   `PROBE_ATTRIBUTION_NOT_RECORDED` / `MORE_THAN_ONE_PLAYER_PROBED:<a,b>` /
   `PROBED_PLAYER_IS_NOT_THIS_RUN_S_KIN:<name>`；只有 `{本 run 的 username}` 这一种集合放行。
   缺字段既不读成通过，也不读成「什么都没探所以没事」。
4. **纯增量**：没有 case fixture 引用它（fixture 面禁改），既有 `mandatory`、case id、判据答案一字未动。

## 四、四组读数

### 1. 正对照：真封 bundle 改前/改后逐字节同判

同一容器、同一规范卷 `:ro`，两侧工具（基线 tools 树 vs 本分支 tools 树）各跑一遍
`rejudge_evidence.py`，取 `status / re_judged / disagreements` 整行对比：

```text
$ docker run --rm --entrypoint /bin/bash -v .../minekin-wt-mc0:/src:ro -v /d/Temp/mc0-base-tools:/base:ro \
    -v minekin-runner-data:/data:ro -v /d/Temp/mc0-verif:/verif -e PYTHONPATH=/src/src minekin-runner:local \
    -lc 'for side in base after; do TOOLS=/base 或 /src/tools;
         python $TOOLS/rejudge_evidence.py /data/kin/kin-01/run/evidence/<bundle> \
               --cases-dir /src/tests/fixtures/cases ...; done'
base CORE-060   ed2bbad7 {"disagreements": [], "re_judged": {..., "result": "PASS"}, "status": "agrees"}
base OFFLINE-010 61b4f025 {"disagreements": [], "re_judged": {..., "result": "PASS"}, "status": "agrees"}
base CORE-060   08f206bf {"disagreements": [], "re_judged": {..., "result": "FAIL"}, "status": "agrees"}
after CORE-060  ed2bbad7 / after OFFLINE-010 61b4f025 / after CORE-060 08f206bf —— 三行与 base 逐字符相同
base rows: 3 after rows: 3 identical: True
```

即：PASS 的一份仍 PASS（`CORE-060` `ed2bbad7…`、`OFFLINE-010` `61b4f025…`），FAIL 的一份仍按原两条
（`RELEASE_NOT_LOGGED`、`NEVER_MOVED:0.10`）FAIL（`08f206bf…`），三份的 `disagreements` 都仍是 `[]`。

**老 bundle 不会因缺字段转红，也不会因缺字段被读成绿**——把三份真实 bundle 直接喂给新判据：

```text
ed2bbad7051f4014956bcce86fc17443 username='Kin' probed_players=None -> PROBE_ATTRIBUTION_NOT_RECORDED
61b4f0253cc84e2183d8913f3ad77867 username='Kin' probed_players=None -> PROBE_ATTRIBUTION_NOT_RECORDED
08f206bfaed94e4f9a22aed82c1c24d6 username='Kin' probed_players=None -> PROBE_ATTRIBUTION_NOT_RECORDED
```

它们今天不红，是因为没有任何 case 声明这条判据（`evaluate()` 只跑 case 点名的那些）；一旦 M-C1 点名，
全卷 66 份带 `asserter-inputs.json` 的 bundle 一律具名拒绝，而不是被静默读成通过。

**端到端那一格也量了**（不提交，脚本在 lane 施工位）：同一份伪造 run 分别用基线工具与本分支工具封存，
比较封出的 `asserter-inputs.json`：

```text
ab606edaf4a56e3969708b8d7630282336e12176701cfbe6403ea62a204875b5  base/asserter-inputs.json
ab606edaf4a56e3969708b8d7630282336e12176701cfbe6403ea62a204875b5  after-unnamed/asserter-inputs.json
f331916733f48bbd5c39ad98dc44ef4f77a5b38b32242ce3e71cd46ba48dab84  after-named/asserter-inputs.json   # ["Kin","Kin2"]
```

不传 `--probed-player` 的一次封存与基线**逐字节相同**（严于「行为不变」），传了的两名版封出来后
`rejudge` 仍 `disagreements=[]`、新判据按名答 `MORE_THAN_ONE_PLAYER_PROBED:Kin,Kin2`。

### 2. 新判据非空洞：scratch 目录合成四份文档（`/data` 之外，规范卷未参与）

```text
$ docker run --rm --entrypoint /bin/bash -v .../minekin-wt-mc0:/src:ro -v /d/Temp/mc0-scratch:/scratch \
    -e PYTHONPATH=/src/src minekin-runner:local -lc 'cd /src && python /scratch/probe_cases.py'
(a) probed == {username}               probed_players=('Kin',)           -> None
(b) probed == {username, Kin2}         probed_players=('Kin', 'Kin2')    -> MORE_THAN_ONE_PLAYER_PROBED:Kin,Kin2
(c) probed == {Kin2}, username Kin     probed_players=('Kin2',)          -> PROBED_PLAYER_IS_NOT_THIS_RUN_S_KIN:Kin2
(d) field absent                       probed_players=None               -> PROBE_ATTRIBUTION_NOT_RECORDED
```

四条互不相同 ⇒ 判据不是恒真也不是恒假：(a) 只有在名字恰为本 run 的 Kin 时才绿，把 (a) 的名字换成 (c) 即红，
这就是反转。(d) 是缺字段；另有第五组把「写了键但没写名字」也钉住 —— `[]`、`["Kin", 7]`、`"Kin"`（字符串不是列表）、
`{"a":1}`、`null` 五种形状一律 `PROBE_ATTRIBUTION_NOT_RECORDED`（`tests/unit/test_probe_target_carrier.py`）。

### 3. 门载荷一字未动（本卡不注册 case）

`gate_payload_sha256` 不是仓库字段，是 M 侧读法：`report_promotion.py --data-root /data` 的
`work_packages` + `overall` 子集按 `sort_keys` 序列化取 sha256。规范卷 `:ro`。

```text
PRE  （基线 5d0cd2a 工作树，改动前）: report_rc=1
     gate_payload_sha256 cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6
     overall_blocks ['REQUIRED_CASE_NOT_REGISTERED']
     W30 promotable=False blocks ['NO_MANDATORY_CASES','REQUIRED_CASE_NOT_REGISTERED']
     p0-core promotable=False  |  W30.absent ['OFFLINE-060','OFFLINE-080']
POST （本分支改动后，同一命令、同一卷）: report_rc=1
     gate_payload_sha256 cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6
     overall_blocks ['REQUIRED_CASE_NOT_REGISTERED']
     W30 promotable=False  |  p0-core promotable=False  |  W30.absent ['OFFLINE-060','OFFLINE-080']
```

PRE == POST == 卡面给定值，`report_rc=1`，`W30` 与 `p0-core` 仍未晋级，absent 名单一字未差。

### 4. 套件（受控镜像内）

**环境注（否则误判 35 红）**：镜像系统 sqlite 是 3.45.1，本仓 `connect_writer` 要求 3.51.3+，
必须 `-e LD_LIBRARY_PATH=/opt/sqlite/lib`（镜像自带 3.53.4）。缺它时基线也照样红 35 条 + 31 errors，
不是完整性故障。补上后：

```text
$ docker run --rm ... -e PYTHONPATH=/src/src -e LD_LIBRARY_PATH=/opt/sqlite/lib minekin-runner:local \
    -lc 'cd /src && python -m pytest tests/unit/test_probe_target_carrier.py \
         tests/unit/test_case_evidence_assertions.py tests/unit/test_seal_run_evidence.py \
         tests/unit/test_seal_repo_case.py tests/unit/test_run_repo_case.py \
         tests/unit/test_report_promotion.py tests/unit/test_report_soak.py \
         tests/contract/test_case_assertions.py tests/contract/test_case_coverage.py -q'
1 failed, 663 passed in 1071.16s (0:17:51)
```

唯一那条红 = `tests/unit/test_run_repo_case.py::test_the_command_exits_by_what_it_found`，已在**基线检出树**
（`git archive 5d0cd2a` 全量副本，同样 `LD_LIBRARY_PATH`）单点复跑同样红：

```text
基线树: FAILED tests/unit/test_run_repo_case.py::test_the_command_exits_by_what_it_found  → 1 failed, 16 passed in 13.61s
```

其因与既往记录一致：镜像内 `find_spec("pytest") is None`，`run_repo_case.py` 要跑仓库自检类检查必然
得到假 FAIL —— 环境缺件，非本卡改动。另跑一遍证据面相邻套件：

```text
$ ... python -m pytest tests/unit/test_evidence_bundle.py tests/unit/test_evidence_verify.py \
      tests/contract/test_evidence_layout.py tests/contract/test_replay_evidence.py \
      tests/contract/test_fixture_consumers.py tests/unit/test_case_registry.py \
      tests/unit/test_probe_target_carrier.py -q
185 passed in 63.11s (0:01:03)
```

宿主面 CI 等价闸（仓库既有口径）：`uv run --frozen ruff check` / `ruff format --check` 三个改动文件全绿，
`uv run --frozen pyright`（strict）三个改动文件 `0 errors`。新测试自带 10 条。

## 五、本卡未做 / 未测（具名）

- **判据未进 `ASSERTIONS`**：见第二节矛盾与两行待授权。本卡的载体半边已完成并可被 M-C1 直接引用。
- **runner 半边未做**（属后续卡）：`test-orchestrator/runner/domain.sh` 一字未动；它今天已有
  `probe_args=(--probe-player "${probe:-${player}}" ...)`（`domain.sh:482`）与
  `run_controlled_server.py:861-862`，但**没有任何一条路径把这个名字交给 `seal_run_evidence.py`**。
  因此卷上仍不会有第二份 bundle 带 `probed_players`：字段只可能出现在下一次显式传参的封存里。
- **没有跑过任何 LAN 加入者 run**，没有新封一份证据到规范卷（规范卷全程 `:ro`），没有注册 case，
  没有动 registry / 门禁 / `mandatory`。
- **两个真玩家同服的归属反例未测**：`MORE_THAN_ONE_PLAYER_PROBED` 至今只由合成文档与伪造封存触发；
  「一次真 run 真的探了 `Kin` 与 `Kin2`」这件事需要 M-C1 之后的真跑卡。
- 全量 `tests/` 未复跑（17 分钟只覆盖 9 个 tools 相关套件）；`verify_tested_provenance.py` 未跑（无 built
  bridge jar 时报 `BRIDGE_JAR_MISSING`，缺产物非完整性故障）。
- `--probed-player` 的名字合法性**不另设校验**：`run_controlled_server.py:489-505` 已在拼命令前用
  `is_valid_username` 具名拒止非法玩家名，本卡只记「操作者说服务器被问了谁」，不复制那道判定。
