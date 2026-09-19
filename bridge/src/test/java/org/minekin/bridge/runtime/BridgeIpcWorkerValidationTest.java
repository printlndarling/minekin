package org.minekin.bridge.runtime;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertThrows;

import io.minekin.protocol.v1.ReleaseAllInputs;
import org.junit.jupiter.api.Test;

final class BridgeIpcWorkerValidationTest {
    @Test
    void releaseRequiresBoundedIdentityGenerationAndReason() {
        assertDoesNotThrow(() -> BridgeIpcWorker.validateRelease(release("release-1", 1, "EXPLICIT")));
        assertThrows(
                java.io.IOException.class,
                () -> BridgeIpcWorker.validateRelease(release("", 1, "EXPLICIT")));
        assertThrows(
                java.io.IOException.class,
                () -> BridgeIpcWorker.validateRelease(release("release-1", 0, "EXPLICIT")));
        assertThrows(
                java.io.IOException.class,
                () -> BridgeIpcWorker.validateRelease(release("release-1", 1, "bad\nreason")));
        assertThrows(
                java.io.IOException.class,
                () -> BridgeIpcWorker.validateRelease(release("x".repeat(129), 1, "EXPLICIT")));
    }

    private static ReleaseAllInputs release(String actionId, long generation, String reason) {
        return ReleaseAllInputs.newBuilder()
                .setActionId(actionId)
                .setGeneration(generation)
                .setReasonCode(reason)
                .build();
    }
}
