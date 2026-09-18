"""The pinned vanilla server must agree between the contract and the frozen metadata.

The evidence contract records the server jar's SHA-1 and the server-truth field
`server_jar_sha1` carries it into every bundle. The frozen Mojang metadata is where
that jar is actually pointed at. Two documents agreeing today is not the same as
two documents that cannot disagree, so this asserts it.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
VERSION_METADATA = REPOSITORY_ROOT / "tests" / "fixtures" / "launcher" / "1.21.4.json"

# From docs/p0-validation-evidence-contract.md, which is also where the evidence
# bundle's `server_jar_sha1` gets its value.
DOCUMENTED_SERVER_SHA1 = "4707d00eb834b446575d89a61a11b5d548d8c001"
DOCUMENTED_SERVER_SIZE = 56_880_250

CONTENT_HASHED_PATH = re.compile(r"/objects/([0-9a-f]{40})/")


def server_download() -> dict[str, object]:
    document = json.loads(VERSION_METADATA.read_bytes())
    return dict(document["downloads"]["server"])


def test_the_frozen_metadata_points_at_the_documented_server() -> None:
    server = server_download()

    assert server["sha1"] == DOCUMENTED_SERVER_SHA1
    assert server["size"] == DOCUMENTED_SERVER_SIZE


def test_the_pinned_url_is_content_addressed_by_the_digest_it_declares() -> None:
    """Mojang's path carries the SHA-1, so a mismatch here is a corrupted fixture."""

    server = server_download()
    match = CONTENT_HASHED_PATH.search(str(server["url"]))

    assert match is not None, server["url"]
    assert match.group(1) == server["sha1"]


def documented(path: str) -> str:
    return (REPOSITORY_ROOT / path).read_text(encoding="utf-8")


def test_the_evidence_contract_records_the_same_digest() -> None:
    """The number the bundle will carry is the number the metadata serves."""

    contract = documented("docs/p0-validation-evidence-contract.md")

    assert f"`{DOCUMENTED_SERVER_SHA1}`" in contract
    assert f'server_jar_sha1: "{DOCUMENTED_SERVER_SHA1}"' in contract


def test_the_reference_notes_record_the_same_size() -> None:
    """The size is stated where the upstream was checked, and it must stay true."""

    references = documented("docs/references.md")

    assert f"`{DOCUMENTED_SERVER_SHA1}`" in references
    assert f"{DOCUMENTED_SERVER_SIZE:,} bytes" in references
