from dataclasses import FrozenInstanceError

import pytest

from minekin_core.domain.auth_policy import AuthPolicy


def test_default_policy_is_offline_and_contains_no_credentials() -> None:
    policy = AuthPolicy()

    assert policy.as_event_payload() == {
        "auth_mode": "offline",
        "online_adapter_enabled": False,
        "server_profile_id": None,
        "server_profile_revision": None,
    }
    policy.require_offline_launch()


def test_target_policy_binds_a_reviewed_profile_without_allowing_rebinding() -> None:
    policy = AuthPolicy.from_profile(profile_id="p0-controlled", revision="ab" * 32)

    assert policy.as_event_payload()["server_profile_revision"] == "ab" * 32
    with pytest.raises(FrozenInstanceError):
        policy.server_profile_id = "another-profile"  # type: ignore[misc]


@pytest.mark.parametrize(
    "changes",
    [
        {"auth_mode": "microsoft"},
        {"online_adapter_enabled": True},
        {"server_profile_id": "p0-controlled"},
        {"server_profile_revision": "ab" * 32},
        {"server_profile_id": "", "server_profile_revision": "ab" * 32},
        {"server_profile_id": "p0-controlled", "server_profile_revision": "not-a-digest"},
    ],
)
def test_p0_refuses_unreviewed_or_unpaired_policy(changes: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        AuthPolicy(**changes)  # type: ignore[arg-type]
