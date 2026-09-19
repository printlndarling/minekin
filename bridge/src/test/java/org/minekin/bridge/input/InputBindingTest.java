package org.minekin.bridge.input;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.Arrays;
import java.util.List;
import java.util.Optional;
import org.junit.jupiter.api.Test;

/** The capability names are wire vocabulary, so they are pinned here. */
final class InputBindingTest {

    @Test
    void everyCapabilityTheBridgeDrivesRoundTrips() {
        for (InputBinding binding : InputBinding.values()) {
            assertEquals(
                    Optional.of(binding),
                    InputBinding.of(binding.capability()),
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
                        "move.sneak",
                        "use.hand"),
                Arrays.stream(InputBinding.values()).map(InputBinding::capability).toList());
    }

    @Test
    void aCapabilityTheBridgeDoesNotDriveIsNotInvented() {
        assertTrue(InputBinding.of("look.yaw").isEmpty());
        assertTrue(InputBinding.of("move.forward ").isEmpty());
        assertTrue(InputBinding.of("").isEmpty());
        assertTrue(InputBinding.of(null).isEmpty());
    }
}
