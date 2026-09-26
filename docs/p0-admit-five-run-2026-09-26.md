# 五条 ADMIT 行的当前构建真跑封证（B2 的第三刀）

> 真跑 + 只读记录，2026-09-26，E 证据 lane，工作分支 `codex/minekin-evidence`。
> 卡片：[执行计划 §4 `P0-CONTROLLED-CAMPAIGN-001`](development-execution-plan.md)。卡面在 B2 第二刀之后点名的那一格：
> 「剩余是 5 条 `only_another_build` 的 `ADMIT-001/040/060/100/110`」。**本记录就是这五条的新读数。**
> 被测构建：工作分支 `48fe79e`，它是主干 `ed37260` 之上的纯文档提交，源码与主干逐字相同；
> 五条 bundle 的 `launch_plan_digest` 都是 `bcc0c10d46ab5c0b…`，与前两刀同一份当前仓库构建。
> 本卡**不改**产品代码、case 判据、registry 字节、`status/gaps`；卷上既有的 90 份 bundle 与 attempt 序列
> 一份未删、一份未改，失败材料全部留着。
> **这一刀和第二刀一样弱：它不点亮任何门的晋级。** 五条都是 `mandatory: false` 的行（§3 第 3 节实测），
> 把它们的 bundle 从卷上取走，门一字不变（§4 的 R1）。
> 挂载即证据：真跑走 `run.sh`（仓库 `/src:ro`、规范卷可写、服务端与客户端同容器 —— loopback-only profile 唯一允许的形态）；
> 两次只读读数/反证 run 的开头都印 `src writable False | data writable False`。全程未连接任何远程服务器，
> 文中不出现任何基础设施地址。
> 本文每个数字出自 §1 点名的某份 `.tmp/` 日志；「日志 §N」指该日志的小节，不带前缀的 §N 指本文小节。

## 0. 一句话读数

B1 盘点分出的「本根只有别的构建的证据」那一格，从 **5 条** 变成 **0 条**：五条各在**当前仓库构建**上跑了一轮
受控本地真跑，各自封出一份 `verified`、复判 `AGREES`、判据版本对得上今天的 case 摘要的 PASS bundle
（`2/2、6/6、6/6、3/3、3/3` 条观测全中，零分歧）。规范卷的底色因此从 `attempts 54 / bundles 90 / from_another_build 61`
变成 **`attempts 59 / bundles 95 / from_another_build 61`** —— 五份新 bundle 都不在「另一个构建」名单里，
而名单本身一份未少。四条门读数和第二刀收口时**完全相同**（W40 与 p0-core 仍 `REQUIRED_CASE_NOT_REGISTERED`、
`satisfied: []`），这正是本卡预期要证明的事：这五条不是 mandatory，补上它们不动任何门。

## 1. 复现入口（本轮真实用过的命令）

真跑五条。每行只差 `MINEKIN_DOMAIN_CASE` 和该场景自己需要的旋钮；其余全部相同
（`kin-01`、规范卷、同一份钉住的 1.21.4 服务端 jar）。jar 用宿主上已 verify 的副本：
`$PWD/.tmp/vanilla/server.jar`，实测 `56,880,250` 字节、sha1 `4707d00eb834b446575d89a61a11b5d548d8c001`，
与 `tools/run_controlled_server.py` 里 `SERVER_RECIPES["1.21.4"]` 的 pin 逐字节相同。

```bash
common='MINEKIN_SERVER_JAR="$PWD/.tmp/vanilla/server.jar" MINEKIN_KIN_ID=kin-01'
profile='--profile tests/fixtures/runtime-input/bundle-p0-core-1.21.4.json
          --server-profile tests/fixtures/runtime-input/controlled-offline-server.json'

# ADMIT-001 裸 join：身份到达世界且服务端认得它
eval "$common" MINEKIN_DOMAIN_CASE=ADMIT-001 \
  bash test-orchestrator/runner/run.sh domain session start $profile      # → .tmp/e-b3-admit001-run.log
# ADMIT-040 服务端 online-mode=true、而 Server Profile 是 offline ⇒ 认证模式不一致
eval "$common" MINEKIN_DOMAIN_CASE=ADMIT-040 MINEKIN_DOMAIN_ONLINE_MODE=true \
  bash test-orchestrator/runner/run.sh domain session start $profile      # → .tmp/e-b3-admit040-run.log
# ADMIT-060 服务端下发资源包且 require-resource-pack=true，profile 的策略是 deny
eval "$common" MINEKIN_DOMAIN_CASE=ADMIT-060 MINEKIN_DOMAIN_RESOURCE_PACK=1 \
  bash test-orchestrator/runner/run.sh domain session start $profile      # → .tmp/e-b3-admit060-run.log
# ADMIT-100 Core 拒收首个快照 ⇒ 中断被分类进账本、Bridge 也分类了它
eval "$common" MINEKIN_DOMAIN_CASE=ADMIT-100 MINEKIN_DOMAIN_REFUSE_FIRST_SNAPSHOT=1 \
  bash test-orchestrator/runner/run.sh domain session start $profile      # → .tmp/e-b3-admit100-run.log
# ADMIT-110 对面是一个只收不答的黑洞 ⇒ 到点放弃、取消真的到达客户端并被执行
eval "$common" MINEKIN_DOMAIN_CASE=ADMIT-110 MINEKIN_DOMAIN_BLACK_HOLE=1 \
  bash test-orchestrator/runner/run.sh domain session start $profile      # → .tmp/e-b3-admit110-run.log
```

命令行是操作记录，bundle 里封的是 `argv_digest`（逐字见 §2 的表），不是 argv 明文；逐字重放需要照上面那组 env 组合。
五条的 `MINEKIN_DOMAIN_SECONDS` 一律取 `domain.sh` 的默认 240 秒界，没有为任何一条放宽或收紧：
从各 run document 的 `started_at` 到对应日志末行的墙钟实测是 **45 / 75 / 69 / 72 / 78 秒**（顺序同上），
五条都远端不到那条界，没有任何一条是被超时截出来的。

**旋钮生效不靠叙述，靠 bundle 里的字节**（下面这条只读命令就能复核，也是为什么 `ADMIT-060` 基线那次 FAIL 与本轮
PASS 的差别不可能是环境漂移）：

```bash
export MSYS_NO_PATHCONV=1
docker run --rm --entrypoint /bin/bash -v minekin-runner-data:/data:ro minekin-runner:local -lc '
  for r in b8da082d f3ce6fec e7e6687d b5d411db; do
    grep -E "^(online-mode|require-resource-pack|resource-pack=)" \
      /data/kin/kin-01/run/evidence/${r}*/server/server.properties; done'
```

读数与反证（同一镜像、同一只读挂载，破坏性动作全在 `/tmp` 下的副本里）：

```bash
export MSYS_NO_PATHCONV=1; REPO="$(cygpath -m "$PWD")"
for s in b3-admit-readout b3-admit-reversals; do
  docker run --rm --entrypoint /bin/bash \
    -v "${REPO}:/src:ro" -v minekin-runner-data:/data:ro \
    -e MINEKIN_HOME=/data -e PYTHONPATH=/src/src -e LD_LIBRARY_PATH=/opt/sqlite/lib \
    -w /src minekin-runner:local -lc "bash /src/.tmp/${s}.sh" > ".tmp/${s}.log" 2>&1
done
```

两个脚本在 E 工作树的 `.tmp/` 里（`.tmp` 不入版本库，脚本本身是本轮复现材料的一部分，其逐节内容在两份日志开头都会印出来）。
`b3-admit-reversals.sh` 会先自己从卷上把「当前构建的五行」的完整 run id 读出来再动手，所以它不依赖本文抄写的短 id。

判据锚点不必进容器，仓库里直接复核：

```bash
sed -n '1418,1439p' tools/assert_case_evidence.py   # first_snapshot_admitted：join 行、快照计数、PLAYABLE
sed -n '1028,1044p' tools/assert_case_evidence.py   # server_observed_join_identity
sed -n '2193,2300p' tools/assert_case_evidence.py   # ADMIT-100/110 用到的中断/放弃/取消四条
cat tests/fixtures/cases/admit-001.json tests/fixtures/cases/admit-040.json \
    tests/fixtures/cases/admit-060.json tests/fixtures/cases/admit-100.json \
    tests/fixtures/cases/admit-110.json             # 五条都是 work_package=W40、mandatory=false
```

## 2. 五行的读数

| case | run id | attempt | 场景字节证据 | 判据 | 卷上 bundle 数 | `bundle_digest`（verify 输出） |
| --- | --- | --- | --- | --- | --- | --- |
| `ADMIT-001` | `b8da082d37034161b5c32a0df40cd51d` | seq 2（顶掉 `68b23249`） | `server.properties`: `online-mode=false`、`white-list=true`；服务端日志有到达行 | `server_observed_join_identity`、`first_snapshot_admitted` 2/2 | 2 | `2ef9d080563da488…c65b069d` |
| `ADMIT-040` | `f3ce6fecc17d45238d80ca0fb889bce4` | seq 2（顶掉 `6b5856d5`） | `server.properties`: `online-mode=true` 而 profile 是 `auth_mode=offline`；日志行 `the session recorded the expected auth mismatch` | 认证冻结/不一致分类/单一策略单一进程/未入世界 6/6 | 2 | `daeb4ed5150734e7…2be61545` |
| `ADMIT-060` | `e7e6687d7f6d4a24830472b48c15dc01` | seq 3（顶掉 `7bc740ea`） | `require-resource-pack=true`、`resource-pack=http://127.0.0.1:32915/minekin-domain-pack.zip`、`resource-pack-sha1=a351bd36…` | 服务端确实要求包/封住的 profile 拒了它/上线的策略是冻住的那份/客户端从未下载/未入世界/未授租约 6/6 | 3 | `15acc833f3e6901b…43743eacc` |
| `ADMIT-100` | `b5d411db00ad46309113562292b87ca2` | seq 1（本根第一条当前构建） | run document：`snapshots_admitted=0`、`connection_state=FAILED`、`outcome=BRIDGE_LOST`；日志行 `the session was interrupted, as this run expected` | 拒收分类进账本/Bridge 也分类了/未入世界 3/3 | 2 | `4d578acd3b5125e8…cd723d43` |
| `ADMIT-110` | `40790771a02e47b5aa383a199be10360` | seq 1（本根第一条当前构建） | 无 `server/` 目录（黑洞 run，对面只有监听器）；日志行 `the client dialled the black hole and got nothing`；`snapshots_admitted=0` | 到点放弃/未入世界/取消真的到达客户端并被执行 3/3 | 3 | `ef3ecc507a79112c…f171e241` |

五条的 `argv_digest`（逐字）：`ADMIT-001 ea5a29ac89fc24521e06692fffbf69f46386f3bb3130924278254a1c5ccde0a1`、
`ADMIT-040 548711b72be5faec1dc62fe26b8f1fae601f7e9d9cb58a7cabc1343ea3ab77ef`、
`ADMIT-060 1b700fd25bdbb0c15e217b9a5708eaf634822778aa3b74f9339572d0c442c3fd`、
`ADMIT-100 f0c7c18d6d7c5eea43dc3e375d6d70be234cbd7e6b0582696c21285049679826`、
`ADMIT-110 eb7e19c99e6b8680ac3850dc559d516914d63c6f0628258c7e1426aee93729f2`。
服务端 run 目录依次是 `run-175 / 176 / 177 / 178`（`ADMIT-110` 无服务端目录），
`started_at` 依次 `11:42:57.6Z / 11:44:42.5Z / 11:46:47.0Z / 11:49:18.1Z / 11:51:11.8Z`（UTC），
每条都是本轮的一次 attempt 就判出 PASS（`session exited 0` → `the case verdict is PASS`），
attempt 序号 2/2/3/1/1 记的是这条 case 在本根上的历史，不是本轮重试次数。

## 3. 四读（同一份字节，四个互不通气的人）

1. **harness 自己的封口与验封**（日志各 run 的第 9–12 行）：五条都印出
   `domain: sealing run evidence for case <ID>` → 一份 13（`ADMIT-110` 是 10）条 artifact 的清单 →
   `the case verdict is PASS` → `evidence verify said {..., "result": "PASS"}`。
2. **`python -m minekin_core evidence verify <run-id>` 在只读挂载上重跑**（日志 §R3）：
   `ADMIT-040` 的 `f3ce6fec…` 在反证 run 里以 `rc=0`、`artifacts 13`、`result PASS` 通过；
   并且 `run-document.json` 的 sha256 实量仍是清单里那个 `a6764ece…`。
3. **`tools/report_promotion.py --data-root /data`**（日志 §1）：
   `evidence counts: {"attempts": 59, "bundles": 95, "from_another_build": 61, "unreadable": 0, "unsealed": 0, "unverified": 0}` ——
   与第二刀收口时的 `54 / 90 / 61` 相比 attempts+5、bundles+5，`from_another_build` 一字未变，
   多出来的五份都不在那份名单里；`rc=1` 是「不晋级」而不是「读坏了」。
   逐行看（日志 §2）：五条各有一条 `build=True verified=True sealed=True re_judged=AGREES crit_match=True violations=0`
   （`b8da082d / f3ce6fec / e7e6687d / b5d411db / 40790771`），`ADMIT-100/110` 各是**本根第一条**当前构建行。
4. **`tools/rejudge_evidence.py` 只看封住的字节重判**（日志 §4）：
   `ADMIT-001 observed=2/2 rc=0`、`ADMIT-040 6/6`、`ADMIT-060 6/6`、`ADMIT-100 3/3`、`ADMIT-110 3/3`，
   五条的 `disagreements` 都是 `[]`。同一轮里旧材料也照旧被重判：`ADMIT-060` 的 seq 1 `3c17aa78` 仍是
   `sealed=FAIL rejudged=PASS`（3 条分歧，`rc=1`），`ADMIT-100 af320713` / `ADMIT-110 4c5760e4 / c383d4f1`
   仍是 `rc=2 unjudged`（它们封的是别的 case 版本摘要）。

## 4. 反证（三个动作，全在 `/tmp` 的副本上；规范卷全程 `:ro`）

日志：`.tmp/b3-admit-reversals.log`，开头印 `src writable False | data writable False`。

| 记号 | 动作 | 读数 |
| --- | --- | --- |
| **P（正对照）** | 整卷原样复制到 `/tmp`，什么都不动 | bundles **95**、`from_another_build` 仍是那 61 个 run id、`unverified 0 / unreadable 0`；五条各有一行当前构建 PASS。**这证明 R1 的变化不是复制动作本身造出来的。** |
| **R1（非空转）** | 在同一份副本里删掉本轮这五个 run 目录 | bundles **90**，五条的当前构建行全部变 `[]`；而 `W40 promotable=False blocks=["REQUIRED_CASE_NOT_REGISTERED"] satisfied=[]`、`p0-core` 同一读数、`W60 promotable=True blocks=[]`、`overall` 一字未变。**取走与补上给出同一份门读数 ⇒ 这五条今天不动任何门，本卡的边界不是话说得小，而是门真的没动。** |
| **R2（一位字节）** | 把 `ADMIT-040` 副本里的 `run-document.json` 末尾加一个换行（1811 → 1812 字节） | `evidence verify` **`rc=12`**、`tools/rejudge_evidence.py` **`rc=2`** 且理由是 `ARTIFACT_DIGEST_MISMATCH:run-document.json`（「the bundle does not hold up, so there is nothing to re-judge」）。**密封是按字节执法的，不是按名字执法的。** |
| **R3（canonical 未伤）** | 同一条 `f3ce6fec…` 直接对规范卷验 | `rc=0`、`result PASS`、`run-document.json` 的 sha256 仍等于 manifest 里记的 `a6764ece…`。R2 的破坏只发生在副本里。 |

P 与 R1 是一对，R2 与 R3 是一对：前者证明「本轮读到的推进确实来自这五份 bundle」，后者证明
「验封/复判真的会拒绝被改动的 bundle，而且规范卷没被这轮反证碰过」。

## 5. 本卡不声称

- **不点亮任何门的晋级。** 五条都是 `mandatory: false`（`tests/fixtures/cases/admit-*.json`），
  且它们出现在 `W40` 与 `p0-core` 的 `requirement.non_mandatory` 名单里（日志 §3 实测两行都列出这五个 id）。
  两门的 `satisfied_cases` 今天仍是 `[]`，阻断者仍是 `REQUIRED_CASE_NOT_REGISTERED` —— 那是**主控侧**的
  mandatory 登记缺口，不由 E 翻。
- **不声称 `p0-core` 或 `W40` tested**，也不声称任何门可晋级；`W60 promotable=True` 是它自己那三条 mandatory
  行的结果，与本轮无关（R1 同时抽掉五行它也不变）。
- **不覆盖旧失败材料。** `ADMIT-060` 的 `3c17aa78`（FAIL + `DISAGREES` + `SERVER_RESOURCE_PACK_URL_NOT_LOOPBACK`
  那条具体失败）与 `ADMIT-110` 的 `c383d4f1`（FAIL）都还在卷上、还在同一份读数里；本轮是把它们**旁边**补上
  当前构建的一行，不是把它们换掉。
- **不声称五条各自覆盖了「非 loopback / LAN / 真实远程」场景。** 它们的输入都是
  `bundle-p0-core-1.21.4.json` + `controlled-offline-server.json`，全程 loopback、同一容器。
- **不声称 B2 卡面收口。** 卡面后半段（`§3.3` 的卡队列、`BLOCKED_DECISION` 群、L3/L5/L6、崩溃恢复、
  restart 协调、离线身份、soak）按 [执行计划](development-execution-plan.md) 等主控排期；
  另外 `ADMIT-010/020/030/050/090/120` 与 `HOST*` 那批仍在 `overall.requirement.absent` 名单里（日志 §1 的 31 个），
  本轮一份也未触及。
- **不触碰 V08、不连接用户的远程服务器、不写规范卷以外的数据。** 本轮对规范卷只有五次真跑的追加写入
  （E 是它唯一的写入者），以及若干次 `:ro` 读取。

## 6. 与卡面的对应

| 卡面要求 | 本轮交付 | 未交付 |
| --- | --- | --- |
| 「在受控 dedicated offline 与必要 LAN 场景补当前 build 的 mandatory sealed bundle」 | 五轮受控本地真跑 + 五份当前构建 sealed bundle（§2、§3） | mandatory 本身：门仍缺 `REQUIRED_CASE_NOT_REGISTERED`，登记在主控侧 |
| 「剩余是 5 条 `only_another_build` 的 `ADMIT-001/040/060/100/110`」 | 该格从 5 变 0：`from_another_build` 名单长度不变而五份新 bundle 都不在其中（§3 第 3 读） | —— |
| 「不翻 registry、不改判据、不动 `status/gaps`」 | 提交是纯文档（本文件 + 计划/todo/handoff 三处回勾），`git diff` 无 `tools/`、`tests/fixtures/cases/`、`src/` 字节 | —— |
| 「给出反证与边界」 | P/R1/R2/R3（§4）+ 六条不声称（§5） | LAN 与真远程场景仍待主控排期 |
