"""The game options a managed client starts with.

A fresh game directory is a *first run*, and vanilla's first run shows the
accessibility onboarding screen — "Welcome to Minecraft! Would you like to enable
the Narrator or visit the Accessibility Settings?" — before anything else. That
screen is not a detail of the first launch. `--quickPlaySingleplayer` does not get
past it, so a session that was asked to enter a world sat on that page for as long
as it was left running, and neither the launcher nor the client's log said so: the
log of such a run ends at the texture atlases and stays there.

The overlay is a fresh game directory for every session generation, so this is not
a one-off. It is the state every managed client starts in.

What vanilla gates on is the *existence* of `options.txt`, and that was measured
rather than assumed, in the runner, one run each:

- no `options.txt`: the onboarding screen, and the world is never entered — the
  client's log stops at the atlases, and the seeded world's files are untouched
  minutes later;
- `options.txt` holding `onboardAccessibility:true`: the world loads
  (`Preparing start region for dimension minecraft:overworld`, then
  `Loaded 38 advancements`), which is the thing a host session needs;
- `options.txt` holding only `narrator:0`: the world loads too — so it is the
  file's existence that decides, not the key the screen would have written.

`onboardAccessibility:true` is written anyway, because it is the option that says
what is true about this client: nobody is going to press Continue for it, and a
managed client is past onboarding by definition.
"""

from __future__ import annotations

from pathlib import Path

from minekin_core.domain.errors import ErrorCategory, MinekinError, Retryability

#: The file vanilla reads its options from, and the one whose absence makes a game
#: directory a first run.
OPTIONS_FILE = "options.txt"

#: The option the onboarding screen writes when it is dismissed. Written here for
#: the reason above; the screen is suppressed by the file existing.
ONBOARDED_OPTION = "onboardAccessibility:true"


def _reject(message: str) -> MinekinError:
    return MinekinError(
        "launcher.options",
        "prepare",
        ErrorCategory.CONFIG,
        Retryability.OPERATOR_ACTION,
        message,
    )


def game_options_path(overlay: Path) -> Path:
    """Where vanilla looks for its options, given that the overlay is the game dir."""

    if not overlay.is_absolute():
        raise _reject("the session overlay must be an absolute path")
    return overlay.resolve() / OPTIONS_FILE


def prepare_game_options(overlay: Path) -> Path:
    """Place a minimal `options.txt`, unless the game directory already has one.

    Never overwritten. An overlay that already carries options is one the client
    wrote, and a launcher that replaced it would be taking a Kin's settings away
    between generations — the file is the client's, and this only supplies the one
    a fresh game directory cannot have.
    """

    path = game_options_path(overlay)
    if path.exists():
        return path
    path.write_text(f"{ONBOARDED_OPTION}\n", encoding="utf-8")
    return path
