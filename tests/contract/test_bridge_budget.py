"""The one report the Bridge may drop, and the reason it is allowed to drop it.

The event outbox is bounded and every publisher on it fails closed when it is full:
a lifecycle phase nobody could deliver leaves a session joined and going nowhere, and
stopping the client is the safer answer to that. A budget window is the opposite case
— it is a measurement of the Bridge, so stopping a client because the measurement
could not be delivered would make the sampler the cause of the fault it exists to
detect. It is dropped, logged, and seen as a hole in the window ordinals.

That rule cannot be reached by a test here. The publisher needs a live worker with
two sockets and a full outbox, which is a real client, and this repository's whole
reason for the offline checks is that a real client is the one thing it cannot
reproduce locally. So the rule is pinned at the source, which is the weaker claim
and is stated as such: what this can say is that the code that would make the
decision is the code that makes it, not that a run has exercised it.

The contrast is the useful part. If every publisher refused to fail closed the rule
would be no rule, and if the budget's did it would be a hazard — so both directions
are asserted rather than only the interesting one.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
WORKER = (
    REPOSITORY_ROOT
    / "bridge"
    / "src"
    / "main"
    / "java"
    / "org"
    / "minekin"
    / "bridge"
    / "runtime"
    / "BridgeIpcWorker.java"
)

#: The publishers that must fail closed, and the one that must not.
FAIL_CLOSED_BY_DESIGN: Final[tuple[str, ...]] = (
    "publishLifecycle",
    "publishObservation",
    "publishActionResult",
    "publishHostLifecycle",
)
DROPPABLE_BY_DESIGN: Final[str] = "publishBudgetWindow"

_METHOD = re.compile(
    r"^    (?:public|private|static|protected|\s)*[\w<>\[\], .]+ (?P<name>\w+)\([^)]*\)\s*\{",
    flags=re.MULTILINE,
)


def method_body(name: str) -> str:
    """One method's text, from its signature to the closing brace in column four.

    Braces are counted rather than searched for the first one after the signature:
    every one of these methods contains blocks, and a body that stopped at the first
    `}` would be a body that stops before the decision under test.
    """

    text = WORKER.read_text(encoding="utf-8")
    match = next((found for found in _METHOD.finditer(text) if found.group("name") == name), None)
    assert match is not None, f"{name} is not in {WORKER.name}; this check would pass vacuously"

    depth = 0
    for index in range(match.end() - 1, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[match.start() : index + 1]
    raise AssertionError(f"{name} is not closed in {WORKER.name}")


def test_the_lifecycle_and_result_publishers_still_fail_closed() -> None:
    """The negative control: dropping everything would make the rule above meaningless."""

    for name in FAIL_CLOSED_BY_DESIGN:
        assert "failClosed()" in method_body(name), name


def test_the_budget_publisher_drops_instead_of_stopping_the_client() -> None:
    """A measurement that could stop a session is a measurement that causes the fault.

    The window is lost and said to be lost — the gap in the ordinals is the evidence,
    and the warning is where an operator reads which window it was.
    """

    body = method_body(DROPPABLE_BY_DESIGN)

    assert "failClosed()" not in body
    assert "eventOutbox.offer(" in body, "the drop has to be the offer failing"
    assert "LOGGER.warn(" in body, "a dropped window is named, not silent"


def test_the_extracted_body_is_the_method_and_not_a_prefix_of_it() -> None:
    """A parser that stopped early would make the assertions above agree with anything."""

    body = method_body("publishBudgetWindow")

    assert body.rstrip().endswith("}")
    assert body.count("{") == body.count("}")
    assert body.count("{") > 1, "a body of one block is a body that was cut short"
