# H1f — the joiner profile's version comes from the run (2026-09-27)

Lane: H (test harness). Card: `minekin-joiner-version-from-run`.
Branch: `codex/minekin-joiner-version-from-run`, base = `ea97c5c44ec5f3ac9a6a16274648cc52a4dccbfe`
(verified: `git merge-base HEAD origin/main` → `ea97c5c44ec5f3ac9a6a16274648cc52a4dccbfe`).

## What was wrong, in one paragraph

`test-orchestrator/runner/domain.sh` wrote the joining second client's LAN profile
(`/tmp/domain-join-profile.json`) from a hardcoded Python dict whose
`minecraft_version` was the literal `"1.21.4"` (base bytes, lines 728-745). The server's
own version was *not* a constant: `launched_version` is read from the bundle profile's
recipe at the top of the script (base line 413 onward) and handed to
`tools/run_controlled_server.py` through `version_args` (base lines 456-458, 579-583).
So a run that started a 1.20.1 server handed its joiner a profile claiming 1.21.4 —
which is why V's V1/V2 records could not reproduce *or* exclude the ⑤-family client
endings (`GLFW 0x1000E`, `XDG_RUNTIME_DIR`) on the 1.20.1 side: the joiner's profile
described a different world than the one it dialed.

## Change surface

```
$ git diff ea97c5c..HEAD --stat   (implementation commit 02a8b4b)
 test-orchestrator/runner/domain.sh    |  20 +++-
 tests/contract/test_runner_scripts.py | 184 ++++++++++++++++++++++++++++++++++
 2 files changed, 201 insertions(+), 3 deletions(-)
```

- `test-orchestrator/runner/domain.sh` (+17/-3): the
  writer call now passes `"${launched_version}"` as a third argument, the dict entry is
  `"minecraft_version": version,`, and a named refusal gate stands immediately above it
  (shape copied from the `domain.sh:400-407` auto+joiner refusal: stderr line + `exit 2`).
  No constant remains to fall back to.
- `tests/contract/test_runner_scripts.py`: two new tests —
  `test_the_joiner_profile_version_comes_from_the_run` and
  `test_the_joiner_version_contract_is_not_an_always_true_claim` — plus the predicates
  `joiner_profile_version_comes_from_the_run()` / `joiner_version_refusal_is_named()` and
  the byte constants `JOINER_PROFILE_WRITER` / `JOINER_VERSION_REFUSAL`.
- This record.

Hard boundaries kept: the auto+joiner refusal (now lines 404-407) is untouched and still
asserted by the new test as unchanged; `src/**`, `tools/**`, fixtures, registry,
manifests, case criteria and M's doc surface were not touched. Nothing was sealed; the
spec volume `minekin-runner-data` was never mounted at all by these probes (they need no
`/data`), and no container used it.

## Probe method (used by acceptances 1, 3, 4)

`.tmp/h1f-joiner-probe.sh` (scratch, uncommitted, gitignored): extracts the shipped
joiner-profile section **verbatim** from a given `domain.sh` — from the refusal gate if
present, else the base writer line, through the terminating `PY` — prints the extracted
bytes, then sources them in a subshell with `lan_port=25565` and a chosen
`launched_version`, and dumps `/tmp/domain-join-profile.json`. It runs inside the
controlled image (`minekin-runner:local`) with the repo mounted read-only:

```
REPO=$(pwd -W)
MSYS2_ARG_CONV_EXCL='*' docker run --rm -v "${REPO}:/src:ro" minekin-runner:local \
    bash /src/.tmp/h1f-joiner-probe.sh <domain.sh> <launched_version|NONE>
```

## Acceptance 1 — load-bearing readings, before and after

**Before (base bytes at `.tmp/h1f/base-domain.sh` = `git show ea97c5c:test-orchestrator/runner/domain.sh`),
run holding the 1.20.1 version the recipe read would carry:**

```
$ ... docker run ... bash /src/.tmp/h1f-joiner-probe.sh /src/.tmp/h1f/base-domain.sh 1.20.1
extracted lines 728-745 of /src/.tmp/h1f/base-domain.sh
==== extracted block (shipped bytes, verbatim) ====
    python - "${lan_port}" /tmp/domain-join-profile.json <<'PY'
import json
import sys

port, path = int(sys.argv[1]), sys.argv[2]
profile = {
    "schema_version": 1,
    "profile_id": "p0-lan-host-fixture",
    "host": "127.0.0.1",
    "port": port,
    "auth_mode": "offline",
    "minecraft_version": "1.21.4",
    "visibility": "isolated_test_only",
    "resource_pack_policy": "deny",
}
with open(path, "w", encoding="utf-8") as document:
    document.write(json.dumps(profile, indent=2) + "\n")
PY
==== drive: lan_port=25565 launched_version='1.20.1' ====
==== drive rc=0 ====
==== /tmp/domain-join-profile.json ====
{
  "schema_version": 1,
  "profile_id": "p0-lan-host-fixture",
  "host": "127.0.0.1",
  "port": 25565,
  "auth_mode": "offline",
  "minecraft_version": "1.21.4",
  "visibility": "isolated_test_only",
  "resource_pack_policy": "deny"
}
```

The run's own version (1.20.1) is ignored by the base writer. Also measured on base with
no version at all (`NONE`): identical output, rc 0, `"minecraft_version": "1.21.4"` —
the silent fallback this card kills.

**After (shipped bytes, same drive with 1.20.1):**

```
$ ... docker run ... bash /src/.tmp/h1f-joiner-probe.sh /src/test-orchestrator/runner/domain.sh 1.20.1
extracted lines 738-759 of /src/test-orchestrator/runner/domain.sh
==== drive: lan_port=25565 launched_version='1.20.1' ====
==== drive rc=0 ====
==== /tmp/domain-join-profile.json ====
{
  "schema_version": 1,
  "profile_id": "p0-lan-host-fixture",
  "host": "127.0.0.1",
  "port": 25565,
  "auth_mode": "offline",
  "minecraft_version": "1.20.1",
  "visibility": "isolated_test_only",
  "resource_pack_policy": "deny"
}
```

Diff of the two profiles: `minecraft_version` only. `profile_id`, `host`, `port`,
`auth_mode` (and `schema_version`, `visibility`, `resource_pack_policy`) are byte-identical.

## Acceptance 2 — non-tautology: the new tests measured red on base, green after

Swap the base `domain.sh` bytes in, run only the two new tests (new test bytes unchanged):

```
$ cp .tmp/h1f/base-domain.sh test-orchestrator/runner/domain.sh
$ uv run --frozen pytest tests/contract/test_runner_scripts.py -q \
      -k "test_the_joiner_profile_version_comes_from_the_run or test_the_joiner_version_contract_is_not_an_always_true_claim"
FAILED tests/contract/test_runner_scripts.py::test_the_joiner_profile_version_comes_from_the_run
FAILED tests/contract/test_runner_scripts.py::test_the_joiner_version_contract_is_not_an_always_true_claim
2 failed, 27 deselected in 0.16s

$ cp .tmp/h1f/new-domain.sh test-orchestrator/runner/domain.sh   # restore shipped bytes
$ uv run --frozen pytest tests/contract/test_runner_scripts.py -q \
      -k "test_the_joiner_profile_version_comes_from_the_run or test_the_joiner_version_contract_is_not_an_always_true_claim"
2 passed, 27 deselected in 0.05s
```

And the whole file green on
the shipped bytes:

```
$ uv run --frozen pytest tests/contract/test_runner_scripts.py -q
29 passed in 0.21s
```

The reversal test additionally mutates the *shipped* bytes (RV-0 splices the base writer
back in; RV-1 restores the dict constant; RV-2 deletes the gate; RV-3 removes its
`exit 2`; RV-4 moves the gate below the writer) and each mutation flips exactly the
predicate named, so neither half of the contract can be an always-true claim.

## Acceptance 3 — named refusal, no profile left behind

Shipped bytes, drive with no launched version (fresh `/tmp`, file removed before):

```
$ ... docker run ... bash /src/.tmp/h1f-joiner-probe.sh /src/test-orchestrator/runner/domain.sh NONE
==== drive: lan_port=25565 launched_version='' ====
domain: the joining client must carry the version this run launched, and this run
launched none it could name; refusing to write a joiner profile at a guessed version
==== drive rc=2 ====
==== /tmp/domain-join-profile.json ====
(file not written)
```

End-to-end from the *cause* side — a bundle profile whose recipe cannot be read, fed
through the exact `launched_version` read `domain.sh` performs for a named profile
(lines 413-418, unchanged by this card):

```
$ docker run ... bash -c '
    printf "{\"schema_version\":1}\n" > /tmp/h1f-unversioned-bundle.json
    launched_version="$(python -c "...[\"minecraft\"][\"version\"]..." \
        /tmp/h1f-unversioned-bundle.json 2>/dev/null)" || launched_version=""
    echo "recipe read yields launched_version=[${launched_version}]"
    bash /src/.tmp/h1f-joiner-probe.sh /src/test-orchestrator/runner/domain.sh NONE'
recipe read yields launched_version=[]
==== drive: lan_port=25565 launched_version='' ====
domain: the joining client must carry the version this run launched, and this run launched none it could name; refusing to write a joiner profile at a guessed version
==== drive rc=2 ====
(file not written)
```

The base bytes in the same situation wrote `minecraft_version: 1.21.4` with rc 0
(Acceptance 1, second measurement) — so the refusal is what changed, and the gate sits
*before* the writer (pinned by `joiner_version_refusal_is_named`: gate index < writer
index, each counted exactly once).

## Acceptance 4 — cross-version positive control

Both drives, shipped bytes, same container invocation:

- `launched_version=1.20.1` → profile says `"minecraft_version": "1.20.1"`, rc 0 (verbatim above).
- `launched_version=1.21.4` → profile says `"minecraft_version": "1.21.4"`, rc 0:

```
==== drive: lan_port=25565 launched_version='1.21.4' ====
==== drive rc=0 ====
==== /tmp/domain-join-profile.json ====
{
  "schema_version": 1,
  "profile_id": "p0-lan-host-fixture",
  "host": "127.0.0.1",
  "port": 25565,
  "auth_mode": "offline",
  "minecraft_version": "1.21.4",
  "visibility": "isolated_test_only",
  "resource_pack_policy": "deny"
}
```

The two version *sources* are therefore demonstrably two different values flowing to the
profile; 1.21.4 appearing in the output is the run naming it, not a constant.

## Acceptance 5 — live boundary

No full local live run (real server JVM + joining client) was started for this card: the
card does not require a green 1.20.1 JOIN, and the block-level drives above carry all
five readings it asks for. What the card changes is upstream of every ⑤-family ending:
the 1.20.1 joiner now *can* be given a profile that says 1.20.1, which base could not.
The ⑤ family itself (`GLFW 0x1000E`, `XDG_RUNTIME_DIR`, bridge 取料, budget frontier) is
untouched and remains V's recorded state: `project-v1201`'s named blockers stand, and
this card neither reproduces nor excludes them — it only removes the profile-version
confound that made the question unanswerable. Nothing sealed; no attempt/bundle created.

## Repository gates (on the branch tree, shipped bytes)

```
$ bash -n test-orchestrator/runner/domain.sh
(quiet; rc 0)  → echoed BASH_N_OK

$ uv run --frozen pytest tests/contract/test_runner_scripts.py -q
29 passed in 0.21s

$ uv run --frozen pytest -q
.......                                                                  [100%]
=========================== short test summary info ===========================
SKIPPED [1] tests\unit\test_orphans.py:686: this platform cannot answer the question, so it can never say gone
SKIPPED [1] tests\unit\test_silent_listener.py:123: a Windows terminate is not a signal
SKIPPED [1] tests\unit\test_tested_provenance.py:354: bridge-1201/build/libs/minekin-bridge-1201-0.0.0.jar is not built on this host, and the reviewed Bridge bytes are one of the things this check measures
2596 passed, 3 skipped in 360.18s (0:06:00)

The known-full-load flaky
`tests/unit/test_session_supervision.py::test_a_deadline_does_not_cancel_a_world_the_kin_is_already_in`
did not fail on this run (summary line above is `2596 passed, 3 skipped`), so no separate
re-run evidence is owed.

$ uv run ruff format --check .
352 files already formatted

$ uv run ruff check .
All checks passed!

$ uv run python tools/check_case_assertions.py
Case assertion implementations: OK (150 registered)

$ uv run python tools/verify_fixture_digests.py
W00 schema and fixture digests: OK

$ uv run python tools/check_boundaries.py
Minekin package dependency boundaries: OK

$ git diff --check
(quiet, rc 0)
```

## Not tested

- A real 1.20.1 (or 1.21.4) server+joiner end-to-end run under the new bytes — not
  required by the card; the version-source claim is measured at the writer block and at
  the recipe read, both on shipped bytes, in the controlled container.
- `MINEKIN_DOMAIN_OPEN_LAN` interaction with an auto-bundle run *plus* joiner: still
  refused by the untouched gate at lines 404-407 (its text is asserted unchanged).

## Blockers

None for this card's surface. The 1.20.1 JOIN-变绿 question stays where V left it
(three supply-chain blockers + the ⑤ family); this card was explicitly not gated on it.

## Conclusion

DONE
