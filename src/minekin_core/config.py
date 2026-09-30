"""Frozen P0 runtime requirements and operator-supplied locations.

Nothing here creates anything. Reading the environment is how the operator states
where data lives. A new offline Kin defaults to the stable name `minekin`;
existing identities are read from their persisted ledger, not regenerated here.
"""

from __future__ import annotations

import os
import re
import shutil
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from pathlib import Path

from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability
from minekin_core.domain.offline_identity import is_valid_username

DATA_ROOT_VARIABLE = "MINEKIN_HOME"
USERNAME_VARIABLE = "MINEKIN_USERNAME"
DEFAULT_USERNAME = "minekin"
JAVA_VARIABLE = "MINEKIN_JAVA"
KIN_VARIABLE = "MINEKIN_KIN_ID"
PERSONA_SEED_VARIABLE = "MINEKIN_PERSONA_SEED"
LOCAL_ENV_FILE_NAME = ".env"
LOCAL_ENV_FILE_VARIABLE = "MINEKIN_ENV_FILE"

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
    """The initial name for a new Kin; never a rename of a persisted identity."""

    source = os.environ if environ is None else environ
    value = source.get(USERNAME_VARIABLE, DEFAULT_USERNAME)
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


def configured_persona_seed(environ: Mapping[str, str] | None = None) -> str | None:
    """The seed the operator states for a new Kin's persona, or none at all.

    Absent is not a mistake: `init` then draws one and persists it, so the person
    the Kin got is still reproducible afterwards. A name that is present but empty
    is a stated seed nobody filled in, and drawing a different one would quietly
    answer a request the operator did not make.
    """

    source = os.environ if environ is None else environ
    if PERSONA_SEED_VARIABLE not in source:
        return None
    value = source[PERSONA_SEED_VARIABLE]
    if not value.strip():
        raise _reject(f"{PERSONA_SEED_VARIABLE} is set but empty; unset it to let init draw one")
    return value


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


LOCAL_ENV_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def parse_local_environment(text: str) -> dict[str, str]:
    """Read a `.env` body into names and values.

    A line that is blank, a comment, or carries no `=` is not a variable, so a
    half-typed line cannot set a name nobody typed. Surrounding quotes are the
    file's delimiters rather than part of the value, because the values this file
    holds are URLs and keys that an operator pastes with quotes around them.
    """

    parsed: dict[str, str] = {}
    for line in text.splitlines():
        entry = line.strip()
        if not entry or entry.startswith("#"):
            continue
        if entry.startswith("export "):
            entry = entry[len("export ") :].strip()
        name, separator, value = entry.partition("=")
        if not separator:
            continue
        name = name.strip()
        if not LOCAL_ENV_NAME_PATTERN.match(name):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        parsed[name] = value
    return parsed


def local_environment_path(
    environ: Mapping[str, str] | None = None, cwd: Path | None = None
) -> Path:
    """Which file carries the operator's names: the one they point at, else `./.env`."""

    source = os.environ if environ is None else environ
    explicit = source.get(LOCAL_ENV_FILE_VARIABLE, "").strip()
    if explicit:
        return Path(explicit)
    return (Path.cwd() if cwd is None else cwd) / LOCAL_ENV_FILE_NAME


def load_local_environment(
    environ: MutableMapping[str, str] | None = None, cwd: Path | None = None
) -> tuple[str, ...]:
    """Put the file's names into the environment, and say which ones went in.

    This is the one place a file is allowed to speak for the environment, and it is
    called at the process boundary rather than from a reader: the environment stays
    the interface every other module sees. A name the operator already exported
    outranks the file, since the shell's own statement was made later and on
    purpose. Only the names are returned — a value that came back from this
    function is a value that can end up in a log.
    """

    source = os.environ if environ is None else environ
    path = local_environment_path(environ=source, cwd=cwd)
    if not path.is_file():
        return ()
    loaded: tuple[str, ...] = ()
    for name, value in parse_local_environment(path.read_text(encoding="utf-8")).items():
        if name in source:
            continue
        source[name] = value
        loaded = (*loaded, name)
    return loaded


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
