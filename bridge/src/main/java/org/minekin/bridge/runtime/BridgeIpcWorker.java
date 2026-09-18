package org.minekin.bridge.runtime;

import com.google.protobuf.ByteString;
import io.minekin.protocol.v1.BridgeBootstrapDescriptor;
import io.minekin.protocol.v1.Channel;
import io.minekin.protocol.v1.CoreHello;
import io.minekin.protocol.v1.Envelope;
import io.minekin.protocol.v1.Heartbeat;
import io.minekin.protocol.v1.ProtocolVersion;
import java.io.IOException;
import java.nio.channels.SocketChannel;
import java.nio.file.Path;
import java.time.Duration;
import java.util.Set;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.function.Consumer;
import org.minekin.bridge.protocol.BootstrapDescriptorAdapter;
import org.minekin.bridge.protocol.DescriptorLoader;
import org.minekin.bridge.protocol.EndpointConnector;
import org.minekin.bridge.protocol.EnvelopeGate;
import org.minekin.bridge.protocol.HandshakeGate;
import org.minekin.bridge.protocol.NioEnvelopeChannel;

/** Owns descriptor I/O, both local sockets, protobuf encoding, and handshake on a daemon thread. */
public final class BridgeIpcWorker implements AutoCloseable {
    public static final String BRIDGE_HELLO_TYPE = "minekin.v1.BridgeHello";
    public static final String CORE_HELLO_TYPE = "minekin.v1.CoreHello";
    public static final String HEARTBEAT_TYPE = "minekin.v1.Heartbeat";
    private static final long MONOTONIC_ORIGIN = System.nanoTime();

    private final Path descriptorPath;
    private final Duration connectTimeout;
    private final Duration handshakeTimeout;
    private final BridgePhaseMachine phases;
    private final BoundedChannel<Notice> clientNotices;
    private final AtomicBoolean started = new AtomicBoolean();
    private final AtomicBoolean stopping = new AtomicBoolean();
    private volatile Thread thread;
    private volatile NioEnvelopeChannel control;
    private volatile NioEnvelopeChannel event;

    public BridgeIpcWorker(
            Path descriptorPath,
            Duration connectTimeout,
            Duration handshakeTimeout,
            int noticeCapacity,
            BridgePhaseMachine phases) {
        this.descriptorPath = descriptorPath.toAbsolutePath().normalize();
        this.connectTimeout = requirePositive(connectTimeout, "connectTimeout");
        this.handshakeTimeout = requirePositive(handshakeTimeout, "handshakeTimeout");
        this.phases = java.util.Objects.requireNonNull(phases, "phases");
        clientNotices = new BoundedChannel<>(noticeCapacity);
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

    public int drainClientNotices(int limit, Consumer<Notice> consumer) {
        return clientNotices.drain(limit, consumer);
    }

    public BridgePhaseMachine.Phase phase() {
        return phases.phase();
    }

    public long rejectedNoticeCount() {
        return clientNotices.rejectedCount();
    }

    @Override
    public void close() {
        stopping.set(true);
        closeQuietly(control);
        closeQuietly(event);
        Thread worker = thread;
        if (worker != null) {
            worker.interrupt();
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
            heartbeatLoop(descriptor, heartbeat);
        } catch (Exception error) {
            if (!stopping.get()) {
                phases.safeStop();
                clientNotices.offer(Notice.SAFE_STOP);
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
                Set.of(CORE_HELLO_TYPE, HEARTBEAT_TYPE));
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
        if (!clientNotices.offer(Notice.OBSERVE_ONLY)) {
            throw new IOException("client notice queue is full after handshake");
        }
        return new HeartbeatState(
                gate, Duration.ofMillis(Math.multiplyExact(coreHello.getHeartbeatIntervalMs(), 3L)));
    }

    private void heartbeatLoop(
            BootstrapDescriptorAdapter.AdaptedDescriptor descriptor, HeartbeatState state)
            throws IOException {
        while (!stopping.get()) {
            Envelope envelope = control.read(state.timeout());
            state.gate().validate(envelope);
            if (!HEARTBEAT_TYPE.equals(envelope.getMessageType())) {
                throw new IOException("CoreHello may not be replayed after activation");
            }
            Heartbeat heartbeat = Heartbeat.parseFrom(envelope.getPayload());
            if (heartbeat.getGeneration() != descriptor.expected().generation()
                    || heartbeat.getMonotonicNs() == 0) {
                throw new IOException("heartbeat identity is invalid");
            }
        }
    }

    private static Envelope envelope(
            BootstrapDescriptorAdapter.AdaptedDescriptor descriptor,
            String messageType,
            long sequence,
            ByteString payload) {
        HandshakeGate.Expected expected = descriptor.expected();
        return Envelope.newBuilder()
                .setProtocol(ProtocolVersion.newBuilder()
                        .setMajor(expected.protocolMajor())
                        .setMinor(expected.protocolMinor()))
                .setMessageType(messageType)
                .setChannel(Channel.CHANNEL_CONTROL)
                .setSequence(sequence)
                .setKinId(expected.kinId())
                .setSessionId(expected.sessionId())
                .setGeneration(expected.generation())
                .setClientInstanceId(expected.clientInstanceId())
                .setMonotonicNs(monotonicNow())
                .setPayload(payload)
                .build();
    }

    private static Duration requirePositive(Duration value, String name) {
        if (value == null || value.isZero() || value.isNegative()) {
            throw new IllegalArgumentException(name + " must be positive");
        }
        return value;
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

    public enum Notice {
        OBSERVE_ONLY,
        SAFE_STOP
    }

    private record HeartbeatState(EnvelopeGate gate, Duration timeout) {}
}
