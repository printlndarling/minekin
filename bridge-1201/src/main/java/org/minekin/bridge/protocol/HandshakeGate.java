package org.minekin.bridge.protocol;

import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.HexFormat;
import java.util.Objects;
import java.util.Set;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import org.minekin.bridge.runtime.BridgePhaseMachine;

/** Validates the immutable W20 handshake before entering OBSERVE_ONLY. */
public final class HandshakeGate {
    public static final String HANDSHAKE_CAPABILITY = "session.handshake.v1";
    public static final String ADMISSION_CAPABILITY = "admission.connect.v1";
    /**
     * The capability that authorises movement, named by the contract's
     * {@code control.<skill>.v1} convention. A client can be admitted to a world
     * without being steerable, and the negotiation is what keeps those two apart.
     */
    public static final String MOVE_CAPABILITY = "control.move.v1";
    /**
     * And looking, which is its own capability for the same reason: a client can
     * be steerable without being turnable, and the negotiation is what keeps
     * those two apart.
     */
    public static final String LOOK_CAPABILITY = "control.look.v1";
    // And using what is in front of it: the capability that lets a Kin act on the
    // world rather than only move through it.
    public static final String USE_CAPABILITY = "control.use.v1";
    // And publishing the world this client is hosting. Not an input skill, so not
    // named like one: it is the one lifecycle operation on the integrated server
    // that the boundary contract lets the Bridge's host adapter reach for, and a
    // client can be steerable, turnable and able to use things without being able
    // to host anything at all.
    public static final String HOST_LAN_CAPABILITY = "host.lan.v1";
    public static final int MIN_FRAME_BYTES = 1024;
    public static final int MAX_FRAME_BYTES = 16 * 1024 * 1024;

    private final Expected expected;
    private final BridgePhaseMachine phases;
    private boolean consumed;

    public HandshakeGate(Expected expected, BridgePhaseMachine phases) {
        this.expected = Objects.requireNonNull(expected, "expected");
        this.phases = Objects.requireNonNull(phases, "phases");
    }

    public BridgeHelloData bridgeHello() {
        byte[] proof = hmac(expected.sessionKey(), proofContext(expected));
        return new BridgeHelloData(
                expected.protocolMajor(),
                expected.protocolMinor(),
                expected.kinId(),
                expected.sessionId(),
                expected.generation(),
                expected.clientInstanceId(),
                expected.bundleDigest(),
                expected.bridgeDigest(),
                expected.minecraftVersion(),
                expected.fabricLoaderVersion(),
                HexFormat.of().formatHex(expected.launchNonce()),
                expected.capabilities(),
                HexFormat.of().formatHex(proof));
    }

    public synchronized boolean accept(CoreHelloData coreHello) {
        Objects.requireNonNull(coreHello, "coreHello");
        String expectedProof = proofForCoreHello(coreHello);
        boolean valid = !consumed
                && phases.phase() == BridgePhaseMachine.Phase.IPC_CONNECTING
                && coreHello.protocolMajor() == expected.protocolMajor()
                && coreHello.protocolMinor() <= expected.protocolMinor()
                && MessageDigest.isEqual(
                        coreHello.sessionId().getBytes(StandardCharsets.UTF_8),
                        expected.sessionId().getBytes(StandardCharsets.UTF_8))
                && coreHello.generation() == expected.generation()
                && expected.capabilities().containsAll(coreHello.acceptedCapabilities())
                && coreHello.acceptedCapabilities().contains(HANDSHAKE_CAPABILITY)
                && coreHello.heartbeatIntervalMs() >= 100
                && coreHello.heartbeatIntervalMs() <= 10_000
                && coreHello.maxFrameBytes() >= MIN_FRAME_BYTES
                && coreHello.maxFrameBytes() <= MAX_FRAME_BYTES
                && coreHello.proof().matches("[0-9a-f]{64}")
                && MessageDigest.isEqual(
                        coreHello.proof().getBytes(StandardCharsets.US_ASCII),
                        expectedProof.getBytes(StandardCharsets.US_ASCII));
        consumed = true;
        if (!valid) {
            phases.safeStop();
            return false;
        }
        phases.transition(BridgePhaseMachine.Phase.OBSERVE_ONLY);
        return true;
    }

    public String proofForCoreHello(CoreHelloData value) {
        Objects.requireNonNull(value, "value");
        String capabilities = value.acceptedCapabilities().stream().sorted().reduce(
                (left, right) -> left + "," + right).orElse("");
        String context = String.join(
                "\0",
                "minekin-core-hello-v1",
                Integer.toString(value.protocolMajor()),
                Integer.toString(value.protocolMinor()),
                value.sessionId(),
                Long.toUnsignedString(value.generation()),
                capabilities,
                Integer.toString(value.heartbeatIntervalMs()),
                Integer.toString(value.maxFrameBytes()),
                HexFormat.of().formatHex(expected.launchNonce()));
        return HexFormat.of().formatHex(
                hmac(expected.sessionKey(), context.getBytes(StandardCharsets.UTF_8)));
    }

    private static byte[] proofContext(Expected value) {
        String capabilities = value.capabilities().stream().sorted().reduce(
                (left, right) -> left + "," + right).orElse("");
        String context = String.join(
                "\0",
                "minekin-bridge-hello-v1",
                Integer.toString(value.protocolMajor()),
                Integer.toString(value.protocolMinor()),
                value.kinId(),
                value.sessionId(),
                Long.toUnsignedString(value.generation()),
                value.clientInstanceId(),
                value.bundleDigest(),
                value.bridgeDigest(),
                value.minecraftVersion(),
                value.fabricLoaderVersion(),
                capabilities,
                HexFormat.of().formatHex(value.launchNonce()));
        return context.getBytes(StandardCharsets.UTF_8);
    }

    private static byte[] hmac(byte[] key, byte[] value) {
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(key, "HmacSHA256"));
            return mac.doFinal(value);
        } catch (GeneralSecurityException error) {
            throw new IllegalStateException("HmacSHA256 is unavailable", error);
        }
    }

    public record Expected(
            int protocolMajor,
            int protocolMinor,
            String kinId,
            String sessionId,
            long generation,
            String clientInstanceId,
            String bundleDigest,
            String bridgeDigest,
            String minecraftVersion,
            String fabricLoaderVersion,
            byte[] launchNonce,
            byte[] sessionKey,
            Set<String> capabilities) {
        public Expected {
            requireText(kinId, "kinId");
            requireText(sessionId, "sessionId");
            requireText(clientInstanceId, "clientInstanceId");
            requireDigest(bundleDigest, "bundleDigest");
            requireDigest(bridgeDigest, "bridgeDigest");
            if (!"1.21.4".equals(minecraftVersion) || !"0.16.9".equals(fabricLoaderVersion)) {
                throw new IllegalArgumentException("game and Loader versions must match p0-core");
            }
            if (protocolMajor < 1 || protocolMinor < 0 || generation < 1) {
                throw new IllegalArgumentException("protocol and generation must be positive");
            }
            if (launchNonce.length != 32 || sessionKey.length != 32) {
                throw new IllegalArgumentException("nonce and session key must be 256-bit");
            }
            launchNonce = Arrays.copyOf(launchNonce, launchNonce.length);
            sessionKey = Arrays.copyOf(sessionKey, sessionKey.length);
            capabilities = Set.copyOf(capabilities);
            if (!capabilities.contains(HANDSHAKE_CAPABILITY)) {
                throw new IllegalArgumentException("handshake capability is mandatory");
            }
        }

        @Override
        public byte[] launchNonce() {
            return Arrays.copyOf(launchNonce, launchNonce.length);
        }

        @Override
        public byte[] sessionKey() {
            return Arrays.copyOf(sessionKey, sessionKey.length);
        }

        private static void requireText(String value, String field) {
            if (value == null || value.isBlank()) {
                throw new IllegalArgumentException(field + " is required");
            }
        }

        private static void requireDigest(String value, String field) {
            requireText(value, field);
            if (!value.matches("[0-9a-f]{64}")) {
                throw new IllegalArgumentException(field + " must be lowercase SHA-256");
            }
        }
    }

    public record BridgeHelloData(
            int protocolMajor,
            int protocolMinor,
            String kinId,
            String sessionId,
            long generation,
            String clientInstanceId,
            String bundleDigest,
            String bridgeDigest,
            String minecraftVersion,
            String fabricLoaderVersion,
            String launchNonce,
            Set<String> capabilities,
            String proof) {}

    public record CoreHelloData(
            int protocolMajor,
            int protocolMinor,
            String sessionId,
            long generation,
            Set<String> acceptedCapabilities,
            int heartbeatIntervalMs,
            int maxFrameBytes,
            String proof) {
        public CoreHelloData {
            Objects.requireNonNull(sessionId, "sessionId");
            acceptedCapabilities = Set.copyOf(acceptedCapabilities);
            Objects.requireNonNull(proof, "proof");
        }
    }
}
