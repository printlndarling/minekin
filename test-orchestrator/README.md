# P0 test orchestrator boundary

This directory is reserved for the isolated test process that owns vanilla
server lifecycle, fault injection, and server-truth evidence. It is not part of
the `minekin-core` wheel or the Bridge JAR, and it has no write path back into
Runtime observations, projections, planning, or control.

W00 freezes this boundary only. The executable orchestrator is introduced with
the W40/W50 controlled-server and oracle-isolation work packages.
