from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from minekin_core.adapters.launcher.server_profile import (
    ManagedTargetProfile,
    ServerProfile,
    load_managed_target_profile,
    load_server_profile,
    load_session_server_profile,
)
from minekin_core.domain.admission import decide_endpoint
from minekin_core.domain.errors import ErrorCategory, MinekinError

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "runtime-input"
    / "controlled-offline-server.json"
)

VALID: dict[str, object] = {
    "schema_version": 1,
    "profile_id": "p0-controlled-offline-loopback",
    "host": "127.0.0.1",
    "port": 25565,
    "auth_mode": "offline",
    "minecraft_version": "1.21.4",
    "visibility": "isolated_test_only",
    "resource_pack_policy": "deny",
}


def write(tmp_path: Path, document: object, name: str = "profile.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def load(tmp_path: Path, *, name: str = "profile.json", **overrides: object) -> ServerProfile:
    return load_server_profile(write(tmp_path, {**VALID, **overrides}, name))


def load_document(tmp_path: Path, document: dict[str, object]) -> ServerProfile:
    return load_server_profile(write(tmp_path, document))


def test_the_reviewed_fixture_loads() -> None:
    profile = load_server_profile(FIXTURE)

    assert profile.profile_id == "p0-controlled-offline-loopback"
    assert profile.host == "127.0.0.1"
    assert profile.port == 25565
    assert profile.endpoint() == "127.0.0.1:25565"
    assert profile.is_loopback
    assert profile.auth_mode == "offline"
    assert profile.resource_pack_policy == "deny"


def test_revision_is_the_digest_of_the_reviewed_document() -> None:
    expected = hashlib.sha256(
        json.dumps(VALID, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    assert load_server_profile(FIXTURE).revision == expected


def test_revision_changes_when_any_admission_field_changes(tmp_path: Path) -> None:
    baseline = load(tmp_path, name="a.json")

    assert load(tmp_path, port=25566, name="b.json").revision != baseline.revision
    assert (
        load(tmp_path, resource_pack_policy="prompt", name="c.json").revision != baseline.revision
    )


def test_ipv6_loopback_is_bracketed_in_the_endpoint(tmp_path: Path) -> None:
    profile = load(tmp_path, host="::1")

    assert profile.is_loopback
    assert profile.endpoint() == "[::1]:25565"


@pytest.mark.parametrize(
    "host",
    ["localhost", "example.com", "192.168.1.5", "0.0.0.0", "::", "127.0.0.2", "10.0.0.1"],
)
def test_only_the_two_loopback_literals_are_admitted(tmp_path: Path, host: str) -> None:
    with pytest.raises(MinekinError, match="loopback"):
        load(tmp_path, host=host)


@pytest.mark.parametrize("port", [0, 65536, -1, "25565", 25565.0, True, None])
def test_a_port_must_be_an_integer_in_range(tmp_path: Path, port: object) -> None:
    with pytest.raises(MinekinError, match="port"):
        load(tmp_path, port=port)


def test_online_mode_is_not_an_admissible_target(tmp_path: Path) -> None:
    with pytest.raises(MinekinError, match="online-mode"):
        load(tmp_path, auth_mode="online")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("minecraft_version", "1.21.3"),
        ("visibility", "public"),
        ("resource_pack_policy", "allow"),
        ("schema_version", 2),
    ],
)
def test_unreviewed_values_are_rejected(tmp_path: Path, field: str, value: object) -> None:
    with pytest.raises(MinekinError, match=field):
        load_document(tmp_path, {**VALID, field: value})


@pytest.mark.parametrize("profile_id", ["Upper", "-lead", "with space", "UPPER.CASE"])
def test_a_profile_id_must_be_a_lowercase_reference(tmp_path: Path, profile_id: str) -> None:
    with pytest.raises(MinekinError, match="profile_id"):
        load(tmp_path, profile_id=profile_id)


def test_unreviewed_extra_fields_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(MinekinError, match="unreviewed fields"):
        load(tmp_path, server_listing=[])


def test_missing_fields_are_rejected(tmp_path: Path) -> None:
    document = {key: value for key, value in VALID.items() if key != "visibility"}

    with pytest.raises(MinekinError, match="missing fields"):
        load_server_profile(write(tmp_path, document))


@pytest.mark.parametrize("document", [[], "profile", 7, None])
def test_a_profile_must_be_a_json_object(tmp_path: Path, document: object) -> None:
    with pytest.raises(MinekinError, match="must be an object"):
        load_server_profile(write(tmp_path, document))


def test_unreadable_or_malformed_json_is_rejected(tmp_path: Path) -> None:
    missing = tmp_path / "absent.json"

    with pytest.raises(MinekinError, match="not readable"):
        load_server_profile(missing)

    broken = tmp_path / "broken.json"
    broken.write_text("{ not json", encoding="utf-8")
    with pytest.raises(MinekinError, match="not readable"):
        load_server_profile(broken)


def test_a_profile_inside_the_host_minecraft_directory_is_rejected(tmp_path: Path) -> None:
    nested = tmp_path / ".minecraft" / "profile.json"
    nested.parent.mkdir()
    nested.write_text(json.dumps(VALID), encoding="utf-8")

    with pytest.raises(MinekinError, match="minecraft"):
        load_server_profile(nested)


def test_profile_errors_are_classified_as_admission_failures(tmp_path: Path) -> None:
    with pytest.raises(MinekinError) as raised:
        load(tmp_path, host="localhost")

    assert raised.value.category is ErrorCategory.ADMISSION
    assert raised.value.exit_code == 17


def test_the_evidence_document_carries_the_revision(tmp_path: Path) -> None:
    profile = load(tmp_path)

    assert profile.as_document() == {**VALID, "revision": profile.revision}


REMOTE_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "launcher"
    / "managed-remote-target-example.json"
)

VALID_V2: dict[str, object] = {
    "schema_version": 2,
    "profile_id": "managed-remote-example-docu",
    "host": "198.51.100.20",
    "port": 25565,
    "auth_mode": "offline",
    "version_policy": {"mode": "explicit_allowlist", "allowed_versions": ["1.20.1"]},
    "resource_pack_policy": "deny",
    "target_authorization": {
        "granted_by": "operator-local",
        "basis": "Documentation TEST-NET-1 address standing in for the operator's private 1.20.1"
        " offline-mode test server; the real endpoint lives only in the untracked private"
        " profile.",
    },
}


def load_v2(
    tmp_path: Path, *, name: str = "profile.json", **overrides: object
) -> ManagedTargetProfile:
    return load_managed_target_profile(write(tmp_path, {**VALID_V2, **overrides}, name))


def load_v2_document(tmp_path: Path, document: dict[str, object]) -> ManagedTargetProfile:
    return load_managed_target_profile(write(tmp_path, document))


def test_the_anonymous_remote_fixture_loads() -> None:
    profile = load_managed_target_profile(REMOTE_FIXTURE)

    assert profile.profile_id == "managed-remote-example-docu"
    assert profile.host == "198.51.100.20"
    assert profile.port == 25565
    assert profile.endpoint() == "198.51.100.20:25565"
    assert profile.allowed_versions == ("1.20.1",)
    assert profile.pinned_bundle_id is None
    assert profile.authorization_granted_by == "operator-local"


def test_the_remote_fixture_is_never_the_loopback_target() -> None:
    assert not load_managed_target_profile(REMOTE_FIXTURE).is_loopback


def test_v2_revision_tracks_the_saved_target(tmp_path: Path) -> None:
    baseline = load_v2(tmp_path, name="a.json")

    assert load_v2(tmp_path, host="198.51.100.21", name="b.json").revision != baseline.revision
    document = json.loads(json.dumps(VALID_V2))
    document["port"] = 25566
    assert load_managed_target_profile(write(tmp_path, document, name="c.json")).revision != (
        baseline.revision
    )


def test_v2_profile_exports_a_single_address_policy(tmp_path: Path) -> None:
    profile = load_v2(tmp_path)
    policy = profile.address_policy()

    assert decide_endpoint(policy, profile.host, profile.port).allowed
    assert not decide_endpoint(policy, "198.51.100.21", profile.port).allowed
    assert not decide_endpoint(policy, "::ffff:c633:6414", profile.port).allowed


@pytest.mark.parametrize("host", ["localhost", "play.example.org", "mc.internal", "", " . "])
def test_v2_never_admits_a_resolvable_name(tmp_path: Path, host: str) -> None:
    with pytest.raises(MinekinError, match="host"):
        load_v2(tmp_path, host=host)


@pytest.mark.parametrize("host", ["198.51.100.020", "1.2.3", "::0:0", "2001:DB8::1"])
def test_v2_admits_only_the_normalized_literal(tmp_path: Path, host: str) -> None:
    with pytest.raises(MinekinError, match="host"):
        load_v2(tmp_path, host=host)


@pytest.mark.parametrize(
    "host", ["169.254.169.254", "fe80::1", "0.0.0.0", "::", "224.0.0.1", "ff02::1"]
)
def test_v2_cannot_pin_an_unconditionally_blocked_address(tmp_path: Path, host: str) -> None:
    with pytest.raises(MinekinError, match="address policy"):
        load_v2(tmp_path, host=host)


def test_a_loopback_literal_remains_savable_under_v2(tmp_path: Path) -> None:
    profile = load_v2(tmp_path, host="127.0.0.1")

    assert profile.is_loopback


@pytest.mark.parametrize("port", [0, 65536, -1, "25565", 25565.0, True, None])
def test_v2_port_rules_match_v1(tmp_path: Path, port: object) -> None:
    with pytest.raises(MinekinError, match="port"):
        load_v2(tmp_path, port=port)


def test_v2_online_mode_is_not_admissible(tmp_path: Path) -> None:
    with pytest.raises(MinekinError, match="online-mode"):
        load_v2(tmp_path, auth_mode="online")


@pytest.mark.parametrize(
    "policy",
    [
        {"mode": "probe_then_pin", "allowed_versions": ["1.20.1"]},
        {"mode": "explicit_allowlist", "allowed_versions": []},
        {"mode": "explicit_allowlist", "allowed_versions": "1.20.1"},
        {"mode": "explicit_allowlist", "allowed_versions": ["latest"]},
        {"mode": "explicit_allowlist", "allowed_versions": ["1.21.4-snapshot"]},
        {"mode": "explicit_allowlist", "allowed_versions": ["1.20.1", "1.20.1"]},
        {"mode": "explicit_allowlist"},
        {"allowed_versions": ["1.20.1"]},
        {"mode": "explicit_allowlist", "allowed_versions": ["1.20.1"], "prefer": "newest"},
        "explicit_allowlist",
    ],
)
def test_v2_version_policy_is_reviewed_too(tmp_path: Path, policy: object) -> None:
    with pytest.raises(MinekinError, match="version_policy"):
        load_v2(tmp_path, version_policy=policy)


@pytest.mark.parametrize(
    "authorization",
    [
        {"granted_by": "Operator", "basis": "explicitly approved by the operator"},
        {"granted_by": "operator-local"},
        {"granted_by": "operator-local", "basis": "ok"},
        {"granted_by": "operator-local", "basis": "approved", "expires": "never"},
        "trust me",
    ],
)
def test_v2_target_authorization_is_reviewed_too(tmp_path: Path, authorization: object) -> None:
    with pytest.raises(MinekinError, match=r"target_authorization|granted_by"):
        load_v2(tmp_path, target_authorization=authorization)


def test_v2_accepts_a_reviewed_pinned_bundle(tmp_path: Path) -> None:
    profile = load_v2(tmp_path, pinned_bundle_id="p0-core-1.20.1")

    assert profile.pinned_bundle_id == "p0-core-1.20.1"


@pytest.mark.parametrize("pinned", ["Pinned", "with space", 7, ""])
def test_v2_pinned_bundle_id_must_be_a_reference(tmp_path: Path, pinned: object) -> None:
    with pytest.raises(MinekinError, match="pinned_bundle_id"):
        load_v2(tmp_path, pinned_bundle_id=pinned)


def test_v2_rejects_unreviewed_and_missing_fields(tmp_path: Path) -> None:
    with pytest.raises(MinekinError, match="unreviewed fields"):
        load_v2(tmp_path, server_listing=[])
    with pytest.raises(MinekinError, match="unreviewed fields"):
        load_v2(tmp_path, visibility="isolated_test_only")
    stripped = {key: value for key, value in VALID_V2.items() if key != "target_authorization"}

    with pytest.raises(MinekinError, match="missing fields"):
        load_managed_target_profile(write(tmp_path, stripped))


@pytest.mark.parametrize("schema_version", [1, 3, "2", True])
def test_v2_is_bound_to_its_own_schema_revision(tmp_path: Path, schema_version: object) -> None:
    with pytest.raises(MinekinError, match="schema_version"):
        load_v2(tmp_path, schema_version=schema_version)


def test_the_v1_loader_never_accepts_a_v2_document(tmp_path: Path) -> None:
    path = write(tmp_path, VALID_V2)

    with pytest.raises(MinekinError):
        load_server_profile(path)


def test_the_v2_loader_never_accepts_the_v1_fixture(tmp_path: Path) -> None:
    with pytest.raises(MinekinError):
        load_managed_target_profile(FIXTURE)


def test_v2_inside_the_host_minecraft_directory_is_rejected(tmp_path: Path) -> None:
    nested = tmp_path / ".minecraft" / "profile.json"
    nested.parent.mkdir()
    nested.write_text(json.dumps(VALID_V2), encoding="utf-8")

    with pytest.raises(MinekinError, match="minecraft"):
        load_managed_target_profile(nested)


def test_v2_errors_are_admission_failures(tmp_path: Path) -> None:
    with pytest.raises(MinekinError) as raised:
        load_v2(tmp_path, host="localhost")

    assert raised.value.category is ErrorCategory.ADMISSION
    assert raised.value.exit_code == 17


def test_v2_evidence_document_round_trips(tmp_path: Path) -> None:
    profile = load_v2(tmp_path, pinned_bundle_id="p0-core-1.20.1")

    assert profile.as_document() == {
        **VALID_V2,
        "pinned_bundle_id": "p0-core-1.20.1",
        "revision": profile.revision,
    }


SESSION_V2: dict[str, object] = {**VALID_V2, "host": "127.0.0.1"}


def load_session_v2(tmp_path: Path, **overrides: object) -> object:
    return load_session_server_profile(
        write(tmp_path, {**SESSION_V2, **overrides}), minecraft_version="1.20.1"
    )


def test_a_matching_v1_document_loads_through_the_session_path(tmp_path: Path) -> None:
    write(tmp_path, VALID)

    profile = load_session_server_profile(FIXTURE, minecraft_version="1.21.4")

    assert isinstance(profile, ServerProfile)
    assert profile == load_server_profile(FIXTURE)
    assert profile.revision == load_server_profile(tmp_path / "profile.json").revision


def test_a_v1_document_pinned_to_another_version_is_not_a_session_target(tmp_path: Path) -> None:
    # The 1.20.1 run cannot borrow the 1.21.4 profile: the pinned constant stays
    # where V01 froze it, and the mismatch is what says no.
    with pytest.raises(MinekinError, match=r"pins 1\.21\.4"):
        load_session_server_profile(write(tmp_path, VALID), minecraft_version="1.20.1")


def test_a_loopback_v2_target_in_the_controlled_domain_loads(tmp_path: Path) -> None:
    profile = load_session_v2(tmp_path)

    assert isinstance(profile, ManagedTargetProfile)
    assert profile.is_loopback
    assert profile.allowed_versions == ("1.20.1",)
    assert profile == load_managed_target_profile(tmp_path / "profile.json")


@pytest.mark.parametrize("host", ["198.51.100.20", "10.0.0.5", "172.16.3.9"])
def test_every_saved_non_loopback_literal_stays_unjoinable(tmp_path: Path, host: str) -> None:
    with pytest.raises(MinekinError, match="loopback"):
        load_session_v2(tmp_path, host=host)


def test_a_version_policy_that_lists_several_versions_is_not_a_session_target(
    tmp_path: Path,
) -> None:
    with pytest.raises(MinekinError, match="exactly one version"):
        load_session_v2(
            tmp_path,
            version_policy={"mode": "explicit_allowlist", "allowed_versions": ["1.20.1", "1.21.4"]},
        )


def test_the_target_version_must_be_the_version_being_launched(tmp_path: Path) -> None:
    with pytest.raises(MinekinError, match=r"allows 1\.21\.4"):
        load_session_server_profile(
            write(
                tmp_path,
                {
                    **SESSION_V2,
                    "version_policy": {
                        "mode": "explicit_allowlist",
                        "allowed_versions": ["1.21.4"],
                    },
                },
            ),
            minecraft_version="1.20.1",
        )


def test_a_v2_document_still_meets_every_v2_loading_rule(tmp_path: Path) -> None:
    with pytest.raises(MinekinError, match="online-mode"):
        load_session_v2(tmp_path, auth_mode="online")


@pytest.mark.parametrize("schema_version", [0, 3, 1.0, "1"])
def test_an_unreviewed_schema_version_has_no_session_loader(
    tmp_path: Path, schema_version: object
) -> None:
    with pytest.raises(MinekinError):
        load_session_server_profile(
            write(tmp_path, {**VALID, "schema_version": schema_version}),
            minecraft_version="1.21.4",
        )


def test_a_session_profile_that_fails_to_load_is_still_an_admission_failure(
    tmp_path: Path,
) -> None:
    with pytest.raises(MinekinError) as caught:
        load_session_v2(tmp_path, host="198.51.100.20")

    assert caught.value.category is ErrorCategory.ADMISSION
