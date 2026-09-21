"""What the Bridge's host boundary is written in, declared once.

The `hosted-world-control-boundary-contract` splits the Bridge into a client core and
a narrow host-control adapter, and gives the reason: the integrated server runs in
the same JVM, so what stands between a Kin's perception and the server's own truth is
which types the code may name. Two gates enforce that, and they look at different
things:

- `check_bridge_host_boundary.py` reads the sources: who is *allowed to write* these
  names.
- `check_bridge_artifacts.py` reads the build output: what the compiler *left behind*,
  including what a dependency tree brought in rather than what anyone wrote.

Two gates with two copies of the vocabulary would be two rules. The whole point of
the second gate is that the first one can be walked around without editing anything a
person reads, so a drift between them would be a drift in the direction of the hole.
The tables below are therefore one file, imported by both, and neither gate owns them.

`DENIED_ALWAYS` is what is *in* the world — worlds, entities, players, chunks, the
save files — plus the reflection escapes that would turn any of those rules into a
formality. Forbidden everywhere, the adapter included: an adapter that can read a
player's inventory is a second road for server truth into the product, which is the
thing the boundary exists to prevent.

`DENIED_OUTSIDE_HOST` is the door to the server and the server type itself. Opening a
world to LAN is a lifecycle call and the contract gives the adapter that job; any
other file naming `IntegratedServer` or calling `getServer()` is reaching past the
boundary.

The markers are spelled the way Yarn spells them, because that is what someone
writing Bridge code reads and greps for. The build output does not use those spellings
— see `bridge/host-boundary-names.json` for the other half of this vocabulary.
"""

from __future__ import annotations

import re

#: The package the contract allows to hold the lifecycle adapter. Nothing else may
#: name the server. Written as a package rather than a path because that is what a
#: file declares and what the allowance is keyed on.
HOST_PACKAGE = "org.minekin.bridge.host"

#: The same package in the form a class file uses, where packages are directories
#: and the separator is a slash rather than a dot.
HOST_PACKAGE_PATH = HOST_PACKAGE.replace(".", "/")

#: Forbidden in every file, with the reason each one is on the list.
DENIED_ALWAYS: dict[str, str] = {
    "ServerWorld": "a server world is what is in the world, not what happened to the client",
    "ServerLevel": "a server level is what is in the world, not what happened to the client",
    "ServerPlayerEntity": "server-side player state is the oracle's truth, not the Kin's",
    "PlayerManager": "the player list is server truth the Kin cannot see",
    "ServerChunkManager": "chunk state behind the client's view is hidden truth",
    "ServerEntityManager": "entities the client cannot see are hidden truth",
    "NbtIo": "reading save files is reading the world from behind the client",
    "LevelStorage": "the save's own storage is not something the client may open",
    "java.lang.reflect": "reflection makes every rule above a formality",
    "java.lang.invoke.MethodHandles": "method handles make every rule above a formality",
    "Class.forName": "looking a class up by name is reflection with a string",
    "setAccessible": "opening a member for access is how reflection gets around this list",
    "sun.misc.Unsafe": "unsafe access makes every rule above a formality",
}

#: Forbidden everywhere except the host adapter.
DENIED_OUTSIDE_HOST: dict[str, str] = {
    "getServer()": "the door to the integrated server belongs to the lifecycle adapter",
    "MinecraftServer": "the server type belongs to the lifecycle adapter",
    "IntegratedServer": "the integrated server type belongs to the lifecycle adapter",
    "net.minecraft.server.": "the server package belongs to the lifecycle adapter, by allowlist",
}

#: Refused in every file, adapter included: a precise allowlist is not a wildcard.
WILDCARD_SERVER_IMPORT = re.compile(
    r"^\s*import\s+(static\s+)?net\.minecraft\.server\.[\w.]*\*\s*;"
)

#: The bridge test-probes belong to a test-only source set and the contract keeps them
#: out of the production bundle. Spelled here for the artifact gate, which is the gate
#: that can actually see whether they stayed out.
PROBE_PACKAGE_PREFIXES: tuple[str, ...] = (
    "org.minekin.bridge.probe",
    "org.minekin.bridge.test",
)


def bare_marker(marker: str) -> str:
    """A marker as it is spelled when it is a name rather than a call.

    `getServer()` is how the contract writes the call; a class file stores the method
    name the call resolves to, which is `getServer`. Everything else is already a
    name and passes through unchanged.
    """

    return marker[:-2] if marker.endswith("()") else marker


def is_identifier(marker: str) -> bool:
    """Whether this marker is a whole name, rather than a prefix or a dotted class.

    A bare type name has to match as an identifier: `IntegratedServer` is the server
    type, while `IntegratedServerControl` is the adapter in this repository that wraps
    it, and the runtime naming the adapter is the seam working rather than the rule
    being broken. Markers that are not identifiers — a package prefix, a call with its
    parentheses, a dotted reflection class — are matched as they are, because there are
    no boundaries to get wrong.
    """

    return marker.replace("_", "").isalnum()
