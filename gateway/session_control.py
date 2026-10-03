"""The third authorized Dashboard write, and the first control verb: stopping a Kin's session.

`docs/gateway-dashboard-readonly-contract-2026-09-28.md` froze the reads, and the two settings
writes (the identity rename, the operator-config save) were the only exceptions until the
whole-project goal's Phase D opened session control. It does not open all of it at once, and the
order is not arbitrary. Of the four verbs a panel eventually needs — start, pause, resume, stop —
**stop is the only one this process can perform safely today**, and the reason is architectural:

* **Stop needs no new machinery.** A running session is supervised by its own `session start`
  process, and it already reads a stop request from a file the whole product owns
  (`adapters/launcher/stop_request.py`): request and receipt JSON under the run root, addressed by
  session, generation and pid. `minekin_core.cli.session.stop_session` writes that request, waits
  (bounded) for the live client to release its inputs, and then terminates only a process whose
  identity it can prove from `/proc`. So the Gateway can ask a session to stop by calling that one
  function over the persisted markers — it does not spawn, own or hold the client's socket.

* **Stop reduces, never initiates.** It releases inputs and ends activity. It cannot connect to a
  server, call a model, or replay an action, so it does not touch the restart-safety rule that a
  saved goal must never reconnect or re-execute on its own. Start is the opposite — it launches a
  JVM and joins a world — and there is no detached supervisor for the Gateway to hand that to; a
  run must be hosted by the live process that owns the Bridge IPC loop. Pause/resume would need a
  `PAUSED` session state the frozen state machine does not have. Both are honest gaps, recorded in
  the read model's `unavailableControls` rather than faked.

Since 2026-10-03 that "no detached supervisor" premise has a successor rather than a refutation:
`gateway/session_jobs.py` is a supervised, bounded start owned by the Gateway process itself, and
`ReadService.session` composes it onto this module's read — appending `start` to the available
verbs and dropping the base reason above before anything is served. This module stays the stop-only
surface its own tests pin; the served composition is pinned by the HTTP case in
`tests/unit/test_gateway_session_control.py`.

Ownership is the boundary that makes even stop safe to expose, and this layer does not weaken it:
`stop_session` terminates a pid only after proving it from its recorded argv digest, and reports a
process it cannot prove rather than killing it (a host that cannot read `/proc` proves nothing, so
it never force-terminates there and relies on the honored release). The Gateway never opens a
socket to the client or shells out; it calls one Core function and reports what came back, `blocked`
still spelled `blocked`.

The source/auth layering is not re-drawn here either: the same-origin, loopback, content-type and
CSRF checks live once in :func:`gateway.identity.authorize_write`, and the server's shared write
handler runs them before this module is reached.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

from gateway.identity import refusal
from gateway.readmodel import STALE_AFTER_MS
from minekin_core.application.ports.clock import Clock
from minekin_core.cli.session import stop_session
from minekin_core.cli.status import ObservedState, read_status

#: The read that shows whether a session can be stopped, and the write that stops it. Singular
#: `/session`; the plural `/dashboard/sessions` stays a `404` because this surface has one Kin.
SESSION_PATH: Final = "/api/v1/dashboard/session"
SESSION_STOP_PATH: Final = "/api/v1/dashboard/session/stop"

#: A stop body is a confirmation flag; anything larger is noise.
MAX_STOP_BODY_BYTES: Final = 4096

SCHEMA: Final = "kin-dashboard-session/1.0.0"

#: The one control verb this surface currently offers, and the reasons the other three are absent.
#: Kept as data in the read so a panel renders the same boundary the server enforces, rather than
#: a button that a later POST would refuse.
_AVAILABLE_CONTROLS: Final = ("stop",)
_UNAVAILABLE_CONTROLS: Final = {
    "start": (
        "starting a session launches a client and joins a world; that must be hosted by the live "
        "`session start` process, which the read-only Gateway is not"
    ),
    "pause": "the session state machine has no PAUSED state yet, so there is nothing to pause into",
    "resume": "the session state machine has no PAUSED state yet, so there is nothing to resume",
}


def session_read(
    root: Path, *, kin_selector: str | None, clock: Clock, csrf_token: str
) -> dict[str, Any]:
    """The observed session state plus what this surface can actually do about it.

    `stopAllowed` mirrors the exact predicate the write enforces — a session that is not idle — so
    the panel enables the button for the same reason the server would act, not a poll that raced a
    launch. The state and the availability are derived from the same `read_status` call the rename
    form already trusts.
    """

    state = read_status(root, kin_selector=kin_selector).state
    return {
        "schemaVersion": SCHEMA,
        "state": state.value,
        "stopAllowed": state is not ObservedState.IDLE,
        "availableControls": list(_AVAILABLE_CONTROLS),
        "unavailableControls": dict(_UNAVAILABLE_CONTROLS),
        "csrfToken": csrf_token,
        "observedAt": clock.utc_now().isoformat(),
        "staleAfterMs": STALE_AFTER_MS,
    }


def stop_from_request(
    root: Path, *, kin_selector: str | None, body: Mapping[str, Any]
) -> tuple[int, dict[str, Any]]:
    """Stop the Kin's recorded clients, refusing anything that is not an explicit, live stop.

    The verb itself is Core's `stop_session`, so the ownership proof and the
    release-before-terminate ordering stay one definition whether a stop arrives from the CLI or
    a panel — this layer adds no termination logic of its own. A refused request never reaches
    Core, and an idle Kin is reported as `session_not_running` rather than run through a stop
    that would do nothing and read as a success. The origin/CSRF/content-type check has already
    run in `authorize_write`.
    """

    reason = _stop_body_reason(body)
    if reason:
        return refusal(400, "invalid_request", reason, schema=SCHEMA)

    state = read_status(root, kin_selector=kin_selector).state
    if state is ObservedState.IDLE:
        return refusal(
            409,
            "session_not_running",
            "this Kin has no running session to stop",
            schema=SCHEMA,
        )

    report = stop_session(root, kin_selector=kin_selector)
    return 200, {"schemaVersion": SCHEMA, "state": state.value, "report": report.as_dict()}


def _stop_body_reason(body: Mapping[str, Any]) -> str:
    """Why a stop body is not a well-formed confirmation, or the empty string when it is.

    Stopping is the first control verb on this surface, so it requires an explicit `confirm`: a
    stray POST, or a panel that fires on a keystroke, should not end a session. The check is
    deliberately the same explicit-confirmation shape the rename uses, so "act" always means a
    deliberate request rather than a side effect of reading.
    """

    unknown = set(body) - {"confirm"}
    if unknown:
        return f"unexpected field(s): {', '.join(sorted(unknown))}"
    if body.get("confirm") is not True:
        return "stopping requires an explicit confirmation (confirm must be true)"
    return ""
