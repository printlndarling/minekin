"""Loopback decision test double. Never use its answers as real-model evidence."""

from __future__ import annotations

import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


def fixture_server(token: str, *, port: int = 18991) -> ThreadingHTTPServer:
    calls: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            pass  # Request bodies, headers and model prose are never logged.

        def reply(self, status: int, value: dict[str, Any]) -> None:
            payload = json.dumps(value).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self) -> None:
            if self.path != "/health":
                self.reply(404, {})
                return
            self.reply(
                200,
                {"source": "control_path_test_double", "instanceId": token, "calls": list(calls)},
            )

        def do_POST(self) -> None:
            if self.path == f"/control/{token}/stop":
                self.reply(200, {"stopped": True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            if self.path != "/v1/chat/completions" or self.headers.get("Authorization"):
                self.reply(400, {"error": "fixture accepts no credentials"})
                return
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 65536:
                self.reply(400, {})
                return
            request = json.loads(self.rfile.read(length))
            offer = json.loads(request["messages"][-1]["content"])
            if "turn_to" not in offer["feasible_skill_ids"]:
                self.reply(400, {"error": "turn is not feasible"})
                return
            calls.append("turn_to")
            self.reply(
                200,
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "skill_id": "turn_to",
                                        "arguments": {"yaw_degrees": 45.0, "pitch_degrees": 0.0},
                                        "intent_generation": offer["intent_generation"],
                                        "reason": "Explicit local control-path test double",
                                    }
                                )
                            }
                        }
                    ],
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0},
                },
            )

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def serve(token: str) -> None:
    with fixture_server(token) as server:
        server.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control-token", required=True)
    serve(parser.parse_args().control_token)
