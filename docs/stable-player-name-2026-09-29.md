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
branch. The panel/service rename card is NOT implemented or verified yet.
No remote connection was performed to investigate the user's pasted server log.
Names `Beerooski` and `MCOcto` have not been attributed to Qoder: server-side log
entries alone do not establish which client or automation originated them.
