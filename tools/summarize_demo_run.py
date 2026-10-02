"""Summarize a completed local demo without echoing configuration or model prose."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, cast

PREFIX = "domain: the run document said "


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument(
        "--compact", action="store_true", help="show counts and only the last steps"
    )
    args = parser.parse_args()
    try:
        lines = args.log.read_text(encoding="utf-8").splitlines()
        document = next(line[len(PREFIX) :] for line in reversed(lines) if line.startswith(PREFIX))
        record = cast(dict[str, Any], json.loads(document))
        run = cast(dict[str, Any], record["run"])
        raw_autonomous: object = run["autonomous"]
        if not isinstance(raw_autonomous, dict):
            raise ValueError("not an autonomous run")
        autonomous = cast(dict[str, Any], raw_autonomous)
    except (OSError, StopIteration, ValueError, KeyError, TypeError):
        print("No completed autonomous run document was found.")
        return 2
    steps = cast(list[dict[str, Any]], autonomous.get("steps", []))
    mind = cast(dict[str, Any], autonomous.get("mind", {}))
    print(
        json.dumps(
            {
                "session_id": record.get("session_id"),
                "outcome": run.get("outcome"),
                "stop_reason": autonomous.get("stop_reason"),
                "goal_met": mind.get("goal_met"),
                "model_calls": mind.get("model_calls"),
                "confirmed": autonomous.get("confirmed"),
                "actions_applied": run.get("actions_applied"),
                "actions_refused": run.get("actions_refused"),
                "input_release_failed": run.get("input_release_failed"),
                "model_spent_micro": mind.get("model_spent_micro"),
                "sources": dict(Counter(step.get("intent", {}).get("source") for step in steps)),
                "observations": run.get("world_observations"),
                "steps": [
                    {
                        "step": i,
                        "skill": step.get("intent", {}).get("skill"),
                        "source": step.get("intent", {}).get("source"),
                        "result": step.get("result"),
                        "reason": step.get("reason"),
                        "details": step.get("details", {}),
                    }
                    for i, step in enumerate(steps, 1)
                    if not args.compact or i > len(steps) - 5
                ],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
