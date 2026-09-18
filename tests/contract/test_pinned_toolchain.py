"""The CI gates must run tools whose versions this repository pins.

A gate that runs "whatever is newest" can turn red — or, worse, keep passing
while checking something different — without any change to this repository. Each
tool the workflow installs is therefore asserted to be pinned by version, in the
same spirit as the dependency locks and fixture digests.
"""

from __future__ import annotations

from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPOSITORY_ROOT / ".github" / "workflows" / "ci.yml"

# Tools the workflow installs itself and must therefore pin.
PINNED_ACTIONS = ("bufbuild/buf-action@",)


def workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def step_block(uses_prefix: str) -> list[str]:
    """The lines of the step that references `uses_prefix`, up to the next step."""

    lines = workflow_text().splitlines()
    for index, line in enumerate(lines):
        if uses_prefix in line:
            block: list[str] = []
            for following in lines[index + 1 :]:
                if following.strip().startswith("- ") or following.strip().startswith("- uses"):
                    break
                block.append(following)
            return block
    raise AssertionError(f"{uses_prefix} is not referenced in {WORKFLOW.name}")


def test_every_installed_action_pins_the_version_it_installs() -> None:
    """The `uses:` reference is pinned by tag; that does not pin what it downloads."""

    for prefix in PINNED_ACTIONS:
        block = step_block(prefix)

        assert any(line.strip().startswith("version:") for line in block), (
            f"{prefix} does not pin the version of the tool it installs; "
            "an unpinned tool can change this gate's behaviour on its own schedule"
        )


def test_every_installed_action_verifies_the_download() -> None:
    """A version names what to fetch; a digest is what proves it arrived intact."""

    for prefix in PINNED_ACTIONS:
        block = step_block(prefix)

        checksums = [
            line.strip().removeprefix("checksum:").strip()
            for line in block
            if line.strip().startswith("checksum:")
        ]
        assert len(checksums) == 1, f"{prefix} must supply exactly one checksum"
        assert len(checksums[0]) == 64, f"{prefix} checksum is not a sha256: {checksums[0]!r}"
        assert all(character in "0123456789abcdef" for character in checksums[0]), checksums[0]


def test_the_buf_cli_version_is_the_reviewed_one() -> None:
    """Lint and format rules move between releases, and their output is a gate."""

    pinned = [line.strip() for line in step_block("bufbuild/buf-action@") if "version:" in line]

    assert pinned == ["version: v1.50.0"], pinned
