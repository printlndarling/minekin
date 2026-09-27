# P0-OFFLINE-090-100-CASE-SPEC-001 — OFFLINE-090 / OFFLINE-100 case-definition draft

- Card: `P0-OFFLINE-090-100-EVIDENCE-CHECK-001`, sub-slot **B1-b-1** (draft only, no gates beyond this file's parse).
- Prepared in worktree `../minekin-wt-b1b`, branch `codex/minekin-offline-090-100`, base
  `03c1d95bd7c8c440756e91598afd3b1bc91938a4` (identity re-checked this session:
  `git rev-parse HEAD` = that SHA; `git status --porcelain` empty before this file; remote
  `https://github.com/printlndarling/minekin.git`).
- Status: **draft for M review/cherry-pick. Nothing registered, nothing sealed, volume
  `minekin-runner-data` mounted `:ro` for every reading below.**
- Round 2 revision: 090's exposure reading and registration shape (§2.1/§2.4-§2.7) and
  100's A→B→A proof set (§3.5 B/C, §3.6) were rewritten to the boundaries 主控 pinned;
  all five former open questions (§7) are closed as named facts. Section numbering and
  the already-verified §5 readings are unchanged.
- All code citations are to the bytes at this base (or `origin/main` where stated). No
  citation to prior conversation is used as evidence; anything not re-measured here is
  marked 未测.
- Round 14 trunk edit by 主控 (2026-09-27): this file is no longer a placement draft — its
  rows are registered on trunk, and the A→B→A run §3.5 called for now exists on the volume.
  The edits are confined to §3.5 C, §3.6 and this bullet: C4's negative clause is scoped to
  the carrier that actually seals (the pairwise `previous-run-trace.jsonl` is not a
  three-run timeline), and the "no controlled triple exists yet" wording is replaced by the
  sealed `kin-e-aba` readings. `case_version` digests the registered function bytes plus the
  fixture, not this file, so none of this moves a registry digest or invalidates a bundle.
- Round 15-19 trunk edits by 主控 (2026-09-27): §2.7's volume-wide positive control (round
  15) and the new §2.8 — the file-level carrier injections, the digest guard on those very
  carriers, and what actually makes the Dashboard half answer (round 17) — replace the
  "file-level remains 未测" wording; §3.6's "9, 10 and 11 remain 未测" is replaced by E-CX's
  readings plus 主控's independent recheck; the new §2.9 drives the 崩溃 half on a sealed
  crash report and records two reading boundaries it exposed (a run document names no case,
  and the directory-side volume count is 99, not the ledger-side 105/107). Same scope rule as
  the round-14 bullet: these edits touch prose only, no judgement byte, no fixture, no
  registry status, so no digest moves and no bundle is invalidated. Nothing here closes
  OFFLINE-090 or OFFLINE-100.
- Placement: this draft sits at `docs/p0-offline-090-100-case-spec-2026-09-27.md`, the E lane's existing per-card record convention under `docs/` (precedent: `docs/p0-core030-runner-rerun-2026-09-27.md`) and within this card's allowed paths; the previous session's invented top-level `harness/case-specs/` location is not a carrier in any ref of this repository and is not kept.

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

### 2.1 Proposed registration shape (父案 + 非门禁子案；fixture shape copied from `tests/fixtures/cases/offline-010.json` and `offline-030-prism-parity-001.json`)

Sub-case (carries the assertable half: "日志与崩溃载体的认证正文零暴露"):

```json
{
  "schema_version": 1,
  "case_id": "OFFLINE-090-BUNDLE-CARRIERS-001",
  "work_package": "W30",
  "mandatory": false,
  "inputs": [],
  "assertions": ["auth_field_bodies_are_not_exposed_in_bundle_carriers"]
}
```

Parent (keeps the whole contract row, i.e. the Dashboard half included):

```json
{
  "schema_version": 1,
  "case_id": "OFFLINE-090",
  "work_package": "W30",
  "mandatory": false,
  "inputs": [],
  "assertions": [
    "auth_field_bodies_are_not_exposed_in_bundle_carriers",
    "auth_field_bodies_are_not_exposed_on_the_dashboard"
  ]
}
```

- `OFFLINE-090-BUNDLE-CARRIERS-001` follows the repo's existing sub-case convention
  verbatim: `OFFLINE-030-PRISM-PARITY-001` / `OFFLINE-030-ENUM-ALIGNED-001`
  (`<PARENT>-<SUBTOPIC>-NNN`, fixture file `offline-090-bundle-carriers-001.json`), whose
  precedent is "父 id 保留另一半句" (`docs/development-todo-history-through-cef712b.md:1741`).
  No new registry structure is invented: the sub-case is an ordinary non-gate
  (`mandatory: false`) fixture-shaped manifest.
- **父案 `OFFLINE-090` 的状态不得为 PASS（主控判定）。** The current bundles carry no
  Dashboard carrier at all (§2.3 last row: 53 declared paths volume-wide, none
  dashboard-shaped; OFFLINE 系 crash-reports 0 份), so even a green sub-case is only
  **部分证据** for the parent row: the log half rests on sealed bytes, the crash half on
  carrier absence, and the Dashboard half has no readable carrier — its assertion must
  return a named evidence-gap verdict (e.g. `DASHBOARD_CARRIER_NOT_SEALABLE`), never a
  silent 0. This draft therefore registers neither as closed and marks the parent gap by
  name.
- `mandatory: false` mirrors every sibling OFFLINE fixture on this base (e.g.
  `offline-010.json`, `offline-030-prism-parity-001.json`); flipping it is forbidden to
  this lane and belongs to the gate-promotion card.
- `case_version` is then fixed by construction: sha256 of the sorted-key, compact-separator
  document (`src/minekin_core/domain/cases.py:732-734`). Recording the digest here is
  pointless — it must be read off after registration.
- These manifests are **design text only**: no fixture file is committed by this card
  (§5.4, §7.2 — registration is M's surface).

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
| `client/crash-reports/*` | sealed at `tools/seal_run_evidence.py:252-254` | **0 OFFLINE bundles carry it**; the only 3 crash artifacts on the whole volume sit on `kin-04 / 8164024d…`, `kin-e-rr-seal / 787168062c…`, `kin-e-rr-seal2 / 6286f1e5…` (`crash-2026-09-26_12.24.07/-17.19.18/-17.31.04-client.txt`). **Round-18 correction (was: "belong to CORE-030 runs")**: a run document holds no case-identification field, so that attribution comes from E's records, not from bundle bytes — see §2.9 |
| `bridge-trace.jsonl` (full ledger timeline) | `LEDGER_TIMELINE_ARTIFACT` (`src/minekin_core/adapters/evidence/trace.py:73`) | 2/2, 2/2, 5/5 |
| Dashboard | **no sealed carrier exists** | the bundles of that scan declare 53 distinct artifact paths; a case-insensitive scan for `dashboard/ui/panel/web` yields only two `checks/*.log` false positives whose "ui" comes from the substring in `uuid` ⇒ material-outside boundary (acceptance ④ of the card). **Round-18 denominator note**: the row above quoted "all 107 bundles", which is the ledger-side底数 of that session; a whole-volume directory census now reads **99** bundle dirs (§2.9), and every count in this document that says "the volume holds N bundles" means that directory-side number |

`orchestrator-trace.json` (declared in 107/107 bundles) is a harness-side record and is
**not** the ledger — it must never be used as the 账本 carrier.

### 2.4 Expected outcome (per contract row)

Over the readable carriers of a 090 run, the number of exposures of authentication-field
bodies — token/xuid/clientId **in field/parameter context** — is 0, in logs, in crash
reports, and on the Dashboard. The count is per §2.5's field-context reading, not per
bare-literal search; the Dashboard half is not readable from any bundle today (§2.1), so
on current material only the sub-case half of this sentence can ever be green.

### 2.5 Assertion (single, taken from the criterion column; no padding assertions)

`auth_field_bodies_are_not_exposed_in_bundle_carriers` — reading as **pinned by 主控**
(§2.6); field-for-field:

1. **The credential literals are NOT taken from `asserter-inputs.json`, and this
   assertion reads no literals from it.** That artifact carries exactly the keys
   `schema_version / kin_id / run_id / username / previous_run_id`
   (`tools/assert_case_evidence.py:747-758`, `asserter_inputs_bytes`) — it contains **no
   token, no xuid, no clientId** — so there is nothing credential-shaped in it to
   extract, and the earlier draft's "take the run's credential literals" step is
   withdrawn (§7.1, closed).
2. Judge exposure by **field/parameter context**, not by bare value search: an exposure
   is the co-occurrence of an authentication field name / option name **with its value**
   — argv pairs keyed `--accessToken` / `--access-token`, the JSON key
   `auth_access_token` (that placeholder→value mapping is exactly what
   `src/minekin_core/adapters/launcher/offline_session.py:166` defines; `clientid` /
   `auth_xuid` at `:176-177`; the Prism-parity flags `--clientId` / `--xuid` at `:10`,
   `:247`), or `xuid` / `clientId` key-value pairs. Only a recognizable credential body
   appearing **inside such a context** counts as one exposure.
3. **The offline sentinels are public, non-secret values** (主控-pinned):
   `access_token_argv="0"`, `client_id_argv=EMPTY_ARGV`, `xuid_argv=EMPTY_ARGV`
   (`src/minekin_core/adapters/launcher/offline_session.py:71-73` and `:82-84`;
   `EMPTY_ARGV: Final[str] = ""` at `:36`). Therefore **any occurrence of the digit `0`
   or of an empty value — anywhere, in any context — is never counted as a leak**; a
   standalone `0` as a count, coordinate or latency is not evidence of anything.
4. Search each readable carrier of §2.3 under rules 2-3; assert exposure count 0.
5. Crash half: same search over `client/crash-reports/*` **when declared** — 0 OFFLINE
   bundles declare it (§2.3), so on current material this sub-half rests on carrier
   absence, not on scanned bytes. Round 18 drove the search on a crash report that *is*
   sealed elsewhere on the volume and named the exposure there (§2.9), which upgrades the
   instrument's reach, not this row's evidence: 对 OFFLINE 系而言仍是载体缺席。
6. Dashboard half: **not assertable from a bundle** (§2.3 last row) — it is carried by
   the parent case as a named evidence gap (§2.1), never closed by "0 exposures inside
   bundle".
7. Standing fact, retained: authentication fields are **uniformly classified and redacted
   in the harness's own outputs** — `SECRET_CLASSIFICATION` covers
   access_token/client_id/xuid precisely so an online adapter cannot inherit a weaker
   log schema (`offline_session.py:25-33`), evidence views carry policy and presence but
   "never a value" (`candidate_document`, `offline_session.py:278-290`), and the sealer
   **refuses** a bundle containing a credential literal rather than redacting it
   (`src/minekin_core/adapters/evidence/bundle.py:1-9`). **The assertion must not have
   its redaction removed to turn green.**

### 2.6 Reading pinned by 主控 (was: blocking ambiguity for M)

- The ambiguity in the first draft was real: the offline candidates' own literals are
  public constants in the repo (`access_token_argv="0"`,
  `client_id_argv=EMPTY_ARGV`, `xuid_argv=EMPTY_ARGV`,
  `offline_session.py:71-73, 82-84`), so a bare-literal search over free-text logs is
  not decidable. **This reading is now pinned by 主控 and closed here** (see §2.5
  rules 2-3; §7.1 is resolved, not open): judge **认证正文在字段/参数上下文中的暴露**,
  never the bare digit or empty argv.
- The first draft also carried an unverified quote from the prior conversation
  ("standalone-`0` appears in the bridge trace of 94/94 bundles"). Per this sub-slot's
  rules such a quote is not evidence, and **this session's re-measurement on the `:ro`
  volume refutes it as quoted**: across all 94 `bridge-trace.jsonl` files the *character*
  `0` appears in 94/94 (ids, timestamps, coordinates like `0.0`), but a *standalone*
  token — bare `0` or quoted `"0"` as its own JSON value — appears in **0/94** files
  (patterns `(?<![0-9A-Za-z_.])0(?![0-9A-Za-z_.])`, `"0"`, `: 0`; sample: line 1 of
  `kin-01/run/evidence/3d5606ce…/bridge-trace.jsonl` has no standalone token). The quote
  is therefore struck; the design decision it was adducing for is unaffected, because it
  is now settled by 主控 rather than by that measurement.
- `src/minekin_core/adapters/evidence/bundle.py:1-9`: sealing *refuses* (raises before
  writing anything) rather than redacts a bundle containing a credential literal. So the
  minimal counterexample "one real exposure gets sealed and judged red" is **only
  constructible on a labelled copy outside the volume** (expected outcome there: refusal,
  not a red verdict). A copy demo: `write_bundle(dir, manifest,
  {"client/stdout.log": b"...token=<secret>..."}, secrets=["<secret>"])` raises
  `MinekinError` and writes no directory.

### 2.7 Minimal counterexample / positive control (design; file-level half executed by 主控, round 17 — see §2.8)

All three below were designed to run on a **labelled copy outside the volume** (`/tmp`,
never `/data`), against §2.5's pinned reading. **主控 (round 15, 2026-09-27) executed two
of the shapes; the file-level copy injection was executed by 主控 on 2026-09-27 (round 17)
and its readings are §2.8.**

- **Executed by 主控 (round 15) — positive control over real sealed bytes.** The registered
  judgement was driven read-only over every bundle on the canonical volume: 99 bundles,
  1103 declared text carriers, `auth_field_bodies_are_not_exposed_in_bundle_carriers`
  answered `None` for all **65** bundles it could load and **0** answered red. 34 bundles
  raised `Unreadable` from the loader (they are not this case's run shape; named rather
  than counted as green). Non-vacuity of the scan itself: **50** bundles do carry one of
  `AUTHENTICATION_FIELD_NAMES` somewhere in their text carriers, so the zero above is a
  reading over bytes that contain the fields, not over bytes that lack them. Reproduce:
  `bash /src/.tmp/m-r15-090-live.sh` under the standard `:ro` container mount (log
  `.tmp/m-r15-090-live.log`).
- **Executed by 主控 (round 15) — exposure / reverse controls at the carrier-text level**,
  i.e. `authentication_exposures` over the strings the rule operates on (in-memory; no file
  written): a context-bearing secret reds in all three shapes a body can appear in —
  JSON `"accessToken": "<64-hex>"`, argv `--accessToken <64-hex>`, and the same pair nested
  inside a sealed ledger row's escaped `payload_json` — while every public form stays
  green: the digit `0` as the field's value, an empty body, `<redacted>`, the launcher
  template placeholder `${auth_access_token}`, a presence-only key
  (`client_id_present`/`xuid_present`), and a flag followed by an ordinary word
  (`--xuid none configured`). Ten pairs, all matching the pinned expectation.
  **This is the 公版哨兵保护 of §2.5 rule 3 measured rather than asserted**, and it holds
  at the text level only: of the ten pairs, the two that matter for this case — the JSON
  field/body pair and the ledger-row nesting — were since re-judged through
  `read_sealed_material` over a carrier *file* (§2.8); the other eight remain text-level
  readings.
- Counterexample (红), file-level: inject into one carrier of the copy a context-bearing
  exposure — argv-shaped `--accessToken <fabricated-secret>` or JSON `"auth_access_token":
  "<fabricated-secret>"` — ⇒ exposure count ≥ 1 ⇒ assertion red with a named violation.
  **Executed by 主控 (round 17) in both file shapes a bundle holds — a `.log` carrier and a
  JSONL ledger row — readings in §2.8.**
- Reverse control (不得红): inject into the same copy bare `0` occurrences — the digit
  `0` as a standalone value in counting/coordinate/latency positions, and `EMPTY_ARGV`
  empty values — ⇒ exposure count stays 0 ⇒ the assertion must stay green. This is the
  公版哨兵保护, straight from §2.5 rule 3. **Executed at the text level above, and at the
  file level by 主控 (round 17): the same carrier appended with `{"accessToken": "0"}` stays
  green in both file shapes (§2.8, `log-public-sentinel` / `trace-row-public-sentinel`).**
- Positive control: the same reading over the unaltered sealed bytes → count 0 (every
  authentication field in a sealed bundle is either the public sentinel or redacted,
  §2.5 rule 7). **Executed by 主控 as the 65/0 volume reading above** (the earlier carrier
  census behind it is in §5), and again per-copy in §2.8 (`control`: 14 carriers, both
  clauses green/refusing, `verify rc=0`).
- Digest guard (per card acceptance ②, generic): tamper one byte of a declared artifact in
  a `/tmp` copy of a bundle → `python -m minekin_core evidence verify <run>` exits
  `ExitCode.STORAGE = 12` (`src/minekin_core/domain/errors.py:39`) with violation
  `ARTIFACT_DIGEST_MISMATCH:<path>` (`src/minekin_core/adapters/evidence/bundle.py:255`);
  restore → exit 0. (Design cites current repo bytes; the run was executed in prior
  conversation only — **未测 this session**; **round 17 measured it on the exposure
  carriers themselves, §2.8**.)

### 2.8 File-level carriers, digest guard and the Dashboard refusal's mechanism (主控, round 17, 2026-09-27)

§2.7 left one present-tense claim standing: the exposure judgement had only ever been
driven over strings, never over a carrier *file* that the reader opens from disk. This
section measures that, plus the seal's digest guard on those same files, plus what actually
makes the Dashboard half answer. Drive: `bash /src/.tmp/m-r17-090-filelevel.sh` under the
standard read-only container mount (`-v minekin-runner-data:/data:ro`, no writes to the
volume; log `.tmp/m-r17-090-filelevel.log`).

**Census, file-level.** Of 99 bundles, 65 load through `read_sealed_material`, and **49 of
those carry one of `AUTHENTICATION_FIELD_NAMES` inside a carrier file the reader actually
opens**. The driven bundle is `kin-01 / run 03bd3a22f6ac43aea07d470222cd2c92`
(`bundle_digest 368d206ccf535efeb4c23ba948962d3ffea45924fd18ee93249908d3a65b9bab`), which
declares 14 text carriers: `asserter-inputs.json`, `bridge-trace.jsonl`,
`client/latest.log`, `client/server-resource-packs.json`, `client/stderr.log`,
`client/stdout.log`, `fault-injection.json`, `orchestrator-trace.json`,
`previous-run-trace.jsonl`, `run-document.json`, `server/server.log`,
`server/server.properties`, `server/usercache.json`, `trusted/server-profile.json`.
(Note the shape of the list: `asserter-inputs.json` is a carrier like any other, and the
exposures below are made in the run's own logs and ledger — not in that file.)

Each row below appends **one line** to a `/tmp` copy of the named carrier, then re-reads
the copy through `read_sealed_material` and asks the two registered clauses, `evidence
verify` and `tools/rejudge_evidence.py`:

| drive | 载体半句 | Dashboard 半句 | verify / rejudge |
| --- | --- | --- | --- |
| `control` (untouched) | `None` | `DASHBOARD_CARRIER_NOT_SEALED` | `rc=0` / `rc=0` `Rejudge evidence: OK` |
| `log-real-secret` (`client/latest.log` += `{"accessToken": "<64 a>"}`) | **`AUTH_BODY_EXPOSED:client/latest.log:accessToken`** | refusal | `rc=12` / `rc=2 ARTIFACT_DIGEST_MISMATCH:client/latest.log` |
| `log-public-sentinel` (same line, body `0`) | `None` | refusal | `rc=12` / `rc=2` same mismatch |
| `trace-row-real-secret` (`bridge-trace.jsonl` += a well-formed JSON row with the secret) | **`AUTH_BODY_EXPOSED:bridge-trace.jsonl:accessToken`** | refusal | `rc=12` / `rc=2 ARTIFACT_DIGEST_MISMATCH:bridge-trace.jsonl` |
| `trace-row-public-sentinel` (same row, body `0`) | `None` | refusal | `rc=12` / `rc=2` same mismatch |
| `trace-prose-not-json` (append non-JSON prose to the ledger) | `read_sealed_material` raises `Unreadable: …/bridge-trace.jsonl has a line that is not JSON` | — | — |
| `dashboard-undeclared-clean` (add `dashboard/view.txt`, leave the manifest alone) | `None` | `DASHBOARD_CARRIER_NOT_SEALED` | `rc=12` / `rc=2 UNDECLARED_FILE:dashboard/view.txt` |
| `dashboard-declared-clean` (add the file **and** a manifest `artifacts` entry) | `None` | **`None`** — carriers 14 → 15 | `rc=12 evidence manifest artifact size must be an integer` / `rc=1 MinekinError` |
| `dashboard-declared-secret` (declared entry, body in the file) | `None` | **`AUTH_BODY_EXPOSED:dashboard/view.txt:accessToken`** | same `rc=12` / `rc=1` |
| `manifest-without-text-carriers` (drop every text-suffixed entry) | **`NO_EXPOSURE_CARRIERS_READABLE`** | refusal | `rc=12` / `rc=2 BUNDLE_DIGEST_MISMATCH, UNDECLARED_FILE:asserter-inp…` |

**What that settles.**
- The judgement is not a string-only instrument: the two red rows are read out of files the
  manifest declares, by name (`client/latest.log`, `bridge-trace.jsonl`), and the same
  field with the public sentinel body stays green in both file shapes — so the 公版哨兵保护
  of §2.5 rule 3 holds *through* the file path, and the red is caused by the body rather
  than by the field name appearing.
- The digest guard covers the exposure carriers themselves: every tampered copy is refused
  (`ARTIFACT_DIGEST_MISMATCH:<the very carrier>`, `verify rc=12`, rejudge `unjudged`), and
  the guard answers even when the exposure verdict is green (`log-public-sentinel`,
  `trace-row-public-sentinel`) — the two instruments are independent, so a run cannot be
  quietly rewritten into a clean 090.
- An unreadable ledger is not a clean ledger: making the trace non-JSON raises `Unreadable`
  by name rather than returning zero exposures.
- **The Dashboard half's refusal is carrier-driven, not a constant**: the clause answers
  (`None`, and red on a real body) the moment a `dashboard/` carrier is declared in the
  manifest — while the *seal* channel refuses the hand-made entry for lacking a well-formed
  `size`, and refuses the undeclared file as `UNDECLARED_FILE`. That is the exact shape of
  the 主控保留 decision this document keeps open: a Dashboard answer requires genuinely
  sealing such a carrier (schema `minekin.p0.evidence.v1`, which re-seals the volume), not
  editing a judgement.
- `NO_EXPOSURE_CARRIERS_READABLE` is reached and named, so "nothing to scan" is not
  reportable as a clean scan.

**What this does not do.** It closes nothing: on real sealed bytes the parent row still
answers `DASHBOARD_CARRIER_NOT_SEALED` for the Dashboard half (row `control` above, and the
volume-wide 65/0 census of §2.7), the case stays `non_mandatory`, no 非门禁子案 id was
created, and no carrier was sealed. Both clauses ran on `/tmp` copies only.

### 2.9 The 崩溃 half, driven on a crash report that is genuinely sealed (主控, round 18, 2026-09-27)

§2.7/§2.8 measured the log and JSONL carrier shapes. The row's second word — 崩溃 — was
still only argued from suffixes, so this round drove it against real sealed crash-report
bytes. Reproduce (canonical volume read-only; every mutation in a labelled `/tmp` copy;
nothing sealed):

```bash
export MSYS_NO_PATHCONV=1; REPO="$(cygpath -m "$PWD")"
docker run --rm --entrypoint /bin/bash -w /src -v "${REPO}:/src:ro" \
  -v minekin-runner-data:/data:ro -e MINEKIN_HOME=/data -e PYTHONPATH=/src/src \
  minekin-runner:local -lc 'bash /src/.tmp/m-r18-090-crash.sh'
# log: .tmp/m-r18-090-crash.log (rc=0); attribution probe: .tmp/m-r18-case-attribution.sh
```

Census first, with a positive control (`.tmp/m-r18-090-crash.log`): of **99** bundles on the
volume, **3** hold a sealed file under `client/crash-reports/` —
`kin-04 / 8164024d769241c5a85d196fd4b1fe57` (`crash-2026-09-26_12.24.07-client.txt`),
`kin-e-rr-seal / 787168062c4047b48e32620984d6d814`, and
`kin-e-rr-seal2 / 6286f1e5a4a6403b9cfb3b564f2b3118`; while the `kin-e-aba` roots that carry
OFFLINE-100's triple hold **5** bundles and **0** crash reports. The first is the bundle
driven below: 10 text carriers, the crash report among them (`crash_carrier_declared=True`),
`bundle_digest 70380d06e752403dcc484656b9ea39ce404058a9a8bca15441ca9001e57ed2c2`.

The denominator was re-derived on purpose (`.tmp/m-r18-bundle-census.sh`,
`.tmp/m-r18-bundle-census2.sh`): walking every `/data/<name-root>/*/run/evidence/<dir>`
gives `total_bundle_dirs=99`, all under `/data/kin`, all named 32-hex, all holding a
`manifest.json`, and no odd-named sibling (`odd_names=[] count=0`). So 99 is the
directory-side whole volume, and the 105/107 figures quoted by earlier inventory rows are
ledger-side counts — a census in this document states which of the two it used.

| drive (line appended to the sealed crash report) | 载体半句 | Dashboard 半句 | `evidence verify` |
| --- | --- | --- | --- |
| `control` (untouched) | `None` | `DASHBOARD_CARRIER_NOT_SEALED` | `rc=0`, 10 artifacts |
| `crash-json-real-secret` (`{"accessToken": "<64 a>"}`) | **`AUTH_BODY_EXPOSED:client/crash-reports/crash-2026-09-26_12.24.07-client.txt:accessToken`** | refusal | `rc=12` |
| `crash-json-public-sentinel` (same line, body `0`) | `None` | refusal | `rc=12` |
| `crash-flag-real-secret` (`--accessToken <64 a>`) | **`AUTH_BODY_EXPOSED:…:accessToken`** (same carrier) | refusal | `rc=12` |
| `crash-flag-public-sentinel` (`--accessToken 0`) | `None` | refusal | `rc=12` |
| `crash-clientid-xuid-sentinel` (`{"clientId": "0", "xuid": "0"}`) | `None` | refusal | `rc=12` |

**What that settles.**
- The 崩溃 half is judgeable at file level, not just in a unit test: a crash report is a  manifest-declared carrier (`.txt` ∈ `EXPOSURE_CARRIER_SUFFIXES`), and the judgement goes
  red inside its real bytes under both field shapes — a JSON field and an `--option value`
  pair — naming the carrier and the field.
- The public-sentinel protection of §2.5 rule 3 survives the crash path: body `0` for
  `accessToken`, `clientId` and `xuid` stays `None` in three separate drives, so the red in
  rows 2/4 is caused by the body, not by the field name appearing.
- The seal's digest guard covers this carrier class too: all five mutated copies are refused
  with `rc=12`, including the three whose exposure verdict stayed green.
- **A new reading boundary, and it cuts against a tempting claim.** `run-document.json`
  carries no case-identification field (`.tmp/m-r18-case-attribution.sh`: distinct values
  read from `case_id`/`case`/`case_ids` across all 99 bundles = `[]`), so *which case a crash
  belongs to* is not readable from bundle bytes. The three carrier bundles are attributable
  to the `CORE-030` family only through E's own records (`E-RR` names both `kin-e-rr-seal*`
  re-runs), not through the carriers. Therefore 「OFFLINE 家族的崩溃载体为零」 is a statement
  about named kin roots, and for the registered 090 row the crash half stays **无该家族载体**,
  which is not the same fact as 「测过且计数为 0」.

**What this does not do.** Nothing was sealed, no case was moved, and 090 is not closer to
PASS: on its own registered evidence the row still has no crash-report carrier and still
answers `DASHBOARD_CARRIER_NOT_SEALED` for the Dashboard half. The crash bytes driven above
are another case's sealed run, used — as §2.8 used the log/JSONL carriers — to show the
instrument reads files rather than an invented set.

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
  `tools/assert_case_evidence.py:747-758`).
- Green iff `kin_id` is a single value across both timelines and equals the input's
  `kin_id`; every previous-timeline row's `run_id` equals `previous_run_id`; every
  this-timeline row's `run_id` equals `run_id` (the scoping the sealer guarantees by
  construction, `previous_run_rows`/`ledger_rows`, `tools/assert_case_evidence.py:282-344`).
- This is the "重启" half: `previous_run_id` empty ⇒ `PREVIOUS_IS_FIRST_RUN`, no verdict
  fabricated (`previous_run_rows` doc: "Empty when this run is the Kin's first").

**B. `the_external_identity_and_world_context_do_not_cross_runs` — 重启那一半（主控判定：不足以证明整条 A→B→A）**

- External identity (server's own record, not the client's claim): in
  `server/usercache.json`, the entry for `asserter-inputs.json:username` must equal
  `str(offline_player_uuid(username))` (`src/minekin_core/domain/offline_identity.py:39`) —
  the same rule the existing runtime asserter applies in
  `server_observed_join_identity` (registered name, `tools/assert_case_evidence.py:1028-1044,
  3447`); the new function must not re-derive that rule from prose.
- Non-crossing of session/world coordinate: the sets of `session_id` (and of
  non-null `world_context_id`) over the two timelines must be disjoint; a run's session
  must not resume the dead run's (`the_restart_runs_as_a_new_session` is the registered
  predecessor with the same shape, `tools/assert_case_evidence.py:2041-2064`).
  `generation` alone may legitimately restart per run — cite, do not assert, unless M
  pins otherwise.
- **Scope warning (主控判定, retained here so no reader re-expands it):** this clause
  compares *two adjacent runs* only. It is a necessary condition of the 重启 half, and
  by itself does **not** prove the contract row's A→B→A — the three-run closure lives
  in §3.5 C, and only there.

**C. A→B→A 三段的完整断言集合（主控钉下的必要条件：五条缺一即整条不成立）**

For runs A1 → B → A2 (each its own sealed bundle, chained via
`previous_run_id`/`supersedes_run_id` in the frozen `EVIDENCE-SEQUENCE` shape), with
timelines read pairwise per §3.3. Shared definitions, all from bundle fields actually
present (measured this session on the `:ro` volume):

- **run set**: each timeline's rows carry exactly one `run_id` (sealer-scoped by
  construction, `previous_run_rows`/`ledger_rows`, `tools/assert_case_evidence.py:282-344`);
  the triple's three `asserter-inputs.json` files (`kin_id/run_id/username/previous_run_id`,
  `:747-758`) name the three runs.
- **session of a run**: its `session_id` as attributed in the ledger (`_ledger_session`
  path used by `the_restart_runs_as_a_new_session`, `:2041-2064`). Measured this session:
  each OFFLINE timeline carries exactly **one** non-null `session_id` value
  (`f2ecb728…`: `d852ccf0…`; `3d5606ce…`: `6e92b314…`; their previous-run traces name
  the predecessor's single value, disjoint from the current one).
- **"获确认的" world context, in bundle fields** — no prose: for a run against the
  controlled isolated server it is the tuple `(profile_id, revision, level-name)` with
  (a) `profile_id` and `revision` read from `trusted/server-profile.json` (sealed fields,
  measured in `3d5606ce…`: `profile_id="p0-controlled-offline-loopback"`, `revision=
  "c742c476…"`, plus `host/port/auth_mode/visibility`);
  (b) `level-name` read from `server/server.properties` (measured: `:27`
  `level-name=world`) and required to equal the quoted name of the
  `Preparing level "<name>"` line in `server/server.log` (measured: `:61`
  `Preparing level "world"`);
  (c) **确认** = the server observed this run's identity in that world: `server/server.log`
  carries `<username> joined the game` for the run's own `asserter-inputs.json:username`
  (`RunMaterial.join_line`, `tools/assert_case_evidence.py:451-454`; measured `:67`), and
  `server/usercache.json[username] == str(offline_player_uuid(username))` — exactly the
  registered `server_observed_join_identity` rule (`:1028-1044`; `offline_identity.py:39`),
  the same "confirmed by the first player-equivalent observation" shape as the activation
  ladder's rule 3 (`src/minekin_core/domain/world_activation.py:11-12, 207`).
  A world context nobody confirmed is not a world context: missing join line ⇒
  `JOIN_NOT_LOGGED`, missing usercache entry ⇒ `IDENTITY_NOT_RECORDED`, mismatch ⇒
  `IDENTITY_UUID_MISMATCH:<uuid>` — all named non-green, none of them green.
  **Measured negative fact:** the ledger column `world_context_id` exists
  (`_LEDGER_COLUMNS`, `tools/assert_case_evidence.py:251-257`) but is null in **all rows
  of all 94 sealed `bridge-trace.jsonl` files** on the volume (this session's `:ro`
  recount: 0 non-null rows), so the confirmed-context judgement above reads the
  `trusted/` + `server/` carriers; inventing a ledger equality over nulls is forbidden.

Clauses, each named with its judgement and red/green condition:

- **C1 `the_kin_id_is_single_across_the_triple`** — ①: `kin_id` has one value over all
  three timelines and equals all three `asserter-inputs.json:kin_id`. Green iff single;
  red otherwise (`KIN_ID_NOT_SINGLE_ACROSS_TRIPLE`), per-run scoping per the run-set
  definition. (Subsumes A across three runs; A remains the two-run form.)
- **C2 `the_triple_runs_as_three_distinct_sessions`** — ②: the three runs' `session_id`
  sets are pairwise disjoint, each a single non-null value (shape above). Green iff
  three distinct; red otherwise (`SESSIONS_NOT_THREE_DISTINCT`); an unattributable
  timeline is `NO_SESSION_ATTRIBUTION_IN_LEDGER`, not green.
- **C3 `the_two_a_runs_share_one_confirmed_world_context`** — ③: W(A1) and W(A2) both
  exist *and are confirmed* per the definition above, and their
  `(profile_id, revision, level-name)` tuples are equal. Green iff equal-and-confirmed;
  red `A_ENDS_NOT_THE_SAME_CONFIRMED_WORLD`; either end unconfirmed ⇒ that end's named
  non-green code, not green.
- **C4 `the_b_run_does_not_cross_into_a`** — ④: B's session set and confirmed-context
  tuple appear in neither A1's **own timeline** nor A2's **own timeline**, A's confirmed
  context tuple ≠ B's, and the pairwise §3.5 B disjointness holds for both A1|B and B|A2.
  Red `B_CROSSES_INTO_A` on any shared session/world-context occurrence in those scopes.
  **Scope corrected by 主控 (round 14, 2026-09-27).** This row used to read "in neither
  A1's nor A2's timeline **or carrier pair**", and that form is unsatisfiable by
  construction: a bundle's carrier pair includes the sealed `previous-run-trace.jsonl`,
  which *is* the predecessor's timeline, so in any honest A→B→A run A2's carrier pair
  holds B's own session. Measured on the sealed triple — A2
  `7ff026e4bca646c58f8eee2c2b000867` `previous_timeline.sessions =
  ["4ba0825eee234506bcdca524d1631df9"]`, and that value is B
  `a26e2c35b66e498b828900877397a73f`'s own session. The judgement therefore scopes to
  each run's **own** rows plus the sealed context tuples; it never asks the predecessor
  trace to be empty. The wording is a design-doc change only — `case_version` digests the
  registered function bytes and the fixture, not this file — so it moves no registry
  digest and invalidates no sealed bundle.
- **C5 `the_external_identity_is_server_observed_in_all_three`** — ⑤: for each of the
  three runs, the registered `server_observed_join_identity` rule holds against that
  bundle's own `server/usercache.json` + `server/server.log` — no re-derivation of the
  rule, no client-side self-claim. Red = the rule's own named codes.

The on-volume situation as measured at draft time: 46 sealed previous-run links whose both
ends exist (B1-b-0 probe, incl. the OFFLINE chain `f2ecb728…(010) → 3d5606ce…(020) →
ee9d5ad3… / f0f35035…(030 children)`), and at that point **no A→B→A triple had been
produced on the volume for identity-switch purposes**.

**Updated by 主控 (round 14, 2026-09-27): that first controlled run now exists.** Kin root
`kin-e-aba`, A→B→A = attempts seq 3/4/5 — A1 `cd215ca1caf74bd0b230abe8de72e568`,
B `a26e2c35b66e498b828900877397a73f`, A2 `7ff026e4bca646c58f8eee2c2b000867` — all `SEALED`,
each `evidence verify` `verified: true` with 13 artifacts, each `rejudge_evidence`
`status: agrees` at `case_version a44289e8cdbc0643eebb7ff73985014a8fb87e176c622fd2a1c085f7abcc8a3b`,
and the two failed warm-up attempts (`fd516eb6…`, `c96aa8bd…`, both `HANDSHAKE_TIMEOUT`)
left on the volume untouched. Clause-by-clause readings are in
`docs/p0-offline-100-a-b-a-run-2026-09-27.md`. What the run supplies is real bytes for
C1, C2, C5 and — under the corrected C4 scope — C4's disjointness, plus C3's tuple
equality. What it does not supply is the cross-bundle chain carrier, so the registered row
still answers `A_B_A_TRIPLE_NOT_SEALED` and the definition still closes nothing: closing it
needs 主控 to decide whether evidence schema `minekin.p0.evidence.v1` grows a field, which
would re-seal the volume.

### 3.6 Minimal counterexamples / positive controls (design; runtime state per item below)

Positive controls (available material): runs `3d5606ced37849e3b17a4c418fa33ab4`
(OFFLINE-020, previous `f2ecb728df754826abf4a052be138a2d` sealed),
`ee9d5ad3d57344da8452069102e27216` and `cb5e2119845e41868c28e5aeb1370ce3`
(OFFLINE-030 children) — all five OFFLINE-030*/010*/020* bundles qualify per §3.3
declared-path census. **But these are previous-run *pairs*: they can only ever control
the 重启 half (§3.5 A/B). At draft time the volume had never produced any A→B→A triple
for identity switching (named in §3.5 C), so no positive control existed this side of a
controlled run for clauses C1-C5 — every C-clause probe below was design-only, 未测.**
**Updated by 主控 (round 14, 2026-09-27): the controlled triple now exists** (§3.5 C's
update paragraph), and with it the positive control for C1, C2, C4 (corrected scope) and
C5 is measured on real sealed bytes rather than designed — 主控 re-read all three bundles
independently with `rejudge_evidence` + `evidence verify` on the current trunk bytes. The
counterexamples are a different axis: at round 14 only 8's first half had been run
(E's labelled-copy trial, §6 of the run record); the round-16 note below adds 9, 10 and 11,
and §3.7 drives the server-side clause of 4's family (dropping or malforming the identity
cache, not the uuid remap this item names). Items 1-3 and 5-6 stay design-only.
Counterexamples, each a single
named-field edit on an in-memory copy of those sealed bytes (never the
volume):

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

Triple counterexamples for §3.5 C (each designed against an A1/B/A2 triple; the truth
 carriers are the sealed three, so an edit is made on a labelled out-of-volume copy and
 the canonical volume is never written. **Updated by 主控 (round 14, 2026-09-27): the
 triple now exists** — `kin-e-aba` sequences 3/4/5, digests in §3.5 C's update paragraph.
 8's first half has been run on such a copy; **round 16 (2026-09-27) executed 9, 10 and 11**
 — E's `p0-offline-100-counterexamples-2026-09-27.md`, merged as `5dbcc8a`, and 主控's
 independent recheck (`.tmp/m-r16-cx-recheck.sh`, log `.tmp/m-r16-cx-recheck.log`):
 9 → `KIN_ID_NOT_CONTINUOUS:kin-e-aba,kin-e-aba-forged` with `verify rc=12`, 10's cross
 variant → `SESSION_ID_SHARED_ACROSS_RUNS:<A1's session>`, 11 → `IDENTITY_NOT_RECORDED` with
 `ARTIFACT_MISSING:server/usercache.json`. **10's literal variant (A1's `session_id` reused
 by A2) answers `None` on both clauses** — the registered judgement compares only the
 adjacent pair, so 「两次相邻 run 的 session_id 不同」 is not evidence for the triple, and
 making it judgeable would need the cross-bundle carrier listed under 主控保留 below):

8. forge A2's carriers so its confirmed context names **B's** world (server.properties
   `level-name` / `Preparing level` moved to B's, or B's `server-profile.json` tuple)
   ⇒ C3 red `A_ENDS_NOT_THE_SAME_CONFIRMED_WORLD` (and C4 red).
   **Half-executed** (round 14; §6 of the run record): on a labelled /tmp copy of A2, the
   single field `level-name` → `OTHERWORLD` makes A2's tuple unequal to A1's and makes that
   copy's properties digest disagree with the sealed manifest. Moving the carriers onto
   **B's** actual world, `Preparing level` included, is still 未测.
9. forge `kin_id` to differ in one of the three segments ⇒ C1 red
   `KIN_ID_NOT_SINGLE_ACROSS_TRIPLE`.
10. forge A1 and A2 to reuse the **same** `session_id` ⇒ C2 red
    `SESSIONS_NOT_THREE_DISTINCT`.
11. delete `server/usercache.json` from one segment ⇒ that segment is **not green**:
    the registered rule returns the named `IDENTITY_NOT_RECORDED`
    (`tools/assert_case_evidence.py:1037-1038`) — 不可探/证据缺, reported as such.

### 3.7 The server-evidence clause, driven conjunct by conjunct (主控, round 19, 2026-09-27)

§3.6 left the fifth requirement — 外部身份取服务端证据 — as design. The registered clause
(`the_world_and_the_identity_are_the_server_s_record`, `tools/assert_case_evidence.py:3778`)
reads four third-party accounts and requires three to agree before it even looks at the join,
so this round asked whether *each* of those conditions can actually fail, on sealed bytes.
Reproduce (volume `:ro`, mutations in labelled `/tmp` copies, nothing sealed):

```bash
export MSYS_NO_PATHCONV=1; REPO="$(cygpath -m "$PWD")"
docker run --rm --entrypoint /bin/bash -w /src -v "${REPO}:/src:ro" \
  -v minekin-runner-data:/data:ro -e MINEKIN_HOME=/data -e PYTHONPATH=/src/src \
  minekin-runner:local -lc 'bash /src/.tmp/m-r19-100-server-clause.sh'
# log: .tmp/m-r19-100-server-clause.log (rc=0)
```

First the whole `kin-e-aba` root: **5** sealed bundles, of which three answer `None` from the
clause and two — `c96aa8bd26b2477fabd869214b2ed44c`, `fd516eb623704d0db454fe636af7dbc0` —
answer **`JOIN_NOT_LOGGED`** (named, not attributed: see the case-field boundary in §2.9).
The driven bundle is the first of the clean three, `7ff026e4bca646c58f8eee2c2b000867`
(E's A2; `bundle_digest 0cc1fb99111d4cef11c47dcb86305784130b6a9746bc77251d5289a80dfb92b7`,
13 artifacts, control `verify rc=0`). What its own sealed bytes say: server log
`Preparing level "world"`, `server.properties level-name=world`,
`profile_id=p0-controlled-offline-loopback`,
`revision=c742c47670997ac5f8f9e9f3bcca6304a041b253fe953dc0906923affb798d4b`.

| mutation (one field per copy) | clause answer |
| --- | --- |
| control | `None` |
| log stops naming the world it opened | `SERVER_LOG_NEVER_NAMED_THE_WORLD_IT_OPENED` |
| log names `m19-other-world` while the properties still say `world` | `SERVER_OPENED_A_WORLD_OTHER_THAN_ITS_PROPERTIES:m19-other-world` |
| `level-name` removed from `server.properties` | `SERVER_PROPERTIES_SAY_NOTHING_ABOUT_THE_WORLD` |
| profile `revision` set to a non-digest | `SERVER_PROFILE_HAS_NO_REVISION_DIGEST:'not-a-digest'` |
| profile `profile_id` emptied | `SERVER_PROFILE_NAMES_NO_WORLD` |
| `trusted/server-profile.json` dropped | `NO_SEALED_SERVER_PROFILE` |
| `server/usercache.json` replaced by an empty player list | `read_sealed_material` raises `Unreadable: … usercache.json is not a list of identities` |
| `server/usercache.json` dropped | **`IDENTITY_NOT_RECORDED`** — with profile, properties and log all still agreeing |

Every mutated copy was refused by the seal (`evidence verify rc=12`), so the clause and the
integrity channel stay independent instruments, as in §2.8.

**What that settles.**
- The clause is neither always-true nor single-condition: seven distinct named refusals, each
  caused by exactly one changed field, and each reachable through the file path rather than a
  hand-built `RunMaterial`.
- The 服务端证据 requirement has teeth: with the server's own join record removed, the clause
  answers `IDENTITY_NOT_RECORDED` even though the world-side accounts all agree — so a run
  cannot satisfy this clause out of the client's claims, which is what 卡面第 2 条 asked for.
- A malformed identity cache is named rather than silently read as "nobody joined"; a missing
  one is `IDENTITY_NOT_RECORDED`. Those are different answers and both are reachable.
- The gate side is unchanged after rounds 17-19: `gate_payload_sha256` still
  `cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6`, `report_rc=1`,
  `W30`/`p0-core` still `promotable False` (`.tmp/m-r19-payload-after-r18.log`).

**What this does not do.** It does not make OFFLINE-100 judgeable: the parent row still
answers `A_B_A_TRIPLE_NOT_SEALED`, 「首尾 A 同一获确认 world context」 and 「三次不同会话」
stay unjudgeable by construction (§3.6 and the by-construction note in
[[project-offline-100-triple-not-judgeable-by-construction]]), the two `JOIN_NOT_LOGGED` runs
are named without a case attribution, and nothing was sealed, registered or promoted.

### 3.8 The restart-pair clauses, driven field by field (主控, round 20, 2026-09-27)

§3.6 left items 1, 2, 3 and the 5/6 pair as design. They are now driven on the same sealed
A2 bytes §3.7 used — one changed field per labelled `/tmp` copy, volume `:ro`, nothing sealed:

```bash
export MSYS_NO_PATHCONV=1; REPO="$(cygpath -m "$PWD")"
docker run --rm --entrypoint /bin/bash -w /src -v "${REPO}:/src:ro" \
  -v minekin-runner-data:/data:ro -e MINEKIN_HOME=/data -e PYTHONPATH=/src/src \
  minekin-runner:local -lc 'bash /src/.tmp/m-r20-100-ab-clauses.sh'      # log …/m-r20-100-ab-clauses.log
# then, for the field-location question that follow-up answered:
#   .tmp/m-r20b-previous-run-id.sh  and  .tmp/m-r20c-asserter-inputs.sh
```

Census of the driven pair (all read from the bundle, not asserted): `kin-e-aba` /
`7ff026e4…`, `previous_run_id = a26e2c35b66e498b828900877397a73f`, **19** rows on this run's
carrier `bridge-trace.jsonl` and **19** on the previous run's carrier
`previous-run-trace.jsonl`, `here_sessions = ['ed3fdc067e294d5e9b356c34ca9a058b']`,
`prev_sessions = ['4ba0825eee234506bcdca524d1631df9']`; the unmodified copy answers `None /
None` with `verify rc=0` (13 artifacts, `bundle_digest 0cc1fb99…`).

| mutation (one field, one carrier) | `kin_id` clause | `session` clause |
| --- | --- | --- |
| control | `None` | `None` |
| §3.6 1 — previous carrier's `kin_id` → `kin-m20-foreign` | `KIN_ID_NOT_CONTINUOUS:kin-e-aba,kin-m20-foreign` | `None` |
| §3.6 2 — one previous row's `run_id` → foreign | `PREVIOUS_ROWS_NOT_ONE_RUN:m20-not-the-previous-run` | `None` |
| §3.6 3 — one **this-run** row's `kin_id` → foreign | `KIN_ID_NOT_CONTINUOUS:kin-e-aba,kin-m20-foreign` | `None` |
| one this-run row's `run_id` → foreign | `THIS_TIMELINE_ROWS_ARE_NOT_ONE_RUN:m20-not-this-run` | `None` |
| one this-run row's `kin_id` emptied | `LEDGER_ROW_NAMES_NO_KIN` | `None` |
| §3.6 5 — previous carrier takes **this run's** session | `None` | `SESSION_ID_SHARED_ACROSS_RUNS:ed3fdc06…` |
| §3.6 6 — a foreign session only in this run's rows | `None` | **`None`** (the control for 5) |
| previous carrier emptied | `PREVIOUS_TRACE_NOT_SEALED` | `PREVIOUS_TRACE_NOT_SEALED` |
| previous rows name no session | `None` | `PREVIOUS_RUN_HAS_NO_SESSION_ATTRIBUTION` |
| this-run rows name no session | `None` | `NO_SESSION_ATTRIBUTION_IN_LEDGER` |

**What that settles.**
- Items 1, 2, 3, 5 and 6 of §3.6 are measurements now, not design: each named refusal is
  reachable through a file the reader actually opens, and the two sides of the comparison are
  separately reachable (the same `KIN_ID_NOT_CONTINUOUS` message arrives from the previous
  carrier *and* from this run's carrier).
- Item 6 is the non-vacuity proof for item 5: adding a session value that appears **only** in
  this run's rows leaves both clauses green, so the rule really tests *crossing*, not
  uniqueness — the pair cannot be satisfied by inventing a new session either.
- Absence is refused rather than counted: an empty previous carrier is
  `PREVIOUS_TRACE_NOT_SEALED`, and rows that exist but name no session are
  `PREVIOUS_RUN_HAS_NO_SESSION_ATTRIBUTION` / `NO_SESSION_ATTRIBUTION_IN_LEDGER` — three
  different answers, all reachable, so neither side of the pair can go green on a hole.
- **Where `previous_run_id` actually lives** (this round's second, unplanned measurement):
  clearing it in `run-document.json` is a **no-op** — the first drive printed the real
  top-level keys (`argv_digest, generation, kin_id, overlay, pid, recovery, run, run_id,
  schema_version, session_id, started_at, status`) and the clause stayed `None / None` with
  `verify rc=0`. The field is carried in **`asserter-inputs.json`**, whose complete key set is
  `['kin_id', 'previous_run_id', 'run_id', 'schema_version', 'username']`; clearing that one
  field makes both clauses answer **`PREVIOUS_IS_FIRST_RUN`**, and it still answers
  `PREVIOUS_IS_FIRST_RUN` when the previous trace carrier is emptied too — the field test is
  checked before carrier emptiness. That key inventory re-measures, at field-name level, the
  premise of 卡面第 1 条: `asserter-inputs.json` carries no `token`/`xuid`/`clientId` to read.
- Every forged copy above was refused by the seal (`evidence verify rc=12`); the only copies
  that stayed `rc=0` were the control and the two no-op edits, which is the same
  instrument-independence as §2.8 and §3.7.
- Gate side unchanged: payload still `cfa0f1184bee30df6a1d9fcf45778c9cef074ece6761c47fe7d6b9f49863afd6`,
  `report_rc=1`, `W30`/`p0-core` `promotable False`, `W30.absent = OFFLINE-060/080`,
  `non_mandatory 11 (W30) / 24 (p0-core)`, `misattributed 0`
  (`.tmp/m-r20c-asserter-inputs.log`).

**What this does not do.** These are the **pair** clauses (the 重启 half, §3.5 A/B). Driving
them does not touch the triple: the parent row still answers `A_B_A_TRIPLE_NOT_SEALED`, and
「首尾 A 同一获确认 world context」/「三次不同会话」 stay unjudgeable by construction (§3.6,
[[project-offline-100-triple-not-judgeable-by-construction]]). §3.6 item 4's literal uuid
remap (`SERVER_SAW_ANOTHER_IDENTITY`) is still design — §3.7 drove the neighbouring
drop/malform refusals, not that edit. Nothing was sealed, registered, or promoted.

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
rc=0. **Stop cell reported; this draft is the patch-set input for M.** 主控已钉 (§7.2):
asserter functions、`tools/check_case_assertions.py:170` 的 `IMPLEMENTATIONS` 条目与
manifest 登记**由 M 独占实施，逐案提交并测试**。本卡不写 fixture、不动 `tools/**`;
this round-2 revision likewise adds nothing beyond edits to this one docs file.

## 6. Evidence boundaries and four-state declaration

- Measured this session (§5): volume census, gate rows, registry absence, mount
  identity. Round-2 re-measurements on the `:ro` volume, cited where they appear:
  standalone-`0` token recount over all 94 `bridge-trace.jsonl` files (§2.6),
  `world_context_id` null census (0 non-null rows in 94 files) and per-run single
  `session_id` values (§3.5 C), and the `asserter_inputs_bytes` key list
  (`tools/assert_case_evidence.py:747-758`, §2.5 rule 1). **Design-only, 未测 this
  session**: every §2.7/§3.6 probe/reversal run (their
  predecessors were exercised in the prior conversation whose logs are `未提交` and not
  citable as evidence per this sub-slot's rules — re-run them in the follow-up slot that
  also gets the asserter functions).
- Four states: **未合并 main / 仅在本分支 (`codex/minekin-offline-090-100`) /
  无真封存证据新增（本卡全程 `:ro`，未建 attempt、未封 bundle）/ 断言运行读法尚未量**。
- Nothing here connects to or reads any remote/third-party server; the isolated-server
  constraint of contract `:158` is written into both case definitions.

## 7. 主控 rulings (formerly open questions for M — all closed here as named facts)

1. **Closed — 090 exposure reading pinned.** The offline sentinel is a **public
   non-secret value** (`access_token_argv="0"`, `client_id_argv=EMPTY_ARGV`,
   `xuid_argv=EMPTY_ARGV`, `offline_session.py:71, 82`); any digit `0` or empty value
   occurring anywhere is **not** a leak. The judgement is 认证正文在字段/参数上下文中的
   暴露 (argv `--accessToken`/`--access-token` key-value, JSON key `auth_access_token`
   per `offline_session.py:166`, `xuid`/`clientId` key-value pairs), as written into
   §2.5. Credential literals are **not** read from `asserter-inputs.json` — it carries
   no token/xuid/clientId keys at all (§2.5 rule 1). Harness-side redaction of
   authentication fields stays as-is; it is never lifted to make the assertion green.
2. **Closed — implementation ownership.** The asserter functions, the
   `IMPLEMENTATIONS` entries in `tools/check_case_assertions.py:170`, and the manifest
   registration are **M's exclusive surface**, landed case by case with their own tests.
   This card writes no fixture and touches no `tools/**` file; the fixtures proposed in
   §2.1/§3.1 remain design text until M's per-case commits.
3. **Closed — Dashboard half of 090.** This round does **not** commission a
   dashboard-evidence carrier. The gap is kept on the parent case by name:
   `OFFLINE-090-BUNDLE-CARRIERS-001` (non-gate sub-case, §2.1) carries only the
   log-and-crash half of the row, and **父案 `OFFLINE-090` 保留 Dashboard 半句的缺口，
   状态不得为 PASS** — it must not be marked PASS, nor may "registered as
   non-mandatory" be read as closure.
4. **Closed — A→B→A OFFLINE-100 schedule.** The controlled run may enter E's
   规范卷独占写窗, with two named preconditions: the judgement above (C1-C5) is frozen
   first, and H's current volume-writing task yields the window. It uses **only the
   local isolated server — the user's remote server is never contacted**. Until a full
   three-segment (A1/B/A2) evidence triple exists, OFFLINE-100 stays 未完成; the
   definition in §3.5 C changes nothing by itself.
5. **Closed — `OFFLINE-070` gets its own card.** 070 is registered **单独排卡**, not
   batched with 090/100: its `identity_revision`/人格根 gap is not a drive-by fix for
   these two cases. Any batching suggestion in earlier drafts of this file is withdrawn.
