# V1201-REAIM-LIVE-OBSERVATION-WINDOWS-001：#50 §5 再获取在 Windows 受控 run 上活体触发（2026-10-02）

> **一句话结论**：#50 的 Core 再获取半边（`last_target_block` + `angle_to_degrees` 一次重瞄）此前只有单测覆盖、活体触发一直记为「压在受控 Linux runner 上、本 Windows 机取不到」。**本轮实测该前提作废**：把已审桥 jar 从填好的卷里的既有 session 复制回 gitignored、源摘要排除的 `bridge-1201/build/libs/`，一发 `demo.sh --autonomous` 即在 Windows 干净收尾，并**在真实 run 文档里看到了重瞄那一步**——collect 把玩家挪开、准星丢了原木后，`turn_to` 报出 `turn back to the resource block this mind was breaking`、算得非 45° 倍数的精确角、CONFIRMED，紧随的 `break_seen_block` 也 CONFIRMED（**不再 AIM_STALL**）。本轮**不封证、不晋级、不改任何产品字节**；`3×3 终产物 CONFIRM` 仍待 #47 桥侧上报。

## 一、承载字节与放行机制（先核摘要）

| 项 | 值 |
| --- | --- |
| 主干基线 | `495e613`（本轮提交前远端 `main`） |
| 复用产物 `bridge-1201/build/libs/minekin-bridge-1201-0.0.0.jar` | sha256 `ff2540824ee354149cdc7230d40f9d1eacbbed267ef9cf9936f6f64778672519`，1,442,677 B（从卷 `minekin-local-demo` 既有 session 的 `mods/` 逐字节复制、双端 `sha256sum` 核对；未跟踪、`.gitignore` 覆盖，工作树零改动） |
| 源树摘要为何不受影响 | `recipe.py` 的 `source_tree_sha256` 排除 `build/`、`.gradle/` ⇒ 放 jar **不动** candidate `source_digest`（live `113e4524…` 仍等于配方钉值），`_candidate_1201_audit` 的 source/jar 两道 pin 皆过 |
| run1（未触发面） | run `3943768408db4e0f81ecce6f3c2b3c04`，10 步上限 |
| run2（触发面） | run `9e97b7ea3c0740bb86dcd84e62f05a10`，18 步上限 |
| 远程服 | **未连接**；`.tmp/local-test-server.txt` 未读；服务端由 run 自起且只听容器内 loopback |

## 二、两发的分工（run1 证「没触发」，run2 证「触发」）

- **run1**：`--autonomous`、无模型走 `local_reflection`、世界在 Kin 视线里堆原木。10 步全 `CONFIRMED`（break→collect→craft 板→close→craft 棍→close→break→collect→craft 板→close），**两次 `break_seen_block` 均首攻命中、零 `AIM_STALL`** ⇒ 重瞄兜底那条分支这次**没被走到**（正负无从分辨，故 run1 不算 #50 的活体正对照，只算管线可跑的正对照）。收尾 `STOPPED_ON_REQUEST`、exit 0、`release.released [332]/unconfirmed []`、`--rm` 容器自动清。
- **run2**：同卷同 kin、把步数预算放到 18，让本地链多循环几轮采集。第 7、第 15 步出现 `skill: turn_to`、`reason: "turn back to the resource block this mind was breaking"`、`result: CONFIRMED`，其 `pitch/yaw` 是**计算的精确角（−47.39°/108.03°、−63.97°/40.94°）而非盲扫的 45° 倍数**——这把它判别于同 run 里第 16、17 步那种 `look for the next thing the milestone needs` 的 45° 倍数盲扫。紧随第 8 步 `break_seen_block` **CONFIRMED** ⇒ **第 2 根原木经重瞄可达、不再 `AIM_STALL`**，正是 `461adba`/`00520e1` 要产出的行为。全程 `perceived_information_class = PLAYER_EQUIVALENT`（回忆的只是准星自报过的那一格坐标，非被禁的 chunk scan）。

## 三、诚实边界（勿写高）

1. **这是活体观察 run，不是封证**：未传 `MINEKIN_DEMO_CASE`，不进 registry、不动门载荷、不晋级；`goal_met: false` 只因步数/观察未凑够终产物 3×3；**该卡点经 24 步活体改判，见下第四节**（非 #47、非步数上限）。
2. **前提作废的范围**：作废的是「Windows 取不到任何可观察活 run」。**受控 Linux runner 仍然必需的是「改桥源码后重建出不同 digest 的 jar 并原子重封」**——现成 reviewed jar 只喂得了**未改源**的观察 run，喂不了改源后的重封。⇒ #47（桥侧 `craftable_recipe_ids` emit → 重建 → `bundle verify` → 四处原子重封）不受本轮影响，仍是有界接管单元、`bridge-1201/` 在 forbidden_paths、需主控点头。
3. **不重跑赌角度**：run1 没进 stall 就不刷 run 去凑；run2 是「放足同一确定性预算让本地链自然多走几轮」的一次尝试，非反复 rerun 碰运气。
4. **#46 非空失效**：两发 `recovery.invalidated []`（本发无陈旧项），代码层已覆盖、活体非空读数仍属反伪造保留口，勿造。

**关联**：#50 Core 半边 `461adba`+`00520e1`；#47 观察 schema 首片 `1ec49ae`；独占锁 `5ec8d29`。历史读数保留不动，本文只追加一枚 2026-10-02 的 Windows 活体观察。


## 四、追加（2026-10-02，同一 Windows 机、24 步活体）：把 3×3 终产物卡点从 #47 改判到 §5 堆叠原木再获取

用**产品自身允许的最大步数 24**（`--autonomous-steps` 硬上界 24，先前 40 被 CLI 以 `CONFIG / --autonomous-steps must be between 1 and 24` 拒起 exit 10）在同卷同 kin 再跑一发 `local_reflection`（`model_calls 0`、`MODEL_NOT_CONFIGURED`、`decision_source local_reflection`）。**链条与 run2 逐字节复现**（break→collect→板→close→棍→close→重瞄→break#2→collect→板→close→**工作台 CONFIRMED**→close→`select_hotbar slot6` 工作台「to stand it up」→重瞄→盲扫×3→`NO_FRESH_OBSERVATION`，run_id `e315379e…`，exit 0、`STOPPED_ON_REQUEST`、`input_release_failed false`、`recovery.invalidated []`）⇒ 确定性、非赌角度。

**由此坐实的改判（勿再凭旧记忆）：**
1. **终产物卡点不在 #47**：curated 合成表**已把 `minecraft:crafting_table` 判可行并 `craft_take_result` 活体 CONFIRMED**（第 12 代意图），随后 `select_hotbar` 把它拿到快捷栏准备放置。⇒ 旧账「3×3 终产物属 #47 世界 attested 面未凑够」**错**：世界 attested 根本不是这支链的前提，curated 半边足以造出台面。
2. **真正的终产物卡点在 §5 堆叠原木再获取**：世界只在 Kin 视线里堆**三根**原木（`domain.sh:198-205` + `run_controlled_server.py`）。木镐材料净算：3 原木→12 板，台面 4 + 棍配 2 + 镐 3 = 9 ≤ 12（有余量）⇒ **第三根原木物理可得且材料够**。但 `last_target_block` 记住的是**刚被砍空的那一格**（`player_mind.py:1154` 在 break 时记下待砍格，砍后即成空气）；`_reaim_at_resource` 一次性朝该空格中心转向（`player_mind.py:1252` 用后即清），准星穿过空格、**够不到堆叠里剩下的上一根原木** ⇒ 回落到盲扫 `look for the next thing`（第 16-18 代，`YAW_OUT_OF_RANGE` 观察被拒 17 次），未再 `break_seen_block`，先撞 `NO_FRESH_OBSERVATION`。
3. **不是步数上限**：本发 stop 是 `NO_FRESH_OBSERVATION` 而非 `STEP_BUDGET_SPENT`，且即便取产品最大 24 步、链条在第 15 代（砍第 2 根后的重瞄）就到同一堵墙 ⇒ 加步数不解决，问题在「回忆空格→够不到下一根」。

**为何不可单方安全修**：把回忆从「自报过的格」扩到「该格上方/相邻未自报的格」以确定命中堆叠里的下一根，正是 §5 冻结的玩家等价边界所禁的「探测准星从未自报的方块」＝chunk-scan 侧影，属**主控保留的 §5 决定**（用户先前授权的只是「回忆准星自报的那一格」这一窄形态）。改采集/放置次序也不能凭空变出第三块板——第三根原木必须先拿到。⇒ 这不再是一个可孤立落的 Core 补丁，而是一枚需要主控点头的**设计选择**：要么放宽 §5 到「允许对同一已见树干列做邻居回忆」，要么在活 run 里以产品允许的形态（如让 Kin 不因 collect 位移而丢失对堆叠的准星）使第三根可达。

**诚实边界**：本节是活体观察 + 读码定位（非凭记忆），无 `MINEKIN_DEMO_CASE`、不封证、不晋级；纠正的只是本文与旧账里「3×3 终产物属 #47」这一**现在时错报**，历史 run1/run2 读数与本文第二节对 #50 重瞄的正对照证明保留不动。

**关联**：#50 Core 半边 `461adba`+`00520e1`；#47 观察 schema 首片 `1ec49ae`（本轮证明它与木镐终产物**无关**，#47 只为**非 curated** 配方的世界 attested 而存在）；§5 边界见 `player_mind.py:883-885`。
