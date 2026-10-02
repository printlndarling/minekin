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

1. **这是活体观察 run，不是封证**：未传 `MINEKIN_DEMO_CASE`，不进 registry、不动门载荷、不晋级；`goal_met: false` 只因 18 步预算耗在终产物 3×3 立工作台（属 #47 世界 attested 面）未凑够，与 #50 断言无关。
2. **前提作废的范围**：作废的是「Windows 取不到任何可观察活 run」。**受控 Linux runner 仍然必需的是「改桥源码后重建出不同 digest 的 jar 并原子重封」**——现成 reviewed jar 只喂得了**未改源**的观察 run，喂不了改源后的重封。⇒ #47（桥侧 `craftable_recipe_ids` emit → 重建 → `bundle verify` → 四处原子重封）不受本轮影响，仍是有界接管单元、`bridge-1201/` 在 forbidden_paths、需主控点头。
3. **不重跑赌角度**：run1 没进 stall 就不刷 run 去凑；run2 是「放足同一确定性预算让本地链自然多走几轮」的一次尝试，非反复 rerun 碰运气。
4. **#46 非空失效**：两发 `recovery.invalidated []`（本发无陈旧项），代码层已覆盖、活体非空读数仍属反伪造保留口，勿造。

**关联**：#50 Core 半边 `461adba`+`00520e1`；#47 观察 schema 首片 `1ec49ae`；独占锁 `5ec8d29`。历史读数保留不动，本文只追加一枚 2026-10-02 的 Windows 活体观察。
