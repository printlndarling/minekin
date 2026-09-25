import java.nio.ByteBuffer;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.function.Function;
import org.minekin.bridge.protocol.FrameCodec;
import org.minekin.bridge.protocol.HandshakeGate;
import org.minekin.bridge.runtime.BoundedChannel;
import org.minekin.bridge.runtime.BridgeMetrics;
import org.minekin.bridge.runtime.BridgePhaseMachine;
import org.minekin.bridge.runtime.CallbackBudget;

public final class BridgeProtocolSelfTest {
    private static final Set<String> BASELINE_CAPABILITIES =
            Set.of("session.handshake.v1", "observation.lifecycle.v1");
    private static final int DEFAULT_HEARTBEAT_MS = 500;
    private static final int DEFAULT_MAX_FRAME_BYTES = 4 * 1024 * 1024;

    /**
     * The version pair is named by the checker from the root's own `[versions]` table. Each root's
     * gate pins a different pair, so a shared self-test that spelled one out would prove nothing
     * about the other.
     */
    private static final String MINECRAFT_VERSION = namedVersion("minekin.selftest.minecraft");
    private static final String FABRIC_LOADER_VERSION = namedVersion("minekin.selftest.fabric.loader");

    private static String namedVersion(String property) {
        String value = System.getProperty(property);
        if (value == null || value.isBlank()) {
            throw new AssertionError("the checker must name this root's own version with -D" + property);
        }
        return value;
    }

    public static void main(String[] args) {
        framingIsNetworkOrderAndIncremental();
        oversizedFramesFailBeforeAllocation();
        queuesNeverBlockOrGrowPastTheirBound();
        phasesFailClosedAndNeverPermitInput();
        handshakeIsSingleUseAndIdentityBound();
        wrongNonceProtocolAndCapabilitiesAreRejected();
        handshakeBoundsAdmitOnlyTheAcceptedRange();
        budgetsAreBoundedAndKeepTheNewest();
        aClockThatWentBackwardsMeasuresNothing();
        recordingStaysBoundedWorkWhateverItIsGiven();
        metricsSampleBothSeriesOverOneWindow();
        aWindowThatOutranItsRingSaysSo();
        aWindowThatWasNotDeliveredStillConsumesItsNumber();
    }

    /**
     * The budget's whole memory is its ring, for a long run as much as a short one.
     *
     * <p>A million samples into a budget of four is the shape of every run: the
     * retention stays at the capacity and the newest are the ones kept, because the
     * tail is where a stall shows up.
     */
    private static void budgetsAreBoundedAndKeepTheNewest() {
        CallbackBudget budget = new CallbackBudget(4);
        require(budget.capacity() == 4, "the capacity is what was asked for");
        for (int sample = 1; sample <= 1_000_000; sample++) {
            budget.record(sample);
        }
        CallbackBudget.Window window = budget.take();
        require(window.recorded() == 1_000_000, "every sample is counted");
        require(window.nanos().length == 4, "retention is the capacity, not the count");
        require(
                java.util.Arrays.equals(
                        window.nanos(), new long[] {999_997L, 999_998L, 999_999L, 1_000_000L}),
                "the newest samples are the ones kept");
        require(budget.take().nanos().length == 0, "a taken window begins a new one");
    }

    private static void aClockThatWentBackwardsMeasuresNothing() {
        CallbackBudget budget = new CallbackBudget(2);
        budget.record(-1);

        require(budget.take().recorded() == 0, "a negative duration is refused, not stored");
    }

    /**
     * The record path is bounded work, and this is a guard on that rather than a
     * measurement of it.
     *
     * <p>A million array writes take a few milliseconds, so the margin below is three
     * orders of magnitude wide and cannot flake. What it would catch is the thing that
     * would actually matter: a {@code record} that started doing I/O, taking a lock or
     * allocating would not stay inside it — and that is the one way this class could
     * become the stall it exists to detect.
     *
     * <p>What is <em>not</em> claimed here is the end-to-end one. That the client
     * thread is never held up by this needs a real client, and the contract says so:
     * the prototype records the budget, and a run campaign is what judges it.
     */
    private static void recordingStaysBoundedWorkWhateverItIsGiven() {
        CallbackBudget budget = new CallbackBudget(4096);
        long startedAt = System.nanoTime();
        for (int sample = 0; sample < 1_000_000; sample++) {
            budget.record(sample);
        }
        long elapsedMillis = (System.nanoTime() - startedAt) / 1_000_000L;

        require(
                elapsedMillis < 5_000,
                "a million samples do not take five seconds: " + elapsedMillis + "ms");
        require(budget.capacity() == 4096, "and the memory did not grow with them");
    }

    private static void metricsSampleBothSeriesOverOneWindow() {
        BridgeMetrics metrics = new BridgeMetrics(8, 1_000L);
        require(!metrics.recordTick(1, 0), "the first tick opens a window");
        require(!metrics.recordTick(1, 400), "a window is not closed early");
        require(metrics.recordTick(1, 1_000), "a window closes at its cadence");

        List<BridgeMetrics.Snapshot> windows = metrics.takeWindows();
        require(windows.size() == 2, "one window per series");
        BridgeMetrics.Snapshot tick = windows.get(0);
        BridgeMetrics.Snapshot interval = windows.get(1);
        require(tick.label().equals(BridgeMetrics.TICK_LABEL), "the tick series");
        require(interval.label().equals(BridgeMetrics.INTERVAL_LABEL), "the interval series");
        require(tick.window() == 1 && interval.window() == 1, "both carry one window number");
        require(tick.nanos().length == 3, "three ticks in the window");
        require(
                interval.nanos().length == 2,
                "the first tick has no predecessor, so it contributes no interval");
        require(
                interval.nanos()[0] == 400 && interval.nanos()[1] == 600,
                "an interval is the period from one tick to the next");
    }

    private static void aWindowThatOutranItsRingSaysSo() {
        BridgeMetrics metrics = new BridgeMetrics(2, 999L);
        for (int tick = 0; tick <= 999; tick++) {
            metrics.recordTick(1, tick);
        }

        List<BridgeMetrics.Snapshot> windows = metrics.takeWindows();

        require(windows.get(0).recorded() == 1_000, "every tick is counted");
        require(windows.get(0).nanos().length == 2, "and two of them are still held");
    }

    /**
     * A window consumes its number when it closes, not when it is delivered.
     *
     * <p>This is the whole mechanism behind a hole in the evidence: the one report the
     * Bridge is allowed to drop is its own budget, and a reader must still be able to
     * see that it was built. Numbers 1 and 3 with no 2 say exactly that.
     */
    private static void aWindowThatWasNotDeliveredStillConsumesItsNumber() {
        BridgeMetrics metrics = new BridgeMetrics(4, 100L);
        metrics.recordTick(1, 0);
        metrics.recordTick(1, 100);
        List<BridgeMetrics.Snapshot> built = metrics.takeWindows();
        require(built.get(0).window() == 1, "the first window is number one");

        metrics.recordTick(1, 200);
        List<BridgeMetrics.Snapshot> next = metrics.takeWindows();

        require(next.get(0).window() == 2, "the ordinal advances with no delivery in between");
        require(metrics.windowCount() == 2, "and closed windows are counted whether or not sent");
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
        queue.replaceWith("safe-stop");
        List<String> terminal = new ArrayList<>();
        queue.drain(2, terminal::add);
        require(terminal.equals(List.of("safe-stop")), "safe-stop replaces queued work");
        require(queue.rejectedCount() == 2, "replaced work is observable as rejected");
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
        // Each root pins exactly one version pair, so a hello naming any other must not even build
        // the expectation this gate would honour.
        expectFailure(
                () ->
                        new HandshakeGate.Expected(
                                1,
                                0,
                                "kin-01",
                                "session-01",
                                4,
                                "client-01",
                                "a".repeat(64),
                                "b".repeat(64),
                                MINECRAFT_VERSION + "-other-root",
                                FABRIC_LOADER_VERSION + "-other-root",
                                new byte[32],
                                new byte[32],
                                BASELINE_CAPABILITIES));
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
                MINECRAFT_VERSION,
                FABRIC_LOADER_VERSION,
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
