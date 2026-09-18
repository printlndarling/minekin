import java.nio.ByteBuffer;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.function.Function;
import org.minekin.bridge.protocol.FrameCodec;
import org.minekin.bridge.protocol.HandshakeGate;
import org.minekin.bridge.runtime.BoundedChannel;
import org.minekin.bridge.runtime.BridgePhaseMachine;

public final class BridgeProtocolSelfTest {
    private static final Set<String> BASELINE_CAPABILITIES =
            Set.of("session.handshake.v1", "observation.lifecycle.v1");
    private static final int DEFAULT_HEARTBEAT_MS = 500;
    private static final int DEFAULT_MAX_FRAME_BYTES = 4 * 1024 * 1024;

    public static void main(String[] args) {
        framingIsNetworkOrderAndIncremental();
        oversizedFramesFailBeforeAllocation();
        queuesNeverBlockOrGrowPastTheirBound();
        phasesFailClosedAndNeverPermitInput();
        handshakeIsSingleUseAndIdentityBound();
        wrongNonceProtocolAndCapabilitiesAreRejected();
        handshakeBoundsAdmitOnlyTheAcceptedRange();
    }

    private static void framingIsNetworkOrderAndIncremental() {
        byte[] payload = new byte[] {1, 2, 3, 4, 5};
        ByteBuffer encoded = FrameCodec.encode(payload, 64);
        require(encoded.getInt() == payload.length, "network-order length prefix");
        encoded.rewind();
        FrameCodec.Decoder decoder = new FrameCodec.Decoder(64);
        List<byte[]> decoded = new ArrayList<>();
        while (encoded.hasRemaining()) {
            decoder.accept(ByteBuffer.wrap(new byte[] {encoded.get()}), decoded::add);
        }
        require(decoded.size() == 1, "exactly one fragmented frame");
        require(java.util.Arrays.equals(payload, decoded.get(0)), "payload round trip");
        require(!decoder.hasPartialFrame(), "decoder is at a frame boundary");
    }

    private static void oversizedFramesFailBeforeAllocation() {
        FrameCodec.Decoder decoder = new FrameCodec.Decoder(8);
        expectFailure(() -> decoder.accept(ByteBuffer.allocate(4).putInt(9).flip(), ignored -> {}));
        expectFailure(() -> FrameCodec.encode(new byte[0], 8));
    }

    private static void queuesNeverBlockOrGrowPastTheirBound() {
        BoundedChannel<String> queue = new BoundedChannel<>(2);
        require(queue.offer("one"), "first queue entry");
        require(queue.offer("two"), "second queue entry");
        require(!queue.offer("three"), "overflow is rejected");
        require(queue.size() == 2, "queue remains bounded");
        require(queue.rejectedCount() == 1, "overflow is observable");
        List<String> drained = new ArrayList<>();
        require(queue.drain(1, drained::add) == 1, "tick drain budget");
        require(drained.equals(List.of("one")), "FIFO handoff");
    }

    private static void phasesFailClosedAndNeverPermitInput() {
        BridgePhaseMachine phases = new BridgePhaseMachine();
        require(phases.phase() == BridgePhaseMachine.Phase.MOD_LOADED, "initial phase");
        phases.transition(BridgePhaseMachine.Phase.IPC_CONNECTING);
        phases.transition(BridgePhaseMachine.Phase.OBSERVE_ONLY);
        require(!phases.permitsInput(), "W20 stays read-only");
        expectFailure(() -> phases.transition(BridgePhaseMachine.Phase.PLAYABLE));
        phases.safeStop();
        require(phases.phase() == BridgePhaseMachine.Phase.SAFE_STOP, "safe stop is terminal");
    }

    private static void handshakeIsSingleUseAndIdentityBound() {
        HandshakeGate.Expected expected = expectedHandshake();
        BridgePhaseMachine phases = new BridgePhaseMachine();
        phases.transition(BridgePhaseMachine.Phase.IPC_CONNECTING);
        HandshakeGate gate = new HandshakeGate(expected, phases);
        require(gate.bridgeHello().proof().length() == 64, "HMAC proof is SHA-256 hex");
        require(gate.bridgeHello().launchNonce().length() == 64, "nonce is explicit 256-bit hex");
        var accepted = signed(
                gate,
                1,
                0,
                "session-01",
                4,
                BASELINE_CAPABILITIES,
                DEFAULT_HEARTBEAT_MS,
                DEFAULT_MAX_FRAME_BYTES);
        require(gate.accept(accepted), "matching Core hello");
        require(phases.phase() == BridgePhaseMachine.Phase.OBSERVE_ONLY, "observe-only activation");
        require(!gate.accept(accepted), "handshake cannot be replayed");
        require(phases.phase() == BridgePhaseMachine.Phase.SAFE_STOP, "replay is fail-closed");

        expectHandshakeRejected(expected, gate2 -> signed(
                gate2, 1, 0, "session-01", 5, BASELINE_CAPABILITIES,
                DEFAULT_HEARTBEAT_MS, DEFAULT_MAX_FRAME_BYTES));

        BridgePhaseMachine badProofPhases = new BridgePhaseMachine();
        badProofPhases.transition(BridgePhaseMachine.Phase.IPC_CONNECTING);
        HandshakeGate badProofGate = new HandshakeGate(expected, badProofPhases);
        var badProof = new HandshakeGate.CoreHelloData(
                1,
                0,
                "session-01",
                4,
                BASELINE_CAPABILITIES,
                DEFAULT_HEARTBEAT_MS,
                DEFAULT_MAX_FRAME_BYTES,
                "0".repeat(64));
        require(!badProofGate.accept(badProof), "invalid Core proof is rejected");
    }

    /** A wrong nonce, protocol revision, session or capability set must never reach OBSERVE_ONLY. */
    private static void wrongNonceProtocolAndCapabilitiesAreRejected() {
        HandshakeGate.Expected expected = expectedHandshake();

        expectHandshakeRejected(expected, gate -> signed(
                gate, 2, 0, "session-01", 4, BASELINE_CAPABILITIES,
                DEFAULT_HEARTBEAT_MS, DEFAULT_MAX_FRAME_BYTES));
        expectHandshakeRejected(expected, gate -> signed(
                gate, 1, 1, "session-01", 4, BASELINE_CAPABILITIES,
                DEFAULT_HEARTBEAT_MS, DEFAULT_MAX_FRAME_BYTES));
        expectHandshakeRejected(expected, gate -> signed(
                gate, 1, 0, "session-02", 4, BASELINE_CAPABILITIES,
                DEFAULT_HEARTBEAT_MS, DEFAULT_MAX_FRAME_BYTES));
        expectHandshakeRejected(expected, gate -> signed(
                gate, 1, 0, "session-01", 4, Set.of("observation.lifecycle.v1"),
                DEFAULT_HEARTBEAT_MS, DEFAULT_MAX_FRAME_BYTES));
        expectHandshakeRejected(expected, gate -> signed(
                gate, 1, 0, "session-01", 4,
                Set.of("session.handshake.v1", "control.move.v1"),
                DEFAULT_HEARTBEAT_MS, DEFAULT_MAX_FRAME_BYTES));

        // The launch nonce is inside both signed contexts, so a hello bound to a
        // previous launch must not be admitted.
        byte[] staleNonce = new byte[32];
        java.util.Arrays.fill(staleNonce, (byte) 9);
        HandshakeGate.Expected staleLaunch = new HandshakeGate.Expected(
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
                staleNonce,
                expected.sessionKey(),
                expected.capabilities());
        BridgePhaseMachine signerPhases = new BridgePhaseMachine();
        signerPhases.transition(BridgePhaseMachine.Phase.IPC_CONNECTING);
        HandshakeGate signer = new HandshakeGate(expected, signerPhases);
        HandshakeGate.CoreHelloData helloForCurrentLaunch = signed(
                signer,
                1,
                0,
                "session-01",
                4,
                BASELINE_CAPABILITIES,
                DEFAULT_HEARTBEAT_MS,
                DEFAULT_MAX_FRAME_BYTES);
        expectHandshakeRejected(staleLaunch, ignored -> helloForCurrentLaunch);
    }

    private static void handshakeBoundsAdmitOnlyTheAcceptedRange() {
        HandshakeGate.Expected expected = expectedHandshake();

        expectHandshakeRejected(expected, gate -> signed(
                gate, 1, 0, "session-01", 4, BASELINE_CAPABILITIES, 99, DEFAULT_MAX_FRAME_BYTES));
        expectHandshakeRejected(expected, gate -> signed(
                gate, 1, 0, "session-01", 4, BASELINE_CAPABILITIES, 10_001, DEFAULT_MAX_FRAME_BYTES));
        expectHandshakeRejected(expected, gate -> signed(
                gate, 1, 0, "session-01", 4, BASELINE_CAPABILITIES, DEFAULT_HEARTBEAT_MS, 1023));
        expectHandshakeRejected(expected, gate -> signed(
                gate, 1, 0, "session-01", 4, BASELINE_CAPABILITIES, DEFAULT_HEARTBEAT_MS,
                16 * 1024 * 1024 + 1));

        expectHandshakeAccepted(expected, gate -> signed(
                gate, 1, 0, "session-01", 4, BASELINE_CAPABILITIES, 100, 1024));
        expectHandshakeAccepted(expected, gate -> signed(
                gate, 1, 0, "session-01", 4, BASELINE_CAPABILITIES, 10_000, 16 * 1024 * 1024));
    }

    private static HandshakeGate.Expected expectedHandshake() {
        byte[] nonce = new byte[32];
        byte[] key = new byte[32];
        java.util.Arrays.fill(nonce, (byte) 7);
        java.util.Arrays.fill(key, (byte) 11);
        return new HandshakeGate.Expected(
                1,
                0,
                "kin-01",
                "session-01",
                4,
                "client-01",
                "a".repeat(64),
                "b".repeat(64),
                "1.21.4",
                "0.16.9",
                nonce,
                key,
                BASELINE_CAPABILITIES);
    }

    private static HandshakeGate.CoreHelloData signed(
            HandshakeGate gate,
            int protocolMajor,
            int protocolMinor,
            String sessionId,
            long generation,
            Set<String> capabilities,
            int heartbeatIntervalMs,
            int maxFrameBytes) {
        var unsigned = new HandshakeGate.CoreHelloData(
                protocolMajor,
                protocolMinor,
                sessionId,
                generation,
                capabilities,
                heartbeatIntervalMs,
                maxFrameBytes,
                "");
        return new HandshakeGate.CoreHelloData(
                unsigned.protocolMajor(),
                unsigned.protocolMinor(),
                unsigned.sessionId(),
                unsigned.generation(),
                unsigned.acceptedCapabilities(),
                unsigned.heartbeatIntervalMs(),
                unsigned.maxFrameBytes(),
                gate.proofForCoreHello(unsigned));
    }

    private static void expectHandshakeRejected(
            HandshakeGate.Expected expected, Function<HandshakeGate, HandshakeGate.CoreHelloData> build) {
        BridgePhaseMachine phases = new BridgePhaseMachine();
        phases.transition(BridgePhaseMachine.Phase.IPC_CONNECTING);
        HandshakeGate gate = new HandshakeGate(expected, phases);
        require(!gate.accept(build.apply(gate)), "mismatched Core hello must be rejected");
        require(
                phases.phase() == BridgePhaseMachine.Phase.SAFE_STOP,
                "rejected handshake safe-stops the Bridge");
    }

    private static void expectHandshakeAccepted(
            HandshakeGate.Expected expected, Function<HandshakeGate, HandshakeGate.CoreHelloData> build) {
        BridgePhaseMachine phases = new BridgePhaseMachine();
        phases.transition(BridgePhaseMachine.Phase.IPC_CONNECTING);
        HandshakeGate gate = new HandshakeGate(expected, phases);
        require(gate.accept(build.apply(gate)), "accepted Core hello must be admitted");
        require(
                phases.phase() == BridgePhaseMachine.Phase.OBSERVE_ONLY,
                "accepted handshake reaches OBSERVE_ONLY");
        require(!phases.permitsInput(), "OBSERVE_ONLY still refuses input");
    }

    private static void expectFailure(Runnable operation) {
        try {
            operation.run();
            throw new AssertionError("expected operation to fail");
        } catch (IllegalArgumentException | IllegalStateException expected) {
            // Expected fail-closed result.
        }
    }

    private static void require(boolean condition, String message) {
        if (!condition) {
            throw new AssertionError(message);
        }
    }
}
