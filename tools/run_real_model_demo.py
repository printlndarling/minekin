"""Run one bounded local model demo using literal configuration assignments."""

from __future__ import annotations

import argparse
import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path

from minekin_core.domain.skill_parameters import MAX_QUANTITY, is_item_id

ROOT = Path(__file__).resolve().parents[1]
NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def model_environment(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:]
        words = shlex.split(line, comments=True)
        if len(words) != 1 or "=" not in words[0]:
            raise ValueError("model configuration must contain literal assignments")
        name, value = words[0].split("=", 1)
        if NAME.fullmatch(name) is None:
            raise ValueError("invalid configuration variable name")
        values[name] = value
    selected = {
        name: value
        for name, value in values.items()
        if name == "MINEKIN_MODEL" or name.startswith("MINEKIN_MODEL_")
    }
    key_name = selected.get("MINEKIN_MODEL_API_KEY_ENV", "")
    if key_name:
        if NAME.fullmatch(key_name) is None or key_name in {
            "PATH",
            "PYTHONPATH",
            "HOME",
            "CODEX_HOME",
        }:
            raise ValueError("invalid model credential variable")
        if key_name in values:
            selected[key_name] = values[key_name]
    return selected


def goal_environment(product: str, quantity: int, source_item: str) -> dict[str, str]:
    """Pass a typed goal to the existing parameterized demo, without adding an action chain."""
    if not is_item_id(product) or not is_item_id(source_item):
        raise ValueError("goal and source must be namespaced item identifiers")
    if isinstance(quantity, bool) or not 1 <= quantity <= MAX_QUANTITY:
        raise ValueError(f"goal quantity must be 1..{MAX_QUANTITY}")
    return {
        "MINEKIN_DEMO_GOAL_PRODUCT": product,
        "MINEKIN_DEMO_GOAL_QUANTITY": str(quantity),
        "MINEKIN_DEMO_GOAL_SOURCE_ITEM": source_item,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-env", type=Path, default=ROOT / ".env")
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--volume", default="minekin-local-demo2")
    parser.add_argument("--kin", default="kin-3x3-fresh-20261002")
    parser.add_argument("--steps", type=int, default=48)
    parser.add_argument("--wait-seconds", type=int, default=420)
    parser.add_argument("--cost-cap-micro", type=int, default=10_000)
    parser.add_argument("--provider", choices=("openai_compatible",), default="openai_compatible")
    parser.add_argument(
        "--difficulty", choices=("peaceful", "easy", "normal", "hard"), default="normal"
    )
    parser.add_argument("--goal-product", default="minecraft:wooden_pickaxe")
    parser.add_argument("--goal-quantity", type=int, default=1)
    parser.add_argument("--goal-source", default="minecraft:oak_log")
    parser.add_argument(
        "--bundle-profile",
        default="",
        help="explicit candidate override; default uses the reviewed automatic registry",
    )
    parser.add_argument("--bash", type=Path)
    args = parser.parse_args()
    if not 1 <= args.steps <= 64 or not 1 <= args.wait_seconds <= 900:
        parser.error("steps must be 1..64 and wait-seconds 1..900")
    if not 1 <= args.cost_cap_micro <= 1_000_000:
        parser.error("cost-cap-micro must be 1..1000000 ledger units")
    try:
        goal_values = goal_environment(args.goal_product, args.goal_quantity, args.goal_source)
    except ValueError as error:
        parser.error(str(error))
    try:
        configured = model_environment(args.model_env)
    except (OSError, ValueError):
        parser.error("cannot read literal model configuration; no values were printed")
    configured["MINEKIN_MODEL_PROVIDER"] = args.provider
    bash = args.bash
    if bash is None:
        git = shutil.which("git")
        git_bash = None if git is None else Path(git).parent / "bash.exe"
        if git is not None and git_bash is not None and not git_bash.exists():
            git_bash = Path(git).parent.parent / "bin" / "bash.exe"
        bash = git_bash if git_bash is not None and git_bash.exists() else shutil.which("bash")
    if bash is None:
        parser.error("bash was not found")
    environment = dict(os.environ)
    configured["MINEKIN_MODEL_RUN_COST_CAP"] = str(args.cost_cap_micro)
    environment.update(configured)
    environment.update(goal_values)
    environment.update(
        {
            "MINEKIN_RUNNER_FORWARD_ENV": ",".join(configured),
            "MINEKIN_SERVER_JAR": ".tmp/mc-1.20.1-server.jar",
            "MINEKIN_DOMAIN_DIFFICULTY": args.difficulty,
            "MINEKIN_DEMO_VOLUME": args.volume,
            "MINEKIN_DEMO_KIN": args.kin,
            "MINEKIN_DEMO_BUNDLE_PROFILE": args.bundle_profile,
            "MINEKIN_DEMO_AUTONOMOUS_STEPS": str(args.steps),
            "MINEKIN_DEMO_AUTONOMOUS_WAIT_SECONDS": str(args.wait_seconds),
            "MINEKIN_MODEL_RUN_COST_CAP": str(args.cost_cap_micro),
        }
    )
    args.log.parent.mkdir(parents=True, exist_ok=True)
    print("Starting one local model demo; output is saved to the requested log.", flush=True)
    with args.log.open("w", encoding="utf-8") as output:
        return subprocess.run(
            [str(bash), "test-orchestrator/runner/demo.sh", "--autonomous"],
            cwd=ROOT,
            env=environment,
            stdout=output,
            stderr=subprocess.STDOUT,
            check=False,
        ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
