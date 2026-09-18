import com.google.protobuf.ByteString;
import io.minekin.protocol.v1.BridgeBootstrapDescriptor;
import io.minekin.protocol.v1.BridgeHello;
import io.minekin.protocol.v1.Capability;
import io.minekin.protocol.v1.Channel;
import io.minekin.protocol.v1.CoreHello;
import io.minekin.protocol.v1.EndpointTransport;
import io.minekin.protocol.v1.Envelope;
import io.minekin.protocol.v1.Heartbeat;
import io.minekin.protocol.v1.IpcEndpoint;
import io.minekin.protocol.v1.ProtocolVersion;
import java.net.InetSocketAddress;
import java.net.StandardProtocolFamily;
import java.nio.channels.ServerSocketChannel;
import java.nio.channels.SocketChannel;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.attribute.PosixFilePermission;
import java.time.Duration;
import java.util.HexFormat;
import java.util.Set;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.atomic.AtomicReference;
import org.minekin.bridge.protocol.BootstrapDescriptorAdapter;
import org.minekin.bridge.protocol.FramedEnvelopeChannel;
import org.minekin.bridge.protocol.HandshakeGate;
import org.minekin.bridge.runtime.BridgeIpcWorker;
import org.minekin.bridge.runtime.BridgePhaseMachine;

/** End-to-end loopback check for the daemon worker and its two socket connections. */
public final class BridgeIpcWorkerSelfTest {
    private static final int MAX_FRAME_BYTES = 1_048_576;
    private static final String DIGEST = "cd".repeat(32);

    private BridgeIpcWorkerSelfTest() {}

    public static void main(String[] arguments) throws Exception {
        try (ServerSocketChannel controlServer = server();
                ServerSocketChannel eventServer = server()) {
            int controlPort = ((InetSocketAddress) controlServer.getLocalAddress()).getPort();
            int eventPort = ((InetSocketAddress) eventServer.getLocalAddress()).getPort();
            BridgeBootstrapDescriptor descriptor = descriptor(controlPort, eventPort);
            Path descriptorPath = Files.createTempFile("minekin-worker-", ".pb");
            makePrivateIfSupported(descriptorPath);
            Files.write(descriptorPath, descriptor.toByteArray());

            CountDownLatch releaseServer = new CountDownLatch(1);
            AtomicReference<Throwable> serverFailure = new AtomicReference<>();
            Thread serverThread = new Thread(
                    () -> serve(controlServer, eventServer, descriptor, releaseServer, serverFailure),
                    "minekin-test-runtime");
            serverThread.start();

            BridgePhaseMachine phases = new BridgePhaseMachine();
            try (BridgeIpcWorker worker = new BridgeIpcWorker(
                    descriptorPath,
                    Duration.ofSeconds(2),
                    Duration.ofSeconds(2),
                    4,
                    phases)) {
                long start = System.nanoTime();
                worker.start();
                assert System.nanoTime() - start < Duration.ofMillis(500).toNanos()
                        : "worker start performed blocking I/O";
                BridgeIpcWorker.Notice notice = awaitNotice(worker, Duration.ofSeconds(4));
                assert notice == BridgeIpcWorker.Notice.OBSERVE_ONLY;
                assert worker.phase() == BridgePhaseMachine.Phase.OBSERVE_ONLY;
                assert Files.notExists(descriptorPath);
            } finally {
                releaseServer.countDown();
                serverThread.join(3_000);
            }
            assert !serverThread.isAlive() : "test Runtime did not stop";
            if (serverFailure.get() != null) {
                throw new AssertionError("test Runtime failed", serverFailure.get());
            }
        }
        System.out.println("Minekin Bridge IPC worker self-test: OK");
    }

    private static void serve(
            ServerSocketChannel controlServer,
            ServerSocketChannel eventServer,
            BridgeBootstrapDescriptor descriptor,
            CountDownLatch release,
            AtomicReference<Throwable> failure) {
        try (SocketChannel controlSocket = controlServer.accept();
                SocketChannel eventSocket = eventServer.accept()) {
            FramedEnvelopeChannel control = new FramedEnvelopeChannel(
                    controlSocket, controlSocket, Channel.CHANNEL_CONTROL, MAX_FRAME_BYTES);
            Envelope bridgeEnvelope = control.read();
            assert bridgeEnvelope.getMessageType().equals(BridgeIpcWorker.BRIDGE_HELLO_TYPE);
            BridgeHello bridgeHello = BridgeHello.parseFrom(bridgeEnvelope.getPayload());
            assert bridgeHello.getSessionId().equals("session-worker");

            BootstrapDescriptorAdapter.AdaptedDescriptor adapted =
                    BootstrapDescriptorAdapter.adapt(descriptor);
            HandshakeGate proofGate =
                    new HandshakeGate(adapted.expected(), new BridgePhaseMachine());
            HandshakeGate.CoreHelloData unsigned = new HandshakeGate.CoreHelloData(
                    1,
                    0,
                    "session-worker",
                    3,
                    Set.of(HandshakeGate.HANDSHAKE_CAPABILITY),
                    500,
                    MAX_FRAME_BYTES,
                    "0".repeat(64));
            CoreHello coreHello = CoreHello.newBuilder()
                    .setProtocol(ProtocolVersion.newBuilder().setMajor(1))
                    .setSessionId("session-worker")
                    .setGeneration(3)
                    .addAcceptedCapabilities(capability())
                    .setHeartbeatIntervalMs(500)
                    .setMaxFrameBytes(MAX_FRAME_BYTES)
                    .setProof(ByteString.copyFrom(
                            HexFormat.of().parseHex(proofGate.proofForCoreHello(unsigned))))
                    .build();
            control.write(envelope(1, BridgeIpcWorker.CORE_HELLO_TYPE, coreHello.toByteString()));
            Heartbeat heartbeat = Heartbeat.newBuilder()
                    .setGeneration(3)
                    .setMonotonicNs(1)
                    .build();
            control.write(envelope(2, BridgeIpcWorker.HEARTBEAT_TYPE, heartbeat.toByteString()));
            release.await();
        } catch (Throwable error) {
            failure.set(error);
        }
    }

    private static BridgeIpcWorker.Notice awaitNotice(
            BridgeIpcWorker worker, Duration timeout) throws Exception {
        AtomicReference<BridgeIpcWorker.Notice> result = new AtomicReference<>();
        long deadline = System.nanoTime() + timeout.toNanos();
        while (result.get() == null && System.nanoTime() < deadline) {
            worker.drainClientNotices(1, result::set);
            if (result.get() == null) {
                Thread.sleep(5);
            }
        }
        return result.get();
    }

    private static ServerSocketChannel server() throws Exception {
        ServerSocketChannel server = ServerSocketChannel.open(StandardProtocolFamily.INET);
        server.bind(new InetSocketAddress("127.0.0.1", 0));
        return server;
    }

    private static BridgeBootstrapDescriptor descriptor(int controlPort, int eventPort) {
        return BridgeBootstrapDescriptor.newBuilder()
                .setProtocol(ProtocolVersion.newBuilder().setMajor(1))
                .setKinId("kin-worker")
                .setSessionId("session-worker")
                .setGeneration(3)
                .setClientInstanceId("client-worker")
                .setBundleDigest(DIGEST)
                .setBridgeDigest(DIGEST)
                .setLaunchNonce(ByteString.copyFrom(new byte[32]))
                .setSessionKey(ByteString.copyFrom(new byte[32]))
                .addAdvertisedCapabilities(capability())
                .addEndpoints(endpoint(Channel.CHANNEL_CONTROL, controlPort))
                .addEndpoints(endpoint(Channel.CHANNEL_EVENT, eventPort))
                .setMaxFrameBytes(MAX_FRAME_BYTES)
                .build();
    }

    private static Envelope envelope(long sequence, String type, ByteString payload) {
        return Envelope.newBuilder()
                .setProtocol(ProtocolVersion.newBuilder().setMajor(1))
                .setMessageType(type)
                .setChannel(Channel.CHANNEL_CONTROL)
                .setSequence(sequence)
                .setKinId("kin-worker")
                .setSessionId("session-worker")
                .setGeneration(3)
                .setClientInstanceId("client-worker")
                .setMonotonicNs(sequence)
                .setPayload(payload)
                .build();
    }

    private static IpcEndpoint endpoint(Channel channel, int port) {
        return IpcEndpoint.newBuilder()
                .setChannel(channel)
                .setTransport(EndpointTransport.ENDPOINT_TRANSPORT_LOOPBACK_TCP)
                .setHost("127.0.0.1")
                .setPort(port)
                .build();
    }

    private static Capability capability() {
        return Capability.newBuilder()
                .setName(HandshakeGate.HANDSHAKE_CAPABILITY)
                .setVersion(1)
                .build();
    }

    private static void makePrivateIfSupported(Path path) throws Exception {
        try {
            Files.setPosixFilePermissions(
                    path, Set.of(PosixFilePermission.OWNER_READ, PosixFilePermission.OWNER_WRITE));
        } catch (UnsupportedOperationException ignored) {
            // Windows session-directory ACLs are validated by the launcher.
        }
    }
}
