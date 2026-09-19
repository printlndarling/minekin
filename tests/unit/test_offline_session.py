from __future__ import annotations

import json
from pathlib import Path

import pytest

from minekin_core.adapters.launcher.launch_plan import (
    build_launch_plan,
    game_environment,
)
from minekin_core.adapters.launcher.offline_session import (
    OFFLINE_SESSION_CANDIDATES,
    SECRET_CLASSIFICATION,
    LiteralArgument,
    PlaceholderArgument,
    SessionCandidate,
    candidate_document,
    parse_game_argument_template,
    resolve_game_arguments,
    session_argument_values,
)
from minekin_core.domain.errors import ErrorCategory, MinekinError
from minekin_core.domain.ids import OpaqueId
from minekin_core.domain.offline_identity import OfflineIdentityMaterial

PROFILE = Path(__file__).resolve().parents[1] / "fixtures/runtime-input/bundle-p0-core-1.21.4.json"
OFF_A, OFF_B = OFFLINE_SESSION_CANDIDATES


def material(username: str = "Kin") -> OfflineIdentityMaterial:
    return OfflineIdentityMaterial(
        local_profile_id=OpaqueId("kin-01"),
        identity_revision=1,
        username=username,
        created_at="2026-09-19T00:00:00Z",
    )


def template() -> tuple[LiteralArgument | PlaceholderArgument, ...]:
    plan = build_launch_plan(PROFILE)
    return parse_game_argument_template(plan["runtime"]["game_arg_template"])


def arguments(candidate: SessionCandidate = OFF_A) -> list[str]:
    plan = build_launch_plan(PROFILE)
    return resolve_game_arguments(
        parse_game_argument_template(plan["runtime"]["game_arg_template"]),
        material=material(),
        candidate=candidate,
        environment=game_environment(plan),
    )


def test_the_offline_candidate_matrix_is_exactly_off_a_and_off_b() -> None:
    assert [candidate.candidate_id for candidate in OFFLINE_SESSION_CANDIDATES] == [
        "prism-parity",
        "enum-aligned",
    ]
    assert [candidate.user_type_argv for candidate in OFFLINE_SESSION_CANDIDATES] == [
        "offline",
        "legacy",
    ]


def test_off_b_changes_only_the_user_type() -> None:
    first, second = OFFLINE_SESSION_CANDIDATES

    assert (first.candidate_id, second.candidate_id) == ("prism-parity", "enum-aligned")
    assert (first.user_type_argv, second.user_type_argv) == ("offline", "legacy")
    for field in ("uuid_encoding", "access_token_argv", "client_id_argv", "xuid_argv"):
        assert getattr(first, field) == getattr(second, field), field


def test_frozen_candidates_use_the_public_token_and_explicit_empty_options() -> None:
    for candidate in OFFLINE_SESSION_CANDIDATES:
        assert candidate.access_token_argv == "0"
        assert candidate.uuid_encoding == "id128"
        assert candidate.client_id_argv == ""
        assert candidate.xuid_argv == ""


def test_session_values_are_bound_to_one_identity_revision() -> None:
    values = session_argument_values(material(), OFF_A)

    assert values["auth_player_name"] == "Kin"
    assert values["auth_uuid"] == "8f40376bc23f3ef1b5535564eea75639"
    assert values["user_type"] == "offline"
    assert values["auth_access_token"] == "0"
    assert values["clientid"] == ""
    assert values["auth_xuid"] == ""


def test_canonical_uuid_encoding_is_available_for_the_off_c_comparison() -> None:
    canonical = SessionCandidate(
        candidate_id="uuid-form",
        user_type_argv="offline",
        uuid_encoding="canonical",
        access_token_argv="0",
        client_id_argv="",
        xuid_argv="",
    )

    assert (
        session_argument_values(material(), canonical)["auth_uuid"]
        == "8f40376b-c23f-3ef1-b553-5564eea75639"
    )


def test_offline_argv_keeps_the_empty_client_credentials_as_their_own_elements() -> None:
    argv = arguments()

    assert argv[argv.index("--clientId") + 1] == ""
    assert argv[argv.index("--xuid") + 1] == ""
    # The empty elements must not swallow the following flag.
    assert argv[argv.index("--xuid") + 2] == "--userType"
    assert argv[argv.index("--userType") + 1] == "offline"
    assert argv[argv.index("--accessToken") + 1] == "0"


def test_no_argument_survives_as_a_literal_placeholder() -> None:
    argv = arguments()

    assert not [argument for argument in argv if "${" in argument]
    assert len(argv) == len(template())


@pytest.mark.parametrize("candidate", OFFLINE_SESSION_CANDIDATES, ids=lambda c: c.candidate_id)
def test_every_frozen_candidate_resolves_the_full_reviewed_template(
    candidate: SessionCandidate,
) -> None:
    argv = arguments(candidate)

    assert argv[0] == "--username"
    assert argv[1] == "Kin"
    assert argv[-2:] == ["--versionType", "release"]


def test_an_empty_environment_value_is_refused_before_it_reaches_argv() -> None:
    entries = (LiteralArgument("--gameDir"), PlaceholderArgument("game_directory"))

    with pytest.raises(MinekinError, match="must not supply empty values"):
        resolve_game_arguments(
            entries, material=material(), candidate=OFF_A, environment={"game_directory": ""}
        )


def test_an_unknown_placeholder_is_rejected_rather_than_emptied() -> None:
    entries = (LiteralArgument("--server"), PlaceholderArgument("server_address"))

    with pytest.raises(MinekinError, match="unresolved game argument placeholder"):
        resolve_game_arguments(
            entries, material=material(), candidate=OFF_A, environment={"version_name": "1.21.4"}
        )


def test_an_empty_value_must_stay_attached_to_an_option_flag() -> None:
    entries = (LiteralArgument("--clientId"), PlaceholderArgument("clientid"))
    assert resolve_game_arguments(
        entries, material=material(), candidate=OFF_A, environment={}
    ) == ["--clientId", ""]

    detached = (LiteralArgument("Kin"), PlaceholderArgument("clientid"))
    with pytest.raises(MinekinError, match="attached to its own option flag"):
        resolve_game_arguments(detached, material=material(), candidate=OFF_A, environment={})


def test_a_template_entry_that_is_not_typed_is_rejected() -> None:
    with pytest.raises(MinekinError, match="unknown kind"):
        parse_game_argument_template([{"kind": "computed"}])
    with pytest.raises(MinekinError, match="must not contain a placeholder"):
        parse_game_argument_template([{"kind": "literal", "value": "--server ${host}"}])


def test_candidate_document_reports_presence_without_values() -> None:
    document = candidate_document(OFF_A)

    assert document == {
        "candidate_id": "prism-parity",
        "user_type_argv": "offline",
        "uuid_encoding": "id128",
        "access_token_argv_present": True,
        "client_id_argv_present": False,
        "xuid_argv_present": False,
        "credential_values_exposed": False,
        "secret_classification": dict(SECRET_CLASSIFICATION),
    }
    # The sentinel is a credential-shaped value and must not survive into evidence.
    assert OFF_A.access_token_argv not in json.dumps(document)


def test_game_environment_carries_only_paths_and_version_identity() -> None:
    plan = build_launch_plan(PROFILE)
    environment = game_environment(plan)

    assert environment == {
        "version_name": "1.21.4",
        "version_type": "release",
        "game_directory": "session/",
        "assets_root": "bundle/assets",
        "assets_index_name": "19",
    }
    assert not [name for name in environment if "token" in name or "player" in name]


def test_session_errors_are_classified_as_session_failures() -> None:
    with pytest.raises(MinekinError) as raised:
        resolve_game_arguments(
            (PlaceholderArgument("auth_xuid"),),
            material=material(),
            candidate=OFF_A,
            environment={},
        )

    assert raised.value.category is ErrorCategory.SESSION
    assert raised.value.exit_code == 16
