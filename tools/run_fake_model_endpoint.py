"""A local fake OpenAI-compatible endpoint, for proving the model wiring on a live run.

The PlayerMind's provider contract is already covered in-process by
`tests/unit/test_model_provider_fake_endpoint.py`; what that cannot show is the shape a run
carries when a decision really came back over a socket: `decision_source: model` in the run
document and on the panel, with `model_calls` counted and a cost priced from reported usage.
This script is the endpoint half of that measurement. It is started inside the session's own
container, on that container's loopback, which is the only address the provider's base-URL rule
accepts for plain http (`domain/model_access.py` refuses a non-loopback http hop because the
key would cross it in the clear). Nothing here is published on a port, nothing listens on an
interface but `127.0.0.1`, and no real provider is contacted.

It answers one way and one way only: the first skill id the request offered, with the
generation the request carried echoed back. That is deliberately not a good player — it is a
known answer, so a run document that says the model chose can be checked against a choice
nobody could have produced by `local_reflection`.

Nothing it receives is written out. The request's `Authorization` header is never read, and the
prompt text is never logged: an operator pointing a real key at this would still find neither
the key nor the world's description in a log line.
"""

from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import cast

COMPLETIONS_PATH = "/chat/completions"
MAX_REQUEST_BYTES = 1_048_576

counts = {"calls": 0, "refusals": 0}


class FakeCompletionsHandler(BaseHTTPRequestHandler):
    """Serve one completion shape, and answer 404 for everything else."""

    server_version = "MinekinFakeModel/1"
    protocol_version = "HTTP/1.1"

    def do_POST(self) -> None:
        if self.path != COMPLETIONS_PATH:
            self._reply(404, {"error": {"message": "no such path"}})
            return
        body = self._read_body()
        if body is None:
            counts["refusals"] += 1
            self._reply(413, {"error": {"message": "body too large"}})
            return
        offer = _offer_of(body)
        if offer is None:
            counts["refusals"] += 1
            self._reply(400, {"error": {"message": "no offer in the request"}})
            return
        skill_ids = offer.get("feasible_skill_ids")
        if not isinstance(skill_ids, list):
            counts["refusals"] += 1
            self._reply(422, {"error": {"message": "the request offered no skill"}})
            return
        offered = cast("list[object]", skill_ids)
        if not offered or not isinstance(offered[0], str):
            counts["refusals"] += 1
            self._reply(422, {"error": {"message": "the request offered no skill"}})
            return
        chosen = offered[0]
        generation = offer.get("intent_generation")
        prompt_tokens = max(1, len(body) // 4)
        completion_tokens = max(1, len(chosen) // 4)
        content = json.dumps(
            {
                "skill_id": chosen,
                "reason": "the fake endpoint names the first offer",
                "intent_generation": generation if isinstance(generation, int) else 0,
            }
        )
        counts["calls"] += 1
        # Only counts and the chosen id: no header, no prompt, no observation text.
        print(
            f"fake-model: call {counts['calls']} chose {chosen} "
            f"from {len(offered)} offered (generation={generation})",
            flush=True,
        )
        self._reply(
            200,
            {
                "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens,
                },
            },
        )

    def do_GET(self) -> None:
        self._reply(405, {"error": {"message": "this endpoint serves completions by POST"}})

    def log_message(self, format: str, *args: object) -> None:
        """Quiet the access log: it would carry the request line and the client identity."""

    def _read_body(self) -> bytes | None:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return None
        if length > MAX_REQUEST_BYTES:
            return None
        return self.rfile.read(length)

    def _reply(self, status: int, payload: dict[str, object]) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def _offer_of(body: bytes) -> dict[str, object] | None:
    """The user message restated as data, or None when the request is not that shape.

    The provider sends one system prompt and one user message holding the offer; a request
    that does not look like that is not a decision being asked for, and inventing an answer
    would make the run document say the model chose something nobody offered.
    """

    try:
        document: object = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(document, dict):
        return None
    fields = cast("dict[str, object]", document)
    message_value = fields.get("messages")
    if not isinstance(message_value, list):
        return None
    messages = cast("list[object]", message_value)
    if len(messages) < 2:
        return None
    last = messages[-1]
    if not isinstance(last, dict):
        return None
    content = cast("dict[str, object]", last).get("content")
    if not isinstance(content, str):
        return None
    try:
        offer: object = json.loads(content)
    except json.JSONDecodeError:
        return None
    return cast("dict[str, object]", offer) if isinstance(offer, dict) else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Serve a loopback-only fake OpenAI-compatible completions endpoint."
    )
    parser.add_argument("port", type=int, help="the loopback port to bind")
    arguments = parser.parse_args(argv)
    port = cast("int", arguments.port)
    if not 1 <= port <= 65_535:
        print(f"fake-model: refused port {port}", file=sys.stderr, flush=True)
        return 2
    server = ThreadingHTTPServer(("127.0.0.1", port), FakeCompletionsHandler)
    print(f"fake-model: serving {COMPLETIONS_PATH} on 127.0.0.1:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    print(f"fake-model: {counts['calls']} answered, {counts['refusals']} refused", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
