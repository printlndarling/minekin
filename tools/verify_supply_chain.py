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

`--save-server` keeps the server jar this run already verified. The server is not
part of the client bundle, so no other tool holds those bytes: the runner that
starts the server says "download the pinned server jar first" and nothing was
that step. Saving the payload this tool has just checked against the pin is the
one place the two cannot disagree, and it stays opt-in for the same reason
`--include-server` is.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VERSION = "1.21.4"
DEFAULT_MAX_BYTES = 8 * 1024 * 1024
FETCH_TIMEOUT_S = 60.0


@dataclass(frozen=True, slots=True)
class ReviewedStack:
    """Where one reviewed Minecraft version's pinned bytes live and what they are.

    The recipe holds the digests, so this names the documents that carry them
    rather than copying the digests a second time: a second copy is a claim that
    can disagree with the one the product enforces.
    """

    bundle_profile: Path
    version_metadata: Path
    fabric_api_url: str
    fabric_api_size: int
    fabric_api_sha256: str


def reviewed_stacks() -> dict[str, ReviewedStack]:
    from minekin_core.adapters.launcher import recipe

    fixtures = REPOSITORY_ROOT / "tests" / "fixtures"
    return {
        DEFAULT_VERSION: ReviewedStack(
            bundle_profile=fixtures / "runtime-input" / "bundle-p0-core-1.21.4.json",
            version_metadata=fixtures / "launcher" / "1.21.4.json",
            fabric_api_url=recipe.FABRIC_API_URL,
            fabric_api_size=recipe.FABRIC_API_SIZE,
            fabric_api_sha256=recipe.FABRIC_API_SHA256,
        ),
        recipe.MINECRAFT_1201_VERSION: ReviewedStack(
            bundle_profile=fixtures / "runtime-input" / "bundle-candidate-1.20.1.json",
            version_metadata=fixtures / "launcher" / "1.20.1.json",
            fabric_api_url=recipe.FABRIC_API_1201_URL,
            fabric_api_size=recipe.FABRIC_API_1201_SIZE,
            fabric_api_sha256=recipe.FABRIC_API_1201_SHA256,
        ),
    }


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


def server_artifact(stack: ReviewedStack) -> dict[str, object]:
    """The pinned vanilla server the test domain runs, from the frozen metadata.

    It is not part of the client bundle, which is why it is opt-in: it is fifty
    times the size of everything else this tool fetches put together.
    """

    import json

    downloads = json.loads(stack.version_metadata.read_bytes())["downloads"]
    return dict(downloads["server"])


def keep(payload: bytes, destination: Path) -> str:
    """Write verified bytes to `destination`, or refuse what is already there.

    A different file at that path is somebody's server jar, a partial download,
    or another version, and the one thing all three must not become is "the
    pinned server" by being written over. So the bytes go to a staging name
    first, and only a payload that has already been checked against the pin
    reaches the final one.
    """

    if destination.exists():
        if destination.read_bytes() == payload:
            return "already present"
        raise ValueError(f"{destination} is not the pinned jar; refusing to replace it")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staged = destination.with_name(f"{destination.name}.staging")
    staged.write_bytes(payload)
    staged.replace(destination)
    return "saved"


def plan(stack: ReviewedStack) -> list[dict[str, object]]:
    from minekin_core.adapters.launcher.launch_plan import build_launch_plan

    return list(build_launch_plan(stack.bundle_profile)["artifacts"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--version",
        default=DEFAULT_VERSION,
        metavar="VERSION",
        help="which reviewed stack to re-check; one of the versions the recipe pins",
    )
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    parser.add_argument(
        "--include-server",
        action="store_true",
        help="also verify the pinned vanilla server jar (not part of the bundle)",
    )
    parser.add_argument(
        "--save-server",
        default=None,
        metavar="PATH",
        help=(
            "keep the verified server jar at PATH (implies --include-server); "
            "refuses to replace a different file already there"
        ),
    )
    args = parser.parse_args()

    stacks = reviewed_stacks()
    stack = stacks.get(args.version)
    if stack is None:
        print(
            f"no reviewed supply chain is pinned for Minecraft {args.version}; "
            f"this tool checks {', '.join(sorted(stacks))} and refuses to guess at another",
            file=sys.stderr,
        )
        return 2

    selected = _smallest_per_host(plan(stack))
    server = server_artifact(stack) if args.include_server or args.save_server else None
    planned_bytes = sum(int(str(item["size"])) for item in selected) + stack.fabric_api_size
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

    payload = _read(stack.fabric_api_url)
    digest = hashlib.sha256(payload).hexdigest()
    if digest != stack.fabric_api_sha256 or len(payload) != stack.fabric_api_size:
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
            verified.append(
                Verified(f"com.mojang:server:{args.version}", len(payload), digest, None)
            )
            if args.save_server is not None:
                # Only bytes that already matched the pin are offered to `keep`.
                try:
                    outcome = keep(payload, Path(args.save_server).resolve())
                except ValueError as refusal:
                    print(str(refusal), file=sys.stderr)
                    return 1
                print(f"{outcome}: {Path(args.save_server).resolve()}")

    for item in verified:
        print(f"ok  {item.name}  {item.size} bytes")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"Supply chain: OK ({len(verified)} pinned artifacts still match)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
