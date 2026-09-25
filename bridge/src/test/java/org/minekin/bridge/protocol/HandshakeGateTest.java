package org.minekin.bridge.protocol;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import java.util.Set;
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

    private static final String DIGEST = "0".repeat(64);

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

    /**
     * A declaration has to match the recipe it is running against, or it is refused.
     *
     * <p>Root 1.21.4 is allowed to say exactly one pair of versions — the game and the
     * Loader it actually runs — because Core compares this hello against the reviewed
     * recipe for the session. The other root's pair is a different recipe entirely:
     * carrying {@code 1.20.1}/{@code 0.19.5} here would be a Bridge reporting an
     * intention rather than the truth, which is the false statement the identity
     * record exists to make impossible. So the pinned pair is accepted and that pair
     * is refused, on purpose.
     */
    @Test
    void onlyTheVersionPairThisRootActuallyRunsIsAccepted() {
        HandshakeGate.Expected pinned = expected("1.21.4", "0.16.9");
        assertEquals("1.21.4", pinned.minecraftVersion());
        assertEquals("0.16.9", pinned.fabricLoaderVersion());

        IllegalArgumentException refused =
                assertThrows(IllegalArgumentException.class, () -> expected("1.20.1", "0.19.5"));
        assertTrue(refused.getMessage().contains("p0-core"));
    }

    private static HandshakeGate.Expected expected(String game, String loader) {
        return new HandshakeGate.Expected(
                1,
                0,
                "kin-1",
                "session-1",
                1L,
                "instance-1",
                DIGEST,
                DIGEST,
                game,
                loader,
                new byte[32],
                new byte[32],
                Set.of(HandshakeGate.HANDSHAKE_CAPABILITY));
    }
}
