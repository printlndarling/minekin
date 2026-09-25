from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path

import pytest

from bridge_peer import (  # type: ignore[import-not-found]
    close_writers,
    connect,
    envelope,
    hello,
    write_frame,
)
from minekin_core.adapters.bridge.bootstrap import (
    DESCRIPTOR_FILENAME,
    bridge_session_for,
    descriptor_path,
)
from minekin_core.adapters.bridge.ipc import (
    BRIDGE_HELLO_TYPE,
    BridgeIpcHost,
    BridgeSession,
    IpcProtocolError,
)
from minekin_core.adapters.launcher.launch_plan import build_launch_plan
from minekin_core.domain.errors import ErrorCategory, MinekinError
from minekin_core.domain.ids import KinId
from minekin_core.generated.minekin.v1 import envelope_pb2

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


def test_the_session_verifies_the_versions_the_plan_launches() -> None:
    """Core's expectation is the plan's, so two candidates pair with two recipes."""

    built = session()

    assert built.minecraft_version == "1.21.4"
    assert built.fabric_loader_version == "0.16.9"


def test_a_plan_that_does_not_say_which_loader_it_launches_is_refused() -> None:
    reviewed = plan()
    del reviewed["bundle"]["fabric_loader"]  # type: ignore[index]

    with pytest.raises(MinekinError, match="fabric_loader"):
        session(reviewed)


def test_a_plan_with_no_bundle_section_is_refused() -> None:
    reviewed = plan()
    del reviewed["bundle"]

    with pytest.raises(MinekinError, match="bundle section"):
        session(reviewed)


@pytest.mark.parametrize("key", ["minecraft", "fabric_loader"])
@pytest.mark.parametrize("value", ["", "1.21.4 ", "1.21.4\00.16.9", "v1.21.4", "x" * 32])
def test_a_plan_whose_version_the_recipe_could_not_pin_is_refused(key: str, value: str) -> None:
    """Both strings enter a proof context joined by NUL, so shape is a boundary.

    `"1.21.4\\00.16.9"` is the case the guard exists for: as one field it is
    nonsense, as a context it is two fields pretending to be one.
    """

    reviewed = plan()
    reviewed["bundle"][key] = value  # type: ignore[index]

    with pytest.raises(MinekinError, match=key):
        session(reviewed)


def test_a_session_cannot_hold_an_unshaped_version_either() -> None:
    built = session()

    with pytest.raises(ValueError, match="minecraft_version"):
        replace(built, minecraft_version="1.21.4 ")


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


#: Measured against the proof the shipped code built before the versions came off the
#: session: the two strings were spelled out in the context, and this hex is what
#: that context hashes to for the reviewed 1.21.4 plan and these secrets.
BRIDGE_HELLO_PROOF_1214 = "dd1e49ce34d4ce9662b48a7f35ead3910727244f7aae907081ab06514bdc0c5e"


def authenticate(
    host_session: BridgeSession, hello_session: BridgeSession, proof: str, tmp_path: Path
) -> None:
    """Put a hello carrying `proof` over the real loopback seam and let Core judge it.

    The declared identity fields come from `hello_session`, so the only question
    left standing is the one the card answers: which digest does Core compute for
    *this* session, from this session's own versions?
    """

    async def scenario() -> None:
        host = BridgeIpcHost(host_session)
        descriptor = await host.prepare(tmp_path / "descriptor.pb")
        _control_reader, control_writer = await connect(descriptor, envelope_pb2.CHANNEL_CONTROL)
        _event_reader, event_writer = await connect(descriptor, envelope_pb2.CHANNEL_EVENT)
        value = hello(hello_session, proof=proof)
        await write_frame(
            control_writer,
            envelope(
                hello_session,
                BRIDGE_HELLO_TYPE,
                envelope_pb2.CHANNEL_CONTROL,
                1,
                value.SerializeToString(deterministic=True),
            ),
        )
        assert await host.authenticate() == value
        await host.close()
        await close_writers(control_writer, event_writer)

    asyncio.run(scenario())


def test_the_reviewed_1214_session_is_still_proved_by_the_digest_it_always_had(
    tmp_path: Path,
) -> None:
    """The card's own guarantee, in bytes rather than in words.

    Core, not a re-derivation in this file, is what accepts the pre-change digest.
    """

    built = session(nonce=b"n" * 32, session_key=b"k" * 32)

    authenticate(built, built, BRIDGE_HELLO_PROOF_1214, tmp_path)


@pytest.mark.parametrize(
    "other",
    [
        pytest.param({"minecraft_version": "1.20.1"}, id="minecraft"),
        pytest.param({"fabric_loader_version": "0.19.5"}, id="fabric_loader"),
    ],
)
def test_a_session_with_one_version_of_the_pair_moved_does_not_share_that_digest(
    tmp_path: Path, other: dict[str, str]
) -> None:
    """The pin cannot be satisfied by dropping the versions out of the context.

    A session that resolved the other candidate's version is well-formed and
    consistent with itself, and still must not be proved by the digest the 1.21.4
    session carries — which is only true while the versions are in the context.
    """

    built = session(nonce=b"n" * 32, session_key=b"k" * 32)
    variant = replace(built, **other)  # type: ignore[arg-type]

    with pytest.raises(IpcProtocolError, match="was rejected"):
        authenticate(variant, variant, BRIDGE_HELLO_PROOF_1214, tmp_path)
