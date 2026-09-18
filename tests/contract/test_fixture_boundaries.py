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
        if path.parent.name != "schemas":
            assert value["schema_version"] == 1, path


def test_runtime_fixtures_conform_to_their_json_schemas() -> None:
    pairs = (
        ("bundle-manifest.schema.json", "runtime-input/bundle-p0-core-1.21.4.json"),
        ("server-profile.schema.json", "runtime-input/controlled-offline-server.json"),
        ("case-manifest.schema.json", "cases/w00-contract-001.json"),
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
