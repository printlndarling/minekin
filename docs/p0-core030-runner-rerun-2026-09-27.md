# CORE-030 runner 修复的真实通道复跑（E-RR）：③ 已证，封证两刀如实落 FAIL

日期：2026-09-27（宿主本地）；卷上两份新 bundle 的宿主 `started_at` 为 `2026-09-26T17:17:12Z` 与
`2026-09-26T17:29:15Z`（bundle 字节本身不记时钟，先后秩序由台账 `sequence + supersedes_run_id` 佐证）。
分支 `codex/minekin-evidence`，起点 `626a454`（E-CO），`git fetch origin` 后 `git merge origin/main`
为**干净 fast-forward，无冲突**（E 分支已是主干祖先，M 已把 E-CO 整条合入），合并后 HEAD =
`be4e79b98baafea85f1230de587fc5b7b8b15a89`（含 H1b `d09e9b2`、H1 自动路径 `be4e79b`、读者面 `0ab208c`）。
工作树：`C:\Users\darling\Documents\agent_work\minekin-wt-evidence`。日志：本工作树 `.tmp/e-rr-*.log`（不入版本库）。

## 1. 目的与一句话结论

第四刀的 ③ 缺陷（`domain.sh:657` 对全新 joiner Kin 的静默 `rc=2`）在主干由 `1dc6101`/`d09e9b2` 修复，
此后 trunk 记录里 ③ 一直是「代码 + 单元/契约测试」。本卡补的是真实通道那一半。结论分两截，都不粉饰：

1. **③ 的修复在真实 `domain.sh` 通道里成立**：全新 joiner Kin（无 `run/session/`）走真 runner，
   基线读不再杀run —— 现路径由 preparation `mkdir -p`（`domain.sh:699`）先把目录备好并继续；
   去掉那一行 `mkdir` 的真实脚本副本则打出**具名一行读数并继续**（§2 探针 B）。
   反转（§2 探针 D）：修复前字节（`d09e9b2^1`）在同一形状下仍是 3 行日志 + `rc=2`、0 字节说明。
2. **封证没有拿到 PASS，两刀如实落卷**：两次真跑都走到封存并各封一份 FAIL bundle
   （seq 3 `787168062c4047b48e32620984d6d814`、seq 4 `6286f1e5a4a6403b9cfb3b564f2b3118`，
   后一份 supersedes 前一份），拒止逐字是第四刀 FAIL 同款
   `NO_CONNECTION_WAS_DIALLED` / `THE_CLIENT_NEVER_DIALLED_A_PORT`。
   阻断者不是 ③，而是加入者客户端的 GLFW `[0x1000E]`（第四刀偏差 B 家族）——
   但本卡把它从「1/3 偶发、不可重现」量成了「joiner 4/4、宿主 0/6、跨新旧两镜像都崩」：
   **⑤ 的「不再量到才开诊断卡」前提今天被推翻了**（§5）。

## 2. 探针（全部真 `domain.sh`，无手写桩；卷上只追加，未改写任何旧字节）

镜像 `minekin-runner:local`（`b67a4d917306`），配方同 E-CO §3；探针都不设 `MINEKIN_DOMAIN_CASE`（不封存）。

| 记号 | 命令形状（原文见对应日志） | 读数 |
| --- | --- | --- |
| A 现路径全新 joiner | 未改动 `run.sh domain` + 全新 `kin-e-rr-seal`（见 §3 第一刀）| joiner prep 成功（`was created as Kin2`→`world is published on 25570`），基线读通过（目录已由 `:699` 预建），run 继续到封存 |
| B 具名分支 | `.tmp/domain-fixed-noprep.sh`（当前 `domain.sh` 逐字节副本仅删 `:699` 那行 `mkdir -p …/run/session`）+ 全新 `kin-e-rr-branch` | 第 4 行逐字：`domain: the joining Kin kin-e-rr-branch has no session directory yet at /data/kin/kin-e-rr-branch/run/session; the join baseline is empty`，随后继续起加入者客户端（`.tmp/e-rr-02-branch-probe.log`，run 完走 rc=0）|
| C 正对照 | 未改动 `run.sh domain` + `kin-e-rr-branch`（此时 `run/session/` 已有 2 个会话目录）| 无具名行（走 `if` 分支，`ls` 基线成立），run 继续（`.tmp/e-rr-04-positive-control.log`）|
| D 反转 | `.tmp/domain-prefix-d09e9b2.sh`（`d09e9b2^1` 的修复前字节，其 preparation 只有 `mkdir -p …/run`）+ 全新 `kin-e-rr-rev` | 恰好复现第四刀第一次的形状：3 行日志后 run 死掉，`rc=2`，没有任何一行说目录不存在（`.tmp/e-rr-03-prefix-reversal.log`）；该 Kin 0 个会话、0 份 crash —— 死在起加入者之前 |

一个必须如实说的口径细节：卡面说的「`ea5423e^`-era 修复前字节」实际**已含修复**
（`d09e9b2` 早于 `ea5423e`，`git merge-base --is-ancestor` 量到），所以反转用的是 `d09e9b2^1` 的字节。

## 3. 两次真跑封证（当前构建 `be4e79b` 工作树，`launch_plan_digest bcc0c10d…`、`bridge_digest 0ee2070b…`、1.21.4，与四刀同一份构建）

```bash
cd /c/Users/darling/Documents/agent_work/minekin-wt-evidence
export MSYS_NO_PATHCONV=1
MINEKIN_KIN_ID=kin-01 MINEKIN_DOMAIN_CASE=CORE-030 MINEKIN_DOMAIN_CASE_ON=joiner \
MINEKIN_DOMAIN_JOIN=kin-e-rr-seal MINEKIN_DOMAIN_OPEN_LAN=1 MINEKIN_DOMAIN_LAN_PORT=25570 \
MINEKIN_DOMAIN_SECONDS=420 \
  bash test-orchestrator/runner/run.sh domain session start \
    --profile tests/fixtures/runtime-input/bundle-p0-core-1.21.4.json \
    --world-save tests/fixtures/saves/kinworld --world-name kinworld
#   → .tmp/e-rr-05-seal-run1.log（rc=1，seq 3 FAIL）；第二刀一字未改，只换 MINEKIN_DOMAIN_JOIN=kin-e-rr-seal2
#   → .tmp/e-rr-05-seal-run2.log（rc=1，seq 4 FAIL，supersedes seq 3）
```

两刀的 bundle 事实（`/data/kin/kin-e-rr-seal{,2}/run/evidence/<run-id>`，manifest 原文在
`.tmp/e-rr-09/10-bundle-facts*.log`）：10 件 artifact；`case_version 994d749585150ce2…`（判据未动）；
`environment.renderer_display` 实测 `llvmpipe (LLVM 20.1.2, 256 bits)`（与第四刀 PASS/FAIL 两份逐字同族）；
宿主半侧全好：`lan_publication {LAN_OPENED, 25570}`、`world_snapshot.settings_digest 3bdd4aff…`
逐字节等于 `core-030.json` 的 `level.dat` pin；加入者半侧：`latest.log` 3825 字节止于 `Setting user: Kin2`，
`crash-reports/` 各 1 份 7210 字节的 `[0x1000E] Failed to detect any supported platform`，
run document `outcome HANDSHAKE_TIMEOUT`。判据失败两条具名（§1）。

## 4. 四读（对本卡封的两份，全部 `cmd >/dev/null 2>&1; rc=$?` 式记码；原文 `.tmp/e-rr-07-readout.log`、`e-rr-08-report-after.log`）

1. **verdict**（run 日志末段）：两刀都是 `the case verdict is FAIL` + `did not hold for this run`，
   封存自报 `"attempt_sequence": 3` / `4`、`supersedes` 各指前一份。
2. **`python -m minekin_core evidence verify <run-id>`**（只读挂载）：两份都 `rc=0`、
   `verified true / sealed true / result FAIL / artifacts 10 / violations []` —— 验封查密封完整性，不是输赢。
3. **`tools/report_promotion.py --data-root /data`**：`report_rc=1`（= 不晋级，非读坏）。
   底色 `attempts 69→71 / bundles 105→107 / from_another_build 61→61`，
   `unverified/unsealed/unreadable/sealed_without_bundle` 全 `[]`。
   `CORE-030` 六行：seq1 FAIL、seq2 PASS（第四刀，字节原封、行在）、seq3 FAIL、seq4 FAIL（均
   `from_repository_build true / re_judged AGREES`）+ 两条旧构建行。**台账链尾现在是 FAIL**——
   这是「保留每个失败 attempt」的直接后果，本卡不动它、也不粉饰。
   门一字未动：`gate_payload_sha256 fb0152c85d029ee0…`（与封前基线及第三、四、五刀逐字符相同），
   `p0-core`/`overall` 仍 `REQUIRED_CASE_NOT_REGISTERED`，`W60 promotable true`。
4. **`tools/rejudge_evidence.py <bundle-dir>`**：两份都 `rc=0`、`status agrees`，
   `failures` 逐字复现那两条具名拒止（本卡是 session 形状、封了 `asserter-inputs.json`，
   所以第二读法就是复判本身，不是「重跑检查」替代口径）。

## 5. ⑤（GLFW `[0x1000E]`）的新读数——只量现象，不写根因

本卡顺带量到（不是设计目标，如实报告）：加入者客户端崩溃从第四刀的「1/3、重跑即过」变成
**4/4 全崩**（`kin-e-rr-branch`×2、`kin-e-rr-seal`、`kin-e-rr-seal2`），而**宿主客户端 0/6 全好**；
崩溃签名与第四刀 FAIL bundle 逐字同族（`RenderSystem.initBackendSystem → GLX._initGlfw`）。
二分探针（`.tmp/e-rr-06-image-probe.log`）：换上**修前镜像** `minekin-runner-before:local`（`3f0938809910`，
无 H1a pytest 层）跑同一真实脚本，加入者仍同签名崩溃 ⇒ **H1a 镜像重建不是变量**；
`join_the_published_world` 的 `xvfb-run -a` 启动行在 `ed37260..be4e79b` 逐字未变（diff 只有行号位移），
`FORWARDED_VARIABLES` 转发链（`config.py:52-56`）自第四刀零改动。裸 `xvfb-run -a glxinfo -B` 在两种镜像里
都 3/3 拿到 `llvmpipe`，封存时的 `renderer_display` 也是实测 `llvmpipe`。
⇒ 现象边界：崩只发生在被管 joiner 客户端的 JVM 内、跨镜像、当前稳定复现；根因不写；
两把钥匙（crash report）都封在卷上。**这推翻了一刀「不再量到才开诊断卡」的前提，⑤ 建议升级。**

## 6. 读者面 `0ab208c` 的两问（卡面第 5 步，量出来的回答）

- `repo_checks_not_from_the_controlled_interpreter`：读数为 9 个 run id，全部是 E-CO/第五刀记录里点过名的
  9 份**修前 repo-evidence bundle**（`157eccd2 / 4f324c20 / 5d12b151 / 66c51fc7 / 7aa541e5 / 935c034a /
  e2393e92 / f2335016 / f4203033`）；E-CO 的 4 份镜像内重封不在列。**本卡两刀没有使该字段变化**——它是
  repo-check 形状的读者面，本卡封的是 session 形状（两份新 run id 都不在其中，且该字段按构造只读
  bundle 自己记录的 check 解释器）。
- 每 bundle 的 `check_interpreters`：本卡两份（以及卷上全部 6 条 `CORE-030` 行）都是 `[]`——
  **session/LAN 形状的 bundle 不记 check 解释器**，按卡面口径如实回答「此 bundle 无 check 解释器记录」，
  不强造读数。附一条底色：`reading_interpreter` 是 `/opt/minekin/bin/python`、
  `controlled_check_interpreter` 是 `/opt/minekin/bin/python3`（同镜像不同入口名，与本卡无关）。

## 7. 本卡没有做 / 不声称

- **不声称本卡产出了当前构建的 LAN PASS 封证。** 当前构建的 LAN PASS 仍是第四刀的 seq 2
  `19ff9064…`；本卡的两份新封都是 FAIL，链尾在 seq 4 FAIL。若 ⑤ 被治好，下一刀应封新 seq 顶掉链尾。
- **不声称 ③ 之外的任何 runner 修复经过验证**，也不声称 ⑤ 的根因、归类或「这是 trunk 回归」——
  §5 只给现象与二分边界（镜像、脚本字节、转发链三个变量都被量过并排除）。
- 不点亮、不声称任何门晋级；`promotable` 无一被触碰；registry/`mandatory`/`status`/判据/产品代码/
  runner/工具零改动（`git status --porcelain -- src tools tests test-orchestrator schemas bridge` 0 行）。
- 未测：加入者在任何配置下能否 PASS（两刀 FAIL 后按卡停手）；宿主侧同签名崩溃（0/6 未见）；
  B 探针那行的删除副本只动 `.tmp/`，主干脚本未动；1.20.1、HOST 族、其余 LAN 形状（换端口、
  宿主中途退出、二次加入）一概未碰。
- 规范卷 `minekin-runner-data`：E 仍是唯一写入者；本卡写入 = 4 次探针与 2 次真跑对 `kin/` 工作目录的
  追加（新 Kin 目录与 `kin-01` 的新会话目录）+ 封存的两份 bundle 与 2 条台账行；
  所有读数与反转均在 `:ro` 挂载（每份日志首行哨兵 `data writable False`），既有 attempt/bundle 字节零改写。
- **全程未连接、未探测、也未读取用户的远程服务器**（`.tmp/local-test-server.txt` 未被打开）；
  本文只出现 loopback/受控本地地址与卷名、镜像名。

## 8. 停点

`BLOCKED_HARNESS`（按卡面口径）：③ 路径已被真实通道证明可走通（具名读数 + 继续 + 反转仍静默），
封存通道本身也走通了（两份 FAIL 都按规则封进卷）；挡住 PASS 的是 ⑤ 家族的 joiner 客户端
`[0x1000E]`，其当前读数见 §5，材料在卷（两份 crash report、四份会话目录）。E 停在此前沿，
不改判据、不 patch runner、不动 ⑤ 的诊断。
