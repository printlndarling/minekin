# 四条仓库自检行的当前构建封证（B2 的第五刀）

> 真跑 + 只读记录，2026-09-26，E 证据 lane，工作分支 `codex/minekin-evidence`。
> 卡片：[执行计划 §4 `P0-CONTROLLED-CAMPAIGN-001`](development-execution-plan.md)。这一刀收的是
> [B1 盘点](p0-evidence-inventory-2026-09-26.md) §6 三格里第三格的名字：「判官只需仓库字节但本根零 bundle 17 条」。
> 被测构建：工作分支 `2a83109`（第四刀的记录提交）之上的**同一份主干源码**；四份 bundle 的
> `launch_plan_digest` 都是 `bcc0c10d46ab5c0b…`，与前四刀同一份当前仓库构建。
> 本卡**不改**产品代码、case 判据、registry 字节、`status/gaps`；卷上既有的 97 份 bundle 与 61 条 attempt 序列
> 一份未删、一份未改，失败材料全部留着。
> **这一刀和前三刀一样弱，而且弱得更彻底**：四行都是 `mandatory: false`，而门读数在本刀前后
> 是**同一个摘要**（§3 第 3 读，`fb0152c8…`）—— 不是「看起来没变」，是整份门 payload 逐字节没变。
> 挂载即证据：封证走 `minekin-runner:local`（仓库 `/src:ro`、规范卷可写只有封证那一次）；
> 所有读数与反证 run 的开头都印 `src writable False | data writable False`。
> 全程未连接任何远程服务器，文中不出现任何基础设施地址。
> 本文每个数字出自 §1 点名的某份 `.tmp/` 日志；「日志 §N」指该日志的小节，不带前缀的 §N 指本文小节。
> 本轮的脚本与日志**都在 E 工作树的 `.tmp/` 里**（`.tmp` 不入版本库）。

## 0. 一句话读数

B1 分出的「判官只需仓库字节但本根零 bundle」那一格，从 **17 条** 变成 **13 条**，而剩下的 13 条
**全部是 HOST 家族**（`HOST-010/020/050/060/070/080`、`HOSTCOMMIT-090/110`、`HOSTCTL-001/010/050/060/070`，
逐字对照 [盘点 §2](p0-evidence-inventory-2026-09-26.md) 那 18 条名单减去第二刀的 `OFFLINE-030` 再减去本轮四条）。
四条 `OFFLINE-001/040/050` + `ADMIT-080` 各封一份**当前构建**的 PASS bundle（`5/5、3/3、3/3、6/6` 条检查全 held），
卷的底色因此是 `attempts 61→65 / bundles 97→101 / from_another_build 61`（名单长度一字未变）。
**门一寸未动，而且是量出来的**：封证前后各跑一次 `report_promotion.py`，把 `work_packages` 与 `overall` 整段
按 sort_keys 序列化后取 sha256，两次都是 `fb0152c85d029ee0…`（日志 readout §gate_digest 两行）。
也就是说 B2 卡面点名的「只差运行」的三种形状至此全部清空，而门禁缺口仍是主控侧的
`REQUIRED_CASE_NOT_REGISTERED` / `NO_MANDATORY_CASES`。E 到 HOST 家族门前停住：HOST 的所有权未冻结
（[执行计划](development-execution-plan.md) §5 与既有决定），封它们等于往未决定的 ownership 里加读数。

## 1. 复现入口（本轮真实用过的命令）

这条路是 09-25 就走过并被记录在案的那条：检查跑在**有仓库工具链的地方**（宿主 `.venv`，pytest 9.1.1），
封存跑在**受控镜像里**（`seal_repo_case.py` 只要 verdict 与各检查的完整输出，不需要 pytest）。
为什么必须分两处，见 §5 的实测。

宿主侧，四条 case 各跑一遍判据（工作树根目录）：

```bash
cd /c/Users/darling/Documents/agent_work/minekin-wt-evidence
for c in offline-001 offline-040 offline-050 admit-080; do
  .venv/Scripts/python.exe tools/run_repo_case.py --case tests/fixtures/cases/$c.json \
    --output-directory .tmp/b5-repo-out/$c > .tmp/b5-verdict-$c.json
done      # 四条 exit=0；5/3/3/6 条检查全 held ⇒ .tmp/b5-verdict-*.json
```

容器侧，四份 verdict 封进规范卷（**这一条是本轮唯一对卷的写**；`/src` 只读）：

```bash
export MSYS_NO_PATHCONV=1; REPO="$(cygpath -m "$PWD")"
docker run --rm --entrypoint /bin/bash \
  -v "${REPO}:/src:ro" -v minekin-runner-data:/data \
  -e MINEKIN_HOME=/data -e PYTHONPATH=/src/src -e LD_LIBRARY_PATH=/opt/sqlite/lib \
  -w /src minekin-runner:local -lc 'bash /src/.tmp/b5-seal.sh' > .tmp/b5-seal.log 2>&1
```

`b5-seal.sh` 里每行只差 case 名，其余四个参数全部相同：

```bash
python3 tools/seal_repo_case.py --data-root /data \
  --case tests/fixtures/cases/<c>.json \
  --profile tests/fixtures/runtime-input/bundle-p0-core-1.21.4.json \
  --verdict /src/.tmp/b5-verdict-<c>.json \
  --output-directory /src/.tmp/b5-repo-out/<c>
```

读数与反证（同一镜像、`/data:ro`，破坏性动作全在容器 `/tmp` 或宿主 `.tmp` 的副本里）：

```bash
for s in b5-readout b5-reversals b5-copy-delete b5-env-gap; do
  docker run --rm --entrypoint /bin/bash -v "${REPO}:/src:ro" -v minekin-runner-data:/data:ro \
    -e MINEKIN_HOME=/data -e PYTHONPATH=/src/src -e LD_LIBRARY_PATH=/opt/sqlite/lib \
    -w /src minekin-runner:local -lc "bash /src/.tmp/${s}.sh" > ".tmp/${s}.log" 2>&1
done
bash .tmp/b5-r4-mutation.sh   > .tmp/b5-r4-mutation.log 2>&1      # 宿主：产品钉住性反证
bash .tmp/b5-r4b-offline040.sh > .tmp/b5-r4b-offline040.log 2>&1   # 宿主：OFFLINE-040 自己的那条
```

判据锚点不必进容器，仓库里直接复核：

```bash
.venv/Scripts/python.exe -c "
import sys,json; sys.path.insert(0,'tools')
from check_case_assertions import IMPLEMENTATIONS as I
for c in ['offline-001','offline-040','offline-050','admit-080']:
    d=json.load(open(f'tests/fixtures/cases/{c}.json',encoding='utf-8'))
    print(c, d['mandatory'], d['work_package'], [(n, I[n].kind, I[n].target) for n in d['assertions']])"
```

逐文件的计数用它下面这一段（同一条命令的最后两行换成计数器；这两行是本卡下面那句「9/2/5/1」的出处）：

```bash
.venv/Scripts/python.exe -c "
import sys,json,collections
sys.path.insert(0,'tools')
from check_case_assertions import IMPLEMENTATIONS as I
tot=0; files=collections.Counter()
for c in ['offline-001','offline-040','offline-050','admit-080']:
    d=json.load(open(f'tests/fixtures/cases/{c}.json',encoding='utf-8'))
    a=[(n, I[n].kind, I[n].target) for n in d['assertions']]
    tot+=len(a)
    for n,k,t in a: files[t.split('::')[0]]+=1
print('total checks',tot); print('by file',dict(files))"
# total checks 17
# by file {'tests/unit/test_offline_session.py': 9, 'tests/unit/test_session_material.py': 2,
#          'tests/unit/test_connection_generation.py': 5, 'tests/unit/test_session_state.py': 1}
```

17 条检查全部是 `pytest` 类，落在**四个**测试文件里（上面那段计数命令的 `by file` 实测：9/2/5/1，总数 17）：
`OFFLINE-001/040/050` 三案共 11 条，其中 **9 条**在 `tests/unit/test_offline_session.py`、
**2 条**在 `tests/unit/test_session_material.py`（`OFFLINE-040` 的 id128 与大写报告同一性）；
`ADMIT-080` 的 6 条分在 `tests/unit/test_connection_generation.py`（**5 条**）与
`tests/unit/test_session_state.py`（**1 条**），即代次/关闭/迟到回调那组。四条 case 都是 `mandatory: false`
（`OFFLINE-001/040/050` 属 W30，`ADMIT-080` 属 W40）。

## 2. 四行的读数

| case | run id | attempt | 检查 | 工件 | 判据版本 `case_version` | `bundle_digest` |
| --- | --- | --- | --- | --- | --- | --- |
| `OFFLINE-001` | `935c034a99f04fa9a121e7ef739a3f5d` | seq 1（本根第一条） | 5/5 | 9 | `6b0241fc26b7…` | `a82cf49010c7ccff…` |
| `OFFLINE-040` | `4f324c20830f4e95a62e497e5b3d7a3b` | seq 1（本根第一条） | 3/3 | 7 | `a3beb905a353…` | `54385ddf7daca6ce…` |
| `OFFLINE-050` | `f42030333c904d489e2042fb95bccf22` | seq 1（本根第一条） | 3/3 | 7 | `b4beb8a694f4…` | `5b58bead0cc7bbe3…` |
| `ADMIT-080` | `66c51fc7a2384c9d8b09ddf96ac129f2` | seq 1（本根第一条） | 6/6 | 10 | `35081d5f8123…` | `058d1232ec291e0d…` |

封证墙钟（UTC，`manifest.json` 与 `bundle.sha256` 的 mtime，日志 copy-delete §a3 与容器 `date -u -r` 实测）：
`13:16:14 / 13:16:17 / 13:16:20 / 13:16:23`，四条各一次就封成，没有重试。
每条目录里磁盘上确实有 `5/3/3/6` 份 `checks/*.log`（检查的**完整输出**，不是摘要），
`bundle.sha256` 都是 65 字节（一个摘要 + 换行）。

**这四份 bundle 装的是什么**（与运行类 bundle 的同与异，`seal_repo_case.py` 的 docstring 就是这条边界）：
`check-verdict.json`（runner 的判决）、每条检查的完整输出、**case 定义本身**（于是读者能独立重算
`case_version`）、被比较的那份夹具摘要清单 `contracts/manifest.sha256`、`orchestrator-trace.json`（谁跑的、
每条检查是什么）。世界段与「这次没有世界」的运行同一条记录：`kind: none` + 空文档摘要
`e3b0c44298fc…`；`server_jar_sha1` 与 `server_observed_name_uuid` 都是空串。日志 readout §manifests 逐条印出。

**两处必须说清的环境事实**（不是缺陷报告，是读数口径）：

1. `environment` 段记的是**封存进程**所在的环境：`Linux 6.18.33.2-microsoft-standard-WSL2`、
   Temurin `21.0.12.1`、`20 vCPU / 7.6 GiB`、`renderer_display: unmeasured`；
   而 `orchestrator-trace.json` 里每条检查的命令第一个元素是
   `C:\Users\darling\Documents\agent_work\minekin-wt-evidence\.venv\Scripts\python.exe`。
   **两者本来就不是同一台机器上的两个进程**，这是仓库自检类通道与生俱来的形状：卷上 09-25 那三份
   （`f2335016 / e2393e92 / 157eccd2`）量的也是同一形状（日志 readout §manifests、copy-delete §b）。
   本轮没有伪造任何一方：检查确实在宿主跑了，封存确实在受控容器里跑了。
2. `identity.configured_profile` 今天四条都是 `bundle-p0-core-1.21.4.json#b615d114e96151d1`，
   而 09-25 那三份记的是 `…#e3bfbae8f41914ee`；两者的 `launch_plan_digest` **都是** `bcc0c10d46ab…`。
   也就是说：profile 文件的**字节**变了（`profile_reference` 钉整份文件摘要），而 launch plan 覆盖的是
   解析出来的配方字段，所以构建身份没动。本轮三刀的运行类 bundle 也记 `b615d114…`
   （`ADMIT-001 b8da082d…` 与 `CORE-030 19ff9064…`，日志 copy-delete §b 实测两行）——
   读者不要期待今天的 bundle 里出现 `e3bfbae8…`。

## 3. 四读（同一份字节，四个互不通气的人）

1. **封存自己的输出**（日志 seal）：四条各印 `"status": "sealed"`、`"result": "PASS"`、`"failures": []`、
   `attempt_sequence: 1`，并逐条给出 `bundle_digest`（§2 那一列）。
2. **`python -m minekin_core evidence verify <run-id>` 在只读挂载上**（日志 readout §verify）：
   四条 `rc=0`、`result PASS`、`artifacts 9/7/7/10`，`bundle_digest` 与第 1 读逐字相同。
3. **`tools/report_promotion.py --data-root /data`**（日志 readout §counts/§gates）：
   `evidence counts {attempts 65, bundles 101, from_another_build 61, unreadable 0, unsealed 0, unverified 0}`；
   四行都是 `from_repository_build: true`、`launch_plan_digest bcc0c10d46ab…`、`verified: true`、
   `sealed: true`、`result: PASS`、`violations: []`。逐门读数：
   `W30 blocks [NO_MANDATORY_CASES, REQUIRED_CASE_NOT_REGISTERED] non_mandatory 8`（本轮三条都在名单里）、
   `W40 blocks [REQUIRED_CASE_NOT_REGISTERED] non_mandatory 6`（`ADMIT-080` 在名单里）、
   `p0-core non_mandatory 21`（四条都在）、`W60 promotable true`、`overall promotable false / blocking 31`。
   **整段门 payload 的 sha256 在封证前后是同一个值** `fb0152c85d029ee06a41a34e84f9656cd23fae0b1e166322c494d1190cd178da`
   （封前那份由同一容器对 `.tmp/b5-baseline.log` 里那行完整 JSON 重算，日志 readout §before gate_digest）。
4. **复判端**：`tools/rejudge_evidence.py` 对这四份各报 `rc=2`、`status unjudged`，理由是
   「does not record the inputs its judgement was made with (`asserter-inputs.json`) —— a re-judge would have to
   guess them」（日志 readout §rejudge）。这正是仓库自检类 bundle 的既有口径（09-25 记录里就量过一次），
   所以这条通道的**第二次读法是重跑它的检查**，不是 `rejudge_evidence.py`。本轮四条都重跑了：
   宿主上对未改动的树各跑一遍，`PASS 5/5、3/3、3/3、6/6`，且是四个**全新的 run id**
   `c844cffa… / 5826ff69… / 25696021… / e115a539…`（日志 b5-rerun 与 b5-r4b 末段）——
   同意，但不是同一份字节，这一点按字面写在这里。

## 4. 反证（六件动作，全在副本上；规范卷全程 `:ro`，唯一例外是 §1 那一次封证）

| 记号 | 动作 | 读数 |
| --- | --- | --- |
| **P（正对照）** | 把 `repo-evidence/` + attempt 台账原样复制到容器 `/tmp`，什么都不动（532 KB，不必复制 19 GB 的 `kin/`） | 读者列出 **9 份 bundle**、`attempts 65`、`unverified 0`，本轮四条各一行 `verified True sealed True result PASS violations []`。**R-A/R-B 的变化因此不是复制动作本身造出来的。** |
| **R-A（一位字节，检查输出）** | 在 P 的副本里给 `OFFLINE-001` 某条 `checks/*.log` 末尾加一个换行（102 → 103 字节） | `evidence verify` **`rc=12`**、`status invalid`、`verified false`、`violations ["ARTIFACT_DIGEST_MISMATCH:checks/…"]`；`rejudge_evidence.py` **`rc=2`** 但**理由换了**：不再是 asserter-inputs 那句，而是 `the bundle does not hold up … ARTIFACT_DIGEST_MISMATCH:<同一条>` —— 字节核对排在 inputs 之前；`report_promotion` 同一份副本 `unverified: 1`，名单里正是 `935c034a…`。**把这一个字节的改动还原，`verify` 立刻回到 `rc=0`。** |
| **R-B（一位字节，判决工件）** | 换一份工件：给 `OFFLINE-050` 的 `check-verdict.json` 加一个换行（→ 2379 字节） | 同样 `rc=12`、`status invalid`。**密封按字节执法，与工件叫什么名字无关。** |
| **R-C（规范卷未伤）** | 同四条 run id 再对规范卷验 | 四条 `rc=0`、`result PASS`、`bundle_digest` 与 §2 逐字相同；台账里每案恰好一条 `('…', 1, 'SEALED')`，卷上 attempt 总数 65。 |
| **R-D（产品钉住性：改一字节产品代码，检查会不会红）** | 把 `src/` 复制到 `.tmp/b5-mut`（副本），只改 4 行：两处 `access_token_argv="0"`→`"1"`（`adapters/launcher/offline_session.py`）、两处 `CallbackDisposition.STALE_GENERATION`→`FAILED`（`domain/connection.py:194,278`）；用 `PYTHONPATH` 指向副本再跑四案（副本优先已被单独量过：`minekin_core.__file__` 落在副本里） | `OFFLINE-001` **FAIL 3/5**（红的正是 token 与空凭证那两条）、`OFFLINE-050` **FAIL 2/3**（`test_candidate_document_reports_presence_without_values`）、`ADMIT-080` **FAIL 4/6**（stale close 与 reconnect 那两条）；`OFFLINE-040` 这一轮**仍 PASS 3/3** —— 那两处改动碰不到它的判据，于是给它单独一刀（`.tmp/b5-mut3`，只改 `domain/offline_identity.py` 的 `return str(self.uuid)` → `return self.uuid.hex.upper()`）：`OFFLINE-040` **FAIL 2/3**，红的是 canonical 编码那条。四份 FAIL verdict 封进**宿主 `.tmp/b5-scratch-root`**（台账与 bundle 都在卷外，卷从未被指名），`seal_repo_case.py` 对四条分别 `exit=1/0/1/1` 并如实封出 `result FAIL` + 非空 `failures` —— **失败材料留着，且读者读得出它是 FAIL。** |
| **R-E（取走的方向）** | 在 P 那份副本里删掉本轮四个 run 目录 | `bundles 9 → 5`，列出的 case 名正好少掉这四条，`attempts` 仍是 65。**顺带量到一件关于读者的事实**：台账里那四行 `SEALED` 指向已不存在的目录时，`unsealed` 与 `unreadable` 都是 **0** —— 半套卷的拒绝只朝一个方向生效（有 bundle 无台账 ⇒ `unusable`，09-25 量过；有台账无 bundle ⇒ 今天 0/0）。这条读数交给主控判断是否是一张卡，E 不动工具。 |
| **R-F（门的方向）** | 不是动作，是第 3 读里的两次真读数 | 封前 97 份 bundle 与封后 101 份 bundle，`work_packages`+`overall` 整段 sha256 **相同**。补上这四份与「不补」给出同一份门读数 ⇒ **本卡的边界不是话说得小，而是门真的没动。** |

**写文档期间卷没有再被碰过**（日志 `.tmp/b5-final-verify.log`，`13:42:09` UTC，`/src:ro` + `/data:ro`）：
四条 `evidence verify` 仍 `rc=0`，`artifacts 9/7/7/10`、`bundle_digest` 与 §2 那一列逐字相同，
`/data/repo-evidence` 仍是 9 个目录，台账 `rows 65 / sealed 65` 且四条各一行 `seq 1 SEALED`。

## 5. 一处环境边界（实测，不是叙述）

这四条检查**不能**在受控镜像里跑，而且如果硬跑会封出一份**由环境造成的假 FAIL**：

- 镜像里 `pytest` 不存在：`find_spec("pytest")` → `None`；
  `/opt/minekin/lib/python3.12/site-packages` 只有 `['google','pip','pip-24.0.dist-info','protobuf-6.33.6.dist-info']`。
- 在镜像里对 `offline-001` 跑 `run_repo_case.py`（不封存、不写任何东西）⇒ `rc=1`、
  `result FAIL`、五条全 `CHECK_FAILED:exit 1`，每条 detail 都是
  `/opt/minekin/bin/python3: No module named pytest`（日志 env-gap）。
- 出处是钉死的：`test-orchestrator/runner/Dockerfile` 那段注释与
  `RUN python3 -m venv /opt/minekin && … pip install "protobuf==6.33.6"`（日志 env-gap 末段原文）。

本轮**没有**为绕过它做任何一件事：没有临时 `pip install`（把网络上未钉住的代码放进封证链路，等于让封出来的字节
依赖一份没人评审的环境），没有改镜像（`test-orchestrator/` 不在本卡允许路径内，且这是基础设施不是证据），
也没有在容器里把那份假 FAIL 封进卷。走的是 09-25 已在卷上留下三份的同一条通道。
**这条边界值得主控一格处置**：要么给受控镜像加一份钉住的测试工具链（属基础设施卡），
要么明确「仓库自检类 bundle 的 environment 段就按封存进程记」是本项目的正式口径。E 不自作决定。

## 6. 本卡不声称

- **不点亮任何门的晋级。** 四条都是 `mandatory: false`，且都列在所属门的 `requirement.non_mandatory` 里
  （第 3 读实测）；门 payload 摘要前后相同（R-F）。
- **不声称 `re_judged = AGREES`。** 这四条报的是 `UNJUDGED` + 那句既有理由（第 4 读），
  第二次读法是重跑检查，四条各有独立的重跑且同意；这与运行类 bundle 的复判不是同一种强度，请照此读数使用。
- **不声称 HOST 家族那 13 条被覆盖，也不封它们。** 第三格剩下的 13 条全是 `HOST*`；
  HOST 的 ownership 未冻结（执行计划 §5），且既有记录早写过「HOST 的拒绝面判据已在本地代码里，缺的是决定不是判据」。
- **不声称这四行覆盖了任何运行时/网络场景。** 它们的判据全部是仓库内纯检查（17 条 pytest 节点，§1 末尾点名），
  没有 Minecraft、没有 LAN、没有远程。
- **不翻 registry、不改 `mandatory`、不动 `status/gaps`**，也不声称 §3.3 的卡队列或 `BLOCKED_DECISION` 群有任何推进。
- **不触碰 V08、不连接用户的远程服务器、不写规范卷以外的数据。** 本轮对规范卷只有四次封存追加；
  反证用的 FAIL bundle 在宿主 `.tmp/b5-scratch-root`，容器副本在容器 `/tmp`，随容器销毁。
- **不声称 `domain.sh:657` 与 GLFW `[0x0E]` 那两条 runner 缺陷已处置**，也不声称受控镜像需要 pytest 这件事已由谁决定。

## 7. 与卡面的对应

| 卡面要求 | 本轮交付 | 未交付 |
| --- | --- | --- |
| 「在受控环境下补当前 build 的 sealed PASS bundle」 | 四份当前构建（`bcc0c10d…`）repo bundle，四读齐全 + 六件反证（§2–§4） | mandatory 登记/晋级（主控） |
| B1 §6 第三格「判官只需仓库字节但本根零 bundle 17 条」 | 非 HOST 的 4 条清空（17 → 13），剩下的 13 条**全部**属 HOST 家族 | HOST 那 13 条：等 ownership 决定，不是缺判据 |
| 「不 patch 已提交的 runner/产品代码、不新增断言」 | 提交是纯文档；`git status --porcelain -- src tools tests test-orchestrator` 本轮全程为空（§4 的动作只在 `.tmp` 副本里） | —— |
| 「给出反证与边界」 | P/R-A/R-B/R-C/R-D/R-E/R-F（§4）+ 环境边界（§5）+ 七条不声称（§6） | 受控镜像是否加钉住的测试工具链 = 主控/基础设施决定 |

## 8. 打包时的基础门（E 工作树 `2a83109` 之上的当前树，本次提交只动 `docs/`）

`uv run --frozen` 逐条真跑：`ruff check .` → `All checks passed`；`ruff format --check .` → `339 files already formatted`；
`pyright` → `0 errors, 0 warnings, 0 informations`；`pytest -q` → `2509 passed, 2 skipped in 352.47s`
（两条 skip 各自点名：`test_orphans.py:686` 平台答不了这个问题、`test_silent_listener.py:123` Windows 的 terminate 不是信号）；
`check_boundaries.py` → `OK`；`check_case_assertions.py` → `OK (140 registered)`；
`verify_fixture_digests.py` → `W00 schema and fixture digests: OK`；`check_workflow_pins.py` → `OK`。
`git status --porcelain -- src tools tests test-orchestrator schemas bridge` 为空 ⇒ 本轮没有任何产品/工具/夹具改动。
