"""Issue exactly ONE structured decision against the model this operator configured.

The shipped CLI has no standalone "ask the model" subcommand — a decision is only ever drawn from
inside a supervised 1.20.1 session (`cli/session.py:_mind_for_run` → `run_autonomous_loop`). That
is the right shape for a real run, but it means the question *"does a real, non-scripted answerer
actually return a skill this build can honour, chosen from an offer it was handed and not from a
hardcoded list?"* has no cheap, bounded probe. This script is that probe. It builds one reading, one
mind over the configured provider, and calls `next_intent` once, so it sends at most one request:
finite by construction, and it cannot loop-burn a spend cap.

It is deliberately a *projection*, not a player: it runs no keystrokes and touches no game. What it
proves is the boundary Core cares about — that a reply arriving over a socket from a remote answerer
survives `compose_decision` (in-bounds skill, matching generation, arguments this side can resolve)
and comes back as a `MindIntent` whose `source` is `model`. `tests/unit` cover the same path against
a scripted provider and the fake loopback endpoint; those say the code is correct — this says the
wiring reaches a *live* endpoint and reads an answer nobody wrote here.

Nothing secret is printed. Only the safe half of the configuration is echoed (provider name, model,
endpoint host, timeout, cap) plus a boolean for whether the key's variable resolves — never the key
and never the config field that names it as a value. The decision projection is the mind's own
`as_document()`, whose `reason` is already bounded and redacted against whatever went on the wire.

A no-credential machine is a supported outcome, not an error: with `MINEKIN_MODEL_PROVIDER` unset or
`off`, `model_config()` returns the `off` shape, this script says so by name and exits 2 having sent
nothing. To reach a real endpoint the operator opts in for this one process (export the provider
variable, or point `MINEKIN_MODEL_*` at an endpoint) without editing the run's default.

Usage:

    uv run python tools/probe_real_model_decision.py
    MINEKIN_MODEL_PROVIDER=openai_compatible uv run python tools/probe_real_model_decision.py
    ... --product minecraft:crafting_table --quantity 1 --planks 8 --no-aim-log
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
from typing import Final, cast

from minekin_core import config
from minekin_core.adapters.model import model_provider_for
from minekin_core.application.player_mind import (
    DECISION_FROM_MODEL,
    MindIntent,
    mind_for,
)
from minekin_core.domain.goal_spec import Milestone
from minekin_core.domain.model_access import (
    ModelConfig,
    cost_ledger_for,
    key_for,
    model_config,
)
from minekin_core.domain.perception import (
    AimFace,
    AimKind,
    AimTargetValue,
    BlockTargetValue,
    InventoryStackValue,
    InventoryValue,
    SelfStateValue,
    WorldObservationValue,
)

LOG: Final = "minecraft:oak_log"
PLANKS: Final = "minecraft:oak_planks"


def _state() -> SelfStateValue:
    return SelfStateValue(
        health=20.0,
        max_health=20.0,
        food=20,
        saturation=5.0,
        alive=True,
        x=0.0,
        y=64.0,
        z=0.0,
        yaw_degrees=0.0,
        pitch_degrees=0.0,
        selected_slot=None,
    )


def _aimed_log() -> AimTargetValue:
    return AimTargetValue(
        game_tick=100,
        kind=AimKind.BLOCK,
        block=BlockTargetValue(x=4, y=-2, z=9, face=AimFace.UP),
        targeted_block_id=LOG,
        distance=2.0,
    )


def _reading(*, planks: int, aim_log: bool) -> WorldObservationValue:
    """The one scene the mind is asked about: a trunk in view and a hand full of planks.

    Both a break and a craft are live offers on this reading, so a chosen `skill_id` is a real
    pick between them rather than the only answer available — which is what makes `source: model`
    mean something. The inventory count is a knob because it decides whether a craft toward the
    asked-for product is even affordable, and an unaffordable ask would be refused locally before
    the endpoint ever mattered.
    """

    items: list[tuple[int, str, int]] = []
    if planks > 0:
        items.append((0, PLANKS, planks))
    return WorldObservationValue(
        generation=1,
        game_tick=100,
        self_state=_state(),
        aim=_aimed_log() if aim_log else None,
        inventory=InventoryValue(
            revision=7,
            stacks=tuple(
                InventoryStackValue(slot=slot, item_id=item_id, count=count)
                for slot, item_id, count in items
            ),
        ),
        visible_entities=(),
        mining=None,
        gui=None,
    )


def _safe_config_lines(cfg: ModelConfig) -> list[str]:
    """The half of the configuration that is safe to echo: names, a host, and numbers.

    `api_key_env` is shown as the variable name it is (that is the whole design — the field holds a
    name, never a key), and the key's *presence* is reduced to a boolean by `key_for`. The base URL
    is reduced to its host so a path or any accidental userinfo never reaches a terminal.
    """

    host = urllib.parse.urlsplit(cfg.base_url).hostname or "(no host)"
    resolved = key_for(cfg) is not None if cfg.enabled else False
    return [
        f"provider={cfg.provider}",
        f"model={cfg.model or '(unset)'}",
        f"endpoint_host={host}",
        f"key_var={cfg.api_key_env or '(unset)'}",
        f"key_resolved={resolved}",
        f"timeout_ms={cfg.timeout_ms}",
        f"run_cost_cap={cfg.run_cost_cap}",
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Draw one structured decision from the configured model; print it, run nothing."
    )
    parser.add_argument(
        "--product",
        default="",
        help="an optional standing milestone product id; empty means no goal is held",
    )
    parser.add_argument(
        "--quantity", type=int, default=1, help="how many of the milestone product to ask for"
    )
    parser.add_argument(
        "--planks", type=int, default=5, help="planks staged in the bag (a craft affordance knob)"
    )
    parser.add_argument(
        "--no-aim-log",
        dest="aim_log",
        action="store_false",
        help="hide the aimed log so a break is not offered",
    )
    arguments = parser.parse_args(argv)
    product = cast("str", arguments.product)
    quantity = cast("int", arguments.quantity)
    planks = cast("int", arguments.planks)
    aim_log = cast("bool", arguments.aim_log)

    config.load_local_environment()
    try:
        cfg = model_config()
    except Exception as error:  # a half-entered configuration is a refusal, not a stack trace
        print(f"probe-model: refused to read configuration: {error}", file=sys.stderr, flush=True)
        return 2

    print("probe-model: " + " ".join(_safe_config_lines(cfg)), flush=True)

    if not cfg.enabled:
        print(
            "probe-model: provider is off — nothing was sent. To reach a live endpoint export "
            "MINEKIN_MODEL_PROVIDER=openai_compatible (and the MINEKIN_MODEL_* variables) for "
            "this process.",
            file=sys.stderr,
            flush=True,
        )
        return 2

    ledger = cost_ledger_for(cfg)
    provider = model_provider_for(cfg, ledger=ledger)
    goal = (
        Milestone(
            product_id=product,
            source_item_id=PLANKS,
            quantity=quantity,
            direction=f"hold {quantity} {product}",
        )
        if product
        else None
    )
    mind = mind_for(
        provider,
        ledger,
        kin_id="probe",
        persona_seed="probe",
        goal=goal,
        model_enabled=True,
    )

    intent: MindIntent = mind.next_intent(_reading(planks=planks, aim_log=aim_log))
    projection = intent.as_document()
    projection["ledger"] = dict(ledger.as_document())
    projection["env_was_set_provider"] = "MINEKIN_MODEL_PROVIDER" in os.environ

    print(json.dumps(projection, indent=2, ensure_ascii=False), flush=True)

    if intent.source == DECISION_FROM_MODEL:
        print("probe-model: source=model — a live answerer chose an honourable skill.", flush=True)
        return 0
    print(
        f"probe-model: source={intent.source or 'unknown'} — fell back locally "
        f"(refusal={intent.model_refusal or 'none'}); the endpoint did not yield a usable answer.",
        file=sys.stderr,
        flush=True,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
