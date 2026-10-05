"""Persisted personality reaches the provider without granting additional actions.

The endpoint is a local test double: these prove transport and admission, not real
LLM behavioural distinctiveness or successful gameplay.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from minekin_core.adapters.filestore.persona_store import read_persona, write_persona
from minekin_core.adapters.model import OffModelProvider
from minekin_core.adapters.model.openai_compatible import OpenAICompatibleProvider
from minekin_core.application.player_mind import DecisionPolicy, mind_for
from minekin_core.cli.session import mind_for_run
from minekin_core.domain.errors import MinekinError
from minekin_core.domain.model_access import CostLedger, Decision, DecisionRequest, model_config
from minekin_core.domain.perception import InventoryValue, SelfStateValue, WorldObservationValue
from minekin_core.domain.persona import derive_persona


@pytest.fixture
def endpoint() -> Iterator[tuple[str, list[dict[str, Any]]]]:
    arrivals: list[dict[str, Any]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            offer = json.loads(body["messages"][1]["content"])
            arrivals.append(offer)
            response = json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "skill_id": "turn_to",
                                        "arguments": {"yaw_degrees": 90, "pitch_degrees": 0},
                                        "reason": "observe another direction",
                                        "intent_generation": offer["intent_generation"],
                                    }
                                )
                            }
                        }
                    ],
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1", arrivals
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)


def provider(url: str) -> OpenAICompatibleProvider:
    env = {
        "MINEKIN_MODEL_PROVIDER": "openai_compatible",
        "MINEKIN_MODEL_BASE_URL": url,
        "MINEKIN_MODEL": "local-test-double",
        "MINEKIN_MODEL_API_KEY": "fake-persona-test-key",
    }
    return OpenAICompatibleProvider(model_config(env), env)


def test_persisted_manifest_is_shown_without_seed_and_changes_the_offer(
    endpoint: tuple[str, list[dict[str, Any]]],
    tmp_path: Path,
) -> None:
    url, arrivals = endpoint
    original = derive_persona("kin-persona", "original-persisted-seed")
    write_persona(tmp_path, original)
    loaded = read_persona(tmp_path)
    model = provider(url)
    for persona in (loaded, derive_persona("kin-persona", "different-seed")):
        answer = model.decide(
            DecisionRequest(
                observation_ref="obs-1",
                feasible_skill_ids=("turn_to",),
                persona_seed="changed-environment-seed",
                persona=persona,
            )
        )
        assert isinstance(answer, Decision)
        assert answer.skill_id == "turn_to"
    assert arrivals[0]["persona"]["traits"] == dict(original.traits)
    assert arrivals[0]["persona"] == original.decision_context()
    assert arrivals[0]["persona"]["value_priority"] == list(original.value_priority)
    assert arrivals[0]["persona"] != arrivals[1]["persona"]
    assert all(offer["feasible_skill_ids"] == ["turn_to"] for offer in arrivals)
    assert all(offer["persona_seed"] == "" for offer in arrivals)
    assert "original-persisted-seed" not in json.dumps(arrivals)
    assert "changed-environment-seed" not in json.dumps(arrivals)
    assert read_persona(tmp_path) == original


def test_missing_manifest_is_unknown_not_redrawn(
    endpoint: tuple[str, list[dict[str, Any]]],
) -> None:
    url, arrivals = endpoint
    provider(url).decide(DecisionRequest(observation_ref="obs-1", feasible_skill_ids=("turn_to",)))
    assert arrivals[0]["persona"] is None


def test_historical_lifecycle_is_data_not_world_knowledge(
    endpoint: tuple[str, list[dict[str, Any]]],
) -> None:
    url, arrivals = endpoint
    history = {
        "status": "found",
        "freshness": "historical",
        "current_world_applicability": "unknown",
        "world_facts": "not_retrieved",
        "record": {"last_recorded_phase": "STOPPED", "input_release": "unknown"},
        "skill_experiences": {
            "status": "found",
            "current_world_applicability": "unknown",
            "records": [
                {
                    "event_id": "past-attempt",
                    "skill": "consume_item",
                    "result": "UNKNOWN",
                    "reason": "NO_CONFIRMING_OBSERVATION",
                    "decision_source": "model",
                }
            ],
        },
    }
    answer = provider(url).decide(
        DecisionRequest(
            observation_ref="new-observation",
            feasible_skill_ids=("turn_to",),
            session_history=history,
        )
    )
    assert isinstance(answer, Decision)
    assert arrivals[0]["session_history"] == history
    assert arrivals[0]["feasible_skill_ids"] == ["turn_to"]


def test_mind_passes_the_saved_manifest_to_its_real_provider(
    endpoint: tuple[str, list[dict[str, Any]]],
) -> None:
    url, arrivals = endpoint
    persona = derive_persona("kin-persona", "saved-seed")
    mind = mind_for(
        provider(url), CostLedger(run_cost_cap=500_000), kin_id="kin-persona", persona=persona
    )
    reading = WorldObservationValue(
        generation=1,
        game_tick=100,
        self_state=SelfStateValue(20, 20, 20, 5, True, yaw_degrees=0, pitch_degrees=0),
        aim=None,
        inventory=InventoryValue(1, ()),
        visible_entities=(),
        mining=None,
        gui=None,
    )
    intent = mind.next_intent(reading)
    assert arrivals[0]["persona"]["traits"] == dict(persona.traits)
    assert mind.persona == persona
    assert mind.as_document()["persona_context"] == persona.decision_context()
    assert (
        intent.as_document()["persona_context_ref"] == persona.decision_context()["manifest_sha256"]
    )


def test_local_reflection_does_not_claim_a_personality_influence() -> None:
    persona = derive_persona("kin-persona", "saved-seed")
    mind = mind_for(
        OffModelProvider(),
        CostLedger(run_cost_cap=500_000),
        kin_id="kin-persona",
        persona=persona,
        policy=DecisionPolicy.RULES,
    )
    reading = WorldObservationValue(
        generation=1,
        game_tick=100,
        self_state=SelfStateValue(20, 20, 20, 5, True, yaw_degrees=0, pitch_degrees=0),
        aim=None,
        inventory=InventoryValue(1, ()),
        visible_entities=(),
        mining=None,
        gui=None,
    )
    intent = mind.next_intent(reading)
    assert intent.source == "local_reflection"
    assert intent.as_document()["persona_context_ref"] is None
    assert mind.as_document()["persona_context"] == persona.decision_context()


def test_persona_from_another_kin_is_refused_before_any_call(
    endpoint: tuple[str, list[dict[str, Any]]],
) -> None:
    url, arrivals = endpoint
    with pytest.raises(ValueError, match="belong to this Kin"):
        mind_for(
            provider(url),
            CostLedger(run_cost_cap=500_000),
            kin_id="different-kin",
            persona=derive_persona("kin-persona", "saved-seed"),
        )
    assert arrivals == []


def test_runtime_reloads_saved_personality_not_the_environment_seed(tmp_path: Path) -> None:
    original = derive_persona("kin-persona", "original-seed")
    write_persona(tmp_path, original)
    first = mind_for_run("kin-persona", {"MINEKIN_PERSONA_SEED": "env-first"}, kin_dir=tmp_path)
    restarted = mind_for_run(
        "kin-persona", {"MINEKIN_PERSONA_SEED": "env-changed"}, kin_dir=tmp_path
    )
    assert first.persona == restarted.persona == original
    assert restarted.persona_seed == ""
    assert first.as_document()["persona_context"] == restarted.as_document()["persona_context"]
    assert read_persona(tmp_path) == original


def test_runtime_missing_persona_does_not_create_or_redraw(tmp_path: Path) -> None:
    missing = tmp_path / "legacy-kin"
    mind = mind_for_run("kin-persona", {"MINEKIN_PERSONA_SEED": "new-seed"}, kin_dir=missing)
    assert mind.persona is None
    assert mind.as_document()["persona_context"] is None
    assert mind.persona_seed == ""
    assert not missing.exists()


def test_runtime_refuses_corrupt_or_foreign_saved_persona(tmp_path: Path) -> None:
    original = derive_persona("other-kin", "seed")
    path = write_persona(tmp_path, original)
    with pytest.raises(ValueError, match="belong to this Kin"):
        mind_for_run("kin-persona", {}, kin_dir=tmp_path)
    path.write_text("{broken-json", encoding="utf-8")
    with pytest.raises(MinekinError, match="readable JSON"):
        mind_for_run("kin-persona", {}, kin_dir=tmp_path)
