import java.nio.ByteBuffer;
import java.util.ArrayList;
import java.util.List;
import org.minekin.bridge.protocol.FrameCodec;
import org.minekin.bridge.protocol.HandshakeGate;
import org.minekin.bridge.runtime.BoundedChannel;
import org.minekin.bridge.runtime.BridgePhaseMachine;

public final class BridgeProtocolSelfTest {
    public static void main(String[] args) {
        framingIsNetworkOrderAndIncremental();
        oversizedFramesFailBeforeAllocation();
        queuesNeverBlockOrGrowPastTheirBound();
        phasesFailClosedAndNeverPermitInput();
        handshakeIsSingleUseAndIdentityBound();
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
        byte[] nonce = new byte[32];
        byte[] key = new byte[32];
        java.util.Arrays.fill(nonce, (byte) 7);
        java.util.Arrays.fill(key, (byte) 11);
        var expected = new HandshakeGate.Expected(
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
                java.util.Set.of("session.handshake.v1", "observation.lifecycle.v1"));
        BridgePhaseMachine phases = new BridgePhaseMachine();
        phases.transition(BridgePhaseMachine.Phase.IPC_CONNECTING);
        HandshakeGate gate = new HandshakeGate(expected, phases);
        require(gate.bridgeHello().proof().length() == 64, "HMAC proof is SHA-256 hex");
        require(gate.bridgeHello().launchNonce().length() == 64, "nonce is explicit 256-bit hex");
        var unsigned = new HandshakeGate.CoreHelloData(
                1,
                0,
                "session-01",
                4,
                java.util.Set.of("session.handshake.v1", "observation.lifecycle.v1"),
                500,
                4 * 1024 * 1024,
                "");
        var accepted = new HandshakeGate.CoreHelloData(
                unsigned.protocolMajor(),
                unsigned.protocolMinor(),
                unsigned.sessionId(),
                unsigned.generation(),
                unsigned.acceptedCapabilities(),
                unsigned.heartbeatIntervalMs(),
                unsigned.maxFrameBytes(),
                gate.proofForCoreHello(unsigned));
        require(gate.accept(accepted), "matching Core hello");
        require(phases.phase() == BridgePhaseMachine.Phase.OBSERVE_ONLY, "observe-only activation");
        require(!gate.accept(accepted), "handshake cannot be replayed");
        require(phases.phase() == BridgePhaseMachine.Phase.SAFE_STOP, "replay is fail-closed");

        BridgePhaseMachine rejectedPhases = new BridgePhaseMachine();
        rejectedPhases.transition(BridgePhaseMachine.Phase.IPC_CONNECTING);
        HandshakeGate rejected = new HandshakeGate(expected, rejectedPhases);
        var wrongGenerationUnsigned = new HandshakeGate.CoreHelloData(
                1,
                0,
                "session-01",
                5,
                java.util.Set.of("session.handshake.v1"),
                500,
                4 * 1024 * 1024,
                "");
        var wrongGeneration = new HandshakeGate.CoreHelloData(
                wrongGenerationUnsigned.protocolMajor(),
                wrongGenerationUnsigned.protocolMinor(),
                wrongGenerationUnsigned.sessionId(),
                wrongGenerationUnsigned.generation(),
                wrongGenerationUnsigned.acceptedCapabilities(),
                wrongGenerationUnsigned.heartbeatIntervalMs(),
                wrongGenerationUnsigned.maxFrameBytes(),
                rejected.proofForCoreHello(wrongGenerationUnsigned));
        require(!rejected.accept(wrongGeneration), "old or future generation is rejected");
        require(
                rejectedPhases.phase() == BridgePhaseMachine.Phase.SAFE_STOP,
                "identity mismatch safe-stops");

        BridgePhaseMachine badProofPhases = new BridgePhaseMachine();
        badProofPhases.transition(BridgePhaseMachine.Phase.IPC_CONNECTING);
        HandshakeGate badProofGate = new HandshakeGate(expected, badProofPhases);
        var badProof = new HandshakeGate.CoreHelloData(
                1,
                0,
                "session-01",
                4,
                java.util.Set.of("session.handshake.v1"),
                500,
                4 * 1024 * 1024,
                "0".repeat(64));
        require(!badProofGate.accept(badProof), "invalid Core proof is rejected");
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
