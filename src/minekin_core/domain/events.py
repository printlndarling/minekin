"""Trusted source labels for append-only P0 domain events."""

from __future__ import annotations

from enum import StrEnum


class EventSource(StrEnum):
    CORE = "CORE"
    BRIDGE = "BRIDGE"
    LAUNCHER = "LAUNCHER"
    OPERATOR_CLI = "OPERATOR_CLI"
    SERVER_ORACLE_TEST_ONLY = "SERVER_ORACLE_TEST_ONLY"

    @property
    def allowed_in_product_store(self) -> bool:
        return self is not EventSource.SERVER_ORACLE_TEST_ONLY


class TrustClass(StrEnum):
    CORE = "CORE"
    BRIDGE_FILTERED = "BRIDGE_FILTERED"
    LAUNCHER = "LAUNCHER"
    OPERATOR = "OPERATOR"
    UNTRUSTED_WORLD_CONTENT = "UNTRUSTED_WORLD_CONTENT"
    #: Text a model suggested and a gateway accepted: the writer was Core, the words
    #: were remote. Kept apart from CORE so a reader can tell an intention this side
    #: wrote from one it agreed to keep, without asking who ran the check
    #: (`docs/memory-retrieval-consolidation-contract.md`, rule 7).
    MODEL_SUGGESTED = "MODEL_SUGGESTED"
    #: A real account's words, heard through the client. Testimony with its sender
    #: attached — never a system fact, never a permission, and never upgraded by
    #: being summarised later (the memory contract's rule 4). Its own class because
    #: a later reader must be able to tell "a player said this" from "the world is
    #: like this", and because display names are attributes: identity is keyed on
    #: accounts, never merged by name.
    PLAYER_CHAT = "PLAYER_CHAT"
