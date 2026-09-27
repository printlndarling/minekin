# H1h `V1201-LAN-JOINER-BOUNDED-CONTROL-DRIVER-001` — 受控 LAN 加入者的显式限幅控制驱动（runner 侧）

- **卡片**：`docs/v1201-lan-control-next-2026-09-27.md` §2「### H1h」，逐字取其允许面 / 实现边界 / 红绿验收；顺序与后续依赖取同文 §2 的 H1h→V5→M-C1→E7→M-G1 队列与 §3 的停线规则。
- **Lane / 分支**：`codex/minekin-lan-joiner-bounded-control`（H lane），基线 `24ac6e0ee69cb1926fb4ce5c8439834caaa37fb3`（＝当时的 `main`，未 rebase、未 merge、未推 `main`）。
- **被改字节身份**：
  - 改前（基线）：`test-orchestrator/runner/domain.sh` = `ff69c87994f15be37a07090c664c60fdbf8cd620689bfd07fe3a837431e982c4`
  - 改后（本卡交付字节）：`test-orchestrator/runner/domain.sh` = `baad190aaa5ee1695a88b52e98cc270c8e1a4bc878a0bcd2d0c27f94b74ff6f3`
  - 本文引用的每一条活体读数都由 `.tmp/h1h_measure.py` 打印，该脚本首两行输出即上面两个 sha256，
    所以任何一条读数都能被独立判断是在「基线字节」还是「本卡字节」上量到的。
- **本卡状态**：**DELIVERED**。成功上界＝驱动**能**在被拒之外把一次有界 look 与一段 ≤2 秒 forward 组到第二客户端的
  `session start` 上，且越界/无加入者/`--hold-at join` 三种情形**具名拒止、零下发**；
  **不宣称任何真实第二客户端转过或走过**，不封证，不写规范卷，不注册 case。

---

## 1. 这条驱动是什么

`domain.sh` 新增一段默认关闭的驱动（`test-orchestrator/runner/domain.sh:415-640`，其中被契约测试与本记录
共同抽取的区间是 `:464`（`# --- joiner-control-driver begin`）到 `:640`（`# --- joiner-control wiring end ---`））：
它读取三个 `MINEKIN_DOMAIN_JOIN_*` 名字，在**任何 JVM 启动之前**把请求限定成

* 至多一次 look：`--look-yaw-degrees`、`--look-pitch-degrees`（各自至多出现一次）；
* 至多一段前进：`--hold-forward-seconds`（至多出现一次）。

组好的数组 `joiner_control_args` 只进入一个地方：`build_joiner_session_argv()` 折出的
`joiner_session_argv`，而该数组在整个文件里只被使用两次——一次是本卡的读回打印块，一次是
`join_the_published_world()` 里那条后台化的加入者 `session start`（原先手写的三行字面命令被换成该数组）。
宿主会话那一行仍是 run 自己的参数 `"$@"`，本卡没有为它构造任何东西。

它**不**新增产品面：`session start` 本来就接受这三个旗标（`--hold-forward-seconds` 需要的
`--server-profile` 早已在那一行上），它驱动的 lease 本来就是加入者自己的
（launch 行已设 `MINEKIN_KIN_ID="${joiner}"`）；准入、寻址、认证、Bridge、封存 schema 一律未动。
`release` 不是旗标——它是 hold 的 lease 到期时产品本来的动作，因此「hold 长度的上界」就是「释放的上界」。

### 1.1 本卡引入的 env 名字（精确四个）

| 名字 | 语义 | 允许范围（本卡构造值） | 越界行为 |
|---|---|---|---|
| `MINEKIN_DOMAIN_JOIN_LOOK_YAW` | 加入者一次 yaw 转向（度，带符号） | 非零且 \|v\| ≤ 45 | 具名拒止，不夹取 |
| `MINEKIN_DOMAIN_JOIN_LOOK_PITCH` | 加入者一次 pitch 俯仰（度，带符号） | 非零且 \|v\| ≤ 30 | 具名拒止，不夹取 |
| `MINEKIN_DOMAIN_JOIN_HOLD_FORWARD_SECONDS` | 加入者一段前进保持（秒） | > 0 且 ≤ 2 | 具名拒止，不夹取 |
| `MINEKIN_DOMAIN_JOIN_CONTROL_PRINT` | 打印加入者将被启动的那一行后退出 0 | 空 / `0` ＝未请求 | 拒止先于打印；无加入者或无 profile 时具名拒止 |

四个名字全部**默认关闭**：未设置＝零控制旗标；设置但为空串＝与未设置同义（读数 A3 证明）。

### 1.2 限幅是构造，不是测量

45 / 30 / 2 秒是**本卡为「一次被审的有界动作」所选的宽度**，不是任何产品常量的读数，也不是活体测得的能力边界：
yaw 45° 大到足以让宿主服务端的 `Rotation` 显示航向确实变了；pitch 30° 停在原版会照实上报的区间内；
2 秒是本 harness 的行走等待在释放后仍能拿到两次稳定读数的最长保持。
卡片规定 V5 才做活体读数，E7 才谈封证；因此这三个数在此只有「构造 + 被契约测试钉住字面量」这一种身份
（`JOINER_CONTROL_BOUNDS` 与 `domain.sh:471-473` 逐字对齐，改一个数即红）。

## 2. 复现命令（所有读数共用）

镜像解释器是 `python`（无 `python3`）；规范卷 `minekin-runner-data` **全程未挂载**（连 `:ro` 都不需要）。
`.tmp/` 以可写方式另挂一处，仅用于放派生脚本与变异副本；重定向一律在宿主侧完成。

```bash
export MSYS_NO_PATHCONV=1
WT=C:/Users/darling/Documents/agent_work/minekin-wt-h1h
# 基线字节的原始 dump（宿主侧，仓库外产物）
git -C "$WT" show 24ac6e0:test-orchestrator/runner/domain.sh > "$WT/.tmp/base-domain.sh"

docker run --rm --entrypoint /bin/bash \
  -v "$WT:/src:ro" -v "$WT/.tmp:/out" -e PYTHONPATH=/src/src \
  minekin-runner:local -lc \
  'cd /src && python /src/.tmp/h1h_measure.py'      # 37 项读数，全部字面输出
```

驱动器不转录任何一行命令行：加入者的 argv 由 `domain.sh` **自己的**读回面打印，
基线的 argv 由 `git show 24ac6e0:…` 的那几行原文重新交给 `bash -c '… "$@"'`（与真启动同一道接缝）切词。

## 3. 四项验收读数（逐字输出，取自 `.tmp/h1h-measure-2026-09-27.log`）

### 读数 A — 默认关闭：加入者那一行与基线 `24ac6e0` **逐字节相同**

```
PASS  A1 1.20.1 profile, no control env == base 24ac6e0
      | rc=0
      | base 24ac6e0 line, split by bash: python -m minekin_core session start --profile /src/tests/fixtures/launcher/1.20.1.json --server-profile /tmp/domain-join-profile.json
      | shipped line, printed by domain.sh: python -m minekin_core session start --profile /src/tests/fixtures/launcher/1.20.1.json --server-profile /tmp/domain-join-profile.json
      | byte-for-byte: EQUAL (shipped 134 bytes, base 134 bytes)
PASS  A2 1.21.4 (v1 frozen route), no control env == base 24ac6e0
      | byte-for-byte: EQUAL (shipped 134 bytes, base 134 bytes)
PASS  A3 control names delivered but empty == base 24ac6e0
      | byte-for-byte: EQUAL (shipped 134 bytes, base 134 bytes)
PASS  A4 CONTROL_PRINT=0 means 'not asked': the run falls through to the next guard
      | rc=2 (2 = the pre-existing host-side joiner guard, below this card's block)
      | stderr: domain: no server profile; this run joins no world
      | domain: a joiner needs a world to join; set MINEKIN_DOMAIN_OPEN_LAN=1
```

A2 就是 v1 的 1.21.4 冻结行为：同一条加入者行，逐字节未变。
A4 说明「`0` 与未设置同义」不是靠不打印来主张的：该 run 越过了本卡的读回块，继续走到**它下面**那条早已有之的
加入者前置守卫才停下（因此本读数全程也不会起任何 JVM）。

### 读数 B — 越界一律**具名**拒止，且零下发

12 条越界请求（含 0、非数字、带 shell 元字符者）全部：`rc=2`、命令行里没有旗标、消息里同时点名旋钮与上界、
并且带原句「Refused, never clamped.」。逐字样例：

```
PASS  B1 MINEKIN_DOMAIN_JOIN_LOOK_YAW=90
      | env MINEKIN_DOMAIN_JOIN_LOOK_YAW='90'  ->  rc=2
      | stderr: domain: MINEKIN_DOMAIN_JOIN_LOOK_YAW=90 is outside the bound this driver carries for it: one look of at most 45 degrees in either direction, and never zero. Refused, never clamped.
PASS  B1 MINEKIN_DOMAIN_JOIN_LOOK_PITCH=60
      | stderr: domain: MINEKIN_DOMAIN_JOIN_LOOK_PITCH=60 is outside the bound this driver carries for it: one look of at most 30 degrees in either direction, and never zero. Refused, never clamped.
PASS  B1 MINEKIN_DOMAIN_JOIN_HOLD_FORWARD_SECONDS=10
      | stderr: domain: MINEKIN_DOMAIN_JOIN_HOLD_FORWARD_SECONDS=10 is outside the bound this driver carries for it: one forward hold of more than 0 and at most 2 seconds. Refused, never clamped.
PASS  B1 MINEKIN_DOMAIN_JOIN_LOOK_YAW=both          （非数字在算术比较之前按形状拒掉）
PASS  B1 MINEKIN_DOMAIN_JOIN_LOOK_YAW=0 / PITCH=0 / FORWARD=0 / FORWARD=-1   （零与负保持具名拒止）
PASS  B1 MINEKIN_DOMAIN_JOIN_HOLD_FORWARD_SECONDS=1; touch /tmp/pwned
PASS  B2 the shell-metacharacter ask created no file
      | /tmp/pwned exists: False
PASS  B3 mixed ask (in-range yaw + out-of-range forward) refused on the bad knob alone
      | rc=2  line: []
```

判定不是「有 stderr 输出」：`judge_refusal` 同时要求 `rc!=0`、组出的 argv 为空、消息含旋钮名、消息含该旋钮自己的
上界数字、消息含「never clamped」。B3 额外证明混合请求不会把好的那半先发出去。

### 读数 C — 没有加入者却武装控制：具名拒止

```
PASS  C1 arm MINEKIN_DOMAIN_JOIN_LOOK_YAW=10 with MINEKIN_DOMAIN_JOIN unset  ->  rc=2
      | stderr: domain: the ask (MINEKIN_DOMAIN_JOIN_LOOK_YAW) needs a joining client to drive and this run has none (MINEKIN_DOMAIN_JOIN is unset); refused rather than carried as a knob that does nothing
PASS  C2 all three armed with no joiner still names all three
      | stderr: domain: the ask (MINEKIN_DOMAIN_JOIN_LOOK_YAW, MINEKIN_DOMAIN_JOIN_LOOK_PITCH, MINEKIN_DOMAIN_JOIN_HOLD_FORWARD_SECONDS) needs a joining client to drive …
```

同一驱动的另一半（`--hold-at join`，phase 由 run 自己的参数读入）也具名拒止：

```
PASS  E1 shipped bytes refuse a joining hold asked at the join, by name
      | rc=2
      | stderr: domain: the ask (MINEKIN_DOMAIN_JOIN_HOLD_FORWARD_SECONDS) needs a playable moment for the joining client, and this run asks for its hold at the join (--hold-at join); there is none to drive it from, so the ask is refused
```

### 读数 D — 组出的数组只接进一处，且绝不接到宿主那一行

```
PASS  D1 the composed array reaches exactly the joiner's backgrounded start
      | `python -m minekin_core session start` literal in the file: 1
      | `"${joiner_control_args[@]}"` uses: 1
      | `"${joiner_session_argv[@]}"` uses: 2
      | joining client's launch line ends at: >/tmp/domain-join-session.json 2>/tmp/domain-join-session.err &
      | hosting session's launch line: minekin-session-supervisor \ "${client_env[@]}" python -m minekin_core "$@" "${lan_args[@]}" \ >/tmp/domain-session.json 2>/tmp/do
      | bound literal `joiner_control_max_yaw=45`: 1
      | bound literal `joiner_control_max_pitch=30`: 1
      | bound literal `joiner_control_max_forward_seconds=2`: 1
```

### 正对照 P — 范围内的一次请求确实落到加入者那一行

```
PASS  P1 a plain in-range ask reaches the joining client's line
      | rc=0
      | line: python -m minekin_core session start --profile /src/tests/fixtures/launcher/1.20.1.json --server-profile /tmp/domain-join-profile.json --look-yaw-degrees 22.5 --look-pitch-degrees -10 --hold-forward-seconds 1.5
      | yaw words: 1 pitch: 1 forward: 1
```

### 边界 F — 主控保留的 auto+joiner 拒止一字未改、并且先回答

```
PASS  F1 auto-bundle + joiner + armed control refused by the untouched controller block
      | rc=2
      | stderr: domain: an auto-bundle run cannot also ask for a joining second client; the joiner is started from a named bundle profile
PASS  F2 that block's bytes, base 24ac6e0 vs shipped
      | base sha256 09543aec52b270204e2e72131663231a5e55bd07ad3a373f48558f8799a72229
      | shipped sha256 09543aec52b270204e2e72131663231a5e55bd07ad3a373f48558f8799a72229
```

即：`--auto-bundle` × joiner 的整段（`domain.sh` 基线 :400-412 那个 `if` 块）在本卡字节上 sha256 与基线相同，
且它在文件里的位置早于本卡任何一次 `compose_joiner_control_args`——F1 里本卡自己的拒止没有抢在它前面。
`config.FORWARDED_VARIABLES`（`run.sh`）本卡未碰，见 §6。

37 项读数汇总：`total checks: 37  passed: 37  failed: 0`，脚本 `measure_rc=0`，
且 `container /data created during the run: False`（零证据写）。

## 4. 红绿对与非空转反证

**红绿对**（卡片验收第一条）：把本卡 8 个新契约测试（27 个参数化用例）在同worktree、同一镜像下分别跑在
基线字节与本卡字节上——基线用只读 bind 覆盖 `test-orchestrator/runner/domain.sh`，其余字节不变：

```
### base (domain.sh = ff69c879…)   27 failed, 37 deselected in 5.06s
### shipped (domain.sh = baad190a…) 27 passed, 37 deselected in 2.03s
```

原始红读数的逐条清单在 `.tmp/h1h-red-on-base-2026-09-27.log`（`ValueError: substring not found` 等，
即旧字节上根本没有这段驱动）。

**非空转反证**：同一个驱动器、同一套判据，跑在 `.tmp/mutants/` 下**故意改坏**的副本上（变异只落在派生副本，
不进提交）。每条都要求「变异被具名抓到」，否则该条判 FAIL：

| 变异 | 播种方式 | 抓它的判据 | 实测 |
|---|---|---|---|
| RV1 夹取 | 把 yaw 越界拒止整段换成 `yaw="${joiner_control_max_yaw}"` | B | `MINEKIN_DOMAIN_JOIN_LOOK_YAW=90` 在变异副本上 `rc=0` 且下发 `--look-yaw-degrees 45`（没人请求过的 45°）→ 判据点名「accepted an out-of-range ask」「control flag on the joining client's line」 |
| RV2 默认打开 | 删掉「三者皆空即返回」并把 yaw 追加改成无条件 | A | 未武装的 run 组出 `… --look-yaw-degrees `（空值旗标）→ 判据点名「a control flag reached the line with nothing asked」 |
| RV3 只报不停 | 把 pitch 拒止消息后的 `exit 2` 换成 `:` | B | 消息仍打印，但 `rc=0` 且 `--look-yaw-degrees`/pitch 旗标下发 → 只有 rc 的测试会当成通过，本判据不会 |
| RV4 放宽上界 | `joiner_control_max_forward_seconds=2` → `=30` | D + B | D 点名该字面量不再是单一构造值；B 在同一副本上把 `FORWARD=10` 判为「accepted an out-of-range ask at rc=0」（RV4b） |
| RV5 去掉「必须有加入者」守卫 | `exit 2` → `:`，**只用驱动区间单独跑**（整文件通道看不到：读回块自带第二道 joiner 守卫，会假绿） | C | 无加入者的 run 在副本上 `rc=0` 并组出 `… --look-yaw-degrees 10` → 点名「composed a joining line for a run with no joining client」；同判据先在本卡字节上确认仍拒（RV5a） |
| RV6 接到宿主行 | 在 `minekin-session-supervisor` 那一行尾部追加 `"${joiner_session_argv[@]}"` | D | 点名「the composed joiner array reached the hosting session's line」＋数组使用数由 2 变 3 |
| RV7 数组接两处 | 把 `"${joiner_control_args[@]}"` 写两遍 | D | 点名「the bounded ask reaches more than one command line」 |
| RV8 去掉 phase 守卫 | `--hold-at join` 拒止的 `exit 2` → `:` | 整文件读回面 | 副本上 `rc=0` 且 `--hold-forward-seconds 1` 下发（本该零下发） |

RV1/RV3/RV4b/RV5/RV8 是「把通过改成失败」的**行为**反证（下发或 rc 变了），RV6/RV7 是「多接一处」的形状反证；
RV5 特意为它另开一条单独跑驱动区间的通道，并把这条通道的必要性写进上面的表——否则读者会以为整文件读回面
足以覆盖所有变异。

## 5. 门禁表

| 门禁 | 命令 | 结果 |
|---|---|---|
| `bash -n` | `bash -n test-orchestrator/runner/domain.sh` | rc=0 |
| runner 契约 | `python -m pytest -q tests/contract/test_runner_scripts.py` | **64 passed**（38 个 `def test_`，其中 8 个本卡新增；基线为 30 个），rc=0 |
| 红绿对 | 同上 `-k` 选本卡 27 例 | 基线字节 27 failed / 本卡字节 27 passed |
| 原始读数脚本 | `python /src/.tmp/h1h_measure.py` | 37 项全 PASS，`measure_rc=0` |
| ruff | `ruff check tests/contract/test_runner_scripts.py` | All checks passed!（`.tmp/h1h_measure.py` 不入库，其风格不计） |
| 全量本地测试 | 宿主 Git Bash，`uv run python -m pytest -q tests/` | **2631 passed, 3 skipped in 563.60s**，rc=0（见 §5.1） |

镜像解释器为 `python`；容器内跑 `tests/unit` 全量时需要 `LD_LIBRARY_PATH=/opt/sqlite/lib`
（否则镜像链到系统 SQLite 3.45.1，`tests/unit/test_case_evidence_assertions.py` 会有 13 条
`SQLiteCompatibilityError` 的**假红**；该口径由主控当日复量：带该变量 487 passed）。

### 5.1 全量本地测试：容器不可整跑，宿主全绿

`tests/` 在本镜像里**不能整目录一次跑完**：`tests/contract/test_fixture_boundaries.py`、
`tests/contract/test_server_profile_schema.py`、`tests/unit/test_fault_injection.py` 三个模块在收集期即
`ModuleNotFoundError: No module named 'jsonschema'`（镜像缺依赖，与本卡两个路径无关；这三条在本卡
改前/改后同现）。绕开这三条的容器内整目录运行在本窗口内超过 13 分钟未结束（输出被管道缓冲，无法判断进度），
已随窗口结束终止。全量绿是在**宿主**上量到的（宿主 uv 环境有 jsonschema）：

```
2631 passed, 3 skipped in 563.60s (0:09:23)
SKIPPED tests\unit\test_orphans.py:686         this platform cannot answer the question, so it can never say gone
SKIPPED tests\unit\test_silent_listener.py:123  a Windows terminate is not a signal
SKIPPED tests\unit\test_tested_provenance.py:354 bridge-1201/build/libs/minekin-bridge-1201-0.0.0.jar is not built on this host
```

三条 skip 都是平台/构建产物条件，与本卡两个路径无关；原始日志 `.tmp/h1h-full-suite-host.log`（不入库）。
本卡**没有**在同一镜像内量到全量绿，也没有在容器里复跑这三条 skip。

## 6. 本卡不证明什么

1. **没有任何真实第二客户端转过或走过。** 全部读数只到「组出的命令行」与「拒止确实发生且具名」这一层；
   没有起 JVM，没有 Bridge 握手，没有 `PLAYABLE` 后的实际输入下发，没有宿主服务端 oracle 的 yaw/水平坐标读数。
   活体读数属 **V5 `V1201-LAN-JOINER-LOCAL-CONTROL-READOUT-001`**，本卡是它的前置而不是它的一部分。
2. **没有封证、没有 attempt/bundle、规范卷零写。** `minekin-runner-data` 全程未挂载；
   每次读数后 `/data` 在容器内仍不存在（§3 末行）。任何一条读数都不得被引为 sealed evidence。
3. **没有注册 case、没有改判据/fixture/registry/门禁/schema。** `tests/fixtures/cases/**`、`tools/**`、
   `src/**` 零改动；`--hold-at` 语义与 `config.FORWARDED_VARIABLES` 未动。
4. **`run.sh` 还不转发这四个新名字，所以经 `run.sh domain` 的真跑目前无法武装本驱动。**
   这是本卡的**发现**而不是本卡的产出：包装器在允许面之外，故只在契约里把它钉成一个精确集合
   （`JOINER_CONTROL_KNOBS`，四元素；出现第五个未转发名、或这四个真出现在 `run.sh` 里，都会在那里变红）。
   V5 若要用 `run.sh` 起活体 run，需要主控先批一张把四个名字加进 `config.FORWARDED_VARIABLES` 的范围修订卡
   （或由 V5 直接调 `domain.sh`）。
5. **上限是构造值**（§1.2）：45°/30°/2s 不是产品常量，也不是测得的能力边界；把它们当作测量结果引用即为误述。
6. 未测：加入者旧代/错误 Kin/未 `PLAYABLE` 时的产品侧拒止（那是产品自己的 lease/代次判断，本卡只保证
   runner 不下发越界请求）；多加入者、并发、任何非 loopback 或公网目标、任何在线认证，一律未去。

## 7. 交付与回读

- 允许面核对（交付前 `git status --porcelain`）：仅
  `test-orchestrator/runner/domain.sh`、`tests/contract/test_runner_scripts.py` 两份已改，
  加本文件一份新增。原始测量脚本、其日志与 `.tmp/mutants/` 变异副本全部留在 `.tmp/`（`.gitignore:10`），**不入库**。
- 提交拆两笔：第一笔 `domain.sh` + 契约测试（驱动与其判据同批），第二笔本记录。
- 分支只推 `codex/minekin-lan-joiner-bounded-control`；不合 `main`、不 merge，集成由主控执行。
