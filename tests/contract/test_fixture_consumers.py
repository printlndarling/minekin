"""Every frozen fixture is read by something, and this is what keeps that true.

`tests/fixtures/replay/session-preparing.v1.json` sat in the repository from W00 with
nothing reading it. That was deliberate — "commit the fixture and its expectation first,
then the implementation" — but the deliberate part was in a todo note, and a note is not
a thing that notices. The only way to know that fixture had no consumer was to have read
that sentence.

So this is the checking version of it. A fixture nothing names is either a fixture whose
implementation has not landed yet (fine, and worth saying out loud) or one whose
implementation was removed and took its last reader with it (not fine, and silent). The
rule cannot tell those apart and neither can a reader, so both are refused and the way
through is to write down which one it is.

Two exemptions, each for a reason rather than for convenience:

- `cases/` is read a directory at a time — the registry globs it — so its files are
  consumed without ever being named. The exemption is the *directory*, and it is itself
  checked: if that loader stops globbing, the premise is gone and the test says so.
- `manifest.sha256` is the list of everything else, read by the digest gate.
"""

from __future__ import annotations

from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPOSITORY_ROOT / "tests" / "fixtures"

#: Fixtures read by globbing rather than by name, with the code that globs them.
GLOB_CONSUMED: dict[str, str] = {"cases": "minekin_core/adapters/evidence/promotion.py"}

#: Not data: the digest manifest is the list of the others.
NOT_DATA = frozenset({"manifest.sha256"})


def searchable_sources() -> dict[Path, str]:
    """Every file that could name a fixture: the code, the tests, and the two roots."""

    found: dict[Path, str] = {}
    for root in ("src", "tools", "tests"):
        for path in (REPOSITORY_ROOT / root).rglob("*"):
            if not path.is_file() or path.suffix not in {".py", ".java"}:
                continue
            if path.is_relative_to(FIXTURES):
                continue
            found[path] = path.read_text(encoding="utf-8", errors="replace")
    for name in ("README.md", "pyproject.toml"):
        path = REPOSITORY_ROOT / name
        if path.is_file():
            found[path] = path.read_text(encoding="utf-8", errors="replace")
    return found


def unconsumed(
    fixtures: Path, sources: dict[Path, str], *, base: Path = REPOSITORY_ROOT
) -> list[str]:
    """Every fixture under `fixtures` that no source names, and that no glob reads."""

    found: list[str] = []
    for fixture in sorted(fixtures.rglob("*")):
        if not fixture.is_file() or fixture.suffix == ".md":
            continue
        if fixture.name in NOT_DATA or fixture.parent.name in GLOB_CONSUMED:
            continue
        relative = fixture.relative_to(base).as_posix()
        if any(relative in text or fixture.name in text for text in sources.values()):
            continue
        found.append(relative)
    return found


def test_the_glob_exemption_still_describes_something_real() -> None:
    """An exemption that outlives the code it exempts is just a hole.

    This is why the exemption is a claim rather than a list of paths: if the registry
    stops reading that directory, every case fixture becomes unconsumed at once, and
    nothing else here would say so.
    """

    for directory, source in GLOB_CONSUMED.items():
        assert (FIXTURES / directory).is_dir(), directory
        code = (REPOSITORY_ROOT / "src" / source).read_text(encoding="utf-8")

        assert "glob(" in code, f"{source} no longer globs, so {directory}/ is not read"


def test_every_fixture_is_named_by_something() -> None:
    found = unconsumed(FIXTURES, searchable_sources())

    assert found == [], (
        "frozen fixtures nothing reads: " + ", ".join(found) + ". Either land the "
        "implementation that reads one, or say in the todo why it is waiting — a fixture "
        "with no consumer is not noticed by anything else"
    )


def test_the_rule_catches_a_fixture_nobody_reads(tmp_path: Path) -> None:
    """The negative control: a rule that cannot fail is a comment.

    A fixture with a name nothing mentions — which is the shape a committed-and-
    unimplemented fixture has — has to come back from the rule.

    The name is assembled rather than written, and that is not a trick: the rule scans
    the tests as well as the code, because a test fixture named by a test *is* consumed.
    A literal here would make this file its own counterexample and the control would
    pass for the wrong reason — which is exactly what it did the first time.
    """

    name = "-".join(["ORPHAN", "NOBODY", "READS"]) + ".v9.json"
    fixtures = tmp_path / "tests" / "fixtures" / "replay"
    fixtures.mkdir(parents=True)
    (fixtures / "session-preparing.v1.json").write_text("{}\n", encoding="utf-8")
    (fixtures / name).write_text("{}\n", encoding="utf-8")

    found = unconsumed(tmp_path / "tests" / "fixtures", searchable_sources(), base=tmp_path)

    assert found == [f"tests/fixtures/replay/{name}"], found


def test_the_rule_accepts_a_fixture_the_tree_names(tmp_path: Path) -> None:
    """The other half of the control: the rule is not simply refusing everything."""

    fixtures = tmp_path / "tests" / "fixtures" / "replay"
    fixtures.mkdir(parents=True)
    (fixtures / "session-preparing.v1.json").write_text("{}\n", encoding="utf-8")

    found = unconsumed(tmp_path / "tests" / "fixtures", searchable_sources(), base=tmp_path)

    assert found == []
