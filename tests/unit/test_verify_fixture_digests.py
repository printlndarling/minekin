"""The frozen fixture manifest has one unambiguous reviewed value per path."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Protocol, cast

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class _Verifier(Protocol):
    MANIFEST: Path
    ManifestError: type[ValueError]

    def parse_manifest(
        self, manifest: Path | None = None
    ) -> tuple[dict[str, tuple[int, str]], list[str]]: ...

    def frozen_digests(self) -> dict[str, str]: ...


def load_verifier() -> _Verifier:
    """Load the standalone tool by path, independent of another test's sys.path."""

    spec = importlib.util.spec_from_file_location(
        "test_verify_fixture_digests_tool",
        REPOSITORY_ROOT / "tools" / "verify_fixture_digests.py",
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load tools/verify_fixture_digests.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return cast(_Verifier, module)


verifier = load_verifier()


def write_manifest(tmp_path: Path, *lines: str) -> Path:
    manifest = tmp_path / "manifest.sha256"
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return manifest


def test_duplicate_logical_paths_are_rejected(tmp_path: Path) -> None:
    digest = "a" * 64
    manifest = write_manifest(
        tmp_path,
        f"{digest}  tests/fixtures/example.json",
        f"{digest}  tests/fixtures/example.json",
    )

    entries, errors = verifier.parse_manifest(manifest)

    assert entries == {"tests/fixtures/example.json": (1, digest)}
    assert errors == [
        "manifest.sha256:2: duplicate path 'tests/fixtures/example.json' (first listed on line 1)"
    ]


@pytest.mark.parametrize(
    ("line", "reason"),
    [
        ("not-a-manifest-entry", "malformed line"),
        (f"{'g' * 64}  tests/fixtures/example.json", "malformed digest"),
        (f"{'a' * 64}  tests/fixtures/./example.json", "unsafe path"),
        (f"{'a' * 64}  tests\\fixtures\\example.json", "unsafe path"),
    ],
)
def test_malformed_or_noncanonical_entries_are_rejected(
    tmp_path: Path, line: str, reason: str
) -> None:
    entries, errors = verifier.parse_manifest(write_manifest(tmp_path, line))

    assert entries == {}
    assert len(errors) == 1
    assert reason in errors[0]


def test_public_digest_reader_fails_closed_on_a_manifest_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = write_manifest(tmp_path, "not-a-manifest-entry")
    monkeypatch.setattr(verifier, "MANIFEST", manifest)

    with pytest.raises(verifier.ManifestError, match="malformed line"):
        verifier.frozen_digests()
