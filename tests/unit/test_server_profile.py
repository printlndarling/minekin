from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from minekin_core.adapters.launcher.server_profile import ServerProfile, load_server_profile
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
