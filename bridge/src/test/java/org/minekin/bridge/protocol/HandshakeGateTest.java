package org.minekin.bridge.protocol;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.util.List;
import org.junit.jupiter.api.Test;

/**
 * The capability strings are wire names, and both languages have to spell them the
 * same way.
 *
 * <p>They are carried literally in the handshake: Core advertises what it accepts and
 * the Bridge refuses a command whose capability was never negotiated. A rename on one
 * side is therefore not a refactor but a command that stops arriving — and it would
 * arrive as silence, because a capability that never matches is a check that never
 * passes rather than an error anybody sees. Pinning the strings here means a rename
 * has to be made twice on purpose.
 */
final class HandshakeGateTest {

    @Test
    void everyCapabilityIsTheNameTheOtherSideUses() {
        assertEquals(
                List.of(
                        "session.handshake.v1",
                        "admission.connect.v1",
                        "control.move.v1",
                        "control.look.v1",
                        "control.use.v1",
                        "host.lan.v1"),
                List.of(
                        HandshakeGate.HANDSHAKE_CAPABILITY,
                        HandshakeGate.ADMISSION_CAPABILITY,
                        HandshakeGate.MOVE_CAPABILITY,
                        HandshakeGate.LOOK_CAPABILITY,
                        HandshakeGate.USE_CAPABILITY,
                        HandshakeGate.HOST_LAN_CAPABILITY));
    }
}
