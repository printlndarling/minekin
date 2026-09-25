"""Whether a `tested` registry entry is backed by the artifacts it names.

The card this covers asks one question that no earlier gate answers: can the word
`tested` in the reviewed registry be checked against the machine rather than read
on trust? The checks below are the card's own counterexamples, and each one has to
end in a named refusal rather than in a softer default:

- a digest that disagrees with the real artifact,
- an artifact that is missing or cannot be read, with the refusal naming which,
- a citation to a bundle that was never sealed, or sealed under another digest,
- a registry whose text moved while every artifact stayed where it was,
- and an entry point that writes anything at all, which is refused by being a
  read-only contract the test can check by hashing what it was pointed at, before
  and after.

The domain half is measured with synthetic readings, because the rule it holds —
"an unmeasured citation is not a pass" above all — has to be checkable on a host
with no built Bridge. The tool half runs against the real checkout and a temporary
evidence root, so the digests it argues about are the ones the registry currently
pins rather than copies of them kept in this file.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import sys
from dataclasses import replace
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

from bundle_support import manifest as sealed_manifest
from minekin_core.adapters.evidence.bundle import verify_bundle, write_bundle
from minekin_core.adapters.launcher.recipe import (
    BRIDGE_1201_JAR_RELATIVE_PATH,
    MINECRAFT_1201_VERSION,
)
from minekin_core.domain.version_probe import ProbeObservation, ProbeOutcome
from minekin_core.domain.version_resolution import (
    BridgeMeasurement,
    CitationMeasurement,
    EntryMeasurements,
    ProvenanceViolation,
    RegistryEntry,
    load_reviewed_registry,
    resolve,
    verify_entry_provenance,
    verify_registry_provenance,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = REPOSITORY_ROOT / "tests" / "fixtures" / "registry" / "reviewed-tested-bundles.json"
CASE_ID = "PROV-001"
RUN_ID = "5c1f9a7b2d3e4f6089abcdef01234567"


def load_tool() -> ModuleType:
    sys.path.insert(0, str(REPOSITORY_ROOT))
    try:
        return importlib.import_module("tools.verify_tested_provenance")
    finally:
        sys.path.remove(str(REPOSITORY_ROOT))


PROVENANCE = load_tool()


def registry_document() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(REGISTRY_PATH.read_bytes()))


def reviewed_entry(version_text: str = MINECRAFT_1201_VERSION) -> RegistryEntry:
    """One entry of the reviewed registry, as the loader reads it."""

    registry = load_reviewed_registry(registry_document())
    return next(entry for entry in registry.entries if entry.version_text == version_text)


def raw_entry_document(version_text: str = MINECRAFT_1201_VERSION) -> dict[str, Any]:
    """One reviewed entry exactly as the fixture writes it, citations and all.

    Read from the registry rather than restated here, so a renewed build moves this
    test with it instead of leaving a green assertion about a digest nobody seals
    under any more.
    """

    for item in cast(list[dict[str, Any]], registry_document()["entries"]):
        if item["version_text"] == version_text:
            return dict(item)
    raise AssertionError(f"the reviewed registry no longer carries a {version_text} entry")


def entry_document(**overrides: Any) -> dict[str, Any]:
    """The reviewed 1.20.1 entry as a document, citing nothing yet."""

    found = raw_entry_document()
    found["evidence"] = []
    found.update(overrides)
    return found


def citation(run_id: str, entry: dict[str, Any], *, digest: str | None = None) -> dict[str, Any]:
    return {
        "case_id": CASE_ID,
        "run_id": run_id,
        "bundle_digest": digest or hashlib.sha256(run_id.encode()).hexdigest(),
        "bridge_digest": entry["bridge_digest"],
        "launch_plan_digest": entry["launch_plan_digest"],
        "result": "PASS",
        "attempt": 1,
    }


def registry_file(tmp_path: Path, *entries: dict[str, Any]) -> Path:
    document = {"schema_version": 1, "kind": "reviewed-bundle-registry", "entries": list(entries)}
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def seal(data_root: Path, entry: dict[str, Any], *, seal_bytes: bool = False) -> Path:
    """Seal one bundle carrying an entry's build digests, at the address a run id names."""

    payload = replace(
        sealed_manifest(RUN_ID),
        case_id=CASE_ID,
        bridge_digest=str(entry["bridge_digest"]),
        launch_plan_digest=str(entry["launch_plan_digest"]),
    )
    directory = data_root / "kin" / "profile-r1" / "run" / "evidence" / RUN_ID
    write_bundle(directory, payload, {"timeline.jsonl": b'{"state":"JOINED"}\n'}, seal=seal_bytes)
    return directory


def cite_sealed(data_root: Path, tmp_path: Path, *, seal_bytes: bool = False) -> dict[str, Any]:
    """A one-entry registry whose citation points at a bundle that is really there."""

    entry = entry_document()
    directory = seal(data_root, entry, seal_bytes=seal_bytes)
    entry["evidence"] = [citation(RUN_ID, entry, digest=verify_bundle(directory).bundle_digest)]
    return entry


def report_for(tmp_path: Path, data_root: Path, path: Path) -> dict[str, object]:
    return cast(
        dict[str, object],
        PROVENANCE.report(registry_path=path, data_root=data_root, workspace_root=REPOSITORY_ROOT),
    )


def findings(report: dict[str, object], bundle_id: str) -> list[dict[str, Any]]:
    entries = cast(list[dict[str, Any]], report["entries"])
    return next(item["findings"] for item in entries if item["bundle_id"] == bundle_id)


def violations(report: dict[str, object], bundle_id: str) -> set[str]:
    return {str(item["violation"]) for item in findings(report, bundle_id)}


def text_of(report: dict[str, object], violation: str) -> str:
    entries = cast(list[dict[str, Any]], report["entries"])
    return " ".join(
        f"{item['subject']} {item['detail']}"
        for entry in entries
        for item in entry["findings"]
        if item["violation"] == violation
    )


def complete_readings(entry: RegistryEntry, **overrides: Any) -> EntryMeasurements:
    """Readings that back every claim of one entry, one of them replaceable per test."""

    bridge = BridgeMeasurement(
        source_root="bridge-1201",
        jar_path=BRIDGE_1201_JAR_RELATIVE_PATH,
        jar_sha256=entry.bridge_digest,
        jar_size=1,
        source_digest="b" * 64,
    )
    citations = tuple(
        CitationMeasurement(
            run_id=ref.run_id,
            present=True,
            readable=True,
            sealed=True,
            consistent=True,
            bundle_digest=ref.bundle_digest,
            case_id=ref.case_id,
            result="PASS",
            bridge_digest=entry.bridge_digest,
            launch_plan_digest=entry.launch_plan_digest,
        )
        for ref in entry.evidence
    )
    document: dict[str, Any] = {
        "recipe_digest": entry.recipe_digest,
        "recipe_source_digest": bridge.source_digest,
        "plan_sha256": entry.launch_plan_digest,
        "bridge": bridge,
        "citations": citations,
    }
    document.update(overrides)
    return EntryMeasurements(**document)


def one_citation_changed(entry: RegistryEntry, **changes: Any) -> EntryMeasurements:
    """Complete readings with the first cited bundle read differently, the rest kept."""

    readings = complete_readings(entry)
    changed = replace(readings.citations[0], **changes)
    return replace(readings, citations=(changed, *readings.citations[1:]))


# --- the domain rules, on synthetic readings --------------------------------------


def test_an_entry_nobody_measured_is_not_a_pass() -> None:
    entry = reviewed_entry()
    result = verify_entry_provenance(entry, None)
    assert result.verified is False
    assert [item.violation for item in result.findings] == [ProvenanceViolation.ENTRY_NOT_MEASURED]


def test_a_read_backed_entry_verifies_and_an_empty_reading_does_not() -> None:
    entry = reviewed_entry()
    assert verify_entry_provenance(entry, complete_readings(entry)).verified is True
    assert verify_entry_provenance(entry, complete_readings(entry, citations=())).verified is False


def test_a_citation_nobody_read_is_refused_by_run_id() -> None:
    entry = reviewed_entry()
    result = verify_entry_provenance(entry, complete_readings(entry, citations=()))
    assert {item.violation for item in result.findings} == {ProvenanceViolation.CITATION_UNMEASURED}
    assert {item.subject for item in result.findings} == {
        f"{ref.case_id}@{ref.run_id}" for ref in entry.evidence
    }


def test_a_bundle_that_records_something_other_than_a_pass_is_refused() -> None:
    entry = reviewed_entry()
    result = verify_entry_provenance(entry, one_citation_changed(entry, result="FAIL"))
    assert {item.violation for item in result.findings} == {ProvenanceViolation.CITATION_NOT_PASS}
    assert result.findings[0].subject == f"{entry.evidence[0].case_id}@{entry.evidence[0].run_id}"


def test_a_bundle_sealed_against_another_build_is_refused_even_when_it_verifies() -> None:
    entry = reviewed_entry()
    readings = one_citation_changed(entry, bridge_digest="f" * 64)
    result = verify_entry_provenance(entry, readings)
    assert {item.violation for item in result.findings} == {
        ProvenanceViolation.CITATION_BUILD_DISAGREES
    }


def test_bridge_bytes_that_are_not_there_are_named_apart_from_bytes_that_moved() -> None:
    entry = reviewed_entry()
    missing = verify_entry_provenance(
        entry,
        complete_readings(
            entry,
            bridge=replace(
                cast(BridgeMeasurement, complete_readings(entry).bridge),
                jar_sha256=None,
                jar_size=None,
                source_digest=None,
            ),
        ),
    )
    assert {item.violation for item in missing.findings} == {
        ProvenanceViolation.BRIDGE_JAR_MISSING,
        ProvenanceViolation.SOURCE_TREE_MISSING,
    }

    moved = verify_entry_provenance(
        entry,
        complete_readings(
            entry,
            bridge=replace(
                cast(BridgeMeasurement, complete_readings(entry).bridge),
                jar_sha256="0" * 64,
                source_digest="1" * 64,
            ),
        ),
    )
    assert {item.violation for item in moved.findings} == {
        ProvenanceViolation.BRIDGE_JAR_DIGEST_MISMATCH,
        ProvenanceViolation.SOURCE_DIGEST_MISMATCH,
    }


def test_only_tested_entries_are_verified_and_the_rest_are_named_as_skipped() -> None:
    draft = dict(entry_document())
    draft["bundle_id"] = "a-candidate-entry"
    draft["status"] = "candidate"
    draft["evidence"] = []
    # A `tested` entry the loader would refuse to read cites nothing, so the skipped
    # one has to be the draft and the checked one keeps its real citations.
    tested = raw_entry_document()
    registry = load_reviewed_registry(
        {"schema_version": 1, "kind": "reviewed-bundle-registry", "entries": [draft, tested]}
    )
    summary = verify_registry_provenance(registry, {})
    assert [item.bundle_id for item in summary.entries] == [tested["bundle_id"]]
    assert summary.skipped == ("a-candidate-entry",)
    assert summary.verified is False
    assert summary.as_document()["skipped_not_tested"] == ["a-candidate-entry"]


# --- the read-only entry point, on the real checkout ------------------------------


@pytest.fixture
def data_root(tmp_path: Path) -> Path:
    root = tmp_path / "data"
    root.mkdir()
    return root


def test_the_bridge_bytes_are_measured_rather_than_the_pin_repeated(
    data_root: Path, tmp_path: Path
) -> None:
    """The card's own stop condition, checked as a positive observation.

    A report that echoed `recipe.py`'s constants would name a jar digest on any host;
    a report that hashed the jar names one only where the bytes are. Where the jar is
    built the two readings coincide and this test proves little — the host without it,
    which is what CI looks like, is where the refusal to echo shows.
    """

    entry = cite_sealed(data_root, tmp_path)
    path = registry_file(tmp_path, entry)
    built = (REPOSITORY_ROOT / BRIDGE_1201_JAR_RELATIVE_PATH).is_file()

    document = report_for(tmp_path, data_root, path)
    entries = cast(list[dict[str, Any]], document["entries"])
    measured = cast(dict[str, Any], entries[0]["measured"])
    if built:
        assert cast(str, measured["bridge"]["jar_sha256"]) == entry["bridge_digest"]
    else:
        assert measured["bridge"]["jar_sha256"] is None
        assert violations(document, entry["bundle_id"]) == {
            ProvenanceViolation.BRIDGE_JAR_MISSING.value
        }


def test_an_entry_backed_by_the_artifacts_it_names_verifies(
    data_root: Path, tmp_path: Path
) -> None:
    if not (REPOSITORY_ROOT / BRIDGE_1201_JAR_RELATIVE_PATH).is_file():
        pytest.skip(
            f"{BRIDGE_1201_JAR_RELATIVE_PATH} is not built on this host, and the reviewed "
            "Bridge bytes are one of the things this check measures"
        )
    entry = cite_sealed(data_root, tmp_path)
    document = report_for(tmp_path, data_root, registry_file(tmp_path, entry))
    assert document["verified"] is True
    assert findings(document, entry["bundle_id"]) == []


def test_a_bundle_whose_bytes_moved_after_sealing_is_refused(
    data_root: Path, tmp_path: Path
) -> None:
    entry = cite_sealed(data_root, tmp_path)
    path = registry_file(tmp_path, entry)
    directory = data_root / "kin" / "profile-r1" / "run" / "evidence" / RUN_ID
    (directory / "timeline.jsonl").write_bytes(b'{"state":"LEFT"}\n')

    document = report_for(tmp_path, data_root, path)
    assert document["verified"] is False
    assert ProvenanceViolation.CITATION_BUNDLE_INCONSISTENT.value in violations(
        document, entry["bundle_id"]
    )
    assert RUN_ID in text_of(document, ProvenanceViolation.CITATION_BUNDLE_INCONSISTENT.value)


def test_a_citation_to_a_run_that_was_never_sealed_names_the_missing_artifact(
    data_root: Path, tmp_path: Path
) -> None:
    entry = entry_document(evidence=[citation(RUN_ID, entry_document())])
    document = report_for(tmp_path, data_root, registry_file(tmp_path, entry))
    assert document["verified"] is False
    assert ProvenanceViolation.CITATION_BUNDLE_MISSING.value in violations(
        document, entry["bundle_id"]
    )
    assert RUN_ID in text_of(document, ProvenanceViolation.CITATION_BUNDLE_MISSING.value)


def test_a_bundle_directory_without_a_manifest_is_unreadable_rather_than_absent(
    data_root: Path, tmp_path: Path
) -> None:
    entry = entry_document(evidence=[citation(RUN_ID, entry_document())])
    directory = data_root / "kin" / "profile-r1" / "run" / "evidence" / RUN_ID
    directory.mkdir(parents=True)
    (directory / "bundle.sha256").write_text("0" * 64, encoding="ascii")

    document = report_for(tmp_path, data_root, registry_file(tmp_path, entry))
    assert ProvenanceViolation.CITATION_BUNDLE_UNREADABLE.value in violations(
        document, entry["bundle_id"]
    )


def test_a_citation_to_a_digest_nothing_was_sealed_under_is_refused(
    data_root: Path, tmp_path: Path
) -> None:
    entry = entry_document(evidence=[citation(RUN_ID, entry_document(), digest="a" * 64)])
    seal(data_root, entry)
    document = report_for(tmp_path, data_root, registry_file(tmp_path, entry))
    assert ProvenanceViolation.CITATION_DIGEST_MISMATCH.value in violations(
        document, entry["bundle_id"]
    )
    assert "a" * 64 in text_of(document, ProvenanceViolation.CITATION_DIGEST_MISMATCH.value)


def test_moving_the_registry_text_without_moving_the_artifacts_is_refused(
    data_root: Path, tmp_path: Path
) -> None:
    entry = cite_sealed(data_root, tmp_path)
    recipe = REPOSITORY_ROOT / str(entry["recipe_path"])
    before = hashlib.sha256(recipe.read_bytes()).hexdigest()

    tampered = dict(entry)
    tampered["recipe_digest"] = "e" * 64
    document = report_for(tmp_path, data_root, registry_file(tmp_path, tampered))

    assert document["verified"] is False
    assert ProvenanceViolation.RECIPE_DIGEST_MISMATCH.value in violations(
        document, tampered["bundle_id"]
    )
    # The artifact did not move, so the refusal is about the document — which is the
    # whole point of the counterexample.
    assert hashlib.sha256(recipe.read_bytes()).hexdigest() == before


def test_a_writable_but_intact_bundle_is_reported_without_being_refused(
    data_root: Path, tmp_path: Path
) -> None:
    entry = cite_sealed(data_root, tmp_path)
    entries = cast(
        list[dict[str, Any]],
        report_for(tmp_path, data_root, registry_file(tmp_path, entry))["entries"],
    )
    citations = cast(list[dict[str, Any]], entries[0]["measured"]["citations"])
    assert citations[0]["sealed"] is False
    assert citations[0]["consistent"] is True


def test_two_bundles_under_one_run_id_make_the_reading_impossible(
    data_root: Path, tmp_path: Path
) -> None:
    entry = cite_sealed(data_root, tmp_path)
    write_bundle(
        data_root / "repo-evidence" / RUN_ID,
        replace(
            sealed_manifest(RUN_ID),
            case_id=CASE_ID,
            bridge_digest=str(entry["bridge_digest"]),
            launch_plan_digest=str(entry["launch_plan_digest"]),
        ),
        {"timeline.jsonl": b"{}\n"},
    )
    with pytest.raises(PROVENANCE.Unusable, match="a run id names one bundle"):
        report_for(tmp_path, data_root, registry_file(tmp_path, entry))


def _tree_state(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root).as_posix()): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_the_entry_point_writes_nothing_it_was_pointed_at(
    data_root: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    entry = cite_sealed(data_root, tmp_path)
    path = registry_file(tmp_path, entry)
    recipe = REPOSITORY_ROOT / str(entry["recipe_path"])
    data_before = _tree_state(data_root)
    registry_before = path.read_bytes()
    reviewed_before = _tree_state(REGISTRY_PATH.parent)
    recipe_before = hashlib.sha256(recipe.read_bytes()).hexdigest()

    code = PROVENANCE.main(
        [
            "--registry",
            str(path),
            "--data-root",
            str(data_root),
            "--workspace-root",
            str(REPOSITORY_ROOT),
        ]
    )

    assert code in (PROVENANCE.EXIT_VERIFIED, PROVENANCE.EXIT_REFUSED)
    assert _tree_state(data_root) == data_before
    assert path.read_bytes() == registry_before
    assert _tree_state(REGISTRY_PATH.parent) == reviewed_before
    assert hashlib.sha256(recipe.read_bytes()).hexdigest() == recipe_before
    assert json.loads(capsys.readouterr().out)["kind"] == "tested-provenance-report"


def test_verifying_provenance_leaves_resolution_exactly_as_it_was(tmp_path: Path) -> None:
    """The refusals this card adds must not reach the resolver in either direction."""

    registry = load_reviewed_registry(registry_document())
    observation = ProbeObservation(
        outcome=ProbeOutcome.OBSERVED,
        profile_id="p0-test-profile",
        profile_revision="9" * 64,
        endpoint="192.0.2.20:25565",
        resolution_chain=("as-saved:192.0.2.20:25565",),
        protocol=763,
        version_text="1.20.1",
        refusal_reasons=(),
        detail=None,
    )
    before = resolve(registry, observation, os_arch="linux-x86_64")
    empty = tmp_path / "nothing-here"
    empty.mkdir()
    assert (
        cast(
            dict[str, object],
            PROVENANCE.report(
                registry_path=REGISTRY_PATH, data_root=empty, workspace_root=REPOSITORY_ROOT
            ),
        )["verified"]
        is False
    )
    after = resolve(registry, observation, os_arch="linux-x86_64")
    assert after.as_document() == before.as_document()
