"""Materialising the reviewed launch plan into a real command line.

The plan deliberately holds run-root-relative paths, because the run root is
chosen per run while the plan must stay identical across runs. This module is the
one place that turns them into absolute paths, so "which directory did this
actually point at" has a single answer.

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

from minekin_core.adapters.launcher.launch_plan import game_environment
from minekin_core.adapters.launcher.offline_session import (
    SessionCandidate,
    parse_game_argument_template,
    resolve_game_arguments,
)
from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability
from minekin_core.domain.offline_identity import OfflineIdentityMaterial

# Prefixes the plan uses for its run-root-relative paths. Anything starting with
# one of these is resolved against the run root; anything else passes through.
RUN_ROOT_PREFIXES: tuple[str, ...] = ("artifact-store/", "bundle/", "session/")

# The game arguments that name a directory rather than a value.
ENVIRONMENT_PATH_KEYS: frozenset[str] = frozenset({"game_directory", "assets_root"})

_PATH_ARGUMENT = re.compile(r"^(?P<key>-[A-Za-z0-9_.]+)=(?P<value>.*)$")
_HOST_MINECRAFT = ".minecraft"


def _reject(message: str) -> MinekinError:
    return MinekinError(
        "launcher.process", "build", ErrorCategory.CONFIG, Retryability.OPERATOR_ACTION, message
    )


@dataclass(frozen=True, slots=True)
class ClientProcessSpec:
    """Exactly what to invoke, and where, for one managed client."""

    argv: tuple[str, ...]
    working_directory: Path
    java_executable: Path
    run_root: Path
    main_class: str

    def as_document(self) -> dict[str, object]:
        return {
            "java_executable": str(self.java_executable),
            "working_directory": str(self.working_directory),
            "run_root": str(self.run_root),
            "main_class": self.main_class,
            "argv_length": len(self.argv),
            "argv_digest": argument_digest(self.argv),
        }


def argument_digest(argv: tuple[str, ...]) -> str:
    """A stable digest of the command line, for evidence rather than for replay."""

    # NUL-joined: an argument cannot contain NUL, so no two argv lists collide.
    return hashlib.sha256("\0".join(argv).encode("utf-8", errors="surrogatepass")).hexdigest()


def build_process_spec(
    plan: Mapping[str, Any],
    *,
    run_root: Path,
    material: OfflineIdentityMaterial,
    candidate: SessionCandidate,
    java_executable: Path,
) -> ClientProcessSpec:
    """Assemble the full command line for one offline managed-client launch."""

    # Checked before resolving: `resolve()` would turn a relative root into an
    # absolute one against the current directory, which is the silent
    # wrong-location failure this whole module exists to prevent.
    if not run_root.is_absolute():
        raise _reject("the run root must be an absolute path")
    root = run_root.resolve()

    runtime = _section(plan, "runtime")
    bundle = _section(plan, "bundle")

    jvm_args = _resolved_jvm_args(runtime, root)
    main_class = bundle.get("main_class")
    if not isinstance(main_class, str) or not main_class:
        raise _reject("launch plan has no main class")

    environment = game_environment(plan)
    resolved_environment = {
        name: (str(_resolve(root, value)) if name in ENVIRONMENT_PATH_KEYS else value)
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
    return ClientProcessSpec(
        argv=argv,
        working_directory=_resolve(root, environment["game_directory"]),
        java_executable=java_executable,
        run_root=root,
        main_class=main_class,
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


def _resolve(root: Path, value: str) -> Path:
    """Turn one plan-relative path into an absolute path inside the run root."""

    if Path(value).is_absolute() or _mentions_host_minecraft(value):
        raise _reject(f"plan path {value!r} is not a run-root-relative path")
    if not value.startswith(RUN_ROOT_PREFIXES):
        raise _reject(f"plan path {value!r} is outside the reviewed run-root prefixes")
    return (root / value).resolve()


def _string_list(runtime: Mapping[str, Any], key: str) -> list[str]:
    value = runtime.get(key)
    if not isinstance(value, list):
        raise _reject(f"launch plan {key} must be a list of strings")
    items = cast(list[object], value)
    if not all(isinstance(item, str) for item in items):
        raise _reject(f"launch plan {key} must be a list of strings")
    return [cast(str, item) for item in items]


def _resolved_jvm_args(runtime: Mapping[str, Any], root: Path) -> list[str]:
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
            joined = separator.join(str(_resolve(root, entry)) for entry in classpath)
            resolved.extend(["-cp", joined])
            index += 2
            continue
        match = _PATH_ARGUMENT.match(argument)
        if match is not None and match.group("value").startswith(RUN_ROOT_PREFIXES):
            resolved.append(f"{match.group('key')}={_resolve(root, match.group('value'))}")
        else:
            resolved.append(argument)
        index += 1
    return resolved


def _require_materialised(argv: tuple[str, ...]) -> None:
    """Refuse a command line that still carries a relative plan path.

    A relative path would resolve against the child process's working directory,
    which is the game directory, not the run root, so it would silently point at
    the wrong place instead of failing.
    """

    for argument in argv:
        if argument.startswith(RUN_ROOT_PREFIXES):
            raise _reject(f"argument {argument!r} was left as a run-root-relative path")
        if _mentions_host_minecraft(argument):
            raise _reject(f"argument {argument!r} refers to the host .minecraft directory")
