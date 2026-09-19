from __future__ import annotations

from pathlib import Path

import pytest

from minekin_core.adapters.bridge.bootstrap import (
    DESCRIPTOR_FILENAME,
    bridge_session_for,
    descriptor_path,
)
from minekin_core.adapters.launcher.launch_plan import build_launch_plan
from minekin_core.domain.errors import ErrorCategory, MinekinError
from minekin_core.domain.ids import KinId

PROFILE = Path(__file__).resolve().parents[1] / "fixtures/runtime-input/bundle-p0-core-1.21.4.json"
KIN = KinId("kin-01")


def plan() -> dict[str, object]:
    return build_launch_plan(PROFILE)


def session(plan_document: dict[str, object] | None = None, **overrides: object):
    arguments: dict[str, object] = {
        "kin_id": KIN,
        "session_id": "session-1",
        "generation": 1,
        "client_instance_id": "client-1",
    }
    arguments.update(overrides)
    return bridge_session_for(plan_document if plan_document is not None else plan(), **arguments)  # type: ignore[arg-type]


# Resolved once so the expected strings match on any host platform.
OVERLAY = Path("/srv/minekin/run/session/session-1/generation-1").resolve()


def test_the_descriptor_lands_in_the_session_overlay() -> None:
    assert descriptor_path(OVERLAY) == OVERLAY / DESCRIPTOR_FILENAME


def test_a_relative_overlay_is_refused() -> None:
    """The descriptor holds the session key, so where it lands cannot be left to the cwd."""

    with pytest.raises(MinekinError, match="absolute") as raised:
        descriptor_path(Path("session/session-1/generation-1"))

    assert raised.value.category is ErrorCategory.IPC_PROTOCOL


def test_the_reviewed_plan_binds_the_session_it_launches() -> None:
    reviewed = plan()

    built = session(reviewed)

    assert built.kin_id == str(KIN)
    assert built.session_id == "session-1"
    assert built.generation == 1
    assert built.client_instance_id == "client-1"
    assert built.bundle_digest == reviewed["plan_sha256"]
    assert built.bridge_digest == reviewed["bridge_source_sha256"]


@pytest.mark.parametrize("key", ["plan_sha256", "bridge_source_sha256"])
@pytest.mark.parametrize("value", [None, "", "AB" * 32, "a" * 63, 7])
def test_a_plan_without_a_usable_digest_is_refused(key: str, value: object) -> None:
    broken = dict(plan())
    if value is None:
        del broken[key]
    else:
        broken[key] = value

    with pytest.raises(MinekinError, match=key) as raised:
        session(broken)

    assert raised.value.category is ErrorCategory.IPC_PROTOCOL


def test_each_launch_gets_its_own_secrets() -> None:
    first = session()
    second = session()

    assert len(first.launch_nonce) == 32
    assert len(first.session_key) == 32
    assert first.launch_nonce != second.launch_nonce
    assert first.session_key != second.session_key


def test_injected_secrets_are_used_verbatim() -> None:
    built = session(nonce=b"n" * 32, session_key=b"k" * 32)

    assert built.launch_nonce == b"n" * 32
    assert built.session_key == b"k" * 32


@pytest.mark.parametrize("secret", [b"short", b"s" * 33, b""])
def test_a_secret_that_is_not_256_bits_is_refused(secret: bytes) -> None:
    with pytest.raises(MinekinError, match="32 bytes"):
        session(nonce=secret)
