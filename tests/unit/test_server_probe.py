from __future__ import annotations

import json
from pathlib import Path

import pytest

from minekin_core.adapters.launcher.server_probe import (
    ProbeMalformed,
    ProbeNoResponse,
    ProbeOversize,
    ProbeTimeout,
    ResolvedTarget,
    build_handshake,
    build_status_request,
    parse_status_payload,
    probe_profile,
    status_json_from_packet,
)
from minekin_core.adapters.launcher.server_profile import (
    load_managed_target_profile,
    load_server_profile,
)
from minekin_core.domain.version_probe import ProbeOutcome, endpoint_ref

V1_FIXTURE = Path("tests/fixtures/runtime-input/controlled-offline-server.json")
V2_FIXTURE = Path("tests/fixtures/launcher/managed-remote-target-example.json")


def payload(protocol: int | None = 770, name: str | None = "1.21.4", **extra: object) -> bytes:
    version: dict[str, object] = {}
    if protocol is not None:
        version["protocol"] = protocol
    if name is not None:
        version["name"] = name
    document: dict[str, object] = {"version": version, "description": "A Minecraft Server"}
    document.update(extra)
    return json.dumps(document).encode("utf-8")


class FakeResolver:
    def __init__(self, targets: tuple[ResolvedTarget, ...]) -> None:
        self._targets = targets
        self.calls = 0

    def resolve(self, profile: object) -> tuple[ResolvedTarget, ...]:
        del profile
        self.calls += 1
        return self._targets


class FakeTransport:
    def __init__(self, result: bytes | Exception) -> None:
        self._result = result
        self.calls: list[tuple[str, int, float]] = []

    def fetch(self, host: str, port: int, timeout_s: float) -> bytes:
        self.calls.append((host, port, timeout_s))
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


def loopback_target(port: int = 25565) -> ResolvedTarget:
    return ResolvedTarget("127.0.0.1", port)


def test_a_loopback_status_answer_is_observed() -> None:
    profile = load_server_profile(V1_FIXTURE)
    transport = FakeTransport(payload())

    observation = probe_profile(
        profile,
        resolver=FakeResolver((loopback_target(),)),
        transport=transport,
        timeout_s=3.0,
    )

    assert observation.outcome is ProbeOutcome.OBSERVED
    assert observation.protocol == 770
    assert observation.version_text == "1.21.4"
    assert observation.endpoint == "127.0.0.1:25565"
    assert transport.calls == [("127.0.0.1", 25565, 3.0)]
    assert observation.resolution_chain[0] == "saved:127.0.0.1:25565"
    assert observation.resolution_chain[1] == "as-saved:127.0.0.1:25565"
    assert observation.resolution_chain[-1] == f"payload:{len(payload())}"


@pytest.mark.parametrize(
    "target", [ResolvedTarget("10.0.0.5", 25565), ResolvedTarget("10.0.0.5", 25565, via_srv=True)]
)
def test_a_resolved_endpoint_outside_the_policy_never_reaches_the_transport(
    target: ResolvedTarget,
) -> None:
    """DNS rebinding and a redirecting SRV record are stopped before any connect."""

    profile = load_server_profile(V1_FIXTURE)
    transport = FakeTransport(payload())

    observation = probe_profile(profile, resolver=FakeResolver((target,)), transport=transport)

    assert observation.outcome is ProbeOutcome.POLICY_REFUSAL
    assert "OUTSIDE_POLICY" in observation.refusal_reasons
    assert transport.calls == []


def test_an_srv_step_is_recorded_in_the_chain() -> None:
    profile = load_server_profile(V1_FIXTURE)

    observation = probe_profile(
        profile,
        resolver=FakeResolver((ResolvedTarget("127.0.0.1", 25566, via_srv=True),)),
        transport=FakeTransport(payload()),
    )

    assert observation.outcome is ProbeOutcome.OBSERVED
    assert observation.resolution_chain[1] == "srv:127.0.0.1:25566"


def test_multiple_candidates_are_ambiguous_without_connecting() -> None:
    profile = load_server_profile(V1_FIXTURE)
    transport = FakeTransport(payload())

    observation = probe_profile(
        profile,
        resolver=FakeResolver((loopback_target(), ResolvedTarget("127.0.0.2", 25565))),
        transport=transport,
    )

    assert observation.outcome is ProbeOutcome.AMBIGUOUS
    assert observation.refusal_reasons == ("RESOLUTION_AMBIGUOUS",)
    assert transport.calls == []
    assert "resolved:2 candidates" in observation.resolution_chain[-1]


def test_a_stale_entry_is_reported_as_expired_before_a_decision() -> None:
    profile = load_server_profile(V1_FIXTURE)

    observation = probe_profile(
        profile,
        resolver=FakeResolver((ResolvedTarget("127.0.0.1", 25565, stale=True),)),
        transport=FakeTransport(payload()),
    )

    assert observation.outcome is ProbeOutcome.CACHE_EXPIRED
    assert observation.refusal_reasons == ("RESOLUTION_EXPIRED",)


@pytest.mark.parametrize(
    ("error", "outcome"),
    [
        (ProbeTimeout("connect timed out"), ProbeOutcome.TIMEOUT),
        (ProbeNoResponse("refused"), ProbeOutcome.NO_RESPONSE),
        (ProbeOversize("too big"), ProbeOutcome.OVERSIZE),
        (ProbeMalformed("not a frame"), ProbeOutcome.MALFORMED),
    ],
)
def test_a_transport_failure_becomes_its_own_outcome(
    error: Exception, outcome: ProbeOutcome
) -> None:
    profile = load_server_profile(V1_FIXTURE)

    observation = probe_profile(
        profile,
        resolver=FakeResolver((loopback_target(),)),
        transport=FakeTransport(error),
    )

    assert observation.outcome is outcome
    assert observation.detail == str(error)


def test_a_non_json_body_is_malformed() -> None:
    profile = load_server_profile(V1_FIXTURE)

    observation = probe_profile(
        profile,
        resolver=FakeResolver((loopback_target(),)),
        transport=FakeTransport(b"\xff\xfe not json"),
    )

    assert observation.outcome is ProbeOutcome.MALFORMED


def test_a_display_text_over_the_cap_is_malformed() -> None:
    profile = load_server_profile(V1_FIXTURE)

    observation = probe_profile(
        profile,
        resolver=FakeResolver((loopback_target(),)),
        transport=FakeTransport(payload(name="x" * 200)),
    )

    assert observation.outcome is ProbeOutcome.MALFORMED


def test_a_multi_version_proxy_listing_is_ambiguous_but_keeps_raw_values() -> None:
    profile = load_server_profile(V1_FIXTURE)

    observation = probe_profile(
        profile,
        resolver=FakeResolver((loopback_target(),)),
        transport=FakeTransport(payload(versions=[{"protocol": 763}, {"protocol": 770}])),
    )

    assert observation.outcome is ProbeOutcome.AMBIGUOUS
    assert observation.refusal_reasons == ("MULTI_VERSION_PROXY",)
    assert observation.protocol == 770
    assert observation.version_text == "1.21.4"


def test_a_saved_address_outside_the_echo_ranges_is_referenced_only_by_profile(
    tmp_path: Path,
) -> None:
    document = json.loads(V2_FIXTURE.read_text(encoding="utf-8"))
    document["host"] = "10.20.30.40"
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    profile = load_managed_target_profile(path)

    observation = probe_profile(
        profile,
        resolver=FakeResolver((ResolvedTarget("10.20.30.40", 25565),)),
        transport=FakeTransport(payload(protocol=763, name="1.20.1")),
    )

    assert observation.outcome is ProbeOutcome.OBSERVED
    assert observation.endpoint == f"profile:{document['profile_id']}"
    assert "10.20.30.40" not in json.dumps(observation.as_document())


def test_a_document_range_target_is_echoed_rather_than_redacted() -> None:
    profile = load_managed_target_profile(V2_FIXTURE)

    assert endpoint_ref(profile.host, profile.port, profile.profile_id) == "198.51.100.20:25565"


# --- framing and parsing helpers -------------------------------------------------


def test_the_handshake_frames_one_packet_with_the_saved_host_and_next_state() -> None:
    frame = build_handshake("127.0.0.1", 25565)
    # Declared length prefix equals the rest of the buffer.
    assert frame[0] == len(frame) - 1
    assert frame.endswith(b"\x01")  # next state: status
    assert b"127.0.0.1" in frame


def test_the_status_request_is_a_single_empty_packet() -> None:
    assert build_status_request() == b"\x01\x00"


def _framed_status_packet(document: bytes) -> bytes:
    """The packet body the transport reads: a 0x00 id, then the JSON string.

    Built with single-byte varints, which is what every small document this test
    uses actually encodes to (id 0x00 and a length under 128).
    """

    assert len(document) < 128
    return bytes((0x00, len(document))) + document


def test_the_transport_peels_the_packet_id_and_string_length_off_the_body() -> None:
    document = b'{"version":{"protocol":769,"name":"1.21.4"}}'

    assert status_json_from_packet(_framed_status_packet(document)) == document


def test_a_real_framed_response_is_observed_end_to_end() -> None:
    """What the live 1.21.4 probe exercised: body framing, then JSON parsing."""

    body = _framed_status_packet(b'{"version":{"protocol":769,"name":"1.21.4"}}')

    assert parse_status_payload(status_json_from_packet(body)) == (769, "1.21.4", False)


def test_a_packet_with_the_wrong_id_is_malformed() -> None:
    with pytest.raises(ProbeMalformed, match="packet id"):
        status_json_from_packet(bytes((0x01, 0x02)) + b"{}")


def test_a_string_truncated_below_its_declared_length_is_malformed() -> None:
    with pytest.raises(ProbeMalformed, match="declared length"):
        status_json_from_packet(bytes((0x00, 50)) + b'{"a"')


def test_parsing_rejects_a_body_with_neither_protocol_nor_text() -> None:
    with pytest.raises(ProbeMalformed):
        parse_status_payload(json.dumps({"version": {}}).encode())


def test_parsing_reads_a_protocol_only_answer() -> None:
    assert parse_status_payload(payload(protocol=763, name=None)) == (763, None, False)
