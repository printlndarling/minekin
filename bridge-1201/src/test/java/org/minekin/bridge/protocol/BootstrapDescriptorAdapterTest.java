package org.minekin.bridge.protocol;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import com.google.protobuf.ByteString;
import io.minekin.protocol.v1.BridgeBootstrapDescriptor;
import io.minekin.protocol.v1.Capability;
import io.minekin.protocol.v1.Channel;
import io.minekin.protocol.v1.EndpointTransport;
import io.minekin.protocol.v1.IpcEndpoint;
import io.minekin.protocol.v1.ProtocolVersion;
import org.junit.jupiter.api.Test;
import org.minekin.bridge.runtime.ClientRuntimeIdentity;

/**
 * The versions the Bridge puts on the wire are the ones the client is running, not the
 * ones the descriptor happens to carry.
 *
 * <p>A bootstrap descriptor is written by the Launcher, and the whole point of the
 * identity record is that the Bridge reports itself from the live loader rather than
 * repeating a declaration it was handed. So {@code adapt} has to route the supplied
 * identity into the {@link HandshakeGate.Expected} it builds — and refuse outright when
 * that identity names a recipe this 1.20.1 root does not run.
 */
final class BootstrapDescriptorAdapterTest {

    private static final String DIGEST = "0".repeat(64);

    @Test
    void adaptRoutesTheRealRuntimeVersionsIntoTheHandshake() {
        BootstrapDescriptorAdapter.AdaptedDescriptor adapted =
                BootstrapDescriptorAdapter.adapt(
                        descriptor(), new ClientRuntimeIdentity("1.20.1", "0.19.5"));

        assertEquals("1.20.1", adapted.expected().minecraftVersion());
        assertEquals("0.19.5", adapted.expected().fabricLoaderVersion());
    }

    @Test
    void anIdentityThatIsNotThisRootsRecipeIsRefused() {
        assertThrows(
                IllegalArgumentException.class,
                () ->
                        BootstrapDescriptorAdapter.adapt(
                                descriptor(), new ClientRuntimeIdentity("1.21.4", "0.16.9")));
    }

    private static BridgeBootstrapDescriptor descriptor() {
        return BridgeBootstrapDescriptor.newBuilder()
                .setProtocol(ProtocolVersion.newBuilder().setMajor(1).setMinor(0))
                .setKinId("kin-1")
                .setSessionId("session-1")
                .setGeneration(1L)
                .setClientInstanceId("instance-1")
                .setBundleDigest(DIGEST)
                .setBridgeDigest(DIGEST)
                .setLaunchNonce(ByteString.copyFrom(new byte[32]))
                .setSessionKey(ByteString.copyFrom(new byte[32]))
                .addAdvertisedCapabilities(
                        Capability.newBuilder()
                                .setName(HandshakeGate.HANDSHAKE_CAPABILITY)
                                .setVersion(1))
                .addEndpoints(endpoint(Channel.CHANNEL_CONTROL, 4001))
                .addEndpoints(endpoint(Channel.CHANNEL_EVENT, 4002))
                .setMaxFrameBytes(65536)
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
}
