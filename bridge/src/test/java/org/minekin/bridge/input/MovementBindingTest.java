package org.minekin.bridge.input;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.Arrays;
import java.util.List;
import java.util.Optional;
import org.junit.jupiter.api.Test;

/** The capability names are wire vocabulary, so they are pinned here. */
final class MovementBindingTest {

    @Test
    void everyCapabilityTheBridgeDrivesRoundTrips() {
        for (MovementBinding binding : MovementBinding.values()) {
            assertEquals(
                    Optional.of(binding),
                    MovementBinding.of(binding.capability()),
                    binding + " must be reachable by the name it is pressed under");
        }
    }

    @Test
    void theWireNamesAreTheReviewedOnes() {
        // Core and the Bridge have to agree on these strings, and a rename on one
        // side is a command that presses nothing at all — silently.
        assertEquals(
                List.of(
                        "move.forward",
                        "move.back",
                        "move.left",
                        "move.right",
                        "move.jump",
                        "move.sneak"),
                Arrays.stream(MovementBinding.values()).map(MovementBinding::capability).toList());
    }

    @Test
    void aCapabilityTheBridgeDoesNotDriveIsNotInvented() {
        assertTrue(MovementBinding.of("look.yaw").isEmpty());
        assertTrue(MovementBinding.of("move.forward ").isEmpty());
        assertTrue(MovementBinding.of("").isEmpty());
        assertTrue(MovementBinding.of(null).isEmpty());
    }
}
