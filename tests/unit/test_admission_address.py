from __future__ import annotations

import ipaddress

import pytest

from minekin_core.domain.admission import (
    AddressPolicy,
    AddressReason,
    decide_endpoint,
)

P0 = AddressPolicy.p0_loopback()
OPEN_POLICY = AddressPolicy((ipaddress.ip_network("0.0.0.0/0"), ipaddress.ip_network("::/0")))


def reasons(host: str, port: int = 25565, policy: AddressPolicy = P0) -> tuple[AddressReason, ...]:
    return decide_endpoint(policy, host, port).reasons


def test_the_frozen_policy_admits_both_loopback_literals() -> None:
    for host in ("127.0.0.1", "::1"):
        decision = decide_endpoint(P0, host, 25565)

        assert decision.allowed, host
        assert decision.reasons == ()
        assert decision.address == host


def test_a_bracketed_ipv6_literal_is_accepted() -> None:
    decision = decide_endpoint(P0, "[::1]", 25565)

    assert decision.allowed
    assert decision.address == "::1"


@pytest.mark.parametrize("host", ["127.0.0.2", "10.0.0.1", "192.168.1.5", "100.64.0.1"])
def test_an_address_outside_the_policy_is_refused(host: str) -> None:
    assert reasons(host) == (AddressReason.OUTSIDE_POLICY,)


@pytest.mark.parametrize("host", ["localhost", "example.com", "play.example.org", "", "  "])
def test_a_name_is_never_resolved_into_place(host: str) -> None:
    """A name can rebind, so only a literal that the policy already admits counts."""

    decision = decide_endpoint(P0, host, 25565)

    assert not decision.allowed
    assert decision.reasons == (AddressReason.NOT_A_LITERAL,)
    assert decision.address is None


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("169.254.169.254", AddressReason.LINK_LOCAL),
        ("169.254.0.1", AddressReason.LINK_LOCAL),
        ("fe80::1", AddressReason.LINK_LOCAL),
        ("0.0.0.0", AddressReason.UNSPECIFIED),
        ("::", AddressReason.UNSPECIFIED),
        ("224.0.0.1", AddressReason.MULTICAST),
        ("ff02::1", AddressReason.MULTICAST),
    ],
)
def test_the_unconditional_blocks_hold_under_a_wide_open_policy(
    host: str, expected: AddressReason
) -> None:
    """No policy may be widened into the metadata, unspecified or multicast ranges."""

    assert expected in reasons(host, policy=OPEN_POLICY)
    assert not decide_endpoint(OPEN_POLICY, host, 25565).allowed


def test_the_metadata_address_is_blocked_twice_over() -> None:
    """It is outside the frozen policy and unconditionally link-local."""

    assert set(reasons("169.254.169.254")) == {
        AddressReason.LINK_LOCAL,
        AddressReason.OUTSIDE_POLICY,
    }


@pytest.mark.parametrize("port", [0, -1, 65536, True, "25565", None])
def test_a_port_outside_range_is_refused_even_for_an_allowed_host(port: object) -> None:
    decision = decide_endpoint(P0, "127.0.0.1", port)

    assert not decision.allowed
    assert decision.reasons == (AddressReason.PORT_OUT_OF_RANGE,)


def test_a_bad_port_and_a_bad_host_are_both_reported() -> None:
    decision = decide_endpoint(P0, "example.com", 0)

    assert set(decision.reasons) == {
        AddressReason.NOT_A_LITERAL,
        AddressReason.PORT_OUT_OF_RANGE,
    }


def test_the_decision_document_is_evidence_ready() -> None:
    assert decide_endpoint(P0, "169.254.169.254", 25565).as_document() == {
        "allowed": False,
        "reasons": ["LINK_LOCAL", "OUTSIDE_POLICY"],
        "address": "169.254.169.254",
    }
    assert decide_endpoint(P0, "127.0.0.1", 25565).as_document() == {
        "allowed": True,
        "reasons": [],
        "address": "127.0.0.1",
    }


def test_the_address_is_normalized_rather_than_echoed() -> None:
    assert decide_endpoint(P0, "::1", 25565).address == "::1"
    assert decide_endpoint(OPEN_POLICY, "::FFFF:7F00:1", 25565).address == "::ffff:127.0.0.1"


def test_a_policy_must_allow_something() -> None:
    with pytest.raises(ValueError, match="at least one network"):
        AddressPolicy(())


def test_an_explicit_policy_admits_only_its_own_address() -> None:
    policy = AddressPolicy.for_explicit_target("198.51.100.20")

    assert decide_endpoint(policy, "198.51.100.20", 25565).allowed
    refused = decide_endpoint(policy, "198.51.100.21", 25565)
    assert not refused.allowed
    assert refused.reasons == (AddressReason.OUTSIDE_POLICY,)


def test_an_explicit_policy_needs_a_literal_not_a_name() -> None:
    with pytest.raises(ValueError, match="IP literal"):
        AddressPolicy.for_explicit_target("play.example.org")


def test_a_v6_mapped_variant_of_the_target_is_outside_a_v4_policy() -> None:
    """Address-family confusion: same bytes, different family, no admission."""

    policy = AddressPolicy.for_explicit_target("198.51.100.20")

    assert not decide_endpoint(policy, "::ffff:c633:6414", 25565).allowed


def test_an_ipv6_target_policy_is_a_single_host() -> None:
    policy = AddressPolicy.for_explicit_target("2001:db8::1")

    assert decide_endpoint(policy, "2001:db8::1", 25565).allowed
    assert not decide_endpoint(policy, "2001:db8::2", 25565).allowed


@pytest.mark.parametrize(
    "host", ["169.254.169.254", "fe80::1", "0.0.0.0", "::", "224.0.0.1", "ff02::1"]
)
def test_the_unconditional_blocks_hold_even_when_saved_as_the_explicit_target(
    host: str,
) -> None:
    """An operator cannot pin the metadata address even to themselves."""

    policy = AddressPolicy.for_explicit_target(host)
    decision = decide_endpoint(policy, host, 25565)

    assert not decision.allowed
    assert decision.reasons != (AddressReason.OUTSIDE_POLICY,)
