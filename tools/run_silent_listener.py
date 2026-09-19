"""A target that accepts a connection and then says nothing.

It exists so one thing can be measured: what Core does when a world it asked for
never answers. A vanilla server cannot produce that — it answers — and nothing
listening produces a *refusal*, which is a different path through the client and
ends in a different classification. So this accepts the TCP connection, holds it,
and never writes a byte: the client waits for a login response that is not coming,
and the only clock still running is the one Core put on its own attempt.

The address comes from the same reviewed Server Profile the session is given, so
there is one source for "which target" rather than two that could disagree.

It runs until it is signalled, and it says what it accepted, so a run's log says
whether anything ever connected at all — a black hole that nobody dialled proves
nothing about a client giving up.

Exit codes: 0 when it stopped on a signal, 2 when it could not start.
"""

from __future__ import annotations

import argparse
import json
import signal
import socket
import sys
from collections.abc import Sequence
from pathlib import Path

from minekin_core.adapters.launcher.server_profile import load_server_profile

EXIT_STOPPED = 0
EXIT_UNUSABLE = 2

#: How many connections are held at once. One is what the scenario produces; the
#: rest is room for a retry without the listener having to be restarted.
BACKLOG = 4


def _say(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def listen(host: str, port: int) -> socket.socket:
    """Bind and listen, refusing anything the profile could not have named."""

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        listener.bind((host, port))
        listener.listen(BACKLOG)
    except OSError as error:
        # Said out loud and with the documented code: a listener that could not
        # take the address must not look like one that did.
        listener.close()
        _say(f"could not listen on {host}:{port}: {error.strerror or error}")
        raise SystemExit(EXIT_UNUSABLE) from error
    return listener


def run_until_stopped(listener: socket.socket, *, stop: list[bool]) -> None:
    """Accept and hold connections until the flag is set by a signal."""

    held: list[socket.socket] = []
    listener.settimeout(0.2)
    while not stop[0]:
        try:
            connection, address = listener.accept()
        except TimeoutError:
            continue
        except OSError:
            # The listener was closed under us; that is a stop.
            break
        # Nothing is ever sent on this socket, and nothing is read either: a
        # client sends one handshake packet and then waits, which fits in the
        # kernel's buffer. The whole behaviour is silence that stays silence.
        connection.settimeout(0.2)
        held.append(connection)
        _say(json.dumps({"accepted": f"{address[0]}:{address[1]}", "held": len(held)}))
    for connection in held:
        connection.close()
    listener.close()
    _say(json.dumps({"stopped": True, "connections": len(held)}))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Listen on a Server Profile's address and never answer."
    )
    parser.add_argument("--server-profile", type=Path, required=True)
    args = parser.parse_args(argv)

    profile = load_server_profile(args.server_profile)
    listener = listen(profile.host, profile.port)
    _say(json.dumps({"listening": profile.endpoint(), "profile": profile.profile_id}))

    stop = [False]

    def on_signal(_signum: int, _frame: object) -> None:
        stop[0] = True

    for name in ("SIGTERM", "SIGINT"):
        # A background job of a non-interactive shell inherits SIGINT ignored, so
        # both are handled rather than only the polite one.
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), on_signal)

    run_until_stopped(listener, stop=stop)
    return EXIT_STOPPED


if __name__ == "__main__":
    raise SystemExit(main())
