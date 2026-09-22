"""The frozen, bounded offline session candidates and their argv encoding.

The candidate list is closed on purpose. A rejected launch must fail with a
classified error instead of permuting values until something is accepted, and a
placeholder that no candidate defines must never be replaced by an empty string
the way a generic launcher template engine would.

Option flags and their values stay separate argv elements. The offline
clientId/xuid case is the reason: parity with the reviewed Prism source chain is
`--clientId "" --xuid ""`, an explicit empty element after each option, not a
dropped option and not the literal `${clientid}` text.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability
from minekin_core.domain.offline_identity import OfflineIdentityMaterial
from minekin_core.domain.session_material import RecordedSessionMaterial

# Even though the offline sentinel is public, every authentication field is
# classified and redacted the same way so an online adapter cannot inherit a
# weaker log schema.
SECRET_CLASSIFICATION: Final[Mapping[str, str]] = MappingProxyType(
    {
        "access_token": "secret-shaped-nonsecret",
        "client_id": "secret-shaped-nonsecret",
        "xuid": "personal-identifier-shaped",
    }
)

EMPTY_ARGV: Final[str] = ""


def _reject(message: str) -> MinekinError:
    return MinekinError(
        "launcher.session", "resolve", ErrorCategory.SESSION, Retryability.OPERATOR_ACTION, message
    )


@dataclass(frozen=True, slots=True)
class SessionCandidate:
    """One reviewed offline session encoding from the bounded compatibility matrix."""

    candidate_id: str
    user_type_argv: str
    uuid_encoding: str
    access_token_argv: str
    client_id_argv: str
    xuid_argv: str

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError("candidate_id is required")
        if not self.user_type_argv:
            raise ValueError("user_type_argv is required; omit the candidate instead")
        if self.uuid_encoding not in {"id128", "canonical"}:
            raise ValueError("uuid_encoding must be 'id128' or 'canonical'")


# OFF-A: the reviewed Prism source chain. userType is the launcher's own word for
# this account and is not a Minecraft Session.AccountType constant.
PRISM_PARITY = SessionCandidate(
    candidate_id="prism-parity",
    user_type_argv="offline",
    uuid_encoding="id128",
    access_token_argv="0",
    client_id_argv=EMPTY_ARGV,
    xuid_argv=EMPTY_ARGV,
)

# OFF-B: identical materials, only userType moves to a name that exists in the
# client's own enum. A/B are compared; neither is a silent fallback for the other.
ENUM_ALIGNED = SessionCandidate(
    candidate_id="enum-aligned",
    user_type_argv="legacy",
    uuid_encoding="id128",
    access_token_argv="0",
    client_id_argv=EMPTY_ARGV,
    xuid_argv=EMPTY_ARGV,
)

OFFLINE_SESSION_CANDIDATES: Final[tuple[SessionCandidate, ...]] = (PRISM_PARITY, ENUM_ALIGNED)


def candidate_by_id(candidate_id: str | None) -> SessionCandidate:
    """The candidate an operator named, or the first one when they named none.

    Absent means the first — `prism-parity`, the candidate every session launched
    with before there was a way to choose — so a run that does not ask for one is
    the run it always was.

    An id matching nothing is refused rather than falling back, and the refusal
    names what it knows. Falling back is the failure this whole matrix exists to
    make visible: a run that asked for OFF-B and silently got OFF-A would produce
    a sealed bundle for a scenario that did not happen, and every check between
    here and that bundle would pass.
    """

    if candidate_id is None:
        return OFFLINE_SESSION_CANDIDATES[0]
    for candidate in OFFLINE_SESSION_CANDIDATES:
        if candidate.candidate_id == candidate_id:
            return candidate
    known = ", ".join(item.candidate_id for item in OFFLINE_SESSION_CANDIDATES)
    raise ValueError(f"unknown identity candidate {candidate_id!r}; known candidates: {known}")


# Placeholders whose value is allowed to be empty, and only when the candidate
# says so. Everything else must resolve to a non-empty argument.
EMPTY_CAPABLE_PLACEHOLDERS: Final[frozenset[str]] = frozenset({"clientid", "auth_xuid"})


@dataclass(frozen=True, slots=True)
class LiteralArgument:
    value: str


@dataclass(frozen=True, slots=True)
class PlaceholderArgument:
    name: str


Argument = LiteralArgument | PlaceholderArgument


def parse_game_argument_template(template: Sequence[Mapping[str, object]]) -> tuple[Argument, ...]:
    """Turn a launch plan's typed game argument template into validated entries."""

    parsed: list[Argument] = []
    for entry in template:
        kind = entry.get("kind")
        if kind == "literal":
            value = entry.get("value")
            if not isinstance(value, str) or not value:
                raise _reject("literal game argument must be a non-empty string")
            if "${" in value:
                raise _reject("literal game argument must not contain a placeholder")
            parsed.append(LiteralArgument(value))
        elif kind == "placeholder":
            name = entry.get("name")
            if not isinstance(name, str) or not name:
                raise _reject("placeholder game argument must name a placeholder")
            parsed.append(PlaceholderArgument(name))
        else:
            raise _reject("game argument template entry has an unknown kind")
    if not parsed:
        raise _reject("game argument template must not be empty")
    return tuple(parsed)


def session_argument_values(
    material: OfflineIdentityMaterial, candidate: SessionCandidate
) -> dict[str, str]:
    """The argv values a candidate supplies for one identity revision."""

    return {
        "auth_player_name": material.username,
        "auth_uuid": (
            material.uuid_id128 if candidate.uuid_encoding == "id128" else material.uuid_canonical
        ),
        "auth_access_token": candidate.access_token_argv,
        "user_type": candidate.user_type_argv,
        **_empty_capable_option_values(candidate),
    }


def _empty_capable_option_values(candidate: SessionCandidate) -> dict[str, str]:
    """The values of the two placeholders a candidate is allowed to leave empty."""

    return {
        "clientid": candidate.client_id_argv,
        "auth_xuid": candidate.xuid_argv,
    }


def resolve_game_arguments(
    template: Sequence[Argument],
    *,
    material: OfflineIdentityMaterial,
    candidate: SessionCandidate,
    environment: Mapping[str, str],
) -> list[str]:
    """Resolve the game argument template into concrete, independent argv elements.

    `environment` carries the non-session values (paths, version identity). It is
    deliberately not merged with the session values: an unresolved placeholder is
    an error, never an empty substitution.
    """

    values = dict(environment)
    values.update(session_argument_values(material, candidate))
    empty_environment = sorted(name for name, value in environment.items() if value == EMPTY_ARGV)
    if empty_environment:
        raise _reject(
            "game argument environment must not supply empty values: "
            + ", ".join(empty_environment)
        )

    arguments: list[str] = []
    for entry in template:
        if isinstance(entry, LiteralArgument):
            arguments.append(entry.value)
            continue
        if entry.name not in values:
            raise _reject(f"unresolved game argument placeholder {entry.name!r}")
        arguments.append(values[entry.name])

    if any("${" in argument for argument in arguments):
        raise _reject("resolved game argument still contains a literal placeholder")
    _verify_option_value_boundaries(template, arguments, candidate)
    return arguments


def _verify_option_value_boundaries(
    template: Sequence[Argument], arguments: Sequence[str], candidate: SessionCandidate
) -> None:
    """An empty value must stay an element of its own, attached to its option flag."""

    if len(arguments) != len(template):
        raise _reject("resolving game arguments changed the element count")

    option_values = _empty_capable_option_values(candidate)
    expected_empty = [
        index
        for index, entry in enumerate(template)
        if isinstance(entry, PlaceholderArgument)
        and entry.name in EMPTY_CAPABLE_PLACEHOLDERS
        and option_values[entry.name] == EMPTY_ARGV
    ]
    actual_empty = [index for index, argument in enumerate(arguments) if argument == EMPTY_ARGV]
    if actual_empty != expected_empty:
        raise _reject("empty argv elements do not match the candidate's declared empty options")

    for index in actual_empty:
        if index == 0:
            raise _reject("an empty argv value cannot be the first element")
        previous = template[index - 1]
        if not isinstance(previous, LiteralArgument) or not previous.value.startswith("-"):
            raise _reject("an empty argv value must remain attached to its own option flag")


_RECORDED_OPTIONS: Final[tuple[str, ...]] = ("--username", "--uuid", "--clientId", "--xuid")


def recorded_material(
    candidate: SessionCandidate, arguments: Sequence[str]
) -> RecordedSessionMaterial:
    """Read the identity material back out of a resolved argv.

    This reads what was actually encoded rather than re-deriving it from the
    candidate, so a bug that puts a value in the wrong argv slot is caught here
    instead of silently matching a hand-built record.
    """

    values: dict[str, str] = {}
    for option in _RECORDED_OPTIONS:
        positions = [index for index, argument in enumerate(arguments) if argument == option]
        if len(positions) != 1:
            raise _reject(f"resolved argv must carry exactly one {option} option")
        value_index = positions[0] + 1
        if value_index >= len(arguments):
            raise _reject(f"{option} has no value element in the resolved argv")
        values[option] = arguments[value_index]
    return RecordedSessionMaterial(
        identity_candidate_id=candidate.candidate_id,
        username=values["--username"],
        uuid_argv=values["--uuid"],
        client_id_present=values["--clientId"] != EMPTY_ARGV,
        xuid_present=values["--xuid"] != EMPTY_ARGV,
    )


def candidate_document(candidate: SessionCandidate) -> dict[str, object]:
    """Evidence view of a candidate: policy and presence, never a value."""

    return {
        "candidate_id": candidate.candidate_id,
        "user_type_argv": candidate.user_type_argv,
        "uuid_encoding": candidate.uuid_encoding,
        "access_token_argv_present": candidate.access_token_argv != EMPTY_ARGV,
        "client_id_argv_present": candidate.client_id_argv != EMPTY_ARGV,
        "xuid_argv_present": candidate.xuid_argv != EMPTY_ARGV,
        "credential_values_exposed": False,
        "secret_classification": dict(SECRET_CLASSIFICATION),
    }
