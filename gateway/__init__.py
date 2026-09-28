"""The read-only Gateway: one small process that projects Core's existing reads.

P0 Core has no HTTP layer and ADR 0001 keeps it that way, so the Dashboard's
read model lives here, outside `minekin_core`, and reaches the product only
through the reads Core already exposes: `session status`, the append-only
ledger, and a sealed run's evidence bundle. It owns no state of its own.

Two rules follow from that and are the reason this package exists as its own
process rather than a module inside Core:

* It may not write. There is no code path here that opens a writer, and the
  verbs it serves are the three GETs frozen by
  `docs/gateway-dashboard-readonly-contract-2026-09-28.md`.
* It may not invent a reading. A field Core cannot answer is returned as a
  named gap, so "nobody observed this" can never render as a plausible value.
"""
