# P0-OFFLINE-090-100-CASE-SPEC-001 — OFFLINE-090 / OFFLINE-100 case-definition draft

- Card: `P0-OFFLINE-090-100-EVIDENCE-CHECK-001`, sub-slot **B1-b-1** (draft only, no gates beyond this file's parse).
- Prepared in worktree `../minekin-wt-b1b`, branch `codex/minekin-offline-090-100`, base
  `03c1d95bd7c8c440756e91598afd3b1bc91938a4` (identity re-checked this session:
  `git rev-parse HEAD` = that SHA; `git status --porcelain` empty before this file; remote
  `https://github.com/printlndarling/minekin.git`).
- Status: **draft for M review/cherry-pick. Nothing registered, nothing sealed, volume
  `minekin-runner-data` mounted `:ro` for every reading below.**
- All code citations are to the bytes at this base (or `origin/main` where stated). No
  citation to prior conversation is used as evidence; anything not re-measured here is
  marked 未测.

## 1. Contract source (verbatim, `docs/p0-offline-session-compatibility-contract.md`)

Line 155:

> `| OFFLINE-090 | 日志、崩溃与Dashboard脱敏 | token/xuid/clientId正文暴露次数为0 |`

Line 156:

> `| OFFLINE-100 | 重启与A→B→A世界切换 | \`kin_id\`连续，外部身份与world context不串线 |`

Line 158 (binding on both cases; no third-party public offline server is ever a
judgement surface):

> 所有case只在运行者控制的隔离服执行。不得用第三方公网offline服务器做身份探测。

Both ids are already in `REQUIRED_CASES` for `W30` / `p0-core`
(`src/minekin_core/domain/cases.py:341-356`, ids at `:354-355`, declared
`ValidationClass.RUNTIME_REQUIRED`, gate `"W30"`), so registration only moves gate
readings from *absent* to *registered* — it cannot close anything by itself.

## 2. OFFLINE-090

### 2.1 Proposed manifest (fixture shape copied from `tests/fixtures/cases/offline-010.json`)

```json
{
  "schema_version": 1,
  "case_id": "OFFLINE-090",
  "work_package": "W30",
  "mandatory": false,
  "inputs": [],
  "assertions": ["token_xuid_clientid_body_exposure_count_is_zero"]
}
```

- `mandatory: false` mirrors every sibling OFFLINE fixture on this base (e.g.
  `offline-010.json`, `offline-030-prism-parity-001.json`); flipping it is forbidden to
  this lane and belongs to the gate-promotion card.
- `case_version` is then fixed by construction: sha256 of the sorted-key, compact-separator
  document (`src/minekin_core/domain/cases.py:732-734`). Recording the digest here is
  pointless — it must be read off after registration.

### 2.2 Phase / predecessor

Phase `RUNTIME_REQUIRED` (per the declaration at `cases.py:341-346`). Predecessor: none
new — this case adds definitions only; a closed run needs the controlled isolated server
(contract `:158`) and is a separate, volume-writing step.

### 2.3 Input artifacts (sealed carriers; names verbatim from the sealer/asserter constants)

| Carrier | Constant / cite | On-volume availability (B1-b-0 measured) |
|---|---|---|
| `client/stdout.log`, `client/stderr.log`, `client/latest.log` | `CLIENT_STREAM_ARTIFACTS` (`tools/assert_case_evidence.py:709`) | declared in 2/2 OFFLINE-010, 2/2 OFFLINE-020, 5/5 OFFLINE-030* bundles |
| `server/server.log` | `SERVER_LOG_ARTIFACT` (`tools/assert_case_evidence.py:698`; sealed `tools/seal_run_evidence.py:256`) | 2/2, 2/2, 5/5 respectively |
| `server/usercache.json` | `SERVER_IDENTITIES_ARTIFACT` (`tools/assert_case_evidence.py:699`; sealed `tools/seal_run_evidence.py:257`) | 2/2, 2/2, 5/5 |
| `client/crash-reports/*` | sealed at `tools/seal_run_evidence.py:252-254` | **0 OFFLINE bundles carry it**; the only 3 crash artifacts on the whole volume belong to CORE-030 runs (`crash-2026-09-26_12.24.07/-17.19.18/-17.31.04-client.txt`) |
| `bridge-trace.jsonl` (full ledger timeline) | `LEDGER_TIMELINE_ARTIFACT` (`src/minekin_core/adapters/evidence/trace.py:73`) | 2/2, 2/2, 5/5 |
| Dashboard | **no sealed carrier exists** | all 107 bundles declare 53 distinct artifact paths; a case-insensitive scan for `dashboard/ui/panel/web` yields only two `checks/*.log` false positives whose "ui" comes from the substring in `uuid` ⇒ material-outside boundary (acceptance ④ of the card) |

`orchestrator-trace.json` (declared in 107/107 bundles) is a harness-side record and is
**not** the ledger — it must never be used as the 账本 carrier.

### 2.4 Expected outcome (per contract row)

Over the readable carriers of a 090 run, the number of body exposures of the run's
token/xuid/clientId **credential literals** is 0, in logs, in crash reports, and on the
Dashboard.

### 2.5 Assertion (single, taken from the criterion column; no padding assertions)

`token_xuid_clientid_body_exposure_count_is_zero` — proposed reading, field-for-field:

1. Take the run's own credential values from its inputs: `username` and the identity it
   launched with (`asserter-inputs.json` keys `schema_version/kin_id/run_id/username/
   previous_run_id`, `tools/assert_case_evidence.py:70-88` `asserter_inputs_bytes`).
2. Search each readable carrier of §2.3 for those literals; assert count 0.
3. Crash half: same search over `client/crash-reports/*` when declared.
4. Dashboard half: **not assertable from a bundle** (§2.3 last row) — must be registered
   as a material-outside boundary, not silently closed by "0 exposures inside bundle".

### 2.6 Blocking ambiguity for M (do not paper over)

- The offline candidates' *own* literals are public constants in the repo:
  `access_token_argv="0"`, `client_id_argv=EMPTY_ARGV`, `xuid_argv=EMPTY_ARGV`
  (`src/minekin_core/adapters/launcher/offline_session.py:71-73,82-84`). A search for the
  token literal `"0"` inside free-text logs is not decidable without an agreed
  definition of "credential literal set" (the bare token `"0"` appears as an ordinary
  digit everywhere; prior conversation measured standalone-`"0"` in 94/94 bundles with the
  bridge trace — **未测 this session, quoted as unverified**). Under the plausible strict
  reading ("any appearance of the recorded non-empty literals"), no sealed OFFLINE bundle
  can pass; under a "field-scoped argv/JSON occurrence" reading, the assertion is judgable.
  **M must pin the reading in the asserter function; this draft deliberately does not
  choose.**
- `src/minekin_core/adapters/evidence/bundle.py:1-9`: sealing *refuses* (raises before
  writing anything) rather than redacts a bundle containing a credential literal. So the
  minimal counterexample "one real exposure gets sealed and judged red" is **only
  constructible on a labelled copy outside the volume** (expected outcome there: refusal,
  not a red verdict). A copy demo: `write_bundle(dir, manifest,
  {"client/stdout.log": b"...token=<secret>..."}, secrets=["<secret>"])` raises
  `MinekinError` and writes no directory.

### 2.7 Minimal counterexample / positive control (design; runtime part 未测)

- Counterexample (labelled copy in `/tmp`, never on `/data`): inject a fabricated
  credential literal into a copy of one carrier and run the asserter reading of §2.5 →
  exposure count ≥ 1 → assertion red with a named violation.
- Positive control: the same reading over the unaltered sealed bytes → count 0 under the
  field-scoped reading (pending M's decision in §2.6; under the strict reading every
  bundle is red and the control does not exist).
- Digest guard (per card acceptance ②, generic): tamper one byte of a declared artifact in
  a `/tmp` copy of a bundle → `python -m minekin_core evidence verify <run>` exits
  `ExitCode.STORAGE = 12` (`src/minekin_core/domain/errors.py:39`) with violation
  `ARTIFACT_DIGEST_MISMATCH:<path>` (`src/minekin_core/adapters/evidence/bundle.py:255`);
  restore → exit 0. (Design cites current repo bytes; the run was executed in prior
  conversation only — **未测 this session**.)

## 3. OFFLINE-100

### 3.1 Proposed manifest

```json
{
  "schema_version": 1,
  "case_id": "OFFLINE-100",
  "work_package": "W30",
  "mandatory": false,
  "inputs": [],
  "assertions": [
    "the_kin_id_continues_from_the_previous_run",
    "the_external_identity_and_world_context_do_not_cross_runs"
  ]
}
```

### 3.2 Phase / predecessor

Phase `RUNTIME_REQUIRED` (`cases.py:341-356`). Predecessor for a closed run: the run must
follow another run in the same Kin's ledger — the "重启" half — and the full
**A→B→A** world-switch shape must follow the `EVIDENCE-SEQUENCE` carrier shape already
frozen on this base (attempt `sequence` + `supersedes_run_id`; see the card's §5 verdict
and `docs/development-execution-plan.md:242`). No such OFFLINE-100 chain exists sealed on
the volume today (B1-b-0: zero bundles with `case_id` starting `OFFLINE-100`), so 100 can
be *defined* in repo but not *closed* without a future controlled run — that sealing
step is outside this sub-slot (volume write).

### 3.3 Input artifacts

Same bundle inventory as 090 §2.3 (the OFFLINE-010/020/030 rows) plus the cross-run half
of §2.3, and:

| Carrier | Cite | Measured (B1-b-0) |
|---|---|---|
| `previous-run-trace.jsonl` | `PREVIOUS_TIMELINE_ARTIFACT` (`tools/assert_case_evidence.py:693`) | declared in all 2/2/5 OFFLINE bundles above; 67/107 volume-wide (card census) and 56 bundles pair it with `asserter-inputs.json` (this session's probe counts both) |
| ledger row fields | `_LEDGER_COLUMNS` (`tools/assert_case_evidence.py:251-257`): `position, event_id, event_type, schema_version, kin_id, run_id, client_instance_id, session_id, generation, world_context_id, sequence, correlation_id, causation_id, monotonic_ns, observed_at_utc, source, trust_class, payload_json, payload_hash` | both timelines are rendered from exactly these rows (`timeline_bytes`, `tools/assert_case_evidence.py:304-310`) |
| `server/usercache.json` | as §2.3; server-side identity map | present in all OFFLINE bundles above |

### 3.4 Expected outcome (per contract row)

Across a restart (and the A→B→A world switch): `kin_id` is continuous, and neither the
external identity nor the world context crosses between runs.

### 3.5 Assertions (one per clause of the criterion; names derived from the clause text)

**A. `the_kin_id_continues_from_the_previous_run`**

- Read `bridge-trace.jsonl` (this run), `previous-run-trace.jsonl` (the previous run) and
  `asserter-inputs.json` (`kin_id`, `run_id`, `previous_run_id`;
  `tools/assert_case_evidence.py:70-88`).
- Green iff `kin_id` is a single value across both timelines and equals the input's
  `kin_id`; every previous-timeline row's `run_id` equals `previous_run_id`; every
  this-timeline row's `run_id` equals `run_id` (the scoping the sealer guarantees by
  construction, `previous_run_rows`/`ledger_rows`, `tools/assert_case_evidence.py:282-344`).
- This is the "重启" half: `previous_run_id` empty ⇒ `PREVIOUS_IS_FIRST_RUN`, no verdict
  fabricated (`previous_run_rows` doc: "Empty when this run is the Kin's first").

**B. `the_external_identity_and_world_context_do_not_cross_runs`**

- External identity (server's own record, not the client's claim): in
  `server/usercache.json`, the entry for `asserter-inputs.json:username` must equal
  `str(offline_player_uuid(username))` (`src/minekin_core/domain/offline_identity.py:39`) —
  the same rule the existing runtime asserter applies in
  `server_observed_join_identity` (registered name, `tools/assert_case_evidence.py`
  ASSERTIONS block); the new function must not re-derive that rule from prose.
- Non-crossing of session/world coordinate: the sets of `session_id` (and of
  non-null `world_context_id`) over the two timelines must be disjoint; a run's session
  must not resume the dead run's (`the_restart_runs_as_a_new_session` is the registered
  predecessor with the same shape). `generation` alone may legitimately restart per run —
  cite, do not assert, unless M pins otherwise.
- A→B→A: for the full switch, the three runs are read in the `EVIDENCE-SEQUENCE` shape
  (attempt sequence + `supersedes_run_id`), A→B and B→A each via the previous-run pair
  above. On-volume material today: 46 sealed previous-run links whose both ends exist
  (B1-b-0 probe, incl. the OFFLINE chain `f2ecb728…(010) → 3d5606ce…(020) → ee9d5ad3… /
  f0f35035…(030 children)`), but no A→B→A triple was ever produced for identity-switch
  purposes ⇒ the A→B→A half needs a future controlled run; defining the assertion does
  not fake the closure.

### 3.6 Minimal counterexamples / positive controls (design; runtime part 未测 this session)

Positive controls (available material): runs `3d5606ced37849e3b17a4c418fa33ab4`
(OFFLINE-020, previous `f2ecb728df754826abf4a052be138a2d` sealed),
`ee9d5ad3d57344da8452069102e27216` and `cb5e2119845e41868c28e5aeb1370ce3`
(OFFLINE-030 children) — all five OFFLINE-030*/010*/020* bundles qualify per §3.3
declared-path census. Counterexamples, each a single named-field edit on an in-memory
copy of those sealed bytes (never the volume):

1. one previous-row `kin_id` → `kin-99` ⇒ A red `KIN_ID_NOT_CONTINUOUS`.
2. previous rows' `run_id` → foreign value ⇒ A red `PREVIOUS_ROWS_NOT_ONE_RUN`.
3. one of this run's rows `kin_id` edited ⇒ A red.
4. `usercache.json` entry for `username` remapped to
   `offline_player_uuid("someone-else")` ⇒ B red `SERVER_SAW_ANOTHER_IDENTITY`.
5. copy one previous-run `session_id` into this run's rows ⇒ B red
   `SESSION_ID_SHARED_ACROSS_RUNS`.
6. control (non-vacuity of 5): a foreign `session_id` appearing **only** in this run
   stays green — the rule is crossing, not uniqueness.
7. generic digest guard as §2.7 (`rc=12` + `ARTIFACT_DIGEST_MISMATCH:<path>`).

## 4. Gate consequences of registering the two manifests (acceptance ③)

- Both ids leave `requirement.absent` and appear in `requirement.non_mandatory`
  (mechanics: `Requirement.absent` → `blocking_cases` +
  `PromotionBlock.REQUIRED_CASE_NOT_REGISTERED`, `src/minekin_core/domain/cases.py:567,
  795, 884-891`; the id inventory at `:354-355`).
- The payload `sha256({"work_packages","overall"}, sort_keys=True)` therefore **must
  move** from the baseline `fb0152c85d029ee06a41a34e84f9656cd23fae0b1e166322c494d1190cd178da`
  (re-measured twice this session, §5.3). Which exact block each id lands in after
  registration (`CASE_WITHOUT_EVIDENCE` vs `REQUIRED_CASE_NOT_REGISTERED` residue from
  the still-unregistered 060/070/080) must be reported **separately per the card**; that
  is a post-registration measurement and **未测 here** — registration cannot be committed
  without the tools/** additions of §5.4, which are M's surface.
- Hard invariant to re-prove at registration time: `promotable` stays
  `W00/W10/W20/W60`; `W30` and `p0-core` stay `promotable:false`. Any writing that makes
  them true is gate promotion → stop.

## 5. B1-b-0 measured readings quoted by this draft (this session, volume `:ro`)

### 5.1 Mount identity / registry

- `/src writable False | data writable False`; head of `codex/minekin-offline-090-100` =
  `03c1d95b…`, tree clean.
- `git ls-remote --heads origin`: only `codex/minekin-harness` (`44922b8`) and `main`
  (`796316a`); **no `codex/minekin-harness-registry` ⇒ registry branch has no commits,
  and neither `origin/main` nor this base contains a `harness/` tree ⇒ registry contents
  are not readable today (expected; M must write it back or rebuild).**
- Image `minekin-runner:local` = `b67a4d917306`; volume `minekin-runner-data` present;
  `docker ps -a`: no minekin containers live.

### 5.2 Sealed-manifest census (case-prefixed, declared `artifacts[].path`)

- 107 bundle dirs. OFFLINE-010: 2 bundles (`61b4f025…`, `f2ecb728…`), OFFLINE-020: 2
  (`3d5606ce…`, `6ad6f000…`), OFFLINE-030 incl. children: 5 (`3ea7c6b9…`,
  `6393b228…`, `cb5e2119…`, `ee9d5ad3…`, `f0f35035…`) — all PASS, each declaring
  `bridge-trace.jsonl`, `previous-run-trace.jsonl`, all 3 client streams,
  `server/server.log`, `server/usercache.json`, `server/server.properties`,
  `asserter-inputs.json`, `orchestrator-trace.json`; **0 declare crash reports**.
- OFFLINE-070 / OFFLINE-090 / OFFLINE-100: **zero sealed bundles** (070 is also still in
  `requirement.absent`, §5.3 — its absence corroborates the registry read).
- Cross-run: 56 bundles pair `previous-run-trace.jsonl` + `asserter-inputs.json`; for 46
  of them the previous bundle is also sealed on the volume. Longest sealed previous-run
  chain: 25 runs (kin-01 campaign chain, newest tail `ADMIT-110 407907710…`).
- Artifact-path universe: 53 distinct declared paths over all bundles; none
  dashboard-shaped (only `uuid`-substring false positives, §2.3); the 3 crash-report
  artifacts belong to CORE-030 runs only.

### 5.3 Gate rows today (pre-registration; report rc=1 = blocked, expected)

- payload sha256 = `fb0152c85d029ee06a41a34e84f9656cd23fae0b1e166322c494d1190cd178da`
  (identical across two independent report calls this session; also the card's baseline
  ⇒ baseline reproduced).
- `promotable: W00, W10, W20, W60`.
- `W30`: `promotable false`, blocks `["NO_MANDATORY_CASES","REQUIRED_CASE_NOT_REGISTERED"]`,
  `requirement.absent` ⊇ `OFFLINE-060,070,080,090,100`; `p0-core`: blocks
  `["REQUIRED_CASE_NOT_REGISTERED"]` with the same absent superset; `overall` likewise.
  Verbatim JSON of both rows was captured in this session's run output (transient buffer;
  not written to any repo/worktree file).

### 5.4 Why no fixture is committed by this draft

Registering either manifest requires, per the base's own tooling: the named assertion
functions existing in `tools/assert_case_evidence.py` (unregistered names ⇒ INCOMPLETE at
evaluate time) and entries in the IMPLEMENTATIONS map of
`tools/check_case_assertions.py`, plus two added lines in
`tests/fixtures/manifest.sha256` (`tools/verify_fixture_digests.py`). The first two are
`tools/**` — M's surface per the card's hard boundary ④ (the card text repeats it). A
fixture committed without them would break `python tools/check_case_assertions.py`
rc=0. **Stop cell reported; this draft is the patch-set input for M.** The only file this
sub-slot adds is this `harness/case-specs/P0-OFFLINE-090-100-CASE-SPEC-001.md`.

## 6. Evidence boundaries and four-state declaration

- Measured this session (§5): volume census, gate rows, registry absence, mount
  identity. **Design-only, 未测 this session**: every §2.7/§3.6 probe/reversal run (their
  predecessors were exercised in the prior conversation whose logs are `未提交` and not
  citable as evidence per this sub-slot's rules — re-run them in the follow-up slot that
  also gets the asserter functions).
- Four states: **未合并 main / 仅在本分支 (`codex/minekin-offline-090-100`) /
  无真封存证据新增（本卡全程 `:ro`，未建 attempt、未封 bundle）/ 断言运行读法尚未量**。
- Nothing here connects to or reads any remote/third-party server; the isolated-server
  constraint of contract `:158` is written into both case definitions.

## 7. Open questions for M

1. Pin the credential-literal reading of 090 §2.6 (strict vs field-scoped), else the
   case is definitionally red-on-sealed-material forever.
2. Who lands the two asserter functions + IMPLEMENTATIONS entries + manifest.sha256
   lines (tools/** = M) so §2.1/§3.1 fixtures become committable.
3. Dashboard half of 090: accept permanent material-outside boundary in the case note, or
   commission a dashboard-evidence carrier (out of this lane).
4. A→B→A OFFLINE-100 controlled run: schedule under the volume's sole-writer window
   (definition alone closes nothing).
5. Whether 070 (also absent, zero bundles) should be batched with this registration.
