"""Allowlisted summaries of recorded mind inputs; never a personality efficacy verdict."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, cast

from minekin_core.domain.persona import PERSONA_ALGORITHM, TRAIT_NAMES, VALUE_NAMES
from minekin_core.domain.session_state import SessionState
from minekin_core.domain.world_actions import ActionResultClass, skill_capabilities


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
    experience = _experience_summary(raw.get("skill_experiences"))
    if status in ("not_retrieved", "ledger_missing", "ledger_unavailable", "invalid_record"):
        return f"status={status}; historical; current_world_applicability=unknown{experience}"
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
        f"input_release=unknown; current_world_applicability=unknown{experience}"
    )


def _experience_summary(value: object) -> str:
    """Recorded retrieval inputs, not a fresh ledger lookup or model efficacy verdict."""
    raw = _record(value)
    if raw is None or raw.get("retriever_version") != "skill-experiences-v2":
        return ""  # older documents never implied this retrieval capability
    invalid = "; 技能经历摘要不合法, 未展示"
    if any(
        raw.get(key) != expected
        for key, expected in {
            "freshness": "historical",
            "current_world_applicability": "unknown",
            "game_version_applicability": "unknown",
            "world_facts": "not_retrieved",
        }.items()
    ):
        return invalid
    status = raw.get("status")
    if status in ("not_retrieved", "ledger_missing", "ledger_unavailable", "invalid_record"):
        return f"; 技能经历检索={status}"
    scanned = raw.get("scanned_records")
    omitted = raw.get("records_omitted_within_scan")
    patterns_omitted = raw.get("patterns_omitted_within_scan")
    older = raw.get("older_records_not_scanned")
    patterns = raw.get("patterns")
    if (
        status != "found"
        or type(scanned) is not int
        or not 1 <= scanned <= 64
        or type(omitted) is not int
        or not 0 <= omitted <= scanned
        or type(patterns_omitted) is not int
        or not 0 <= patterns_omitted <= scanned
        or type(older) is not bool
        or (older and scanned != 64)
        or not isinstance(patterns, list)
        or len(cast("list[object]", patterns)) > 8
    ):
        return invalid
    segments: list[str] = []
    seen: set[str] = set()
    total = 0
    for value in cast("list[object]", patterns):
        pattern = _record(value)
        if pattern is None:
            return invalid
        skill = pattern.get("skill")
        counts = _record(pattern.get("result_counts"))
        refs = _record(pattern.get("latest_by_result"))
        if (
            not isinstance(skill, str)
            or skill_capabilities(skill) is None
            or skill in seen
            or counts is None
            or not counts
            or refs is None
            or set(refs) != set(counts)
            or any(
                pattern.get(key) != expected
                for key, expected in {
                    "source": "CORE",
                    "trust_class": "CORE",
                    "freshness": "historical",
                    "current_world_applicability": "unknown",
                }.items()
            )
            or any(
                result not in {member.value for member in ActionResultClass}
                or type(count) is not int
                or not 1 <= count <= scanned
                for result, count in counts.items()
            )
            or any(
                not isinstance(ref, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", ref)
                for ref in refs.values()
            )
        ):
            return invalid
        seen.add(skill)
        total += sum(counts.values())
        segments.append(
            f"{skill}: "
            + ", ".join(
                f"{result}={count} [event={refs[result]}]" for result, count in counts.items()
            )
        )
    if total > scanned:
        return invalid
    scope = "; 更老记录未扫描" if older else ""
    return (
        f"; 历史技能窗口 {scanned}/64 条{scope}; 省略明细 {omitted} 条、技能摘要 "
        f"{patterns_omitted} 项; 世界/版本适用性未知; " + "; ".join(segments)
    )
