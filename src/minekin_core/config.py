"""Frozen P0 runtime requirements and operator-supplied locations.

Nothing here creates anything. Reading the environment is how the operator states
where data lives and which name a Kin plays under; see
`docs/run-directory-proposal.md` for why those two have no defaults.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability
from minekin_core.domain.offline_identity import is_valid_username

DATA_ROOT_VARIABLE = "MINEKIN_HOME"
USERNAME_VARIABLE = "MINEKIN_USERNAME"
JAVA_VARIABLE = "MINEKIN_JAVA"
KIN_VARIABLE = "MINEKIN_KIN_ID"

# The host facts a managed client is allowed to observe. This is a list in the
# code rather than an operator-supplied list on purpose: a forwarded value comes
# from the operator's host, so letting the operator name the names would hand
# them the one reviewable door — `LD_PRELOAD` arrives through it as readily as a
# display does.
#
# `DISPLAY` and `XAUTHORITY` are the two halves of one fact: where the display
# is, and the credential that may use it. The second is not optional. A virtual
# display started by `xvfb-run` authenticates its clients with a cookie file,
# and the client's own `HOME` is redirected into its session — so with only
# `DISPLAY` forwarded, GLFW is refused by the X server and says something that
# does not mention authentication at all: "Failed to initialize GLFW, errors:
# GLFW error during init: [0x1000E] Failed to detect any supported platform".
#
# The last name is a different kind of thing from the first two, and it is here
# because this list is the only channel that reaches the client JVM: it is not a
# fact about the host but a request the operator makes for one run, asking the
# Bridge to report this generation's first snapshot with `authoritative=false` so
# that Core's own filter has something to refuse (`ADMIT-070`). Core neither reads
# nor acts on its value — it only lends the name — and a build with the variable
# absent behaves exactly as it did before. The Bridge reads it, says so in its own
# log, and the alternative (a new command on the wire to ask the client to lie
# about itself) is a permanent protocol surface standing in for a diagnostic.
BRIDGE_NON_AUTHORITATIVE_FIRST_SNAPSHOT_VARIABLE: str = (
    "MINEKIN_BRIDGE_NON_AUTHORITATIVE_FIRST_SNAPSHOT"
)

FORWARDED_VARIABLES: tuple[str, ...] = (
    "DISPLAY",
    "XAUTHORITY",
    BRIDGE_NON_AUTHORITATIVE_FIRST_SNAPSHOT_VARIABLE,
)


def _reject(message: str) -> MinekinError:
    return MinekinError(
        "config", "resolve", ErrorCategory.CONFIG, Retryability.OPERATOR_ACTION, message
    )


def data_root(environ: Mapping[str, str] | None = None) -> Path:
    """The operator's data root, which deliberately has no default.

    A default would create directories under someone's home directory because
    they ran a command, rather than because they said where data belongs.
    """

    source = os.environ if environ is None else environ
    raw = source.get(DATA_ROOT_VARIABLE, "")
    if not raw.strip():
        raise _reject(f"{DATA_ROOT_VARIABLE} is required and has no default")
    path = Path(raw)
    # Checked before resolving, which would otherwise make it absolute against
    # the current directory and hide the mistake.
    if not path.is_absolute():
        raise _reject(f"{DATA_ROOT_VARIABLE} must be an absolute path")
    return path.resolve()


def configured_username(environ: Mapping[str, str] | None = None) -> str:
    """The name this Kin plays under, as stated by the operator."""

    source = os.environ if environ is None else environ
    value = source.get(USERNAME_VARIABLE, "")
    if not value.strip():
        raise _reject(f"{USERNAME_VARIABLE} is required and has no default")
    if not is_valid_username(value):
        raise _reject(
            f"{USERNAME_VARIABLE} must follow the vanilla 3-16 [A-Za-z0-9_] rule: {value!r}"
        )
    return value


def kin_selector(environ: Mapping[str, str] | None = None) -> str | None:
    """An explicit Kin choice, needed only when the root holds more than one."""

    source = os.environ if environ is None else environ
    value = source.get(KIN_VARIABLE, "").strip()
    return value or None


def forwarded_environment(environ: Mapping[str, str] | None = None) -> dict[str, str]:
    """The named host facts that are present, for the client to be given.

    `DISPLAY` is here because a virtual display is a fact about the host and not
    about the session: the client renders where the *operator* put the display,
    and nothing inside a session overlay can answer which one that is. A
    variable that is unset, or set to nothing, is simply absent — the client then
    has no display, which is also a fact about the host rather than something to
    invent a value for. `XAUTHORITY` is the same fact continued: the name of the
    file holding the credential for that display.
    """

    source = os.environ if environ is None else environ
    forwarded: dict[str, str] = {}
    for name in FORWARDED_VARIABLES:
        value = source.get(name)
        if value is not None and value.strip():
            forwarded[name] = value
    return forwarded


def java_executable(environ: Mapping[str, str] | None = None) -> Path:
    """Where Java lives: named by the operator, otherwise found on `PATH`."""

    source = os.environ if environ is None else environ
    explicit = source.get(JAVA_VARIABLE, "").strip()
    if explicit:
        path = Path(explicit)
        if not path.is_absolute():
            raise _reject(f"{JAVA_VARIABLE} must be an absolute path")
        if not path.is_file():
            raise _reject(f"{JAVA_VARIABLE} names a file that does not exist: {path}")
        return path
    found = shutil.which("java")
    if found is None:
        raise _reject(f"java was not found on PATH; set {JAVA_VARIABLE} to name one")
    return Path(found)


@dataclass(frozen=True, slots=True)
class RuntimeRequirements:
    """Versions that a Minekin P0 host must provide.

    This is deliberately configuration data rather than environment discovery.
    In particular, importing this module never creates a run directory or invokes
    a package manager.
    """

    python_min: tuple[int, int] = (3, 12)
    python_max_exclusive: tuple[int, int] = (3, 14)
    java_major: int = 21
    protobuf_distribution: str = "protobuf"
    # The checked-in gencode calls ValidateProtobufRuntimeVersion(6, 31, 1), so a
    # host below that floor fails at import rather than at a check. Keep this in
    # step with the pyproject floor and the generated modules.
    protobuf_min: tuple[int, int] = (6, 31)
    protobuf_max_exclusive: tuple[int, int] = (7, 0)

    def supports_python(self, version: tuple[int, int]) -> bool:
        return self.python_min <= version < self.python_max_exclusive

    def supports_protobuf(self, version: tuple[int, int]) -> bool:
        return self.protobuf_min <= version < self.protobuf_max_exclusive


P0_REQUIREMENTS = RuntimeRequirements()
