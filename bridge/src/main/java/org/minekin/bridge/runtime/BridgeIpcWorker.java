package org.minekin.bridge.runtime;

import com.google.protobuf.ByteString;
import io.minekin.protocol.v1.AdmissionFailureReason;
import io.minekin.protocol.v1.BridgeBootstrapDescriptor;
import io.minekin.protocol.v1.CancelConnection;
import io.minekin.protocol.v1.Channel;
import io.minekin.protocol.v1.ConnectWorld;
import io.minekin.protocol.v1.ConnectionLifecycle;
import io.minekin.protocol.v1.ConnectionPhase;
import io.minekin.protocol.v1.CoreHello;
import io.minekin.protocol.v1.Envelope;
import io.minekin.protocol.v1.Heartbeat;
import io.minekin.protocol.v1.ProtocolVersion;
import io.minekin.protocol.v1.ReleaseAllInputs;
import java.io.IOException;
import java.net.SocketTimeoutException;
import java.nio.channels.SocketChannel;
import java.nio.file.Path;
import java.time.Duration;
import java.util.Set;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.function.Consumer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.minekin.bridge.protocol.AdmissionCommandGate;
import org.minekin.bridge.protocol.BootstrapDescriptorAdapter;
import org.minekin.bridge.protocol.DescriptorLoader;
import org.minekin.bridge.protocol.EndpointConnector;
import org.minekin.bridge.protocol.EnvelopeGate;
import org.minekin.bridge.protocol.HandshakeGate;
import org.minekin.bridge.input.BridgeInputController;
import org.minekin.bridge.input.InputWatchdog;
import org.minekin.bridge.input.KeySink;
import org.minekin.bridge.protocol.NioEnvelopeChannel;

/** Owns descriptor I/O, both local sockets, protobuf encoding, and handshake on a daemon thread. */
public final class BridgeIpcWorker implements AutoCloseable {
    public static final String BRIDGE_HELLO_TYPE = "minekin.v1.BridgeHello";
    public static final String CORE_HELLO_TYPE = "minekin.v1.CoreHello";
    public static final String HEARTBEAT_TYPE = "minekin.v1.Heartbeat";
    public static final String CONNECT_WORLD_TYPE = "minekin.v1.ConnectWorld";
    public static final String CANCEL_CONNECTION_TYPE = "minekin.v1.CancelConnection";
    public static final String CONNECTION_LIFECYCLE_TYPE = "minekin.v1.ConnectionLifecycle";
    public static final String RELEASE_ALL_INPUTS_TYPE = "minekin.v1.ReleaseAllInputs";
    private static final Logger LOGGER = LoggerFactory.getLogger("minekin-bridge");
    /**
     * How many heartbeat intervals of silence the Bridge tolerates before it lets go of
     * the player's controls. More than one, because a single missed interval is ordinary
     * scheduling jitter rather than a reason to stop walking.
     */
    private static final int INPUT_MISSED_HEARTBEATS = 3;
    private static final long MONOTONIC_ORIGIN = System.nanoTime();

    private final Path descriptorPath;
    private final Duration connectTimeout;
    private final Duration handshakeTimeout;
    private final BridgePhaseMachine phases;
    private final KeySink keySink;
    private final BoundedChannel<ClientMessage> clientInbox;
    private final BoundedChannel<ConnectionLifecycle> eventOutbox;
    private final AdmissionCommandGate admissionCommands = new AdmissionCommandGate();
    private final AtomicBoolean started = new AtomicBoolean();
    private final AtomicBoolean stopping = new AtomicBoolean();
    private volatile Thread thread;
    private volatile Thread eventThread;
    private volatile NioEnvelopeChannel control;
    private volatile NioEnvelopeChannel event;
    private volatile BridgeInputController input;

    public BridgeIpcWorker(
            Path descriptorPath,
            Duration connectTimeout,
            Duration handshakeTimeout,
            int inboxCapacity,
            BridgePhaseMachine phases,
            KeySink keySink) {
        this.descriptorPath = descriptorPath.toAbsolutePath().normalize();
        this.connectTimeout = requirePositive(connectTimeout, "connectTimeout");
        this.handshakeTimeout = requirePositive(handshakeTimeout, "handshakeTimeout");
        this.phases = java.util.Objects.requireNonNull(phases, "phases");
        this.keySink = java.util.Objects.requireNonNull(keySink, "keySink");
        clientInbox = new BoundedChannel<>(inboxCapacity);
        eventOutbox = new BoundedChannel<>(inboxCapacity);
    }

    /** Starts exactly once and returns without descriptor or socket I/O. */
    public void start() {
        if (!started.compareAndSet(false, true)) {
            throw new IllegalStateException("Bridge IPC worker already started");
        }
        Thread worker = new Thread(this::run, "minekin-bridge-ipc");
        worker.setDaemon(true);
        thread = worker;
        worker.start();
    }

    public int drainClientMessages(int limit, Consumer<ClientMessage> consumer) {
        return clientInbox.drain(limit, consumer);
    }

    public BridgePhaseMachine.Phase phase() {
        return phases.phase();
    }

    /**
     * The watchdog's clock, driven from the client thread.
     *
     * <p>The heartbeat loop already refuses to wait forever for Core, and this is
     * the other failure: a worker thread that is itself wedged, which no loop can
     * notice. The client thread is still ticking when that happens, and this is
     * what it does about it. Returns true on the tick that let go.
     */
    public boolean tickInput() {
        BridgeInputController controller = input;
        boolean released = controller != null && controller.tick(monotonicNow());
        if (released) {
            LOGGER.warn("bridge released input after {}", BridgeInputController.ReleaseReason.TIMEOUT);
        }
        return released;
    }

    /** Apply an input-side client message synchronously on the client tick. */
    public boolean handleInputMessage(ClientMessage message) {
        java.util.Objects.requireNonNull(message, "message");
        if (message instanceof ReleaseCommand release) {
            releaseInputs(
                    BridgeInputController.ReleaseReason.CORE_REQUEST,
                    release.value().getReasonCode());
            return true;
        }
        if (message == Notice.SAFE_STOP) {
            releaseInputs(BridgeInputController.ReleaseReason.BRIDGE_FAULT, "");
        }
        return false;
    }

    /** Client-thread shutdown/error hook; logs only after the bindings changed. */
    public void releaseInputsOnClientThread(
            BridgeInputController.ReleaseReason reason, String reasonCode) {
        releaseInputs(reason, reasonCode);
    }

    public long rejectedMessageCount() {
        return clientInbox.rejectedCount() + eventOutbox.rejectedCount();
    }

    /** Non-blocking client-thread handoff for must-deliver lifecycle events. */
    public boolean publishLifecycle(ConnectionLifecycle lifecycle) {
        java.util.Objects.requireNonNull(lifecycle, "lifecycle");
        if (stopping.get() || !started.get() || event == null || !validLifecycle(lifecycle)) {
            LOGGER.warn(
                    "bridge dropped a lifecycle report: stopping={} started={} event={} valid={}",
                    stopping.get(),
                    started.get(),
                    event != null,
                    validLifecycle(lifecycle));
            return false;
        }
        if (!eventOutbox.offer(lifecycle)) {
            // Worth saying out loud: this is the Bridge failing itself closed
            // because a phase it must deliver had nowhere to go, and the client
            // it is attached to will be cancelled a moment later. Without this
            // line the client simply stops, with no cause anywhere.
            LOGGER.error(
                    "bridge event outbox is full ({} held), failing closed on {}",
                    eventOutbox.size(),
                    lifecycle.getPhase());
            failClosed();
            return false;
        }
        return true;
    }

    @Override
    public void close() {
        if (!stopping.compareAndSet(false, true)) {
            return;
        }
        // Closing invalidates every queued command. The client-thread caller may
        // already have released input, but SAFE_STOP must still be the only next
        // message if a tick drains again during shutdown.
        clientInbox.replaceWith(Notice.SAFE_STOP);
        closeQuietly(control);
        closeQuietly(event);
        Thread worker = thread;
        if (worker != null) {
            worker.interrupt();
        }
        Thread writer = eventThread;
        if (writer != null) {
            writer.interrupt();
        }
    }

    private void run() {
        try {
            BridgeBootstrapDescriptor raw = DescriptorLoader.loadAndDelete(descriptorPath);
            BootstrapDescriptorAdapter.AdaptedDescriptor descriptor =
                    BootstrapDescriptorAdapter.adapt(raw);
            phases.transition(BridgePhaseMachine.Phase.IPC_CONNECTING);
            control = connect(
                    descriptor.endpoints().control(), Channel.CHANNEL_CONTROL, descriptor.maxFrameBytes());
            event = connect(
                    descriptor.endpoints().event(), Channel.CHANNEL_EVENT, descriptor.maxFrameBytes());
            HeartbeatState heartbeat = handshake(descriptor);
            startEventWriter(descriptor);
            heartbeatLoop(descriptor, heartbeat);
        } catch (Exception error) {
            if (!stopping.get()) {
                failClosed();
            }
        } finally {
            closeQuietly(control);
            closeQuietly(event);
        }
    }

    private NioEnvelopeChannel connect(
            io.minekin.protocol.v1.IpcEndpoint endpoint, Channel channel, int maxFrameBytes)
            throws IOException {
        SocketChannel socket = EndpointConnector.connect(endpoint, connectTimeout);
        try {
            return new NioEnvelopeChannel(socket, channel, maxFrameBytes);
        } catch (IOException | RuntimeException error) {
            socket.close();
            throw error;
        }
    }

    private HeartbeatState handshake(BootstrapDescriptorAdapter.AdaptedDescriptor descriptor)
            throws IOException {
        HandshakeGate handshake = new HandshakeGate(descriptor.expected(), phases);
        Envelope bridgeHello = envelope(
                descriptor,
                BRIDGE_HELLO_TYPE,
                Channel.CHANNEL_CONTROL,
                1,
                BootstrapDescriptorAdapter.toProto(handshake.bridgeHello()).toByteString());
        control.write(bridgeHello, handshakeTimeout);

        EnvelopeGate gate = new EnvelopeGate(
                new EnvelopeGate.Expected(
                        descriptor.expected().protocolMajor(),
                        descriptor.expected().protocolMinor(),
                        descriptor.expected().kinId(),
                        descriptor.expected().sessionId(),
                        descriptor.expected().generation(),
                        descriptor.expected().clientInstanceId()),
                Channel.CHANNEL_CONTROL,
                Set.of(
                        CORE_HELLO_TYPE,
                        HEARTBEAT_TYPE,
                        CONNECT_WORLD_TYPE,
                        CANCEL_CONNECTION_TYPE,
                        RELEASE_ALL_INPUTS_TYPE));
        Envelope reply = control.read(handshakeTimeout);
        gate.validate(reply);
        if (!CORE_HELLO_TYPE.equals(reply.getMessageType())) {
            throw new IOException("first control message is not CoreHello");
        }
        CoreHello coreHello = CoreHello.parseFrom(reply.getPayload());
        HandshakeGate.CoreHelloData accepted = BootstrapDescriptorAdapter.fromProto(coreHello);
        if (!handshake.accept(accepted)) {
            throw new IOException("CoreHello proof or negotiated values were rejected");
        }
        if (!clientInbox.offer(Notice.OBSERVE_ONLY)) {
            throw new IOException("client notice queue is full after handshake");
        }
        BridgeInputController created = new BridgeInputController(
                keySink,
                new InputWatchdog(
                        Duration.ofMillis(coreHello.getHeartbeatIntervalMs()).toNanos(),
                        INPUT_MISSED_HEARTBEATS),
                descriptor.expected().generation());
        created.observeCoreMessage(monotonicNow());
        input = created;
        return new HeartbeatState(
                gate,
                Duration.ofMillis(Math.multiplyExact(coreHello.getHeartbeatIntervalMs(), 3L)),
                accepted.acceptedCapabilities());
    }

    private void startEventWriter(BootstrapDescriptorAdapter.AdaptedDescriptor descriptor) {
        Thread writer = new Thread(() -> eventWriterLoop(descriptor), "minekin-bridge-events");
        writer.setDaemon(true);
        eventThread = writer;
        writer.start();
    }

    private void eventWriterLoop(BootstrapDescriptorAdapter.AdaptedDescriptor descriptor) {
        long sequence = 1;
        try {
            while (!stopping.get()) {
                ConnectionLifecycle lifecycle = eventOutbox.take();
                Envelope outbound = envelope(
                        descriptor,
                        CONNECTION_LIFECYCLE_TYPE,
                        Channel.CHANNEL_EVENT,
                        sequence,
                        lifecycle.toByteString());
                event.write(outbound, handshakeTimeout);
                if (sequence == Long.MAX_VALUE) {
                    throw new IOException("event sequence exhausted the P0 signed range");
                }
                sequence++;
            }
        } catch (InterruptedException interrupted) {
            Thread.currentThread().interrupt();
            if (!stopping.get()) {
                failClosed();
            }
        } catch (Exception error) {
            if (!stopping.get()) {
                failClosed();
            }
        }
    }

    private void heartbeatLoop(
            BootstrapDescriptorAdapter.AdaptedDescriptor descriptor, HeartbeatState state)
            throws IOException {
        long heartbeatDeadline = heartbeatDeadline(state.timeout());
        while (!stopping.get()) {
            long remaining = heartbeatDeadline - System.nanoTime();
            if (remaining <= 0) {
                throw new SocketTimeoutException("Bridge heartbeat timed out");
            }
            Envelope envelope = control.read(Duration.ofNanos(remaining));
            state.gate().validate(envelope);
            if (HEARTBEAT_TYPE.equals(envelope.getMessageType())) {
                Heartbeat heartbeat = Heartbeat.parseFrom(envelope.getPayload());
                if (heartbeat.getGeneration() != descriptor.expected().generation()
                        || heartbeat.getMonotonicNs() == 0) {
                    throw new IOException("heartbeat identity is invalid");
                }
                observeCoreMessage();
                heartbeatDeadline = heartbeatDeadline(state.timeout());
            } else if (CONNECT_WORLD_TYPE.equals(envelope.getMessageType())) {
                ConnectWorld command = ConnectWorld.parseFrom(envelope.getPayload());
                validateConnectDeadline(command, envelope.getMonotonicNs());
                admissionCommands.acceptConnect(command, state.capabilities());
                observeCoreMessage();
                if (!clientInbox.offer(new ConnectCommand(command))) {
                    throw new IOException("client inbox is full for ConnectWorld");
                }
            } else if (RELEASE_ALL_INPUTS_TYPE.equals(envelope.getMessageType())) {
                ReleaseAllInputs command = ReleaseAllInputs.parseFrom(envelope.getPayload());
                validateRelease(command);
                observeCoreMessage();
                // Release is deliberately fail-safe: a stale positive generation
                // still lifts keys. It may not grant control, so suppressing it on a
                // generation mismatch would only preserve unsafe state.
                if (!clientInbox.offer(new ReleaseCommand(command))) {
                    throw new IOException("client inbox is full for ReleaseAllInputs");
                }
            } else if (CANCEL_CONNECTION_TYPE.equals(envelope.getMessageType())) {
                CancelConnection command = CancelConnection.parseFrom(envelope.getPayload());
                admissionCommands.acceptCancel(command, state.capabilities());
                observeCoreMessage();
                if (!clientInbox.offer(new CancelCommand(command))) {
                    throw new IOException("client inbox is full for CancelConnection");
                }
            } else {
                throw new IOException("CoreHello may not be replayed after activation");
            }
        }
    }

    private static Envelope envelope(
            BootstrapDescriptorAdapter.AdaptedDescriptor descriptor,
            String messageType,
            Channel channel,
            long sequence,
            ByteString payload) {
        HandshakeGate.Expected expected = descriptor.expected();
        return Envelope.newBuilder()
                .setProtocol(ProtocolVersion.newBuilder()
                        .setMajor(expected.protocolMajor())
                        .setMinor(expected.protocolMinor()))
                .setMessageType(messageType)
                .setChannel(channel)
                .setSequence(sequence)
                .setKinId(expected.kinId())
                .setSessionId(expected.sessionId())
                .setGeneration(expected.generation())
                .setClientInstanceId(expected.clientInstanceId())
                .setMonotonicNs(monotonicNow())
                .setPayload(payload)
                .build();
    }

    private static boolean validLifecycle(ConnectionLifecycle lifecycle) {
        if (lifecycle.getGeneration() == 0
                || lifecycle.getServerProfileId().isBlank()
                || !lifecycle.getServerProfileRevision().matches("[0-9a-f]{64}")
                || lifecycle.getPhase() == ConnectionPhase.CONNECTION_PHASE_UNSPECIFIED
                || lifecycle.getPhase() == ConnectionPhase.UNRECOGNIZED
                || lifecycle.getFailureReason() == AdmissionFailureReason.UNRECOGNIZED) {
            return false;
        }
        boolean terminalPhase = switch (lifecycle.getPhase()) {
            case CONNECTION_PHASE_DISCONNECTED,
                    CONNECTION_PHASE_FAILED,
                    CONNECTION_PHASE_CANCELLED -> true;
            default -> false;
        };
        if (terminalPhase != lifecycle.getTerminal()) {
            return false;
        }
        // Core classifies on the phase and the reason together, so a reason that
        // does not belong to the phase is a contradiction, not extra detail.
        AdmissionFailureReason reason = lifecycle.getFailureReason();
        return switch (lifecycle.getPhase()) {
            case CONNECTION_PHASE_FAILED ->
                    reason != AdmissionFailureReason.ADMISSION_FAILURE_REASON_UNSPECIFIED
                            && reason != AdmissionFailureReason.ADMISSION_FAILURE_REASON_CANCELLED;
            case CONNECTION_PHASE_CANCELLED ->
                    reason == AdmissionFailureReason.ADMISSION_FAILURE_REASON_UNSPECIFIED
                            || reason
                                    == AdmissionFailureReason.ADMISSION_FAILURE_REASON_CANCELLED;
            default -> reason == AdmissionFailureReason.ADMISSION_FAILURE_REASON_UNSPECIFIED;
        };
    }

    /**
     * Hands the input back on the client thread. Faults arrive here through the
     * terminal inbox notice; normal shutdown calls the explicit client-thread hook.
     */
    private void releaseInputs(BridgeInputController.ReleaseReason reason, String reasonCode) {
        BridgeInputController controller = input;
        if (controller == null) {
            return;
        }
        java.util.List<String> released = controller.releaseAll(reason);
        if (reasonCode == null || reasonCode.isBlank()) {
            LOGGER.info("bridge released {} input(s) after {}", released.size(), reason);
        } else {
            LOGGER.info(
                    "bridge released {} input(s) after {} ({})",
                    released.size(),
                    reason,
                    reasonCode);
        }
    }

    private void observeCoreMessage() {
        BridgeInputController controller = input;
        if (controller != null) {
            controller.observeCoreMessage(monotonicNow());
        }
    }

    static void validateRelease(ReleaseAllInputs command) throws IOException {
        if (command.getActionId().isBlank()
                || command.getActionId().length() > 128
                || command.getGeneration() == 0
                || !command.getReasonCode().matches("[A-Z0-9_]{1,64}")) {
            throw new IOException("ReleaseAllInputs identity or reason is invalid");
        }
    }

    /**
     * Refuses a connect command that Core has already stopped waiting for.
     *
     * <p>The deadline and the envelope's own timestamp come from the same
     * clock — Core's — so their difference is a duration, and a duration is the
     * only thing two processes without a shared origin can agree on. Comparing
     * the raw deadline against this JVM's {@code System.nanoTime()} would be
     * comparing two unrelated numbers and would pass or fail by accident.
     *
     * <p>This is checked when the command is read rather than when the client
     * tick consumes it, because that is the moment the sender's stamp is still
     * on hand. Starting a connection Core has given up on is the failure this
     * exists to prevent: it would put a client in a world nobody is waiting
     * for, under a generation Core no longer tracks.
     */
    static void validateConnectDeadline(ConnectWorld command, long receivedAtNanos) throws IOException {
        long remaining;
        try {
            remaining = Math.subtractExact(command.getDeadlineMonotonicNs(), receivedAtNanos);
        } catch (ArithmeticException overflow) {
            throw new IOException("ConnectWorld deadline is not a usable duration");
        }
        if (remaining <= 0) {
            throw new IOException("ConnectWorld expired before the client could act on it");
        }
    }

    private void failClosed() {
        if (!stopping.compareAndSet(false, true)) {
            return;
        }
        LOGGER.error("bridge is failing closed; the client will be stopped by its next tick");
        phases.safeStop();
        clientInbox.replaceWith(Notice.SAFE_STOP);
        closeQuietly(control);
        closeQuietly(event);
        Thread controlWorker = thread;
        if (controlWorker != null && controlWorker != Thread.currentThread()) {
            controlWorker.interrupt();
        }
        Thread writer = eventThread;
        if (writer != null && writer != Thread.currentThread()) {
            writer.interrupt();
        }
    }

    private static Duration requirePositive(Duration value, String name) {
        if (value == null || value.isZero() || value.isNegative()) {
            throw new IllegalArgumentException(name + " must be positive");
        }
        return value;
    }

    private static long heartbeatDeadline(Duration timeout) {
        try {
            return Math.addExact(System.nanoTime(), timeout.toNanos());
        } catch (ArithmeticException error) {
            throw new IllegalArgumentException("heartbeat timeout is too large", error);
        }
    }

    private static long monotonicNow() {
        return Math.max(1, System.nanoTime() - MONOTONIC_ORIGIN);
    }

    private static void closeQuietly(AutoCloseable closeable) {
        if (closeable != null) {
            try {
                closeable.close();
            } catch (Exception ignored) {
                // The session is already stopping or failed closed.
            }
        }
    }

    public sealed interface ClientMessage
            permits Notice, ConnectCommand, CancelCommand, ReleaseCommand {}

    public enum Notice implements ClientMessage {
        OBSERVE_ONLY,
        SAFE_STOP
    }

    public record ConnectCommand(ConnectWorld value) implements ClientMessage {}

    public record CancelCommand(CancelConnection value) implements ClientMessage {}

    public record ReleaseCommand(ReleaseAllInputs value) implements ClientMessage {}

    private record HeartbeatState(EnvelopeGate gate, Duration timeout, Set<String> capabilities) {
        private HeartbeatState {
            capabilities = Set.copyOf(capabilities);
        }
    }
}
