package org.minekin.bridge.runtime;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import io.minekin.protocol.v1.ConnectWorld;
import io.minekin.protocol.v1.RespawnInput;
import io.minekin.protocol.v1.SayInput;
import io.minekin.protocol.v1.LookInput;
import io.minekin.protocol.v1.MoveInput;
import io.minekin.protocol.v1.ReleaseAllInputs;
import org.minekin.bridge.input.BridgeInputController;
import java.io.IOException;
import java.net.SocketTimeoutException;
import org.junit.jupiter.api.Test;

final class BridgeIpcWorkerValidationTest {
    @Test
    void releaseRequiresBoundedIdentityGenerationAndReason() {
        assertDoesNotThrow(() -> BridgeIpcWorker.validateRelease(release("release-1", 1, "EXPLICIT")));
        assertThrows(
                IOException.class,
                () -> BridgeIpcWorker.validateRelease(release("", 1, "EXPLICIT")));
        assertThrows(
                IOException.class,
                () -> BridgeIpcWorker.validateRelease(release("release-1", 0, "EXPLICIT")));
        assertThrows(
                IOException.class,
                () -> BridgeIpcWorker.validateRelease(release("release-1", 1, "bad\nreason")));
        assertThrows(
                IOException.class,
                () -> BridgeIpcWorker.validateRelease(release("x".repeat(129), 1, "EXPLICIT")));
    }

    @Test
    void theConnectDeadlineIsMeasuredAgainstTheStampThatCarriesIt() {
        long received = 1_000_000_000L;

        assertDoesNotThrow(
                () ->
                        BridgeIpcWorker.validateConnectDeadline(
                                connect(received + 5_000_000_000L), received));
    }

    @Test
    void aConnectCommandThatExpiredBeforeItWasReadIsRefused() {
        long received = 1_000_000_000L;

        // Exactly at the deadline is already too late: the client would be told
        // to connect at the instant Core stopped meaning it.
        assertThrows(
                IOException.class,
                () -> BridgeIpcWorker.validateConnectDeadline(connect(received), received));
        assertThrows(
                IOException.class,
                () -> BridgeIpcWorker.validateConnectDeadline(connect(received - 1), received));
    }

    @Test
    void aDeadlineThatIsNotAClaimedDurationIsRefused() {
        // A uint64 that does not fit a signed long, read as a huge deadline, must
        // not wrap around into "still in the future".
        assertThrows(
                IOException.class,
                () ->
                        BridgeIpcWorker.validateConnectDeadline(
                                connect(Long.MIN_VALUE), Long.MAX_VALUE));
    }

    private static ConnectWorld connect(long deadlineMonotonicNs) {
        return ConnectWorld.newBuilder().setDeadlineMonotonicNs(deadlineMonotonicNs).build();
    }

    private static ReleaseAllInputs release(String actionId, long generation, String reason) {
        return ReleaseAllInputs.newBuilder()
                .setActionId(actionId)
                .setGeneration(generation)
                .setReasonCode(reason)
                .build();
    }

    @Test
    void aMoveCommandWithoutIdentityIsRefusedBeforeItReachesTheClient() {
        assertDoesNotThrow(() -> BridgeIpcWorker.validateMove(move("walk-1", 1, "lease-1", 1f, 0f)));

        assertThrows(
                IllegalArgumentException.class,
                () -> BridgeIpcWorker.validateMove(move("", 1, "lease-1", 1f, 0f)));
        assertThrows(
                IllegalArgumentException.class,
                () -> BridgeIpcWorker.validateMove(move("walk-1", 0, "lease-1", 1f, 0f)));
        assertThrows(
                IllegalArgumentException.class,
                () -> BridgeIpcWorker.validateMove(move("walk-1", 1, "", 1f, 0f)));
        assertThrows(
                IllegalArgumentException.class,
                () -> BridgeIpcWorker.validateMove(move("x".repeat(129), 1, "lease-1", 1f, 0f)));
    }

    @Test
    void anAxisThatIsNotAnAxisIsRefusedRatherThanClamped() {
        // NaN compares false against every bound, so a naive range check lets it
        // through — and a NaN axis is a command nobody meant.
        assertThrows(
                IllegalArgumentException.class,
                () -> BridgeIpcWorker.validateMove(move("walk-1", 1, "lease-1", Float.NaN, 0f)));
        assertThrows(
                IllegalArgumentException.class,
                () -> BridgeIpcWorker.validateMove(move("walk-1", 1, "lease-1", 1.5f, 0f)));
        assertThrows(
                IllegalArgumentException.class,
                () -> BridgeIpcWorker.validateMove(
                        move("walk-1", 1, "lease-1", 0f, Float.POSITIVE_INFINITY)));
    }

    @Test
    void aMoveDeadlineIsRestatedInThisClockWithoutChangingItsDuration() {
        long received = 1_000_000_000L;
        // The envelope stamp and the deadline are Core's clock; the difference is
        // the only thing two clocks can agree on.
        MoveInput translated = BridgeIpcWorker.onLocalClock(moveAt(received + 5_000_000_000L), received);
        long localRemaining = translated.getDeadlineMonotonicNs() - BridgeIpcWorker.monotonicNow();

        assertTrue(localRemaining > 0, "a command five seconds out must still be in the future");
        assertTrue(localRemaining <= 5_000_000_000L, "and it must not have grown");
        assertTrue(localRemaining > 4_000_000_000L, "and it must not have shrunk");
    }

    @Test
    void aMoveThatExpiredIsRestatedInThePastRatherThanThrown() {
        long received = 1_000_000_000L;

        // A late command is not a broken one: the controller refuses it with a
        // code Core can record, which is a different outcome from failing closed.
        MoveInput late = BridgeIpcWorker.onLocalClock(moveAt(received), received);
        assertTrue(late.getDeadlineMonotonicNs() < BridgeIpcWorker.monotonicNow());
        assertTrue(BridgeIpcWorker.onLocalClock(moveAt(received - 1), received)
                .getDeadlineMonotonicNs()
                < BridgeIpcWorker.monotonicNow());
    }

    @Test
    void aMoveWithoutADeadlineIsLeftWithoutOne() {
        assertSame(0L, BridgeIpcWorker.onLocalClock(moveAt(0), 1_000_000_000L).getDeadlineMonotonicNs());
    }

    private static MoveInput move(
            String actionId, long generation, String leaseId, float forward, float strafe) {
        return MoveInput.newBuilder()
                .setActionId(actionId)
                .setGeneration(generation)
                .setLeaseId(leaseId)
                .setForward(forward)
                .setStrafe(strafe)
                .build();
    }

    private static MoveInput moveAt(long deadlineMonotonicNs) {
        return move("walk-1", 1, "lease-1", 1f, 0f).toBuilder()
                .setDeadlineMonotonicNs(deadlineMonotonicNs)
                .build();
    }

    @Test
    void theKeysComeUpLongBeforeTheClientIsStopped() {
        // The two responses to a silent Core are ordered, and the order is the
        // whole point: at the same tolerance the release never happens, because
        // stopping the client wins the race. Measured — two seconds of silence
        // stopped the client and the contract's release never ran.
        assertTrue(
                BridgeIpcWorker.INPUT_MISSED_HEARTBEATS < BridgeIpcWorker.CORE_ABSENT_INTERVALS,
                "the input watchdog must lapse strictly before the transport gives up");
    }

    @Test
    void aLookWithoutIdentityOrWithAnImpossibleTurnIsRefused() {
        assertDoesNotThrow(() -> BridgeIpcWorker.validateLook(look("look-1", 1, "lease-1", 90f, 0f)));

        assertThrows(
                IllegalArgumentException.class,
                () -> BridgeIpcWorker.validateLook(look("", 1, "lease-1", 90f, 0f)));
        assertThrows(
                IllegalArgumentException.class,
                () -> BridgeIpcWorker.validateLook(look("look-1", 0, "lease-1", 90f, 0f)));
        assertThrows(
                IllegalArgumentException.class,
                () -> BridgeIpcWorker.validateLook(look("look-1", 1, "", 90f, 0f)));
        assertThrows(
                IllegalArgumentException.class,
                () -> BridgeIpcWorker.validateLook(look("look-1", 1, "lease-1", Float.NaN, 0f)));
        assertThrows(
                IllegalArgumentException.class,
                () -> BridgeIpcWorker.validateLook(
                        look("look-1", 1, "lease-1", 0f, Float.POSITIVE_INFINITY)));
    }

    @Test
    void aLookDeadlineIsRestatedInThisClockTheSameWay() {
        long received = 1_000_000_000L;

        LookInput translated = BridgeIpcWorker.onLocalClock(
                look("look-1", 1, "lease-1", 90f, 0f).toBuilder()
                        .setDeadlineMonotonicNs(received + 5_000_000_000L)
                        .build(),
                received);
        long localRemaining = translated.getDeadlineMonotonicNs() - BridgeIpcWorker.monotonicNow();

        assertTrue(localRemaining > 4_000_000_000L && localRemaining <= 5_000_000_000L);
        // And a look that expired is restated in the past rather than thrown on,
        // for the same reason a late movement command is: not turning is safe.
        assertTrue(
                BridgeIpcWorker.onLocalClock(
                                look("look-1", 1, "lease-1", 90f, 0f).toBuilder()
                                        .setDeadlineMonotonicNs(received)
                                        .build(),
                                received)
                        .getDeadlineMonotonicNs()
                        < BridgeIpcWorker.monotonicNow());
    }

    private static LookInput look(
            String actionId, long generation, String leaseId, float yaw, float pitch) {
        return LookInput.newBuilder()
                .setActionId(actionId)
                .setGeneration(generation)
                .setLeaseId(leaseId)
                .setDeltaYawDegrees(yaw)
                .setDeltaPitchDegrees(pitch)
                .build();
    }

    @Test
    void aChannelThatWentAwayIsNotABridgeFault() {
        // The two are different facts about a run and the release reason says which:
        // a Core whose socket closed is not a Bridge that broke, and a log that calls
        // both BRIDGE_FAULT sends an operator to look at the wrong process.
        assertEquals(
                BridgeInputController.ReleaseReason.IPC_LOST,
                BridgeIpcWorker.reasonFor(new BridgeIpcWorker.IpcLost(new IOException("closed"))));
        assertEquals(
                BridgeInputController.ReleaseReason.IPC_LOST,
                BridgeIpcWorker.reasonFor(new SocketTimeoutException("stopped answering")));
    }

    @Test
    void everyOtherWayOfFailingClosedIsTheBridgesOwnFault() {
        // A gate refusing a message, a parse failure, and a bug are all the Bridge
        // declining to go on with something it was sent or something it did.
        assertEquals(
                BridgeInputController.ReleaseReason.BRIDGE_FAULT,
                BridgeIpcWorker.reasonFor(new IllegalArgumentException("bad MoveInput")));
        assertEquals(
                BridgeInputController.ReleaseReason.BRIDGE_FAULT,
                BridgeIpcWorker.reasonFor(new IOException("not the transport")));
        assertEquals(
                BridgeInputController.ReleaseReason.BRIDGE_FAULT,
                BridgeIpcWorker.reasonFor(new IllegalStateException("an invariant broke")));
    }
    @Test
    void respawnRequiresBoundedIdentityGenerationAndADeadline() {
        RespawnInput valid = RespawnInput.newBuilder()
                .setActionId("respawn-1").setLeaseId("lease-1")
                .setGeneration(1).setDeadlineMonotonicNs(10_000).build();
        assertDoesNotThrow(() -> BridgeIpcWorker.validateRespawn(valid));
        for (RespawnInput invalid : new RespawnInput[] {
            valid.toBuilder().setActionId("").build(),
            valid.toBuilder().setLeaseId("").build(),
            valid.toBuilder().setActionId("x".repeat(129)).build(),
            valid.toBuilder().setGeneration(0).build(),
            valid.toBuilder().setDeadlineMonotonicNs(0).build()
        }) {
            assertThrows(IllegalArgumentException.class,
                    () -> BridgeIpcWorker.validateRespawn(invalid));
        }
    }

    @Test
    void sayRequiresBoundedIdentityGenerationAndADeadline() {
        SayInput valid = SayInput.newBuilder()
                .setActionId("say-1").setLeaseId("lease-1")
                .setGeneration(1).setDeadlineMonotonicNs(10_000).setText("hello").build();
        assertDoesNotThrow(() -> BridgeIpcWorker.validateSay(valid));
        for (SayInput invalid : new SayInput[] {
            valid.toBuilder().setActionId("").build(),
            valid.toBuilder().setLeaseId("").build(),
            valid.toBuilder().setGeneration(0).build(),
            valid.toBuilder().setDeadlineMonotonicNs(0).build()
        }) {
            assertThrows(IllegalArgumentException.class,
                    () -> BridgeIpcWorker.validateSay(invalid));
        }
    }

    @Test
    void aSayLineIsRefusedUnlessItIsSpeech() {
        assertEquals("", BridgeIpcWorker.sayRefusal("hello there"));
        assertEquals("", BridgeIpcWorker.sayRefusal("  leading spaces are still speech"));
        assertEquals("", BridgeIpcWorker.sayRefusal("x".repeat(BridgeIpcWorker.SAY_MAX_CHARS)));
        assertEquals("SAY_TEXT_EMPTY", BridgeIpcWorker.sayRefusal("   "));
        assertEquals("SAY_TEXT_EMPTY", BridgeIpcWorker.sayRefusal(null));
        assertEquals("SAY_TEXT_TOO_LONG",
                BridgeIpcWorker.sayRefusal("x".repeat(BridgeIpcWorker.SAY_MAX_CHARS + 1)));
        assertEquals("SAY_TEXT_IS_A_COMMAND", BridgeIpcWorker.sayRefusal("/kill"));
        assertEquals("SAY_TEXT_IS_A_COMMAND", BridgeIpcWorker.sayRefusal("   /tp 0 0"));
    }

    @Test
    void everyInputTypeTheControlLoopDispatchesIsAllowedOnTheControlChannel() {
        // One entry per dispatch branch in `heartbeatLoop`. A bounds check that passes
        // is not enough: a type the loop handles but the envelope allowlist omits is
        // refused by `EnvelopeGate.validate` before the branch runs, and the client is
        // stopped with a generic BRIDGE_FAULT that cannot say which frame did it. That
        // is how RespawnInput's first live send ended a run whose branch, capability,
        // bounds check and Java test all existed (2026-10-05) — only this list was
        // never told. Add the type here when you add the branch, or this fails.
        assertTrue(
                BridgeIpcWorker.controlEnvelopeTypes()
                        .containsAll(
                                java.util.List.of(
                                        BridgeIpcWorker.CORE_HELLO_TYPE,
                                        BridgeIpcWorker.HEARTBEAT_TYPE,
                                        BridgeIpcWorker.CONNECT_WORLD_TYPE,
                                        BridgeIpcWorker.CANCEL_CONNECTION_TYPE,
                                        BridgeIpcWorker.OPEN_LAN_TYPE,
                                        BridgeIpcWorker.RELEASE_ALL_INPUTS_TYPE,
                                        BridgeIpcWorker.MOVE_INPUT_TYPE,
                                        BridgeIpcWorker.LOOK_INPUT_TYPE,
                                        BridgeIpcWorker.USE_INPUT_TYPE,
                                        BridgeIpcWorker.AIM_INPUT_TYPE,
                                        BridgeIpcWorker.MINE_INPUT_TYPE,
                                        BridgeIpcWorker.HOTBAR_SELECT_INPUT_TYPE,
                                        BridgeIpcWorker.RESPAWN_INPUT_TYPE,
                                        BridgeIpcWorker.SAY_INPUT_TYPE,
                                        BridgeIpcWorker.SCREEN_INPUT_TYPE,
                                        BridgeIpcWorker.GUI_CLICK_INPUT_TYPE)));
    }

}
