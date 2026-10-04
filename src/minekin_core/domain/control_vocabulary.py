"""The words a Kin may ask with, kept above the transport that carries them.

Each name here is a cell of the negotiation table or a command on the wire, and
both gates have to answer under the same spelling: the Bridge refuses a command
whose capability was never granted, Core refuses to *send* one it was never
granted, and a run document can only compare those two refusals if they are the
same string written once.

That is why they live in `domain` rather than in the host adapter. A skill layer
that checks its own permission before it builds a message is by contract above
the transport, and if the vocabulary stayed below it the layer that must refuse
first would have to import the layer it is refusing on behalf of.

The strings themselves are frozen contract surface (S1 §capabilities, S2 §1 and
§3), so a rename here is a protocol change, not a refactor.
"""

from __future__ import annotations

import time
from typing import Final

#: The hello itself, negotiated before anything else may be asked.
HANDSHAKE_CAPABILITY: Final = "session.handshake.v1"
#: Being allowed to join a world at all — which is not the same as being allowed
#: to be driven inside it.
ADMISSION_CAPABILITY: Final = "admission.connect.v1"
# The contract names input capabilities `control.<skill>.v1`. Movement is the
# first one, and it is negotiated rather than assumed: a client can be admitted
# to a world without being steerable, and the two must be able to differ.
MOVE_CAPABILITY: Final = "control.move.v1"
# And looking, which is its own capability for the same reason: a client can be
# steerable without being turnable, and the two must be able to differ.
LOOK_CAPABILITY: Final = "control.look.v1"
# And using what is in front of it, its own capability for the same reason again:
# a client can be steerable and turnable without being allowed to touch anything,
# and that is the capability that lets a Kin act on the world rather than only
# move through it.
USE_CAPABILITY: Final = "control.use.v1"
# S2's five action surfaces and its one observation surface, each its own cell of
# the negotiation table for the reason the table already states: a client that can
# turn may not be allowed to break, one that can break may not be allowed to
# touch a GUI, and observation is read-only and switches apart from all of them.
AIM_CAPABILITY: Final = "control.aim.v1"
MINE_CAPABILITY: Final = "control.mine.v1"
HOTBAR_CAPABILITY: Final = "control.hotbar.v1"
SCREEN_CAPABILITY: Final = "control.screen.v1"
RESPAWN_CAPABILITY: Final = "control.respawn.v1"
GUI_CAPABILITY: Final = "control.gui.v1"
OBSERVE_WORLD_CAPABILITY: Final = "observe.world.v1"
# Publishing the world the client is hosting is not an input skill and is not
# named like one: it is a lifecycle operation on the server in this same process,
# which is why it is the one capability the boundary contract lets the Bridge's
# host adapter touch. It is negotiated like the others, because a client can be
# steerable, turnable and able to use things without being able to host at all.
HOST_LAN_CAPABILITY: Final = "host.lan.v1"

#: S2's whole surface in one set, because whether it may be offered at all is a
#: question about the Bridge that is on the other end of the socket, not about
#: Core. The hello proof covers the offered set, so an offer that added these to
#: every session would also claim them for a root that refuses them — the reviewed
#: per-version answer lives in `adapters/launcher/recipe.py` and the contract test
#: `test_the_baseline_carries_no_s2_surface_yet` pins it against both roots' source.
WORLD_ACTION_CAPABILITIES: Final = frozenset(
    {
        AIM_CAPABILITY,
        MINE_CAPABILITY,
        HOTBAR_CAPABILITY,
        SCREEN_CAPABILITY,
        GUI_CAPABILITY,
        OBSERVE_WORLD_CAPABILITY,
    }
)

#: What every reviewed Bridge routes, S1's full set. A session that offers more
#: than this is offering something its own Bridge refuses, so the additions are
#: never in the default.
BASELINE_CAPABILITIES: Final = frozenset(
    {
        HANDSHAKE_CAPABILITY,
        ADMISSION_CAPABILITY,
        MOVE_CAPABILITY,
        LOOK_CAPABILITY,
        USE_CAPABILITY,
        HOST_LAN_CAPABILITY,
    }
)

# The commands themselves, one name per thing a Kin may ask the client to do.
# These are the envelope's `message_type`, so they are what a run document
# searches for and what the capability table is keyed by.
CONNECT_WORLD_TYPE: Final = "minekin.v1.ConnectWorld"
CANCEL_CONNECTION_TYPE: Final = "minekin.v1.CancelConnection"
RELEASE_ALL_INPUTS_TYPE: Final = "minekin.v1.ReleaseAllInputs"
OPEN_LAN_TYPE: Final = "minekin.v1.OpenLan"
MOVE_INPUT_TYPE: Final = "minekin.v1.MoveInput"
LOOK_INPUT_TYPE: Final = "minekin.v1.LookInput"
USE_INPUT_TYPE: Final = "minekin.v1.UseInput"
AIM_INPUT_TYPE: Final = "minekin.v1.AimInput"
MINE_INPUT_TYPE: Final = "minekin.v1.MineInput"
HOTBAR_SELECT_INPUT_TYPE: Final = "minekin.v1.HotbarSelectInput"
SCREEN_INPUT_TYPE: Final = "minekin.v1.ScreenInput"
RESPAWN_INPUT_TYPE: Final = "minekin.v1.RespawnInput"
GUI_CLICK_INPUT_TYPE: Final = "minekin.v1.GuiClickInput"

#: The stable refusal token for a command whose capability was never negotiated.
#: Named because the S2 contract asks that both gates — Core's sender and the
#: Bridge's receiver — refuse under the same word, and an untestable "gate has a
#: name" is a comment.
CAPABILITY_NOT_GRANTED: Final = "CAPABILITY_NOT_GRANTED"


def monotonic_ns() -> int:
    """The clock every outbound deadline is expressed in.

    Public because a deadline Core puts *inside* a message has to be computed on
    the same clock as the `monotonic_ns` of the envelope that carries it — that
    difference is the only duration two processes without a shared origin can
    agree on — and two definitions of "now" would silently stop being the same
    clock. The `max(1, …)` keeps a deadline distinct from an absent field: zero
    on the wire means nobody set it.
    """

    return max(1, time.monotonic_ns())
