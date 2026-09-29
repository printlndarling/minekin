# Stable offline player name — user decision, 2026-09-29

New single-player identities default to the exact lowercase username `minekin`.
Persisted Kin identity roots remain authoritative across restart, disconnect,
death and server changes. Never randomly regenerate a username per session,
retry with another identity after refusal, or automatically rename existing Kin.
An explicitly configured initial username remains supported for compatibility.
Blank or invalid explicit configuration is rejected, not silently defaulted.

Offline UUID is derived from the exact username by `offline_player_uuid`.
Changing the name (including case) therefore changes the server-side offline
UUID: this is not a promise that inventory, location or advancements migrate.
Kin ID, session ID and Minecraft player UUID are different identifiers.

## Follow-up implementation card: STABLE-PLAYER-NAME-PANEL-001

Queue at the next safe integration boundary; do not introduce a second NEXT.
User authorizes a narrow local Dashboard identity-settings write surface, not
general session control, public networking or remote server changes.

- Show current stored username and offline UUID; default new identity to `minekin`.
- Rename only on an explicit user submission while the Kin is stopped, with
  confirmation explaining UUID/player-data consequences; refuse active sessions.
- Use the Core identity service, not direct SQL from the Gateway. Validate names,
  persist an identity revision atomically, keep the stable Kin ID, and ensure the
  next launch uses the committed identity. Do not edit old evidence or run records.
- Local write protection must be specified and tested (loopback alone is not
  sufficient protection against cross-origin requests). Fail closed on malformed
  requests, stale revisions, forbidden origins and write failures.
- Tests: restart/retry preserves name and UUID; explicit rename survives restart;
  unchanged name is idempotent; invalid names and active-session rename refuse
  without mutation; former run identities remain unchanged; failed writes atomic.
- Two concurrent clients on the same offline server need distinct explicitly
  configured names; harness fixture names `Kin`/`Kin2` do not define product defaults.
- No server-side player-data migration or claims of transparent continuity after
  rename. Existing identities require deliberate operator action, not auto-upgrade.

The config default and ledger-reopen regression test are implemented on this
branch. The panel/service rename card is now implemented and verified: see
[Panel/service rename — acceptance](#panelservice-rename--acceptance-2026-09-29).
No remote connection was performed to investigate the user's pasted server log.
Names `Beerooski` and `MCOcto` have not been attributed to Qoder: server-side log
entries alone do not establish which client or automation originated them.

## Panel/service rename — acceptance (2026-09-29)

The narrow identity-settings write this card authorizes is implemented end to end.
It is the only exception to the read-only Dashboard; nothing here starts, stops,
pauses or moves a session, and the Gateway never opens `kin_identity` for writing —
the compare-and-swap stays in `minekin_core.cli.rename.rename_identity`.

Delivered surface:
- `gateway/identity.py` — the identity read route and the one rename write, with the
  layered local-write guards (loopback `Host`, same-origin `Origin`, `application/json`,
  a per-process CSRF token handed out only by the identity GET), request validation,
  the stopped-session requirement, the `identity_revision` compare-and-swap, and a
  named refusal per failed layer. Every refusal leaves the stored identity untouched.
- `gateway/server.py` — `ROUTE_TABLE` now carries `GET /api/v1/dashboard/identity` and
  `POST /api/v1/dashboard/identity/rename`; `--routes` prints the methods so the verb
  scan sees a POST only on the sanctioned rename. A POST anywhere else is still `405`.
- `dashboard/**` — an `身份 · 改名` tab (`IdentityPanel.tsx`, `useIdentityController.ts`,
  `identityPolicy.ts`): shows the stored username, offline UUID and identity revision;
  the submit is reachable only while the Kin is stopped, the name is valid
  (`^[A-Za-z0-9_]{3,16}$`), and the operator confirmed the UUID/player-data consequence.
  A server refusal renders named, beside the identity that did not change. The CSRF
  token lives only in the adapter closure, never in the rendered model.
- `dashboard/vite.config.ts` — the `/gateway` proxy sets `changeOrigin:false` so the
  panel's own `Host` reaches the Gateway; that is what lets the authorized same-origin
  rename clear `authorize_write` where a rewritten `Host` would refuse it as
  `cross_origin`. The three reads ignore `Host` and are unaffected.

Card bullets → what proves them:
- Default `minekin`, persisted across restart/retry/death/server change:
  `tests/unit/test_identity_rename.py` (config default + ledger reopen) and the rename
  path preserving the stable Kin ID while only `identity_revision` advances.
- Real username / offline UUID / revision on the panel: the identity read route plus
  `dashboard/src/adapters/identityAdapter.test.ts`.
- Rename only while stopped, with confirmation and the UUID/no-migration notice; refuse
  active sessions: `test_gateway_identity_write.py` (`session_not_stopped`), the panel
  tests, and the live run below.
- Local write protection specified and tested (loopback alone insufficient): the
  parametrized `forbidden_host` / `cross_origin` / `unsupported_media_type` /
  `missing_or_bad_csrf_token` cases, and the atomicity assertions that a refused or
  stale-revision rename changes nothing.

Gates measured on the shipped bytes (this branch):
- Backend: `ruff check`, `ruff format --check`, `pyright` (0 errors), `pytest`
  (`test_gateway_identity_write.py` + `test_gateway_server.py` = 49 passed),
  `check_boundaries.py` OK, `verify_fixture_digests.py` OK.
- Frontend: `tsc --noEmit` + `vite build` clean; `vitest run` 124 passed (18 identity:
  12 adapter + 6 panel); `playwright test` 10 passed with the 4 live specs skipped,
  including the structural read-only boundary case still green with the new tab present.
- Live UI acceptance (`E2E_LIVE_IDENTITY=1`, real Chromium against a running
  `gateway.server` on a fresh IDLE Core root): the panel renamed `minekin`
  (revision 1, UUID `910b8332-459b-35db-8cdc-80a07a2cf72a`) to `renamed_kin`
  (revision 2, UUID `c154f42e-c52d-3204-bf43-ec0ceebcd9e5`); a second read confirmed the
  rename persisted into Core's SQLite rather than living in front-end state.

Not done and left deliberately: no gate promotion, no registry requote, no remote-server
or online-auth change, no player-data migration, and no auto-rename of existing Kin. The
config-default and ledger-reopen work above predates this section and is unchanged.
