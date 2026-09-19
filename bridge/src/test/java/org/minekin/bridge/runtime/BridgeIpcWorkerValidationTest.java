package org.minekin.bridge.runtime;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertThrows;

import io.minekin.protocol.v1.ConnectWorld;
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
}
