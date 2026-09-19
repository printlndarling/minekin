"""Materialising the reviewed launch plan into a real command line.

The plan deliberately holds relative paths, because the roots are chosen per run
while the plan must stay identical across runs. This module is the one place that
turns them into absolute paths, so "which directory did this actually point at"
has a single answer. There are two roots: the run root holds the immutable store
and the read-only bundle, and `session/` names the writable overlay for one
session generation.

Nothing here spawns anything. A process that starts and then misbehaves is much
harder to diagnose than an argv that is wrong before it starts, so the assembly
is a pure function of the plan, the root and the frozen session material.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from minekin_core.adapters.launcher.launch_plan import SESSION_PREFIX, game_environment
from minekin_core.adapters.launcher.offline_session import (
    SessionCandidate,
    parse_game_argument_template,
    resolve_game_arguments,
)
from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability
from minekin_core.domain.offline_identity import OfflineIdentityMaterial

# Plan paths name one of two roots. The immutable store and the read-only bundle
# live under the run root; `session/` names the writable overlay for one session
# generation, which the contract also makes the client's game directory.
RUN_ROOT_PREFIXES: tuple[str, ...] = ("artifact-store/", "bundle/")
PLAN_PATH_PREFIXES: tuple[str, ...] = (*RUN_ROOT_PREFIXES, SESSION_PREFIX)

# The game arguments that name a directory rather than a value.
ENVIRONMENT_PATH_KEYS: frozenset[str] = frozenset({"game_directory", "assets_root"})

# The one variable the Bridge reads at client start to find its bootstrap
# descriptor. The Java side names it in MinekinBridgeClient; the two spellings
# are pinned together in tests/contract/test_bridge_java_constants.py, because a
# rename on either side is invisible until a real client refuses to start.
BRIDGE_DESCRIPTOR_VARIABLE: str = "MINEKIN_BRIDGE_DESCRIPTOR"

_PATH_ARGUMENT = re.compile(r"^(?P<key>-[A-Za-z0-9_.]+)=(?P<value>.*)$")
_HOST_MINECRAFT = ".minecraft"


def _reject(message: str) -> MinekinError:
    return MinekinError(
        "launcher.process", "build", ErrorCategory.CONFIG, Retryability.OPERATOR_ACTION, message
    )


@dataclass(frozen=True, slots=True)
class ClientProcessSpec:
    """Exactly what to invoke, where, and with which environment."""

    argv: tuple[str, ...]
    working_directory: Path
    java_executable: Path
    run_root: Path
    main_class: str
    environment: Mapping[str, str]
    session_directories: tuple[Path, ...] = ()

    def as_document(self) -> dict[str, object]:
        return {
            "java_executable": str(self.java_executable),
            "working_directory": str(self.working_directory),
            "run_root": str(self.run_root),
            "main_class": self.main_class,
            "argv_length": len(self.argv),
            "argv_digest": argument_digest(self.argv),
            "environment_names": sorted(self.environment),
        }


def argument_digest(argv: tuple[str, ...]) -> str:
    """A stable digest of the command line, for evidence rather than for replay."""

    # NUL-joined: an argument cannot contain NUL, so no two argv lists collide.
    return hashlib.sha256("\0".join(argv).encode("utf-8", errors="surrogatepass")).hexdigest()


# User-level locations are redirected into the session rather than inherited. A
# client that inherits the operator's HOME can still reach their files, which is
# exactly the boundary the managed run directory exists to hold.
_SESSION_DIRECTORIES: tuple[tuple[str, str], ...] = (
    ("HOME", ""),
    ("XDG_DATA_HOME", "xdg-data"),
    ("XDG_CONFIG_HOME", "xdg-config"),
    ("XDG_CACHE_HOME", "xdg-cache"),
    ("TMPDIR", "tmp"),
    ("TEMP", "tmp"),
    ("TMP", "tmp"),
)


def session_redirects(working_directory: Path) -> tuple[tuple[str, Path], ...]:
    """The redirected variable names and the session directories they point at.

    The directories have to exist before the client starts: a process handed a
    `TMPDIR` that is not there warns and can fail to make its own temporary files.
    """

    # The working directory is the session overlay, so the redirected variables
    # point inside it rather than at a directory beside it.
    return tuple(
        (name, working_directory / suffix if suffix else working_directory)
        for name, suffix in _SESSION_DIRECTORIES
    )


def redirect_targets(working_directory: Path) -> tuple[Path, ...]:
    return tuple(target for _, target in session_redirects(working_directory))


def client_environment(
    working_directory: Path,
    *,
    forward: Mapping[str, str] | None = None,
    bridge_descriptor: Path | None = None,
) -> dict[str, str]:
    """The environment the client is given, and nothing it is not.

    Nothing is inherited implicitly. Anything the operator's host must supply —
    `DISPLAY` for a virtual display, typically — is named explicitly, so the set
    of host facts a managed client can observe is a reviewable list.

    `bridge_descriptor` is the second kind of entry and is deliberately not part
    of `forward`: forwarded values come from the operator's host, while this one
    is created by Core for this session and must never be supplied by the host.
    """

    environment = {name: str(target) for name, target in session_redirects(working_directory)}
    for name, value in (forward or {}).items():
        if name in environment:
            raise _reject(f"{name} cannot be forwarded; it is already redirected into the session")
        if name == BRIDGE_DESCRIPTOR_VARIABLE:
            # The descriptor carries the session key. A host-supplied value would
            # point the Bridge at a file the operator controls, and with no
            # descriptor of our own this variable would otherwise arrive through
            # the forward list alone.
            raise _reject(
                f"{name} cannot be forwarded; only Core names the bridge bootstrap descriptor"
            )
        if _mentions_host_minecraft(value):
            raise _reject(f"forwarded {name} names the host .minecraft directory")
        environment[name] = value
    if bridge_descriptor is not None:
        if not bridge_descriptor.is_absolute():
            raise _reject("the bridge descriptor path must be absolute")
        if _mentions_host_minecraft(str(bridge_descriptor)):
            raise _reject("the bridge descriptor path names the host .minecraft directory")
        environment[BRIDGE_DESCRIPTOR_VARIABLE] = str(bridge_descriptor)
    return environment


def build_process_spec(
    plan: Mapping[str, Any],
    *,
    run_root: Path,
    overlay: Path,
    material: OfflineIdentityMaterial,
    candidate: SessionCandidate,
    java_executable: Path,
    forward_environment: Mapping[str, str] | None = None,
    bridge_descriptor: Path | None = None,
) -> ClientProcessSpec:
    """Assemble the full command line for one offline managed-client launch."""

    # Checked before resolving: `resolve()` would turn a relative root into an
    # absolute one against the current directory, which is the silent
    # wrong-location failure this whole module exists to prevent.
    if not run_root.is_absolute():
        raise _reject("the run root must be an absolute path")
    if not overlay.is_absolute():
        raise _reject("the session overlay must be an absolute path")
    root = run_root.resolve()
    session = overlay.resolve()

    runtime = _section(plan, "runtime")
    bundle = _section(plan, "bundle")

    jvm_args = _resolved_jvm_args(runtime, root, session)
    main_class = bundle.get("main_class")
    if not isinstance(main_class, str) or not main_class:
        raise _reject("launch plan has no main class")

    environment = game_environment(plan)
    resolved_environment = {
        name: (str(_resolve(root, session, value)) if name in ENVIRONMENT_PATH_KEYS else value)
        for name, value in environment.items()
    }
    template = parse_game_argument_template(
        cast(list[Mapping[str, object]], runtime["game_arg_template"])
    )
    game_args = resolve_game_arguments(
        template, material=material, candidate=candidate, environment=resolved_environment
    )

    argv = (*jvm_args, main_class, *game_args)
    _require_materialised(argv)
    working_directory = _resolve(root, session, environment["game_directory"])
    return ClientProcessSpec(
        argv=argv,
        working_directory=working_directory,
        java_executable=java_executable,
        run_root=root,
        main_class=main_class,
        environment=client_environment(
            working_directory, forward=forward_environment, bridge_descriptor=bridge_descriptor
        ),
        session_directories=redirect_targets(working_directory),
    )


def _section(plan: Mapping[str, Any], key: str) -> dict[str, Any]:
    value = plan.get(key)
    if not isinstance(value, dict):
        raise _reject(f"launch plan is missing its {key} section")
    return cast(dict[str, Any], value)


def _mentions_host_minecraft(argument: str) -> bool:
    """True only when `.minecraft` is a path segment.

    A substring test would fire on `net.minecraft.client.main.Main`, which is a
    class name rather than a directory, so the rule has to be about segments.
    """

    return any(segment.casefold() == _HOST_MINECRAFT for segment in re.split(r"[\\/]", argument))


def _resolve(run_root: Path, overlay: Path, value: str) -> Path:
    """Turn one plan-relative path into the absolute path it names.

    Two roots, not one: `session/` is the writable overlay for this generation
    and everything else is inside the read-only run root. Keeping them apart is
    what makes the overlay actually isolated — resolving `session/game` against
    the run root, as this used to, put the client in a directory shared by every
    session and every generation of the same Kin.
    """

    if Path(value).is_absolute() or _mentions_host_minecraft(value):
        raise _reject(f"plan path {value!r} is not a plan-relative path")
    if not value.startswith(PLAN_PATH_PREFIXES):
        raise _reject(f"plan path {value!r} is outside the reviewed plan path roots")
    if value.startswith(SESSION_PREFIX):
        return (overlay / value[len(SESSION_PREFIX) :]).resolve()
    return (run_root / value).resolve()


def _string_list(runtime: Mapping[str, Any], key: str) -> list[str]:
    value = runtime.get(key)
    if not isinstance(value, list):
        raise _reject(f"launch plan {key} must be a list of strings")
    items = cast(list[object], value)
    if not all(isinstance(item, str) for item in items):
        raise _reject(f"launch plan {key} must be a list of strings")
    return [cast(str, item) for item in items]


def _resolved_jvm_args(runtime: Mapping[str, Any], run_root: Path, overlay: Path) -> list[str]:
    arguments = _string_list(runtime, "jvm_args")
    classpath = _string_list(runtime, "classpath")

    resolved: list[str] = []
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument == "-cp":
            # The classpath is one joined element; rebuild it entry by entry so
            # each entry is resolved rather than the joined string is rewritten.
            if index + 1 >= len(arguments):
                raise _reject("launch plan has a -cp option with no classpath element")
            if arguments[index + 1].startswith("-"):
                # Treating the next option as the classpath would silently drop it.
                raise _reject("launch plan has a -cp option that is not followed by a classpath")
            separator = ":"  # The plan only accepts a linux-x86_64 target.
            joined = separator.join(str(_resolve(run_root, overlay, entry)) for entry in classpath)
            resolved.extend(["-cp", joined])
            index += 2
            continue
        match = _PATH_ARGUMENT.match(argument)
        if match is not None and match.group("value").startswith(PLAN_PATH_PREFIXES):
            resolved.append(
                f"{match.group('key')}={_resolve(run_root, overlay, match.group('value'))}"
            )
        else:
            resolved.append(argument)
        index += 1
    return resolved


def _require_materialised(argv: tuple[str, ...]) -> None:
    """Refuse a command line that still carries a relative plan path.

    A relative path would resolve against the child process's working directory,
    which is the session overlay, not either of the roots the plan paths name, so
    it would silently point at the wrong place instead of failing.
    """

    for argument in argv:
        if argument.startswith(PLAN_PATH_PREFIXES):
            raise _reject(f"argument {argument!r} was left as a plan-relative path")
        if _mentions_host_minecraft(argument):
            raise _reject(f"argument {argument!r} refers to the host .minecraft directory")
