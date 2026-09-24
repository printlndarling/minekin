package org.minekin.bridge.input;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import org.junit.jupiter.api.Test;

/** The ledger of what this Bridge has pressed. */
final class InputOwnershipTest {

    @Test
    void pressingTwiceReportsThatNothingChanged() {
        InputOwnership ownership = new InputOwnership(1);

        assertTrue(ownership.press(BridgeInputController.FORWARD));
        assertFalse(
                ownership.press(BridgeInputController.FORWARD),
                "a caller that presses again must be able to tell that it did nothing");
        assertEquals(1, ownership.size());
    }

    @Test
    void releasingSomethingNotHeldReportsThatNothingChanged() {
        InputOwnership ownership = new InputOwnership(1);

        assertFalse(ownership.release(BridgeInputController.FORWARD));
        ownership.press(BridgeInputController.FORWARD);
        assertTrue(ownership.release(BridgeInputController.FORWARD));
        assertFalse(ownership.holds(BridgeInputController.FORWARD));
    }

    @Test
    void releaseAllReportsWhatWasReleasedAndThenNothing() {
        InputOwnership ownership = new InputOwnership(1);
        ownership.press(BridgeInputController.SNEAK);
        ownership.press(BridgeInputController.FORWARD);

        List<String> released = ownership.releaseAll();

        // Reported, not merely cleared: what it held is what the client has to be
        // told to let go of.
        assertEquals(
                List.of(BridgeInputController.FORWARD, BridgeInputController.SNEAK), released);
        assertEquals(0, ownership.size());
        assertEquals(List.of(), ownership.releaseAll());
    }

    @Test
    void whatIsHeldIsACopyInAStableOrder() {
        InputOwnership ownership = new InputOwnership(1);
        ownership.press(BridgeInputController.RIGHT);
        ownership.press(BridgeInputController.JUMP);

        assertEquals(List.of(BridgeInputController.JUMP, BridgeInputController.RIGHT), ownership.held());

        List<String> snapshot = ownership.held();
        assertThrows(UnsupportedOperationException.class, () -> snapshot.add("move.other"));
        assertEquals(2, ownership.size());
    }

    @Test
    void aCapabilityWithNoNameIsRefused() {
        InputOwnership ownership = new InputOwnership(1);

        assertThrows(IllegalArgumentException.class, () -> ownership.press(" "));
        assertThrows(IllegalArgumentException.class, () -> ownership.release(null));
    }

    @Test
    void theLedgerBelongsToTheGenerationItWasMadeFor() {
        assertEquals(7L, new InputOwnership(7).generation());
    }
}
