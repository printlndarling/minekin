"""A local fake OpenAI-compatible endpoint, for proving the model wiring on a live run.

The PlayerMind's provider contract is already covered in-process by
`tests/unit/test_model_provider_fake_endpoint.py`; what that cannot show is the shape a run
carries when a decision really came back over a socket: `decision_source: model` in the run
document and on the panel, with `model_calls` counted and a cost priced from reported usage.
This script is the endpoint half of that measurement. It is started inside the session's own
container, on that container's loopback, which is the only address the provider's base-URL rule
accepts for plain http (`domain/model_access.py` refuses a non-loopback http hop because the key
would cross it in the clear). Nothing here is published beyond that loopback, and no real provider
is contacted.

The base URL that reaches it is the bare address — `http://127.0.0.1:<port>`, no `/v1` on it —
because `OpenAICompatibleProvider` appends `/chat/completions` itself and this handler answers 404
for every other path. A run that points at `/v1` gets `model_refusal: PROVIDER_STATUS` on every
ask, which is the honest filing but shows nothing.

It answers one way and one way only: the first skill the request offered whose required arguments
this script can state from the request's own observation summary — a craft it can name a
`target_item` for, from the `craft_options` the summary lists, with a `quantity` of one — and
otherwise the first offer it can run without arguments. The generation the request carried is
echoed back. That is deliberately not a good player — it is a known answer, so a run document that
says the model chose can be checked against a choice nobody could have produced by
`local_reflection`, and against a product nobody in Core named.

Nothing it receives is written out. The request's `Authorization` header is never read, and the
prompt text is never logged: an operator pointing a real key at this would still find neither
the key nor the world's description in a log line. The only thing echoed is the parameter this
script chose, which is a game item id read back out of the offer it was handed.
"""

from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import cast

COMPLETIONS_PATH = "/chat/completions"
MAX_REQUEST_BYTES = 1_048_576

#: The one quantity this script ever asks for. A batch is the smallest complete statement of a
#: craft, and a number invented here would be indistinguishable from one the summary supported.
FAKE_QUANTITY = 1

counts = {"calls": 0, "refusals": 0}


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in cast("list[object]", value) if isinstance(item, str)]


def _as_dict(value: object) -> dict[str, object]:
    return cast("dict[str, object]", value) if isinstance(value, dict) else {}


def _first_key(value: object) -> str:
    for key in _as_dict(value):
        if key:
            return key
    return ""


def _arguments_for(parameters: list[object], observation: dict[str, object]) -> dict[str, object]:
    """Fill this skill's declared parameters from the summary the request carried.

    Nothing here looks anything up in the recipe table or the reading: the request already holds
    the list the local layer computed, and this script chooses from it the way the ask vocabulary
    intends — which is the point of running it against a live session.
    """

    craft_options = _string_list(observation.get("craft_options"))
    drop = _first_key(observation.get("dropped_items"))
    arguments: dict[str, object] = {}
    for entry in parameters:
        if not isinstance(entry, dict):
            continue
        field = cast("dict[str, object]", entry)
        name = field.get("name")
        kind = field.get("kind")
        if not isinstance(name, str) or not isinstance(kind, str):
            continue
        if kind == "item_id":
            value = craft_options[0] if name == "target_item" and craft_options else drop
            if value:
                arguments[name] = value
        elif kind == "quantity":
            arguments[name] = FAKE_QUANTITY
    return arguments


def _required_names(parameters: list[object]) -> list[str]:
    """Which of this skill's declared arguments it cannot run without."""

    names: list[str] = []
    for entry in parameters:
        if not isinstance(entry, dict):
            continue
        field = cast("dict[str, object]", entry)
        name = field.get("name")
        if field.get("required") is True and isinstance(name, str):
            names.append(name)
    return names


def _parameters_of(skill_parameters: dict[str, object], candidate: str) -> list[object]:
    declared = skill_parameters.get(candidate)
    return cast("list[object]", declared) if isinstance(declared, list) else []


def _choice_of(
    skill_ids: list[object], skill_parameters: dict[str, object], observation: dict[str, object]
) -> tuple[str, dict[str, object]]:
    """The skill this script answers, and the arguments it can state for it.

    Preference goes to the first offer with a required argument whose value the summary really
    supplied — a craft it can name a product for. That is not a guess at good play: an offer where
    a required argument is fillable is the offer where the ask vocabulary has something to say, and
    the run is being measured on whether a product named over the socket is what the world did. An
    argument-free skill is the fallback, and the first offer with an empty ask last, which is the
    honest shape: the refusal the gate then returns is what the run document reports, rather than
    this script inventing a product the summary never showed.
    """

    fallback = ""
    plain: tuple[str, dict[str, object]] | None = None
    for candidate in skill_ids:
        if not isinstance(candidate, str):
            continue
        if fallback == "":
            fallback = candidate
        parameters = _parameters_of(skill_parameters, candidate)
        required = _required_names(parameters)
        arguments = _arguments_for(parameters, observation)
        if any(name not in arguments for name in required):
            continue
        if required:
            return candidate, arguments
        if plain is None:
            plain = (candidate, arguments)
    if plain is not None:
        return plain
    return fallback, {}


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
        if not offered:
            counts["refusals"] += 1
            self._reply(422, {"error": {"message": "the request offered no skill"}})
            return
        chosen, arguments = _choice_of(
            offered, _as_dict(offer.get("skill_parameters")), _as_dict(offer.get("observation"))
        )
        if not chosen:
            counts["refusals"] += 1
            self._reply(422, {"error": {"message": "the request offered no skill"}})
            return
        generation = offer.get("intent_generation")
        prompt_tokens = max(1, len(body) // 4)
        completion_tokens = max(1, len(chosen) // 4)
        content = json.dumps(
            {
                "skill_id": chosen,
                "arguments": arguments,
                "reason": "the fake endpoint names the first offer it can fill in",
                "intent_generation": generation if isinstance(generation, int) else 0,
            }
        )
        counts["calls"] += 1
        # Only counts, the chosen id and the parameter it named: no header, no prompt, no
        # observation text.
        print(
            f"fake-model: call {counts['calls']} chose {chosen} {json.dumps(arguments)} "
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
