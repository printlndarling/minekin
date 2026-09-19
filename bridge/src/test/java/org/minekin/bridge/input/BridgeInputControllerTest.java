package org.minekin.bridge.input;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.Test;

/**
 * The whole Bridge-side input path, short of the client itself.
 *
 * <p>What the client does with a pressed key is verified on the controlled
 * runner. What is decidable here is everything the last-resort release depends
 * on: what is held, when it is let go, and what a command is allowed to do.
 */
final class BridgeInputControllerTest {

    private static final long INTERVAL = 1_000_000_000L;
    private static final int MISSES = 3;
    private static final long GENERATION = 4L;
    private static final long DEADLINE = 0L; // means "no deadline"

    private static final class RecordingSink implements KeySink {
        private final List<String> events = new ArrayList<>();

        @Override
        public void press(String capability) {
            events.add("press:" + capability);
        }

        @Override
        public void release(String capability) {
            events.add("release:" + capability);
        }
    }

    private static BridgeInputController controllerFor(RecordingSink sink) {
        return new BridgeInputController(sink, new InputWatchdog(INTERVAL, MISSES), GENERATION);
    }

    private static BridgeInputController.Outcome move(
            BridgeInputController controller,
            long nowNanos,
            float forward,
            float strafe,
            boolean jump,
            boolean sneak) {
        return controller.move(nowNanos, DEADLINE, GENERATION, forward, strafe, jump, sneak);
    }

    @Test
    void aCommandPressesTheKeysItAsksForAndNothingElse() {
        RecordingSink sink = new RecordingSink();
        BridgeInputController controller = controllerFor(sink);

        BridgeInputController.Outcome outcome = move(controller, INTERVAL, 1.0f, 0.0f, false, false);

        assertTrue(outcome.applied());
        assertEquals(List.of(BridgeInputController.FORWARD), outcome.held());
        assertEquals(List.of("press:move.forward"), sink.events);
    }

    @Test
    void repeatingACommandPressesNothingTheSecondTime() {
        RecordingSink sink = new RecordingSink();
        BridgeInputController controller = controllerFor(sink);

        move(controller, INTERVAL, 1.0f, 0.0f, true, false);
        move(controller, INTERVAL * 2, 1.0f, 0.0f, true, false);

        assertEquals(List.of("press:move.forward", "press:move.jump"), sink.events);
    }

    @Test
    void droppingAnAxisReleasesExactlyThatAxis() {
        RecordingSink sink = new RecordingSink();
        BridgeInputController controller = controllerFor(sink);
        move(controller, INTERVAL, 1.0f, 1.0f, true, true);

        BridgeInputController.Outcome outcome =
                move(controller, INTERVAL * 2, 1.0f, 0.0f, false, true);

        assertEquals(
                List.of(BridgeInputController.FORWARD, BridgeInputController.SNEAK), outcome.held());
        assertEquals(List.of("release:move.jump", "release:move.right"), sink.events.subList(4, 6));
    }

    @Test
    void reversingAnAxisPressesTheOppositeAndReleasesTheOriginal() {
        RecordingSink sink = new RecordingSink();
        BridgeInputController controller = controllerFor(sink);
        move(controller, INTERVAL, 1.0f, 0.0f, false, false);

        BridgeInputController.Outcome outcome =
                move(controller, INTERVAL * 2, -1.0f, 0.0f, false, false);

        assertEquals(List.of(BridgeInputController.BACK), outcome.held());
        assertEquals(
                List.of("press:move.forward", "press:move.back", "release:move.forward"),
                sink.events);
    }

    @Test
    void lettingGoReleasesEverythingTheLedgerHolds() {
        RecordingSink sink = new RecordingSink();
        BridgeInputController controller = controllerFor(sink);
        move(controller, INTERVAL, 1.0f, -1.0f, true, false);

        List<String> released = controller.releaseAll(BridgeInputController.ReleaseReason.IPC_LOST);

        // In the ledger's own order, which is sorted by capability name.
        assertEquals(
                List.of(
                        BridgeInputController.FORWARD,
                        BridgeInputController.JUMP,
                        BridgeInputController.LEFT),
                released);
        assertEquals(List.of(), controller.held());
        assertEquals(
                List.of("release:move.forward", "release:move.jump", "release:move.left"),
                sink.events.subList(3, 6));
        // The ledger, not the last command, is what gets released, so a second
        // release has nothing left to say.
        assertEquals(List.of(), controller.releaseAll(BridgeInputController.ReleaseReason.IPC_LOST));
    }

    @Test
    void silenceLongEnoughLetsGoOnceAndThenReportsNothingMore() {
        RecordingSink sink = new RecordingSink();
        BridgeInputController controller = controllerFor(sink);
        move(controller, INTERVAL, 1.0f, 0.0f, false, false);

        long expired = INTERVAL + INTERVAL * MISSES + 1;
        assertTrue(controller.tick(expired), "the tick that let go reports that it did");
        assertEquals(List.of(), controller.held());
        assertFalse(controller.tick(expired + INTERVAL), "and no later tick claims it again");
        assertFalse(controller.watchdogExpired(expired + INTERVAL));
    }

    @Test
    void quietButNotQuietEnoughKeepsTheKeysDown() {
        RecordingSink sink = new RecordingSink();
        BridgeInputController controller = controllerFor(sink);
        move(controller, INTERVAL, 1.0f, 0.0f, false, false);

        assertFalse(controller.tick(INTERVAL + INTERVAL * MISSES));
        assertEquals(List.of(BridgeInputController.FORWARD), controller.held());
    }

    @Test
    void hearingFromCoreAgainMakesInputPossibleAgain() {
        RecordingSink sink = new RecordingSink();
        BridgeInputController controller = controllerFor(sink);
        move(controller, INTERVAL, 1.0f, 0.0f, false, false);
        controller.tick(INTERVAL * 10);

        BridgeInputController.Outcome outcome = move(controller, INTERVAL * 11, 0.0f, 1.0f, false, false);

        assertTrue(outcome.applied(), "a fresh message is evidence Core is alive");
        assertEquals(List.of(BridgeInputController.RIGHT), outcome.held());
    }

    @Test
    void aCommandForAGenerationThatEndedIsRefusedAndPressesNothing() {
        RecordingSink sink = new RecordingSink();
        BridgeInputController controller = controllerFor(sink);

        BridgeInputController.Outcome outcome =
                controller.move(INTERVAL, DEADLINE, GENERATION - 1, 1.0f, 0.0f, false, false);

        assertFalse(outcome.applied());
        assertEquals(BridgeInputController.REFUSED_STALE_GENERATION, outcome.refusalCode());
        assertEquals(List.of(), sink.events);
    }

    @Test
    void aCommandPastItsDeadlineIsRefusedAndChangesNothing() {
        RecordingSink sink = new RecordingSink();
        BridgeInputController controller = controllerFor(sink);
        move(controller, INTERVAL, 1.0f, 0.0f, false, false);

        BridgeInputController.Outcome outcome =
                controller.move(
                        INTERVAL + 5, INTERVAL + 1, GENERATION, 0.0f, 0.0f, false, false);

        assertFalse(outcome.applied());
        assertEquals(BridgeInputController.REFUSED_DEADLINE_EXCEEDED, outcome.refusalCode());
        assertEquals(
                List.of(BridgeInputController.FORWARD),
                controller.held(),
                "a late command is not an instruction to let go of an earlier one; withdrawing "
                        + "is Core's decision, not this command's");
    }

    @Test
    void anAxisThatIsNotAReasonableNumberIsRefused() {
        RecordingSink sink = new RecordingSink();
        BridgeInputController controller = controllerFor(sink);

        for (float bad : new float[] {2.0f, -2.0f, Float.NaN, Float.POSITIVE_INFINITY}) {
            BridgeInputController.Outcome outcome = move(controller, INTERVAL, bad, 0.0f, false, false);
            assertFalse(outcome.applied(), "axis " + bad + " must be refused");
            assertEquals(BridgeInputController.REFUSED_MALFORMED, outcome.refusalCode());
        }

        assertEquals(List.of(), sink.events);
    }

    @Test
    void aNewGenerationInheritsNoKeyFromTheOneThatEnded() {
        RecordingSink sink = new RecordingSink();
        BridgeInputController controller = controllerFor(sink);
        move(controller, INTERVAL, 1.0f, 1.0f, true, true);

        List<String> released = controller.beginGeneration(GENERATION + 1);

        assertEquals(
                List.of(
                        BridgeInputController.FORWARD,
                        BridgeInputController.JUMP,
                        BridgeInputController.RIGHT,
                        BridgeInputController.SNEAK),
                released);
        assertEquals(List.of(), controller.held());
        assertEquals(GENERATION + 1, controller.generation());
        // And the new generation is the one commands are accepted for: the old
        // one is refused now, which is what makes the ledger's generation binding
        // more than bookkeeping.
        assertFalse(
                move(controller, INTERVAL * 2, 1.0f, 0.0f, false, false).applied(),
                "a command still naming the generation that ended must be refused");
        BridgeInputController.Outcome outcome =
                controller.move(INTERVAL * 3, DEADLINE, GENERATION + 1, 1.0f, 0.0f, false, false);
        assertTrue(outcome.applied());
        assertEquals(List.of(BridgeInputController.FORWARD), outcome.held());
    }

    @Test
    void aScreenTakingTheKeyboardLetsGoOfEverythingHeld() {
        RecordingSink sink = new RecordingSink();
        BridgeInputController controller = controllerFor(sink);
        move(controller, INTERVAL, 1.0f, 0.0f, true, false);
        assertEquals(
                List.of(BridgeInputController.FORWARD, BridgeInputController.JUMP),
                controller.held());

        assertTrue(controller.blockInput("DeathScreen"), "the call that let go says so");
        assertEquals(List.of(), controller.held());
        assertTrue(controller.inputBlocked());
        assertEquals("DeathScreen", controller.blockedBy());
        assertEquals(
                List.of(
                        "press:move.forward",
                        "press:move.jump",
                        "release:move.forward",
                        "release:move.jump"),
                sink.events);
    }

    @Test
    void aSecondReportOfTheSameScreenIsNotASecondRelease() {
        RecordingSink sink = new RecordingSink();
        BridgeInputController controller = controllerFor(sink);
        move(controller, INTERVAL, 1.0f, 0.0f, false, false);
        controller.blockInput("DeathScreen");
        List<String> after = List.copyOf(sink.events);

        assertFalse(controller.blockInput("DeathScreen"));
        assertEquals(after, sink.events, "nothing was held, and nothing happened");
    }

    @Test
    void aCommandForAClientThatIsNotTakingInputIsRefused() {
        RecordingSink sink = new RecordingSink();
        BridgeInputController controller = controllerFor(sink);
        controller.blockInput("PauseScreen");
        List<String> after = List.copyOf(sink.events);

        BridgeInputController.Outcome outcome = move(controller, INTERVAL, 1.0f, 0.0f, false, false);

        assertFalse(outcome.applied());
        assertEquals(BridgeInputController.REFUSED_GUI_CONFLICT, outcome.refusalCode());
        // Not pressed and not queued: a key pressed at a client that is not reading
        // its keyboard would still be down when it starts reading again.
        assertEquals(after, sink.events);
        assertEquals(List.of(), controller.held());
    }

    @Test
    void theClientTakingInputAgainPressesNothingBack() {
        RecordingSink sink = new RecordingSink();
        BridgeInputController controller = controllerFor(sink);
        move(controller, INTERVAL, 1.0f, 0.0f, false, false);
        controller.blockInput("PauseScreen");
        List<String> after = List.copyOf(sink.events);

        controller.unblockInput();

        assertFalse(controller.inputBlocked());
        assertEquals("", controller.blockedBy());
        assertEquals(after, sink.events, "a command is what presses a key, not a screen closing");

        // And the next command works, which is what makes unblocking mean anything.
        assertTrue(move(controller, INTERVAL * 2, 1.0f, 0.0f, false, false).applied());
        assertEquals(List.of(BridgeInputController.FORWARD), controller.held());
        assertEquals("press:move.forward", sink.events.get(sink.events.size() - 1));
    }

    @Test
    void lettingGoForAScreenStillLeavesALaterSilenceAbleToTimeOut() {
        RecordingSink sink = new RecordingSink();
        BridgeInputController controller = controllerFor(sink);
        move(controller, INTERVAL, 1.0f, 0.0f, false, false);
        controller.blockInput("PauseScreen");
        controller.unblockInput();
        move(controller, INTERVAL * 2, 1.0f, 0.0f, false, false);

        long expired = INTERVAL * 2 + INTERVAL * (MISSES + 1);
        assertTrue(controller.tick(expired), "the watchdog was re-armed by the new command");
        assertEquals(List.of(), controller.held());
    }
}
