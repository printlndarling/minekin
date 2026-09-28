/**
 * Verbatim bytes the real `gateway/readmodel.py` produced (key-sorted captures), never
 * mocks or hand-written shapes. The decoder and the panels are designed against these
 * bytes, not against a guess of the wire shape.
 *
 * Two generations live here on purpose:
 * - `REAL_JOINED_RUN_SNAPSHOT_WIRE` and `REAL_TIMELINE_WIRE` are the historical capture
 *   taken before §2.96 changed the link derivation, so both links answer `disconnected`
 *   and `runtimeState` is `unresolved`. They stay as the record of what that build sent.
 * - `REAL_IN_SESSION_*` / `REAL_AFTER_SESSION_*` are the current capture (§2.97) taken off
 *   the live gateway during a real 1.20.1 LAN demo session and again after teardown, so
 *   the same fields answer `connected` / `idle` while the Kin is in the world.
 */
export const REAL_JOINED_RUN_SNAPSHOT_WIRE: Record<string, unknown> = {
  bridgeHeartbeat: {
    observedAt: "2000-01-01T00:00:00Z",
    sourceRef: "core://status/kin-01/bridgeHeartbeat",
    staleAfterMs: null,
    status: "known",
    value: {
      inputLeaseHeld: { value: false },
      intervalMs: { value: 500 },
      lastObservedAt: { value: "2000-01-01T00:00:00Z" },
      lastSequence: {
        gap: {
          reason: "ControlHeartbeat 只有 generation 与 monotonic_ns；台账 position 是记账顺序，不是桥的计数器。",
          status: "not_wired",
        },
      },
    },
  },
  bridgeLink: {
    observedAt: "2000-01-01T00:00:00Z",
    sourceRef: "core://status/kin-01/bridge_link",
    staleAfterMs: 8000,
    status: "known",
    value: "disconnected",
  },
  evidence: {
    observedAt: null,
    reason: "本 run 还没有已封的证据 bundle：封证只在 case 判定之后写入。",
    sourceRef: "core://status/kin-01/evidence",
    staleAfterMs: null,
    status: "unknown",
    value: null,
  },
  kinId: {
    observedAt: "2000-01-01T00:00:00Z",
    sourceRef: "core://status/kin-01/kin_id",
    staleAfterMs: 8000,
    status: "known",
    value: "kin-01",
  },
  liveView: {
    observedAt: null,
    reason: "没有 framebuffer 采集与媒体中继进程，画面这一面不存在。",
    sourceRef: "core://status/kin-01/liveView",
    staleAfterMs: null,
    status: "not_wired",
    value: null,
  },
  runtimeState: {
    observedAt: "2000-01-01T00:00:00Z",
    sourceRef: "core://status/kin-01/state",
    staleAfterMs: 8000,
    status: "known",
    value: "unresolved",
  },
  schemaVersion: "kin-dashboard-readmodel/1.0.0",
  selfState: {
    observedAt: null,
    reason: "Core 不落相干性快照行：health/food 只在会话内存里，只读投影取不到。",
    sourceRef: "core://status/kin-01/selfState",
    staleAfterMs: null,
    status: "unavailable",
    value: null,
  },
  serverLink: {
    observedAt: "2000-01-01T00:00:00Z",
    sourceRef: "core://status/kin-01/server_link",
    staleAfterMs: 8000,
    status: "known",
    value: "disconnected",
  },
  session: {
    observedAt: "2000-01-01T00:00:00Z",
    sourceRef: "core://status/kin-01/session",
    staleAfterMs: null,
    status: "known",
    value: {
      generation: { value: 1 },
      mode: {
        gap: {
          reason: "Core 尚无会话模式枚举（A_companion/B_standalone 属产品决定）。",
          status: "not_wired",
        },
      },
      overlay: { value: "D:\\\\Temp\\\\shape-fqypyrza\\\\kin\\\\kin-01\\\\run\\\\session\\\\e14d02e5f33e48ecb3b23bc6f17418d9\\\\generation-1" },
      pid: { value: 4242 },
      sessionId: { value: "e14d02e5f33e48ecb3b23bc6f17418d9" },
      startedAt: { value: "2000-01-01T00:00:00Z" },
    },
  },
  versions: {
    observedAt: null,
    reason: "本 run 还没有已封的证据 bundle：封证只在 case 判定之后写入。 版本五件套没有统一读接口，只有已封 bundle 的清单能答其中三个。",
    sourceRef: "core://status/kin-01/versions",
    staleAfterMs: null,
    status: "unavailable",
    value: null,
  },
  world: {
    observedAt: "2000-01-01T00:00:00Z",
    sourceRef: "core://status/kin-01/world",
    staleAfterMs: null,
    status: "known",
    value: {
      epoch: {
        gap: { reason: "同 worldContext：世界坐标类信息的可见性未裁决。", status: "not_wired" },
      },
      joined: { value: true },
      profileId: { value: "srv-profile-00000000000000000000" },
      profileName: {
        gap: { reason: "Core 只记 profile 的 id 与 revision，没有具名显示名载体。", status: "not_wired" },
      },
      resolvedVersion: { gap: { reason: "Core 无 resolvedVersion 具名载体。", status: "not_wired" } },
      worldContext: {
        gap: {
          reason: "world_context_id 的可见性属主控/产品决定（契约 §8），只读面不替它作答。",
          status: "not_wired",
        },
      },
    },
  },
};

/**
 * A verbatim capture taken from the running 1.20.1 LAN demo while the operated
 * session was still in the world — not a mock. Read off the live gateway
 * (kin-lan87b-join, session 8b53ac5ad74648edab87e196d496b8d0, pid 382, joiner run
 * c131e8e782954991bf13d2c2ba4c1742 of demo run 05f0532772b44812998a860bb797f515,
 * §2.97) after §2.96 landed, so both links answer `connected` from the ledger rows
 * and `world.joined` is true. `runtimeState` stays `idle` and the lease stays
 * false because the operated process lives in another container: those two are the
 * named gaps §2.96.6 leaves open, reproduced here rather than smoothed over.
 */
export const REAL_IN_SESSION_SNAPSHOT_WIRE: Record<string, unknown> = {
    "bridgeHeartbeat": {
      "observedAt": "2026-09-28T18:35:42.513836Z",
      "sourceRef": "core://status/kin-lan87b-join/bridgeHeartbeat",
      "staleAfterMs": null,
      "status": "known",
      "value": {
        "inputLeaseHeld": {
          "value": false
        },
        "intervalMs": {
          "value": 500
        },
        "lastObservedAt": {
          "value": "2026-09-28T18:35:42.513836Z"
        },
        "lastSequence": {
          "gap": {
            "reason": "ControlHeartbeat \u53ea\u6709 generation \u4e0e monotonic_ns\uff1b\u53f0\u8d26 position \u662f\u8bb0\u8d26\u987a\u5e8f\uff0c\u4e0d\u662f\u6865\u7684\u8ba1\u6570\u5668\u3002",
            "status": "not_wired"
          }
        }
      }
    },
    "bridgeLink": {
      "observedAt": "2026-09-28T18:35:24.662727Z",
      "sourceRef": "core://status/kin-lan87b-join/bridge_link",
      "staleAfterMs": 8000,
      "status": "known",
      "value": "connected"
    },
    "evidence": {
      "observedAt": null,
      "reason": "\u672c run \u8fd8\u6ca1\u6709\u5df2\u5c01\u7684\u8bc1\u636e bundle\uff1a\u5c01\u8bc1\u53ea\u5728 case \u5224\u5b9a\u4e4b\u540e\u5199\u5165\u3002",
      "sourceRef": "core://status/kin-lan87b-join/evidence",
      "staleAfterMs": null,
      "status": "unknown",
      "value": null
    },
    "kinId": {
      "observedAt": "2026-09-28T18:36:00.828247Z",
      "sourceRef": "core://status/kin-lan87b-join/kin_id",
      "staleAfterMs": 8000,
      "status": "known",
      "value": "kin-lan87b-join"
    },
    "liveView": {
      "observedAt": null,
      "reason": "\u6ca1\u6709 framebuffer \u91c7\u96c6\u4e0e\u5a92\u4f53\u4e2d\u7ee7\u8fdb\u7a0b\uff0c\u753b\u9762\u8fd9\u4e00\u9762\u4e0d\u5b58\u5728\u3002",
      "sourceRef": "core://status/kin-lan87b-join/liveView",
      "staleAfterMs": null,
      "status": "not_wired",
      "value": null
    },
    "runtimeState": {
      "observedAt": "2026-09-28T18:36:00.828247Z",
      "sourceRef": "core://status/kin-lan87b-join/state",
      "staleAfterMs": 8000,
      "status": "known",
      "value": "idle"
    },
    "schemaVersion": "kin-dashboard-readmodel/1.0.0",
    "selfState": {
      "observedAt": null,
      "reason": "Core \u4e0d\u843d\u76f8\u5e72\u6027\u5feb\u7167\u884c\uff1ahealth/food \u53ea\u5728\u4f1a\u8bdd\u5185\u5b58\u91cc\uff0c\u53ea\u8bfb\u6295\u5f71\u53d6\u4e0d\u5230\u3002",
      "sourceRef": "core://status/kin-lan87b-join/selfState",
      "staleAfterMs": null,
      "status": "unavailable",
      "value": null
    },
    "serverLink": {
      "observedAt": "2026-09-28T18:35:40.456173Z",
      "sourceRef": "core://status/kin-lan87b-join/server_link",
      "staleAfterMs": 8000,
      "status": "known",
      "value": "connected"
    },
    "session": {
      "observedAt": "2026-09-28T18:35:02.425756Z",
      "sourceRef": "core://status/kin-lan87b-join/session",
      "staleAfterMs": null,
      "status": "known",
      "value": {
        "generation": {
          "value": 1
        },
        "mode": {
          "gap": {
            "reason": "Core \u5c1a\u65e0\u4f1a\u8bdd\u6a21\u5f0f\u679a\u4e3e\uff08A_companion/B_standalone \u5c5e\u4ea7\u54c1\u51b3\u5b9a\uff09\u3002",
            "status": "not_wired"
          }
        },
        "overlay": {
          "value": "/data/kin/kin-lan87b-join/run/session/8b53ac5ad74648edab87e196d496b8d0/generation-1"
        },
        "pid": {
          "value": 382
        },
        "sessionId": {
          "value": "8b53ac5ad74648edab87e196d496b8d0"
        },
        "startedAt": {
          "value": "2026-09-28T18:35:02.425756Z"
        }
      }
    },
    "versions": {
      "observedAt": null,
      "reason": "\u672c run \u8fd8\u6ca1\u6709\u5df2\u5c01\u7684\u8bc1\u636e bundle\uff1a\u5c01\u8bc1\u53ea\u5728 case \u5224\u5b9a\u4e4b\u540e\u5199\u5165\u3002 \u7248\u672c\u4e94\u4ef6\u5957\u6ca1\u6709\u7edf\u4e00\u8bfb\u63a5\u53e3\uff0c\u53ea\u6709\u5df2\u5c01 bundle \u7684\u6e05\u5355\u80fd\u7b54\u5176\u4e2d\u4e09\u4e2a\u3002",
      "sourceRef": "core://status/kin-lan87b-join/versions",
      "staleAfterMs": null,
      "status": "unavailable",
      "value": null
    },
    "world": {
      "observedAt": "2026-09-28T18:35:02.393310Z",
      "sourceRef": "core://status/kin-lan87b-join/world",
      "staleAfterMs": null,
      "status": "known",
      "value": {
        "epoch": {
          "gap": {
            "reason": "\u540c worldContext\uff1a\u4e16\u754c\u5750\u6807\u7c7b\u4fe1\u606f\u7684\u53ef\u89c1\u6027\u672a\u88c1\u51b3\u3002",
            "status": "not_wired"
          }
        },
        "joined": {
          "value": true
        },
        "profileId": {
          "value": "p0-lan-host-fixture"
        },
        "profileName": {
          "gap": {
            "reason": "Core \u53ea\u8bb0 profile \u7684 id \u4e0e revision\uff0c\u6ca1\u6709\u5177\u540d\u663e\u793a\u540d\u8f7d\u4f53\u3002",
            "status": "not_wired"
          }
        },
        "resolvedVersion": {
          "gap": {
            "reason": "Core \u65e0 resolvedVersion \u5177\u540d\u8f7d\u4f53\u3002",
            "status": "not_wired"
          }
        },
        "worldContext": {
          "gap": {
            "reason": "world_context_id \u7684\u53ef\u89c1\u6027\u5c5e\u4e3b\u63a7/\u4ea7\u54c1\u51b3\u5b9a\uff08\u5951\u7ea6 \u00a78\uff09\uff0c\u53ea\u8bfb\u9762\u4e0d\u66ff\u5b83\u4f5c\u7b54\u3002",
            "status": "not_wired"
          }
        }
      }
    }
};

/**
 * The same Kin root read again after that demo sealed its evidence and tore the
 * session down, so the closing rows are the newest ones the ledger holds: both
 * links fall back to `disconnected`, `world.joined` is false, and `evidence`/
 * `versions` now answer from the sealed manifest. Paired with
 * REAL_IN_SESSION_SNAPSHOT_WIRE this keeps the link assertions non-vacuous — the
 * two bodies really differ in the row-order-derived fields.
 */
export const REAL_AFTER_SESSION_SNAPSHOT_WIRE: Record<string, unknown> = {
    "bridgeHeartbeat": {
      "observedAt": "2026-09-28T18:38:18.718119Z",
      "sourceRef": "core://status/kin-lan87b-join/bridgeHeartbeat",
      "staleAfterMs": null,
      "status": "known",
      "value": {
        "inputLeaseHeld": {
          "value": false
        },
        "intervalMs": {
          "value": 500
        },
        "lastObservedAt": {
          "value": "2026-09-28T18:38:18.718119Z"
        },
        "lastSequence": {
          "gap": {
            "reason": "ControlHeartbeat \u53ea\u6709 generation \u4e0e monotonic_ns\uff1b\u53f0\u8d26 position \u662f\u8bb0\u8d26\u987a\u5e8f\uff0c\u4e0d\u662f\u6865\u7684\u8ba1\u6570\u5668\u3002",
            "status": "not_wired"
          }
        }
      }
    },
    "bridgeLink": {
      "observedAt": "2026-09-28T18:38:18.718119Z",
      "sourceRef": "core://status/kin-lan87b-join/bridge_link",
      "staleAfterMs": 8000,
      "status": "known",
      "value": "disconnected"
    },
    "evidence": {
      "observedAt": "2026-09-28T18:39:00.552558Z",
      "sourceRef": "bundle://c131e8e782954991bf13d2c2ba4c1742/manifest.json",
      "staleAfterMs": null,
      "status": "known",
      "value": {
        "attempt": {
          "value": 7
        },
        "bundleDigest": {
          "value": "ae6a52e4536d6168edad88bdbdc4117e32806e0e21a271106fcbdcd5425e9472"
        },
        "runId": {
          "value": "c131e8e782954991bf13d2c2ba4c1742"
        },
        "sealedAt": {
          "gap": {
            "reason": "manifest.json \u6ca1\u6709\u5177\u540d\u5bc6\u5c01\u65f6\u95f4\u5b57\u6bb5\uff1bsealed_at_utc \u53ea\u5728\u5c01\u8bc1\u5de5\u5177\u7684\u62a5\u544a\u91cc\u3002",
            "status": "not_wired"
          }
        }
      }
    },
    "kinId": {
      "observedAt": "2026-09-28T18:39:00.552558Z",
      "sourceRef": "core://status/kin-lan87b-join/kin_id",
      "staleAfterMs": 8000,
      "status": "known",
      "value": "kin-lan87b-join"
    },
    "liveView": {
      "observedAt": null,
      "reason": "\u6ca1\u6709 framebuffer \u91c7\u96c6\u4e0e\u5a92\u4f53\u4e2d\u7ee7\u8fdb\u7a0b\uff0c\u753b\u9762\u8fd9\u4e00\u9762\u4e0d\u5b58\u5728\u3002",
      "sourceRef": "core://status/kin-lan87b-join/liveView",
      "staleAfterMs": null,
      "status": "not_wired",
      "value": null
    },
    "runtimeState": {
      "observedAt": "2026-09-28T18:39:00.552558Z",
      "sourceRef": "core://status/kin-lan87b-join/state",
      "staleAfterMs": 8000,
      "status": "known",
      "value": "idle"
    },
    "schemaVersion": "kin-dashboard-readmodel/1.0.0",
    "selfState": {
      "observedAt": null,
      "reason": "Core \u4e0d\u843d\u76f8\u5e72\u6027\u5feb\u7167\u884c\uff1ahealth/food \u53ea\u5728\u4f1a\u8bdd\u5185\u5b58\u91cc\uff0c\u53ea\u8bfb\u6295\u5f71\u53d6\u4e0d\u5230\u3002",
      "sourceRef": "core://status/kin-lan87b-join/selfState",
      "staleAfterMs": null,
      "status": "unavailable",
      "value": null
    },
    "serverLink": {
      "observedAt": "2026-09-28T18:38:18.718119Z",
      "sourceRef": "core://status/kin-lan87b-join/server_link",
      "staleAfterMs": 8000,
      "status": "known",
      "value": "disconnected"
    },
    "session": {
      "observedAt": "2026-09-28T18:35:02.425756Z",
      "sourceRef": "core://status/kin-lan87b-join/session",
      "staleAfterMs": null,
      "status": "known",
      "value": {
        "generation": {
          "value": 1
        },
        "mode": {
          "gap": {
            "reason": "Core \u5c1a\u65e0\u4f1a\u8bdd\u6a21\u5f0f\u679a\u4e3e\uff08A_companion/B_standalone \u5c5e\u4ea7\u54c1\u51b3\u5b9a\uff09\u3002",
            "status": "not_wired"
          }
        },
        "overlay": {
          "value": "/data/kin/kin-lan87b-join/run/session/8b53ac5ad74648edab87e196d496b8d0/generation-1"
        },
        "pid": {
          "value": 382
        },
        "sessionId": {
          "value": "8b53ac5ad74648edab87e196d496b8d0"
        },
        "startedAt": {
          "value": "2026-09-28T18:35:02.425756Z"
        }
      }
    },
    "versions": {
      "observedAt": "2026-09-28T18:39:00.552558Z",
      "sourceRef": "core://status/kin-lan87b-join/versions",
      "staleAfterMs": null,
      "status": "known",
      "value": {
        "bridge": {
          "gap": {
            "reason": "\u6e05\u5355\u53ea\u9489 bridge_digest\uff08\u4e00\u679a\u6458\u8981\uff09\uff0c\u6ca1\u6709\u6865\u7248\u672c\u4e32\u8f7d\u4f53\u3002",
            "status": "not_wired"
          }
        },
        "clientBundle": {
          "gap": {
            "reason": "\u6e05\u5355\u8bb0 minecraft/loader/java \u7248\u672c\uff0c\u6ca1\u6709 bundle \u540d\u6216 bundle \u7248\u672c\u5b57\u6bb5\u3002",
            "status": "not_wired"
          }
        },
        "fabricLoader": {
          "value": "0.19.5"
        },
        "java": {
          "value": "openjdk version \"21.0.12.1\" 2026-08-18 LTS / OpenJDK Runtime Environment Temurin-21.0.12.1+1 (build 21.0.12.1+1-LTS)"
        },
        "runtime": {
          "value": "1.20.1"
        }
      }
    },
    "world": {
      "observedAt": "2026-09-28T18:35:02.393310Z",
      "sourceRef": "core://status/kin-lan87b-join/world",
      "staleAfterMs": null,
      "status": "known",
      "value": {
        "epoch": {
          "gap": {
            "reason": "\u540c worldContext\uff1a\u4e16\u754c\u5750\u6807\u7c7b\u4fe1\u606f\u7684\u53ef\u89c1\u6027\u672a\u88c1\u51b3\u3002",
            "status": "not_wired"
          }
        },
        "joined": {
          "value": false
        },
        "profileId": {
          "value": "p0-lan-host-fixture"
        },
        "profileName": {
          "gap": {
            "reason": "Core \u53ea\u8bb0 profile \u7684 id \u4e0e revision\uff0c\u6ca1\u6709\u5177\u540d\u663e\u793a\u540d\u8f7d\u4f53\u3002",
            "status": "not_wired"
          }
        },
        "resolvedVersion": {
          "gap": {
            "reason": "Core \u65e0 resolvedVersion \u5177\u540d\u8f7d\u4f53\u3002",
            "status": "not_wired"
          }
        },
        "worldContext": {
          "gap": {
            "reason": "world_context_id \u7684\u53ef\u89c1\u6027\u5c5e\u4e3b\u63a7/\u4ea7\u54c1\u51b3\u5b9a\uff08\u5951\u7ea6 \u00a78\uff09\uff0c\u53ea\u8bfb\u9762\u4e0d\u66ff\u5b83\u4f5c\u7b54\u3002",
            "status": "not_wired"
          }
        }
      }
    }
};

/**
 * The live gateway's newest 15 rows inside that session window,
 * each verbatim, newest first (cut from the 50-row capture at the launch row).
 * The cut keeps `SessionProcessStarted`, which is what lets the session-progress
 * panel pin this single attempt instead of answering 无法锚定到单次会话.
 */
export const REAL_IN_SESSION_TIMELINE_WIRE: readonly Record<string, unknown>[] = [
    {
      "at": "2026-09-28T18:35:42.513836Z",
      "detail": "reason=TIMEOUT",
      "eventId": "8ed38f9fa63b4a8ca1fcf83a70f7bb43",
      "generation": 1,
      "kind": "input",
      "monotonicMs": null,
      "outcome": "released",
      "sequence": 18,
      "sourceRef": "ledger://kin-lan87b-join/143",
      "title": "InputReleased"
    },
    {
      "at": "2026-09-28T18:35:40.580284Z",
      "detail": "capability=control.look.v1",
      "eventId": "b6d12b914a904d7bb34ea4ff77826857",
      "generation": 1,
      "kind": "input",
      "monotonicMs": null,
      "outcome": "applied",
      "sequence": 17,
      "sourceRef": "ledger://kin-lan87b-join/142",
      "title": "InputLeaseGranted"
    },
    {
      "at": "2026-09-28T18:35:40.518599Z",
      "detail": "capability=control.move.v1",
      "eventId": "b451b8588ffc4c2eb922f018a6cc41c1",
      "generation": 1,
      "kind": "input",
      "monotonicMs": null,
      "outcome": "applied",
      "sequence": 16,
      "sourceRef": "ledger://kin-lan87b-join/141",
      "title": "InputLeaseGranted"
    },
    {
      "at": "2026-09-28T18:35:40.456173Z",
      "detail": "phase=PLAYABLE",
      "eventId": "18c3eb833c9d4940873d52e7ef433f1f",
      "generation": 1,
      "kind": "session",
      "monotonicMs": null,
      "outcome": "applied",
      "sequence": 15,
      "sourceRef": "ledger://kin-lan87b-join/140",
      "title": "PlayableEstablished"
    },
    {
      "at": "2026-09-28T18:35:40.425509Z",
      "detail": "from=JOINED_UNVERIFIED, to=PLAYABLE",
      "eventId": "a59ce98e25304e1fb2dfe1e99194651c",
      "generation": 1,
      "kind": "session",
      "monotonicMs": null,
      "outcome": "applied",
      "sequence": 14,
      "sourceRef": "ledger://kin-lan87b-join/139",
      "title": "SessionStateTransitioned"
    },
    {
      "at": "2026-09-28T18:35:40.378724Z",
      "detail": "session_username=Kin2, session_uuid=20d2112d-ecc9-3e0b-a7f4-5b830b9e6451, matched=True, client_id_present=False, xuid_present=False, credential_values_exposed=False",
      "eventId": "e7b12ddadc934b3580738b4b3c7cde76",
      "generation": 1,
      "kind": "observation",
      "monotonicMs": null,
      "outcome": "applied",
      "sequence": 13,
      "sourceRef": "ledger://kin-lan87b-join/138",
      "title": "SessionIdentityCompared"
    },
    {
      "at": "2026-09-28T18:35:37.735895Z",
      "detail": "phase=JOIN_SEEN",
      "eventId": "c95c6e5fd08d44c184d9c9327255d9b0",
      "generation": 1,
      "kind": "server_feedback",
      "monotonicMs": null,
      "outcome": "applied",
      "sequence": 12,
      "sourceRef": "ledger://kin-lan87b-join/137",
      "title": "JoinObserved"
    },
    {
      "at": "2026-09-28T18:35:37.693612Z",
      "detail": "from=CONNECTING, to=JOINED_UNVERIFIED",
      "eventId": "a9c774458fac4191a89fb755dae8d7ae",
      "generation": 1,
      "kind": "session",
      "monotonicMs": null,
      "outcome": "applied",
      "sequence": 11,
      "sourceRef": "ledger://kin-lan87b-join/136",
      "title": "SessionStateTransitioned"
    },
    {
      "at": "2026-09-28T18:35:32.809124Z",
      "detail": "from=READY_MENU, to=CONNECTING",
      "eventId": "0b9e02fb95a848cdb0088321eded109c",
      "generation": 1,
      "kind": "session",
      "monotonicMs": null,
      "outcome": "applied",
      "sequence": 10,
      "sourceRef": "ledger://kin-lan87b-join/135",
      "title": "SessionStateTransitioned"
    },
    {
      "at": "2026-09-28T18:35:32.786036Z",
      "detail": "resource_pack_policy=deny",
      "eventId": "d701e45e400f497d97f4b2df3ad400f3",
      "generation": 1,
      "kind": "decision",
      "monotonicMs": null,
      "outcome": "applied",
      "sequence": 9,
      "sourceRef": "ledger://kin-lan87b-join/134",
      "title": "ResourcePackPolicyApplied"
    },
    {
      "at": "2026-09-28T18:35:24.697375Z",
      "detail": "from=HANDSHAKING, to=READY_MENU",
      "eventId": "3fb7bba4a0af4542a46915b32372e27a",
      "generation": 1,
      "kind": "session",
      "monotonicMs": null,
      "outcome": "applied",
      "sequence": 8,
      "sourceRef": "ledger://kin-lan87b-join/133",
      "title": "SessionStateTransitioned"
    },
    {
      "at": "2026-09-28T18:35:24.662727Z",
      "detail": null,
      "eventId": "70bf7759d47f4d77985ae5901df800de",
      "generation": 1,
      "kind": "session",
      "monotonicMs": null,
      "outcome": "applied",
      "sequence": 7,
      "sourceRef": "ledger://kin-lan87b-join/132",
      "title": "BridgeHelloAccepted"
    },
    {
      "at": "2026-09-28T18:35:02.474118Z",
      "detail": "from=WAITING_BRIDGE, to=HANDSHAKING",
      "eventId": "bdb7628ad0f34cb0bca03e9579cca376",
      "generation": 1,
      "kind": "session",
      "monotonicMs": null,
      "outcome": "applied",
      "sequence": 6,
      "sourceRef": "ledger://kin-lan87b-join/131",
      "title": "SessionStateTransitioned"
    },
    {
      "at": "2026-09-28T18:35:02.453109Z",
      "detail": "from=STARTING_CLIENT, to=WAITING_BRIDGE",
      "eventId": "f45e38a452464ee79a3fed44f3d86882",
      "generation": 1,
      "kind": "session",
      "monotonicMs": null,
      "outcome": "applied",
      "sequence": 5,
      "sourceRef": "ledger://kin-lan87b-join/130",
      "title": "SessionStateTransitioned"
    },
    {
      "at": "2026-09-28T18:35:02.425756Z",
      "detail": null,
      "eventId": "eaea4cec0b5844f98eaff4a70771d359",
      "generation": 1,
      "kind": "session",
      "monotonicMs": null,
      "outcome": "applied",
      "sequence": 4,
      "sourceRef": "ledger://kin-lan87b-join/129",
      "title": "SessionProcessStarted"
    }
];

/** The alerts read `gateway/readmodel.py::alerts_payload` answers today (§5.3). */
export const REAL_ALERTS_ENVELOPE_WIRE: Record<string, unknown> = {
  status: "not_wired",
  reason: "Core 无告警源：只有台账事件与 run document 的拒止计数，哪些算告警属产品决定。",
  observedAt: "2000-01-01T00:00:00Z",
  sourceRef: "core://status/kin-01/alerts",
  alerts: [],
};

/** Two rows in the shape `gateway/readmodel.py::build_timeline` answers. */
export const REAL_TIMELINE_WIRE: readonly Record<string, unknown>[] = [
  {
    eventId: "evt-2",
    kind: "session",
    at: "2000-01-01T00:00:05Z",
    monotonicMs: null,
    generation: 1,
    sequence: null,
    title: "ClientProcessExited",
    detail: null,
    outcome: "unknown",
    sourceRef: "ledger://kin-01/42",
  },
  {
    eventId: "evt-1",
    kind: "session",
    at: "2000-01-01T00:00:00Z",
    monotonicMs: null,
    generation: 1,
    sequence: null,
    title: "SessionProcessStarted",
    detail: "argv_digest=abc123, phase=launch",
    outcome: "applied",
    sourceRef: "ledger://kin-01/41",
  },
];

export interface LedgerRowSpec {
  readonly title: string;
  readonly kind: string;
  readonly outcome: string;
  readonly detail?: string | null;
}

/**
 * One attempt's worth of rows in the shape `build_timeline` answers, newest first.
 *
 * The field set, the enum values and the `ledger://{kin_id}/{position}` reference are
 * the shipped ones; only the row sequence is chosen here, so a case can describe more
 * than the two-row capture above holds. `specs` is oldest first and positions ascend
 * with it, which is what the attempt pinning reads.
 */
export function gatewayLedgerWires(specs: readonly LedgerRowSpec[], firstPosition = 41): Record<string, unknown>[] {
  const origin = Date.parse("2000-01-01T00:00:00Z");
  return specs
    .map((spec, index) => {
      const position = firstPosition + index;
      return {
        eventId: `evt-${position}`,
        kind: spec.kind,
        at: new Date(origin + position * 1_000).toISOString(),
        monotonicMs: null,
        generation: 1,
        sequence: null,
        title: spec.title,
        detail: spec.detail ?? null,
        outcome: spec.outcome,
        sourceRef: `ledger://kin-01/${position}`,
      };
    })
    .reverse();
}
