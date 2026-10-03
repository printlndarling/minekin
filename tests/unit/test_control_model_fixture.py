"""The control double cannot turn arbitrary model input into privileged test actions."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request

import pytest
from tools.control_model_fixture import fixture_server


def test_control_double_uses_the_feasible_offer_and_refuses_credentials() -> None:
    with fixture_server("owned-control-test", port=0) as server:
        worker = threading.Thread(target=server.serve_forever)
        worker.start()
        base = f"http://127.0.0.1:{server.server_port}"
        http = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            payload = json.dumps(
                {
                    "messages": [
                        {
                            "content": json.dumps(
                                {
                                    "feasible_skill_ids": ["turn_to"],
                                    "intent_generation": 7,
                                }
                            )
                        }
                    ]
                }
            ).encode()
            request = urllib.request.Request(base + "/v1/chat/completions", data=payload)
            with http.open(request, timeout=3) as response:
                result = json.loads(response.read())
            choice = json.loads(result["choices"][0]["message"]["content"])
            assert choice["skill_id"] == "turn_to" and choice["intent_generation"] == 7
            assert result["usage"] == {"prompt_tokens": 0, "completion_tokens": 0}
            request.add_header("Authorization", "Bearer deliberately-fake-test-credential")
            with pytest.raises(urllib.error.HTTPError) as refused:
                http.open(request, timeout=3)
            assert refused.value.code == 400
            missing_offer = json.dumps(
                {
                    "messages": [
                        {
                            "content": json.dumps(
                                {
                                    "feasible_skill_ids": [],
                                    "intent_generation": 7,
                                }
                            )
                        }
                    ]
                }
            ).encode()
            with pytest.raises(urllib.error.HTTPError) as refused:
                http.open(
                    urllib.request.Request(base + "/v1/chat/completions", data=missing_offer),
                    timeout=3,
                )
            assert refused.value.code == 400
            with http.open(base + "/health", timeout=3) as response:
                health = json.loads(response.read())
            assert health["source"] == "control_path_test_double" and health["calls"] == ["turn_to"]
            with pytest.raises(urllib.error.HTTPError) as refused:
                http.open(
                    urllib.request.Request(base + "/control/not-owned/stop", method="POST"),
                    timeout=3,
                )
            assert refused.value.code == 400
        finally:
            server.shutdown()
            worker.join(timeout=3)
            assert not worker.is_alive()
