package org.minekin.bridge.protocol;

import io.minekin.protocol.v1.CancelConnection;
import io.minekin.protocol.v1.ConnectWorld;
import io.minekin.protocol.v1.ConnectionCancelReason;
import io.minekin.protocol.v1.ResourcePackPolicy;
import java.util.Objects;
import java.util.Set;

/** Validates admission commands before they enter the Minecraft client thread. */
public final class AdmissionCommandGate {
    private long nextGeneration = 1;
    private long activeGeneration;

    public synchronized void acceptConnect(ConnectWorld command, Set<String> capabilities) {
        Objects.requireNonNull(command, "command");
        requireCapability(capabilities);
        boolean valid = activeGeneration == 0
                && command.getGeneration() == nextGeneration
                && !command.getRequestId().isBlank()
                && !command.getServerProfileId().isBlank()
                && command.getServerProfileRevision().matches("[0-9a-f]{64}")
                && isLoopback(command.getOriginalHost())
                && command.getPort() >= 1
                && command.getPort() <= 65535
                && command.getResourcePackPolicy() != ResourcePackPolicy.RESOURCE_PACK_POLICY_UNSPECIFIED
                && command.getDeadlineMonotonicNs() > 0;
        if (!valid) {
            throw new IllegalArgumentException("ConnectWorld violates the negotiated admission bounds");
        }
        activeGeneration = command.getGeneration();
        if (nextGeneration == Long.MAX_VALUE) {
            throw new IllegalStateException("connection generation exhausted the P0 signed range");
        }
        nextGeneration++;
    }

    public synchronized void acceptCancel(CancelConnection command, Set<String> capabilities) {
        Objects.requireNonNull(command, "command");
        requireCapability(capabilities);
        boolean valid = activeGeneration != 0
                && command.getGeneration() == activeGeneration
                && !command.getRequestId().isBlank()
                && command.getReason() != ConnectionCancelReason.CONNECTION_CANCEL_REASON_UNSPECIFIED;
        if (!valid) {
            throw new IllegalArgumentException("CancelConnection does not name the active generation");
        }
        // Invalidate synchronously on the IPC thread before the client thread
        // receives the command and closes its channel/network handler.
        activeGeneration = 0;
    }

    public synchronized long activeGeneration() {
        return activeGeneration;
    }

    private static void requireCapability(Set<String> capabilities) {
        Objects.requireNonNull(capabilities, "capabilities");
        if (!capabilities.contains(HandshakeGate.ADMISSION_CAPABILITY)) {
            throw new IllegalArgumentException("admission capability was not negotiated");
        }
    }

    private static boolean isLoopback(String host) {
        return "127.0.0.1".equals(host) || "::1".equals(host);
    }
}
