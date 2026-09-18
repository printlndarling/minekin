import com.google.protobuf.ByteString;
import io.minekin.protocol.v1.BridgeBootstrapDescriptor;
import io.minekin.protocol.v1.BridgeHello;
import io.minekin.protocol.v1.Capability;
import io.minekin.protocol.v1.Channel;
import io.minekin.protocol.v1.CoreHello;
import io.minekin.protocol.v1.EndpointTransport;
import io.minekin.protocol.v1.IpcEndpoint;
import io.minekin.protocol.v1.ProtocolVersion;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.attribute.PosixFilePermission;
import java.util.HexFormat;
import java.util.Set;
import org.minekin.bridge.protocol.BootstrapDescriptorAdapter;
import org.minekin.bridge.protocol.DescriptorLoader;
import org.minekin.bridge.protocol.HandshakeGate;

/** Executable adapter contract check that does not require Fabric or Java 21. */
public final class BridgeProtoAdapterSelfTest {
    private static final String DIGEST = "ab".repeat(32);

    private BridgeProtoAdapterSelfTest() {}

    public static void main(String[] arguments) throws Exception {
        BridgeBootstrapDescriptor descriptor = descriptor("127.0.0.1");
        BootstrapDescriptorAdapter.AdaptedDescriptor adapted =
                BootstrapDescriptorAdapter.adapt(descriptor);
        assert adapted.expected().sessionId().equals("session-1");
        assert adapted.expected().capabilities().equals(Set.of(HandshakeGate.HANDSHAKE_CAPABILITY));
        assert adapted.endpoints().control().getPort() == 26001;
        assert adapted.endpoints().event().getPort() == 26002;

        org.minekin.bridge.runtime.BridgePhaseMachine phases =
                new org.minekin.bridge.runtime.BridgePhaseMachine();
        phases.transition(org.minekin.bridge.runtime.BridgePhaseMachine.Phase.IPC_CONNECTING);
        HandshakeGate gate = new HandshakeGate(adapted.expected(), phases);
        BridgeHello bridgeHello = BootstrapDescriptorAdapter.toProto(gate.bridgeHello());
        assert bridgeHello.getSessionId().equals("session-1");
        assert bridgeHello.getCapabilitiesCount() == 1;

        HandshakeGate.CoreHelloData unsignedCoreHello = new HandshakeGate.CoreHelloData(
                1,
                0,
                "session-1",
                1,
                Set.of(HandshakeGate.HANDSHAKE_CAPABILITY),
                1_000,
                1_048_576,
                "0".repeat(64));
        CoreHello coreHello = CoreHello.newBuilder()
                .setProtocol(ProtocolVersion.newBuilder().setMajor(1))
                .setSessionId("session-1")
                .setGeneration(1)
                .addAcceptedCapabilities(capability())
                .setHeartbeatIntervalMs(1_000)
                .setMaxFrameBytes(1_048_576)
                .setProof(ByteString.copyFrom(
                        HexFormat.of().parseHex(gate.proofForCoreHello(unsignedCoreHello))))
                .build();
        assert gate.accept(BootstrapDescriptorAdapter.fromProto(coreHello));

        Path descriptorPath = Files.createTempFile("minekin-bootstrap-", ".pb");
        makePrivateIfSupported(descriptorPath);
        Files.write(descriptorPath, descriptor.toByteArray());
        assert DescriptorLoader.loadAndDelete(descriptorPath).equals(descriptor);
        assert Files.notExists(descriptorPath);

        boolean rejected = false;
        try {
            BootstrapDescriptorAdapter.adapt(descriptor("0.0.0.0"));
        } catch (IllegalArgumentException expected) {
            rejected = true;
        }
        assert rejected : "non-loopback endpoint was accepted";
        System.out.println("Minekin Bridge protobuf adapter self-test: OK");
    }

    private static BridgeBootstrapDescriptor descriptor(String host) {
        return BridgeBootstrapDescriptor.newBuilder()
                .setProtocol(ProtocolVersion.newBuilder().setMajor(1))
                .setKinId("kin-1")
                .setSessionId("session-1")
                .setGeneration(1)
                .setClientInstanceId("client-1")
                .setBundleDigest(DIGEST)
                .setBridgeDigest(DIGEST)
                .setLaunchNonce(ByteString.copyFrom(new byte[32]))
                .setSessionKey(ByteString.copyFrom(new byte[32]))
                .addAdvertisedCapabilities(capability())
                .addEndpoints(endpoint(Channel.CHANNEL_CONTROL, host, 26001))
                .addEndpoints(endpoint(Channel.CHANNEL_EVENT, host, 26002))
                .setMaxFrameBytes(1_048_576)
                .build();
    }

    private static Capability capability() {
        return Capability.newBuilder()
                .setName(HandshakeGate.HANDSHAKE_CAPABILITY)
                .setVersion(1)
                .build();
    }

    private static IpcEndpoint endpoint(Channel channel, String host, int port) {
        return IpcEndpoint.newBuilder()
                .setChannel(channel)
                .setTransport(EndpointTransport.ENDPOINT_TRANSPORT_LOOPBACK_TCP)
                .setHost(host)
                .setPort(port)
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
