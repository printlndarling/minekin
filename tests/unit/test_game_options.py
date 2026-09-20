"""The first-run state of a session's game directory.

Vanilla shows the accessibility onboarding screen for a game directory that has
never been run, and that screen stands in front of `--quickPlaySingleplayer`: the
client sat on it instead of entering its world, with nothing in the launcher or in
`latest.log` to say why. These tests are about the one file that decides it, and
about not overwriting the client's own settings to get it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from minekin_core.adapters.launcher.game_options import (
    ONBOARDED_OPTION,
    OPTIONS_FILE,
    game_options_path,
    prepare_game_options,
)
from minekin_core.domain.errors import ErrorCategory, MinekinError


def test_the_options_file_is_inside_the_overlay(tmp_path: Path) -> None:
    overlay = tmp_path / "session" / "generation-1"

    assert game_options_path(overlay) == overlay.resolve() / OPTIONS_FILE


def test_a_relative_overlay_is_refused(tmp_path: Path) -> None:
    with pytest.raises(MinekinError, match="absolute") as raised:
        game_options_path(Path("session/generation-1"))

    assert raised.value.component == "launcher.options"
    assert raised.value.category is ErrorCategory.CONFIG


def test_a_fresh_game_directory_is_given_the_file_that_makes_it_not_fresh(
    tmp_path: Path,
) -> None:
    overlay = tmp_path / "generation-1"
    overlay.mkdir()

    written = prepare_game_options(overlay)

    assert written == overlay / OPTIONS_FILE
    assert written.read_text(encoding="utf-8") == f"{ONBOARDED_OPTION}\n"


def test_options_the_client_wrote_are_left_alone(tmp_path: Path) -> None:
    """The file is the client's. Replacing it would take a Kin's settings away."""

    overlay = tmp_path / "generation-1"
    overlay.mkdir()
    (overlay / OPTIONS_FILE).write_text("narrator:0\nfov:0.5\n", encoding="utf-8")

    written = prepare_game_options(overlay)

    assert written.read_text(encoding="utf-8") == "narrator:0\nfov:0.5\n"


def test_the_file_is_placed_where_the_client_reads_it_not_beside_it(tmp_path: Path) -> None:
    """Measured: it is this file existing that suppresses the screen.

    Written into a sibling directory it would leave the overlay a first run, which
    is the failure this whole step exists to stop — and one that looks exactly like
    a client that has not finished starting.
    """

    overlay = tmp_path / "generation-1"
    overlay.mkdir()

    prepare_game_options(overlay)

    assert (overlay / OPTIONS_FILE).is_file()
    assert [path.name for path in sorted(overlay.iterdir())] == [OPTIONS_FILE]
