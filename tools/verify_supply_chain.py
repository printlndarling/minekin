"""Re-verify that the pinned URLs still serve the pinned bytes.

The launch plan and the bundle recipe assert what a bundle is made of by pinning
digests. Nothing in the ordinary test suite can check that the upstreams still
serve those bytes, because that requires the network and the network is not
something CI should depend on. So this is a tool rather than a test: run it when
you want the claim re-checked — after a dependency bump, or before cutting a
bundle.

It spends a bounded number of bytes on purpose. Fetching the whole bundle is a
gigabyte, which is not something to do by accident, so the budget is explicit,
printed, and refuses rather than truncating silently. The artifacts it does fetch
are chosen for coverage: the smallest from every host the plan uses, plus the
recipe's one mod, which is the pin the whole recipe rests on.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE = (
    REPOSITORY_ROOT / "tests" / "fixtures" / "runtime-input" / ("bundle-p0-core-1.21.4.json")
)
DEFAULT_MAX_BYTES = 8 * 1024 * 1024
VERSION_METADATA = REPOSITORY_ROOT / "tests" / "fixtures" / "launcher" / "1.21.4.json"
FETCH_TIMEOUT_S = 60.0


@dataclass(frozen=True, slots=True)
class Verified:
    name: str
    size: int
    sha1: str | None
    sha256: str | None


def _read(url: str) -> bytes:
    from minekin_core.adapters.launcher.fetch import open_https

    with open_https(url, FETCH_TIMEOUT_S) as stream:
        return stream.read()


def _smallest_per_host(artifacts: list[dict[str, object]]) -> list[dict[str, object]]:
    """One artifact per host, the smallest on each, so every upstream is exercised."""

    chosen: dict[str, dict[str, object]] = {}
    for artifact in sorted(artifacts, key=lambda item: int(str(item["size"]))):
        host = str(artifact["url"]).split("/")[2]
        chosen.setdefault(host, artifact)
    return list(chosen.values())


def server_artifact() -> dict[str, object]:
    """The pinned vanilla server the test domain runs, from the frozen metadata.

    It is not part of the client bundle, which is why it is opt-in: it is fifty
    times the size of everything else this tool fetches put together.
    """

    import json

    downloads = json.loads(VERSION_METADATA.read_bytes())["downloads"]
    return dict(downloads["server"])


def plan() -> list[dict[str, object]]:
    from minekin_core.adapters.launcher.launch_plan import build_launch_plan

    return list(build_launch_plan(DEFAULT_PROFILE)["artifacts"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    parser.add_argument(
        "--include-server",
        action="store_true",
        help="also verify the pinned vanilla server jar (~54 MB, not part of the bundle)",
    )
    args = parser.parse_args()

    from minekin_core.adapters.launcher.recipe import (
        FABRIC_API_SHA256,
        FABRIC_API_SIZE,
        FABRIC_API_URL,
    )

    selected = _smallest_per_host(plan())
    server = server_artifact() if args.include_server else None
    planned_bytes = sum(int(str(item["size"])) for item in selected) + FABRIC_API_SIZE
    if server is not None:
        planned_bytes += int(str(server["size"]))
    print(f"budget {args.max_bytes} bytes; this run would fetch {planned_bytes} bytes")
    if planned_bytes > args.max_bytes:
        print(
            f"refused: fetch would exceed the budget by {planned_bytes - args.max_bytes} bytes",
            file=sys.stderr,
        )
        return 1

    verified: list[Verified] = []
    errors: list[str] = []

    for artifact in selected:
        name = str(artifact["coordinate"])
        payload = _read(str(artifact["url"]))
        digest = hashlib.sha1(payload).hexdigest()
        if digest != artifact["sha1"] or len(payload) != artifact["size"]:
            errors.append(f"{name}: pinned SHA-1 or size does not match what the URL served")
            continue
        verified.append(Verified(name, len(payload), digest, None))

    payload = _read(FABRIC_API_URL)
    digest = hashlib.sha256(payload).hexdigest()
    if digest != FABRIC_API_SHA256 or len(payload) != FABRIC_API_SIZE:
        errors.append("fabric-api: the recipe's SHA-256 or size does not match the served jar")
    else:
        verified.append(
            Verified(
                "net.fabricmc.fabric-api", len(payload), hashlib.sha1(payload).hexdigest(), digest
            )
        )

    if server is not None:
        payload = _read(str(server["url"]))
        digest = hashlib.sha1(payload).hexdigest()
        if digest != server["sha1"] or len(payload) != server["size"]:
            errors.append("vanilla server: pinned SHA-1 or size does not match the served jar")
        else:
            verified.append(Verified("com.mojang:server:1.21.4", len(payload), digest, None))

    for item in verified:
        print(f"ok  {item.name}  {item.size} bytes")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"Supply chain: OK ({len(verified)} pinned artifacts still match)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
