"""The gate that keeps the Bridge's client core out of the server.

The host boundary contract splits the Bridge in two and says why: the integrated
server runs in the same JVM, so what stands between a Kin's perception and the
server's own truth is which types the code may name. These tests are about the gate
holding that line — including the two ways it could do harm itself, by refusing what
the adapter legitimately needs and by reading prose as code.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TOOL = "tools/check_bridge_host_boundary.py"

CORE = "org/minekin/bridge/runtime/ClientSnapshot.java"
ADAPTER = "org/minekin/bridge/host/IntegratedServerControl.java"


def _tree(tmp_path: Path, files: dict[str, str]) -> Path:
    sources = tmp_path / "bridge" / "src" / "main" / "java"
    for relative, text in files.items():
        path = sources / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return sources


def _run(sources: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, TOOL, "--sources-dir", str(sources)],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_the_bridge_as_it_stands_is_inside_the_boundary() -> None:
    """Today's production sources name no server type — so the gate has nothing to allow yet."""

    result = subprocess.run(
        [sys.executable, TOOL],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout


def test_a_client_file_that_calls_get_server_is_refused(tmp_path: Path) -> None:
    """`getServer()` is the door, and the adapter is the only thing allowed through it."""

    sources = _tree(tmp_path, {CORE: "class A { void a(MinecraftClient c) { c.getServer(); } }\n"})

    result = _run(sources)

    assert result.returncode == 1
    assert "ClientSnapshot.java:1" in result.stderr
    assert "getServer()" in result.stderr


def test_a_client_file_that_names_the_server_type_is_refused(tmp_path: Path) -> None:
    sources = _tree(tmp_path, {CORE: "class A { IntegratedServer server; }\n"})

    result = _run(sources)

    assert result.returncode == 1
    assert "IntegratedServer" in result.stderr


def test_the_adapter_may_name_the_server_it_drives(tmp_path: Path) -> None:
    """The negative control for the tier above: refusing this would refuse the job."""

    sources = _tree(
        tmp_path,
        {
            ADAPTER: (
                "class A { IntegratedServer s;"
                " boolean open() { return s.openToLan(null, false, 0); } }\n"
            )
        },
    )

    result = _run(sources)

    assert result.returncode == 0, result.stderr


def test_what_is_in_the_world_is_refused_even_in_the_adapter(tmp_path: Path) -> None:
    """The adapter drives the server's lifecycle; it does not get to read the world.

    Otherwise the boundary would have moved rather than closed: server truth would
    reach the product through the module that is allowed to touch the server.
    """

    sources = _tree(tmp_path, {ADAPTER: "class A { ServerPlayerEntity player; }\n"})

    result = _run(sources)

    assert result.returncode == 1
    assert "ServerPlayerEntity" in result.stderr


def test_a_wildcard_over_the_server_package_is_refused_even_for_the_adapter(
    tmp_path: Path,
) -> None:
    """The contract asks for a precise allowlist, and a wildcard is the opposite."""

    sources = _tree(
        tmp_path,
        {ADAPTER: "import net.minecraft.server.integrated.*;\nclass A { }\n"},
    )

    result = _run(sources)

    assert result.returncode == 1
    assert "wildcard import" in result.stderr


def test_reflection_is_refused_wherever_it_appears(tmp_path: Path) -> None:
    sources = _tree(tmp_path, {ADAPTER: "class A { java.lang.reflect.Method m; }\n"})

    result = _run(sources)

    assert result.returncode == 1
    assert "java.lang.reflect" in result.stderr


def test_prose_about_a_type_is_not_a_use_of_it(tmp_path: Path) -> None:
    """The adapter's own javadoc has to explain what it calls, and the rules are
    worth quoting beside the code they govern.

    This is the gate's own failure mode: a rule that fires on the comment
    explaining it teaches people to delete the explanation.
    """

    sources = _tree(
        tmp_path,
        {
            CORE: (
                "/**\n"
                " * This file must not use IntegratedServer or call getServer(); the\n"
                " * adapter in org/minekin/bridge/host does that instead.\n"
                " */\n"
                "class A { }\n"
            ),
            ADAPTER: (
                "// IntegratedServer.openToLan is the call this adapter exists for.\nclass B { }\n"
            ),
        },
    )

    result = _run(sources)

    assert result.returncode == 0, result.stderr


def test_the_line_numbers_point_at_the_file_as_it_is_read(tmp_path: Path) -> None:
    """Comments are blanked rather than removed, so a reported line is the real one."""

    sources = _tree(
        tmp_path,
        {CORE: "/* one\n * two\n */\nclass A { IntegratedServer s; }\n"},
    )

    result = _run(sources)

    assert result.returncode == 1
    assert "ClientSnapshot.java:4" in result.stderr


def test_a_missing_source_tree_is_not_reported_as_a_pass(tmp_path: Path) -> None:
    """A gate that cannot find the code must not say the code is clean."""

    result = _run(tmp_path / "nowhere")

    assert result.returncode == 2
    assert "not a directory" in result.stderr


def test_a_file_whose_package_and_directory_disagree_is_refused(tmp_path: Path) -> None:
    """A move that leaves the `package` line alone still compiles into that package.

    Which module a file belongs to is what it declares, and `javac` never required
    that to match the directory. A gate that read only the path could be walked
    around by a file that declares the adapter's package while sitting somewhere
    else — so disagreement is a violation whichever way round it is.
    """

    sources = _tree(
        tmp_path,
        {
            CORE: "package org.minekin.bridge.host;\nclass A { }\n",
            ADAPTER: "package org.minekin.bridge.runtime;\nclass B { }\n",
        },
    )

    result = _run(sources)

    assert result.returncode == 1
    assert "declares package org.minekin.bridge.host" in result.stderr
    assert "declares package org.minekin.bridge.runtime" in result.stderr


def test_the_declared_package_is_what_decides_the_allowance(tmp_path: Path) -> None:
    """Both halves at once: the mismatch is reported *and* the reference is caught.

    The smuggled file is not quietly granted the allowance on its way to being
    reported for the wrong directory.
    """

    sources = _tree(
        tmp_path,
        {
            CORE: (
                "package org.minekin.bridge.host;\n"
                "class A { void a(MinecraftClient c) { c.getServer(); } }\n"
            )
        },
    )

    result = _run(sources)

    assert result.returncode == 1
    assert "sits in org.minekin.bridge.runtime" in result.stderr
