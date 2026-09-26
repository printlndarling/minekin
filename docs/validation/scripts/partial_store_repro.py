#!/usr/bin/env python
"""V1201-PARTIAL-STORE-AND-JOIN-SMOKE-001 — partial-store reproduction.

Drives the *shipped* launcher fetch/store code (minekin_core.adapters.launcher)
against the reviewed 1.20.1 offline recipe, on this lane's own data volume. It
does not reimplement blob handling: it interrupts a real download and then asks
the same code to resume, so the readings describe production behaviour.

Modes (run each in a fresh container over the same persistent volume):
  plan                 Print the offline-resolved fetch set (no network).
  interrupt N T        Fetch the first N artifacts, hard-kill at T seconds so a
                       real download is cut mid-flight (leaves committed blobs in
                       blobs/sha1 and stranded .staging/<uuid>/payload.part).
  snapshot             Report store state: committed blobs, .staging leftovers,
                       quarantine entries, and a per-artifact present/absent map
                       for the first N (N defaults to the last used count file).
  resume N             Re-fetch the same first N artifacts. Reports reused vs
                       installed vs failed, and cross-checks that every
                       committed+valid blob is reused (verify passed) while every
                       interrupted artifact is re-fetched — never misused.
  corrupt-coord IDX    Truncate committed blob #IDX, then re-verify it: proves a
                       damaged committed blob fails size/sha1 verify and is
                       re-downloaded instead of silently reused.

Run shape (host):
  docker run --rm -v <worktree>:/src:ro -v <scratch>:/scratch \
    -v minekin-v1201-smoke-v1:/data -e MINEKIN_HOME=/data \
    -e PYTHONPATH=/src/src --entrypoint python minekin-runner:local \
    /src/docs/validation/scripts/partial_store_repro.py <mode> [args]
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path

from minekin_core.adapters.launcher.artifacts import ArtifactStore
from minekin_core.adapters.launcher.fetch import ArtifactFetcher
from minekin_core.adapters.launcher.launch_plan import build_launch_plan
from minekin_core.adapters.launcher.provision import plan_fetch_set
from minekin_core.domain.errors import MinekinError

ROOT = Path("/src")
RECIPE = (ROOT / "tests/fixtures/runtime-input/bundle-candidate-1.20.1.json").resolve()
STATE = Path("/scratch/partial_store_state.json")


def load_context() -> tuple[dict, list, ArtifactStore]:
    plan = build_launch_plan(RECIPE, workspace_root=ROOT)
    store_root = Path("/data/kin/kin-v1smoke/run/artifact-store")
    store_root.mkdir(parents=True, exist_ok=True)
    store = ArtifactStore(store_root)
    return plan, list(plan_fetch_set(plan)), store


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {}


def save_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2))


def committed_blobs(store: ArtifactStore) -> list[str]:
    return sorted(
        p.relative_to(store.root).as_posix()
        for p in (store.blobs).rglob("*")
        if p.is_file()
    )


def staging_leftovers(store: ArtifactStore) -> dict:
    out = {}
    if store.staging.exists():
        for d in store.staging.iterdir():
            part = d / "payload.part"
            out[d.name] = part.stat().st_size if part.exists() else None
    return out


def quarantine_entries(store: ArtifactStore) -> list[str]:
    if not store.quarantine.exists():
        return []
    return sorted(d.name for d in store.quarantine.iterdir() if d.is_dir())


def main(argv: list[str]) -> int:
    mode = argv[1] if len(argv) > 1 else "plan"
    plan, artifacts, store = load_context()

    if mode == "plan":
        print(json.dumps({
            "plan_sha256": plan.get("plan_sha256"),
            "artifact_count": len(artifacts),
            "total_bytes": sum(a.size for a in artifacts),
        }, indent=2))
        return 0

    if mode == "snapshot":
        state = load_state()
        n = int(sys.argv[2]) if len(sys.argv) > 2 else state.get("n", 0)
        present = []
        for a in artifacts[:n]:
            try:
                store.verify(a)
                present.append(True)
            except MinekinError:
                present.append(False)
        print(json.dumps({
            "committed_blobs": len(committed_blobs(store)),
            "staging_leftovers": staging_leftovers(store),
            "quarantine": quarantine_entries(store),
            "first_n": n,
            "first_n_verified_present": sum(present),
            "first_n_missing": present.count(False),
        }, indent=2))
        return 0

    if mode == "interrupt":
        n = int(sys.argv[2]); delay = float(sys.argv[3])
        subset = artifacts[:n]
        save_state({"n": n, "subset_coords": [a.coordinate for a in subset]})

        def watchdog() -> None:
            time.sleep(delay)
            sys.stderr.write(f"WATCHDOG: hard-killing mid-download at {delay}s\n")
            sys.stderr.flush()
            os._exit(137)

        threading.Thread(target=watchdog, daemon=True).start()
        fetcher = ArtifactFetcher(store, jobs=8, timeout_s=10.0)
        fetcher.fetch(subset)  # never returns if watchdog fires
        print(json.dumps({"note": "completed before watchdog (raise N or lower T)",
                          **fetcher.fetch(subset).as_document()}, indent=2))
        return 0

    if mode == "resume":
        n = int(sys.argv[2])
        subset = artifacts[:n]
        # Pre-fetch present/absent map (what a naive 'is the file there' view sees).
        pre = {}
        for a in subset:
            path = store.path_for(a)
            try:
                store.verify(a)
                pre[a.coordinate] = "verified"
            except MinekinError:
                pre[a.coordinate] = "missing" if not path.exists() else "present-but-failed"
        fetcher = ArtifactFetcher(store, jobs=4, timeout_s=30.0)
        outcome = fetcher.fetch(subset)
        doc = outcome.as_document()
        doc["pre_fetch_map"] = {
            "verified": sum(1 for v in pre.values() if v == "verified"),
            "missing": sum(1 for v in pre.values() if v == "missing"),
            "present-but-failed": sum(1 for v in pre.values() if v == "present-but-failed"),
        }
        # Cross-check: everything that verified before must be reused, not reinstalled.
        verified_before = {c for c, v in pre.items() if v == "verified"}
        reused = set(outcome.reused)
        installed = set(outcome.installed)
        doc["reuse_invariant_holds"] = verified_before.issubset(reused) and not (verified_before & installed)
        doc["committed_after"] = len(committed_blobs(store))
        doc["staging_after"] = staging_leftovers(store)
        print(json.dumps(doc, indent=2))
        return 0

    if mode == "corrupt-coord":
        idx = int(sys.argv[2])
        a = artifacts[idx]
        store.verify(a)  # must be present & valid first
        path = store.path_for(a)
        before = path.stat().st_mode
        path.chmod(before | stat_write())
        data = path.read_bytes()
        path.write_bytes(data[: max(0, len(data) - 512)])  # truncate -> size+sha1 break
        verdict = {}
        try:
            store.verify(a)
            verdict["verify_after_corrupt"] = "PASSED (BAD: corrupted blob accepted)"
            verdict["false_reuse"] = True
        except MinekinError as e:
            verdict["verify_after_corrupt"] = f"REJECTED ({e.safe_message})"
            verdict["false_reuse"] = False
        # Now let the fetcher decide against the damaged, still-present blob.
        fetcher = ArtifactFetcher(store, jobs=1, timeout_s=30.0)
        out = fetcher.fetch([a]).as_document()
        verdict["outcome_with_blob_present"] = out
        # Hypothesis under test: install() early-returns when target.exists(), so a
        # present-but-damaged blob is a hard failure that the fetcher cannot self-heal.
        verdict["present_but_corrupt_self_heals"] = out["installed"] == 1 and out["complete"]
        # Recovery: remove the damaged blob, then the same fetch must re-download it.
        path.unlink()
        out2 = ArtifactFetcher(store, jobs=1, timeout_s=30.0).fetch([a]).as_document()
        verdict["outcome_after_removal"] = out2
        verdict["recovers_once_removed"] = out2["installed"] == 1 and out2["reused"] == 0 and out2["complete"]
        # A third pass must now reuse the freshly fetched, valid blob (idempotent).
        out3 = ArtifactFetcher(store, jobs=1, timeout_s=30.0).fetch([a]).as_document()
        verdict["third_pass_reuses"] = out3["reused"] == 1 and out3["complete"]
        print(json.dumps({"coordinate": a.coordinate, "truncated_bytes_removed": 512, **verdict}, indent=2))
        return 0

    print(f"unknown mode: {mode}", file=sys.stderr)
    return 2


def stat_write() -> int:
    import stat as _s
    return _s.S_IWUSR


if __name__ == "__main__":
    sys.exit(main(sys.argv))
