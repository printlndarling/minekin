"""The read-only Server List Ping probe.

Everything the probe needs from the outside world sits behind two narrow
protocols: a resolver that says where a saved profile's name leads, and a
transport that fetches one status payload. The production defaults resolve
nothing beyond the saved literal itself, and every candidate is re-decided
against the profile's own address policy *before* a connection is made — a
redirecting SRV record or a rebinding name never reaches the transport.

The probe creates no session, no JVM and no lease, and it never guesses a
version by trying logins: a refusal or an ambiguous answer is the report.
"""

from __future__ import annotations

import json
import socket
from dataclasses import dataclass
from typing import Protocol, cast

from minekin_core.adapters.launcher.server_profile import (
    ManagedTargetProfile,
    ServerProfile,
)
from minekin_core.domain.admission import AddressPolicy, decide_endpoint
from minekin_core.domain.version_probe import (
    MAX_DISPLAY_TEXT_CHARS,
    MAX_STATUS_PAYLOAD_BYTES,
    ProbeObservation,
    ProbeOutcome,
    endpoint_ref,
)

ProbeProfile = ServerProfile | ManagedTargetProfile


@dataclass(frozen=True, slots=True)
class ResolvedTarget:
    """One candidate the resolver produced for the saved profile."""

    host: str
    port: int
    via_srv: bool = False
    stale: bool = False


class TargetResolver(Protocol):
    def resolve(self, profile: ProbeProfile) -> tuple[ResolvedTarget, ...]: ...


class StatusTransport(Protocol):
    def fetch(self, host: str, port: int, timeout_s: float) -> bytes: ...


class ProbeTimeout(Exception):
    """The endpoint stopped answering inside the budget."""


class ProbeNoResponse(Exception):
    """The endpoint refused or closed without a frame."""


class ProbeOversize(Exception):
    """A declared or delivered payload beyond the frozen cap."""


class ProbeMalformed(Exception):
    """A frame or document that is not a status response."""


class SavedAddressResolver:
    """The honest default: the saved literal, unchanged, with no lookup at all."""

    def resolve(self, profile: ProbeProfile) -> tuple[ResolvedTarget, ...]:
        return (ResolvedTarget(profile.host, profile.port),)


def _policy_for(profile: ProbeProfile) -> AddressPolicy:
    if isinstance(profile, ManagedTargetProfile):
        return profile.address_policy()
    return AddressPolicy.p0_loopback()


def _write_varint(value: int) -> bytes:
    if 0 <= value < 128:
        return bytes((value,))
    out = bytearray()
    remaining = value
    while True:
        temp = remaining & 0x7F
        remaining >>= 7
        if remaining:
            out.append(temp | 0x80)
        else:
            out.append(temp)
            return bytes(out)


def _read_varint(data: bytes, start: int) -> tuple[int, int] | None:
    """Decode one protocol varint; None when the buffer does not hold a whole one."""

    value = 0
    position = start
    for shift in range(0, 35, 7):
        if position >= len(data):
            return None
        byte = data[position]
        value |= (byte & 0x7F) << shift
        position += 1
        if not byte & 0x80:
            return value, position
    raise ProbeMalformed("varint longer than five bytes")


def build_handshake(host: str, port: int) -> bytes:
    encoded = host.encode("utf-8")
    body = (
        _write_varint(0x00)
        + _write_varint(0)
        + _write_varint(len(encoded))
        + encoded
        + port.to_bytes(2, "big")
        + _write_varint(1)
    )
    return _write_varint(len(body)) + body


def build_status_request() -> bytes:
    body = _write_varint(0x00)
    return _write_varint(len(body)) + body


def status_json_from_packet(packet: bytes) -> bytes:
    """Peel the packet-id and JSON-string-length varints off a status response body."""

    declared = _read_varint(packet, 0)
    if declared is None:
        raise ProbeMalformed("the status packet carries no id")
    packet_id, position = declared
    if packet_id != 0x00:
        raise ProbeMalformed("the status response packet id is not 0x00")
    declared = _read_varint(packet, position)
    if declared is None:
        raise ProbeMalformed("the status packet carries no string length")
    length, position = declared
    if length < 0 or len(packet) - position < length:
        raise ProbeMalformed("the status string is shorter than its declared length")
    return packet[position : position + length]


class SocketStatusTransport:
    """One framed status exchange, byte- and time-bounded, with nothing reused."""

    def fetch(self, host: str, port: int, timeout_s: float) -> bytes:
        try:
            infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except socket.gaierror as error:
            raise ProbeMalformed("the saved target did not resolve to a socket address") from error
        family, socktype, proto, _, sockaddr = infos[0]
        with socket.socket(family, socktype, proto) as sock:
            sock.settimeout(timeout_s)
            try:
                sock.connect(sockaddr)
            except TimeoutError:
                raise ProbeTimeout("connect timed out") from None
            except OSError:
                raise ProbeNoResponse("the endpoint refused the connection") from None
            sock.sendall(build_handshake(host, port) + build_status_request())
            return status_json_from_packet(self._read_one_frame(sock))

    def _read_one_frame(self, sock: socket.socket) -> bytes:
        buffer = bytearray()
        payload_start = 0
        payload_length: int | None = None
        while True:
            try:
                chunk = sock.recv(8192)
            except TimeoutError:
                raise ProbeTimeout("the response stalled mid-frame") from None
            except OSError:
                raise ProbeNoResponse("the connection broke mid-frame") from None
            if not chunk:
                if payload_length is None:
                    raise ProbeNoResponse("the endpoint closed before any frame")
                raise ProbeMalformed("the frame ended before its declared length")
            buffer.extend(chunk)
            if payload_length is None:
                declared = _read_varint(bytes(buffer), 0)
                if declared is not None:
                    length, payload_start = declared
                    if length < 0:
                        raise ProbeMalformed("a negative frame length is not a response")
                    if length > MAX_STATUS_PAYLOAD_BYTES:
                        raise ProbeOversize("the declared frame exceeds the frozen cap")
                    payload_length = length
            if len(buffer) - payload_start > MAX_STATUS_PAYLOAD_BYTES:
                raise ProbeOversize("the delivered frame exceeds the frozen cap")
            if payload_length is not None and len(buffer) - payload_start >= payload_length:
                return bytes(buffer[payload_start : payload_start + payload_length])


def parse_status_payload(payload: bytes) -> tuple[int | None, str | None, bool]:
    """(protocol, display text, multi-version proxy) or the ProbeMalformed explaining why not."""

    try:
        parsed = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProbeMalformed("the status payload is not UTF-8 JSON") from error
    if not isinstance(parsed, dict):
        raise ProbeMalformed("the status payload is not an object")
    document = cast("dict[str, object]", parsed)
    raw_version = document.get("version")
    if not isinstance(raw_version, dict):
        raise ProbeMalformed("the status payload carries no version object")
    version = cast("dict[str, object]", raw_version)
    raw_protocol = version.get("protocol")
    protocol = (
        raw_protocol
        if isinstance(raw_protocol, int) and not isinstance(raw_protocol, bool)
        else None
    )
    raw_name = version.get("name")
    if raw_name is not None and not isinstance(raw_name, str):
        raise ProbeMalformed("the version display text is not a string")
    if isinstance(raw_name, str) and len(raw_name) > MAX_DISPLAY_TEXT_CHARS:
        raise ProbeMalformed("the version display text is over the frozen cap")
    multi = isinstance(document.get("versions"), list)
    if protocol is None and raw_name is None:
        raise ProbeMalformed("the version object carries neither protocol nor display text")
    return protocol, raw_name, multi


def _refusal(
    profile: ProbeProfile,
    outcome: ProbeOutcome,
    chain: tuple[str, ...],
    *,
    reasons: tuple[str, ...] = (),
    detail: str | None = None,
) -> ProbeObservation:
    return ProbeObservation(
        outcome=outcome,
        profile_id=profile.profile_id,
        profile_revision=profile.revision,
        endpoint=endpoint_ref(profile.host, profile.port, profile.profile_id),
        resolution_chain=chain,
        refusal_reasons=reasons,
        detail=detail,
    )


def probe_profile(
    profile: ProbeProfile,
    *,
    resolver: TargetResolver | None = None,
    transport: StatusTransport | None = None,
    timeout_s: float = 5.0,
) -> ProbeObservation:
    """Ask one saved profile what it is, without ever becoming a player."""

    active_resolver: TargetResolver = resolver if resolver is not None else SavedAddressResolver()
    active_transport: StatusTransport = (
        transport if transport is not None else SocketStatusTransport()
    )
    policy = _policy_for(profile)
    chain = [f"saved:{endpoint_ref(profile.host, profile.port, profile.profile_id)}"]

    targets = active_resolver.resolve(profile)
    if len(targets) != 1:
        return _refusal(
            profile,
            ProbeOutcome.AMBIGUOUS,
            (*chain, f"resolved:{len(targets)} candidates"),
            reasons=("RESOLUTION_AMBIGUOUS",),
            detail="a probe answers one endpoint; multiple candidates need an operator pin",
        )
    target = targets[0]
    step = "srv" if target.via_srv else "as-saved"
    chain = (*chain, f"{step}:{endpoint_ref(target.host, target.port, profile.profile_id)}")

    if target.stale:
        return _refusal(
            profile,
            ProbeOutcome.CACHE_EXPIRED,
            chain,
            reasons=("RESOLUTION_EXPIRED",),
            detail="the resolver handed back an entry past its TTL; a fresh resolution is needed",
        )

    decision = decide_endpoint(policy, target.host, target.port)
    if not decision.allowed:
        # Re-decided *before* connecting: this is the line a rebinding name or a
        # redirecting SRV record has to cross, and it never gets to the transport.
        return _refusal(
            profile,
            ProbeOutcome.POLICY_REFUSAL,
            chain,
            reasons=tuple(reason.value for reason in decision.reasons),
            detail="the resolved endpoint is outside the address policy saved in the profile",
        )

    try:
        payload = active_transport.fetch(target.host, target.port, timeout_s)
    except ProbeTimeout as error:
        return _refusal(profile, ProbeOutcome.TIMEOUT, chain, detail=str(error))
    except ProbeNoResponse as error:
        return _refusal(profile, ProbeOutcome.NO_RESPONSE, chain, detail=str(error))
    except ProbeOversize as error:
        return _refusal(profile, ProbeOutcome.OVERSIZE, chain, detail=str(error))
    except ProbeMalformed as error:
        return _refusal(profile, ProbeOutcome.MALFORMED, chain, detail=str(error))

    chain = (*chain, f"payload:{len(payload)}")
    try:
        protocol, version_text, multi = parse_status_payload(payload)
    except ProbeMalformed as error:
        return _refusal(
            profile,
            ProbeOutcome.MALFORMED,
            chain,
            detail=str(error),
        )
    except ProbeOversize as error:
        return _refusal(profile, ProbeOutcome.OVERSIZE, chain, detail=str(error))

    if multi:
        return ProbeObservation(
            outcome=ProbeOutcome.AMBIGUOUS,
            profile_id=profile.profile_id,
            profile_revision=profile.revision,
            endpoint=endpoint_ref(target.host, target.port, profile.profile_id),
            resolution_chain=chain,
            protocol=protocol,
            version_text=version_text,
            refusal_reasons=("MULTI_VERSION_PROXY",),
            received_bytes=len(payload),
            detail="a multi-version listing was observed; raw values are kept for a pin decision",
        )
    return ProbeObservation(
        outcome=ProbeOutcome.OBSERVED,
        profile_id=profile.profile_id,
        profile_revision=profile.revision,
        endpoint=endpoint_ref(target.host, target.port, profile.profile_id),
        resolution_chain=chain,
        protocol=protocol,
        version_text=version_text,
        received_bytes=len(payload),
    )
