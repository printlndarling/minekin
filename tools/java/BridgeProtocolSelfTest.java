import java.nio.ByteBuffer;
import java.util.ArrayList;
import java.util.List;
import org.minekin.bridge.protocol.FrameCodec;
import org.minekin.bridge.runtime.BoundedChannel;
import org.minekin.bridge.runtime.BridgePhaseMachine;

public final class BridgeProtocolSelfTest {
    public static void main(String[] args) {
        framingIsNetworkOrderAndIncremental();
        oversizedFramesFailBeforeAllocation();
        queuesNeverBlockOrGrowPastTheirBound();
        phasesFailClosedAndNeverPermitInput();
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
