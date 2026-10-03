"""Allowlisted summaries of recorded mind inputs; never a personality efficacy verdict."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, cast

from minekin_core.domain.persona import PERSONA_ALGORITHM, TRAIT_NAMES, VALUE_NAMES
from minekin_core.domain.session_state import SessionState


def _record(value: object) -> dict[str, Any] | None:
    return cast("dict[str, Any]", value) if isinstance(value, dict) else None


def persona_summary(mind: Mapping[str, object]) -> str | None:
    raw = _record(mind.get("persona_context"))
    if raw is None:
        return None
    digest = raw.get("manifest_sha256")
    traits = _record(raw.get("traits"))
    priorities_raw = raw.get("value_priority")
    priorities = cast("list[Any]", priorities_raw) if isinstance(priorities_raw, list) else None
    if (
        not isinstance(digest, str)
        or not re.fullmatch(r"[0-9a-f]{64}", digest)
        or raw.get("algorithm") != PERSONA_ALGORITHM
        or type(raw.get("schema_version")) is not int
        or raw["schema_version"] != 1
        or traits is None
        or set(traits) != set(TRAIT_NAMES)
        or any(type(traits[name]) is not int or not 1 <= traits[name] <= 9 for name in TRAIT_NAMES)
        or priorities is None
        or len(priorities) != len(VALUE_NAMES)
        or any(not isinstance(name, str) for name in priorities)
        or set(priorities) != set(VALUE_NAMES)
    ):
        return None
    values = ", ".join(f"{name}={traits[name]}" for name in TRAIT_NAMES)
    return f"manifest_sha256={digest}; {values}; value_priority={' > '.join(priorities)}"


def history_summary(mind: Mapping[str, object]) -> str | None:
    raw = _record(mind.get("session_history"))
    if raw is None or raw.get("retriever_version") != "last-session-v1":
        return None
    if any(
        raw.get(key) != value
        for key, value in {
            "freshness": "historical",
            "current_world_applicability": "unknown",
            "world_facts": "not_retrieved",
        }.items()
    ):
        return None
    status = raw.get("status")
    if status in ("not_retrieved", "ledger_missing", "ledger_unavailable", "invalid_record"):
        return f"status={status}; historical; current_world_applicability=unknown"
    record = _record(raw.get("record"))
    if status != "found" or record is None:
        return None
    event = record.get("event_id")
    phase = record.get("last_recorded_phase")
    if (
        not isinstance(event, str)
        or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", event)
        or not isinstance(phase, str)
        or phase not in {state.value for state in SessionState}
        or record.get("source") != "CORE"
        or record.get("trust_class") != "CORE"
        or record.get("input_release") != "unknown"
    ):
        return None
    return (
        f"event_id={event}; last_recorded_phase={phase}; historical; "
        "input_release=unknown; current_world_applicability=unknown"
    )
