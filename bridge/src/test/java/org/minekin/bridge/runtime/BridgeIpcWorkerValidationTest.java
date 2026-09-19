package org.minekin.bridge.runtime;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import io.minekin.protocol.v1.ConnectWorld;
import io.minekin.protocol.v1.MoveInput;
import io.minekin.protocol.v1.ReleaseAllInputs;
import java.io.IOException;
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
}
