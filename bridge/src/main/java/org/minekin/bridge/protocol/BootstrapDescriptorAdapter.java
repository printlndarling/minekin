package org.minekin.bridge.protocol;

import io.minekin.protocol.v1.BridgeBootstrapDescriptor;
import io.minekin.protocol.v1.BridgeHello;
import io.minekin.protocol.v1.BridgePhase;
import io.minekin.protocol.v1.Capability;
import io.minekin.protocol.v1.Channel;
import io.minekin.protocol.v1.CoreHello;
import io.minekin.protocol.v1.EndpointTransport;
import io.minekin.protocol.v1.IpcEndpoint;
import io.minekin.protocol.v1.ProtocolVersion;
import java.util.HashSet;
import java.util.HexFormat;
import java.util.Objects;
import java.util.Set;
import org.minekin.bridge.runtime.ClientRuntimeIdentity;

/** Maps generated protobuf values into the dependency-free handshake kernel. */
public final class BootstrapDescriptorAdapter {
    private BootstrapDescriptorAdapter() {}

    public static AdaptedDescriptor adapt(
            BridgeBootstrapDescriptor descriptor, ClientRuntimeIdentity identity) {
        Objects.requireNonNull(identity, "identity");
        if (!descriptor.hasProtocol()
                || descriptor.getProtocol().getMajor() < 1
                || descriptor.getGeneration() < 1
                || descriptor.getLaunchNonce().size() != 32
                || descriptor.getSessionKey().size() != 32
                || descriptor.getMaxFrameBytes() < HandshakeGate.MIN_FRAME_BYTES
                || descriptor.getMaxFrameBytes() > HandshakeGate.MAX_FRAME_BYTES) {
            throw new IllegalArgumentException("bootstrap descriptor has invalid protocol bounds");
        }
        Set<String> capabilities = capabilityNames(descriptor.getAdvertisedCapabilitiesList());
        Endpoints endpoints = endpoints(descriptor);
        byte[] nonce = descriptor.getLaunchNonce().toByteArray();
        byte[] key = descriptor.getSessionKey().toByteArray();
        try {
            HandshakeGate.Expected expected = new HandshakeGate.Expected(
                    descriptor.getProtocol().getMajor(),
                    descriptor.getProtocol().getMinor(),
                    descriptor.getKinId(),
                    descriptor.getSessionId(),
                    descriptor.getGeneration(),
                    descriptor.getClientInstanceId(),
                    descriptor.getBundleDigest(),
                    descriptor.getBridgeDigest(),
                    identity.minecraftVersion(),
                    identity.fabricLoaderVersion(),
                    nonce,
                    key,
                    capabilities);
            return new AdaptedDescriptor(expected, endpoints, descriptor.getMaxFrameBytes());
        } finally {
            java.util.Arrays.fill(nonce, (byte) 0);
            java.util.Arrays.fill(key, (byte) 0);
        }
    }

    public static BridgeHello toProto(HandshakeGate.BridgeHelloData hello) {
        BridgeHello.Builder result = BridgeHello.newBuilder()
                .setProtocol(ProtocolVersion.newBuilder()
                        .setMajor(hello.protocolMajor())
                        .setMinor(hello.protocolMinor()))
                .setLaunchNonce(hello.launchNonce())
                .setProof(hello.proof())
                .setKinId(hello.kinId())
                .setSessionId(hello.sessionId())
                .setGeneration(hello.generation())
                .setClientInstanceId(hello.clientInstanceId())
                .setBundleDigest(hello.bundleDigest())
                .setBridgeDigest(hello.bridgeDigest())
                .setMinecraftVersion(hello.minecraftVersion())
                .setFabricLoaderVersion(hello.fabricLoaderVersion())
                .setPhase(BridgePhase.BRIDGE_PHASE_IPC_CONNECTING);
        hello.capabilities().stream().sorted().forEach(name -> result.addCapabilities(
                Capability.newBuilder().setName(name).setVersion(1)));
        return result.build();
    }

    public static HandshakeGate.CoreHelloData fromProto(CoreHello hello) {
        if (!hello.hasProtocol()) {
            throw new IllegalArgumentException("Core hello protocol is required");
        }
        Set<String> capabilities = capabilityNames(hello.getAcceptedCapabilitiesList());
        return new HandshakeGate.CoreHelloData(
                hello.getProtocol().getMajor(),
                hello.getProtocol().getMinor(),
                hello.getSessionId(),
                hello.getGeneration(),
                capabilities,
                hello.getHeartbeatIntervalMs(),
                hello.getMaxFrameBytes(),
                HexFormat.of().formatHex(hello.getProof().toByteArray()));
    }

    private static Set<String> capabilityNames(java.util.List<Capability> capabilities) {
        Set<String> names = new HashSet<>();
        for (Capability capability : capabilities) {
            if (capability.getVersion() != 1
                    || capability.getName().isBlank()
                    || !names.add(capability.getName())) {
                throw new IllegalArgumentException("capabilities must be unique reviewed v1 names");
            }
        }
        return Set.copyOf(names);
    }

    private static Endpoints endpoints(BridgeBootstrapDescriptor descriptor) {
        IpcEndpoint control = null;
        IpcEndpoint event = null;
        for (IpcEndpoint endpoint : descriptor.getEndpointsList()) {
            validateEndpoint(endpoint);
            if (endpoint.getChannel() == Channel.CHANNEL_CONTROL && control == null) {
                control = endpoint;
            } else if (endpoint.getChannel() == Channel.CHANNEL_EVENT && event == null) {
                event = endpoint;
            } else {
                throw new IllegalArgumentException("descriptor endpoints must be unique by channel");
            }
        }
        if (control == null || event == null || control.getTransport() != event.getTransport()) {
            throw new IllegalArgumentException("control and event endpoints must share one transport");
        }
        return new Endpoints(control, event);
    }

    private static void validateEndpoint(IpcEndpoint endpoint) {
        if (endpoint.getTransport() == EndpointTransport.ENDPOINT_TRANSPORT_UNIX_DOMAIN_SOCKET) {
            if (endpoint.getUnixSocketPath().isBlank()
                    || !endpoint.getHost().isBlank()
                    || endpoint.getPort() != 0) {
                throw new IllegalArgumentException("Unix endpoint fields are inconsistent");
            }
        } else if (endpoint.getTransport() == EndpointTransport.ENDPOINT_TRANSPORT_LOOPBACK_TCP) {
            if (!"127.0.0.1".equals(endpoint.getHost())
                    || endpoint.getPort() < 1
                    || endpoint.getPort() > 65535
                    || !endpoint.getUnixSocketPath().isBlank()) {
                throw new IllegalArgumentException("TCP endpoint must be IPv4 loopback only");
            }
        } else {
            throw new IllegalArgumentException("endpoint transport is unspecified");
        }
    }

    public record AdaptedDescriptor(
            HandshakeGate.Expected expected, Endpoints endpoints, int maxFrameBytes) {}

    public record Endpoints(IpcEndpoint control, IpcEndpoint event) {}
}
