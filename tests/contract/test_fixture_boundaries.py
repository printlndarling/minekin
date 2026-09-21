# pyright: reportUnknownMemberType=false

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_frozen_fixture_digests_match() -> None:
    result = subprocess.run(
        [sys.executable, "tools/verify_fixture_digests.py"],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_all_json_contracts_are_parseable_and_versioned() -> None:
    paths = [
        *sorted((REPOSITORY_ROOT / "schemas").glob("*.json")),
        *sorted((REPOSITORY_ROOT / "tests" / "fixtures").rglob("*.json")),
    ]
    assert paths
    for path in paths:
        value = json.loads(path.read_text(encoding="utf-8"))
        if path.parent.name != "schemas" and "launcher" not in path.parts:
            assert value["schema_version"] == 1, path


def test_runtime_fixtures_conform_to_their_json_schemas() -> None:
    pairs = (
        ("bundle-manifest.schema.json", "runtime-input/bundle-p0-core-1.21.4.json"),
        ("server-profile.schema.json", "runtime-input/controlled-offline-server.json"),
        ("case-manifest.schema.json", "cases/w00-contract-001.json"),
        # The world-creation profile: the shape the P0 policy table freezes, and a
        # profile generated from the proposal fixture beside it. The pair is what
        # makes the schema load-bearing rather than a document about a shape.
        ("world-create.schema.json", "runtime-input/world-create-p0.json"),
    )
    for schema_name, fixture_name in pairs:
        schema = json.loads((REPOSITORY_ROOT / "schemas" / schema_name).read_text(encoding="utf-8"))
        fixture = json.loads(
            (REPOSITORY_ROOT / "tests" / "fixtures" / fixture_name).read_text(encoding="utf-8")
        )
        Draft202012Validator.check_schema(schema)
        errors = list(Draft202012Validator(schema).iter_errors(fixture))
        assert errors == []


def test_runtime_inputs_do_not_reference_oracle() -> None:
    runtime_input = REPOSITORY_ROOT / "tests" / "fixtures" / "runtime-input"
    for path in runtime_input.rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8").casefold()
            assert "tests/oracle" not in text
            assert "server_oracle" not in text
            assert "minekin_test_oracle" not in text


def test_product_build_and_import_boundaries_exclude_oracle() -> None:
    result = subprocess.run(
        [sys.executable, "tools/check_boundaries.py"],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_framing_golden_uses_network_order_length_prefix() -> None:
    path = REPOSITORY_ROOT / "tests" / "fixtures" / "protocol" / "release-all-envelope.v1.json"
    golden = json.loads(path.read_text(encoding="utf-8"))
    envelope = bytes.fromhex(golden["envelope_hex"])
    frame = bytes.fromhex(golden["frame_hex"])
    assert frame[:4] == len(envelope).to_bytes(4, "big")
    assert frame[4:] == envelope


def test_case_manifest_oracle_boundary_is_enforced(tmp_path: Path) -> None:
    """A case declares its oracle inputs separately; the tool checks the declaration."""

    base = {
        "schema_version": 1,
        "case_id": "W50-SNAPSHOT-001",
        "work_package": "W50",
        "mandatory": True,
        "assertions": ["first_snapshot_is_authoritative"],
    }
    (tmp_path / "good.json").write_text(
        json.dumps(
            {
                **base,
                "inputs": ["tests/fixtures/runtime-input/*.json"],
                "oracle_inputs": ["tests/oracle/canary.json"],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "input-names-oracle.json").write_text(
        json.dumps({**base, "inputs": ["tests/oracle/canary.json"]}), encoding="utf-8"
    )
    (tmp_path / "oracle-input-elsewhere.json").write_text(
        json.dumps({**base, "inputs": [], "oracle_inputs": ["tests/fixtures/canary.json"]}),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, "tools/check_boundaries.py", "--cases-dir", str(tmp_path)],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "a declared input references the oracle" in result.stderr
    assert "outside tests/oracle/" in result.stderr
    assert "good.json" not in result.stderr
