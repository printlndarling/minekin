package org.minekin.bridge.protocol;

import io.minekin.protocol.v1.Channel;
import io.minekin.protocol.v1.Envelope;
import java.util.Objects;
import java.util.Set;

/** Stateful, per-connection validation for untrusted IPC envelopes. */
public final class EnvelopeGate {
    private final Expected expected;
    private final Channel channel;
    private final Set<String> allowedMessageTypes;
    private long nextSequence = 1;

    public EnvelopeGate(Expected expected, Channel channel, Set<String> allowedMessageTypes) {
        this.expected = Objects.requireNonNull(expected, "expected");
        this.channel = Objects.requireNonNull(channel, "channel");
        this.allowedMessageTypes = Set.copyOf(allowedMessageTypes);
        if (channel == Channel.CHANNEL_UNSPECIFIED || this.allowedMessageTypes.isEmpty()) {
            throw new IllegalArgumentException("channel and message allowlist are required");
        }
    }

    public synchronized void validate(Envelope envelope) {
        Objects.requireNonNull(envelope, "envelope");
        boolean valid = envelope.hasProtocol()
                && envelope.getProtocol().getMajor() == expected.protocolMajor()
                && envelope.getProtocol().getMinor() <= expected.protocolMinor()
                && envelope.getChannel() == channel
                && envelope.getSequence() == nextSequence
                && allowedMessageTypes.contains(envelope.getMessageType())
                && envelope.getKinId().equals(expected.kinId())
                && envelope.getSessionId().equals(expected.sessionId())
                && envelope.getGeneration() == expected.generation()
                && envelope.getClientInstanceId().equals(expected.clientInstanceId())
                && envelope.getMonotonicNs() > 0
                && !envelope.getPayload().isEmpty();
        if (!valid) {
            throw new IllegalArgumentException("IPC envelope violates the negotiated connection");
        }
        nextSequence++;
        if (nextSequence == 0) {
            throw new IllegalStateException("IPC sequence exhausted");
        }
    }

    public record Expected(
            int protocolMajor,
            int protocolMinor,
            String kinId,
            String sessionId,
            long generation,
            String clientInstanceId) {
        public Expected {
            if (protocolMajor < 1
                    || protocolMinor < 0
                    || generation < 1
                    || kinId == null
                    || kinId.isBlank()
                    || sessionId == null
                    || sessionId.isBlank()
                    || clientInstanceId == null
                    || clientInstanceId.isBlank()) {
                throw new IllegalArgumentException("envelope identity is incomplete");
            }
        }
    }
}
